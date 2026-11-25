# Forecasting

Two different questions, two calls:

- **How good would a day-ahead forecast have been on my data?** `analyze` replays the benchmark's protocol on
  the last `test_days` of the series (rolling origin: each model is refitted on data before the test only)
  and scores every forecast against a fair reference.
- **What will the coming days look like?** `forecast_ahead` looks forward from the end of the data, 1 to 35
  days, hourly and per day, with a confidence label per day.

## The forecast check: `analyze`

```python
from prosumer import analyze, data

load = data.example_house(n_series=2, days=60)
r = analyze(load, test_days=14)
f = r.forecast.set_index("forecast")
print(f[["regime", "skill", "skill_ci_low", "skill_ci_high", "MBE"]].round(3))
assert {"median", "persistence_24h", "seasonal_168h", "mean_7d"} <= set(f.index)
```

The table has one row per forecast, all scored on the same hours:

- `skill` = 1 - RMSE / RMSE of the reference (0 = as good as it, 1 = perfect), with a 95% interval by
  resampling days. The reference is clear-sky persistence for generation with a `site`, "same as yesterday"
  otherwise.
- `median` is the output: the hour-by-hour median of every history-only forecast (regime A). With only the
  three naive rules in it, a note says how far that is from the benchmark's median of 47 models (see
  [Validation](validation.md)).
- `median_corrected` (consumption): the median with its recent bias removed, a row, not the output.
- With `weather=` (a day-ahead weather forecast, e.g. `io.open_meteo.wide(...)`): `weather_linear` (energy =
  a + b x forecast GHI) and every model that takes covariates are regime C rows, and `median_weather` is
  their median when there are two or more. On the benchmark's plants (the only test with a real weather
  forecast, 24 rows) the medians of two to four of the library's weather rows ranked 1st to 11th and beat
  each of their members in 10 of 11 compositions; the four together ranked 1st (+0.372), LightGBM with the
  linear model 9th (+0.346, against +0.330 and +0.312 alone).
- `resolution`: the same scores by hour, day/night blocks, evening peak and daily total (the best model
  changes with the resolution; use the one of your decision).
- `bands` (with a model that gives quantiles, e.g. `forecast.LightGBMQuantile()`): coverage of the 80% and 60%
  bands, width, CRPS, and a causal conformal recalibration.

### Adding models

```python
# needs: lightgbm
from prosumer import analyze, data
from prosumer.forecast import LightGBM

load = data.example_house(n_series=1, days=90)
r = analyze(load, test_days=14, models=[LightGBM(params={"n_estimators": 50})])
assert "LightGBM" in set(r.forecast["forecast"])
```

Every model has a `card` (licence, CPU/GPU, whether it sends data anywhere, regimes) that the report shows.
Available: `Naive`, `LightGBM`, `LightGBMQuantile`, `EmpiricalQuantiles`, and the zero-shot foundation models
`Chronos2`, `TiRex2`, `Toto2`, `FlowState` (Apache-2.0 weights, CPU, each its own extra). They are optional on
purpose: on the plants' weather-forecast regime LightGBM and the linear model together scored +0.346, and the
foundation models brought it to +0.372 at the cost of torch and a few seconds per forecast day.

### Weather

```python
import numpy as np
import pandas as pd
from prosumer import analyze, data, physics

site = (-25.43, -49.27)
pv, _ = data.example_plant(n_series=1, days=60)
ds = pd.date_range(pv.frame["ds"].min(), pv.frame["ds"].max() + pd.Timedelta(days=1), freq="h")
rng = np.random.default_rng(0)
weather = pd.DataFrame({"ds": ds, "ghi_mean": physics.clear_sky_ghi(ds, *site) * rng.uniform(0.4, 1.0, len(ds))})
r = analyze(pv, site=site, test_days=14, weather=weather)
assert "weather_linear" in set(r.forecast["forecast"])
```

For real use, `io.open_meteo.fetch_previous_runs` gives the archive of day-ahead runs (from March 2024) and
`io.open_meteo.wide` turns it into one column per weather model plus their mean and spread:

```python
# network
from prosumer.io import open_meteo

raw = open_meteo.fetch_previous_runs(-24.83, -53.65, start="2025-01-01", end="2025-03-31", tz="America/Sao_Paulo")
weather = open_meteo.wide(raw)
```

## The coming days: `forecast_ahead`

```python
from prosumer import best_windows, data, forecast_ahead

pv, _ = data.example_plant(n_series=1, days=200)
o = forecast_ahead(pv, days=3, site=(-25.43, -49.27))  # no weather: the seasonal expectation
print(o.daily[["date", "total", "low", "high", "confidence"]])
print(best_windows(o, hours=3))
assert len(o.daily) == 3 and (o.daily["source"] == "seasonal").all()
```

- **Generation** (needs the site): the plant is described by two numbers learnt from its own clear days, the
  orientation of the panels (or the tilt and azimuth you give) and the effective peak power. Each hour is that
  power x the irradiance on the panel plane from the weather forecast's GHI, pulled toward the season's
  typical day as the lead grows (`trust`), and only the seasonal expectation beyond lead 8.
- **Consumption**: the weekday/weekend profile of the last 4 weeks (it beat "same as the last day" at every
  lead 1-14 on the Dingle houses).
- `daily.confidence` is "high", "medium", "low" or "seasonal only", from the skill measured per lead day
  (`skill`). `trust` and `skill` were measured on two plants in Parana; elsewhere they are an assumption, and
  every outlook that uses them says so. Both are arguments.
- The live forecast: `io.open_meteo.fetch_forecast(lat, lon, days=16)` (up to 16 days, several models; a model
  whose GHI is physically impossible is dropped from that day on).
- `economics.windows_by_cost(pricing, generation=o, hours=3, kw=2)` ranks the windows by what they cost.

### How wrong the coming days may be: `look_back`

```python
from prosumer import data
from prosumer.outlook import look_back

pv, _ = data.example_plant(n_series=1, days=200)
past = look_back(pv, days=7, site=(-25.43, -49.27))  # each day forecast at 00:00 of that day
print(past.daily[["date", "total", "actual", "error", "source"]])
assert len(past.daily) == 7 and past.daily["actual"].notna().all()
```

Each of the last complete days is forecast by the same method as the coming days, with only the data before
it and, for PV, the weather forecast that existed the day before (`weather=io.open_meteo.fetch_previous_runs(...,
lead_days=1)`; the archive starts in 2024). Without it the past days are the seasonal expectation and the notes
say so. It shows the error of day 1; the later days of the outlook miss by more (`skill` by lead day).

### A range that fits the site: `past=` and `site_range`

The default daily low-high range is meant to hold the real total on 8 days in 10. On two plants in Parana, on
a period that chose nothing (June to November 2026), it held it on only 6.4 to 6.9 days in 10, and on 5 in 10
a week ahead. Given this site's own earlier forecasts next to what happened, the outlook recalibrates it:

```python
from prosumer import data, forecast_ahead
from prosumer.outlook import look_back

pv, _ = data.example_plant(n_series=1, days=200)
site = (-25.43, -49.27)
past = look_back(pv, days=31, site=site)  # 31 days forecast at lead day 1, next to what happened
o = forecast_ahead(pv, days=3, site=site, past=past)
print(o.daily[["date", "lead_day", "total", "low", "high", "range", "range_pairs"]])
assert o.daily["range"].tolist() == ["site", "default", "default"]
```

For each lead day, the errors of the last 60 days of that lead day (only days already known when the forecast
is issued), divided by the width of the default range they were issued with, give the 10th and 90th
percentiles (the conservative finite-sample order statistics); each edge of the day's range moves from the
forecast by those amounts, so the range need not be centred on it. A lead day with fewer than 30 past pairs
keeps the default range. With this rule the range held the real total on 7.9 to 8.2 days in 10 on the same
plants (7.7 to 8.4 at every lead day 1-7); it is wider than the default a week ahead (1.5 to 1.8 times) and about
as wide over the next three days.

- `look_back` gives lead day 1 only (up to 31 days). The other lead days need the outlooks this site issued
  before, stored with what happened: their `daily` tables with an `actual` column added, passed as a list
  (`outlook.past_pairs` says what it reads). A recalibrated table keeps `default_low`/`default_high`, the
  range the errors are measured against.
- Only the daily totals are recalibrated; the hourly ranges are not (the rule was measured on daily totals).
- Measured on generation only, at lead days 1-7, with pairs issued by the same method as the day they
  recalibrate (the outlook with the weather forecast). On consumption, beyond day 7, or with pairs of another
  method (for example `look_back` without archived weather feeding an outlook with a live forecast: then give
  `look_back` the archive, `weather=io.open_meteo.fetch_previous_runs(..., lead_days=1)`) it is untested.
- The app (`app.run`) keeps no forecasts yet, so it shows the default range with a note that says so; the
  local database of 0.10.0 is what lets it learn the site's range.
- `outlook.site_range(o, past, window_days=60, min_pairs=30, levels=(0.1, 0.9))` applies it to an outlook you
  already have.
