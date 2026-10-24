"""Synthetic retrieval evaluation; no personal diaries or live AI calls."""
import json
import os
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['OPENAI_API_KEY'] = 'synthetic-test-key'
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document

class SyntheticEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[0.0, 1.0, 0.0] if 'UNRELATED' in text else [1.0, 0.0, 0.0] for text in texts]
    def embed_query(self, text):
        return [1.0, 0.0, 0.0]

embedding = SyntheticEmbeddings()
fake = types.ModuleType('app.services.embedding_service')
fake.get_embedding_model = lambda: embedding
sys.modules[fake.__name__] = fake
from app.services import rag_service as rag
from app.services import chat_service as chat
from app.services.retrieval_rules import date_scope, retrieval_request
from langchain_chroma import Chroma
from chromadb.config import Settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base, DiaryEntry

class RetrievalEvaluation(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([DiaryEntry(id=i, user_id=1 if i < 4 else 2, title='Synthetic', content='Synthetic', entry_date=date(2026,9,15) if i == 3 else date(2026,10,i)) for i in range(1,5)])
            db.commit()
        database = types.ModuleType('app.database')
        database.SessionLocal = lambda: Session(self.engine)
        self.previous_database = sys.modules.get('app.database')
        sys.modules['app.database'] = database
        self.store = Chroma(collection_name='step66_' + uuid4().hex, embedding_function=embedding,
                            client_settings=Settings(anonymized_telemetry=False))
        self.store.add_documents([
            Document(page_content='Running with a friend brought joy at the park.', metadata={'entry_id':1,'title':'Park','entry_date':'2026-10-01'}),
            Document(page_content='Running with a friend brought joy at the park.', metadata={'entry_id':1,'title':'Park','entry_date':'2026-10-01'}),
            Document(page_content='Running entry from another account.', metadata={'entry_id':4,'title':'Private','entry_date':'2026-10-04'}),
            Document(page_content='UNRELATED cooking instructions.', metadata={'entry_id':2,'title':'Cooking','entry_date':'2026-10-02'}),
            Document(page_content='Running a marathon during September.', metadata={'entry_id':3,'title':'Marathon','entry_date':'2026-09-15'}),
        ])
        self.store_patch = patch.object(rag, 'get_vector_store', return_value=self.store)
        self.store_patch.start()
        self.threshold_patch = patch.dict(os.environ, {'RAG_MIN_COSINE_SIMILARITY':'0.30'})
        self.threshold_patch.start()
    def tearDown(self):
        self.store_patch.stop()
        self.threshold_patch.stop()
        self.store.delete_collection()
        if self.previous_database is None:
            sys.modules.pop('app.database', None)
        else:
            sys.modules['app.database'] = self.previous_database
        self.engine.dispose()

    def test_expected_sources_and_deduplication(self):
        result = rag.search_diary_entries(user_id=1, query='What brought joy while running?')
        self.assertEqual({d.metadata['entry_id'] for d in result}, {1,3})
        self.assertEqual(len(result), 2)

    def test_date_filter_before_ranking(self):
        result = rag.search_diary_entries(user_id=1, query='Running', date_range=(date(2026,9,1),date(2026,9,30)))
        self.assertEqual([d.metadata['entry_id'] for d in result], [3])

    def test_no_relevant_or_dated_results(self):
        result = rag.search_diary_entries(user_id=1, query='Running', date_range=(date(2026,10,2),date(2026,10,2)))
        self.assertEqual(result, [])
        self.assertEqual(rag.search_diary_entries(user_id=1, query='Running', date_range=(date(2020,1,1),date(2020,1,31))), [])
        self.assertEqual(rag.search_diary_entries(user_id=1, query='  '), [])

    def test_other_users_and_orphans_are_excluded(self):
        self.assertEqual(rag.search_diary_entries(user_id=99, query='Running'), [])
        result = rag.search_diary_entries(user_id=2, query='Running')
        self.assertEqual([d.metadata['entry_id'] for d in result], [4])
        self.store.add_documents([Document(page_content='Running orphaned vector.', metadata={'entry_id':999,'title':'Orphan','entry_date':'2026-10-01'})])
        result = rag.search_diary_entries(user_id=1, query='Running')
        self.assertNotIn(999, [d.metadata['entry_id'] for d in result])

    def test_metric_independent_cosine(self):
        self.assertAlmostEqual(rag.cosine_similarity([2,0], [9,0]), 1)
        self.assertEqual(rag.cosine_similarity([1,0], [0,1]), 0)
        self.assertEqual(rag.cosine_similarity([0,0], [1,0]), -1)
        with patch.dict(os.environ, {'RAG_MIN_COSINE_SIMILARITY':'nan'}):
            with self.assertRaises(ValueError):
                rag.search_diary_entries(user_id=1, query='Running')

class DateEvaluation(unittest.TestCase):
    def test_calendar_boundaries(self):
        today = date(2026,1,2)
        self.assertEqual(date_scope('last month',today), (date(2025,12,1),date(2025,12,31)))
        self.assertEqual(date_scope('this week',today), (date(2025,12,29),date(2026,1,4)))
        self.assertEqual(date_scope('February 2024',today), (date(2024,2,1),date(2024,2,29)))
        self.assertEqual(date_scope('last 7 days',today), (date(2025,12,27),today))
        self.assertEqual(date_scope('between 2025-01-01 and 2025-01-31',today), (date(2025,1,1),date(2025,1,31)))

    def test_invalid_dates(self):
        for question in ['on 2026-02-30','2026-10-31 to 2026-10-01','past 0 days', 'since 2026-10-01', 'last Friday', 'this month and last month', 'during October']:
            with self.assertRaises(ValueError):
                date_scope(question,date(2026,10,23))

    def test_followup_uses_user_context_only(self):
        query, scope = retrieval_request('Why did that help?', [
            {'role':'user','content':'What made me happy last month?'},
            {'role':'assistant','content':'Fabricated assistant event'},
        ], date(2026,10,23))
        self.assertNotIn('Fabricated',query)
        self.assertEqual(scope,(date(2026,9,1),date(2026,9,30)))
        self.assertIsNone(retrieval_request('Tell me about work', [{'role':'user','content':'last month'}], date(2026,10,23))[1])

class AnswerEvaluation(unittest.TestCase):
    def setUp(self):
        self.docs = [Document(page_content='A synthetic walk.', metadata={'entry_id':1,'title':'Walk','entry_date':'2026-10-01'}),
                     Document(page_content='A synthetic run.', metadata={'entry_id':2,'title':'Run','entry_date':'2026-10-02'})]
        self.search_patch = patch.object(chat,'search_diary_entries',return_value=self.docs)
        self.search = self.search_patch.start()
        self.prompt_patch = patch.object(chat,'prompt')
        self.prompt = self.prompt_patch.start()
        self.chain = self.prompt.__or__.return_value
    def tearDown(self):
        self.search_patch.stop()
        self.prompt_patch.stop()
    def reply(self, claims):
        self.chain.invoke.return_value = types.SimpleNamespace(content=json.dumps({'claims':claims}),response_metadata={'finish_reason':'stop'})
    def test_only_cited_sources_returned(self):
        self.reply([{'text':'A walk was recorded.', 'evidence':[{'entry_id':1,'quote':'A synthetic walk.'}]}])
        result = chat.ask_diary_chatbot(user_id=1, question='What did I do?')
        self.assertEqual([s['entry_id'] for s in result['sources']],[1])
        self.assertIn('[Diary 1]',result['answer'])
    def test_unknown_source_is_rejected(self):
        self.reply([{'text':'Unsupported claim', 'evidence':[{'entry_id':999,'quote':'Invented source quote.'}]}])
        result = chat.ask_diary_chatbot(user_id=1, question='What did I do?')
        self.assertEqual(result['sources'],[])
        self.assertNotIn('Unsupported claim',result['answer'])
    def test_no_retrieval_skips_ai(self):
        self.search.return_value = []
        self.assertEqual(chat.ask_diary_chatbot(user_id=1, question='An unsupported question')['sources'],[])
        self.chain.invoke.assert_not_called()
    def test_empty_claims_and_invalid_json(self):
        self.reply([])
        self.assertEqual(chat.ask_diary_chatbot(user_id=1, question='Question')['sources'],[])
        self.chain.invoke.return_value.content = 'Not JSON'
        self.assertEqual(chat.ask_diary_chatbot(user_id=1, question='Question')['sources'],[])
    def test_invented_quote_for_real_id_is_rejected(self):
        self.reply([{'text':'An invented vacation.', 'evidence':[{'entry_id':1,'quote':'A vacation in Paris.'}]}])
        result = chat.ask_diary_chatbot(user_id=1, question='What happened?')
        self.assertEqual(result['sources'], [])
        self.assertNotIn('invented vacation', result['answer'])

    def test_invalid_date_skips_retrieval(self):
        self.assertEqual(chat.ask_diary_chatbot(user_id=1, question='on 2026-02-30')['sources'],[])
        self.search.assert_not_called()

if __name__ == '__main__':
    # Verify the actual prompt template before tests substitute a mock chain.
    chat.prompt.format_messages(context='[]', scope='none', history='[]', question='Test')
    unittest.main()

