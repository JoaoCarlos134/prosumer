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
| `test_days` | 28 | days of the forecast check |
| `price` | none | `{"kind": "flat", "price", "export_price", "fixed", "currency", "scheme"}`, `{"kind": "tou", "peak_hours": "17-21", "peak_price", "offpeak_price", ...}` or `{"kind": "brazil", "distributor", "icms", "pis_cofins", "connection", "gd", "cosip", "modality", "peak_start"}` (rates as fractions) |

Files: `{"generation": (bytes, name), "consumption": (bytes, name)}`, one or both. With both, the bill nets the
PV against the household's use hour by hour and the report shows the savings.

## The result (`to_dict()`)

| Key | What |
|---|---|
| `site` | `latitude`, `longitude` (rounded), `timezone`, `address_found` |
| `read` | per file: `file`, `how` (what the reader recognised), `hours`, `start`, `end`, `measured`, `series` |
| `outlooks` | per file: `Outlook.to_dict()` (`hourly`, `daily` with the confidence labels, `method`, `notes`) |
| `windows` | the best block of `load_hours` of each day |
| `windows_by_cost` | with a price: the cheapest block of each day for `load_kw`, with its expected cost |
| `pricing` | one line describing the tariff |
| `report` | `Report.to_dict()`: `summary`, `quality`, `clock`, `diagnostics`, `forecast`, `resolution`, `bands`, `economics` (with a price and the consumption), `provenance`, `notes`, `pending` |
| `notes`, `log` | what the person should know; what each step did |
| `credits` | the source and licence of every outside piece of data (the licences require showing them) |
