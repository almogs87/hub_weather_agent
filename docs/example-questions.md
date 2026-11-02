# Example questions

The app starts with 25 illustrative city locations, including the example existing hubs chicago, detroit, minneapolis, miami, houston, denver and dallas. They are examples, not verified company facilities. Use a hub ID in questions; edit app/hubs.json and restart the server to change the active catalog.

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
- `Compare chicago and dallas for ice storm risk`
- `Tornado risk for dallas`
- `Drought risk for denver`
- `What weather events do you support?` — see the current capabilities in chat.

Chat comparisons use the same frequency, severity and assumed-recovery index as the comparison table. A generic winter question includes snowfall and ice-storm reports; unscored components are disclosed and the result is partial. Sources, scope, coverage and assumptions are available with the results.

NOAA named-event reports cover a county or state rather than a specific hub. Event frequency can be displayed, but a hazard remains unscored if comparable physical severity is unavailable.

## Choosing weather data

Use the **Weather data source** selector above the chat input: Automatic (ERA5 with NOAA fallback), Open-Meteo ERA5 only, or NOAA station observations only. It applies to historical-weather chat analyses; named-event comparisons use NOAA Storm Events. The JSON API accepts optional `weather_source` values `auto`, `open-meteo`, or `noaa`; omitting it retains the server default. Each comparison uses one weather source, never a mixture. NOAA maximum wind is unavailable. The two sources use different measurements and daily conventions, so values may differ.

## Two-hub comparison

Open **Explore and compare**, then click up to two locations. Choose one shared weather event and a 5-, 10-, 20- or 30-year summary period. **Ask in chat** becomes **Compare in chat** for two selected locations and fills the chat input without sending. **Full comparison table** analyzes the chosen event over all four periods. **Reset locations** clears only the selected locations; the previous table, chat, event and settings remain. Red points are illustrative existing hubs; teal points are optional cities. They do not represent real facilities or service coverage. The map is limited to the contiguous United States.

The result provides 5-, 10-, 20- and 30-year periods ending in the last complete calendar year. Daily weather requires at least 80% valid observations for each hub and period. Each period may use a different verified station or source; its evidence shows which. Consecutive daily threshold days form a period; a missing day breaks a period. NOAA reported-event coverage reflects available annual archives, not the completeness of reporting.

The summary names a lower index only when both locations have comparable scores. It identifies partial comparisons and displays available NOAA report counts even when there is not enough severity evidence for a score. Counts describe county or state areas, not hub incidents; different geographic scopes and reporting gaps prevent a reliable facility-risk conclusion. For daily weather, a historical planning-index trend is shown only for the selected period when it spans at least 15 years and has sufficient eligible annual observations; a 5- or 10-year view cannot establish a trend under that standard. Trend intervals are approximate, assume stationary residual dependence and do not predict future weather.

The 0–100 planning index is not a probability of disruption. Its default weights are 50% frequency, 25% mean severity and 25% assumed recovery; the user can edit weights, bands, recovery and normalization benchmarks. For daily data, frequency is qualifying periods per year, normalized to 10 periods/year; severity is the mean peak band as a fraction of the three bands; recovery is the mean illustrative 1/3/7 days normalized to 14 days. Each component is capped at 100. No qualifying periods yield zero components, but do not demonstrate safety. The overall index is the mean of hazards that have a score for every ranked location; it is marked partial when any hazard or location is excluded. Chat and table comparisons share the same settings and default to the last 10 complete years for chat when no dates are provided. Categories may overlap, and this index has not been calibrated to facility losses.

The interface offers floods (including flash floods), hurricanes, tornadoes and ice storms alongside the daily weather measures. Chat winter rankings include snowfall and ice storm reports; ice is explicitly unscored when severity is unavailable. The first release scores hail size, wind magnitude and EF-rated tornadoes when enough physical magnitude values are present; other categories remain unscored but display available counts. NOAA archives can be slow to download the first time. County reports apply to counties, not facilities; statewide fallbacks can include events far away. A warning appears when statewide or mixed geographic scopes are used, including when scores are shown. Historical reporting practices, event classification and archive delays vary. NOAA data does not establish actual outage duration.

The complete Open-Meteo variable catalog is linked from the settings. Only the five listed daily hazards have comparison scoring definitions; other provider variables are not silently scored.

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

The app does not identify named storms, blizzards, snow depth on the ground, freezing rain, tornado tracks, actual road closures or flight cancellations. Flood, hurricane, ice storm and tornado comparisons use NOAA county or statewide event reports, not hub incident records. Ask about rain rather than interpreting heavy precipitation as a flood probability.

## Data sources and geographic coverage

The application uses three source families: Open-Meteo's ERA5 historical weather reanalysis, NOAA NCEI GHCN-Daily station observations as a fallback for snowfall, precipitation and temperatures, NOAA NCEI Storm Events reports for event comparisons, and FEMA's National Risk Index for county-level hazard screening. NOAA fallback does not provide the app's maximum-wind metric. ERA5 and NOAA observations are not silently mixed in one comparison. These sources have broad United States coverage, including Alaska and Hawaii, but a specific coordinate, variable and time period may have inadequate station observations or missing FEMA data. The application has not validated every state or every location; coverage is reported per result. The 25 illustrative locations do not represent national hub coverage.

## Demo and live modes

Start demo mode with `python -m app.server --demo`. It uses a limited keyword parser, not an AI model, and may misunderstand different phrasing. Click **New conversation** when switching topics if a follow-up inherits unwanted context. Start live mode on Windows, macOS or Linux with `python scripts/start_live.py` for natural-language model planning; it prompts for a key without displaying it. Both modes use real weather and FEMA sources or their caches; if a provider is unavailable the app reports the failure.
