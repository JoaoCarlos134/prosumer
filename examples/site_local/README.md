# Local example site: the next days from a CSV

A deliberately crude page to show what `prosumer` does with a person's own data. One Python file
(`app.py`, standard library only) and one HTML form (`index.html`), no JavaScript.

    python examples/site_local/app.py      # then open http://127.0.0.1:8000

You give a CSV (a time column and an energy column), say whether it is solar production or consumption, and
where it is (an address or the coordinates). Optional fields help: tilt, azimuth, kWp, the time zone, the
column names and units, and how many hours your heavy load runs.

## The backend in five steps (`forecast_page` in `app.py`)

| Step | What | Library call |
|---|---|---|
| 1 | read the CSV (separator, decimal comma and date order are guessed) | `prosumer.io.meter.read_table` |
| 2 | where: the typed coordinates, or the address geocoded; rounded to ~1 km; the time zone | `prosumer.io.geocode.geocode`, `round_site`, `timezone_at` |
| 3 | the weather forecast of the next days, six models (production only) | `prosumer.io.open_meteo.fetch_forecast` |
| 4 | the forecast, hourly and per day, with a confidence label | `prosumer.forecast_ahead` |
| 5 | the best block of hours of each day for a heavy load | `prosumer.best_windows` |

How step 4 works: for production, the plant's effective power and the roof's orientation are learnt from
its own clear days; each hour is that power times the sunlight on the panel plane computed from the weather
forecast. The weather is trusted less as the lead grows and the forecast slides toward the season's average
day; past the last weather model (~16 days) it is only that. For consumption, each hour is the average of the
same weekday and hour in the last 4 weeks. Details: the docstring of `prosumer.outlook`.

## What leaves the computer

Only the address (to Nominatim/OpenStreetMap, if you type one) and the coordinates rounded to 2 decimals (to
Open-Meteo). The CSV stays local. The free Open-Meteo API is for non-commercial use.

## Limits

- The ranges are not calibrated intervals (across weather models and the season's spread).
- How much the weather is trusted at each lead (`prosumer.outlook.TRUST`) is provisional until the horizon
  pilot measures it (`docs/projeto/PILOTOS_F1_F2.md`).
- If your data ended long ago, the forecast starts today anyway (the weather forecast starts today); the
  days in between are not forecast.
- Only localhost: it is not meant to be exposed on a network.
