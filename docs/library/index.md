# prosumer

Day-ahead forecasting and analysis of an energy prosumer's **generation** (PV) and **consumption**, from the
files a monitoring portal or a meter exports to a complete, honest report: data quality, the clock of the
data checked against the sun, a forecast check against a fair reference, the next days ahead, the roof and
the health of the plant, and the bill with and without the PV.

Every default comes from a benchmark of 57 forecasting models on real plants and houses, with a pilot and a
gate before anything entered the library. The library never picks "the best model" for you (choosing on the
previous fold made things worse in all seven benchmark tests): the output is the **median** of the forecasts
it ran, scored against a reference, at several resolutions, with notes in plain language. Every number tuned
on the project's own sites is an argument with its origin declared (see [Tuning](tuning.md)).

CPU only by design: the best model of every benchmark test runs on a CPU.

## Install

```bash
pip install "prosumer[lightgbm,net,fronius] @ git+https://github.com/JoaoCarlos134/prosumer"
```

Python 3.11+. The core needs numpy, pandas, pyarrow, scipy and pandera. Extras: `lightgbm` (LightGBM and
scikit-learn), `net` (downloads behind TLS-inspecting proxies), `fronius` (Excel exports), `chronos`, `toto2`,
`ttm` (FlowState), one per foundation model, `embedded`, `plots`, `docs`, `dev`.

## One call

```python
from prosumer import analyze, data

pv, _ = data.example_plant(days=60)  # synthetic; use your own file with io.read_energy
report = analyze(pv, site=(-25.43, -49.27), test_days=14)
print(report.to_markdown()[:400])
assert report.forecast is not None and report.clock is not None
```

`report.to_dict()` is JSON-ready, for an app. The sections are described in
[Forecasting](forecasting.md) and [Diagnostics](diagnostics.md).

## Where to go next

- [Reading data](reading.md): any inverter, logger or meter export, time zones and daylight saving, counters.
- [Forecasting](forecasting.md): the forecast check (`analyze`) and the coming days (`forecast_ahead`).
- [Diagnostics](diagnostics.md): clock checks, roof orientation, clear-day performance and its steps.
- [Economics](economics.md): tariffs, the monthly bill, the cheapest hours for a flexible load; Brazil.
- [Embedded](embedded.md): a fitted model as one C header for a microcontroller.
- [App backend](app.md): `app.run`, files and a JSON request in, everything a page shows out.
- [Tuning](tuning.md): every threshold, its default and where it was chosen.
- [Validation](validation.md): what was checked, against what, and what was not.
- [Guia em português](pt/guia.md).
- [API reference](reference.md) and [changes](changelog.md).

## Data and licences

`data.dingle_houses` downloads the 20 houses of Khadem et al. (2024), *Scientific Data*,
doi:10.1038/s41597-024-03454-2 (CC0). `io.pvdaq` reads NREL's PVDAQ systems (CC BY 4.0,
doi:10.25984/1846021). Open-Meteo data are CC BY 4.0, but its free API is for non-commercial use only. Every
input carries its source and licence to the report (`Report.provenance`).
