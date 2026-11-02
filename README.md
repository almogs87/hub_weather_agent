# Weather Risk Intelligence Agent

For the project story, decisions, lessons and next steps, see the [project handover](docs/project-handover.md).

A local conversational analyst for historical weather exposure and reported weather events. The catalog contains 25 illustrative city locations, including seven example existing hubs; none are verified company facilities.

## Run

Requires Python 3.11+ (tested with the bundled Python; user verified weather retrieval with Python 3.15).

~~~powershell
cd C:\Users\Almog\Documents\Codex\hub_weather_agent
python -m pip install -r requirements.txt
python -m app.server --demo
~~~

Open http://127.0.0.1:8000 . Demo mode uses a limited deterministic question parser, not an LLM; weather still comes from the real API or its cache. No synthetic weather is substituted in the application. The app loads illustrative hubs from app/hubs.json; ask using a hub ID, e.g. 'Snow for denver in 2025', followed by 'What about heat?'. Demo parsing only recognizes simple location IDs, years and hazard words; it is for checking the interface.

For AI mode, Groq is the default provider (openai/gpt-oss-20b). Run `python scripts/start_live.py` on Windows, macOS or Linux to enter a Groq key with hidden input, or securely set GROQ_API_KEY and optionally LLM_PROVIDER/LLM_MODEL. The launcher starts the server itself; open the address it prints. Alternatively, configure the provider, model and API key in your environment and run `python -m app.server` directly.

The example .env file is not auto-loaded. Never commit API keys or paste them into a chat. An AI call is made only when live-mode chat is submitted. An earlier seven-case Groq planning evaluation passed; expanded live-model and current-interface end-to-end checks remain pending. Provider refusal, incomplete output or invalid schema cannot execute an analysis.

The model selects an approved analysis through a strict schema: Groq returns a structured plan; OpenAI returns a function call. Python validates that call and computes every number. Explanations are deterministic templates grounded in returned metrics, preventing narrative arithmetic drift. Conversation context persists in SQLite; the active hub catalog is loaded from app/hubs.json on server startup. Use New conversation to clear the active context.

## Winter replay

Submit an explicit network to POST /api/scenarios/replay, mapping hubs to IDs in app/hubs.json. The replay API remains available, but its form is no longer shown in the chat interface. No capacities or links are invented.

~~~json
{
  "hubs": [{"id":"A","capacity":80}],
  "demands": [{"id":"X","units":60}],
  "links": [{"hub_id":"A","demand_id":"X","distance_km":10}],
  "max_distance_km":100,
  "start":"2025-01-01", "end":"2025-01-07",
  "hub_locations":{"A":"YOUR_REGISTERED_LOCATION_ID"}
}
~~~

Version-one snowfall profile: >=5 cm/day gives 80% available capacity with no additional recovery day; >=15 cm gives 50% with one recovery day; >=25 cm gives 10% with two recovery days. These are illustrative sensitivity assumptions, not official heavy-snow warnings, actual closures or calibrated losses. Bands are configurable through WinterProfile in Python; the UI currently uses the versioned default. All modeled snow days become one-day disruptions; recovery is linear; overlaps use the lowest available fraction.

Historical dates are synchronized by local calendar date. Daily values cannot establish subdaily event overlap, snow squalls, freezing rain, blizzards, road closures or flight cancellations. Airport capacity and road-access closures are not modeled. No rare-event annual probabilities are inferred.

## Weather CLI

~~~powershell
python -m app.weather_cli --latitude 39.7392 --longitude -104.9903 --timezone America/Denver --start 2011-01-01 --end 2025-12-31 --hazard snow
~~~

Coordinates above are an integration example, not a facility recommendation. Hazards: snow, heavy_precipitation, heat, cold, wind. Use --threshold to override and --refresh to retrieve again. Default weather window: 2011-2025, 15 complete years. Defaults: snowfall >0 cm; precipitation >=25 mm/day; maximum temperature >=35 C; minimum temperature <=-10 C; maximum 10m wind >=50 km/h. All are analysis definitions, not closure criteria. Heavy precipitation is not flood probability and wind is not hurricane probability.

Percentages exclude missing days and show coverage. Missing days break event runs. Annual trends require >=12 eligible years within a period spanning >=15 years, with >=4 eligible years in each endpoint five-year window. Eligible years have complete requested calendar windows and >=95% valid observations. Rankings require matching definitions/periods and >=95% overall coverage. Seasonal missingness can still bias comparisons.

Trends use a Theil-Sen slope with an approximate circular residual block bootstrap interval (block length 3, 400 samples, fixed seed). This assumes a linear trend and stationary residual dependence. It is descriptive, not a forecast or overall safety guarantee.

## Tests and evaluations

See [example questions](docs/example-questions.md) for supported questions, follow-ups, and demo limitations.

~~~powershell
python -m unittest discover -s tests -v
python -m evals.run
python -m evals.run --live-model
~~~

98 tests pass; 14 conversation evaluation cases pass with the demo parser and explicit synthetic weather and NOAA event data. --live-model calls the configured real LLM while retaining synthetic data, isolating planning quality from network/data variation. It requires credentials and may incur provider charges. The earlier seven-case live evaluation passed; the expanded 14-case evaluation remains pending.

Headless browser checks passed using isolated synthetic weather: registration, snowfall analysis, heat follow-up, table sorting, network replay, and a 390px mobile layout without page overflow. Live historical weather was independently verified by the user from PowerShell. The earlier seven-case live model evaluation passed; the current interface and expanded schema still need an end-to-end live browser check.

## API

- GET /api/health: readiness, mode, configuration presence (no credentials).
- GET /api/locations: list the JSON hub catalog.
- GET /api/profile: profile, assumptions and source references.
- POST /api/chat: message, optional conversation_id and optional scenario; returns answer, metric cards, intent and optional scenario_result.
- POST /api/scenarios/replay: explicit network JSON; returns daily allocation, losses, recovery and evidence.

Local single-user server binds only 127.0.0.1. The standard-library HTTP server deliberately avoids extra server dependencies for this take-home; public production deployment requires a production server, authentication and operational controls.

## Storage and structure

- app/weather.py, weather_cli.py: ERA5 retrieval, cache and historical analytics.
- app/scenarios.py, winter.py: allocation, disruption/recovery and snowfall profile.
- app/agent.py, schemas.py: model planner, validated requests and deterministic tools.
- app/storage.py: SQLite state; app/server.py: local API.
- app/static/: browser interface; tests/: deterministic and mocked-provider tests.
- evals/: small conversation evaluation set and runner.
- docs/: architecture, assumptions, implementation plan and development status.

Runtime SQLite and weather caches live under data/ and are ignored by Git. Cache envelopes contain raw response text, request URL, timestamp and SHA-256. They are plain JSON rather than compressed files in this version.

## Remaining scope

Population-based national coverage, automatic facility optimization, facility-level flood/hurricane evidence, actual transport-closure data, shipment backlog, voice, alerts and deployment are not implemented. The sample hubs and contiguous-US map do not demonstrate nationwide coverage. Mainland, Alaska and Hawaii are separate service components in scenario inputs; the system does not infer a component from coordinates.

The mandatory full AI-development-session export remains outstanding; a design summary is not a substitute. See docs/architecture.md and docs/assumptions.md.

A shorter weather query can reuse a verified larger cached period when coordinates, timezone, model, units and variables match exactly. Evidence retains the original source URL/hash and records the requested analysis URL plus subset_from_cache. --refresh bypasses this reuse. Weather connection failures are labeled specifically.

Track completed work and next steps in docs/progress.md. Replay now includes summaries, sortable affected-day rows, recovery triggers and automatic accounting checks. Raw evidence remains collapsed.

## Compare networks

Use the API POST /api/scenarios/compare with reference and candidate networks. It enforces equal demand, dates and distance limits; shared hubs retain weather location/component. Each unique weather location is fetched once and reused for both networks. Results show service benefits and costs in additional installed capacity/distance, without assuming that backups escape regional storms. Distance comparison matches the smaller served quantity per demand area/day so reduced service cannot masquerade as shorter transport. No monetary costs or automatic investment recommendation. See docs/network-comparison-test.md for a complete manual test.

Provider and model configuration, hidden-key startup, switching examples and evaluation gates are documented in docs/model-providers.md. An earlier seven-case live Groq evaluation passed; the expanded evaluation remains pending.

Each successful chat answer now includes a collapsed How this answer was produced trace: original model plan, applied policy, response ID/usage when supplied by the provider, and per-location weather cache provenance. Named heavy snow is enforced as the documented illustrative >15 cm/day metric unless an explicit numeric custom amount is supplied. The model plans; deterministic templates produce numerical explanations, so the same query should return the same values in live and demo mode. Weather retrieval retries transient connectivity/502/503/504 errors up to three attempts; access-denied and certificate errors are not retried.

For weather connectivity diagnostics run python -m app.weather_probe from the project root. It tests one-day and full-year Chicago requests directly (no LLM/key), refreshes only successfully validated responses into cache, and reports provider reasons when available. An incomplete location comparison now retains available results but explicitly withholds a complete ranking.

## Independent weather fallback

NOAA NCEI GHCN-Daily station observations now back up Open-Meteo. Default WEATHER_SOURCE=auto retries the complete analysis with NOAA when a primary service/connection request fails; it never silently ranks mixed ERA5 and station results. Sources are shown in answers and evidence. NOAA covers snowfall, precipitation, maximum/minimum temperature; maximum wind is explicitly unsupported. The live launcher supports -WeatherSource noaa, and weather_cli supports --source noaa. See docs/weather-sources.md for source definitions, caveats and a direct verification command. NOAA retrieval was verified for Denver and Chicago.

NOAA station selection uses the official element/year inventory before checking up to sixteen nearest eligible stations. This excludes inactive historical stations before they consume the daily-data search budget. Daily quality/95% coverage checks remain mandatory.

## County hazard screening

The app loads 25 illustrative locations from app/hubs.json, including seven example existing hubs; old saved locations remain untouched but inactive. Chat and table comparisons use the same planning index and NOAA event reports. When there is not enough data to calculate a score, the comparison shows available NOAA report counts and explains their limits. NOAA county/state reports are not facility downtime or an event probability. Actual facilities and their vulnerabilities require separate evidence.

## Hub catalog and map

Edit app/hubs.json and restart the server to change the active locations. Entries need unique IDs, labels, coordinates, timezone, state, region and county FIPS. Existing SQLite locations are preserved but inactive. The map shows hub coordinates, not service coverage; Alaska and Hawaii are not displayed. The locally served state boundaries are from Natural Earth (public domain): https://www.naturalearthdata.com/about/terms-of-use/ .

## Compare two hubs

Use the compact map to select up to two illustrative locations, one weather event and a time period. Compare in chat prepares a question for review; Full comparison table displays all four periods. Reset locations retains the conversation and previous table. The comparison displays frequency, severity, illustrative recovery and a non-probabilistic planning index for the last 5, 10, 20 and 30 complete years. Source data, coverage and geographic limitations are shown with results. Severity, frequency and recovery benchmarks and weights are editable. The NOAA storm archive can take several minutes and substantial disk space on first use. Full details and assumptions: docs/example-questions.md.

## Portable live launcher

Run `python scripts/start_live.py` to use Groq. The key is read from the first Groq key in the Git-ignored `keys.local.md`, or from `GROQ_API_KEY` if no local key exists; if neither is available, it prompts without echo. The key is passed only to the child process. Add `--port 8767`, `--weather-source noaa`, `--model MODEL`, or `--action evaluate` as needed. For OpenAI use `--provider openai --model MODEL`. The launcher does not save the key.
