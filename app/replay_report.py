"""Human-readable replay summaries and independent allocation invariant checks."""
def enrich_report(result,hubs,demands,weather,profile):
    capacities={h.id:h.capacity for h in hubs}
    requirements={d.id:d.units for d in demands}
    observations={h:{r['date']:r['snowfall_sum'] for r in rows} for h,rows in weather.items()}
    failures=[]
    affected=[]
    for day in result['days']:
        triggers=[]
        for hub in hubs:
            snow=observations[hub.id][day['date']]
            bands=[b for b in profile.bands if snow>=b.threshold_cm]
            loss=hub.capacity-day['available_capacities'][hub.id]
            if loss>1e-8 or bands:
                triggers.append(dict(hub_id=hub.id,snowfall_cm=snow,
                    rule=f'>= {bands[-1].threshold_cm:g} cm snowfall' if bands else 'Recovery from earlier snowfall',
                    available_capacity=day['available_capacities'][hub.id],capacity_loss=loss))
        day['weather_impacts']=triggers
        if triggers:affected.append(day)
        for hub in hubs:
            assigned=sum(a['units'] for a in day['assignments'] if a['hub_id']==hub.id)
            if assigned>day['available_capacities'][hub.id]+1e-7:
                failures.append(day['date']+': capacity exceeded for '+hub.id)
            if not -1e-7<=day['available_capacities'][hub.id]<=capacities[hub.id]+1e-7:
                failures.append(day['date']+': invalid available capacity')
        for demand in demands:
            assigned=sum(a['units'] for a in day['assignments'] if a['demand_id']==demand.id)
            if abs(assigned+day['unserved_by_area'][demand.id]-requirements[demand.id])>1e-7:
                failures.append(day['date']+': demand balance mismatch for '+demand.id)
        if abs(sum(a['units'] for a in day['assignments'])-day['served_units'])>1e-7:
            failures.append(day['date']+': served total mismatch')
    result['summary']=dict(simulated_days=len(result['days']),affected_days=len(affected),
        days_with_unserved_demand=sum(d['unserved_units']>1e-8 for d in result['days']),
        days_with_additional_shortfall=sum(d['unserved_units']>result['baseline']['unserved_units']+1e-8 for d in result['days']),
        incremental_unserved_demand_days=result['incremental_unserved_demand_days'],
        total_unserved_demand_days=result['unserved_demand_days'],
        lowest_daily_service_percent=100*result['minimum_served_fraction'])
    result['validation']=dict(passed=not failures,checked_days=len(result['days']),failures=failures,
        checks=['Assigned units do not exceed available hub capacity','Available capacity stays within installed capacity',
                'Served plus unserved equals demand for every area','Assignment totals equal reported served units'],
        limitation='Checks accounting consistency, not accuracy of the assumed weather-impact profile.')
    return result
