"""Paired network comparison with frozen historical weather evidence."""
from .schemas import ComparisonInput
from .scenarios import Hub,Demand,validate
from .weather import WeatherRequest

def compare_networks(service,payload):
    config=ComparisonInput.model_validate(payload)
    # Validate every network before making any external request.
    for scenario in (config.reference,config.candidate):
        links={(l.hub_id,l.demand_id):l.distance_km for l in scenario.links}
        if len(links)!=len(scenario.links):raise ValueError('Duplicate distance link')
        validate([Hub(**h.model_dump()) for h in scenario.hubs],[Demand(**d.model_dump()) for d in scenario.demands],links,scenario.max_distance_km,[])
        if set(scenario.hub_locations)!={h.id for h in scenario.hubs}:
            raise ValueError('Every hub requires exactly one weather location')
    identifiers=set(config.reference.hub_locations.values())|set(config.candidate.hub_locations.values())
    locations=service.store.locations()
    if not identifiers<=set(locations):raise ValueError('Comparison contains unknown weather locations')
    snapshot={}
    for identifier in sorted(identifiers):
        loc=locations[identifier]
        snapshot[identifier]=service.weather.fetch(WeatherRequest(loc['latitude'],loc['longitude'],config.reference.start,config.reference.end,loc['timezone']))
    reference=service.replay(config.reference.model_dump(mode='json'),weather_snapshot=snapshot)
    candidate=service.replay(config.candidate.model_dump(mode='json'),weather_snapshot=snapshot)
    for report,scenario in [(reference,config.reference),(candidate,config.candidate)]:
        report['network_summary']=dict(hub_count=len(scenario.hubs),installed_daily_capacity=sum(h.capacity for h in scenario.hubs))
    daily=[]
    common_units=reference_km=candidate_km=0
    for a,b in zip(reference['days'],candidate['days']):
        daily.append(dict(date=a['date'],reference_unserved=a['unserved_units'],candidate_unserved=b['unserved_units'],
                          avoided_unserved=a['unserved_units']-b['unserved_units'],
                          reference_service_percent=100*a['served_fraction'],candidate_service_percent=100*b['served_fraction']))
        for area in config.reference.demands:
            def totals(day):
                assigned=[r for r in day['assignments'] if r['demand_id']==area.id]
                units=sum(r['units'] for r in assigned)
                km=sum(r['units']*r['distance_km'] for r in assigned)
                return units,km/units if units else 0
            au,ad=totals(a)
            bu,bd=totals(b)
            matched=min(au,bu)
            common_units+=matched
            reference_km+=matched*ad
            candidate_km+=matched*bd
    avoided=reference['unserved_demand_days']-candidate['unserved_demand_days']
    return dict(reference_name=config.reference_name,candidate_name=config.candidate_name,
        reference=reference,candidate=candidate,daily_comparison=daily,
        comparison=dict(avoided_unserved_demand_days=avoided,
            avoided_unserved_percent=100*avoided/reference['unserved_demand_days'] if reference['unserved_demand_days'] else None,
            avoided_incremental_unserved_demand_days=reference['incremental_unserved_demand_days']-candidate['incremental_unserved_demand_days'],
            minimum_service_improvement_percentage_points=100*(candidate['minimum_served_fraction']-reference['minimum_served_fraction']),
            days_candidate_serves_more=sum(d['avoided_unserved']>1e-8 for d in daily),
            days_candidate_serves_less=sum(d['avoided_unserved']< -1e-8 for d in daily),
            common_served_unit_days=common_units,
            common_service_mean_distance_change_km=(candidate_km-reference_km)/common_units if common_units else None),
        evidence=[dict(location_id=i,**snapshot[i]['evidence']) for i in sorted(snapshot)],
        assumptions=['Identical demand, dates, service-distance limit and snowfall profile; one weather snapshot reused for both networks.',
            'Positive avoided demand means the candidate improves service; a negative value means it is worse.',
            'Distance change matches the smaller served quantity per demand area per day, using each network\'s average assigned distance.',
            'Distance is a transport proxy, not travel time or monetary cost. Hub construction and operating costs are excluded.',
            'Two exposed hubs can be disrupted together. Backup is not assumed weather-independent.',
            'No universal winner: service benefits must be weighed against capacity, cost and distance.'])
