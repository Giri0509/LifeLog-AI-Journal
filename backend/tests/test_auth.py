"""HTTP account and isolation checks against an isolated SQLite database."""
import hashlib
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
import test_diary_summary as fixtures
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app, get_db
from app.auth import get_auth_db, COOKIE, _attempts, verify_password
from app.chat_history import get_chat_db
from app.models import Base, DiaryEntry, User, UserSession, ChatConversation

class AccountTests(unittest.TestCase):
    def setUp(self):
        _attempts.clear()
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
        @event.listens_for(self.engine,'connect')
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add(ChatConversation(title='Legacy synthetic chat'))
            db.add(DiaryEntry(title='Legacy test', content='Synthetic private content', entry_date=date(2026,10,1)))
            db.commit()
        def get_test_db():
            with Session(self.engine) as db:
                yield db
        for dependency in (get_db, get_auth_db, get_chat_db):
            app.dependency_overrides[dependency] = get_test_db
        self.owner = TestClient(app)
        self.other = TestClient(app)
        self.credentials = {'username':'Owner','password':'synthetic-password-123'}
        fixtures.chat.ask_diary_chatbot.return_value = {'answer':'Synthetic response','sources':[]}

    def tearDown(self):
        self.owner.close()
        self.other.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register(self, client, username='Owner'):
        response = client.post('/api/auth/register', json={**self.credentials,'username':username})
        self.assertEqual(response.status_code,201, response.text)
        return response.json()['user']['id']

    def test_private_endpoints_require_login(self):
        self.assertEqual(self.owner.get('/api/health').status_code,200)
        for method, url, payload in [
            ('get','/api/diary',None), ('get','/api/conversations',None),
            ('post','/api/diary-summary',{'period':'monthly','anchor_date':'2026-10-01'}),
            ('post','/api/diary-insights',{'period':'monthly','anchor_date':'2026-10-01'}),
            ('post','/api/chat',{'question':'Test'}), ('post','/api/analyze-mood',{'text':'Test'}),
            ('post','/api/diary',{'title':'Test','content':'Test','entry_date':'2026-10-01'}),
        ]:
            response = self.owner.request(method,url,**({'json':payload} if payload else {}))
            self.assertEqual(response.status_code,401, url)

    def test_first_account_claim_and_private_crud(self):
        owner_id = self.register(self.owner)
        self.register(self.other,'Other')
        self.assertEqual(self.owner.get('/api/diary').json()['total'],1)
        self.assertEqual(self.other.get('/api/diary').json()['total'],0)
        self.assertEqual(len(self.owner.get('/api/conversations').json()['conversations']),1)
        self.assertEqual(self.other.get('/api/conversations').json()['conversations'],[])
        entry_id = self.owner.get('/api/diary').json()['entries'][0]['id']
        self.assertEqual(self.other.delete(f'/api/diary/{entry_id}').status_code,404)
        self.assertEqual(self.other.put(f'/api/diary/{entry_id}',json={'title':'Intrusion','content':'Test','entry_date':'2026-10-01'}).status_code,404)
        with Session(self.engine) as db:
            self.assertEqual(db.get(DiaryEntry,entry_id).user_id,owner_id)
        with patch('app.main.analyze_mood',return_value=None), patch('app.main.sync_diary_safely'):
            response = self.other.post('/api/diary',json={'title':'Other diary','content':'Synthetic','entry_date':'2026-10-02'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.owner.get('/api/diary').json()['total'],1)
        self.assertEqual(self.other.get('/api/diary').json()['total'],1)

    def test_login_cookie_rotation_logout_and_expiry(self):
        user_id = self.register(self.owner)
        token = self.owner.cookies.get(COOKIE)
        with Session(self.engine) as db:
            user = db.get(User,user_id)
            self.assertNotEqual(user.password_hash,self.credentials['password'])
            self.assertTrue(verify_password(self.credentials['password'],user.password_hash))
            self.assertIsNotNone(db.get(UserSession,hashlib.sha256(token.encode()).hexdigest()))
        response = self.owner.post('/api/auth/login',json=self.credentials)
        self.assertEqual(response.status_code,200)
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertIn('SameSite=strict',response.headers['set-cookie'])
        self.assertNotEqual(self.owner.cookies.get(COOKIE),token)
        self.assertEqual(self.other.get('/api/auth/me',headers={'cookie':f'{COOKIE}={token}'}).status_code,401)
        current = self.owner.cookies.get(COOKIE)
        with Session(self.engine) as db:
            db.get(UserSession,hashlib.sha256(current.encode()).hexdigest()).expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.owner.get('/api/auth/me').status_code,401)
        self.owner.post('/api/auth/login',json=self.credentials)
        self.assertEqual(self.owner.post('/api/auth/logout').status_code,200)
        self.assertEqual(self.owner.get('/api/diary').status_code,401)

    def test_invalid_credentials_and_origin(self):
        self.register(self.owner)
        self.assertEqual(self.other.post('/api/auth/register',json={**self.credentials,'username':'OWNER'}).status_code,409)
        self.assertEqual(self.other.post('/api/auth/login',json={**self.credentials,'password':'incorrect-password'}).status_code,401)
        response = self.owner.post('/api/auth/logout',headers={'origin':'https://untrusted.example'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.owner.get('/api/auth/me').status_code,200)
        self.assertEqual(self.owner.post('/api/auth/login',json={**self.credentials,'password':'short'}).status_code,422)

    def test_login_attempts_are_limited(self):
        self.register(self.owner)
        for _ in range(20):
            response = self.other.post('/api/auth/login',json={**self.credentials,'password':'wrong-synthetic-password'})
        self.assertEqual(response.status_code,429)

    def test_conversation_isolation(self):
        self.register(self.owner)
        self.register(self.other,'Other')
        chat_id = self.owner.post('/api/conversations').json()['id']
        self.assertEqual(self.owner.post(f'/api/conversations/{chat_id}/messages',json={'question':'Synthetic question'}).status_code,200)
        self.assertEqual(self.other.get('/api/conversations').json()['conversations'],[])
        self.assertEqual(self.other.get(f'/api/conversations/{chat_id}/messages').status_code,404)
        self.assertEqual(self.other.post(f'/api/conversations/{chat_id}/messages',json={'question':'Intrusion'}).status_code,404)
        self.assertEqual(len(self.owner.get(f'/api/conversations/{chat_id}/messages').json()['messages']),2)

    def test_summary_and_insight_isolation(self):
        self.register(self.owner)
        other_id = self.register(self.other,'Other')
        with Session(self.engine) as db:
            db.add(DiaryEntry(user_id=other_id,title='Other private diary',content='Synthetic',entry_date=date(2026,10,2)))
            db.commit()
        for path in ('diary-summary','diary-insights'):
            response = self.other.post(f'/api/{path}',json={'period':'monthly','anchor_date':'2026-10-23'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['entry_count'],1)

if __name__ == '__main__':
    unittest.main()
