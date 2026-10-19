# Validation: what was checked, against what, and what was not

The records behind each line are in `docs/projeto/PILOTOS_F1_F2.md` and `experimentos/testes_previsao/LEIA-ME.md`
(in Portuguese), with the scripts and saved outputs.

## The library reproduces the benchmark

- The benchmark's protocol (folds, windows with causal gap filling, normalisation on training data only, the
  evaluated hours) comes from the library, and the frozen v2 is reproduced exactly (`test_benchmark_protocol`).
- The 260 published metric rows are recomputed by the library from the saved forecasts
  (`test_benchmark_regression`).
- The forecasts themselves: the library's LightGBM regenerates the saved ones in the nine case/regime
  combinations (to 3.5e-18 on the machine that saved them; on another CPU to floating point, skill equal to
  1e-6); TiRex-2, Toto-2.0 and Chronos-2 to <= 8e-6 with identical skill; FlowState exactly.

## Forecasting

- **The output is a median, and which median matters** (pilot of 2026-10-16). The benchmark's median of 47-48
  models was 1st to 3rd in every test. With only the three naive rules (the default of `analyze`) the median
  ranked 29th to 36th. With the library's five models (LightGBM + four foundation models) it came within 0.01
  of the 47-model median in the three history-only tests, but did not tie with the best model in two of them.
  With a weather forecast, the median of the library's four weather rows was 1st of 24 on the plants (+0.372,
  ahead of the 22-model median); over every composition of two to four of them (check of 2026-10-19,
  `confere_medianas_c.py`), 1st to 11th, above each of its members in 10 of 11 (Chronos-2 with TiRex-2 fell
  below TiRex-2 alone); LightGBM with the linear model, 9th (+0.346). One test, two plants in Parana.
- **The coming days** (horizon pilot, 2026-10-12): on two plants in Parana the weather forecast beat the
  seasonal expectation on the daily total at every lead 1-7 (skill +0.49 at lead 1 to +0.20 at lead 7), and
  showed no skill at leads 8-15 (two months of data only). `trust` and `skill` come from there.
- **Not validated**: the lead-day trust and skill anywhere but Parana; the outlook's roof fit against a known
  roof (beyond Cascavel: fitted 15 degrees facing 30, the plant's sheet says 13 facing 25).

## Away from the project's own sites

- **Readers on real files from other brands**: Fronius Solar.web (7 and 5 years of two real plants), Growatt
  (a real export from India, Kaggle, CC BY 4.0: the counter bug was found there), NREL PVDAQ (10 systems' day
  files: their column names do not say the unit). On the whole Growatt file (188 days, 3 kW) the daily counter
  read by the library gives a median of 14.2 kWh a day and matches the inverter's AC power integrated over
  the same hours: median day 1.001, 182 of 188 days within 5% (`confere_growatt.py`, 2026-10-19). The same
  file chose the counter thresholds, so this checks the reading, not the thresholds.
- **PVDAQ pilot** (six US systems with a known roof: Colorado, Maryland, New Jersey, Maine, Nevada): roof fit,
  clock check and the outlook's physical chain against the same procedure on a Parana plant. Not finished (the
  run of 2026-10-17 was stopped for lack of memory after two systems). What it showed already, and the checks
  done since on its cached data: the roof fit came out far too steep (60 degrees for a 45 degree array, 45 for a
  10 degree roof; the azimuths were right). With the true roof, the clear-day performance index falls 40-45%
  from winter to summer at those sites (14% at Cascavel): the library's clear-sky model (Haurwitz) has no
  altitude and no haze (on the clearest days NASA's irradiance is 1.17 x the model in January and 0.83 x in July
  at Golden, 1,700 m), and the module temperature is not modelled. Fitting the roof against NASA's measured
  irradiance found the 45 degree array exactly (45 facing 160, true 45 facing 158). **Until the follow-up pilot
  (`piloto_telhado_medido.py`) settles it, the fitted roof is reliable only where the clear-sky model holds
  (low latitudes, near sea level): give the tilt and azimuth when you know them.**
- **Per-channel diagnostics** (pilot of 2026-10-17, Curitiba's two MPPTs): the share of each channel found 1 of
  3 known events (the return of July 2023), so it does not pass and is not in the library.
- A labelled dataset of cleaning events exists (DuraMAT "Automated PV Systems Cleaning Detection",
  doi:10.21948/1813454) but could not be reached on 2026-10-17: a candidate to check the change points.

## Economics

- Against 104 real Copel bills of one plant (2018-2026, a hand-made summary: kWh imported and injected, total
  paid): without generation the library's energy comes within +-5% (17-19 of 19 bills), not within +-2%
  (COSIP and the effective tax rates are not on the summary); with compensation (GD I) the library bills ~21%
  less than paid: the tax on compensated energy is charged on top of the minimum on the real bills, which no
  reading of the library reproduces yet. Needs detailed bills to settle.
- The legacy tariff study's mean price for 2018 (0.8062 R$/kWh) is reproduced: a regression of the port, not
  an independent check.
- Tarifa branca with generation: hand-worked cases only; not checked against a real bill.
