import copy
from datetime import timedelta
import tempfile
import unittest
from app.agent import Service
from app.storage import Store
from app.comparison import compare_networks
from app.server import dispatch

class Weather:
    def __init__(self):self.calls=[]
    def fetch(self,request):
        self.calls.append(request)
        rows=[]
        day=request.start
        while day<=request.end:
            rows.append(dict(date=day.isoformat(),snowfall_sum=25 if request.latitude==40 and day==request.start else 0))
            day+=timedelta(days=1)
        return dict(rows=rows,evidence=dict(source_id='synthetic:'+str(request.latitude)))

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.weather=Weather()
        self.service=Service(Store(self.tmp.name+'/state.db'),self.weather,mode='demo')
        for identifier,lat in [('exposed',40),('backup',41)]:
            self.service.add_location(dict(id=identifier,latitude=lat,longitude=-105,timezone='UTC'))
        self.reference=dict(hubs=[dict(id='A',capacity=100)],demands=[dict(id='X',units=60)],links=[dict(hub_id='A',demand_id='X',distance_km=10)],max_distance_km=100,start='2025-01-01',end='2025-01-03',hub_locations={'A':'exposed'})
        self.candidate=copy.deepcopy(self.reference)
        self.candidate['hubs'].append(dict(id='B',capacity=100))
        self.candidate['links'].append(dict(hub_id='B',demand_id='X',distance_km=20))
        self.candidate['hub_locations']['B']='backup'
    def tearDown(self):self.tmp.cleanup()
    def compare(self):return dispatch(self.service,'/api/scenarios/compare',dict(reference=self.reference,candidate=self.candidate))

    def test_backup_preserves_service_with_paired_weather(self):
        r=self.compare()
        self.assertAlmostEqual(r['reference']['unserved_demand_days'],55)
        self.assertEqual(r['candidate']['unserved_demand_days'],0)
        self.assertAlmostEqual(r['comparison']['avoided_unserved_demand_days'],55)
        self.assertEqual(r['comparison']['avoided_unserved_percent'],100)
        self.assertEqual(r['comparison']['days_candidate_serves_more'],2)
        self.assertEqual(len(self.weather.calls),2) # One call per unique location, not per network.
        self.assertEqual(r['candidate']['network_summary']['installed_daily_capacity'],200)
        self.assertGreater(r['comparison']['common_service_mean_distance_change_km'],0)

    def test_regional_co_exposure_is_not_ignored(self):
        self.candidate['hub_locations']['B']='exposed'
        r=self.compare()
        self.assertAlmostEqual(r['candidate']['days'][0]['unserved_units'],40)
        self.assertEqual(len(self.weather.calls),1)
        self.assertLess(r['comparison']['avoided_unserved_demand_days'],55)

    def test_identical_networks_and_zero_denominator(self):
        self.reference['hub_locations']['A']='backup'
        self.candidate=copy.deepcopy(self.reference)
        r=self.compare()
        self.assertEqual(r['comparison']['avoided_unserved_demand_days'],0)
        self.assertIsNone(r['comparison']['avoided_unserved_percent'])
        self.assertEqual(r['comparison']['common_service_mean_distance_change_km'],0)

    def test_incomparable_networks_fail_before_data_fetch(self):
        for field,value in [('end','2025-01-04'),('max_distance_km',90),('demands',[dict(id='X',units=90)])]:
            candidate=copy.deepcopy(self.candidate)
            candidate[field]=value
            with self.assertRaises(ValueError):compare_networks(self.service,dict(reference=self.reference,candidate=candidate))
        self.assertEqual(self.weather.calls,[])

    def test_shared_hub_cannot_move(self):
        self.candidate['hub_locations']['A']='backup'
        with self.assertRaises(ValueError):self.compare()
        self.assertEqual(self.weather.calls,[])

    def test_worse_candidate_and_no_common_service(self):
        self.candidate['hubs']=[dict(id='A',capacity=1)]
        self.candidate['links']=self.reference['links']
        self.candidate['hub_locations']={'A':'exposed'}
        r=self.compare()
        self.assertLess(r['comparison']['avoided_unserved_demand_days'],0)
        self.assertEqual(r['comparison']['days_candidate_serves_less'],3)
        self.candidate['links']=[]
        r=self.compare()
        self.assertIsNone(r['comparison']['common_service_mean_distance_change_km'])

if __name__=='__main__':unittest.main()
