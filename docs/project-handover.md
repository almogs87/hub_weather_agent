# Weather risk agent: project handover and lessons learned

This is a narrative handover based on the available conversation and repository, not a verbatim export of the complete chat. It records the product intent, major decisions, implementation, evidence and remaining work as of 2 November 2026. See [progress](progress.md) for chronological checkpoints and [example questions](example-questions.md) for the supported language.

## The assignment and the decision problem

Build a conversational agent that uses public weather and hazard data to answer questions about US hubs. It must expose an API used by a chat interface, use deterministic scoring or ranking, validate structured model outputs, support follow-ups, provide a small runnable evaluation set, and state its assumptions and uncertainty. Alerts and voice were optional bonuses.

The broader operational goal is to plan a network that serves populated US areas and can use other hubs as backups during disruption. A useful network can include both rare severe risks and more frequent events with shorter recovery, provided alternatives exist. This goal requires population, demand, capacity, transport links, common storms and recovery evidence. The current illustrative city comparison does not solve that optimization.

## How the product evolved

1. **Start with trustworthy calculations.** Historical snowfall, precipitation, temperature and wind questions were implemented using deterministic calculations. A structured model plan selects an approved operation; Python validates the plan and computes the result. Follow-ups reuse relevant context, with explicit policy for distinctions such as ordinary snowfall versus illustrative heavy snow.
2. **Make sources and uncertainty visible.** Open-Meteo historical reanalysis and NOAA station data were made selectable, with automatic fallback. NOAA Storm Events was added for named-event reports. FEMA county risk data informed earlier screening, but its relative loss scores were not intuitive as management-facing percentages or suitable as facility outage probabilities.
3. **Make the interface conversational.** The editable location manager was replaced by an illustrative JSON catalog, a compact map and a chat with example prompts under the composer. Existing-hub and optional-city markers are illustrative, not verified facilities or service areas.
4. **Compare frequency and severity.** A configurable 0-100 planning index was introduced for supported daily measures and some named event records. Recovery is an explicit illustrative assumption. Chat and the table use the same comparison engine, rather than allowing the model to invent a ranking.
5. **Reduce friction and reveal incomplete evidence.** Clicking up to two cities, choosing an event and period, and preparing a chat question or full table became the main workflow. Reports are shown when a score cannot be calculated; geography and incomplete data qualify conclusions. A cached-file fallback addressed a failure when the NOAA archive listing could not be reached.

## What a person can do now

Open the app, expand **Explore and compare**, select up to two cities on the map or from the list, choose one weather event and a period, then select **Compare in chat** to prepare an editable question. **Full comparison table** presents 5, 10, 20 and 30 complete-year periods. **Reset locations** preserves the chat and prior table. The chat also accepts direct questions and supported follow-ups.

Examples include `Snow for denver in 2025`, `Heavy snow for chicago in 2025`, `Which hubs in the Midwest are most exposed to winter disruption?`, and `Compare miami and houston for hurricane and flood`. Demo mode uses a limited keyword parser; live mode uses an LLM for planning. Check [example questions](example-questions.md) for supported terms, definitions and restrictions.

The catalog in [app/hubs.json](../app/hubs.json) holds 25 illustrative cities, including seven example existing hubs. Edit the JSON and restart to change it. The map displays the contiguous US, not Alaska or Hawaii; neither the markers nor their status establish national coverage.

## Run and evaluate

From the repository root, install dependencies once with `python -m pip install -r requirements.txt`. Start the limited-parser demo with `python -m app.server --demo`, then open http://127.0.0.1:8000. For live Groq planning, run `python scripts/start_live.py --port 8793` and open http://127.0.0.1:8793. The launcher reads `GROQ_API_KEY` from its environment or prompts with hidden input. Keep the terminal open. The cross-platform Python launcher does not automatically open a browser; `scripts/start-live.ps1` is the Windows PowerShell alternative. See [model providers](model-providers.md) for options.

Restart the server after code changes. If an old app is already listening on a port, stop it or start the new version on another port; refreshing an old server does not load new Python code. A key was previously shared in chat: revoke it and use a new one. Do not commit keys or paste them into messages.

Run `python -m unittest discover -s tests` and `python -m evals.run`. The latest checkpoint passed 98 unit tests and 14 demo conversation evaluations using synthetic evaluation data. An earlier seven-case live Groq planning evaluation passed; the expanded live evaluation and visual end-to-end verification of the current interface remain open. A Chicago-Denver API comparison was checked against cached real weather, and Miami-Houston NOAA cached reports were checked separately.

## Data and interpretation

- **Open-Meteo ERA5:** historical gridded reanalysis for daily weather. It is an estimate, not an observation at a facility.
- **NOAA NCEI GHCN-Daily:** station observations for snowfall, precipitation and temperature; the app does not support maximum wind from this source. Station coverage varies.
- **NOAA NCEI Storm Events:** reported named events by county or larger zones. Available archive years are not proof that every event was reported. Some categories use statewide fallback; counts can represent events far from a hub.
- **FEMA National Risk Index:** county-level relative expected annual loss measures used in earlier screening. A score is not a percent chance that a hub closes, and it is not a facility-specific assessment.

The default planning index weights frequency 50%, severity 25% and assumed recovery 25%, using configurable thresholds and normalization benchmarks. It is an illustrative index, not a probability, forecast or calibrated financial loss. Weather periods use consecutive threshold days; missing days break periods. Named hazards are scored only when adequate comparable physical severity is available. Otherwise, the application reports available counts and labels the comparison partial. Do not compare county counts to statewide counts as if they were equally local.

The Miami-Houston case illustrates why these distinctions matter. Cached NOAA records for 2016-2025 contain 104 versus 6 flood reports and 33 versus 92 flash-flood reports in Miami-Dade and Harris counties respectively. These are reported events, not counts of hub closures; reporting and severity may differ. Hurricane records were statewide for that comparison and cannot establish which hub has higher local hurricane risk. The app still lacks enough comparable severity data for a combined facility-level hurricane-and-flood score.

Historical trends are descriptive and require enough years and coverage. A 5- or 10-year summary does not establish a trend under the comparison policy. The daily weather analysis and comparison index have their own coverage requirements; consult the relevant evidence before comparing results.

## Architecture and further reading

The browser in [app/static](../app/static) calls the local HTTP API in [app/server.py](../app/server.py). [app/agent.py](../app/agent.py), [app/providers.py](../app/providers.py) and [app/schemas.py](../app/schemas.py) handle planning and structured validation. [app/hub_comparison.py](../app/hub_comparison.py) computes shared comparisons; [app/storm_events.py](../app/storm_events.py) reads NOAA event archives; [app/weather_sources.py](../app/weather_sources.py), [app/noaa.py](../app/noaa.py) and [app/weather.py](../app/weather.py) provide daily data and metrics. SQLite and caches under `data/` are local runtime data and are not committed. Scenario replay and network-comparison APIs exist, but require explicit network inputs and do not automatically find an optimal network.

Read [architecture](architecture.md), [assumptions](assumptions.md), [weather sources](weather-sources.md), and [network comparison test](network-comparison-test.md) for implementation details. The full original AI-development-session export is still outstanding where required; this handover is a summary, not a substitute.

## Next work, in priority order

1. **Make hurricane and flood comparison decision-useful.** Add defensible location-specific, comparable hazard and severity evidence, with source coverage and validation. Avoid treating statewide reports, heavy rain or generic wind as direct facility hurricane or flood probabilities. Validate with the Miami-Houston assignment question.
2. **Verify the actual experience.** Test the current map, selection, reset, chat and table visually at desktop and mobile sizes; run the expanded live-model evaluation and real end-to-end questions. Confirm cache fallback with partial or absent local files and clear error messages.
3. **Connect exposure to the business network.** Obtain actual hub locations, capacity, demand, service areas, transport links, backup rules and disruption/recovery history. Test shared regional storms and quantify unmet demand; do not infer independence or recommend locations from weather alone.
4. **Improve measurement and usability.** Calibrate thresholds and weights against operational impacts, add transparent source freshness and data-quality indicators, broaden supported hazards only when defensible, and review the performance of first-time NOAA downloads.
5. **Complete optional and deployment scope.** Consider alerts or voice only after the core comparison is reliable. Production use needs authentication, an appropriate server, monitoring and operational controls.

## Lessons from the work

- A legitimate public metric is not automatically a useful management decision measure. Explain what it measures, its scale and its geographic scope.
- A plausible number is worse than a qualified missing value when severity or location is unknown. Show what is available without turning missing data into zero risk.
- Keep model interpretation separate from deterministic calculation, enforce a schema, and compare chat results with table results.
- Make assumptions inspectable: thresholds, weights, periods, coverage, recovery and source selection all change the answer.
- Treat a comparison as a workflow, not just a model response: city selection, readable summaries, evidence and recovery from stale servers matter.
- Cached public data improves resilience, but archive availability does not prove reporting completeness or future risk.
- The assistant cannot directly inspect a user's weekly or five-hour account limits from this repository; check the product's usage display rather than inventing a remaining balance.
