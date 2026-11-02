"""Compare two illustrative hubs using transparent, non-probabilistic metrics."""
from datetime import date, datetime, timezone
from .schemas import HubComparisonRequest,HubRankingRequest
from .weather import WeatherRequest, finite, trend
from .weather_sources import WeatherSources
from .noaa import NOAAClient

BANDS={'snow':[5,15,25],'heavy_precipitation':[25,50,100],'wind':[50,75,100],'heat':[35,40,45],'cold':[-10,-20,-30]}
VARIABLES={'snow':('snowfall_sum','cm'),'heavy_precipitation':('precipitation_sum','mm'),'wind':('wind_speed_10m_max','km/h'),'heat':('temperature_2m_max','C'),'cold':('temperature_2m_min','C')}
PERIODS=(5,10,20,30)


def daily_measure(rows,start,end,hazard,bands,recovery,frequency_benchmark,recovery_benchmark,weights,include_trend=True):
    variable,unit=VARIABLES[hazard]
    observations={row['date']:row.get(variable) for row in rows if start.isoformat()<=row['date']<=end.isoformat()}
    expected=(end-start).days+1
    valid=sum(v is not None and finite(v) for v in observations.values())
    coverage=valid/expected
    # A missing date breaks an observed run; period peaks determine severity.
    from datetime import timedelta
    day=start; current=0; current_value=None; peaks=[]; peak_values=[]
    while day<=end:
        value=observations.get(day.isoformat()); level=0
        if value is not None and finite(value):
            for i,b in enumerate(bands):
                if value<=b if hazard=='cold' else value>=b:level=i+1
        if level:
            current=max(current,level)
            current_value=value if current_value is None else (min(current_value,value) if hazard=='cold' else max(current_value,value))
        elif current:
            peaks.append(current);peak_values.append(current_value);current=0;current_value=None
        day+=timedelta(days=1)
    if current:peaks.append(current);peak_values.append(current_value)
    years=(end.year-start.year+1)
    frequency=len(peaks)/years
    severity=sum(x/3*100 for x in peaks)/len(peaks) if peaks else 0
    recovery_mean=sum(recovery[x-1] for x in peaks)/len(peaks) if peaks else 0
    frequency_score=min(100,frequency/frequency_benchmark*100)
    recovery_score=min(100,recovery_mean/recovery_benchmark*100)
    score=round((weights[0]*frequency_score+weights[1]*severity+weights[2]*recovery_score)/100,1) if coverage>=.8 else None
    result=dict(start=start.isoformat(),end=end.isoformat(),coverage=round(coverage,4),valid_days=valid,expected_days=expected,
                observed_periods=len(peaks),periods_per_year=round(frequency,2),average_severity_score=round(severity,1),
                average_period_peak=round(sum(peak_values)/len(peak_values),2) if peak_values else None,most_extreme_period_peak=(min(peak_values) if hazard=='cold' else max(peak_values)) if peak_values else None,
                assumed_average_recovery_days=round(recovery_mean,2),index=score,units=unit,bands=bands,
                status='scored' if score is not None else 'insufficient_coverage',
                limitation='Daily threshold periods are not named storms; missing days break periods. Recovery and benchmarks are illustrative; absence of events does not establish safety.')
    if include_trend:
        if years<15:
            result['trend']=dict(status='insufficient_evidence',reason='At least 15 years are required.')
        else:
            annual=[]
            for year in range(start.year,end.year+1):
                metric=daily_measure(rows,date(year,1,1),date(year,12,31),hazard,bands,recovery,frequency_benchmark,recovery_benchmark,weights,False)
                annual.append(dict(year=year,exceedance_percent=metric['index'],eligible_for_trend=metric['index'] is not None))
            result['trend']=trend(annual,start.year,end.year)
            result['trend']['measure']='annual planning index points'
            if result['trend'].get('status')=='descriptive':
                result['trend']['slope_index_points_per_year']=result['trend'].pop('slope_percentage_points_per_year')
                result['trend']['early_five_year_index']=result['trend'].pop('early_five_year_percent')
                result['trend']['recent_five_year_index']=result['trend'].pop('recent_five_year_percent')
    return result

def summarize_comparison(result,period):
    """Summarize two locations without turning missing observations into safety claims."""
    key=str(period);locations=result['locations']
    if len(locations)!=2:return ''
    a,b=locations;names=[a.get('label',a['id']),b.get('label',b['id'])]
    scores=[result['overall'][key].get(x['id']) for x in locations]
    coverage=result['coverage'][key];included=coverage['included_hazards']
    if all(value is not None for value in scores):
        if scores[0]==scores[1]:answer=f'{names[0]} and {names[1]} have the same planning index ({scores[0]:.1f} out of 100) for the scored measures.'
        else:
            winner=0 if scores[0]<scores[1] else 1
            label=', '.join(x.replace('event:','').replace('_',' ') for x in included)
            answer=f'{names[winner]} has the lower planning index for {label} from {result["end_year"]-period+1} to {result["end_year"]} ({scores[winner]:.1f} versus {scores[1-winner]:.1f}).'
        if coverage['partial']:answer+=' This is a partial comparison: there is not enough data to score '+', '.join(x.replace('event:','').replace('_',' ') for x in coverage['excluded_hazards'])+'.'
    else:
        answer=f'There is not enough comparable data to calculate a planning index for both locations for {result["end_year"]-period+1}–{result["end_year"]}.'
        if coverage['partial']:answer+=' This is a partial comparison.'
        if coverage['excluded_locations']:answer+=' Missing comparable data for: '+', '.join(coverage['excluded_locations'])+'.'
    for name,group in result['hazards'].items():
        if group.get('kind')!='reported_event':continue
        items=[group.get('hubs',{}).get(x['id'],{}).get('periods',{}).get(key,{}) for x in locations]
        if group.get('error'):
            answer+=f" {name.replace('event:','')} reports are unavailable: {group['error']}."
            continue
        if all('event_reports' in item for item in items):
            def area(index):
                scope=items[index].get('geographic_scope','unknown')
                return (f"the county containing {names[index]}" if scope=='county' else f"{names[index]}'s state ({locations[index].get('state','unknown')})" if scope=='state' else f"the area around {names[index]}")
            answer+=f" {name.replace('event:','')}: NOAA recorded {items[0]['event_reports']} reports in {area(0)} and {items[1]['event_reports']} in {area(1)}."
            comparable=all(item.get('coverage',0)>=.8 and item.get('geographic_scope')=='county' for item in items)
            if comparable and items[0]['event_reports']!=items[1]['event_reports']:
                larger=0 if items[0]['event_reports']>items[1]['event_reports'] else 1
                answer+=f' This may indicate more reported area exposure near {names[larger]}, but does not establish facility risk.'
            else:answer+=' Reporting gaps or geographic differences prevent a reliable facility-risk conclusion.'
    trends=[]
    for hazard in included:
        group=result['hazards'][hazard]
        if group.get('kind')!='daily':continue
        for item in locations:
            t=group.get('hubs',{}).get(item['id'],{}).get('periods',{}).get(key,{}).get('trend',{})
            if t.get('status')=='descriptive' and t.get('direction') in ('increasing','decreasing'):
                trends.append(f"{item.get('label',item['id'])}'s {hazard.replace('_',' ')} index shows a {t['direction']} historical trend")
    if trends:answer+=' '+'. '.join(trends)+'.'
    elif period<15:answer+=' This period is too short to establish a trend.'
    else:answer+=' The available evidence does not establish a clear trend.'
    return answer+' Recovery settings are illustrative; the index is not a probability of shutdown.'


def compare_hubs(service,payload,now=None,periods=None,end_year=None,allow_many=False):
    config=(HubRankingRequest if allow_many else HubComparisonRequest).model_validate(payload)
    from .storm_events import EVENT_TYPES, StormEventsClient
    locations=service.store.locations()
    if not set(config.locations)<=set(locations):raise ValueError('Unknown hub ID')
    daily=[x for x in config.hazards if x in BANDS]
    events=[x[6:] for x in config.hazards if x.startswith('event:') and x[6:] in EVENT_TYPES]
    if len(daily)+len(events)!=len(config.hazards):raise ValueError('Unknown weather event type')
    if set(config.bands)-set(daily):raise ValueError('Bands supplied for unselected weather type')
    bands={}
    for hazard in daily:
        values=config.bands.get(hazard,BANDS[hazard])
        if len(values)!=3 or any(not finite(v) for v in values) or len(set(values))!=3 or values!=sorted(values,reverse=hazard=='cold'):
            raise ValueError('Severity bands must have three ordered finite values for '+hazard)
        bands[hazard]=values
    periods=tuple(periods or PERIODS)
    if not periods or any(type(n) is not int or n<1 or n>30 for n in periods):raise ValueError('Comparison periods must be 1 to 30 years')
    end_year=end_year or (now or datetime.now(timezone.utc)).year-1
    if end_year>=(now or datetime.now(timezone.utc)).year or end_year-max(periods)+1<1940:raise ValueError('Comparison requires complete historical years since 1940')
    end=date(end_year,12,31);start=date(end_year-29,1,1)
    response=dict(locations=[locations[x] for x in config.locations],end_year=end_year,periods=list(periods),selected_period=getattr(config,'selected_period',periods[0]),weights=config.weights,
                  assumptions=dict(bands=bands,event_benchmarks=config.event_benchmarks,recovery_days=config.recovery_days,frequency_benchmark=config.frequency_benchmark,recovery_benchmark=config.recovery_benchmark,minimum_coverage=.8,
                  warning='Illustrative planning index, not a probability, prediction, or operational loss estimate.'),hazards={})
    for hazard in daily:
        if not isinstance(service.weather,WeatherSources):
            if config.weather_source=='noaa':raise ValueError('Weather provider does not support NOAA selection')
            class PrimaryAdapter:
                def fetch(self,request,refresh=False):return service.weather.fetch(request)
            client=WeatherSources(primary=PrimaryAdapter(),source='open-meteo')
            secondary=client.secondary
        else:secondary=service.weather.secondary
        if isinstance(secondary,NOAAClient):secondary=NOAAClient(cache_dir=secondary.cache_dir,transport=secondary.transport,max_candidates=secondary.max_candidates,radius_km=secondary.radius_km,min_coverage=.8)
        if isinstance(service.weather,WeatherSources):client=WeatherSources(service.weather.primary,secondary,config.weather_source)
        result={i:dict(status='available',periods={}) for i in config.locations}
        # Each horizon is fetched independently so a station without 30 years of history
        # can still contribute a valid five-year analysis. Each horizon uses one source.
        for n in sorted(periods,reverse=True):
            period_start=date(end_year-n+1,1,1)
            requests={i:WeatherRequest(locations[i]['latitude'],locations[i]['longitude'],period_start,end,locations[i]['timezone']) for i in config.locations}
            try:data=client.fetch_group(requests,hazard=hazard)
            except (RuntimeError,ValueError) as exc:data={i:exc for i in config.locations}
            for identifier in config.locations:
                value=data[identifier]
                if isinstance(value,Exception):
                    result[identifier]['periods'][str(n)]=dict(status='unavailable',error=str(value),index=None)
                    continue
                measure=daily_measure(value['rows'],period_start,end,hazard,bands[hazard],config.recovery_days,config.frequency_benchmark,config.recovery_benchmark,config.weights)
                measure['evidence']=value['evidence']
                result[identifier]['periods'][str(n)]=measure
        response['hazards'][hazard]=dict(kind='daily',hubs=result)
    if events:
        try:
            event_results=(getattr(service,'storm_events',None) or StormEventsClient()).compare(locations,config.locations,events,end_year,periods,config.weights,config.frequency_benchmark,config.recovery_benchmark,config.recovery_days,config.event_benchmarks)
            response['hazards'].update({'event:'+k:v for k,v in event_results.items()})
        except (RuntimeError,ValueError) as exc:
            for name in events:response['hazards']['event:'+name]=dict(kind='reported_event',error=str(exc),hubs={})
    overall={};coverage={}
    for n in periods:
        def score(hazard,identifier):
            return response['hazards'][hazard].get('hubs',{}).get(identifier,{}).get('periods',{}).get(str(n),{}).get('index')
        eligible=[i for i in config.locations if any(score(h,i) is not None for h in config.hazards)]
        common=[h for h in config.hazards if eligible and all(score(h,i) is not None for i in eligible)]
        excluded=[h for h in config.hazards if h not in common]
        values={i:(round(sum(score(h,i) for h in common)/len(common),1) if common and i in eligible else None) for i in config.locations}
        overall[str(n)]=values
        coverage[str(n)]=dict(included_hazards=common,excluded_hazards=excluded,excluded_locations=[i for i in config.locations if i not in eligible],partial=bool(excluded or len(eligible)!=len(config.locations)))
    response['overall']=overall;response['coverage']=coverage
    response['summaries']={str(n):summarize_comparison(response,n) for n in periods}
    return response
