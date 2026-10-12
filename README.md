# prosumer

Day-ahead forecasting of energy prosumers' generation and consumption (PV plants, houses with PV), from
meter data to a complete, honest analysis. It is the basis of João Carlos Jachenski Junior's undergraduate
thesis (TCC), whose app is a thin layer over `prosumer.analyze`, and grew out of the Edge AI R&D project at
Lactec.

What makes it different from a forecasting toolkit: every default was decided by a benchmark of 57 models
on real plants and houses (`experimentos/testes_previsao/`), with a pilot and a gate before anything entered
the library, and the library re-does that benchmark's forecasts exactly (checked model by model). It never
picks "the best model" for you (the benchmark showed that choice is unstable); the output is the median of
the forecasts, scored against a fair reference, at several resolutions, with notes in plain language.

**Status: version 0.1 (step E2 of the thesis plan).** CPU only by design: the best model of every benchmark
test runs on a CPU.

## Install

```bash
uv pip install -e ".[lightgbm,net]"          # core + LightGBM + downloads behind TLS-inspecting proxies
uv pip install -e ".[chronos]"               # optional: Chronos-2 (each foundation model is its own extra)
uv pip install -e ".[fronius]"               # optional: read Fronius .xlsx exports
```

Python 3.11+. The core needs numpy, pandas, pyarrow, scipy and pandera only.

## One call: `analyze`

```python
from prosumer import analyze, data

houses = data.dingle_houses("consumption", houses=[1, 2, 3])   # real, public (CC0), downloaded once
report = analyze(houses, test_days=28)
print(report.to_markdown())
```

The report has: data quality (coverage, gaps, series ending apart), a day-ahead forecast check on the last
`test_days` (naive forecasts and their median as the output, skill against the benchmark's reference with a
day-bootstrap 95% CI, nRMSE, bias, R²), the same at several resolutions (hour, day/night, evening peak,
day), the data sources and licences, plain-language notes and the list of what is not available yet.
`report.to_dict()` is JSON-ready, for the app.

Your own data: `io.fronius.read_solarweb(["2024.xlsx", "2025.xlsx"], tz="America/Sao_Paulo", site=site)`
reads the inverter's 5-minute export into hourly kWh (one series per inverter); `io.meter.read_table(...)`
reads any CSV/Excel table of a meter (interval energy, a cumulative counter or average power, `;` and decimal
comma included). Whether Fronius stamps mark the start or the end of each 5 minutes is not documented: run
`analyze` with a site and look at the clock sections.

Add models and weather as you have them:

```python
from prosumer import EnergySeries, analyze
from prosumer.forecast import LightGBM, LightGBMQuantile
from prosumer.io import open_meteo

pv = EnergySeries.from_dataframe(df, unit="kWh", quantity="generation", tz="America/Sao_Paulo", freq="h")
site = (-24.83, -53.65)  # rounded: the coordinates are sent to Open-Meteo
raw = open_meteo.fetch_previous_runs(*site, start="2024-03-07", end="2026-05-31", tz="America/Sao_Paulo")
weather = open_meteo.wide(raw)  # one column per weather model, plus their mean and spread
ghi = [c for c in weather.columns if c.startswith("ghi_") and c != "ghi_spread"]

report = analyze(
    pv,
    site=site,                       # clear-sky reference, sun hours, clock checked against the sun
    weather=weather,                 # regime C (the real day-ahead forecast) and the clock against the clouds
    models=[
        LightGBM(),                  # history only: regime A, enters the median
        LightGBM(ghi, name="LightGBM-weather"),  # several weather models at once (pilot F2(a): best in C)
        LightGBMQuantile(),          # bands: coverage, CRPS, and a conformal recalibration
    ],
)
```

- `issue_hour=12` checks a forecast issued at noon for the rest of the day (pilot F2(d): the evening peak of
  consumption issued at noon beats the one issued at midnight).
- Foundation models: `forecast.Chronos2()`, `forecast.TiRex2()`, `forecast.Toto2()` (zero-shot, Apache-2.0,
  CPU). Each `ModelCard` says its licence, device and whether it sends data anywhere.

Or use the benchmark's protocol directly, to test a model of your own:

```python
from prosumer import DayAhead

task = DayAhead(series, test_start="2020-10-01", refit_days=31)  # rolling origin, causal gap filling
for window in task.windows():
    ...  # forecast window.timestamps from window.history (and window.future_covariates)
```

## Modules

| Module | What it does |
|---|---|
| `analysis` | `analyze(series) -> Report`, the app's single call |
| `contracts` | `EnergySeries`: validated long frame (`unique_id`, `ds`, `y`, `valid`), units, time zone, step |
| `protocol` | `DayAhead`, `folds`, `standardize_by_training`: the benchmark's day-ahead task, without leakage |
| `metrics` | skill and its CI, Diebold–Mariano, `ranking`, `ties_with_best`, metrics by resolution, band scores |
| `forecast` | `Naive`, `LightGBM`, `LightGBMQuantile`, `EmpiricalQuantiles`, `Chronos2`, `TiRex2`, `Toto2`; `rolling_forecast` |
| `postprocessing` | `conformal_quantiles` (causal band recalibration), `correct_bias` (consumption) |
| `physics` | sun position, clear sky, plane-of-array irradiance, orientation fit (numpy only) |
| `quality` | the clock of a PV series checked against the sun (`clock_offset`) and the clouds (`clock_offset_weather`) |
| `diagnostics` | from the energy alone: clear days, roof orientation, clear-day performance index and its steps (cleanings, faults) over time; `analyze(site=..., kwp=...)` |
| `io` | Fronius Solar.web exports (`fronius.read_solarweb`), any meter or station table (`meter.read_table`: interval, cumulative counter or power), Open-Meteo day-ahead forecasts (several models), NASA POWER hourly weather |
| `embedded` | a fitted Ridge, forest or LightGBM with its preprocessing and the day-ahead features, as one C header for an ESP32 (`to_c`, `footprint`, `block_totals`) |
| `provenance` | source and licence of every input, carried to the report |
| `data` | the real Dingle houses (CC0) and synthetic series for tests |

Not written yet: SparseTSF/TTM on a device (E4), soiling vs shading and string faults (they need 5-minute or DC data),
economics with time-of-use tariffs and the Brazilian module (E6).

## What the benchmark found (the defaults come from here)

- The weather input matters about ten times more than the model: on the plants the best skill goes from
  +0.14 (history only) to +0.37 (real day-ahead forecast) to +0.51 (the day's measured weather, a ceiling).
- Zero-shot foundation models lead with history only; a one-feature linear model on the weather is close to
  everything else once weather is in.
- Choosing the best model on the previous fold makes things worse; the median of all is a robust output.
- Bands: raw quantiles are calibrated in 7 of 11 tests; a causal conformal recalibration brings it to 10 of 11.
- Bias correction lifts consumption only for a median of ~40 models; for small medians it lowers the skill,
  so `analyze` reports it as a row, not as the output.

Details, numbers and every pilot: `experimentos/testes_previsao/LEIA-ME.md` and
`docs/projeto/PILOTOS_F1_F2.md` (in Portuguese).

## Data

The 20 houses are the public CC0 dataset of Khadem et al. (2024), "Comprehensive Dataset on Electrical Load
Profiles for Energy Community in Ireland", Scientific Data, doi:10.1038/s41597-024-03454-2 — cite it when
you use `data.dingle_houses`. Open-Meteo data are CC BY 4.0, but its free API is for non-commercial use only.

**Private repository.** The plant series came from third parties and are not cleared for publication.
Owner names were replaced by the plant's city, and coordinates were rounded to ~1 km. Do not reintroduce
any of this.

| Folder | What it is |
|---|---|
| `src/prosumer/` | the library |
| `tests/` | its tests, including exact parity with the benchmark's published numbers |
| `docs/proposta/` | thesis proposal, library feasibility study, plan |
| `docs/projeto/` | state of the analyses, pilots, plans for papers A and B |
| `docs/literatura/` | Edge AI review, references, survey of 127 models |
| `experimentos/testes_previsao/` | the day-ahead forecasting benchmark: scripts, hourly data, environments, results |
| `legado/` | the project's original code (reference only: the raw data stayed at Lactec) |

The package was called `prossumidor` until 2026-10-09. To pick up the work with Claude Code, start with
`CLAUDE.md`.
