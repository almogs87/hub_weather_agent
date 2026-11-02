"""ERA5 retrieval, validated cache, exposure metrics and descriptive trends."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import time
from statistics import median
from urllib.parse import urlencode, parse_qs
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

UNITS = {'snowfall_sum':'cm','precipitation_sum':'mm','temperature_2m_max':'°C','temperature_2m_min':'°C','wind_speed_10m_max':'km/h'}
HAZARDS = {'snow':('snowfall_sum','>',0),'heavy_precipitation':('precipitation_sum','>=',25),'heat':('temperature_2m_max','>=',35),'cold':('temperature_2m_min','<=',-10),'wind':('wind_speed_10m_max','>=',50)}

def finite(value):
    return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)

@dataclass(frozen=True)
class WeatherRequest:
    latitude: float
    longitude: float
    start: date
    end: date
    timezone: str

    def parameters(self):
        for value,limit in [(self.latitude,90),(self.longitude,180)]:
            if not finite(value) or abs(value)>limit:
                raise ValueError('Invalid coordinates')
        ZoneInfo(self.timezone)
        if self.end<self.start or self.end>=datetime.now(timezone.utc).date():
            raise ValueError('Invalid historical period: end must precede today')
        return dict(latitude=self.latitude,longitude=self.longitude,start_date=self.start.isoformat(),end_date=self.end.isoformat(),timezone=self.timezone,models='era5',daily=','.join(UNITS),temperature_unit='celsius',wind_speed_unit='kmh',precipitation_unit='mm')

def normalize(payload,request):
    request.parameters()
    if not isinstance(payload,dict) or payload.get('error'):
        raise ValueError('Provider error or invalid response')
    daily,units=payload.get('daily',{}),payload.get('daily_units',{})
    stamps=daily.get('time',[])
    dates=[date.fromisoformat(s) for s in stamps]
    if len(dates)!=len(set(dates)) or dates!=sorted(dates) or any(d<request.start or d>request.end for d in dates):
        raise ValueError('Duplicate, unordered or out-of-range dates')
    for variable,unit in UNITS.items():
        if units.get(variable)!=unit or len(daily.get(variable,[]))!=len(dates):
            raise ValueError('Unexpected units/array length: '+variable)
    data={}
    for i,stamp in enumerate(stamps):
        row={}
        for variable in UNITS:
            value=daily[variable][i]
            if value is not None and not finite(value):
                raise ValueError('Nonfinite or nonnumeric observation')
            if value is not None and variable in ('snowfall_sum','precipitation_sum','wind_speed_10m_max') and value<0:
                raise ValueError('Negative snow, precipitation or wind')
            row[variable]=value
        data[stamp]=row
    rows=[]
    day=request.start
    while day<=request.end:
        stamp=day.isoformat()
        rows.append(dict(date=stamp,**data.get(stamp,{v:None for v in UNITS})))
        day+=timedelta(days=1)
    return rows

class WeatherClient:
    def __init__(self,cache_dir='data/cache/weather',transport=None):
        self.cache_dir=Path(cache_dir)
        self.transport=transport or self.download

    @staticmethod
    def download(url):
        for attempt in range(3):
            try:
                request=Request(url,headers={'User-Agent':'hub-weather-agent/0.1','Accept':'application/json'})
                with urlopen(request,timeout=20) as response:
                    return response.read()
            except HTTPError as exc:
                if exc.code not in (502,503,504) or attempt==2:raise
            except (URLError,TimeoutError,OSError) as exc:
                reason=getattr(exc,'reason',exc)
                # Do not retry access-denied conditions or certificate failures.
                denied=getattr(reason,'winerror',None)==10013 or getattr(reason,'errno',None) in (13,10013)
                if denied or 'CERTIFICATE_VERIFY_FAILED' in str(reason) or attempt==2:raise
            time.sleep(.5*(attempt+1))

    def covering_cache(self,request,url):
        """Reuse verified observations when only the date window shrinks."""
        wanted=parse_qs(url.split('?',1)[1])
        candidates=[]
        for path in self.cache_dir.glob('*.json'):
            try:
                envelope=json.loads(path.read_text(encoding='utf-8'))
                source_url=envelope['request_url']
                if source_url.split('?',1)[0]!=url.split('?',1)[0]:continue
                params=parse_qs(source_url.split('?',1)[1])
                if {k:v for k,v in params.items() if k not in ('start_date','end_date')}!={k:v for k,v in wanted.items() if k not in ('start_date','end_date')}:continue
                start=date.fromisoformat(params['start_date'][0])
                end=date.fromisoformat(params['end_date'][0])
                if start>request.start or end<request.end:continue
                raw=envelope['raw_response'].encode('utf-8')
                if sha256(raw).hexdigest()!=envelope['sha256']:continue
                source_request=WeatherRequest(request.latitude,request.longitude,start,end,request.timezone)
                normalize(json.loads(raw),source_request)
                candidates.append(((end-start).days,source_url,envelope,source_request))
            except (ValueError,KeyError,TypeError,OSError):
                continue
        if not candidates:return None
        _,_,envelope,source_request=min(candidates,key=lambda item:(item[0],item[1]))
        return envelope,source_request

    def fetch(self,request,refresh=False):
        url='https://archive-api.open-meteo.com/v1/archive?'+urlencode(request.parameters())
        path=self.cache_dir/(sha256(url.encode()).hexdigest()+'.json')
        source_request=request
        cached=path.exists() and not refresh
        covering=self.covering_cache(request,url) if not cached and not refresh else None
        if covering:
            envelope,source_request=covering
            raw=envelope['raw_response'].encode('utf-8')
            cached=True
        elif cached:
            envelope=json.loads(path.read_text(encoding='utf-8'))
            raw=envelope['raw_response'].encode('utf-8')
            if envelope['sha256']!=sha256(raw).hexdigest() or envelope['request_url']!=url:
                raise ValueError('Cache integrity check failed')
        else:
            try:
                raw=self.transport(url)
            except HTTPError as exc:
                detail=''
                try:
                    error=json.loads(exc.read(4096).decode('utf-8',errors='replace'))
                    detail=str(error.get('reason') or error.get('message') or '')
                except (ValueError,OSError):pass
                detail=' '.join(detail.split())[:300]
                suffix=' Provider reason: '+detail if detail else ''
                raise RuntimeError(f'Weather API rejected the request (HTTP {exc.code}); no matching cached data was available.'+suffix) from exc
            except (URLError,TimeoutError,OSError) as exc:
                reason=getattr(exc,'reason',exc)
                code=getattr(reason,'winerror',None) or getattr(reason,'errno',None)
                detail=f' (connection code {code})' if code else ''
                raise RuntimeError('Weather API connection failed'+detail+'. The requested period is not available in a matching cache. Check network access and retry.') from exc
            envelope=dict(request_url=url,retrieved_at=datetime.now(timezone.utc).isoformat(),sha256=sha256(raw).hexdigest(),raw_response=raw.decode('utf-8'))
        payload=json.loads(raw)
        rows=normalize(payload,source_request)
        rows=[row for row in rows if request.start.isoformat()<=row['date']<=request.end.isoformat()]
        if not cached:
            self.cache_dir.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(envelope,ensure_ascii=False),encoding='utf-8')
            temporary.replace(path)
        return dict(rows=rows,evidence=dict(source='Open-Meteo Historical Weather API',model='ERA5',request_url=envelope['request_url'],analysis_request_url=url,source_start=source_request.start.isoformat(),source_end=source_request.end.isoformat(),subset_from_cache=source_request!=request,retrieved_at=envelope['retrieved_at'],source_id='weather:'+envelope['sha256'],content_sha256=envelope['sha256'],cache_hit=cached,requested_coordinates=[request.latitude,request.longitude],returned_coordinates=[payload.get('latitude'),payload.get('longitude')],timezone=request.timezone,units=UNITS,limitation='Gridded reanalysis, not a facility sensor; weather exposure is not downtime.'))

def exposure(rows,start,end,hazard,threshold=None):
    if hazard not in HAZARDS:
        raise ValueError('Unsupported hazard: rain is not flood probability; wind is not hurricane probability')
    if end<start:
        raise ValueError('End precedes start')
    variable,operator,default=HAZARDS[hazard]
    threshold=default if threshold is None else threshold
    if not finite(threshold):
        raise ValueError('Threshold must be finite')
    data={}
    for row in rows:
        stamp=date.fromisoformat(row['date'])
        if stamp in data:
            raise ValueError('Duplicate observation date')
        value=row.get(variable)
        if value is not None and not finite(value):
            raise ValueError('Invalid observation')
        data[stamp]=value
    annual={}
    valid=hits=current=0
    runs=[]
    intensities=[]
    day=start
    while day<=end:
        a=annual.setdefault(day.year,dict(year=day.year,requested_days=0,valid_days=0,exceedance_days=0))
        a['requested_days']+=1
        value=data.get(day)
        hit=False
        if value is not None:
            valid+=1
            a['valid_days']+=1
            hit=value>threshold if operator=='>' else value>=threshold if operator=='>=' else value<=threshold
            if hit:
                hits+=1
                a['exceedance_days']+=1
                intensities.append(value)
        if hit:
            current+=1
        elif current:
            runs.append(current)
            current=0
        day+=timedelta(days=1)
    if current:
        runs.append(current)
    expected=(end-start).days+1
    for a in annual.values():
        year_days=(date(a['year']+1,1,1)-date(a['year'],1,1)).days
        a['eligible_for_trend']=a['requested_days']==year_days and a['valid_days']/year_days>=.95
        a['exceedance_percent']=100*a['exceedance_days']/a['valid_days'] if a['valid_days'] else None
    return dict(hazard=hazard,variable=variable,operator=operator,threshold=threshold,unit=UNITS[variable],start=start.isoformat(),end=end.isoformat(),expected_days=expected,valid_days=valid,missing_days=expected-valid,completeness=valid/expected,exceedance_days=hits,exceedance_percent=100*hits/valid if valid else None,observed_event_runs=len(runs),longest_observed_run_days=max(runs,default=0),mean_exceedance_intensity=sum(intensities)/len(intensities) if intensities else None,annual=list(annual.values()),assumptions=['Thresholds are configurable analysis assumptions, not official closure criteria.','Percentage denominator is valid days; missing days are not safe days.','Missing days and window boundaries can truncate event runs.','No downtime or economic loss inferred.'])

def _slope(points):
    return median((b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(points) for b in points[i+1:])

def trend(annual,first_year,last_year):
    points=sorted((a['year'],a['exceedance_percent']) for a in annual if a['eligible_for_trend'] and first_year<=a['year']<=last_year)
    early=[v for y,v in points if first_year<=y<first_year+5]
    late=[v for y,v in points if last_year-4<=y<=last_year]
    if last_year-first_year<14 or len(points)<12 or len(early)<4 or len(late)<4:
        return dict(status='insufficient_evidence',eligible_years=len(points))
    slope=_slope(points)
    intercept=median(v-slope*y for y,v in points)
    residuals=[v-intercept-slope*y for y,v in points]
    center=sum(residuals)/len(residuals)
    residuals=[r-center for r in residuals]
    rng=random.Random(87)
    slopes=[]
    for _ in range(400):
        sampled=[]
        while len(sampled)<len(points):
            index=rng.randrange(len(points))
            sampled.extend(residuals[(index+j)%len(points)] for j in range(3))
        slopes.append(_slope([(y,intercept+slope*y+sampled[i]) for i,(y,_) in enumerate(points)]))
    slopes.sort()
    low,high=slopes[9],slopes[389]
    return dict(status='descriptive',eligible_years=len(points),slope_percentage_points_per_year=slope,approximate_95_interval=[low,high],early_five_year_percent=sum(early)/len(early),recent_five_year_percent=sum(late)/len(late),direction='increasing' if low>0 else 'decreasing' if high<0 else 'uncertain',method='Theil-Sen; circular residual block bootstrap, block length 3, 400 samples, seed 87',limitations=['Approximate interval assumes a linear trend and stationary residual blocks.','Missing years can disrupt annual dependence. Inspect the annual series.','Short historical record; not a forecast, climate attribution, or overall safety conclusion.'])

def rank_exposure(results):
    keys=('hazard','operator','threshold','unit','start','end')
    if len({tuple(r[k] for k in keys) for r in results})>1:
        raise ValueError('Cannot rank different definitions or periods')
    signatures={(r.get('evidence',{}).get('dataset_family') or r.get('evidence',{}).get('source'),r.get('evidence',{}).get('model'),r.get('evidence',{}).get('day_basis','local civil day')) for r in results}
    if len(signatures)>1:raise ValueError('Cannot rank mixed weather datasets or day definitions')
    ids=[r['location_id'] for r in results]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate location ID')
    eligible=[r for r in results if r['completeness']>=.95 and r['exceedance_percent'] is not None]
    return dict(ranked=sorted(eligible,key=lambda r:(-r['exceedance_percent'],r['location_id'])),excluded=[r['location_id'] for r in results if r not in eligible],basis='Exceedance percentage; not downtime or financial loss')
