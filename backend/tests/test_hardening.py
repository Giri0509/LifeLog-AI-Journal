"""Security and reliability regressions using synthetic data only."""
import importlib.util
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import test_auth as accounts
from app.main import app, get_db
from app.models import Base, User, DiaryEntry, VectorSyncJob, SchemaMigration
from app.services.vector_sync import enqueue_sync, process_one
from app.migrations import migrate
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

class HardeningApiTests(accounts.AccountTests):
    def test_input_limits_and_secret_redaction(self):
        self.register(self.owner)
        for payload in [
            {'title':'   ','content':'Valid','entry_date':'2026-10-01'},
            {'title':'x'*256,'content':'Valid','entry_date':'2026-10-01'},
            {'title':'Valid','content':'x'*20001,'entry_date':'2026-10-01'},
            {'title':'Valid','content':'Valid','entry_date':'not-a-date'},
            {'title':'Valid','content':'Valid','entry_date':'2026-10-01','user_id':999},
        ]:
            self.assertEqual(self.owner.post('/api/diary',json=payload).status_code,422)
        secret = 'sensitive-password-sentinel' * 20
        response = self.owner.post('/api/auth/login',json={'username':'bad username','password':secret})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('sensitive-password-sentinel',response.text)
        self.assertNotIn('input',response.text)

    def test_oversize_requests_are_rejected(self):
        self.register(self.owner)
        response = self.owner.post('/api/diary',content=b'x'*262145,headers={'content-type':'application/json'})
        self.assertEqual(response.status_code,413)
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_streamed_oversize_requests_are_rejected(self):
        self.register(self.owner)
        response = self.owner.post('/api/diary',content=iter([b'x'*150000,b'y'*150000]),headers={'content-type':'application/json'})
        self.assertEqual(response.status_code,413)

    def test_database_failure_has_safe_message(self):
        self.register(self.owner)
        fake_db = MagicMock()
        fake_db.query.side_effect = SQLAlchemyError('private-diary-and-connection-secret')
        app.dependency_overrides[get_db] = lambda: fake_db
        response = self.owner.get('/api/diary')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private-diary',response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_ai_failure_preserves_diary_and_persistent_sync_job(self):
        self.register(self.owner)
        with patch('app.main.analyze_mood',side_effect=RuntimeError('sensitive provider data')), patch('app.main.sync_diary_safely'):
            response = self.owner.post('/api/diary',json={'title':'Synthetic entry','content':'Synthetic content','entry_date':'2026-10-10'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['warnings'])
        with Session(self.engine) as db:
            self.assertEqual(db.query(VectorSyncJob).count(),1)
            self.assertIsNone(db.get(DiaryEntry,response.json()['entry']['id']).mood_score)

class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id=1,username='synthetic',password_hash='not-a-real-password'))
        self.db.commit()
        self.rag = sys.modules['app.services.rag_service']
        self.rag.sync_diary_entry.reset_mock(side_effect=True)
        self.rag.delete_diary_embeddings.reset_mock(side_effect=True)
    def tearDown(self):
        self.db.close()
        self.engine.dispose()
    def diary(self):
        entry=DiaryEntry(user_id=1,title='Synthetic',content='Original synthetic content',entry_date=date(2026,10,1))
        self.db.add(entry)
        self.db.flush()
        return entry
    def test_pending_work_survives_failure_and_reads_current_row(self):
        entry=self.diary()
        entry_id=entry.id
        enqueue_sync(self.db,entry_id)
        self.db.commit()
        self.rag.sync_diary_entry.side_effect=RuntimeError('private-content-sentinel')
        self.assertFalse(process_one(self.db))
        self.db.close()
        self.db=Session(self.engine)
        job=self.db.query(VectorSyncJob).one()
        self.assertEqual(job.attempts,1)
        self.assertEqual(job.last_error,'RuntimeError')
        self.db.get(DiaryEntry,entry_id).content='Updated synthetic content'
        job.next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        self.db.commit()
        self.rag.sync_diary_entry.side_effect=None
        self.assertTrue(process_one(self.db))
        self.rag.sync_diary_entry.assert_called_with(entry_id,'Synthetic','Updated synthetic content','2026-10-01')
        self.assertEqual(self.db.query(VectorSyncJob).count(),0)
    def test_old_upsert_job_cannot_resurrect_deleted_diary(self):
        entry=self.diary()
        entry_id=entry.id
        enqueue_sync(self.db,entry_id)
        self.db.commit()
        self.db.delete(entry)
        enqueue_sync(self.db,entry_id)
        self.db.commit()
        self.assertTrue(process_one(self.db))
        self.assertTrue(process_one(self.db))
        self.rag.sync_diary_entry.assert_not_called()
        self.rag.delete_diary_embeddings.assert_called_with(entry_id)
    def test_repair_queues_orphans_even_when_no_diaries_exist(self):
        from app.index_diaries import index_diary_entries
        store=MagicMock()
        store.get.return_value={'metadatas':[{'entry_id':99}]}
        with patch('app.index_diaries.run_pending',return_value=0):
            index_diary_entries(session_factory=lambda: Session(self.engine),vector_store=store)
        self.assertEqual([row.entry_id for row in self.db.query(VectorSyncJob).all()],[99])

    def test_diary_and_queue_rollback_together(self):
        entry=self.diary()
        enqueue_sync(self.db,entry.id)
        self.db.rollback()
        self.assertEqual(self.db.query(DiaryEntry).count(),0)
        self.assertEqual(self.db.query(VectorSyncJob).count(),0)

class MigrationTests(unittest.TestCase):
    def test_existing_rows_are_preserved_and_versions_are_idempotent(self):
        engine=create_engine('sqlite://')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE diary_entries (id INTEGER PRIMARY KEY, title TEXT NOT NULL)'))
            connection.execute(text("INSERT INTO diary_entries VALUES (1, 'Synthetic legacy row')"))
        migrate(engine)
        migrate(engine)
        self.assertIn('user_id',{c['name'] for c in inspect(engine).get_columns('diary_entries')})
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT title FROM diary_entries')).scalar(),'Synthetic legacy row')
            self.assertEqual(connection.execute(text('SELECT count(*) FROM schema_migrations')).scalar(),2)
        engine.dispose()

class MoodValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[1]/'app'/'services'/'mood_analyzer.py'
        spec=importlib.util.spec_from_file_location('actual_mood_for_test',path)
        cls.module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=cls.module
        with patch.dict('os.environ',{'OPENAI_API_KEY':'synthetic-test-key'}):
            spec.loader.exec_module(cls.module)
    def test_invalid_scores_and_emotions_are_rejected(self):
        valid={'mood':'Happy','mood_score':8,'emotions':['joy'],'summary':'Synthetic summary.'}
        self.assertEqual(self.module.MoodAnalysis.model_validate(valid).mood_score,8)
        for value in [0,11,True,'8']:
            with self.assertRaises(ValidationError):
                self.module.MoodAnalysis.model_validate({**valid,'mood_score':value})
        with self.assertRaises(ValidationError):
            self.module.MoodAnalysis.model_validate({**valid,'emotions':['a','b','c','d']})
        with self.assertRaises(ValidationError):
            self.module.MoodAnalysis.model_validate({**valid,'summary':'   '})
    def test_invalid_provider_response_and_timeouts(self):
        mock=MagicMock()
        mock.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(finish_reason='length',message=SimpleNamespace(content='{}'))])
        with patch.object(self.module,'client',mock):
            with self.assertRaises(ValueError):
                self.module.analyze_mood('Synthetic entry')
            mock.chat.completions.create.side_effect=TimeoutError()
            with self.assertRaises(TimeoutError):
                self.module.analyze_mood('Synthetic entry')

if __name__=='__main__':
    unittest.main()
