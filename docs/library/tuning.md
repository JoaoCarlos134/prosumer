# Tuning: every threshold, its default and where it was chosen

The library was built on the data the project had: two PV plants in Parana (Brazil), 20 houses in Dingle
(Ireland), Fronius exports. A number tuned on those sites and hidden in the code would silently fail for the
next user, so every one of them is an argument, its default is declared below, and the report says when a
default chosen on the project's sites shaped a result. Origins:

- **measured**: fitted or swept on the named data (an assumption elsewhere until checked on another site);
- **set by hand**: chosen while building, on the named data, never swept;
- **generic**: a convention or a physical limit, not fitted to any data.

## Reading (`io`)

| Argument | Default | Origin |
|---|---|---|
| `min_coverage` (readers, `EnergySeries.resample`) | 11/12 | generic: one 5-minute gap per hour |
| counter detection (`io.auto`, module constants) | within days falls <= half the rises (sum and count); rises >= 2 of its steps a day; a single day must sit above its own range, else an error asks for `kind=` | set by hand on a real Growatt export and the review's cases (coarse and hourly registers, 19 readings, a wobbling daily counter, a stepping load, a morning of PV). Cannot tell from a daily counter: an interval export that never covers afternoons, a load that rises all day and falls at midnight |
| counter reset (`meter.read_table`) | a drop > 10 typical steps, or to <= half from >= 5 typical steps; across midnight (`resets="restart"`) to <= half | set by hand on the same Growatt export (5 real restarts, 5 spikes, 157 dips) |
| counter outliers | up to 3 readings that jump > 10 typical steps away and come back | set by hand (review of 2026-10-17) |
| gap in a counter | readings > 1.5 steps apart | generic |
| `io.pvdaq` unit | 99.9% quantile / nameplate in 0.2-1.5 (kW) or 200-1,500 (W) | generic (checked on 10 PVDAQ systems) |

## Clock (`quality`, `analyze(clock_options=..., clock_weather_options=...)`)

| Argument | Default | Origin |
|---|---|---|
| `min_agreement` | 0.5 | generic: most complete days agree |
| `min_days` | 7 (sun), 14 (weather) | generic |
| `orientations` | flat, and 20 and 40 degrees in 8 directions | generic |
| `daylight_share` (weather check) | 0.05 of the month's peak | generic |
| `interval`, `max_interval_h` (weather check) | 90%, 1 h | generic |

## Diagnostics (`diagnose`, `analyze(diagnostics_options=...)`)

| Argument | Default | Origin |
|---|---|---|
| `penalty` | 3 x the BIC | **measured**: swept on the two Parana plants, false alarms checked on 10 Dingle PV houses |
| `clear_window_days`, `clear_quantile`, `clear_ratio` | 31 days, 0.9, 0.9 | set by hand on the two Parana plants |
| `min_segment_days`, `max_breaks` | 15, 11 | set by hand |
| `good_fit_r2` | 0.85 | set by hand (Cascavel 0.93 and Curitiba 0.81 fall either side) |
| `tilts`, `azimuths` | 0-60 degrees, whole compass | generic (widen `tilts` to 90 for facades) |
| `step_note_pct`, `trend_note_pct`, `dead_level`, `roof_passes` | 5%, 5%/year, 0.05, 4 | generic |

## The coming days (`forecast_ahead`)

| Argument | Default | Origin |
|---|---|---|
| `trust` | 1, 1, 1, 0.92, 0.91, 0.86, 0.79 (leads 1-7) | **measured** on the two Parana plants (horizon pilot), capped at 1 |
| `skill` | 0.50 ... 0.20 (leads 1-7) | **measured** there: the daily skill behind the labels |
| `confidence` | high >= 0.40, medium >= 0.25 | set by hand so leads 1-3 read high and 4-6 medium |
| `implausible` | GHI > 1.2 x clear sky + 50 W/m2 | generic (physical) |
| `kw_eff_days` | 60, else 120 days | set by hand (the pilot's rule) |
| `min_month_days` | 5 | set by hand |
| `kwp_share` | 0.8 | generic performance ratio |
| `weeks` (consumption) | 4 | set by hand; the rule was measured on the Dingle houses (beat "same as the last day" at every lead 1-14) |
| clear-day rule | as in diagnostics | set by hand on the two Parana plants |

## The forecast check (`analyze`)

| Setting | Default | Origin |
|---|---|---|
| `test_days` (argument) | 28 | generic |
| `BIAS_DAYS` (module constant, not an argument yet) | 14 | set by hand in the bias-correction pilot (Dingle houses; the value used, not swept) |
| `CALIBRATION_DAYS` (module constant, not an argument yet) | 28 | set by hand in the conformal pilot (the benchmark's three cases; not swept) |

## Economics readings (`economics.brazil`)

Not tuned on data but readings of the law where its text leaves a choice open; the defaults follow the
distributors' practice where it is known: `after_2028` ("tusd"), `gd2_minimum` ("ren_655I"),
`icms_exempt_compensated` ("all"), `bandeira_on_minimum` (True), `pis_cofins_on_charge` (False),
`icms_on_charge` (True), and for tarifa branca with generation `te_energy` (the homologated TE) and
`posto_order` (the dearest posto first).
