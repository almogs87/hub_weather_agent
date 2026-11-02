# Weather Risk Intelligence Agent: implementation plan

Status: proposed implementation contract, 2 November 2026. No real hubs selected.

## Product and boundaries

Build a conversational weather-exposure and network-scenario evaluator. It accepts analyst-supplied candidate locations and networks; it does not silently select actual facilities. It supports the original assignment's weather statistics, comparisons, deterministic rankings, explanations and follow-ups, plus a bounded backup-capacity scenario.

The company-wide geographic requirement covers all 50 states and DC. Treat Alaska and Hawaii as separate service components; do not model mainland road transfers to them. Territories are an explicit future extension. Report national and per-state coverage, so a population-weighted national metric does not conceal unserved states. A synthetic test demonstrates mechanics only, never nationwide coverage.

Population is a demand proxy, not shipment volume. Daily operational demand and facility capacities use compatible scenario units. Financial loss, optimal facility siting, construction cost, real road closures and validated recovery predictions are outside version one.

## Architecture

Browser chat -> FastAPI /chat -> LLM structured intent -> validated tool dispatcher -> data adapters / deterministic analytics -> structured evidence -> grounded explanation -> browser.

LLM can select approved tools, resolve user references and explain results. It cannot author numerical results, execute arbitrary code, invent hub IDs or modify persisted scenarios without an explicit user request. Validate intent and tool arguments with Pydantic, reject extra fields, limit tool calls and handle clarification explicitly. Explanation output must reference evidence IDs; display deterministic result cards independently of the narrative. Treat retrieved text and API data as data, not instructions.

Suggested stack: Python, FastAPI, Pydantic, SQLite, httpx, NumPy/SciPy, pytest; a small HTML/JavaScript chat served by FastAPI. Select the LLM provider after checking available credentials; keep its adapter isolated. A single application process minimizes deployment effort.

## Storage and reproducibility

SQLite stores scenarios, candidate locations, conversation state, source metadata and analysis results. Raw API responses are cached as compressed files with request parameters, retrieval timestamp and content hash; normalized records retain units and source references. Secrets stay in environment variables and out of logs. A saved scenario records its exact data versions, scoring configuration and assumptions. Demo mode uses clearly labeled fixtures; live mode never silently substitutes fixtures.

## Data contracts

All identifiers are strings. Dates are ISO 8601, timestamps UTC, distances km, temperatures Celsius, precipitation mm, snowfall cm, and wind km/h. Weather dates use the location's configured timezone. Missing values are null, never zero.

### CandidateLocation

- id, label, latitude [-90,90], longitude [-180,180], state_code, timezone
- service_component: contiguous_us | alaska | hawaii
- county_fips: optional; required before county hazard attribution
- capacity_units_per_day: positive, supplied assumption or actual company input
- preparedness: optional descriptive metadata, not automatically scored

### DemandArea

- id, label, state_code, latitude, longitude, service_component
- population: nonnegative; population_vintage, source_id
- demand_units_per_day: nonnegative; derivation: supplied | population_proxy

Version one uses representative points such as county internal points. A point approximation cannot establish that every resident is within a service radius.

### NetworkScenario

- id, name, candidate_location_ids, demand_area_ids
- start_date, end_date, daily simulation step
- max_service_distance_km: positive; explicitly a straight-line distance proxy
- allocation_policy: minimize_unserved_then_distance
- disruptions: explicit Disruption objects
- assumptions, config_version, source_ids

Reject duplicate/unknown IDs, incompatible service components, negative capacity and invalid date ranges. No default speed conversion from straight-line distance to delivery time.

### Disruption

- id, hazard, event_group_id, affected_location_ids
- start_date, duration_days >= 1
- available_capacity_fraction in [0,1]
- recovery_days >= 0
- basis: analyst_assumption | historical_weather_proxy | observed_operational_record

On disruption days use the specified capacity fraction. Thereafter recover linearly to full capacity over recovery_days. Zero recovery_days restores capacity the next day. For overlapping disruptions use the minimum available fraction, not additive losses. Grouped IDs permit simultaneous multi-hub events; they do not establish event probabilities.

### WeatherDaily / Evidence

- location_id, local_date, variable values with units
- source_id, dataset/model, retrieved_at, requested/returned coordinates
- validity/completeness flags

Every analysis result includes metric definition, numerator/denominator where relevant, period, units, data coverage, source IDs, assumptions, limitations and calculation version.

## Public data strategy

1. Open-Meteo Historical Weather API: recurring-weather analysis using an explicitly pinned ERA5 model over 2011-01-01 through 2025-12-31 (15 complete calendar years). Reanalysis is gridded modeled history, not a sensor at the building. Use consistent model and units across the period. Initial variables: snowfall, daily precipitation, temperature extrema and maximum wind speed. Validate model-variable availability and actual responses before declaring the adapter complete.
2. NOAA NCEI Storm Events: evidence of reported significant events, including flood and tropical-system impacts. Reporting units, locations, changing practices and incomplete/lagged records limit interpretation. No reported event is not proof of no hazard. Annual bulk CSV is a supplemental ingestion source, not an invented JSON endpoint. Weather data still comes through a public API as the assignment requires.
3. Census population estimates: demand proxy with an explicit available vintage. Pair population with official geography internal points. Verify the selected endpoint and geographic join before ingestion; do not call an old population vintage current.

Rare flood/hurricane exposure requires a dedicated source adapter or must return 'not supported by available evidence'. Do not substitute heavy-rain frequency for flood probability, or high-wind days for hurricane probability. Do not use community-wide economic-loss estimates as facility downtime.

References:
- https://open-meteo.com/en/docs/historical-weather-api
- https://www.ncei.noaa.gov/access/storm-events-database/
- https://www.ncdc.noaa.gov/stormevents/faq.jsp
- https://www.census.gov/data/developers/data-sets/popest-popproj/popest.html

Documentation reviewed; live API connectivity, licensing/usage terms and exact variable/endpoint compatibility remain implementation checks.

## Historical metrics and trend contract

Define configurable hazard thresholds as analysis assumptions, not official closure limits. Keep occurrence thresholds distinct from operational disruption thresholds.

For each variable/hazard return valid observation count, exceedance days, exceedance fraction, annual counts, event runs (consecutive exceedance days) and duration/intensity summaries. An annual rate is eligible when at least 95% of expected observations are valid; mark it partial otherwise. Missing dates break event runs and flag possible truncation. A snowfall-day query explicitly uses snowfall > 0 cm unless the user supplies a different threshold; disclose gridded-model precision and a threshold sensitivity option.

Trend: annualized exceedance rate, slope in percentage points/year, first-five versus last-five-year rates, annual series, eligible-year count and uncertainty. Require at least 12 eligible years and coverage in both comparison windows; otherwise report insufficient trend evidence. Use a robust slope and a documented interval method; expose sensitivity and do not call a direction statistically established when the interval spans zero. Interval assumptions, including temporal dependence, must be stated. No automatic forward extrapolation or general 'safer' label from a single declining metric.

For a deterministic hazard ranking, use annual exceedance fraction descending, tied by stable location ID, and show intensity/duration alongside it. A severity-weighted composite may be offered only with explicit thresholds, bounded normalization and versioned weights; it is not necessary for the first release. No multiplication of the illustrative 1-5 overview scores. No hidden trend multiplier.

## Network evaluator

1. Build eligible hub-demand links only inside the service-distance bound and service component.
2. Calculate daily available hub capacities from disruptions and recovery.
3. Allocate divisible demand with a deterministic linear program: first minimize total unserved units; holding that optimum, minimize assigned demand-distance. Stable ordering makes repeated runs reproducible.
4. Respect every hub capacity and every demand area's requirement. Reallocate daily; retain baseline assignments for rerouting comparisons.
5. Return baseline coverage, daily served fraction, total unserved demand-days, incremental disruption-attributable unserved demand-days, minimum daily service fraction, additional assigned demand-km and daily hub utilization. Compare distance only for comparable served demand; do not imply improvement because difficult demand went unserved.
6. Report structural unserved demand separately from outage-attributable losses. Recovery of hub capacity and recovery of service are separate dates; service may recover sooner through backups. If the run ends first, return 'not recovered within horizon'.

This is a daily flow model, not a queue: unserved units represent unmet daily service and do not carry forward. Therefore no claims about clearing shipment backlog. A queue/backlog extension requires storage and dispatch dynamics. Route accessibility is an explicit assumption; facility weather alone does not demonstrate passable routes.

Historical replay synchronizes the same dates across locations to preserve regional co-exposure. Weather-to-capacity and recovery mappings remain labeled assumptions. A manually forced disaster has no implied annual probability. Report replay-window average losses as conditional historical-scenario results, not calibrated expected annual downtime.

## Synthetic acceptance scenario (no actual hubs selected)

Three abstract facilities A, B, C and two demand areas X, Y. Each area requires 60 units/day. Capacities: A=80, B=80, C=40. Eligibility: X can use A/B; Y can use B/C. Explicit test distance matrix avoids implying geographic siting. No real-location risk conclusions.

- Baseline: all 120 units/day served.
- A closed: B+C serve all 120 units/day, with both fully utilized.
- A and B closed together: only C serves Y; 80 units/day unserved.
- A and B closed for three days, instant recovery: 240 unserved demand-days; full service resumes on day four.
- A closed and B limited to 40: at most 80 served; 40 units/day unserved.
- A closed, B capacity restored from 40 toward 80: service follows explicit recovery steps without exceeding capacity.

Additional tests: baseline capacity already insufficient; unreachable demand; disconnected Alaska/Hawaii components; overlapping hazards; event ending at horizon; leap-year denominator; null snowfall; incomplete annual history; increasing/decreasing/flat synthetic trends; unsupported flood question; ambiguous follow-up; invalid LLM schema; source timeout. Synthetic frequencies never become real US frequency estimates.

## API and conversation contract

- POST /chat: conversation_id, message -> answer, result cards, evidence, assumptions, clarification status.
- POST /scenarios: validated network input -> persisted scenario/version.
- POST /scenarios/{id}/evaluate: disruption configuration -> deterministic result.
- POST /analysis/weather: locations, period, hazards/thresholds -> historical metrics/ranking/trends.
- GET /health: app readiness and configured provider availability without secrets.

Structured LLM intent is a discriminated union: weather_statistic, compare_exposure, rank_exposure, explain_result, evaluate_scenario, clarify, unsupported. Each branch has a strict JSON schema. Tool result is code-generated; structured answer includes explanation and evidence IDs. Persist resolved location IDs, period, metric and scenario so follow-ups can inherit them. Missing context prompts clarification rather than silently selecting locations.

## Repository layout

app/main.py; app/api/; app/agent/; app/schemas/; app/data/; app/analytics/; app/scenarios/; app/storage/; app/static/

tests/unit/; tests/integration/; evals/cases.jsonl; evals/run.py; fixtures/; docs/architecture.md; docs/assumptions.md; docs/ai-session/; README.md; .env.example

## Delivery sequence and gates

1. Foundation: schema models, synthetic allocator and six scenario tests above. Gate: known capacities and outage outcomes reproduce exactly.
2. Data: live weather adapter, cache and normalized records; population/hazard feasibility checks. Gate: dates, units, model, missing values and provenance verified. Test locations are fixtures, not selected facilities.
3. Analytics: historical statistics, rankings and trend analysis. Gate: calculations and trend behavior pass fixed-data tests.
4. API + agent + chat: structured intents and follow-ups. Gate: browser sends requests through API and narratives agree with evidence.
5. Evaluation + handover: one command for deterministic tests; separate credential-dependent live LLM evaluation; README, architecture, limitations and full AI conversation export. Manual interview demo from clean startup. Deployment only after this gate.

Keep the agent's original weather-analysis path working before expanding network features. Defer voice, alerts, automatic facility optimization and road routing until mandatory requirements pass. If time is tight, deliver a tested synthetic network scenario with real historical weather analysis rather than claiming nationwide operational optimization.

## Evaluation and completion

Deterministic checks: numerical correctness, allocation constraints, reproducibility, provenance, missing-data behavior. Agent checks: correct tool/arguments, context resolution, unsupported-request handling, schema compliance, and evidence-supported answers. LLM evaluations use semantic assertions rather than exact prose matching. Live source failure must yield a visible partial/failed result, never an invented answer.

The full AI session is mandatory. Preserve this chat and future work via a verified export before submission; a hand-written summary is not a substitute. Redact secrets if present and disclose redactions. This plan is one part of that record, not the full session.
