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
  their median when there are two or more. On the benchmark's plants the median of the library's four
  weather rows ranked 1st of 24: with a weather forecast, it is the row to read.
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
  typical day as the lead grows (`trust`), and only the seasonal expectation beyond lead 7.
- **Consumption**: the weekday/weekend profile of the last 4 weeks (it beat "same as the last day" at every
  lead 1-14 on the Dingle houses).
- `daily.confidence` is "high", "medium", "low" or "seasonal only", from the skill measured per lead day
  (`skill`). `trust` and `skill` were measured on two plants in Parana; elsewhere they are an assumption, and
  every outlook that uses them says so. Both are arguments.
- The live forecast: `io.open_meteo.fetch_forecast(lat, lon, days=16)` (up to 16 days, several models; a model
  whose GHI is physically impossible is dropped from that day on).
- `economics.windows_by_cost(pricing, generation=o, hours=3, kw=2)` ranks the windows by what they cost.
