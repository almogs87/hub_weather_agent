# Weather Risk Intelligence Agent

First milestone: deterministic daily network scenario engine. No real hub locations have been selected. This is not yet the complete assignment submission: live weather, trends, API, LLM, chat and evaluation cases for the agent remain to be implemented.

Requires Python 3.11+; this milestone uses only the standard library.

From this directory:

```powershell
python -m unittest discover -s tests -v
python -m app.demo
```

The demo returns JSON for three abstract hubs and two demand areas. A regional event closes A and B for three days. It produces 240 unserved demand-days and returns to baseline service on January 4 of the synthetic 2025 timeline.

The allocator maximizes served divisible demand, then minimizes total demand-distance using a residual-network minimum-cost maximum-flow algorithm. This avoids greedy assignments stranding demand. Stable ID ordering resolves equal-cost choices reproducibly. Capacity is enforced each day; unavailable hubs have null utilization rather than a division by zero.

Missing distance links are ineligible. Service components prevent mainland road backup to Alaska or Hawaii. Distances are supplied scenario inputs, not measured road travel. Overlapping outages use the lowest available-capacity fraction. Recovery is linear and explicitly configured. Unserved demand is not carried forward as backlog.

Source modules: `app/scenarios.py` (models, validation, allocator, simulation), `app/demo.py` (synthetic demonstration), `tests/test_scenarios.py` (acceptance and edge cases).

Do not interpret synthetic closures, recovery periods or capacities as observed company data or calibrated weather probabilities. The full AI conversation must be exported separately for the assignment; this repository does not yet include that export.


## Historical weather milestone

Implemented: ERA5 daily data retrieval, source provenance, validated disk cache, threshold exposure, comparable-location ranking and descriptive annual trends. API, LLM chat, population ingestion and rare-hazard adapters remain pending.

Install the timezone database (needed by Python on Windows):

~~~powershell
python -m pip install -r requirements.txt
~~~

Run analysis for coordinates you supply:

~~~powershell
python -m app.weather_cli --latitude 39.7392 --longitude -104.9903 --timezone America/Denver --start 2011-01-01 --end 2025-12-31 --hazard snow
~~~

These are integration-test coordinates, not a facility recommendation. Supported hazards: snow, heavy_precipitation, heat, cold, wind. Override the analysis threshold with --threshold; force new retrieval with --refresh. Output is JSON; data-source failures produce a nonzero exit status and an explicit error without fixture substitution.

Defaults: snowfall >0 cm; precipitation >=25 mm/day; maximum temperature >=35 C; minimum temperature <=-10 C; maximum 10m wind >=50 km/h. These are illustrative analysis thresholds, not official closure triggers. Heavy precipitation is not flood probability and wind is not hurricane probability.

Weather percentages use valid days as the denominator and show coverage. Missing days break observed event runs. Annual trends require at least 12 eligible years within a period spanning at least 15 years; eligibility requires a complete requested calendar year and >=95% valid data. At least four eligible years are required in each endpoint five-year window. Rankings exclude locations below 95% overall coverage and require matching definitions and periods. Comparable overall coverage does not eliminate seasonal missingness bias.

Trend slope uses Theil-Sen with an approximate 95% circular residual block bootstrap interval (three-observation blocks, 400 samples, fixed seed). This assumes a linear trend and stationary residual dependence; missing years complicate interpretation. It is descriptive, not a forecast or a safety guarantee. Inspect the annual series and test other thresholds before making decisions.

Data: https://open-meteo.com/en/docs/historical-weather-api . ERA5 is pinned for consistency across years. Reanalysis represents a grid cell, not a building sensor. Check provider licensing and usage terms before commercial deployment. Cache files contain original response text plus request URL, timestamp and SHA-256; this first version uses plain JSON rather than compressed storage.

Verification: 22 unit/acceptance tests pass. The development sandbox blocks outgoing sockets (WinError 10013), so live retrieval has not yet been verified. Run the coordinate command above from your normal PowerShell session; cached fixtures are only used in isolated unit tests, never automatically in live mode.
