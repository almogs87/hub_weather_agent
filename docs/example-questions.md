# Example questions

The app starts with illustrative hubs named chicago, detroit, minneapolis, miami, houston, denver and dallas. They are examples, not verified company facilities. Use a hub ID in questions; register another location to analyze it.

## Snow and other historical weather

- `Snow for denver in 2025` — days with new snowfall greater than 0 cm, the share of valid days, and consecutive snowfall periods.
- `Heavy snow for chicago in 2025` — days and consecutive periods with more than 15 cm of new snowfall per day. This is an illustrative threshold, not an official warning.
- `All snow events for denver in 2025` — returns to the ordinary greater-than-zero definition, including after a heavy-snow question.
- `Compare chicago and denver for snow in 2025` — compare the percentage of valid days meeting the same definition.
- `Snow for minneapolis in 2011 2025` — analyze 2011 through 2025 inclusive; omit years for the default 2011–2025 window.
- After a question about a location and period, `What about heat?` — use the previous location and dates with the heat definition.
- After a heavy-snow question, `What about denver?` — keep the heavy-snow threshold and change location. Say `Snow for denver in 2025` to return to all snowfall.
- `Heat for houston in 2025`, `Cold for chicago in 2025`, or `Wind for denver in 2025` — use the documented default thresholds.

Consecutive threshold days are counted as an observed period; they are not verified individual storms. Missing days can split periods. Snowfall is newly fallen snow, not the depth of snow on the ground. The app does not currently provide snow depth. Demo mode cannot interpret custom numeric thresholds reliably and asks for clarification; live mode supports numeric threshold requests subject to checking the returned plan and units. NOAA fallback does not provide maximum wind.

## County-level hazard screening

- `Which hubs in the Midwest are most exposed to winter disruption?`
- `Compare miami and houston for hurricane and flood`
- After the comparison, `Compare only flooding`, then `What about dallas?`
- `Why is the dallas hub's weather disruption risk high?` — inspect the available components; the result is partial if a component is missing.

FEMA scores are national county percentiles for estimated annual community losses; they are not the probability of a hub disruption. They include community people and property, not the vulnerability or downtime of a specific facility. Sources, vintage, coverage and limitations are available with the results.

## Supported weather definitions

The demo recognizes the English keywords shown below; other wording may be misread. Each question can include an existing location ID and one year or two years. Two years define full calendar years, inclusive. Without dates, the default is 2011–2025. Dates and locations can carry over in a conversation. The response reports threshold days, the percentage of valid days, consecutive periods and their longest duration; the evidence contains annual statistics and, when eligible, a descriptive trend.

| Ask in demo mode | Daily metric and threshold | Example |
| --- | --- | --- |
| `snow` or `snowfall` | New snowfall > 0 cm | `Snow for denver in 2025` |
| `heavy snow` | New snowfall > 15 cm | `Heavy snow for chicago in 2025` |
| `rain` | Total precipitation >= 25 mm, including the water equivalent of snow | `Rain for houston in 2025` |
| `heat` | Maximum temperature >= 35 °C | `Heat for houston in 2025` |
| `cold` | Minimum temperature <= -10 °C | `Cold for chicago in 2025` |
| `wind` | Maximum 10 m wind speed >= 50 km/h | `Wind for denver in 2025` |

These are configurable analytical definitions, not official warnings or evidence of closure. Demo mode does not reliably recognize custom numeric thresholds or every synonym: for example, use `rain` rather than assuming `precipitation` will be understood. Live model planning is more flexible, but inspect the applied plan to verify the requested amount, units and dates. Comparison requires the same metric and period, adequate coverage, and the same source family. A longer trend requires at least 15 calendar years and sufficient annual coverage.

The app does not identify named storms, blizzards, snow depth on the ground, freezing rain, tornado tracks, actual road closures or flight cancellations. Flood and hurricane questions use FEMA county-level indicators rather than daily weather observations. Example hubs have county mapping; arbitrary newly registered coordinates have historical weather support but cannot use FEMA county screening without a county mapping. Ask about rain rather than interpreting heavy precipitation as a flood probability.

## Data sources and geographic coverage

The application uses three source families: Open-Meteo's ERA5 historical weather reanalysis, NOAA NCEI GHCN-Daily station observations as a fallback for snowfall, precipitation and temperatures, and FEMA's National Risk Index for county-level hazard screening. NOAA fallback does not provide the app's maximum-wind metric. ERA5 and NOAA observations are not silently mixed in one comparison. These sources have broad United States coverage, including Alaska and Hawaii, but a specific coordinate, variable and time period may have inadequate station observations or missing FEMA data. The application has not validated every state or every location; coverage is reported per result. The seven illustrative hubs do not represent national hub coverage.

## Demo and live modes

Start demo mode with `python -m app.server --demo`. It uses a limited keyword parser, not an AI model, and may misunderstand different phrasing. Click **New conversation** when switching topics if a follow-up inherits unwanted context. Start live mode with `.\scripts\start-live.ps1` for natural-language model planning; it prompts for a key without displaying it. Both modes use real weather and FEMA sources or their caches; if a provider is unavailable the app reports the failure.
