# The app's backend: `prosumer.app`

An app on top of the library (the TCC's site, the example site, a notebook) should only render. `app.run`
takes the person's files and a few answers and returns everything a page shows, as strict JSON.

```python
import numpy as np
import pandas as pd
from prosumer import app

# a meter export: day-first dates, ';' and a decimal comma
idx = pd.date_range("2024-01-01", periods=42 * 24, freq="h")
load = 0.3 + np.random.default_rng(1).uniform(0, 0.1, len(idx)) + np.where(idx.hour >= 18, 1.0, 0.0)
csv = pd.DataFrame({"data": idx.strftime("%d/%m/%Y %H:%M"), "consumo (kWh)": load.round(3)})
data = csv.to_csv(index=False, sep=";", decimal=",").encode()

request = {"latitude": -25.43, "longitude": -49.27, "timezone": "America/Sao_Paulo", "days": 7,
           "price": {"kind": "flat", "price": 0.8, "currency": "BRL"}}
result = app.run(request, {"consumption": (data, "meter.csv")})
page = result.to_dict()  # or result.to_json(): strict JSON (NaN becomes null)
print(sorted(page))
print(page["report"]["economics"]["totals"])
```

Typed coordinates and time zone need no network; an `address` is geocoded (Nominatim), the time zone is asked
of Open-Meteo, a generation file gets the live weather forecast (Open-Meteo) and a Brazilian price the
distributor's tariffs (ANEEL). `app.Services` replaces each of those calls (tests, a cache, an offline app).

## The request

A plain JSON object; unknown fields are errors, empty strings mean "not given", numbers may come as text
(decimal comma accepted).

| Field | Default | What |
|---|---|---|
| `address` or `latitude` + `longitude` | required | rounded to ~1 km before anything is sent |
| `timezone` | asked of Open-Meteo | IANA zone of the files' wall-clock times |
| `file_times` | "local" | "UTC" for loggers that write UTC |
| `time_column`, `value_column`, `unit`, `kind` | guessed | help the reader when the guess fails |
| `days` | 7 | days ahead (1-35; the weather reaches 16) |
| `tilt`, `azimuth`, `kwp` | learnt from the data | the panels, when known |
| `load_hours`, `load_kw` | 3, 2.0 | the flexible load to place |
| `weeks` | 4 | recent weeks behind the consumption profile (1-52; 4 is the one measured on the Dingle houses, a note says so for another) |
| `test_days` | 28 | days of the forecast check |
| `issue_hour` | 0 | the hour each day's forecast of the check is made (12 = at noon the day before) |
| `models` | "lightgbm" | the forecasts whose median the check scores: "lightgbm" (the three naive rules and LightGBM, seconds), "naive" (the naive rules only) or "all" (also the zero-shot foundation models installed, minutes and torch). On the benchmark the naive median ranked 29th-36th of ~50, with LightGBM 10th-19th, with the foundation models 4th-5th |
| `price` | none | `{"kind": "flat", "price", "export_price", "fixed", "currency", "scheme"}`, `{"kind": "tou", "peak_hours": "17-21", "peak_price", "offpeak_price", ...}` or `{"kind": "brazil", "distributor", "icms", "pis_cofins", "connection", "gd", "cosip", "modality", "peak_start", "credit"}` (rates as fractions; `gd` "GD I" or "GD II" is required with a PV file; `peak_start` "HH:MM" for the branca; `credit`, the kWh of credit the last bill carried over) |

Files: `{"generation": (bytes, name), "consumption": (bytes, name)}`, one or both. With both, the bill nets the
PV against the household's use hour by hour and the report shows the savings.

`app.peek(data, name, quantity, request)` reads one file as `run` would and says how (the column, unit and
kind chosen, the hours, the span, the share measured), before anything is sent anywhere: a page can show it as
soon as a file is dropped. It takes only the reading fields of the request (the rest is ignored) and raises the
reader's message for a file it cannot read.

```python
from prosumer import app, data

pv, _ = data.example_plant(n_series=1, days=3)
text = pv.frame.assign(time=pv.frame["ds"].dt.strftime("%Y-%m-%d %H:%M"))[["time", "y"]]
text = text.rename(columns={"y": "Energy (kWh)"}).to_csv(index=False).encode()
p = app.peek(text, "inverter.csv", "generation", {"timezone": "America/Sao_Paulo"})
print(p["how"], p["hours"])
assert p["hours"] == 72 and "Energy (kWh)" in p["how"]
```

## The result (`to_dict()`)

| Key | What |
|---|---|
| `site` | `latitude`, `longitude` (rounded), `timezone`, `address_found` |
| `read` | per file: `file`, `how` (what the reader recognised), `hours`, `start`, `end`, `measured`, `series` |
| `outlooks` | per file: `Outlook.to_dict()` (`hourly`, `daily` with the confidence labels, `method`, `notes`) |
| `windows` | the best block of `load_hours` of each day |
| `windows_by_cost` | with a price: the cheapest block of each day for `load_kw`, with its expected cost |
| `pricing` | one line describing the tariff |
| `charts` | what the pages plot: `history_generation` / `history_consumption` (each day of the file: `energy`, `measured_hours`), `check` (the test hours: measured `y`, `evaluated`, and each forecast row), `performance` (a PV file's clear days: `energy`, `expected`, `index`) |
| `report` | `Report.to_dict()`: `summary`, `quality`, `clock`, `diagnostics`, `forecast`, `resolution`, `bands`, `economics` (with a price and the consumption), `provenance`, `notes`, `pending`, `skipped` (a section that could not be made, `forecast` or `economics`, and the note that says why) |
| `notes`, `log` | what the person should know; what each step did |
| `credits` | the source and licence of every outside piece of data (the licences require showing them) |

## In Portuguese

Every note, log line and message for the person is a `prosumer.i18n.Note`: English text that also keeps its
template and values, so the same result renders in Portuguese, numbers with a decimal comma and dates day
first. Errors `run` raises for the person's files or answers work the same way.

```python
from prosumer import i18n

pagina = result.to_dict(lang="pt")  # or result.to_json("pt")
print(pagina["log"][0])  # Local digitado: -25,43; -49,27.
try:
    app.run({**request, "days": 99}, {"consumption": (data, "meter.csv")})
except ValueError as e:
    print(i18n.message(e, "pt"))  # days deve estar entre 1 e 35
```

Codes and names are not translated: table columns, forecast names, the `confidence` values, units, request
fields, series and distributor names, and the sources, licences and citations of the outside data in
`credits` (kept in their source's words). What the library writes there itself is translated: the source
of what the person typed (prices, ICMS and PIS/COFINS rates), the conditions of use in `notes` ("free API:
non-commercial use only", ODbL, ...), and "not declared". The page labels
the codes itself. The Portuguese is one catalog of templates (`prosumer/i18n/pt.py`); a test checks that
every template in the code has its translation with the same placeholders, and two runs of the app
(consumption with a time-of-use price; PV and consumption with a Brazilian price, both `models="naive"`)
check that the notes, the log, how each file was read, the pending and skipped items, the bill's notes and
tariff, the pricing and the credits' notes have no untranslated text and no code in backticks.

The page speaks to a person, not a programmer: where a library note says which argument to pass ("pass
weather=...", the licence note naming `EnergySeries.from_dataframe`), `run` says it the way the request
answers it (`app.FOR_PEOPLE`, template for template, Portuguese included); `analyze` keeps the programmer's
wording.

How long it takes: seven years of hourly PV data (60,000 hours) took ~9 s with `models="naive"` and ~12 s
with the default, on a laptop CPU (2026-10-19), the JSON ~0.65 MB; since the roof is fitted once for the
next days and the diagnostics and the change points and the clock check were vectorised (2026-10-21), ~4 s
with `models="naive"` and ~6.6 s with the default (cloud container, 4 CPUs). Reading the file and the clock
check are most of what is left; a page should show that it is working.
