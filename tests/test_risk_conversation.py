import tempfile
import unittest

from app.agent import Service
from app.hubs import seed_examples
from app.storage import Store
from evals.run import EvaluationFEMA, EvaluationWeather


class RiskConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = Service(Store(self.tmp.name + '/app.db'), EvaluationWeather(), mode='demo', fema=EvaluationFEMA())
        seed_examples(self.service.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_midwest_winter_ranking_and_stable_ties(self):
        result = self.service.chat({'message': 'Which hubs in the Midwest are most exposed to winter disruption?'})
        self.assertEqual(result['result_status'], 'complete')
        self.assertEqual([r['location_id'] for r in result['risk_results']], ['chicago', 'minneapolis', 'detroit'])
        self.assertIn('county', result['answer'])
        self.assertIn('not facility-specific', result['answer'])
        self.assertIn('Chicago ranks highest', result['answer'])
        self.assertIn('counties nationwide', result['answer'])

    def test_risk_followups_preserve_hubs_hazard_and_evidence(self):
        first = self.service.chat({'message': 'Compare Miami and Houston for hurricane and flood'})
        cid = first['conversation_id']
        second = self.service.chat({'message': 'Compare only flooding', 'conversation_id': cid})
        self.assertEqual(second['intent']['hazard'], 'flood')
        self.assertEqual(set(second['intent']['location_ids']), {'miami', 'houston'})
        explain = self.service.chat({'message': 'Why?', 'conversation_id': cid})
        self.assertEqual(explain['risk_results'], second['risk_results'])
        follow = self.service.chat({'message': 'What about Dallas?', 'conversation_id': cid})
        self.assertEqual(follow['intent']['hazard'], 'flood')
        self.assertEqual(follow['intent']['location_ids'], ['dallas'])

    def test_missing_data_stays_partial_in_explanation(self):
        class Missing(EvaluationFEMA):
            def fetch(self, county_fips):
                result = super().fetch(county_fips)
                result['scores']['coastal_flood'] = None
                return result
        self.service.fema = Missing()
        first = self.service.chat({'message': 'Compare Miami and Houston for flood'})
        self.assertEqual(first['result_status'], 'partial')
        self.assertIn('no complete ranking', first['answer'])
        self.assertTrue(all(r['screening_score'] is None for r in first['risk_results']))
        explanation = self.service.chat({'message': 'Why?', 'conversation_id': first['conversation_id']})
        self.assertEqual(explanation['result_status'], 'partial')

    def test_risk_then_snow_uses_weather(self):
        first = self.service.chat({'message': 'Hurricane risk for Dallas'})
        follow = self.service.chat({'message': 'Snow in Dallas in 2025', 'conversation_id': first['conversation_id']})
        self.assertEqual(follow['intent']['action'], 'weather')
        self.assertEqual(follow['cards'][0]['variable'], 'snowfall_sum')


if __name__ == '__main__':
    unittest.main()
