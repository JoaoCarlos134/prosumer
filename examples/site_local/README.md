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
day; from day 8 it is only that (a pilot found no skill in the weather beyond a week). For consumption, each
hour is the average of that hour on the same kind of day (weekday or weekend) in the last 4 weeks. Details and
the measured numbers: the docstring of `prosumer.outlook`.

## What leaves the computer

Only the address (to Nominatim/OpenStreetMap, if you type one) and the coordinates rounded to 2 decimals (to
Open-Meteo). The CSV stays local. The free Open-Meteo API is for non-commercial use.

## Limits

- The ranges are not calibrated intervals (across weather models and the season's spread).
- How much the weather is trusted at each lead (`prosumer.outlook.TRUST`) and the confidence labels were
  measured on two plants in Parana (Brazil); elsewhere they are an assumption. At day 1 the method ties the
  benchmark's LightGBM with real forecasts and is below the median of the benchmark's models.
- Production: if your data ended long ago, the forecast starts today anyway (the weather forecast starts
  today); the days in between are not forecast. Consumption uses no weather and starts the day after your data
  end, whenever that was: check the dates (the page shows the year).
- A roof you type in was not piloted; the one fitted from the data was.
- Only localhost: it is not meant to be exposed on a network.
