from datetime import date
import json
import tempfile
import unittest
from app.noaa import NOAAClient,parse_daily,stations
from app.weather import WeatherRequest,rank_exposure
from app.weather_sources import WeatherSources

STATION='USW00000001'

def record(element,values,quality=None):
    fields=[]
    for i in range(31):
        value=values[i] if i<len(values) else -9999
        fields.append(f'{value:5d} '+('X' if quality==i else ' ')+'0')
    return STATION+'202501'+element+''.join(fields)

def catalog():
    return f'{STATION} {40:8.4f} {-105:9.4f} {1000:6.1f} CO '+f'{"TEST STATION":30s}'

class NOAATests(unittest.TestCase):
    def setUp(self):self.request=WeatherRequest(40,-105,date(2025,1,1),date(2025,1,3),'UTC')
    def test_units_quality_and_missing(self):
        text='\n'.join([record('SNOW',[254,0,-9999]),record('TMAX',[250,300,320],quality=1),record('PRCP',[123,0,0])])
        rows=parse_daily(text,STATION,self.request)
        self.assertEqual(rows[0]['snowfall_sum'],25.4)
        self.assertEqual(rows[0]['precipitation_sum'],12.3)
        self.assertEqual(rows[0]['temperature_2m_max'],25)
        self.assertIsNone(rows[1]['temperature_2m_max'])
        self.assertIsNone(rows[2]['snowfall_sum'])
        self.assertIsNone(rows[0]['wind_speed_10m_max'])
    def test_catalog_distance_and_radius(self):
        selected=stations(catalog(),40,-105)
        self.assertEqual(selected[0]['id'],STATION)
        self.assertAlmostEqual(selected[0]['distance_km'],0)
        self.assertEqual(stations(catalog(),0,0),[])
    def test_cache_provenance_and_snow_is_not_depth(self):
        calls=[]
        def transport(url):
            calls.append(url)
            return (catalog() if url.endswith('stations.txt') else record('SNOW',[10,20,30])+'\n'+record('SNWD',[999,999,999])).encode()
        with tempfile.TemporaryDirectory() as folder:
            client=NOAAClient(folder,transport)
            first=client.fetch(self.request)
            second=client.fetch(self.request)
            self.assertEqual(len(calls),2)
            self.assertEqual(first['rows'][0]['snowfall_sum'],1)
            self.assertTrue(second['evidence']['cache_hit'])
            self.assertEqual(first['evidence']['source_id'],second['evidence']['source_id'])
            self.assertEqual(first['evidence']['station']['id'],STATION)
    def test_low_coverage_and_wind_refused(self):
        def transport(url):return (catalog() if url.endswith('stations.txt') else record('SNOW',[10,-9999,0])).encode()
        with tempfile.TemporaryDirectory() as folder:
            client=NOAAClient(folder,transport)
            with self.assertRaisesRegex(RuntimeError,'95%'):client.fetch(self.request)
            with self.assertRaisesRegex(RuntimeError,'average wind'):client.fetch(self.request,hazard='wind')
    def test_station_mismatch_and_duplicates_rejected(self):
        with self.assertRaises(ValueError):parse_daily(record('SNOW',[0,0,0]),'USW99999999',self.request)
        line=record('SNOW',[0,0,0])
        with self.assertRaises(ValueError):parse_daily(line+'\n'+line,STATION,self.request)

class SourceSelectionTests(unittest.TestCase):
    def test_failure_replays_all_locations_from_one_source(self):
        class Primary:
            def fetch(self,request,refresh=False):
                if request.latitude==41:raise RuntimeError('overloaded')
                return dict(rows=[],evidence=dict(source='ERA5'))
        class Secondary:
            def __init__(self):self.calls=[]
            def fetch(self,request,hazard,refresh=False):
                self.calls.append(request.latitude)
                return dict(rows=[],evidence=dict(source='NOAA'))
        secondary=Secondary()
        requests={i:WeatherRequest(lat,0,date(2025,1,1),date(2025,1,2),'UTC') for i,lat in [('A',40),('B',41)]}
        result=WeatherSources(Primary(),secondary,'auto').fetch_group(requests)
        self.assertEqual(secondary.calls,[40,41])
        self.assertTrue(all(r['evidence']['source']=='NOAA' for r in result.values()))
        self.assertTrue(all(r['evidence']['fallback_reason']=='overloaded' for r in result.values()))
    def test_manual_noaa_selection_skips_primary(self):
        class Primary:
            def fetch(self,*args,**kwargs):raise AssertionError('Primary called')
        class Secondary:
            def fetch(self,*args,**kwargs):return dict(rows=[],evidence={})
        request=WeatherRequest(40,0,date(2025,1,1),date(2025,1,2),'UTC')
        self.assertIn('location',WeatherSources(Primary(),Secondary(),'noaa').fetch_group({'location':request}))
    def test_rank_rejects_mixed_sources(self):
        common=dict(hazard='snow',operator='>',threshold=0,unit='cm',start='2025-01-01',end='2025-12-31',completeness=1,exceedance_percent=10)
        with self.assertRaisesRegex(ValueError,'mixed weather'):
            rank_exposure([dict(common,location_id='A',evidence=dict(source='NOAA')),dict(common,location_id='B',evidence=dict(source='ERA5'))])

if __name__=='__main__':unittest.main()
