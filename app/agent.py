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
        named_risk=any(x in text for x in ('hurricane','flood','winter disruption','weather disruption risk'))
        risk_followup=previous.get('action')=='risk' and bool(ids) and not any(word in text for word in ('snow','heat','cold','rain','wind'))
        if (named_risk or risk_followup) and base['location_ids']:
            hazard=('hurricane_flood' if 'hurricane' in text and 'flood' in text else 'flood' if 'flood' in text else 'hurricane' if 'hurricane' in text else 'winter' if 'winter' in text else previous.get('hazard') if risk_followup else 'overall')
            return Intent(**dict(base,action='risk',hazard=hazard,start=None,end=None,threshold=None))
        if any(word in text for word in ['why','explain']):return Intent(**dict(base,action='explain'))
        for word,hazard in [('snow','snow'),('rain','heavy_precipitation'),('heat','heat'),('cold','cold'),('wind','wind')]:
            if word in text:base['hazard']=hazard
        if base['hazard']!=previous.get('hazard'):base['threshold']=None
        if re.search(r'\bsnow(?:fall)?\b',text) and not re.search(r'\bheavy\s+snow(?:fall)?\b',text) and not re.search(r'\b(?:same|previous|that|those)\b',text):base['threshold']=None
        years=re.findall(r'\b(?:19|20)\d{2}\b',text)
        if years:
            base['start']=date(int(years[0]),1,1)
            base['end']=date(int(years[-1]),12,31)
        if 'last year' in text:
            year=datetime.now(timezone.utc).year-1
            base.update(start=date(year,1,1),end=date(year,12,31))
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
        if end<start or (end-start).days>6000 or start.year<1940:
            raise ValueError('Weather analysis supports up to 6001 days starting in 1940 or later')
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
        intent=Intent.model_validate(self.planner(request.message,state,self.store.locations()).model_dump())
        original_plan=intent.model_dump(mode='json')
        intent,adjustments=apply_metric_policy(request.message,intent)
        if request.scenario is not None:
            state['scenario']=ScenarioInput.model_validate(request.scenario).model_dump(mode='json')
        cards=[]
        scenario_result=None
        data_errors=[]
        risk_results=[]
        if intent.action=='clarify':answer=intent.question or 'Please specify registered location IDs and the requested analysis.'
        elif intent.action=='unsupported':answer='Available evidence does not establish flood/hurricane probabilities, blizzards, road closures or flight cancellations. I can analyze snow, precipitation, heat, cold and wind exposure.'
        elif intent.action=='explain':
            if not state.get('last_answer'):answer='Run an analysis first so I can explain its evidence.'
            else:
                answer=state['last_answer']+' The displayed figures come from the recorded evidence and deterministic calculations.'
                risk_results=state.get('last_risk_results',[])
                data_errors=state.get('last_data_errors',[])
        elif intent.action=='risk':
            locations=self.store.locations()
            if not 1<=len(intent.location_ids)<=5 or len(intent.location_ids)!=len(set(intent.location_ids)):raise ValueError('Select between one and five distinct locations')
            if not set(intent.location_ids)<=set(locations):raise ValueError('Unknown location ID')
            hazards={'winter':['winter'],'hurricane':['hurricane'],'flood':['inland_flood','coastal_flood'],'hurricane_flood':['hurricane','inland_flood','coastal_flood'],'overall':['winter','hurricane','inland_flood','coastal_flood']}.get(intent.hazard)
            if not hazards:raise ValueError('Specify a supported county hazard')
            for loc in intent.location_ids:
                fips=locations[loc].get('county_fips')
                if not fips:
                    data_errors.append(dict(location_id=loc,error='County FIPS unavailable'))
                    continue
                try:
                    result=self.fema.fetch(fips)
                    result['location_id']=loc
                    result['selected_scores']={h:result['scores'][h] for h in hazards}
                    if any(v is None for v in result['selected_scores'].values()):data_errors.append(dict(location_id=loc,error='One or more selected hazard scores unavailable'))
                    result['screening_score']=max(result['selected_scores'].values()) if all(v is not None for v in result['selected_scores'].values()) else None
                    risk_results.append(result)
                except (RuntimeError,ValueError) as exc:data_errors.append(dict(location_id=loc,error=str(exc)))
            complete=not data_errors
            if complete and len(hazards)==1:risk_results.sort(key=lambda r:(-r['screening_score'],r['location_id']))
            def name(item):return item['location_id'].replace('example_','Example ').replace('_',' ').title()
            if complete and len(hazards)==1 and len(risk_results)>1:
                top=risk_results[0]['screening_score']
                leaders=[name(item) for item in risk_results if item['screening_score']==top]
                label=hazards[0].replace('_',' ')
                answer=(' and '.join(leaders)+' rank'+('s' if len(leaders)==1 else '')+' highest among the selected hubs for the '+label+' county screening measure.\n\n')
                answer+='\n'.join(f"{index}. {name(item)}: {item['screening_score']:.1f} out of 100" for index,item in enumerate(risk_results,1))
            else:
                answer=('County hazard comparison:' if complete else 'Comparison incomplete; no complete ranking.')
                for item in risk_results:
                    answer+='\n'+name(item)+': '+', '.join(k.replace('_',' ')+' '+(f'{v:.1f} out of 100' if v is not None else 'unavailable') for k,v in item['selected_scores'].items())+'.'
            answer+='\n\nWhat this means: FEMA compares each county\'s estimated annual community losses for the hazard with counties nationwide; a higher score means a higher relative ranking. These figures reflect county-wide people and property, not facility-specific disruption probabilities or the chance a hub will close.'
            if len(hazards)>1:answer+=' Hazard categories are shown separately; the highest component is an illustrative screening indicator, not a FEMA composite.'
            if data_errors:answer+='\n\nMissing evidence: '+ '; '.join(e['location_id']+': '+e['error'] for e in data_errors)+'.'
            state['intent']=intent.model_dump(mode='json')
            state['last_answer']=answer
            state['last_risk_results']=risk_results
            state['last_data_errors']=data_errors
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
                if end<start or (end-start).days>6000 or start.year<1940:raise ValueError('Invalid or excessive weather period')
                requests={i:WeatherRequest(registered[i]['latitude'],registered[i]['longitude'],start,end,registered[i]['timezone']) for i in intent.location_ids}
                snapshot=self.weather.fetch_group(requests,hazard=hazard)
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
        planning=dict(mode=self.mode,model_plan=original_plan,applied_plan=intent.model_dump(mode='json'),policy_adjustments=adjustments,model_response=getattr(self.planner,'last_metadata',None))
        state['last_planning']=planning
        state['last_mode']=self.mode
        self.store.save(identifier,state)
        return dict(conversation_id=identifier,answer=answer,cards=cards,risk_results=risk_results,scenario_result=scenario_result,mode=self.mode,data_errors=data_errors,result_status='partial' if data_errors else 'complete',planning=planning,model_config=(self.planner.config.public() if hasattr(self.planner,'config') else dict(provider='demo',model='deterministic-parser',configured=True)),intent=intent.model_dump(mode='json'),
                    notice='Demo parser; weather requests still use the real API/cache.' if self.mode=='demo' else 'AI selects a validated analysis; numerical answers are generated by code.')

    @staticmethod
    def describe(r):
        if r['exceedance_percent'] is None:return r['location_id']+': insufficient valid data.'
        label={'snowfall_sum':'daily snowfall','precipitation_sum':'daily precipitation','temperature_2m_max':'daily maximum temperature','temperature_2m_min':'daily minimum temperature','wind_speed_10m_max':'daily maximum wind speed'}[r['variable']]
        return (f"{r['location_id']}: {r['exceedance_days']} of {r['valid_days']} valid days ({r['exceedance_percent']:.2f}%) "
                f"had {label} {r['operator']} {r['threshold']} {r['unit']} during {r['start']}–{r['end']}. "
                f"Consecutive threshold days formed {r['observed_event_runs']} observed {'period' if r['observed_event_runs']==1 else 'periods'}; the longest lasted {r['longest_observed_run_days']} {'day' if r['longest_observed_run_days']==1 else 'days'}. "
                f"Missing days: {r['missing_days']}. Trend: {r['trend'].get('direction','insufficient evidence')}. This is exposure, not predicted shutdown. "
                f"Source: {r.get('evidence',{}).get('source','unspecified')}.")
