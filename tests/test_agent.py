from datetime import date
import json
import tempfile
import unittest
from unittest.mock import patch
from app.agent import Service, DemoPlanner, OpenAIPlanner
from app.schemas import Intent
from app.storage import Store
from app.server import dispatch
from app.weather import UNITS
from app.winter import snowfall_disruptions, WinterProfile

class FakeWeather:
    def fetch(self,request):
        from datetime import timedelta
        rows=[]
        day=request.start
        while day<=request.end:
            rows.append(dict(date=day.isoformat(),snowfall_sum=25 if day==request.start else 0,precipitation_sum=0,temperature_2m_max=36,temperature_2m_min=0,wind_speed_10m_max=0))
            day+=timedelta(days=1)
        return dict(rows=rows,evidence=dict(source_id='fixture:synthetic',source='synthetic test',units=UNITS))

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.service=Service(Store(self.tmp.name+'/state.db'),FakeWeather(),mode='demo')
        for identifier in ['siteA','siteB']:
            self.service.add_location(dict(id=identifier,latitude=40,longitude=-105,timezone='UTC'))
    def tearDown(self):self.tmp.cleanup()

    def test_schema_rejects_unknown_fields(self):
        with self.assertRaises(ValueError):Intent.model_validate(dict(action='weather',location_ids=[],hazard='snow',start=None,end=None,threshold=None,question=None,execute_code='oops'))

    def test_followup_and_persistent_state(self):
        first=self.service.chat(dict(message='Snow for siteA in 2025'))
        second=self.service.chat(dict(message='What about heat?',conversation_id=first['conversation_id']))
        self.assertEqual(second['intent']['location_ids'],['siteA'])
        self.assertEqual(second['intent']['hazard'],'heat')
        self.assertEqual(second['cards'][0]['exceedance_percent'],100)
        self.assertEqual(second['cards'][0]['start'],'2025-01-01')
        reloaded=Store(self.tmp.name+'/state.db').load(first['conversation_id'])[1]
        self.assertEqual(reloaded['intent']['hazard'],'heat')

    def test_missing_location_clarification(self):
        service=Service(Store(self.tmp.name+'/empty.db'),FakeWeather(),mode='demo')
        self.assertEqual(service.chat(dict(message='Show snow'))['intent']['action'],'clarify')

    def test_compare_and_explain(self):
        r=self.service.chat(dict(message='Compare siteB and siteA snow 2025'))
        self.assertEqual([c['location_id'] for c in r['cards']],['siteA','siteB'])
        follow=self.service.chat(dict(message='Why?',conversation_id=r['conversation_id']))
        self.assertIn('deterministic',follow['answer'])

    def test_unsupported_is_explicit(self):
        r=self.service.chat(dict(message='Flood risk for siteA'))
        self.assertEqual(r['intent']['action'],'unsupported')
        self.assertEqual(r['cards'],[])

    def test_unknown_llm_location_rejected(self):
        def planner(*args):return Intent(action='weather',location_ids=['invented'],hazard='snow',start=None,end=None,threshold=None,question=None)
        self.service.planner=planner
        with self.assertRaisesRegex(ValueError,'Unknown location'):self.service.chat(dict(message='show snow'))

    def test_provider_failure_not_replaced(self):
        def broken(*args):raise TimeoutError()
        self.service.weather.fetch=broken
        with self.assertRaises(TimeoutError):self.service.chat(dict(message='snow siteA'))

    def test_winter_profile_boundaries_and_recovery(self):
        rows=[dict(date='2025-01-0'+str(i+1),snowfall_sum=v) for i,v in enumerate([4.9,5,15,25])]
        events=snowfall_disruptions('A',rows)
        self.assertEqual([e.available_fraction for e in events],[.8,.5,.1])
        self.assertEqual([e.recovery_days for e in events],[0,1,2])
        self.assertIn('Illustrative',WinterProfile().describe()['basis'])
        with self.assertRaises(ValueError):snowfall_disruptions('A',[dict(date='2025-01-01',snowfall_sum=None)])

    def scenario(self):
        return dict(hubs=[dict(id='A',capacity=100)],demands=[dict(id='X',units=60)],links=[dict(hub_id='A',demand_id='X',distance_km=10)],max_distance_km=100,start='2025-01-01',end='2025-01-03',hub_locations={'A':'siteA'})

    def test_weather_replay_capacity_and_recovery(self):
        r=dispatch(self.service,'/api/scenarios/replay',self.scenario())
        self.assertAlmostEqual(r['days'][0]['available_capacities']['A'],10)
        self.assertAlmostEqual(r['days'][1]['available_capacities']['A'],55)
        self.assertEqual(r['days'][2]['available_capacities']['A'],100)
        self.assertAlmostEqual(r['incremental_unserved_demand_days'],55)
        self.assertEqual(r['service_recovery_date'],'2025-01-03')
        self.assertEqual(r['evidence'][0]['source_id'],'fixture:synthetic')

    def test_replay_requires_explicit_mapping(self):
        payload=self.scenario()
        payload['hub_locations']={}
        with self.assertRaises(ValueError):self.service.replay(payload)

    def test_live_mode_requires_credentials(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'OPENAI_API_KEY'):OpenAIPlanner()('snow',{}, {})

    def test_mocked_strict_tool_call(self):
        intent=dict(action='clarify',location_ids=[],hazard=None,start=None,end=None,threshold=None,question='Which location?')
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps(dict(status='completed',output=[dict(type='function_call',name='plan_analysis',arguments=json.dumps(intent))])).encode()
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-not-real','OPENAI_MODEL':'test-model'}),patch('app.providers.urlopen',return_value=Response()) as mock:
            result=OpenAIPlanner()('snow',{}, {})
            body=json.loads(mock.call_args.args[0].data)
            self.assertTrue(body['tools'][0]['strict'])
            self.assertFalse(body['parallel_tool_calls'])
            self.assertEqual(result.action,'clarify')

    def test_chat_can_run_supplied_network(self):
        r=self.service.chat(dict(message='Run a winter replay',scenario=self.scenario()))
        self.assertAlmostEqual(r['scenario_result']['incremental_unserved_demand_days'],55)
        self.assertIn('illustrative',r['answer'])

    def test_replay_summary_and_recovery_evidence(self):
        result=self.service.replay(self.scenario())
        self.assertEqual(result['summary']['affected_days'],2)
        self.assertEqual(result['summary']['days_with_unserved_demand'],2)
        self.assertTrue(result['validation']['passed'])
        self.assertEqual(result['days'][0]['weather_impacts'][0]['snowfall_cm'],25)
        self.assertEqual(result['days'][1]['weather_impacts'][0]['rule'],'Recovery from earlier snowfall')
        self.assertEqual(result['days'][2]['weather_impacts'],[])

    def test_pasted_json_gets_guidance(self):
        result=self.service.chat(dict(message=json.dumps(self.scenario())))
        self.assertEqual(result['intent']['action'],'clarify')
        self.assertIn('Scenario JSON',result['answer'])
        self.assertEqual(result['cards'],[])

    def test_accounting_audit_detects_invalid_allocation(self):
        from app.replay_report import enrich_report
        from app.scenarios import Hub,Demand
        result=self.service.replay(self.scenario())
        result['days'][0]['assignments'][0]['units']=1000
        rows=FakeWeather().fetch(type('R',(),dict(start=date(2025,1,1),end=date(2025,1,3)))())['rows']
        enrich_report(result,[Hub('A',100)],[Demand('X',60)],{'A':rows},WinterProfile())
        self.assertFalse(result['validation']['passed'])

    def test_original_model_plan_and_applied_policy_are_visible(self):
        def wrong_plan(*args):
            return Intent(action='weather',location_ids=['siteA'],hazard='snow',start=date(2025,1,1),end=date(2025,12,31),threshold=0,question=None)
        self.service.planner=wrong_plan
        result=self.service.chat(dict(message='Heavy snow for siteA in 2025'))
        self.assertEqual(result['planning']['model_plan']['threshold'],0)
        self.assertEqual(result['planning']['applied_plan']['threshold'],15)
        self.assertTrue(result['planning']['policy_adjustments'])
        self.assertEqual(result['cards'][0]['threshold'],15)

    def test_failed_location_does_not_hide_available_comparison(self):
        original=self.service.weather_analysis
        def selective(location,*args,**kwargs):
            if location=='siteB':raise RuntimeError('Weather data for siteB: HTTP 503')
            return original(location,*args,**kwargs)
        self.service.weather_analysis=selective
        result=self.service.chat(dict(message='Compare snow for siteA and siteB in 2025'))
        self.assertEqual(result['result_status'],'partial')
        self.assertEqual([c['location_id'] for c in result['cards']],['siteA'])
        self.assertEqual(result['data_errors'][0]['location_id'],'siteB')
        self.assertIn('no complete ranking',result['answer'])

if __name__=='__main__':unittest.main()
