# Assumptions and limitations

## Weather and thresholds

ERA5 reanalysis supplies gridded modeled history rather than a sensor at a facility. The same model is pinned throughout the historical window. Complete observations are not proof of perfect accuracy. Local days use the analyst-supplied IANA timezone. Missing observations remain null and are never converted to zero hazard.

Any-snow frequency and operationally consequential snow are different metrics. The daily-snow profile uses analyst assumptions at 5/15/25 cm, with available capacity 80/50/10 percent and additional recovery periods 0/1/2 days. Neither those boundaries nor their consequences are official national standards. Profile version: daily-snow-sensitivity-v1. Change these values and rerun to inspect sensitivity; actual calibration requires company outage records.

NWS heavy-snow warning criteria vary by geography and accumulation window. The current daily local-calendar totals do not reproduce rolling warning windows. Snow squalls can have severe transport effects with little accumulation. Blizzard, freezing rain and airport braking conditions require additional variables/records. The system must not infer those conditions or actual closures from daily snow alone.

References reviewed 2 November 2026:
- https://www.weather.gov/safety/winter-ww
- https://www.weather.gov/safety/winter-snow-squall
- https://www.weather.gov/snow-criteria
- https://ops.fhwa.dot.gov/weather/roadimpact.htm
- https://www.faa.gov/air_traffic/publications/aim_html/chap4_section_3.html
- https://open-meteo.com/en/docs/historical-weather-api

References support the need for differentiated hazards and impact evidence; they do not establish our illustrative hub-capacity fractions or recovery periods. Check provider data/API usage terms before commercial use.

## Network

Candidate facilities and demand are explicit analyst inputs. No locations are selected automatically. Demand/capacity units must match. Distances and eligible links are supplied, not road-network measurements. Capacity can be reallocated each day; unmet demand is not a queue and does not carry forward. No backlog-clearance claim is made. Recovery refers to baseline served throughput, which may already leave demand unserved. The evaluation horizon can truncate recovery.

Alaska, Hawaii and the contiguous US are separate input service components. Geographic component membership is not automatically inferred. Daily regional replay uses matching local dates, preserving day-level co-exposure but not exact simultaneous hours across timezones. Recovery and overlapping effects are assumptions, not historical operational observations.

## Trend and business interpretation

The 15-year window is useful for recurring exposure, but rare-event absence is not safety evidence. Theil-Sen and bootstrap intervals describe this series under stated statistical assumptions; they are not climate attribution, forward probabilities or expected financial loss. Reduced rainfall does not establish reduced flood risk. Rain and wind proxies do not replace flood and hurricane datasets. No population ingestion exists yet; no nationwide service-coverage claim is supported.
