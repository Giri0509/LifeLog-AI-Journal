import sys
import types
import unittest
from datetime import date
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Isolate all external dependencies: no real credentials, diaries, vectors or API calls.
client = MagicMock()
mood = types.ModuleType('app.services.mood_analyzer')
mood.client = client
mood.analyze_mood = MagicMock()
sys.modules[mood.__name__] = mood
chat = types.ModuleType('app.services.chat_service')
chat.ask_diary_chatbot = MagicMock()
sys.modules[chat.__name__] = chat
rag = types.ModuleType('app.services.rag_service')
rag.sync_diary_entry = MagicMock()
rag.delete_diary_embeddings = MagicMock()
sys.modules[rag.__name__] = rag
database = types.ModuleType('app.database')
database.SessionLocal = MagicMock()
sys.modules[database.__name__] = database

from app.services.summary_service import period_bounds, summarize_entries, SummaryTooLarge
from app.main import app, get_db, generate_diary_summary, DiarySummaryRequest
from app.models import Base, DiaryEntry
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from pydantic import ValidationError

class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.user = types.SimpleNamespace(id=1)
        client.reset_mock()
        client.with_options.return_value.chat.completions.create.side_effect = None
        client.with_options.return_value.chat.completions.create.return_value = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='A reflection on the recorded days.'), finish_reason='stop')])
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        app.dependency_overrides[get_db] = lambda: self.db


    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def add(self, day, content='Synthetic test entry'):
        self.db.add(DiaryEntry(user_id=self.user.id, title='Test', content=content, entry_date=date.fromisoformat(day), mood_score=7))
        self.db.commit()

    def post(self, period='monthly', anchor='2026-10-23'):
        try:
            data = generate_diary_summary(DiarySummaryRequest(period=period, anchor_date=anchor), self.db, self.user)
            return types.SimpleNamespace(status_code=200, json=lambda: data, text=str(data))
        except ValidationError:
            return types.SimpleNamespace(status_code=422)
        except HTTPException as error:
            return types.SimpleNamespace(status_code=error.status_code, text=str(error.detail))

    def test_calendar_boundaries(self):
        self.assertEqual(period_bounds('weekly', date(2026, 1, 1)), (date(2025, 12, 29), date(2026, 1, 4)))
        self.assertEqual(period_bounds('monthly', date(2024, 2, 10)), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(period_bounds('monthly', date(2026, 12, 15)), (date(2026, 12, 1), date(2026, 12, 31)))

    def test_empty_and_single_day_skip_provider(self):
        self.assertEqual(self.post().json()['status'], 'insufficient_data')
        self.add('2026-10-01')
        self.add('2026-10-01')
        self.assertEqual(self.post().json()['journaled_days'], 1)
        client.with_options.assert_not_called()

    def test_month_filters_orders_and_includes_boundaries(self):
        for day in ['2026-11-01', '2026-10-31', '2026-09-30', '2026-10-01']:
            self.add(day)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'complete')
        self.assertEqual([s['entry_date'] for s in data['sources']], ['2026-10-01', '2026-10-31'])
        self.assertEqual(data['entry_count'], 2)
        self.assertEqual(client.with_options.return_value.chat.completions.create.call_args.kwargs['model'], 'gpt-4o-mini')

    def test_week_filters(self):
        for day in ['2026-10-18', '2026-10-19', '2026-10-25', '2026-10-26']:
            self.add(day)
        data = self.post('weekly').json()
        self.assertEqual([s['entry_date'] for s in data['sources']], ['2026-10-19', '2026-10-25'])

    def test_invalid_requests(self):
        self.assertEqual(self.post('yearly').status_code, 422)
        self.assertEqual(self.post(anchor='bad-date').status_code, 422)
        self.assertEqual(self.post(anchor='9999-12-31').status_code, 422)

    def test_provider_failure_is_safe(self):
        self.add('2026-10-01')
        self.add('2026-10-02')
        client.with_options.return_value.chat.completions.create.side_effect = RuntimeError('private upstream payload')
        response = self.post()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private upstream payload', response.text)

    def test_oversized_period_skips_provider(self):
        self.add('2026-10-01', 'x' * 60001)
        self.add('2026-10-02')
        self.assertEqual(self.post().status_code, 413)
        client.with_options.assert_not_called()

    def test_incomplete_provider_response(self):
        self.add('2026-10-01')
        self.add('2026-10-02')
        client.with_options.return_value.chat.completions.create.return_value.choices[0].finish_reason = 'length'
        self.assertEqual(self.post().status_code, 502)

if __name__ == '__main__':
    unittest.main()


