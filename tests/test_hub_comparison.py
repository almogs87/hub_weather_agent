import csv,gzip,io,tempfile,unittest
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
from app.hub_comparison import daily_measure,compare_hubs,summarize_comparison
from app.schemas import HubComparisonRequest
from app.storm_events import StormEventsClient
from app.weather_sources import WeatherSources

class ComparisonTests(unittest.TestCase):
    def test_fema_fallback_compares_scores_and_explains_limits(self):
        locations=[dict(id='a',label='Alpha'),dict(id='b',label='Beta')]
        def county(hurricane,inland,coastal):
            return dict(evidence=dict(version='2025'),scores=dict(hurricane=hurricane,inland_flood=inland,coastal_flood=coastal))
        result=dict(locations=locations,end_year=2025,overall={'10':{'a':None,'b':None}},
                    coverage={'10':dict(partial=True,included_hazards=[],excluded_hazards=['event:Hurricane (Typhoon)','event:Flood'],excluded_locations=['a','b'])},
                    hazards={'event:Hurricane (Typhoon)':dict(kind='reported_event',hubs={}), 'event:Flood':dict(kind='reported_event',hubs={})},
                    fema_county_fallback={'a':county(90,70,None),'b':county(80,90,50)})
        text=summarize_comparison(result,10)
        self.assertIn('not enough comparable frequency and severity',text)
        self.assertIn('Hurricane: Beta is lower (Alpha 90.0, Beta 80.0)',text)
        self.assertIn('Inland Flood: Alpha is lower',text)
        self.assertIn('unavailable for coastal flood',text)
        self.assertIn('not percentages or facility shutdown probabilities',text)
        result['fema_county_fallback']['a']['scores']['hurricane']=99.99
        result['fema_county_fallback']['b']['scores']['hurricane']=99.98
        self.assertIn('scores are tied at this precision',summarize_comparison(result,10))
        result['fema_county_fallback']['b']['evidence']['version']='other'
        self.assertNotIn('uses FEMA county',summarize_comparison(result,10))

    def test_summary_is_qualified_and_shows_available_report_counts(self):
        locations=[dict(id='a',label='Alpha',state='IL'),dict(id='b',label='Beta',state='TX')]
        result=dict(locations=locations,end_year=2025,overall={'10':{'a':20.,'b':40.}},
                    coverage={'10':dict(partial=True,included_hazards=['snow'],excluded_hazards=['event:Ice Storm'],excluded_locations=[])},
                    hazards={'snow':dict(kind='daily',hubs={}),
                             'event:Ice Storm':dict(kind='reported_event',hubs={
                                 'a':dict(periods={'10':dict(event_reports=4,coverage=1,geographic_scope='county')}),
                                 'b':dict(periods={'10':dict(event_reports=9,coverage=1,geographic_scope='state')})})})
        text=summarize_comparison(result,10)
        self.assertIn('Alpha has the lower planning index',text)
        self.assertIn('partial comparison',text)
        self.assertIn('4 reports',text);self.assertIn('9 in',text)
        self.assertIn('prevent a reliable facility-risk conclusion',text)
        self.assertNotIn('may indicate more reported area exposure',text)
        result['hazards']['event:Ice Storm']['hubs']['b']['periods']['10']['geographic_scope']='county'
        self.assertIn('may indicate more reported area exposure',summarize_comparison(result,10))
        result['overall']['10']={'a':20.,'b':20.}
        self.assertIn('same planning index',summarize_comparison(result,10))
        result['overall']['10']={'a':None,'b':None}
        for hub in ('a','b'):result['hazards']['event:Ice Storm']['hubs'][hub]['periods']['10']['event_reports']=0
        text=summarize_comparison(result,10)
        self.assertIn('not enough comparable data',text)
        self.assertIn('0 reports',text)
        self.assertNotIn('lower planning index',text)

    def test_summary_mentions_only_supported_selected_period_trends(self):
        locations=[dict(id='a',label='Alpha'),dict(id='b',label='Beta')]
        group=dict(kind='daily',hubs={
            'a':dict(periods={'20':dict(trend=dict(status='descriptive',direction='decreasing'))}),
            'b':dict(periods={'20':dict(trend=dict(status='descriptive',direction='uncertain'))})})
        result=dict(locations=locations,end_year=2025,overall={'20':{'a':10.,'b':20.}},
                    coverage={'20':dict(partial=False,included_hazards=['snow'],excluded_hazards=[],excluded_locations=[])},hazards={'snow':group})
        text=summarize_comparison(result,20)
        self.assertIn("Alpha's snow index shows a decreasing historical trend",text)
        self.assertNotIn("Beta's snow index shows",text)

    def test_trend_uses_selected_period_and_requires_long_history(self):
        rows=[]
        for year in range(2006,2026):
            day=date(year,1,1)
            while day.year==year:
                offset=(day-date(year,1,1)).days
                rows.append(dict(date=day.isoformat(),snowfall_sum=10 if offset%8==0 and offset//8<year-2005 else 0))
                day+=timedelta(days=1)
        long=daily_measure(rows,date(2006,1,1),date(2025,12,31),'snow',[5,15,25],[1,3,7],100,14,[50,25,25])
        short=daily_measure(rows,date(2016,1,1),date(2025,12,31),'snow',[5,15,25],[1,3,7],100,14,[50,25,25])
        self.assertEqual(long['trend']['status'],'descriptive')
        self.assertEqual(long['trend']['direction'],'increasing')
        self.assertEqual(short['trend']['status'],'insufficient_evidence')
    def test_daily_thresholds_coverage_and_weighted_index(self):
        rows=[dict(date=f'2025-01-{i:02d}',snowfall_sum=v) for i,v in enumerate([5,15,0,25,0,None,0,0,None,0],1)]
        result=daily_measure(rows,date(2025,1,1),date(2025,1,10),'snow',[5,15,25],[1,3,7],10,14,[50,25,25])
        self.assertEqual(result['coverage'],.8)
        self.assertEqual(result['observed_periods'],2)
        self.assertEqual(result['assumed_average_recovery_days'],5)
        self.assertIsNotNone(result['index'])
        rows[0]['snowfall_sum']=None
        self.assertIsNone(daily_measure(rows,date(2025,1,1),date(2025,1,10),'snow',[5,15,25],[1,3,7],10,14,[50,25,25])['index'])

    def test_reject_duplicate_hubs_and_invalid_weights(self):
        with self.assertRaises(ValueError):HubComparisonRequest(locations=['a','a'],hazards=['snow'])
        with self.assertRaises(ValueError):HubComparisonRequest(locations=['a','b'],hazards=['snow'],weights=[90,25,25])

    def test_two_hubs_four_periods_and_incomplete_comparison(self):
        class Primary:
            def fetch(self,request,refresh=False):
                day=request.start;rows=[]
                while day<=request.end:
                    rows.append(dict(date=day.isoformat(),snowfall_sum=10 if day.month==1 and day.day==1 else 0))
                    day+=timedelta(days=1)
                return dict(rows=rows,evidence=dict(source='fixture'))
        class Secondary:pass
        class Store:
            def locations(self):return {i:dict(id=i,latitude=40,longitude=-105,timezone='UTC') for i in ('a','b')}
        class Service:pass
        service=Service();service.store=Store();service.weather=WeatherSources(Primary(),Secondary(),'open-meteo')
        result=compare_hubs(service,dict(locations=['a','b'],hazards=['snow'],weather_source='open-meteo'),now=datetime(2026,1,1,tzinfo=timezone.utc))
        self.assertEqual(result['periods'],[5,10,20,30])
        self.assertEqual(result['hazards']['snow']['hubs']['a']['periods']['30']['observed_periods'],30)
        self.assertIsNotNone(result['overall']['30']['a'])

    def test_event_count_coverage_and_state_warning(self):
        def content(cz,county,event_id):
            out=io.StringIO();fields=['EVENT_TYPE','STATE_FIPS','CZ_TYPE','CZ_FIPS','EVENT_ID','MAGNITUDE','TOR_F_SCALE'];w=csv.DictWriter(out,fieldnames=fields);w.writeheader();w.writerow(dict(EVENT_TYPE='Hail',STATE_FIPS='48',CZ_TYPE=cz,CZ_FIPS=county,EVENT_ID=event_id,MAGNITUDE='1.5',TOR_F_SCALE=''));return gzip.compress(out.getvalue().encode())
        index='\n'.join('StormEvents_details-ftp_v1.0_d%d_c20260101.csv.gz'%year for year in range(2021,2026)).encode()
        def transport(url):return index if url.endswith('/') else content('Z','001',url.split('_v1.0_d')[1][:4])
        locations={'a':dict(state='TX',county_fips='48201'),'b':dict(state='TX',county_fips='48113')}
        with tempfile.TemporaryDirectory() as directory:
            result=StormEventsClient(directory,transport).compare(locations,['a','b'],['Hail'],2025,[5],[50,25,25],10,14,[1,3,7])['Hail']
            self.assertIn('Statewide',result['warning'])
            a=result['hubs']['a']['periods']['5'];self.assertEqual(a['coverage'],1)
            self.assertEqual(a['geographic_scope'],'state');self.assertIsNotNone(a['index'])
            self.assertEqual(a['event_reports'],5)

    def test_cached_event_files_work_when_noaa_listing_is_offline(self):
        locations={'a':dict(state='TX',county_fips='48201'),'b':dict(state='TX',county_fips='48113')}
        out=io.StringIO()
        writer=csv.DictWriter(out,fieldnames=['EVENT_TYPE','STATE_FIPS','CZ_TYPE','CZ_FIPS','EVENT_ID'])
        writer.writeheader()
        writer.writerow(dict(EVENT_TYPE='Flood',STATE_FIPS='48',CZ_TYPE='C',CZ_FIPS='201',EVENT_ID='1'))
        def offline(url):raise OSError('offline')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'StormEvents_details-ftp_v1.0_d2025_c20260101.csv.gz'
            path.write_bytes(gzip.compress(out.getvalue().encode()))
            result=StormEventsClient(directory,offline).compare(locations,['a','b'],['Flood'],2025,[1,5],[50,25,25],10,14,[1,3,7])
            periods=result['Flood']['hubs']['a']['periods']
            self.assertEqual(periods['1']['event_reports'],1)
            self.assertEqual(periods['1']['coverage'],1)
            self.assertEqual(periods['5']['coverage'],.2)
            self.assertTrue(result['Flood']['hubs']['a']['evidence']['files'][0]['cache_hit'])

    def test_event_archive_coverage_and_missing_severity_withhold_score(self):
        index='\n'.join('StormEvents_details-ftp_v1.0_d%d_c20260101.csv.gz'%year for year in range(2022,2026)).encode()
        def transport(url):
            if url.endswith('/'):return index
            out=io.StringIO();fields=['EVENT_TYPE','STATE_FIPS','CZ_TYPE','CZ_FIPS','EVENT_ID','MAGNITUDE','TOR_F_SCALE'];writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
            writer.writerow(dict(EVENT_TYPE='Flood',STATE_FIPS='48',CZ_TYPE='Z',CZ_FIPS='001',EVENT_ID=url.split('_v1.0_d')[1][:4],MAGNITUDE='',TOR_F_SCALE=''))
            return gzip.compress(out.getvalue().encode())
        locations={'a':dict(state='TX',county_fips='48201'),'b':dict(state='TX',county_fips='48113')}
        with tempfile.TemporaryDirectory() as directory:
            result=StormEventsClient(directory,transport).compare(locations,['a','b'],['Flood'],2025,[5,10],[50,25,25],10,14,[1,3,7])['Flood']['hubs']['a']['periods']
            self.assertEqual(result['5']['coverage'],.8)
            self.assertEqual(result['5']['event_reports'],4)
            self.assertIsNone(result['5']['index'])
            self.assertLess(result['10']['coverage'],.8)
            self.assertIsNone(result['10']['index'])

    def test_event_scope_is_stable_for_same_period(self):
        index='\n'.join('StormEvents_details-ftp_v1.0_d%d_c20260101.csv.gz'%year for year in range(2016,2026)).encode()
        def transport(url):
            if url.endswith('/'):return index
            year=int(url.split('_v1.0_d')[1][:4]);out=io.StringIO()
            fields=['EVENT_TYPE','STATE_FIPS','CZ_TYPE','CZ_FIPS','EVENT_ID','MAGNITUDE','TOR_F_SCALE']
            writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
            writer.writerow(dict(EVENT_TYPE='Hail',STATE_FIPS='48',CZ_TYPE='Z' if year==2016 else 'C',CZ_FIPS='201',EVENT_ID=str(year),MAGNITUDE='1',TOR_F_SCALE=''))
            return gzip.compress(out.getvalue().encode())
        locations={'a':dict(state='TX',county_fips='48201'),'b':dict(state='TX',county_fips='48201')}
        with tempfile.TemporaryDirectory() as directory:
            client=StormEventsClient(directory,transport)
            one=client.compare(locations,['a','b'],['Hail'],2025,[5],[50,25,25],10,14,[1,3,7])
            multi=client.compare(locations,['a','b'],['Hail'],2025,[5,10],[50,25,25],10,14,[1,3,7])
            self.assertEqual(one['Hail']['hubs']['a']['periods']['5']['index'],multi['Hail']['hubs']['a']['periods']['5']['index'])
            self.assertEqual(multi['Hail']['hubs']['a']['periods']['5']['geographic_scope'],'county')
            self.assertEqual(multi['Hail']['hubs']['a']['periods']['10']['geographic_scope'],'state')

if __name__=='__main__':unittest.main()
