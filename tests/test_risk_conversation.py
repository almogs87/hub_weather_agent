import tempfile
import unittest

from app.agent import Service
from app.hubs import load_hubs
from app.storage import Store
from evals.run import EvaluationFEMA, EvaluationWeather, EvaluationStorm
from app.hub_comparison import compare_hubs


class RiskConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = Service(Store(self.tmp.name + '/app.db',catalog=load_hubs()), EvaluationWeather(), mode='demo', fema=EvaluationFEMA())
        self.service.storm_events=EvaluationStorm()

    def tearDown(self):
        self.tmp.cleanup()

    def test_midwest_winter_ranking_and_stable_ties(self):
        result = self.service.chat({'message': 'Which hubs in the Midwest are most exposed to winter disruption?'})
        self.assertEqual(result['result_status'], 'partial')
        self.assertEqual(len(result['comparison_result']['locations']),7)
        self.assertEqual(result['comparison_result']['periods'],[10])
        self.assertEqual(result['comparison_result']['coverage']['10']['included_hazards'],['snow'])
        self.assertEqual(result['comparison_result']['coverage']['10']['excluded_hazards'],['event:Ice Storm'])
        self.assertTrue(all(score is not None for score in result['comparison_result']['overall']['10'].values()))
        self.assertIn('ice storm', result['answer'].lower())
        self.assertIn('partial', result['answer'].lower())

    def test_risk_followups_preserve_hubs_hazard_and_evidence(self):
        first = self.service.chat({'message': 'Compare Miami and Houston for hurricane and flood'})
        cid = first['conversation_id']
        second = self.service.chat({'message': 'Compare only flooding', 'conversation_id': cid})
        self.assertEqual(second['intent']['hazard'], 'flood')
        self.assertEqual(set(second['intent']['location_ids']), {'miami', 'houston'})
        explain = self.service.chat({'message': 'Why?', 'conversation_id': cid})
        self.assertEqual(explain['comparison_result'], second['comparison_result'])
        follow = self.service.chat({'message': 'What about Dallas?', 'conversation_id': cid})
        self.assertEqual(follow['intent']['hazard'], 'flood')
        self.assertEqual(follow['intent']['location_ids'], ['dallas'])

    def test_missing_data_stays_partial_in_explanation(self):
        first = self.service.chat({'message': 'Compare Miami and Houston for flood'})
        self.assertEqual(first['result_status'], 'partial')
        self.assertIn('not enough comparable frequency and severity data', first['answer'])
        self.assertIn('FEMA', first['answer'])
        self.assertTrue(all(x is None for x in first['comparison_result']['overall']['10'].values()))
        explanation = self.service.chat({'message': 'Why?', 'conversation_id': first['conversation_id']})
        self.assertEqual(explanation['result_status'], 'partial')

    def test_risk_then_snow_uses_weather(self):
        first = self.service.chat({'message': 'Hurricane risk for Dallas'})
        follow = self.service.chat({'message': 'Snow in Dallas in 2025', 'conversation_id': first['conversation_id']})
        self.assertEqual(follow['intent']['action'], 'weather')
        self.assertEqual(follow['cards'][0]['variable'], 'snowfall_sum')

    def test_chat_and_table_use_identical_index_and_settings(self):
        settings=dict(weights=[70,20,10],frequency_benchmark=20,recovery_days=[2,4,8],bands={'snow':[5,15,25]})
        chat=self.service.chat({'message':'Compare chicago and denver for snow','index_settings':settings})
        table=compare_hubs(self.service,dict(locations=['chicago','denver'],hazards=['snow'],**settings),periods=[10])
        self.assertEqual(chat['comparison_result']['overall']['10'],table['overall']['10'])
        self.assertEqual(chat['comparison_result']['weights'],[70,20,10])

    def test_named_hazard_comparison_respects_explicit_period(self):
        result=self.service.chat({'message':'Compare chicago and denver for ice storm from 2006 to 2025'})
        self.assertEqual(result['comparison_result']['periods'],[20])
        self.assertEqual(result['comparison_result']['end_year'],2025)
        self.assertIn('2 reports',result['answer'])

    def test_other_hazards_are_county_screening_not_observed_counts(self):
        for hazard in ('ice storm','tornado','drought'):
            result=self.service.chat({'message':f'Compare chicago and dallas for {hazard} risk'})
            self.assertEqual(result['intent']['action'],'risk')
            self.assertEqual(result['result_status'],'partial')
            self.assertIn('county',result['answer'].lower())
        count=self.service.chat({'message':'How many tornadoes were recorded in dallas?'})
        self.assertEqual(count['intent']['action'],'risk')
        self.assertIn('reports',count['answer'])


if __name__ == '__main__':
    unittest.main()
