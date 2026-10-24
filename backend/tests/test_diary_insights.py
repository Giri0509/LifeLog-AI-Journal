import json
import unittest
from datetime import date
from types import SimpleNamespace
from test_diary_summary import SummaryTests, client
from app.services.insight_service import analyze_patterns
from app.main import generate_diary_insights, DiarySummaryRequest

class InsightTests(SummaryTests):
    def records(self):
        return [SimpleNamespace(id=1, entry_date=date(2026,10,1), title='Test', content='Ran today', emotions=[' Joy ', 'joy', 'pride'], mood_score=8),
                SimpleNamespace(id=2, entry_date=date(2026,10,2), title='Test', content='Ran again', emotions=['JOY'], mood_score=2),
                SimpleNamespace(id=3, entry_date=date(2026,10,2), title='Test', content='Test', emotions=None, mood_score=4)]

    def reply(self, themes):
        client.with_options.return_value.chat.completions.create.return_value.choices[0].message.content = json.dumps({'themes': themes})

    def run_patterns(self, entries=None):
        return analyze_patterns(self.records() if entries is None else entries, 'monthly', date(2026,10,1), date(2026,10,31))

    def test_counts_and_daily_averages(self):
        self.reply([])
        result = self.run_patterns()
        self.assertEqual(result['emotions'], [{'emotion':'joy','count':2}, {'emotion':'pride','count':1}])
        self.assertEqual(result['highest_days'][0]['average'], 8)
        self.assertEqual(result['lowest_days'][0]['average'], 3)
        self.assertEqual(result['emotion_entry_count'], 2)

    def test_valid_theme_dates(self):
        self.reply([{'title':'Running', 'observation':'Running appears on two days.', 'entry_ids':[1,2]}])
        result = self.run_patterns()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual([s['entry_date'] for s in result['themes'][0]['sources']], ['2026-10-01','2026-10-02'])

    def test_unknown_or_same_day_sources_rejected(self):
        for ids in [[1,999], [2,3]]:
            self.reply([{'title':'Test', 'observation':'Test', 'entry_ids':ids}])
            result = self.run_patterns()
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['themes'], [])
            self.assertTrue(result['emotions'])

    def test_empty_skips_ai(self):
        self.assertEqual(self.run_patterns([])['status'], 'insufficient_data')
        client.with_options.assert_not_called()

    def test_invalid_scores_excluded(self):
        rows = self.records()
        rows[0].mood_score = 99
        rows[1].mood_score = None
        rows[2].mood_score = float('nan')
        self.reply([])
        self.assertEqual(self.run_patterns(rows)['highest_days'], [])

    def test_bad_json_retains_statistics(self):
        result = self.run_patterns()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['themes'], [])
        self.assertTrue(result['emotions'])

    def test_insights_endpoint_filters_period(self):
        self.add('2026-09-30')
        self.add('2026-10-01')
        self.add('2026-10-31')
        self.add('2026-11-01')
        self.reply([])
        result = generate_diary_insights(DiarySummaryRequest(period='monthly', anchor_date='2026-10-23'), self.db, self.user)
        self.assertEqual(result['entry_count'], 2)
        self.assertEqual(result['start_date'], '2026-10-01')

if __name__ == '__main__':
    unittest.main()
