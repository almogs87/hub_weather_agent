# Weather sources and fallback

## Source policy

WEATHER_SOURCE can be auto (default), open-meteo, or noaa. The live launcher accepts -WeatherSource with the same options.

- Open-Meteo / ERA5: gridded reanalysis, configured local civil days; original weather variables unchanged.
- NOAA NCEI / GHCN-Daily: independent station observations, station-reported dates, no API key. Downloads official station metadata and individual fixed-width .dly data files.

In auto mode a failed Open-Meteo connection/service request causes the complete location group to retry with NOAA, including locations whose ERA5 data was already cached. This prevents a Denver ERA5 result being ranked silently against Chicago station observations. Data-validation errors are not silently bypassed. If some NOAA locations fail, weather comparisons retain available NOAA results but explicitly withhold a complete ranking. Network comparisons require all weather records and fail explicitly otherwise.

## Supported NOAA metrics

SNOW = new snowfall in millimeters, converted to centimeters. SNWD = snow depth and is never substituted. PRCP is tenths of millimeters, converted to millimeters. TMAX/TMIN are tenths of Celsius, converted to Celsius. Missing -9999 values and nonblank quality flags become null; trace amounts remain zero at reported precision. Daily maximum wind is not supported, and average wind is never substituted.

Station selection: sort US stations within 100 km by distance and stable ID; filter by NOAA inventory showing the requested variable spans the requested years, then inspect up to sixteen eligible candidates; choose the nearest with >=95% requested-variable coverage across the requested period. No suitable station means an explicit error. This bounded search can miss a suitable station outside the candidate cap. It does not prove the chosen station represents a particular facility. Station ID, name, coordinates, distance, rejected candidates, raw-file hashes and retrieval times accompany results. Source files are cached under data/cache/noaa/ and ignored by Git. Use --refresh in the CLI to retrieve updated snapshots.

## Important interpretation

NOAA observation dates may represent different accumulation windows than local midnight-to-midnight days. Elevation, station distance, quality controls and precision can produce different values than ERA5. New NOAA results should not be expected to reproduce cached Denver ERA5 counts. The app displays the source; comparisons use one family/day convention. Actual observation schedules can still differ between stations and are a limitation of daily network replay.

Trend calculations use one fixed station across the selected period; no station splicing. A shorter query may select a different station based on data completeness; inspect the station ID. Annual trend eligibility still requires >=95% annual coverage. Replay continues to reject any missing snowfall date rather than assuming normal capacity. The fallback does not establish actual road or airport closures.

## Verify NOAA from PowerShell

From the project root:

~~~powershell
python -m app.weather_cli --latitude 41.8781 --longitude -87.6298 --timezone America/Chicago --start 2025-01-01 --end 2025-12-31 --hazard snow --source noaa
~~~

This tests NOAA independently of Groq and Open-Meteo. The first run downloads a station catalog and selected station files, so it can take longer than a cached request.

To use NOAA explicitly in live chat from the scripts directory:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-live.ps1 -WeatherSource noaa
~~~

Default startup uses auto fallback, without that extra argument.

## Verification status

70 automated tests pass, including NOAA units, quality filtering, snow-versus-depth separation, cache provenance, candidate rejection and whole-analysis source consistency. The user verified live NOAA downloads, but the initial eight-candidate search selected inactive stations with no 2025 snowfall data. Inventory-based eligibility now excludes them before the sixteen-candidate limit. A successful accepted Chicago result remains to be verified. Run the command above in the normal user terminal before relying on the fallback in the interview. Both providers can be unavailable; the app never manufactures observations.

## Official documentation

- https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt
- https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt
- https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/

NOAA dataset DOI: https://doi.org/10.7289/V5D21VHZ

The NOAA inventory is a separate one-time cached download. Its first/last years are only a candidate filter, not proof of complete daily coverage. Actual records still must meet 95%. Missing values remain null; no incomplete station is made acceptable by this fix.
