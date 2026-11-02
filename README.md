# Weather Risk Intelligence Agent

A local conversational application for exploring historical weather exposure and comparing illustrative US hub locations. The AI model interprets questions through a validated structured schema; Python calculates the weather metrics and planning scores.

## Run the app

Install Python 3.11 or newer, then from the project directory run:

```sh
python -m pip install -r requirements.txt
python scripts/start_live.py
```

Open http://127.0.0.1:8000 and keep the terminal open. The launcher uses Groq by default. It reads the first Groq key in the Git-ignored `keys.local.md`, then `GROQ_API_KEY` if that file has no key, or prompts for a key without displaying it. Keys stay out of the browser and source control. The launcher does not open a browser automatically.

Choose another port with `python scripts/start_live.py --port 8793`. For OpenAI use `--provider openai --model MODEL`. Use `--weather-source noaa` to choose NOAA as the default weather source. Stop the server with Ctrl+C. Restart after changing Python code; if a port is already occupied, stop the old server or choose another port.

To try the application without an AI key, run `python -m app.server --demo`. Demo mode uses a limited keyword parser, while weather data still comes from real public sources or local caches. The Windows PowerShell alternative is `scripts/start-live.ps1`; see [model providers](docs/model-providers.md).

## Use the interface

Ask a question in chat or select up to two cities on the map. Choose a weather event and period, then use **Ask in chat** or **Compare in chat** to prepare an editable question. **Full comparison table** displays the selected event for the last 5, 10, 20 and 30 complete years. **Reset locations** keeps the conversation and previous table.

Examples:

- `Heavy snow for chicago in 2025`
- `Compare chicago and denver for rain from 2016 to 2025`
- `Which hubs in the Midwest are most exposed to winter disruption?`
- `Compare miami and houston for hurricane and flood risk`

See [example questions](docs/example-questions.md) for the supported definitions, follow-ups and limitations. The catalog in [app/hubs.json](app/hubs.json) contains 25 illustrative locations, including seven example existing hubs. Edit it and restart the server to change them. They are not verified facilities or demonstrated service areas; the map shows the contiguous US.

## How comparisons work

For supported measures, the illustrative 0-100 planning index combines frequency (default 50%), severity (25%) and assumed recovery (25%). Thresholds, weights and recovery assumptions are adjustable. A lower index indicates lower modeled exposure under those assumptions; the index is **not** a probability of closure or predicted downtime.

When comparable frequency and severity evidence is insufficient for a selected hazard, the application explains the partial result and can use FEMA county expected annual loss scores as a fallback. FEMA scores rank county-level expected losses relative to other counties; they are not percentages or facility-specific probabilities. Hurricane, inland flood and coastal flood are considered separately. Available NOAA event counts are reported with their geographic and reporting limitations. The sources and assumptions do not establish which specific facility or backup network is safest.

Data sources include Open-Meteo ERA5 reanalysis, NOAA GHCN-Daily station observations, NOAA Storm Events reports, and FEMA's National Risk Index. The weather source selector supports automatic fallback, Open-Meteo only or NOAA station observations only. NOAA station observations do not supply the app's maximum wind metric. Coverage varies by location and period; NOAA event archive years do not guarantee complete reporting. See [weather sources](docs/weather-sources.md).

## Tests and evaluation

```sh
python -m unittest discover -s tests
python -m evals.run
```

The conversation evaluation uses synthetic weather and event data. `python -m evals.run --live-model` additionally calls the configured AI provider and may incur charges. The most recent complete run passed 100 unit tests and 14 demo evaluation cases. The current interface and expanded evaluation have not been fully verified end to end with a live model.

## API and project structure

The browser calls the local API served by [app/server.py](app/server.py). Key routes include `GET /api/health`, `GET /api/locations`, `POST /api/chat` and `POST /api/hub-comparison`. Network replay and comparison are available through `POST /api/scenarios/replay` and `POST /api/scenarios/compare` with explicit network inputs; they do not automatically optimize a real network. The local server binds to loopback and is not configured for public production deployment.

- [app/](app/): interface, API, model planning, deterministic analysis and data adapters.
- [tests/](tests/) and [evals/](evals/): automated checks and conversation evaluation.
- [docs/](docs/): [architecture](docs/architecture.md), [assumptions](docs/assumptions.md), [example questions](docs/example-questions.md), and [source descriptions](docs/weather-sources.md).
- [codex-session-01a19cd3-67dd-7c80-974f-0929d282c993.md](codex-session-01a19cd3-67dd-7c80-974f-0929d282c993.md): exported development session with the shared Groq key redacted.

Runtime caches, the local database, evaluation reports and `keys.local.md` are ignored by Git. Cached NOAA storm archives can be large and are useful for offline comparisons; they are not included in the repository.
