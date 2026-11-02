# Implementation progress

Updated: 2 November 2026. No actual hub locations have been selected.

## 1. Foundation and network scenarios

- [x] Git repository and private GitHub repository established.
- [x] Deterministic demand allocation subject to capacity and distance constraints.
- [x] Backup routing, simultaneous outages, partial capacity and recovery.
- [x] Separate pre-existing shortfall from disruption-attributable shortfall.
- [x] Side-by-side comparison of explicitly supplied networks with/without backup; identical demand/dates/profile and shared weather snapshot.

## 2. Historical data

- [x] Open-Meteo ERA5 adapter with pinned model, validation and provenance.
- [x] Live 2011–2025 Denver-coordinate request verified by user.
- [x] Cached larger periods reused for matching shorter requests.
- [x] Weather-specific connection errors; no silent synthetic-data substitution.
- [ ] Population/geography ingestion for nationwide coverage analysis.
- [ ] Dedicated flood/hurricane evidence; currently explicitly unsupported.
- [ ] Actual road/airport disruption records, if required by final scope.

## 3. Analytics and winter replay

- [x] Frequency, threshold intensity, duration runs and comparable rankings.
- [x] Annual trend with uncertainty and coverage requirements.
- [x] Versioned daily snowfall-to-capacity sensitivity assumptions.
- [x] Historical weather drives same-date multi-hub replay and recovery.
- [x] Replay summary: affected days, unmet-demand days, total/incremental shortfall, minimum service.
- [x] Sortable affected-day table with snowfall, trigger/recovery, capacity and service results.
- [x] Affected-days-only filter; raw JSON collapsed as evidence.
- [x] Automatic daily capacity/demand accounting checks.
- [ ] Editable profile controls and side-by-side sensitivity comparison in the UI.
- [ ] Official local/rolling-window warning classification (not implied by daily thresholds).

## 4. API, agent and interface

- [x] Local HTTP API and browser chat.
- [x] Explicit coordinate registration; no invented facilities.
- [x] Strict model JSON-schema plans (Groq) / function calls (OpenAI), plus shared application validation.
- [x] SQLite conversation context and follow-ups.
- [x] Chat executes an explicitly supplied network replay.
- [x] Pasted scenario JSON in demo chat receives guidance rather than repeating weather.
- [x] Browser checks: registration, chat, follow-up, sorting, replay, affected-day filtering and mobile width.
- [ ] Configure a real Groq API key locally and verify starter model openai/gpt-oss-20b.
- [ ] Replace limited demo parsing with verified live AI for interview use.

## 5. Evaluation and handover

- [x] 70 automated tests pass, including an intentionally invalid allocation detected by the audit.
- [x] Seven conversation cases pass with the demo parser and explicit synthetic weather.
- [x] README, architecture and assumptions documents.
- [x] User manual checks: snow baseline, heat follow-up, heavy snow subset and unsupported flight data.
- [ ] Run the seven conversation cases against the actual model: python -m evals.run --live-model.
- [ ] Repeat user replay test using the new summary/table (no JSON scrolling).
- [ ] Export the complete AI-development conversation; mandatory deliverable.
- [ ] Clean-start installation and final interview rehearsal.
- [ ] Push latest local commits from user's authenticated PowerShell.
- [ ] Optional deployment. Voice/alerts remain deferred bonuses.

## Next implementation order

1. Manually verify the completed network comparison using docs/network-comparison-test.md.
2. Verify Groq planning and follow-ups; evaluate the starter model, then switch model through configuration and compare reports.
3. Add population coverage if time permits without compromising the required agent flow.
4. Finalize submission, export AI session and rehearse the demo.

## Run the updated replay view

Stop the running server with Ctrl+C, then run:

~~~powershell
python -m app.server --demo
~~~

Refresh the browser and rerun the scenario. The default view lists only days with capacity impacts (including recovery). Network totals repeat across affected hubs on the same date and must not be summed across table rows. The accounting audit validates internal consistency, not the real-world accuracy of the assumed weather effects.

## Current boundaries

This is a local single-user application. Weather history is evidence; capacity loss/recovery are illustrative assumptions. It does not establish road closures, flight cancellations, future hazard probabilities, financial losses or national population coverage. Demand does not carry forward as backlog. The live LLM path is implemented but not yet verified with real credentials.

## Network comparison milestone

POST /api/scenarios/compare accepts reference/candidate scenarios. Results include paired daily differences, unmet demand avoided, minimum-service improvement, installed capacity and matched-demand distance change. Browser copy, filtering, sorting and mobile-width checks pass. Negative benefits and shared-storm risk are tested. No real LLM is needed for the comparison form.

## Provider/model switching

Groq is now the default live provider; OpenAI remains supported. Set LLM_PROVIDER/LLM_MODEL or use scripts/start-live.ps1 for hidden-key entry. Per-model evaluations record provider/model and latency. See docs/model-providers.md. Gemini/Ollama require future adapters. Live starter/second-model verification remains pending.

## Live test findings and fixes

User verified Groq live mode can plan Denver snowfall and heat questions. Cross-location comparisons remain blocked by weather-provider connectivity/503 errors in the user test, not demonstrated model-location failures. Fixed a live model heavy-snow threshold mistake with a disclosed application metric policy; original and applied plans remain inspectable. Added response metadata/cache traces and bounded transient weather retries. Seven deterministic conversation cases pass; the seven-case live-model evaluation and successful uncached Chicago/Phoenix comparison remain pending.

## Independent weather source milestone

- [x] NOAA GHCN-Daily adapter for snowfall, precipitation and temperature observations.
- [x] Source-consistent whole-analysis fallback, raw-file cache and station provenance.
- [x] Explicit unsupported maximum-wind fallback; no snow-depth substitution.
- [x] Launcher/CLI source selection and source shown in results.
- [x] Verify live NOAA retrieval outside the network sandbox; Denver station download succeeded on 2 November 2026.
- [x] Repeat Denver/Chicago comparison with NOAA and inspect station coverage (2025 snow, 2 November 2026).

See docs/weather-sources.md. Station daily observation windows differ from ERA5 local civil days; no silent mixing is permitted.

NOAA follow-up: network downloads verified by user; all first eight cached stations had zero 2025 snow observations. Added inventory-based element/year filtering and expanded eligible candidate cap to sixteen; 70 tests pass. Retry the Chicago command to verify an accepted active station.

## Desktop continuation verification ? 2 November 2026

70 unit tests and seven demo conversation evaluations pass. The actual Service.chat comparison path completed with NOAA for both cities: Chicago station US1ILCK0074, 362/365 valid days, 32 days with snowfall >0 cm (8.84%); Denver station USC00052223, 365/365 valid days, 21 snowfall days (5.75%). Chicago used existing cached observations; Denver downloaded a station file outside the network sandbox, then the comparison reused that cache. No live LLM was involved. The local response/provenance report is saved at eval-results/noaa-comparison-2025.json (ignored by Git). No Groq/OpenAI key is configured in the current process; live-model evaluation remains pending credential setup.

## Live Groq evaluation verified ? 2 November 2026

Groq openai/gpt-oss-20b passed all seven conversation cases against synthetic weather after clarifying that winter_replay should be selected even without a supplied network (the application requests missing inputs). Initial run: 6/7; immediate rerun encountered HTTP 429 token limits. Final paced run: 7/7, report eval-results/groq-live-paced-2026-11-02.json (ignored). All 70 unit tests and seven demo evaluations also pass. The runner now accepts --delay-seconds and the hidden-key launcher uses ten seconds between evaluation cases. This verifies live planning separately from real-weather retrieval; a browser end-to-end live sequence and second-model comparison remain pending. Credentials were not written to project files.

## Assignment-focused continuation in progress

Added illustrative hub catalog and FEMA county adapter, seeded on server startup without overwriting existing locations. The risk chat route supports winter, hurricane and flooding comparisons using FEMA expected annual loss scores; missing scores are explicitly partial. FEMA December 2025 data downloaded for all seven example counties. Demo-mode Chicago/Midwest and Miami/Houston examples return results; Dallas is partial because coastal flood is unavailable. Live Groq and browser checks, robust follow-ups, updated evaluations and documentation remain to be completed.

## Current checkpoint

FEMA data for seven example counties has been fetched from the live public service and cached. The chat UI now places example prompts first and displays county hazard scores in a table, with advanced network forms collapsed. Two work streams are underway: model planning/follow-up evaluation and UI/integration verification. The Dallas screening remains partial because FEMA reports no coastal-flood score for Dallas County; this is not replaced with zero. Next: complete follow-up/evaluation changes, verify the browser and update the README. Last user-reported weekly allowance: 78%; the agent cannot read the current balance directly.

## Parallel review results

FEMA follow-up handling and evaluation coverage were extended. All 76 unit tests and 14 demo evaluation cases pass, including the four assignment examples and hazard follow-ups using synthetic evaluation data. The chat displays county scores and source details; advanced network controls are collapsed. Live FEMA data was verified for the seven example counties. Live Groq evaluation with the expanded schema remains pending; a browser check could not run because the browser access host was unavailable. The last known weekly allowance is 78%, pending the user dashboard update.

## HTTP integration checkpoint

The four assignment questions were exercised through the local demo HTTP API with real cached sources. A pre-existing Chicago record originally prevented example region metadata from being seeded; exact location matches now gain missing metadata, and conflicting user locations are preserved with a separately named example. Midwest results now include Chicago, Detroit and Minneapolis. The other examples returned expected results, with Dallas explicitly partial. All 77 unit tests and 14 demo evaluations pass. Browser access host remains unavailable; expanded live Groq evaluation requires a configured key.

## User-selectable source and expanded hazards

Historical chat now accepts per-request source selection (auto, Open-Meteo ERA5, NOAA); the browser has a selector and comparisons remain source-consistent. Capability questions have a deterministic response. FEMA county screening now includes ice storms, tornadoes and drought; it reports relative county expected-loss scores, not recorded event counts. Live FEMA data for seven examples and cached NOAA/ERA5 chat paths were checked. All 82 unit tests and 14 demo evaluations pass. Browser visual and expanded live Groq validation remain open.

## Chat and map redesign

The active hub catalog is now app/hubs.json; stored SQLite locations remain untouched but inactive. The chat scrolls above the composer with examples below, user messages are light blue, and a contiguous-US hub map appears below. Weather answers are concise with per-answer expandable evidence; scenario APIs remain available but their UI forms are removed. The local boundaries use Natural Earth data. 84 unit tests and 14 demo evaluations pass; HTTP endpoints and cached Denver weather were verified. The browser access host was unavailable for visual/mobile inspection; expanded live Groq testing remains pending.

## Two-hub comparison implementation

Added 25 labeled illustrative hubs, a compact map and two-hub selection tray, hazard selection, editable scoring assumptions and a 5/10/20/30-year comparison API. The NOAA Storm Events adapter lists 48 standard types and scores hail, measured wind and EF-rated tornado records only where physical severity is available; all others remain unscored. NOAA state fallback and geographic-scope differences are prominent. Daily weather comparisons use 80% coverage and per-period source provenance. A live Chicago/Denver daily comparison succeeded for all four periods; five-year and 30-year NOAA hail archive checks succeeded, including a Chicago county/Dallas state mismatch warning. All 89 tests and 14 demo evaluations pass. Visual browser and expanded live Groq tests remain open.

## Shared chat and table index

Chat risk and comparison questions now call the same planning index engine as the two-hub table with the selected weights, severity bands, recovery assumptions and weather source. The default is the latest 10 complete years; all seven Midwest catalog locations are included. A live-data demo request completed with seven scored snowfall results and separately labeled unscored statewide ice-storm reports. The two-hub UI now displays a side-by-side table, restricts visible named hazards to core major events and offers advanced settings. A portable hidden-key Python launcher is available at scripts/start_live.py. Automated tests and demo evaluations pass. Expanded live Groq and visual browser verification remain pending.

## Simplified two-location comparisons

Map and list clicks toggle up to two locations. A shared event and period drive the prepared chat question and the full four-period table; reset preserves the chat and previous result. The table prioritizes scores and NOAA report counts, with supporting details expandable. Chat and table use the same deterministic summary and cautiously explain incomplete or geographically mismatched reports. Trend statements use annual planning indexes only when the existing 15-year and coverage requirements are met. All 97 unit tests and 14 demo evaluations pass. Visual browser and expanded live-model verification remain open.

NOAA storm-event lookup now falls back to validated cached annual archives when the directory listing is unavailable, preserving actual year coverage and per-file provenance. An offline 2016?2025 Miami/Houston check returned county flood and flash-flood counts and statewide hurricane reports; those statewide counts cannot establish hub-level hurricane risk. 98 unit tests and 14 demo evaluations pass.
