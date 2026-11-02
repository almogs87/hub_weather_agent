"""NOAA Storm Events archive. Reports describe areas, not observed hub outages."""
from collections import defaultdict
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO,TextIOWrapper
from pathlib import Path
from urllib.request import Request,urlopen
import csv,gzip,json,re

BASE='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
# NOAA Storm Data standard event types; browseable even if no comparable magnitude exists.
EVENT_TYPES=('Astronomical Low Tide','Avalanche','Blizzard','Coastal Flood','Cold/Wind Chill','Debris Flow','Dense Fog','Dense Smoke','Drought','Dust Devil','Dust Storm','Excessive Heat','Extreme Cold/Wind Chill','Flash Flood','Flood','Frost/Freeze','Funnel Cloud','Freezing Fog','Hail','Heat','Heavy Rain','Heavy Snow','High Surf','High Wind','Hurricane (Typhoon)','Ice Storm','Lake-Effect Snow','Lakeshore Flood','Lightning','Marine Hail','Marine High Wind','Marine Strong Wind','Marine Thunderstorm Wind','Rip Current','Seiche','Sleet','Storm Surge/Tide','Strong Wind','Thunderstorm Wind','Tornado','Tropical Depression','Tropical Storm','Tsunami','Volcanic Ash','Waterspout','Wildfire','Winter Storm','Winter Weather')

class StormEventsClient:
    def __init__(self,cache_dir='data/cache/storm_events',transport=None):
        self.cache_dir=Path(cache_dir);self.transport=transport or self.download
    @staticmethod
    def download(url):
        with urlopen(Request(url,headers={'User-Agent':'hub-weather-agent/0.1'}),timeout=30) as r:return r.read()
    def compare(self,locations,identifiers,hazards,end_year,periods,weights,frequency_benchmark,recovery_benchmark,recovery_days,event_benchmarks=None):
        event_benchmarks=event_benchmarks or {'hail_inches':3,'wind_knots':100}
        try:index=self.transport(BASE).decode('utf-8')
        except Exception as exc:
            # Previously downloaded annual files remain usable when the directory
            # listing is offline; coverage below still reflects missing years.
            index='\n'.join(path.name for path in self.cache_dir.glob('StormEvents_details-ftp_v1.0_d*_c*.csv.gz'))
            if not index:raise RuntimeError('NOAA storm event archive is unavailable and no annual files are cached') from exc
        filenames={}
        for name in re.findall(r'StormEvents_details-ftp_v1\.0_d(\d{4})_c(\d{8})\.csv\.gz',index):
            year,revision=name
            if int(year)<=end_year and int(year)>=end_year-max(periods)+1 and revision>filenames.get(int(year),''):
                filenames[int(year)]=revision
        if not filenames:raise RuntimeError('NOAA archive did not list any requested annual files')
        self.cache_dir.mkdir(parents=True,exist_ok=True)
        selected_states={locations[i]['state'] for i in identifiers}
        # NOAA state names are accompanied by a numeric FIPS; use the trusted hub county prefix.
        state_codes={locations[i]['county_fips'][:2] for i in identifiers}
        records=defaultdict(list);availability=set();provenance=[]
        for year,revision in sorted(filenames.items()):
            filename=f'StormEvents_details-ftp_v1.0_d{year}_c{revision}.csv.gz';path=self.cache_dir/filename
            try:
                cached=path.exists()
                raw=path.read_bytes() if cached else self.transport(BASE+filename)
                with gzip.open(BytesIO(raw),'rt',encoding='utf-8',errors='replace',newline='') as stream:
                    reader=csv.DictReader(stream)
                    if not {'EVENT_TYPE','STATE_FIPS','CZ_TYPE','CZ_FIPS','EVENT_ID'}<=set(reader.fieldnames or []):raise ValueError('Unexpected NOAA event archive format')
                    year_records=[]
                    for row in reader:
                        if row.get('EVENT_TYPE') in hazards and str(row.get('STATE_FIPS','')).zfill(2) in state_codes:year_records.append(row)
                if not path.exists():path.write_bytes(raw)
                for row in year_records:records[(year,str(row['STATE_FIPS']).zfill(2),row['EVENT_TYPE'])].append(row)
                availability.add(year);provenance.append(dict(year=year,url=BASE+filename,sha256=sha256(raw).hexdigest(),cache_hit=cached,cached_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()))
            except (OSError,ValueError,EOFError):continue
            except Exception:continue
        if not availability:raise RuntimeError('No requested NOAA storm event archives could be loaded')
        result={}
        for hazard in hazards:
            hubs={}
            for ident in identifiers:
                loc=locations[ident];state=loc['county_fips'][:2];county=loc['county_fips'][2:]
                state_rows=[(year,row) for year in availability for row in records[(year,state,hazard)]]
                output={}
                for n in periods:
                    years=set(range(end_year-n+1,end_year+1));covered=len(years&availability)
                    period_rows=[row for year,row in state_rows if year in years]
                    # Scope is computed per period so chat and table agree for the same window.
                    county_only=bool(period_rows) and all(row.get('CZ_TYPE')=='C' for row in period_rows)
                    scope='county' if county_only else 'state'
                    rows=[row for row in period_rows if scope=='state' or str(row.get('CZ_FIPS','')).zfill(3)==county]
                    unique={row['EVENT_ID']:row for row in rows if row.get('EVENT_ID')};event_count=len(unique);freq=event_count/max(covered,1)
                    magnitudes=[];physical=[]
                    for row in unique.values():
                        try:
                            if hazard=='Tornado':
                                match=re.fullmatch(r'EF([0-5])',row.get('TOR_F_SCALE','').strip(),re.I)
                                if match:
                                    physical.append(int(match.group(1)));magnitudes.append((int(match.group(1))+1)/6)
                            elif hazard=='Hail':
                                value=float(row['MAGNITUDE']);
                                if value>0:
                                    physical.append(value);magnitudes.append(min(value/event_benchmarks['hail_inches'],1))
                            elif hazard in ('Thunderstorm Wind','Strong Wind','High Wind'):
                                value=float(row['MAGNITUDE']);
                                if value>0:
                                    physical.append(value);magnitudes.append(min(value/event_benchmarks['wind_knots'],1))
                        except (ValueError,KeyError,TypeError):pass
                    severity=sum(magnitudes)/len(magnitudes)*100 if magnitudes else None
                    recovery=sum(recovery_days[min(int(m*3),2)] for m in magnitudes)/len(magnitudes) if magnitudes else None
                    score=round((weights[0]*min(100,freq/frequency_benchmark*100)+weights[1]*severity+weights[2]*min(100,recovery/recovery_benchmark*100))/100,1) if covered/n>=.8 and severity is not None and len(magnitudes)/max(event_count,1)>=.8 else None
                    output[str(n)]=dict(start=f'{end_year-n+1}-01-01',end=f'{end_year}-12-31',archive_years_available=covered,requested_years=n,coverage=covered/n,
                        event_reports=event_count,periods_per_year=round(freq,2),severity_observations=len(magnitudes),average_severity_score=round(severity,1) if severity is not None else None,average_reported_magnitude=round(sum(physical)/len(physical),2) if physical else None,magnitude_unit=('EF rating number' if hazard=='Tornado' else 'inches' if hazard=='Hail' else 'knots' if hazard in ('Thunderstorm Wind','Strong Wind','High Wind') else None),severity_method=('EF0–EF5: (category+1)/6' if hazard=='Tornado' else f"Hail size in inches / {event_benchmarks['hail_inches']} inches" if hazard=='Hail' else f"Wind speed in knots / {event_benchmarks['wind_knots']} knots" if hazard in ('Thunderstorm Wind','Strong Wind','High Wind') else 'No validated comparable severity measure'),
                        assumed_average_recovery_days=round(recovery,2) if recovery is not None else None,index=score,status='scored' if score is not None else 'unscored',geographic_scope=scope,
                        limitation='NOAA records are reports for a county or entire state, not incidents at this hub. Archived years do not establish reporting completeness. Categories and reports may overlap.')
                hubs[ident]=dict(status='available',periods=output,evidence=dict(source='NOAA NCEI Storm Events',geographic_scope='See each period',files=[x for x in provenance],inspected_at=datetime.now(timezone.utc).isoformat()))
            scopes_by_period=[{item['periods'][str(n)]['geographic_scope'] for item in hubs.values()} for n in periods]
            mixed=any(len(scopes)>1 for scopes in scopes_by_period)
            statewide=any('state' in scopes for scopes in scopes_by_period)
            result[hazard]=dict(kind='reported_event',hubs=hubs,warning='Geographic scopes differ: statewide counts can cover events far from the hub.' if mixed else ('Statewide event reports can occur far from either hub.' if statewide else 'County-level reports are not facility observations.'))
        return result
