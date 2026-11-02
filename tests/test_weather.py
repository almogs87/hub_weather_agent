import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from app.weather import WeatherRequest, WeatherClient, UNITS, normalize, exposure, trend, rank_exposure

class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.request=WeatherRequest(40,-105,date(2024,2,28),date(2024,3,1),'UTC')
        self.payload=dict(latitude=40,longitude=-105,daily_units=UNITS.copy(),daily=dict(time=['2024-02-28','2024-02-29','2024-03-01']))
        for variable in UNITS:
            self.payload['daily'][variable]=[0,1,None]

    def test_leap_day_and_missing_denominator(self):
        rows=normalize(self.payload,self.request)
        result=exposure(rows,self.request.start,self.request.end,'snow')
        self.assertEqual(result['expected_days'],3)
        self.assertEqual(result['valid_days'],2)
        self.assertEqual(result['exceedance_percent'],50)
        self.assertFalse(result['annual'][0]['eligible_for_trend'])

    def test_absent_date_is_null_not_zero(self):
        for values in self.payload['daily'].values():
            values.pop(1)
        rows=normalize(self.payload,self.request)
        self.assertIsNone(rows[1]['snowfall_sum'])
        self.assertEqual(len(rows),3)

    def test_invalid_provider_data(self):
        bad=copy.deepcopy(self.payload)
        bad['daily_units']['snowfall_sum']='mm'
        with self.assertRaises(ValueError): normalize(bad,self.request)
        bad=copy.deepcopy(self.payload)
        bad['daily']['snowfall_sum'][0]=-1
        with self.assertRaises(ValueError): normalize(bad,self.request)
        bad=copy.deepcopy(self.payload)
        bad['daily']['time'][1]=bad['daily']['time'][0]
        with self.assertRaises(ValueError): normalize(bad,self.request)
        bad=copy.deepcopy(self.payload)
        bad['daily']['wind_speed_10m_max'][0]=float('nan')
        with self.assertRaises(ValueError): normalize(bad,self.request)

    def test_cache_and_provenance(self):
        calls=[]
        def transport(url):
            calls.append(url)
            return json.dumps(self.payload).encode()
        with tempfile.TemporaryDirectory() as directory:
            client=WeatherClient(directory,transport)
            first=client.fetch(self.request)
            second=client.fetch(self.request)
            self.assertEqual(len(calls),1)
            self.assertFalse(first['evidence']['cache_hit'])
            self.assertTrue(second['evidence']['cache_hit'])
            self.assertEqual(first['evidence']['source_id'],second['evidence']['source_id'])
            self.assertIn('models=era5',calls[0])
            path=next(Path(directory).glob('*.json'))
            envelope=json.loads(path.read_text())
            envelope['raw_response']='{}'
            path.write_text(json.dumps(envelope))
            with self.assertRaises(ValueError):client.fetch(self.request)

    def test_failure_does_not_create_fixtures(self):
        def broken(url):raise TimeoutError('test timeout')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError,'Weather API connection failed'):WeatherClient(directory,broken).fetch(self.request)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_missing_breaks_event_runs(self):
        rows=[dict(date='2024-01-0'+str(i),snowfall_sum=v) for i,v in enumerate([1,1,None,1,0],1)]
        r=exposure(rows,date(2024,1,1),date(2024,1,5),'snow')
        self.assertEqual(r['observed_event_runs'],2)
        self.assertEqual(r['longest_observed_run_days'],2)
        self.assertEqual(r['exceedance_percent'],75)

    def test_threshold_operators(self):
        row=dict(date='2024-01-01',snowfall_sum=0,precipitation_sum=25,temperature_2m_min=-10)
        for hazard,expected in [('snow',0),('heavy_precipitation',1),('cold',1)]:
            self.assertEqual(exposure([row],date(2024,1,1),date(2024,1,1),hazard)['exceedance_days'],expected)
        with self.assertRaises(ValueError):exposure([],self.request.start,self.request.end,'flood')

    def test_trend_directions_and_reproducibility(self):
        for sign,label in [(1,'increasing'),(-1,'decreasing'),(0,'uncertain')]:
            annual=[dict(year=y,eligible_for_trend=True,exceedance_percent=30+sign*(y-2011)) for y in range(2011,2026)]
            r=trend(annual,2011,2025)
            self.assertEqual(r['direction'],label)
            self.assertAlmostEqual(r['slope_percentage_points_per_year'],sign)
            self.assertEqual(r,trend(annual,2011,2025))
        self.assertEqual(trend([],2011,2025)['status'],'insufficient_evidence')

    def test_ranking_requires_comparable_metrics(self):
        a=exposure(normalize(self.payload,self.request),self.request.start,self.request.end,'snow')
        # Explicitly inadequate coverage must not receive a reassuring ranking.
        a['location_id']='A'
        self.assertEqual(rank_exposure([a])['excluded'],['A'])
        b=copy.deepcopy(a)
        a['completeness']=b['completeness']=1
        b['location_id']='B'
        self.assertEqual([r['location_id'] for r in rank_exposure([b,a])['ranked']],['A','B'])
        b['threshold']=1
        with self.assertRaises(ValueError):rank_exposure([a,b])

    def test_coordinate_validation(self):
        for latitude in [91,float('nan'),True]:
            with self.assertRaises(ValueError):WeatherRequest(latitude,0,date(2024,1,1),date(2024,1,2),'UTC').parameters()

    def test_subset_reuses_verified_source(self):
        calls=[]
        def transport(url):
            calls.append(url)
            return json.dumps(self.payload).encode()
        with tempfile.TemporaryDirectory() as directory:
            client=WeatherClient(directory,transport)
            original=client.fetch(self.request)
            result=client.fetch(WeatherRequest(40,-105,date(2024,2,29),date(2024,3,1),'UTC'))
            self.assertEqual(len(calls),1)
            self.assertEqual(len(result['rows']),2)
            self.assertEqual(result['rows'][0]['date'],'2024-02-29')
            self.assertTrue(result['evidence']['subset_from_cache'])
            self.assertEqual(result['evidence']['source_id'],original['evidence']['source_id'])
            self.assertEqual(result['evidence']['request_url'],original['evidence']['request_url'])
            self.assertNotEqual(result['evidence']['analysis_request_url'],original['evidence']['request_url'])

    def test_cache_does_not_cross_location(self):
        calls=[]
        def transport(url):
            calls.append(url)
            return json.dumps(self.payload).encode()
        with tempfile.TemporaryDirectory() as directory:
            client=WeatherClient(directory,transport)
            client.fetch(self.request)
            client.fetch(WeatherRequest(41,-105,self.request.start,self.request.end,'UTC'))
            self.assertEqual(len(calls),2)

if __name__=='__main__':unittest.main()
