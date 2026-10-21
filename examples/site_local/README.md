# Local example site: the next days from a CSV

A deliberately crude page to show what `prosumer` does with a person's own data. One Python file
(`app.py`, standard library only) and one HTML form (`index.html`), no JavaScript.

    python examples/site_local/app.py      # then open http://127.0.0.1:8000

You give a CSV (a time column and an energy column), say whether it is solar production or consumption, and
where it is (an address or the coordinates). Optional fields help: tilt, azimuth, kWp, the time zone, the
column names and units, and how many hours your heavy load runs.

Optionally, what you pay: one price for every hour, a simple time-of-use price (a peak price on weekdays in
the hours you give, another price the rest of the time and all weekend), with a fixed monthly charge, what an
exported kWh is worth and how exports are paid (net metering, net billing or nothing); or, in Brazil, the
tarifa convencional of Copel, Cemig, Enel SP or Light, downloaded from ANEEL's open data (ODbL; the page
credits ANEEL), with the ICMS and PIS/COFINS you read on your own bill (no defaults: they change by state and
month), the connection (custo de disponibilidade), the GD class of your PV (Lei 14.300) and the COSIP. The
page then shows the cheapest block of each day by expected cost next to the best one by energy and, for a
consumption file, your bill month by month with the expected monthly bill (the mean of the complete months).
Without a connection the Brazilian tariff fails with a clear message (choose a flat or time-of-use price).

## The backend: one call to `prosumer.app.run`

`app.py` turns the form into the request of `prosumer.app.run` (`_request`: only the price fields of the kind
chosen, the ICMS and PIS/COFINS typed in % as fractions) and its `Result` into HTML (`_render`); everything
else is the library's. `run` does seven steps, each one library call (its docstring has the details):

| Step | What | Library call |
|---|---|---|
| 1 | where: the typed coordinates, or the address geocoded; rounded to ~1 km; the time zone | `prosumer.io.geocode.geocode`, `round_site`, `timezone_at` |
| 2 | read the file (layout recognised; energy column by name and unit, never by position) | `prosumer.io.read_energy` |
| 3 | the weather forecast of the next days, six models (production only) | `prosumer.io.open_meteo.fetch_forecast` |
| 4 | the forecast, hourly and per day, with a confidence label | `prosumer.forecast_ahead` |
| 5 | the best block of hours of each day for a heavy load; with a price, the cheapest by expected cost | `prosumer.best_windows`, `prosumer.economics.windows_by_cost` |
| 6 | the analysis of the data (quality, clock, forecast check; with a price and a consumption file, the bill of each month and the expected monthly bill) | `prosumer.analyze` |
| 7 | what the pages plot | `Result.charts` |

The TCC's site does the same in TypeScript, on the same JSON (`Result.to_json`, also in Portuguese).

How step 4 works: for production, the plant's effective power and the roof's orientation are learnt from
its own clear days; each hour is that power times the sunlight on the panel plane computed from the weather
forecast. The weather is trusted less as the lead grows and the forecast slides toward the season's average
day; from day 8 it is only that (a pilot found no skill in the weather beyond a week). For consumption, each
hour is the average of that hour on the same kind of day (weekday or weekend) in the last 4 weeks. Details and
the measured numbers: the docstring of `prosumer.outlook`.

## What leaves the computer

Only the address (to Nominatim/OpenStreetMap, if you type one), the coordinates rounded to 2 decimals (to
Open-Meteo) and, for a Brazilian tariff, the distributor's name (to ANEEL). The CSV stays local. The free
Open-Meteo API is for non-commercial use.

## Limits

- The ranges are not calibrated intervals (across weather models and the season's spread).
- How much the weather is trusted at each lead (`prosumer.outlook.TRUST`) and the confidence labels were
  measured on two plants in Parana (Brazil); elsewhere they are an assumption. At day 1 the method ties the
  benchmark's LightGBM with real forecasts and is below the median of the benchmark's models.
- Production: if your data ended long ago, the forecast starts today anyway (the weather forecast starts
  today); the days in between are not forecast. Consumption uses no weather and starts the day after your data
  end, whenever that was: check the dates (the page shows the year).
- A roof you type in was not piloted; the one fitted from the data was.
- Money: expected costs from point forecasts (a cloudy surprise moves them); calendar months, not the
  meter's reading cycle; hourly netting. Brazil: this page offers the tarifa convencional only (the library
  bills tarifa branca too, with and without PV, from `prosumer.economics.brazil`), no real bill of these
  distributors was checked against; a month without a published bandeira
  takes the last one, with a note.
- Only localhost: it is not meant to be exposed on a network.
