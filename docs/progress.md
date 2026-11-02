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
- [x] Strict JSON-schema model function calls plus application validation.
- [x] SQLite conversation context and follow-ups.
- [x] Chat executes an explicitly supplied network replay.
- [x] Pasted scenario JSON in demo chat receives guidance rather than repeating weather.
- [x] Browser checks: registration, chat, follow-up, sorting, replay, affected-day filtering and mobile width.
- [ ] Configure a real OpenAI API key/model locally and verify a live AI conversation.
- [ ] Replace limited demo parsing with verified live AI for interview use.

## 5. Evaluation and handover

- [x] 46 automated tests pass, including an intentionally invalid allocation detected by the audit.
- [x] Six conversation cases pass with the demo parser and explicit synthetic weather.
- [x] README, architecture and assumptions documents.
- [x] User manual checks: snow baseline, heat follow-up, heavy snow subset and unsupported flight data.
- [ ] Run the six conversation cases against the actual model: python -m evals.run --live-model.
- [ ] Repeat user replay test using the new summary/table (no JSON scrolling).
- [ ] Export the complete AI-development conversation; mandatory deliverable.
- [ ] Clean-start installation and final interview rehearsal.
- [ ] Push latest local commits from user's authenticated PowerShell.
- [ ] Optional deployment. Voice/alerts remain deferred bonuses.

## Next implementation order

1. Manually verify the completed network comparison using docs/network-comparison-test.md.
2. Verify live AI planning and follow-up behavior; complete real-model evaluation.
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
