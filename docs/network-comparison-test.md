# Compare networks: manual test

Restart the server and refresh the browser. This is an illustrative capacity test using existing Denver weather, not a site recommendation. Both abstract hubs share the same weather footprint, so this tests spare capacity under co-exposure rather than geographic independence.

## Reference network

Paste into the existing Scenario JSON field:

~~~json
{
  "hubs": [{"id":"A","capacity":100}],
  "demands": [{"id":"X","units":90}],
  "links": [{"hub_id":"A","demand_id":"X","distance_km":10}],
  "max_distance_km":100,
  "start":"2025-01-01",
  "end":"2025-12-31",
  "hub_locations":{"A":"denver"}
}
~~~

## Candidate network

Paste into Candidate network JSON under Compare networks:

~~~json
{
  "hubs": [{"id":"A","capacity":100},{"id":"B","capacity":40}],
  "demands": [{"id":"X","units":90}],
  "links": [
    {"hub_id":"A","demand_id":"X","distance_km":10},
    {"hub_id":"B","demand_id":"X","distance_km":20}
  ],
  "max_distance_km":100,
  "start":"2025-01-01",
  "end":"2025-12-31",
  "hub_locations":{"A":"denver","B":"denver"}
}
~~~

Click Compare networks. The tool rejects different dates, demand or distance limits, and reuses the same weather observations for both networks.

On any day with 5 to below 15 cm snowfall, the reference has 80 available units versus demand 90: 10 unserved. The candidate has 112 available units across A and B: all 90 can be served. Actual totals depend on the historical snowfall in the selected period. Days with greater snowfall follow the stronger profile bands; recovery effects also apply.

Review total unmet demand, weather-added unmet demand, minimum service, installed capacity and matched-service distance change. Positive unmet-demand avoided means the candidate improved service. Construction and operating costs are not included, so this is not an investment recommendation.

The default daily table shows only dates with different service. Uncheck the filter to include all dates. If service is identical, the interface states that rather than claiming a benefit.

For a geographic-diversity experiment, explicitly register a second test location and change B's weather mapping. The same demand, dates and service-distance limit must remain. The supplied distances still need to be plausible; the app does not calculate real road routes.
