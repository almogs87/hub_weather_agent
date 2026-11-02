"""Bounded model planning; all weather and scenario numbers are code-generated."""
from datetime import date, datetime, timezone
import json
import os
import re
from urllib.request import Request, urlopen
from .schemas import Intent, Location, ScenarioInput
from .storage import Store
from .weather import WeatherClient, WeatherRequest, exposure, trend, rank_exposure
from .winter import WinterProfile, snowfall_disruptions
from .scenarios import Hub, Demand, evaluate, validate
from .replay_report import enrich_report
from .intent_policy import apply_metric_policy
from .weather_sources import WeatherSources
from .fema import FEMAClient

from .providers import OpenAIPlanner, ModelConfig, build_planner

class DemoPlanner:
    """Explicit offline parser for interface tests, not an AI substitute."""
    def __call__(self,message,state,locations):
        text=message.lower()
        if re.search(r'\b(?:what|which|list)\b.*\b(?:weather|hazards?|events?)\b.*\b(?:support|available|analy[sz]e|ask|answer|types?)\b|\b(?:supported|available)\s+(?:weather|hazards?|events?)\b',text):
            return Intent(action='capabilities',location_ids=[],hazard=None,start=None,end=None,threshold=None,question=None)
        if re.search(r'\bsnow\s*(?:depth|height|on the ground)\b',text):
            return Intent(action='clarify',location_ids=[],hazard=None,start=None,end=None,threshold=None,question='Snow depth on the ground is not available here. Ask about new snowfall per day instead.')
        if re.search(r'\d+(?:\.\d+)?\s*(?:cm|mm|inches|inch)\b',text):
            return Intent(action='clarify',location_ids=[],hazard=None,start=None,end=None,threshold=None,question='Demo mode cannot reliably interpret custom amounts. Use live AI mode or ask for heavy snow, defined here as more than 15 cm of new snowfall in a day.')
        if message.lstrip().startswith('{'):
            return Intent(action='clarify',location_ids=[],hazard=None,start=None,end=None,threshold=None,question='Paste network JSON into the Scenario JSON field below and click Run replay; the chat box expects a question.')
        previous=state.get('intent',{})
        base=dict(action='weather',location_ids=[],hazard=previous.get('hazard') or 'snow',start=previous.get('start'),end=previous.get('end'),threshold=previous.get('threshold'),question=None)
        if any(word in text for word in ['flight','blizzard','road closure']):
            return Intent(**dict(base,action='unsupported'))
        if 'replay' in text:return Intent(**dict(base,action='winter_replay'))
        ids=[i for i in locations if re.search(r'(?<!\w)'+re.escape(i.lower())+r'(?!\w)',text)]
        if 'midwest' in text:ids=[i for i,loc in locations.items() if loc.get('region','').lower()=='midwest']
        base['location_ids']=ids or previous.get('location_ids',[])
        years=re.findall(r'\b(?:19|20)\d{2}\b',text)
        if years:
            base['start']=date(int(years[0]),1,1)
            base['end']=date(int(years[-1]),12,31)
        if 'last year' in text:
            year=datetime.now(timezone.utc).year-1
            base.update(start=date(year,1,1),end=date(year,12,31))
        named_risk=any(x in text for x in ('hurricane','flood','winter disruption','weather disruption risk','ice storm','tornado','drought'))
        risk_followup=previous.get('action')=='risk' and bool(ids) and not any(word in text for word in ('snow','heat','cold','rain','wind'))
        if (named_risk or risk_followup) and base['location_ids']:
            hazard=('hurricane_flood' if 'hurricane' in text and 'flood' in text else 'flood' if 'flood' in text else 'hurricane' if 'hurricane' in text else 'ice_storm' if 'ice storm' in text else 'tornado' if 'tornado' in text else 'drought' if 'drought' in text else 'winter' if 'winter' in text else previous.get('hazard') if risk_followup else 'overall')
            return Intent(**dict(base,action='risk',hazard=hazard,threshold=None))
        if any(word in text for word in ['why','explain']):return Intent(**dict(base,action='explain'))
        for word,hazard in [('snow','snow'),('rain','heavy_precipitation'),('heat','heat'),('cold','cold'),('wind','wind')]:
            if word in text:base['hazard']=hazard
        if base['hazard']!=previous.get('hazard'):base['threshold']=None
        if re.search(r'\bsnow(?:fall)?\b',text) and not re.search(r'\bheavy\s+snow(?:fall)?\b',text) and not re.search(r'\b(?:same|previous|that|those)\b',text):base['threshold']=None
        if 'heavy snow' in text:base['threshold']=15
        if 'compare' in text or 'rank' in text:base['action']='compare'
        if not base['location_ids']:
            base.update(action='clarify',question='Register a location and include its ID in your question.')
        return Intent(**base)

class Service:
    def __init__(self,store=None,weather=None,planner=None,mode='live',fema=None):
        self.store=store or Store()
        self.weather=weather or WeatherSources()
        self.mode=mode
        self.fema=fema or FEMAClient()
        self.planner=planner or (DemoPlanner() if mode=='demo' else build_planner())

    def add_location(self,payload):
        location=Location.model_validate(payload)
        # Validate timezone without performing a data request.
        WeatherRequest(location.latitude,location.longitude,date(2020,1,1),date(2020,1,2),location.timezone).parameters()
        self.store.add_location(location.model_dump())
        return location.model_dump()

    def weather_analysis(self,location_id,start,end,hazard,threshold=None,dataset=None):
        locations=self.store.locations()
        if location_id not in locations:raise ValueError('Unknown location ID: '+location_id)
        if end<start or (end-start).days>10957 or start.year<1940:
            raise ValueError('Weather analysis supports up to 10958 days starting in 1940 or later')
        location=locations[location_id]
        try:
            request=WeatherRequest(location['latitude'],location['longitude'],start,end,location['timezone'])
            data=dataset if dataset is not None else (self.weather.fetch(request,hazard=hazard) if isinstance(self.weather,WeatherSources) else self.weather.fetch(request))
            if isinstance(data,Exception):raise data
        except RuntimeError as exc:
            raise RuntimeError(f'Weather data for {location_id} ({start} through {end}): {exc}') from exc
        result=exposure(data['rows'],start,end,hazard,threshold)
        result.update(location_id=location_id,evidence=data['evidence'],trend=trend(result['annual'],start.year,end.year))
        return result

    def replay(self,payload,weather_snapshot=None):
        scenario=ScenarioInput.model_validate(payload)
        hubs=[Hub(**h.model_dump()) for h in scenario.hubs]
        demands=[Demand(**d.model_dump()) for d in scenario.demands]
        links={(l.hub_id,l.demand_id):l.distance_km for l in scenario.links}
        if len(links)!=len(scenario.links):raise ValueError('Duplicate distance link')
        validate(hubs,demands,links,scenario.max_distance_km,[])
        hub_ids={h.id for h in hubs}
        if set(scenario.hub_locations)!=hub_ids:raise ValueError('Every hub requires exactly one registered weather location')
        locations=self.store.locations()
        events,evidence=[],[]
        weather_rows={}
        profile=WinterProfile()
        if weather_snapshot is None and hasattr(self.weather,'fetch_group'):
            identifiers=set(scenario.hub_locations.values())
            if not identifiers<=set(locations):raise ValueError('Unknown weather location')
            requests={i:WeatherRequest(locations[i]['latitude'],locations[i]['longitude'],scenario.start,scenario.end,locations[i]['timezone']) for i in identifiers}
            weather_snapshot=self.weather.fetch_group(requests,hazard='snow')
        for hub in hubs:
            identifier=scenario.hub_locations[hub.id]
            if identifier not in locations:raise ValueError('Unknown weather location: '+identifier)
            loc=locations[identifier]
            dataset=(weather_snapshot[identifier] if weather_snapshot is not None else
                     self.weather.fetch(WeatherRequest(loc['latitude'],loc['longitude'],scenario.start,scenario.end,loc['timezone'])))
            if isinstance(dataset,Exception):raise dataset
            expected=(scenario.end-scenario.start).days+1
            if len(dataset['rows'])!=expected:raise ValueError('Replay requires every date')
            weather_rows[hub.id]=dataset['rows']
            events.extend(snowfall_disruptions(hub.id,dataset['rows'],profile))
            evidence.append(dict(hub_id=hub.id,**dataset['evidence']))
        result=evaluate(hubs,demands,links,scenario.max_distance_km,scenario.start,scenario.end,events)
        enrich_report(result,hubs,demands,weather_rows,profile)
        result.update(profile=profile.describe(),evidence=evidence,weather_trigger_days=len(events),
                      limitation='Matching reported dates replayed; source-specific observation windows and subdaily overlap are not modeled. No annual loss probabilities inferred.')
        return result

    def chat(self,payload):
        from .schemas import ChatRequest
        request=ChatRequest.model_validate(payload)
        identifier,state=self.store.load(request.conversation_id)
        capability=DemoPlanner()(request.message,{},{} )
        intent=capability if capability.action=='capabilities' else Intent.model_validate(self.planner(request.message,state,self.store.locations()).model_dump())
        original_plan=intent.model_dump(mode='json')
        intent,adjustments=apply_metric_policy(request.message,intent)
        if request.scenario is not None:
            state['scenario']=ScenarioInput.model_validate(request.scenario).model_dump(mode='json')
        cards=[]
        scenario_result=None
        data_errors=[]
        risk_results=[]
        comparison_result=None
        if intent.action=='clarify':answer=intent.question or 'Please specify registered location IDs and the requested analysis.'
        elif intent.action=='capabilities':answer=('I can analyze daily snowfall, precipitation, heat, cold, and maximum wind. For hub comparisons I can also show NOAA reports of floods, hurricanes, tornadoes, and ice storms; those reports may be unscored when comparable severity is unavailable. Historical daily data can use Open-Meteo ERA5 or NOAA stations; NOAA maximum wind is unavailable. Snow depth and actual hub closures are not currently measured.')
        elif intent.action=='unsupported':answer='Available evidence does not establish flood/hurricane probabilities, blizzards, road closures or flight cancellations. I can analyze snow, precipitation, heat, cold and wind exposure.'
        elif intent.action=='explain':
            if not state.get('last_answer'):answer='Run an analysis first so I can explain its evidence.'
            else:
                answer=state['last_answer']+' The displayed figures come from the recorded evidence and deterministic calculations.'
                risk_results=state.get('last_risk_results',[])
                data_errors=state.get('last_data_errors',[])
                comparison_result=state.get('last_comparison')
        elif intent.action in ('risk','compare'):
            from .hub_comparison import compare_hubs
            locations=self.store.locations()
            ids=intent.location_ids
            if re.search(r'\bmidwest\b',request.message.lower()):
                ids=[i for i,loc in locations.items() if loc.get('region','').lower()=='midwest']
                intent=intent.model_copy(update=dict(location_ids=ids))
            if not ids or len(ids)!=len(set(ids)) or len(ids)>25:raise ValueError('Select between one and 25 distinct locations')
            if not set(ids)<=set(locations):raise ValueError('Unknown location ID')
            mapping={'winter':['snow','event:Ice Storm'],'hurricane':['event:Hurricane (Typhoon)'],
                     'flood':['event:Flood','event:Flash Flood'],'hurricane_flood':['event:Hurricane (Typhoon)','event:Flood','event:Flash Flood'],
                     'overall':['snow','event:Ice Storm','event:Flood','event:Flash Flood','event:Hurricane (Typhoon)'],
                     'ice_storm':['event:Ice Storm'],'tornado':['event:Tornado'],'drought':['event:Drought'],
                     'snow':['snow'],'heavy_precipitation':['heavy_precipitation'],'heat':['heat'],'cold':['cold'],'wind':['wind']}
            selected=mapping.get(intent.hazard or 'snow')
            if not selected:raise ValueError('Specify a supported hazard')
            default_threshold={'snow':0,'heavy_precipitation':25,'heat':35,'cold':-10,'wind':50}.get(intent.hazard)
            if intent.action=='compare' and intent.threshold is not None and intent.threshold!=default_threshold:
                answer='Custom thresholds for the planning index are set under Index assumptions. Use those settings and ask again.'
            else:
                period=10;end_year=None
                if intent.start is not None or intent.end is not None:
                    if not intent.start or not intent.end or (intent.start.month,intent.start.day)!=(1,1) or (intent.end.month,intent.end.day)!=(12,31):
                        raise ValueError('Index comparisons require complete calendar years')
                    period=intent.end.year-intent.start.year+1;end_year=intent.end.year
                settings=request.index_settings.model_dump() if request.index_settings else {}
                settings['bands']={k:v for k,v in settings.get('bands',{}).items() if k in selected}
                source=request.weather_source or os.environ.get('WEATHER_SOURCE','auto')
                comparison_result=compare_hubs(self,dict(locations=ids,hazards=selected,weather_source=source,**settings),periods=[period],end_year=end_year,allow_many=True)
                period_key=str(period);values=comparison_result['overall'][period_key];coverage=comparison_result['coverage'][period_key]
                ranked=sorted(((score,identifier) for identifier,score in values.items() if score is not None),key=lambda item:(-item[0],item[1]))
                start_year=comparison_result['end_year']-period+1
                included=', '.join(x.replace('event:','').replace('_',' ') for x in coverage['included_hazards'])
                answer=f'Planning comparison for {start_year} to {comparison_result["end_year"]}. '
                if ranked:
                    answer+=f'Based on {included}, the available index is:'
                    answer+='\n'+'\n'.join(f'{n}. {locations[i].get("label",i).replace("_"," ").title()}: {score:.1f} / 100' for n,(score,i) in enumerate(ranked,1))
                else:answer+='There is not enough comparable evidence to calculate an index.'
                if coverage['partial']:
                    answer+='\n\nThis is a partial comparison.'
                    if coverage['excluded_hazards']:answer+=' Not enough data to score: '+', '.join(x.replace('event:','').replace('_',' ') for x in coverage['excluded_hazards'])+'.'
                    for hazard in coverage['excluded_hazards']:
                        group=comparison_result['hazards'].get(hazard,{})
                        if group.get('kind')!='reported_event':continue
                        if group.get('error'):
                            answer+='\n'+hazard.replace('event:','')+' data unavailable: '+group['error']+'.'
                            continue
                        reports=[]
                        for location_id in ids:
                            item=group.get('hubs',{}).get(location_id,{}).get('periods',{}).get(period_key,{})
                            if 'event_reports' in item:
                                reports.append(f"{locations[location_id].get('label',location_id)}: {item['event_reports']} reports ({item.get('geographic_scope','unknown scope')}, {item.get('archive_years_available','?')}/{item.get('requested_years','?')} archive years)")
                        if reports:answer+='\n'+hazard.replace('event:','')+' reports: '+ '; '.join(reports)+'. These are area reports, not hub incidents.'
                    if coverage['excluded_locations']:answer+=' Locations without comparable scores: '+', '.join(coverage['excluded_locations'])+'.'
                    data_errors=[dict(location_id=i,error='Insufficient comparable evidence') for i in coverage['excluded_locations']]
                    if not data_errors:data_errors=[dict(location_id='',error='One or more selected hazards are unscored')]
                warnings=[v['warning'] for v in comparison_result['hazards'].values() if v.get('warning')]
                if warnings:answer+='\n\n'+' '.join(dict.fromkeys(warnings))
                answer+='\n\nThis index uses frequency, severity and assumed recovery; it is not the probability of a shutdown.'
                if len(ids)==2:answer=comparison_result['summaries'][period_key]
                state['intent']=intent.model_dump(mode='json');state['last_answer']=answer
                state['last_risk_results']=[];state['last_data_errors']=data_errors;state['last_comparison']=comparison_result
        elif intent.action=='winter_replay':
            if not state.get('scenario'):
                answer='Supply a network in the scenario form, then ask for a winter replay. I will not invent facilities, capacities or backup links.'
            else:
                scenario_result=self.replay(state['scenario'])
                answer=(f"Winter replay: {scenario_result['incremental_unserved_demand_days']:.2f} incremental unserved demand-days; "
                        f"minimum daily service {100*scenario_result['minimum_served_fraction']:.1f}%. Capacity loss and recovery are illustrative assumptions, not observed closures.")
                state['last_answer']=answer
        else:
            if intent.hazard not in (None, 'snow', 'heavy_precipitation', 'heat', 'cold', 'wind'):
                raise ValueError('Historical weather requires a supported weather hazard')
            if not 1<=len(intent.location_ids)<=5:raise ValueError('Select between one and five registered locations')
            if len(intent.location_ids)!=len(set(intent.location_ids)):raise ValueError('Duplicate location IDs')
            start=intent.start or date(2011,1,1)
            end=intent.end or date(2025,12,31)
            hazard=intent.hazard or 'snow'
            snapshot=None
            if hasattr(self.weather,'fetch_group'):
                registered=self.store.locations()
                if not set(intent.location_ids)<=set(registered):raise ValueError('Unknown location ID')
                if end<start or (end-start).days>10957 or start.year<1940:raise ValueError('Invalid or excessive weather period')
                requests={i:WeatherRequest(registered[i]['latitude'],registered[i]['longitude'],start,end,registered[i]['timezone']) for i in intent.location_ids}
                selected=self.weather
                if request.weather_source is not None:
                    if not isinstance(self.weather,WeatherSources):raise ValueError('Weather source selection is not supported by this weather provider')
                    selected=WeatherSources(primary=self.weather.primary,secondary=self.weather.secondary,source=request.weather_source)
                snapshot=selected.fetch_group(requests,hazard=hazard)
            for loc in intent.location_ids:
                try:
                    cards.append(self.weather_analysis(loc,start,end,hazard,intent.threshold,dataset=snapshot[loc] if snapshot is not None else None))
                except RuntimeError as exc:
                    if intent.action!='compare':raise
                    data_errors.append(dict(location_id=loc,error=str(exc)))
            if intent.action=='compare' and data_errors:
                answer='Comparison incomplete: no complete ranking was produced. Unavailable locations: '+', '.join(e['location_id'] for e in data_errors)+'. '
                answer+=' '.join(e['error'] for e in data_errors)+' Available results: '
            elif intent.action=='compare':
                ranked=rank_exposure(cards)
                cards=ranked['ranked']
                excluded=ranked['excluded']
                answer='Ranked by exceedance-day percentage. '+('Excluded for inadequate coverage: '+', '.join(excluded)+'. ' if excluded else '')
            else:answer=''
            answer+=' '.join(self.describe(r) for r in cards)
            intent=intent.model_copy(update=dict(start=start,end=end,hazard=hazard))
            state['intent']=intent.model_dump(mode='json')
            state['last_answer']=answer
            state['last_risk_results']=[]
            state['last_data_errors']=data_errors
            state['last_comparison']=None
        planning=dict(mode=self.mode,model_plan=original_plan,applied_plan=intent.model_dump(mode='json'),policy_adjustments=adjustments,model_response=getattr(self.planner,'last_metadata',None))
        state['last_planning']=planning
        state['last_mode']=self.mode
        self.store.save(identifier,state)
        return dict(conversation_id=identifier,answer=answer,cards=cards,risk_results=risk_results,comparison_result=comparison_result,scenario_result=scenario_result,mode=self.mode,data_errors=data_errors,result_status='partial' if data_errors else 'complete',planning=planning,model_config=(self.planner.config.public() if hasattr(self.planner,'config') else dict(provider='demo',model='deterministic-parser',configured=True)),intent=intent.model_dump(mode='json'),
                    notice='Demo parser; weather requests still use the real API/cache.' if self.mode=='demo' else 'AI selects a validated analysis; numerical answers are generated by code.')

    @staticmethod
    def describe(r):
        if r['exceedance_percent'] is None:return r['location_id']+': insufficient valid data.'
        label={'snowfall_sum':'snowfall','precipitation_sum':'heavy precipitation','temperature_2m_max':'hot weather','temperature_2m_min':'cold weather','wind_speed_10m_max':'strong winds'}[r['variable']]
        name=r['location_id'].replace('_',' ').title()
        start,end=r['start'][:4],r['end'][:4]
        period=start if start==end and r['start'].endswith('01-01') and r['end'].endswith('12-31') else f"{r['start']} to {r['end']}"
        qualifying='heavy snowfall' if r['variable']=='snowfall_sum' and r['threshold']>0 else label
        answer=f"In {period}, {name} had {qualifying} on about {r['exceedance_percent']:.1f}% of days with available data."
        if r['observed_event_runs']:
            answer+=f" The longest consecutive period lasted {r['longest_observed_run_days']} {'day' if r['longest_observed_run_days']==1 else 'days'}."
        if r['missing_days']:answer+=f" Some days are missing from the record ({r['missing_days']} days)."
        return answer
