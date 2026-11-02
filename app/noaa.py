"""NOAA GHCN-Daily station observations; no API key required.
Official format: https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt
"""
from calendar import monthrange
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from .weather import WeatherClient,UNITS

BASE='https://www.ncei.noaa.gov/pub/data/ghcn/daily/'
ELEMENTS={'SNOW':('snowfall_sum',.1),'PRCP':('precipitation_sum',.1),'TMAX':('temperature_2m_max',.1),'TMIN':('temperature_2m_min',.1)}

def distance_km(a,b,c,d):
    lat1,lat2=map(math.radians,(a,c))
    x=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(d-b)/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(x)))

def stations(text,latitude,longitude,radius=100):
    result=[]
    for line in text.splitlines():
        if len(line)<71 or not line.startswith('US'):continue
        try:
            lat,lon=float(line[12:20]),float(line[21:30])
            distance=distance_km(latitude,longitude,lat,lon)
            if distance<=radius:
                result.append(dict(id=line[:11],latitude=lat,longitude=lon,name=line[41:71].strip(),distance_km=distance))
        except ValueError:continue
    return sorted(result,key=lambda s:(s['distance_km'],s['id']))

def parse_daily(text,station_id,request):
    rows={}
    day=request.start
    while day<=request.end:
        rows[day.isoformat()]=dict(date=day.isoformat(),**{v:None for v in UNITS})
        day+=timedelta(days=1)
    seen=set()
    for line in text.splitlines():
        if len(line)<269:raise ValueError('Truncated NOAA daily record')
        if line[:11]!=station_id:raise ValueError('NOAA station identity mismatch')
        year,month=int(line[11:15]),int(line[15:17])
        element=line[17:21]
        if year<request.start.year or year>request.end.year or element not in ELEMENTS:continue
        variable,scale=ELEMENTS[element]
        for number in range(1,monthrange(year,month)[1]+1):
            stamp=date(year,month,number).isoformat()
            if stamp not in rows:continue
            unique=(stamp,element)
            if unique in seen:raise ValueError('Duplicate NOAA element/date')
            seen.add(unique)
            offset=21+(number-1)*8
            value=int(line[offset:offset+5])
            measurement,quality=line[offset+5],line[offset+6]
            # A nonblank quality flag marks a value that failed a QA check.
            # Trace amounts remain numeric zero at reported precision; disclose it.
            if value==-9999 or quality!=' ':continue
            if element in ('SNOW','PRCP') and value<0:raise ValueError('Negative NOAA precipitation/snow')
            rows[stamp][variable]=round(value*scale,6)
    return list(rows.values())

def eligible_inventory(text,element,start_year,end_year,station_ids):
    """Inventory years identify candidate records; actual daily coverage is checked later."""
    eligible=set()
    for line in text.splitlines():
        if len(line)<45 or line[:11] not in station_ids or line[31:35]!=element:continue
        try:
            if int(line[36:40])<=start_year and int(line[41:45])>=end_year:
                eligible.add(line[:11])
        except ValueError:continue
    return eligible

class NOAAClient:
    def __init__(self,cache_dir='data/cache/noaa',transport=None,max_candidates=16,radius_km=100,min_coverage=.95):
        self.cache_dir=Path(cache_dir)
        self.transport=transport or WeatherClient.download
        self.max_candidates=max_candidates
        self.radius_km=radius_km
        if not 0<min_coverage<=1:raise ValueError('Invalid minimum coverage')
        self.min_coverage=min_coverage

    def raw(self,url,refresh=False):
        path=self.cache_dir/(sha256(url.encode()).hexdigest()+'.json')
        cached=path.exists() and not refresh
        if cached:
            envelope=json.loads(path.read_text(encoding='utf-8'))
            if envelope['url']!=url or sha256(envelope['text'].encode()).hexdigest()!=envelope['sha256']:
                raise ValueError('NOAA cache integrity failure')
        else:
            try:text=self.transport(url).decode('ascii')
            except Exception as exc:raise RuntimeError('NOAA download failed for '+url.rsplit('/',1)[-1]+': '+type(exc).__name__) from exc
            envelope=dict(url=url,text=text,sha256=sha256(text.encode()).hexdigest(),retrieved_at=datetime.now(timezone.utc).isoformat())
            self.cache_dir.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(envelope),encoding='utf-8')
        return envelope,cached

    def fetch(self,request,hazard='snow',refresh=False):
        request.parameters()
        if hazard=='wind':raise RuntimeError('NOAA fallback does not support the current daily maximum-wind definition; average wind is not substituted')
        variable={'snow':'snowfall_sum','heat':'temperature_2m_max','cold':'temperature_2m_min','heavy_precipitation':'precipitation_sum'}[hazard]
        catalog,_=self.raw(BASE+'ghcnd-stations.txt',refresh)
        candidates=stations(catalog['text'],request.latitude,request.longitude,self.radius_km)
        element=next(e for e,(v,_) in ELEMENTS.items() if v==variable)
        inventory,_=self.raw(BASE+'ghcnd-inventory.txt',refresh)
        eligible=eligible_inventory(inventory['text'],element,request.start.year,request.end.year,{s['id'] for s in candidates})
        nearby_count=len(candidates)
        candidates=[s for s in candidates if s['id'] in eligible]
        rejected=[]
        for station in candidates[:self.max_candidates]:
            try:
                envelope,cached=self.raw(BASE+'all/'+station['id']+'.dly',refresh)
                rows=parse_daily(envelope['text'],station['id'],request)
                completeness=sum(r[variable] is not None for r in rows)/len(rows)
                if completeness<self.min_coverage:
                    rejected.append(station['id']+f': {completeness:.1%} {variable} coverage (requires {self.min_coverage:.0%})')
                    continue
                return dict(rows=rows,evidence=dict(source='NOAA NCEI GHCN-Daily',model='station observations',dataset_family='noaa-ghcn-daily',
                    day_basis='station-reported observation date',station=station,requested_coordinates=[request.latitude,request.longitude],
                    returned_coordinates=[station['latitude'],station['longitude']],timezone=request.timezone,
                    request_url=envelope['url'],catalog_url=catalog['url'],catalog_sha256=catalog['sha256'],inventory_url=inventory['url'],inventory_sha256=inventory['sha256'],requested_variable_completeness=completeness,
                    retrieved_at=envelope['retrieved_at'],source_id='noaa:'+envelope['sha256'],content_sha256=envelope['sha256'],cache_hit=cached,
                    analysis_start=request.start.isoformat(),analysis_end=request.end.isoformat(),units=UNITS,
                    selection=f'Nearest station within {self.radius_km} km among up to {self.max_candidates} inventory-eligible candidates with {self.min_coverage:.0%} actual coverage',
                    nearby_station_count=nearby_count,inventory_eligible_count=len(candidates),
                    rejected_candidates=rejected,
                    limitation='Station observation periods may differ from local midnight days; elevation and distance affect representativeness. Quality-flagged/missing values excluded. Trace snowfall counts as zero at reported precision. Wind maximum unsupported.'))
            except (RuntimeError,ValueError) as exc:rejected.append(station['id']+': '+str(exc))
        raise RuntimeError('NOAA found no suitable station within '+str(self.radius_km)+f' km with at least {self.min_coverage:.0%} coverage; '+('; '.join(rejected) if rejected else f'{nearby_count} nearby stations, {len(candidates)} inventory-eligible for {element} in {request.start.year}-{request.end.year}'))
