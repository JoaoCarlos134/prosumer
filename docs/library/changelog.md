# Changes

## Unreleased (after 0.1.0)

**Compatibility**

- pandas 3.1: the library no longer uses `dayofweek` / `dayofyear` (deprecated there; `day_of_week` /
  `day_of_year` exist since pandas 1.1), which warned from the outlook, LightGBM's features, the sun, the bill's
  weekends, the embedded export and the diagnostics.

**Speed**

- `app.run` on seven years of hourly PV: ~10 s -> ~6 s (`models="naive"`, same JSON byte for byte). The roof
  fit computes the plane-independent part of the irradiance once per fit, not once per plane of the grid, and
  is remembered by its inputs (`forecast_ahead` and `diagnose` on the same series fit it once); the clear sky
  and the sun vectors of long spans are remembered too (`physics.MEMORY`); the complete days are counted
  without a Python function per day.
- `app.run` on seven years of hourly PV: ~6.0 s -> ~4.1 s naive, ~8.3 s -> ~6.6 s with LightGBM (measured in
  the cloud container, 4 CPUs; same JSON byte for byte, English and Portuguese). The change-point search
  (`diagnostics`) fills each row of its dynamic programme for every end at once and shares the rows between
  the numbers of segments (0.47-0.61 s -> 0.07 s per call on 973 clear days, called twice); the clock check
  (`quality.clock_offset`) centres the production profiles once instead of once per plane orientation and
  labels the months without `strftime` (1.17 s -> 0.50 s with the sun already computed).

**Languages**

- `prosumer.i18n`: every note, log line and message for the person (reports, outlooks, bills, the readers,
  `app.run`) is a `Note`, English text that renders in Portuguese too: `Report`, `Outlook`, `Diagnosis`,
  `Bill` and `app.Result` take `to_dict(lang="pt")`, `i18n.message(error, "pt")` gives an error's text. One
  catalog of ~230 templates (`i18n/pt.py`), checked against the code by a test.
- `app.run`: a failed download of the weather, the address or the time zone is a message for the person
  (it was the bare network error), as a tariff already was.
- Fixed: a Brazilian price with an unknown `connection` (e.g. "bifasico") crashed `app.run` with a bare
  `KeyError`; `brazil.bill` and the app now say which connections exist (or take the minimum in kWh).
- Fixed (review of 2026-10-21): what the person types into `app.run` is checked with a message in both
  languages: `kind`, `timezone` (an unknown zone was a `ZoneInfoNotFoundError`), `time_column` (a name not in
  the file was a bare `KeyError`, also in `io.read_energy`), `price.scheme`, ICMS and PIS/COFINS each in
  [0, 1) and their sum below 1, `peak_start` (a value without ":" crashed `brazil.branca_blocks`), `gd`
  (required with a PV file: the message asked for dates the request cannot take) and a missing ANEEL
  components file of a year GD II needs.
- Portuguese pages: the source of typed prices and ICMS/PIS rates, and "not declared", are translated; a
  time step reads "5 min" or "1 day" in both languages (it was pandas' "0 days 00:05:00"); months read
  02/2026 in Portuguese; the connection minimum of a Brazilian price takes the decimal comma; a list that
  holds notes is joined in the page's language even when it mixes plain texts. `i18n.frame` takes a
  generator.
- Fixed (2026-10-23): `app.run` refused a wall-clock file with every hour of the daylight-saving changes
  (no gap in spring, one row for autumn's repeated hour, as the Dingle dataset and filled-in exports write
  it) with "pass dst='drop'", an argument the app's person cannot give. It is read without those hours and
  the log says so (and how to say the file is in UTC). The reader's error is now a `DaylightSavingError`, a
  `ContractError`.
- Fixed: `app.run` took a blank price field (`"currency": ""`, as a web form sends it) as its value, and
  `gd` with a consumption file only was an unknown field; blank is "not given" and `gd` is ignored without PV.
  The example site (`examples/site_local`) is now a thin shell over `app.run`.
- Fixed (review of 2026-10-21): `physics.mean_sun` remembered for a long span returned the first caller's
  index name and freq; `metrics.skill_ci95` warned (divide by zero) when a resampled set of test days had no
  reference error, which a nearly dead test period gives (its bounds are NaN, quietly); the example page told a
  person who had sent the consumption to "upload it" when the bill could not be made (it says why now), and
  its tax boxes, in %, got messages in fractions.
- Fixed: a PV or meter file whose evaluated test hours are all zero (an inverter dead in the last
  `test_days`) made `analyze`, and so `app.run`, raise from the metrics; the forecast check is now skipped
  with a note and the rest of the report is kept.

**Reading data**

- `io.auto.read_energy` and `io.auto.sniff`: a file of unknown layout, the energy column chosen by name and
  unit, never by position; ambiguous files are errors that list the columns.
- Counters are read as counters (a lifetime register, or an inverter's daily counter such as Growatt's
  `E-Today`), detected by their values; readings taken as logged (drifting timestamps), spikes dropped, a
  restart at midnight read as one. A real Growatt export used to give ~1,000 kWh a day from 3 kW.
- `io.pvdaq`: NREL PVDAQ systems (USA, CC BY 4.0), the unit inferred from the nameplate.
- `io.fronius.read_solarweb` reads the real Solar.web exports (units in brackets, the site's total column).
- `source_tz` in the meter and Fronius readers; `EnergySeries.resample`; `analyze` and `forecast_ahead` take
  15-minute and 1-minute data.
- Frames from the readers can be saved to parquet (provenance kept as a JSON-friendly dict in `attrs`).

**Forecasting**

- `forecast.FlowState` (zero-shot, 9 quantiles) with exact parity with the benchmark.
- `app.run`: the forecast check runs LightGBM by default (`models`: "lightgbm", "naive", "all"); `charts`
  carries what the pages plot (daily history, the test hours, the clear-day performance); `Report.hourly`
  keeps the test hours of `analyze`.
- Fixed: `analyze` with a trained model and less than `bias_days` (consumption) or `calibration_days` (bands)
  of history before the test raised "No objects to concatenate"; the past folds now start a week after the
  first day.
- `analyze`: the row `median_weather` (the median of the weather-based forecasts; with the library's four
  weather rows 1st of 24 on the benchmark's plants, other compositions 1st to 11th), a note when the output
  is the median of the naive forecasts only; `bias_days` and `calibration_days` are arguments.
- `outlook.forecast_ahead` (the next 1-35 days) and `best_windows`; the live forecast
  (`io.open_meteo.fetch_forecast`), geocoding (`io.geocode`).

**Diagnostics**

- `diagnostics.diagnose`: clear days, roof orientation, clear-day performance index and its change points.
- Every threshold of `diagnostics`, `quality` and `outlook` is an argument with its origin declared
  ([Tuning](tuning.md)); `analyze(diagnostics_options=, clock_options=, clock_weather_options=)`.

**Economics**

- `economics`: tariffs as data, the monthly bill under net metering, net billing or self-consumption,
  `cheapest_windows` and `windows_by_cost`; `analyze(economics=...)`.
- `economics.brazil`: tarifa cheia, bandeiras, custo de disponibilidade, tarifa branca, Lei 14.300 (GD I, GD
  II), ANEEL open data (`io.aneel`, `TariffBook.from_aneel`, tax rates that change by date), and tarifa
  branca with micro-generation (REN 1.000 art. 655-G: per-posto netting, the excess and the credits moved
  between postos by the TE ratio, each credit first in its own posto).
- Tarifa branca without generation: `by_block` has one row per posto (it was a single "all" block).
- Fixed: ANEEL's open data repeat each record with a new `_id`; the tariffs were billed at double.

**Embedded**

- `embedded`: Ridge, forests, LightGBM, SparseTSF and CycleNet as one C header for a microcontroller.

## 0.1.0 (2026-10-12)

The benchmark's protocol in the library (`protocol.DayAhead`, `metrics` at several resolutions, `ranking`,
`ties_with_best`, band scores), `physics`, `quality.clock_offset` and `clock_offset_weather`, `provenance`,
the readers of Open-Meteo, NASA POWER, Fronius Solar.web and meter tables, `data.dingle_houses`, the
forecasters `Naive`, `LightGBM`, `LightGBMQuantile`, `EmpiricalQuantiles`, `Chronos2`, `TiRex2`, `Toto2`, the
conformal recalibration of bands, and `analyze` as the single call.
