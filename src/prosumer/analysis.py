"""The app's single call: `analyze(series) -> Report`.

The TCC app (last step of the plan) receives the user's data and returns a complete analysis. This module
defines that entry point now, while the library is still small, because it fixes what each module must hand
back: a section of the report, with numbers and plain-language notes. Today it covers what the library can
already do without training anything:

- **quality**: coverage, gaps and the series that end on different dates (the leakage case of the benchmark);
  for generation with a site, the clock checked against the sun (`quality.clock_offset`) and, with a
  weather forecast, against its clouds to a fraction of an hour (`quality.clock_offset_weather`);
- **diagnostics** (generation with a site): clear-day performance from the energy alone, the roof orientation
  and the steps of that performance over time (`diagnostics.diagnose`);
- **forecast check**: the day-ahead task of the benchmark (`DayAhead`) on the last `test_days` of the data,
  with the naive forecasts that need no training (same as yesterday, same day last week, mean of the last 7
  days) and their MEDIAN as the output (the library never picks "the best model": section 5c of the proposal),
  scored against the benchmark's reference, with a day-bootstrap CI and the metrics at several resolutions;
- **economics** (with `economics=` and a consumption): the monthly bill under the given tariff (core or
  Brazilian), its totals, the expected monthly bill and, with generation, the savings against no PV.

Every report also lists its inputs (`Report.provenance`: the series, the weather, each model) with source,
licence and citation, and notes what has no known licence, is for non-commercial use only or sends the data
out, so the app can say what an analysis used and under what terms.

The sections that need what was not given or not written yet (weather, bands, economics) are listed in
`Report.pending` (for economics, also what the bill does not model even when it is there), so the app can
show what is missing instead of silently leaving it out.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd

from . import diagnostics, metrics, physics
from .contracts import EnergySeries, step
from .diagnostics import Diagnosis, diagnose
from .economics.core import Pricing, Tariff, as_pricing
from .forecast import EmpiricalQuantiles, Forecaster, Probabilistic, rolling_forecast, rolling_quantiles
from .postprocessing import conformal_quantiles, correct_bias
from .protocol import DayAhead, H, Regime, Window
from .provenance import Provenance
from .provenance import of as provenance_of
from .quality import clock_notes, clock_offset, clock_offset_weather, clock_weather_notes

CONTEXT = 168  # one week of history: the longest naive forecast looks 7 days back
OUTPUT = "median"
CORRECTED = "median_corrected"  # consumption: the median with its recent bias removed (a row, not the output)
# with two or more weather rows (regime C), their median: on the benchmark's plants the median of the
# library's four weather rows was 1st of 24 (+0.372, ahead of the 22-model ensemble's +0.367; 2026-10-16)
WEATHER_OUTPUT = "median_weather"
BIAS_DAYS = 14  # days of past forecasts the bias factor of consumption looks at (`correct_bias`)
CALIBRATION_DAYS = 28  # forecasts before the test that recalibrate each band (conformal)
# what the economics section does not do even when it is there (kept in `Report.pending`)
ECONOMICS_LEFT = (
    "Not modelled: tarifa branca with generation (per-posto netting), COSIP read from a bill (type it as "
    "`brazil.Setup(cosip=...)`), grupo A (demand charges), the tax reform of LC 214/2025."
)

PENDING = {
    "weather (regimes B and C)": "pass `weather=io.open_meteo.wide(...)` (Open-Meteo, several models)",
    "bands (quantiles)": "pass a model with quantiles, e.g. `models=[forecast.LightGBMQuantile()]`",
    "diagnostics": "pass `site=(lat, lon)` with a generation series: clear-day performance and its changes",
    "economics": "pass `economics=` (an `economics.Tariff`, `economics.Plan` or `economics.brazil.Setup`) "
    "with the consumption (the series, or `consumption=` next to a generation series): the monthly bill, "
    f"and the savings with `generation=`. {ECONOMICS_LEFT}",
}


@dataclass
class EconomicsSection:
    """The bill section of a `Report` (`analyze(economics=...)`).

    `monthly` and `by_block`: the bill's tables as `economics.bill` / `economics.brazil.bill` return them
    (money in `currency`; `by_block` per tariff block, a single "all" block for the Brazilian bill);
    `totals`: one row per site over all months (`months, complete_months, consumption, generation,
    grid_import, export, total, without_pv, savings, mean_month`), `mean_month` being the mean bill of the
    months with every hour measured (the expected monthly bill; NaN when no month is complete); `tariff`: a
    one-line description; `notes`: the bill's notes; `provenance`: where the prices came from.
    """

    tariff: str
    scheme: str
    currency: str
    monthly: pd.DataFrame
    by_block: pd.DataFrame
    totals: pd.DataFrame
    notes: list[str] = field(default_factory=list)
    provenance: pd.DataFrame | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tariff": self.tariff,
            "scheme": self.scheme,
            "currency": self.currency,
            "monthly": _records(self.monthly),
            "by_block": _records(self.by_block),
            "totals": _records(self.totals),
            "notes": list(self.notes),
            "provenance": _records(self.provenance),
        }

    def to_markdown(self) -> str:
        m = self.monthly.copy()
        m["month"] = pd.to_datetime(m["month"]).dt.strftime("%Y-%m")
        cols = [
            c
            for c in (
                "unique_id",
                "month",
                "coverage",
                "consumption",
                "generation",
                "grid_import",
                "export",
                "compensated",
                "credit_balance",
                "total",
                "without_pv",
                "savings",
            )
            if c in m.columns
        ]
        lines = [
            "## Economics",
            "",
            f"Tariff: {self.tariff}. Scheme: {self.scheme}. Money in {self.currency}, energy in kWh; "
            "calendar months. `without_pv`: the same consumption all bought from the grid.",
            "",
            _table(m[cols]),
        ]
        blocks = self.by_block
        if len(set(blocks["block"])) > 1:
            b = blocks.copy()
            b["month"] = pd.to_datetime(b["month"]).dt.strftime("%Y-%m")
            lines += ["", "### By tariff block", "", _table(b)]
        totals = self.totals.astype(object)  # no complete month: "n/a", the note says why
        totals["mean_month"] = [v if np.isfinite(v) else "n/a" for v in self.totals["mean_month"]]
        lines += ["", "### Totals", "", _table(totals)]
        if self.notes:
            lines += ["", *[f"- {n}" for n in self.notes]]
        return "\n".join(lines)


@dataclass
class Report:
    """What `analyze` returns. Plain data: the app renders it, `to_markdown` gives a readable text version."""

    summary: dict[str, Any]
    quality: pd.DataFrame
    notes: list[str] = field(default_factory=list)
    forecast: pd.DataFrame | None = None  # one row per forecast: skill, CI, nRMSE, MBE, R2
    resolution: pd.DataFrame | None = None  # the output (median) and the weather forecast, per resolution
    weather: pd.DataFrame | None = None  # coverage of each weather model, when a forecast was given
    bands: pd.DataFrame | None = None  # calibration and CRPS of each model's quantile band
    clock: pd.DataFrame | None = None  # generation with a site: clock offset against the sun, per period
    # generation with `weather`: clock offset against the clouds of the forecast, to a fraction of an hour
    clock_weather: pd.DataFrame | None = None
    # where each input came from and its licence: the series, the weather and each model (see `_provenance`)
    provenance: pd.DataFrame | None = None
    # generation with a site: roof orientation, clear-day performance index, its segments and steps
    diagnostics: Diagnosis | None = None
    # with `economics=` and a consumption: the monthly bill, its totals and the savings of the PV
    economics: EconomicsSection | None = None
    pending: dict[str, str] = field(default_factory=lambda: dict(PENDING))

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly version (timestamps as ISO text, tables as lists of records)."""
        records = _records
        return {
            "summary": {k: _plain(v) for k, v in self.summary.items()},
            "quality": records(self.quality),
            "notes": list(self.notes),
            "forecast": records(self.forecast),
            "resolution": records(self.resolution),
            "weather": records(self.weather),
            "bands": records(self.bands),
            "clock": records(self.clock),
            "clock_weather": records(self.clock_weather),
            "provenance": records(self.provenance),
            "diagnostics": None if self.diagnostics is None else self.diagnostics.to_dict(),
            "economics": None if self.economics is None else self.economics.to_dict(),
            "pending": dict(self.pending),
        }

    def to_markdown(self) -> str:
        s = self.summary
        lines = [
            f"# Analysis: {s['quantity']}, {s['n_series']} series",
            "",
            f"{s['start']} to {s['end']} ({s['tz']}, step {s['freq']}, unit {s['unit']}).",
            "",
            "## Data quality",
            "",
            _table(self.quality),
        ]
        if self.clock is not None and not self.clock.empty:
            lines += [
                "",
                "### Clock against the sun",
                "",
                "Hours the production is late (+) or early (-) relative to the clear sky at the site, for "
                "the whole series and per month; `confident` when most complete days agree.",
                "",
                _table(self.clock),
            ]
        if self.clock_weather is not None and not self.clock_weather.empty:
            lines += [
                "",
                "### Clock against the weather",
                "",
                "Hours the production follows the clouds of the weather forecast late (+) or early (-), to a "
                "fraction of an hour, with a 90% interval by resampling days; independent of the roof's "
                "orientation. A day-ahead forecast can carry its own timing error of a few tenths of an "
                "hour.",
                "",
                _table(self.clock_weather),
            ]
        d = self.diagnostics
        if d is not None and not d.orientation.empty:
            lines += [
                "",
                "## Diagnostics",
                "",
                "From the energy alone: the days the production itself shows as cloudless, the roof "
                "orientation fitted on them, and the clear-day performance index (energy over the clear-sky "
                "expectation on that plane; a performance ratio with `kwp`, the effective peak power in kW "
                "without it) as a straight line per segment. Steps between segments are events: a cleaning "
                "or a repair (up), a fault or new shading (down).",
                "",
                _table(d.orientation),
            ]
            if not d.segments.empty:
                lines += ["", "### Segments", "", _table(d.segments)]
            if not d.steps.empty:
                lines += ["", "### Steps", "", _table(d.steps)]
        if self.notes:
            lines += ["", "## Notes", "", *[f"- {n}" for n in self.notes]]
        if self.forecast is not None:
            lines += [
                "",
                "## Day-ahead forecast check",
                "",
                f"Test: {s['test_start']} to {s['test_end']}, issued at {s['issue_hour']:02d}:00, "
                f"{s['test_windows']} series-days. Skill against `{s['reference']}` (0 = same as it). "
                f"Output: the {OUTPUT} of the regime A forecasts (history only); regime C uses the weather "
                f"forecast issued the day before, and `{WEATHER_OUTPUT}` is the median of the regime C rows "
                "when there are two or more.",
                "",
                _table(self.forecast),
            ]
        if self.resolution is not None:
            lines += ["", "### At several resolutions", "", _table(self.resolution)]
        if self.bands is not None:
            lines += [
                "",
                "### Bands",
                "",
                "Share of the hours inside the central 80% and 60% intervals (calibrated: within 5 points "
                "of nominal), mean width of the 80% band and CRPS, against the quantiles of the same hour "
                "over the last 14 days, all on the same hours.",
                "",
                _table(self.bands),
            ]
        if self.economics is not None:
            lines += ["", self.economics.to_markdown()]
        if self.weather is not None:
            lines += [
                "",
                "## Weather forecast",
                "",
                "Coverage of each model, from the first day of data to the end of the test.",
                "",
                _table(self.weather),
            ]
        if self.provenance is not None and not self.provenance.empty:
            lines += [
                "",
                "## Data sources and licences",
                "",
                "What this analysis used, under what licence, and what to cite when sharing its results.",
                "",
                _table(self.provenance[[c for c in _PROVENANCE_SHOWN if c in self.provenance.columns]]),
            ]
        lines += ["", "## Not available yet", "", *[f"- **{k}**: {v}" for k, v in self.pending.items()]]
        return "\n".join(lines) + "\n"


def analyze(
    series: EnergySeries,
    *,
    site: tuple[float, float] | None = None,
    test_days: int = 28,
    issue_hour: int = 0,
    levels: dict[str, metrics.Level] | None = None,
    weather: pd.DataFrame | None = None,
    models: Sequence[Forecaster] = (),
    kwp: float | dict[str, float] | None = None,
    economics: Tariff | Pricing | None = None,
    consumption: EnergySeries | None = None,
    generation: EnergySeries | None = None,
    diagnostics_options: Mapping[str, Any] | None = None,
    clock_options: Mapping[str, Any] | None = None,
    clock_weather_options: Mapping[str, Any] | None = None,
) -> Report:
    """Quality and a day-ahead forecast check of `series`, as one report.

    `site`: (latitude, longitude) of a generation series. With it the reference is clear-sky persistence and
    only the hours with sun count, as in the benchmark's plants, and the clock of each series is checked
    against the sun (`Report.clock`, with a note when it is off); without it the reference is "same as
    yesterday" and the hours count by the training profile. `test_days`: the last days of the data used as the
    test. `issue_hour`: as in `DayAhead` (12 = the evening issued at noon). `levels`: resolutions of
    `metrics.by_resolution` (default: hour, day/night, evening peak, day; `metrics.by_blocks` for a tariff).

    `weather`: the day-ahead weather forecast, as `io.open_meteo.wide` returns it (`ds`, `ghi_<model>`,
    `ghi_mean`, ...; with `unique_id` for one site per series, without it the same weather for every series).
    It adds the weather section (coverage of each model) and, for generation, the regime C forecast
    `weather_linear`: energy = a + b x the mean forecast GHI, per series, fitted on the sun hours before the
    test (the benchmark's "linear physics" on GHI instead of the panel-plane irradiance). Every row of the
    table is then scored on the same hours: those with a weather forecast.

    `models`: forecasters of `prosumer.forecast` to add as rows, run with the rolling origin on the same test
    days. A model whose card includes regime A (history only) is a regime A row and enters the median; one
    that takes covariates (e.g. `LightGBM(["ghi_mean"])`, `Chronos2(["ghi_mean"])`) is a regime C row and
    needs `weather`. Foundation models get 1024 hours of history, as in the benchmark.

    Generation with a `site` also gets the diagnostics (`diagnostics.diagnose`: clear days, roof orientation,
    clear-day performance index and its change points, `Report.diagnostics`); `kwp` (one value, or per
    `unique_id`) turns the index into a performance ratio. `diagnostics_options`: the tuning keyword arguments
    of `diagnose` by name (e.g. `{"tilts": np.arange(0, 91, 5.0)}` for facade panels, `{"penalty": 2.0}`);
    with the defaults of the penalty and of the clear-day rule, chosen on the project's own sites, a note says
    so. `clock_options` and `clock_weather_options`: keyword arguments of `quality.clock_offset` and
    `quality.clock_offset_weather` by name (e.g. `{"min_agreement": 0.6}`, `{"max_shift_h": 3}`); the
    `column` of the weather check is chosen by `analyze`.

    `economics`: how the household pays, as an `economics.Tariff` (net metering), an `economics.Plan` (a
    tariff and the export scheme: net metering, net billing or self-consumption) or an
    `economics.brazil.Setup` (an ANEEL tariff book, the connection, the GD class and the readings of Lei
    14.300). It adds `Report.economics`: the monthly bill (by tariff block for time-of-use), its totals, the
    expected monthly bill (mean of the complete months) and, with generation, the bill without the PV and the
    savings; plus the tariff's sources in `Report.provenance`. The bill needs the consumption: the series
    itself, or `consumption=` next to a generation series; `generation=` adds the PV to a consumption
    series. The two series are paired by `unique_id` (or one each, whatever their names), netted hour by
    hour, and billed by calendar month. A bill that cannot be made (a generation series alone, a tariff with
    no vigencia for the data's dates, tarifa branca with generation) leaves the section out with a note.
    """
    if test_days < 2:
        raise ValueError("test_days must be >= 2: the confidence interval resamples days")
    knobs = diagnostics._knobs(diagnostics_options or {})  # checked before any work
    clock_kw = _options(clock_options, clock_offset, "clock_options", skip=("series", "site"))
    clock_w_kw = _options(
        clock_weather_options,
        clock_offset_weather,
        "clock_weather_options",
        skip=("series", "weather", "column"),
    )
    early: list[str] = []  # notes from before the quality section
    series = _to_hourly(series, "series", early)
    consumption = _to_hourly(consumption, "consumption", early) if consumption is not None else None
    generation = _to_hourly(generation, "generation", early) if generation is not None else None
    s = series.to_kwh()
    if s.freq != "h":
        raise ValueError(f"The day-ahead check needs hourly data or finer, not freq={s.freq!r}")
    frame = s.frame
    end = frame.loc[frame["valid"], "ds"].max().normalize()
    test_start = end - pd.Timedelta(days=test_days - 1)
    summary: dict[str, Any] = {
        "quantity": s.quantity,
        "unit": s.unit,
        "tz": s.tz,
        "freq": s.freq,
        "n_series": len(s.series),
        "start": frame["ds"].min(),
        "end": frame["ds"].max(),
    }
    quality, notes = _quality(s)
    notes = [*early, *notes]
    clock = None
    if s.quantity == "generation" and site is not None:
        clock = clock_offset(s, site, **clock_kw)
        notes.extend(clock_notes(clock))
    w = None if weather is None else _weather_frame(weather, s.series)
    clock_weather = None
    if s.quantity == "generation" and w is not None:
        ghi = (
            "ghi_mean"
            if "ghi_mean" in w.columns
            else next((c for c in w.columns if c.startswith("ghi")), None)
        )
        if ghi is not None:
            clock_weather = clock_offset_weather(s, w, column=ghi, **clock_w_kw)
            notes.extend(clock_weather_notes(clock_weather))
    diag = None
    base_pending = dict(PENDING)
    if s.quantity == "generation" and site is not None:
        diag = diagnose(s, site, kwp=kwp, **dict(diagnostics_options or {}))
        notes.extend(diag.notes)
        notes.extend(_diagnostics_defaults_note(diag, knobs))
        base_pending["diagnostics"] = (
            "soiling vs shading and string faults need DC or 5-minute data (not yet)"
        )
    econ, econ_sources, econ_note = _economics(series, economics, consumption, generation)
    if econ_note:
        notes.append(econ_note)
    if econ is not None:
        base_pending["economics"] = ECONOMICS_LEFT
    elif econ_note and economics is not None:
        base_pending["economics"] = f"{econ_note} {ECONOMICS_LEFT}"

    def skipped(reason: str) -> Report:
        """The report without the forecast check: every other section is kept."""
        sources, source_notes = _provenance(s, None, (), econ_sources)
        return Report(
            summary=summary,
            quality=quality,
            notes=[*notes, f"Forecast check skipped: {reason}", *source_notes],
            clock=clock,
            clock_weather=clock_weather,
            provenance=sources,
            diagnostics=diag,
            economics=econ,
            pending=base_pending,
        )

    first = frame["ds"].min().normalize()
    if not (frame.loc[frame["valid"], "y"] != 0).any():
        # nothing to forecast, and every reference has zero error (the skill would divide by zero)
        return skipped("every value is zero (a dead meter or inverter, or the wrong column).")
    if test_start - first < pd.Timedelta(hours=CONTEXT):
        return skipped(f"it needs {CONTEXT // 24} days of history before the {test_days} test days.")

    task = DayAhead(
        s, test_start=test_start, test_end=end, refit_days=test_days, context=CONTEXT, issue_hour=issue_hour
    )
    windows = task.windows()
    if not windows:
        return skipped("no test day has all its target hours measured.")

    is_gen = s.quantity == "generation"
    reference = "clear_sky_persistence" if is_gen and site is not None else "persistence_24h"
    fc = _naive_forecasts(windows, site, reference)
    actual = frame.loc[frame["valid"], ["unique_id", "ds", "y"]]
    keep = _evaluated(actual, fc, is_gen, site, test_start)
    actual = actual.loc[keep]
    regimes = {OUTPUT: "A", **dict.fromkeys(_NAIVE, "A"), reference: "A"}
    weather_table = None
    bands_raw: dict[str, pd.DataFrame] = {}
    # consumption: every median forecast also over the BIAS_DAYS before the test, so the bias factor of the
    # first test day already has its days (the benchmark had only the test and left its first week as is)
    point_past: dict[str, pd.DataFrame] = {}
    is_cons = s.quantity == "consumption"
    if is_cons:
        point_past = _past_naive(task, test_start)
    bands_past: dict[str, pd.DataFrame] = {}  # the same model's bands over the calibration days
    for model in models:
        name = model.card.name
        if name in fc.columns:
            raise ValueError(f"Two forecasts named {name!r}")
        history_only = Regime.HISTORY in model.card.regimes
        if not history_only and w is None:
            notes.append(f"{name} needs a weather forecast (`weather=`): left out.")
            continue
        task_m = DayAhead(
            s,
            test_start=test_start,
            test_end=end,
            refit_days=test_days,
            context=1024 if model.card.family == "foundation" else CONTEXT,
            min_history=CONTEXT,  # the same test days as the naive forecasts
            issue_hour=issue_hour,
            covariates=None if history_only else w,
        )
        if hasattr(model, "predict_quantiles") and hasattr(model, "levels"):
            # one fit: the point is the 0.5 level, or the model's own (`point_from_quantiles`, FlowState)
            qf = rolling_quantiles(cast(Probabilistic, model), task_m)
            bands_raw[name] = qf.drop(columns="yhat")
            past_q = _calibration_bands(cast(Probabilistic, model), task_m, test_start)
            bands_past[name] = past_q.drop(columns="yhat")
            out = qf[["unique_id", "ds", "yhat"]]
            if is_cons and history_only:
                point_past[name] = past_q[["unique_id", "ds", "yhat"]]
        else:
            out = rolling_forecast(model, task_m)
            if is_cons and history_only:
                point_past[name] = rolling_forecast(model, _before(task_m, test_start, BIAS_DAYS))
        fc = fc.merge(out.rename(columns={"yhat": name}), on=["unique_id", "ds"], how="left")
        regimes[name] = "A" if history_only else "C"
    # the output: median of every regime A forecast (the naive ones and the A models; not the reference alone)
    in_median = [
        *_NAIVE,
        *[n for n, r in regimes.items() if r == "A" and n not in (OUTPUT, reference, *_NAIVE)],
    ]
    fc[OUTPUT] = fc[in_median].median(axis=1)
    output = OUTPUT
    if len(in_median) == len(_NAIVE):
        notes.append(
            f"The output (`{OUTPUT}`) is the median of the {len(_NAIVE)} naive forecasts only. In the "
            "benchmark that median ranked 29th to 36th of ~53; with the library's five models added "
            "(`models=[LightGBM(), Chronos2(), TiRex2(), Toto2(), FlowState()]`) it came within 0.01 of the "
            "median of all 47 benchmark models in the three history-only tests, still short of the best "
            "model in two of them (pilot of 2026-10-16)."
        )
    if is_cons:
        fc = _corrected_median(fc, point_past, in_median, frame, test_start)
        regimes[CORRECTED] = "A"
    if w is not None:
        weather_table = _weather_coverage(w, frame["ds"].min(), end + pd.Timedelta(hours=H - 1))
        if is_gen:
            fc, note = _weather_linear(fc, w, s, site, test_start)
            if note:
                notes.append(note)
            else:
                regimes["weather_linear"] = "C"
    weather_rows = [n for n, r in regimes.items() if r == "C"]
    if len(weather_rows) >= 2:
        fc[WEATHER_OUTPUT] = fc[weather_rows].median(axis=1)
        regimes[WEATHER_OUTPUT] = "C"
        notes.append(
            f"`{WEATHER_OUTPUT}` is the median of the {len(weather_rows)} forecasts that use the weather "
            f"({', '.join(weather_rows)}). With a weather forecast it is the row to read: on the benchmark's "
            "two plants the median of the library's four weather rows ranked 1st of 24 (pilot of 2026-10-16)."
        )
    # common support: every row on the hours where every forecast exists (a gap in one drops the hour for all)
    missing = fc.loc[fc[list(regimes)].isna().any(axis=1), ["unique_id", "ds"]].assign(_drop=True)
    flagged = actual.merge(missing, on=["unique_id", "ds"], how="left")["_drop"].fillna(False).to_numpy(bool)
    actual = actual.loc[~flagged]
    if flagged.any():
        notes.append(
            f"{int(flagged.sum())} test hours without a forecast from every model left out of every row."
        )
    ref = fc[["unique_id", "ds", reference]].rename(columns={reference: "yhat"})
    _, r_ref = metrics.align(ref, actual, ref)
    if len(r_ref) and not (r_ref["yhat"].to_numpy() != r_ref["y"].to_numpy()).any():
        # every skill would divide by zero (`metrics.skill`): constant or exactly repeating data
        return skipped(
            f"the series repeats exactly: the reference ({reference}) is perfect on every test hour, so "
            "the skill is undefined. A stuck meter, a fixed estimate or synthetic data?"
        )
    rows, aligned = [], {}
    for name, regime in regimes.items():
        m, r = metrics.align(fc[["unique_id", "ds", name]].rename(columns={name: "yhat"}), actual, ref)
        row = {"forecast": name, "regime": regime, "skill": metrics.skill(m, r)}
        try:
            row["skill_ci_low"], row["skill_ci_high"] = metrics.skill_ci95(m, r)
        except ValueError:
            row["skill_ci_low"] = row["skill_ci_high"] = float("nan")
        mm = metrics.metrics(m)
        row.update(nRMSE=mm["nRMSE"], MBE=mm["MBE"], R2=mm["R2"], R2_daily=mm["R2_daily"])
        rows.append(row)
        aligned[name] = (m, r)
    # the reference last, the regime C forecast after the regime A ones
    table = pd.DataFrame(rows)
    order = list(
        dict.fromkeys(
            [
                output,
                CORRECTED,
                *_NAIVE,
                *[n for n, r in regimes.items() if r == "A" and n != reference],
                WEATHER_OUTPUT,
                "weather_linear",
            ]
            + [n for n, r in regimes.items() if r == "C"]
            + [reference]
        )
    )
    table = table.set_index("forecast").loc[[n for n in order if n in set(table["forecast"])]].reset_index()
    resolution = pd.concat(
        [
            metrics.by_resolution(*aligned[n], levels).assign(forecast=n)
            for n in [output, *[n for n, r in regimes.items() if r == "C"]]
            if n in aligned
        ],
        ignore_index=True,
    )
    resolution = resolution[["forecast", *[c for c in resolution.columns if c != "forecast"]]]
    bands = None
    if bands_raw:
        reference_band = rolling_quantiles(
            EmpiricalQuantiles(),
            DayAhead(
                s,
                test_start=test_start,
                test_end=end,
                refit_days=test_days,
                context=24 * 14,
                min_history=CONTEXT,
                issue_hour=issue_hour,
            ),
        ).drop(columns="yhat")
        hours_of = _production_hours(s, is_gen, site, test_start - pd.Timedelta(days=CALIBRATION_DAYS))
        measured = frame.loc[frame["valid"], ["unique_id", "ds", "y"]]
        band_regimes = dict(regimes)
        for name in list(bands_raw):
            past = bands_past[name]
            both = bands_raw[name] if past.empty else pd.concat([past, bands_raw[name]], ignore_index=True)
            cq = conformal_quantiles(both, measured, days=CALIBRATION_DAYS, hours=hours_of(both))
            cq = cq[cq["ds"] >= test_start]
            uncalibrated = cq.loc[~cq["conformal"], "ds"].dt.normalize().nunique()
            if uncalibrated:
                notes.append(
                    f"{name}+conformal: {uncalibrated} test days without 7 days of past errors were left "
                    "as the model gave them."
                )
            bands_raw[f"{name}+conformal"] = cq.drop(columns="conformal")
            band_regimes[f"{name}+conformal"] = regimes[name]
        bands, band_notes = _bands(bands_raw, reference_band, actual, band_regimes)
        notes.extend(band_notes)

    summary |= {
        "test_start": test_start.date().isoformat(),
        "test_end": end.date().isoformat(),
        "issue_hour": issue_hour,
        "test_windows": len(windows),
        "reference": reference,
        "output": output,
    }
    if is_gen and site is None:
        notes.append(
            "Generation without a site: the reference is 'same as yesterday', weaker than the clear-sky "
            "persistence of the benchmark. Pass site=(lat, lon) for the benchmark's reference."
        )
    bias = float(table.loc[table["forecast"] == output, "MBE"].to_numpy(float)[0])
    if abs(bias) > 0.05:
        notes.append(
            f"The output is biased by {bias:+.0%} of the mean (MBE)."
            + (
                f" `{CORRECTED}` removes it, but in the benchmark that raised the skill only for a median of "
                "~40 models; with few models it lowered it."
                if is_cons
                else ""
            )
        )
    pending = dict(base_pending)
    if weather is not None:
        pending.pop("weather (regimes B and C)")
    if bands is not None:
        pending.pop("bands (quantiles)")
    used = [m for m in models if m.card.name in regimes]
    sources, source_notes = _provenance(s, weather, used, econ_sources)
    notes.extend(source_notes)
    return Report(
        summary=summary,
        quality=quality,
        notes=notes,
        forecast=table,
        resolution=resolution,
        weather=weather_table,
        bands=bands,
        clock=clock,
        clock_weather=clock_weather,
        pending=pending,
        provenance=sources,
        diagnostics=diag,
        economics=econ,
    )


# ---------------------------------------------------------------------- pieces
_NAIVE = ("persistence_24h", "seasonal_168h", "mean_7d")


def _to_hourly(x: EnergySeries, what: str, notes: list[str]) -> EnergySeries:
    """A sub-hourly series (15-minute meter, 1-minute logger) summed into hours, with a note; anything else
    as it is (an hourly one, or a coarser one that the hourly checks refuse with their own message)."""
    if x.freq == "h" or step(x.freq) >= pd.Timedelta(hours=1):
        return x
    notes.append(
        f"The {what} came in steps of {x.freq}: summed into hours (an hour counts when at least 11/12 of it "
        "was measured); everything here is hourly."
    )
    return x.resample("h")


def _options(
    options: Mapping[str, Any] | None, func: Callable[..., Any], what: str, skip: Sequence[str]
) -> dict[str, Any]:
    """The keyword arguments of `func` named in `options`; an unknown name is an error before any work."""
    if not options:
        return {}
    allowed = [n for n in inspect.signature(func).parameters if n not in skip]
    unknown = sorted(set(options) - set(allowed))
    if unknown:
        raise ValueError(f"Unknown {what} {unknown}; the options are {allowed}")
    return dict(options)


_PROVENANCE_SHOWN = ("role", "name", "license", "sends_data", "source", "citation", "retrieved", "conditions")


def _diagnostics_defaults_note(diag: Diagnosis, knobs: diagnostics._Knobs) -> list[str]:
    """One note when the diagnostics ran with the settings chosen on the project's own sites (the
    change-point penalty, the clear-day rule): elsewhere they are an assumption, and the person should
    know."""
    if diag.index.empty:  # no clear-day index: neither setting shaped a result
        return []
    default = diagnostics._DEFAULT
    plants = "two plants in Parana (Brazil)"
    used = []
    if knobs.penalty == default.penalty:
        used.append(
            f"the change-point penalty ({default.penalty:g} x the BIC's) was chosen on {plants} and ten PV "
            "houses in Ireland"
        )
        plants = "the same plants"
    clear = ("clear_window_days", "clear_quantile", "clear_ratio")
    if all(getattr(knobs, c) == getattr(default, c) for c in clear):
        used.append(f"the clear-day rule was set by hand on {plants}")
    if not used:
        return []
    it = "they are assumptions" if len(used) > 1 else "it is an assumption"
    return [
        f"Diagnostics: {', and '.join(used)}; elsewhere {it} (`analyze(diagnostics_options=...)` changes "
        f"{'them' if len(used) > 1 else 'it'})."
    ]


_Entry = tuple[str, str, Provenance, bool]  # role, name, provenance, sends the data out


def _provenance(
    s: EnergySeries,
    weather: pd.DataFrame | None,
    models: Sequence[Forecaster],
    extra: Sequence[_Entry] = (),
) -> tuple[pd.DataFrame, list[str]]:
    """One row per input of the analysis (the series, the weather when given, each model that ran, and the
    `extra` inputs: the second series and the tariff of the economics section) with its source and licence,
    and the notes the app must show: unknown licences, non-commercial terms and models that send the data
    out. The built-in naive forecasts are rules of this library and need no row."""
    undeclared = Provenance(source="not declared")
    entries: list[_Entry] = [("series", s.quantity, s.provenance or undeclared, False)]
    if weather is not None:
        entries.append(("weather", "weather forecast", provenance_of(weather) or undeclared, False))
    for m in models:
        c = m.card
        card = Provenance(source=c.source or "not declared", license=c.license)
        entries.append(("model", c.name, card, c.sends_data))
    entries += list(extra)
    rows = _provenance_rows(entries)
    notes = []
    unknown = [f"{role} ({name})" for role, name, p, _ in entries if not p.license_known]
    if unknown:
        notes.append(
            f"Licence unknown for: {', '.join(unknown)}. Find it out before sharing or publishing these "
            "results (`EnergySeries.from_dataframe(provenance=...)`; `prosumer.provenance.attach` for a "
            "weather frame)."
        )
    for role, name, p, _ in entries:
        if p.non_commercial:
            notes.append(f"The {role} {name!r} is for non-commercial use only ({p.license}; {p.notes}).")
    out = [name for _, name, _, sends in entries if sends]
    if out:
        notes.append(f"These models send the series outside this machine: {', '.join(out)} (model card).")
    return pd.DataFrame(rows), notes


def _provenance_rows(entries: Sequence[_Entry]) -> list[dict[str, Any]]:
    return [
        {
            "role": role,
            "name": name,
            "license": p.license,
            "sends_data": sends,
            "source": p.source,
            "citation": p.citation,
            "url": p.url,
            "retrieved": p.retrieved or "",
            "conditions": p.notes,
        }
        for role, name, p, sends in entries
    ]


def _economics(
    series: EnergySeries,
    pricing: Tariff | Pricing | None,
    consumption: EnergySeries | None,
    generation: EnergySeries | None,
) -> tuple[EconomicsSection | None, list[_Entry], str | None]:
    """The bill section, the provenance entries it adds (the second series, the tariff) and a note when it
    was asked for but could not be made."""
    if pricing is None:
        if consumption is not None or generation is not None:
            return None, [], "`consumption=` and `generation=` are used only with `economics=`: ignored."
        return None, [], None
    p = as_pricing(pricing)
    cons: EnergySeries | None
    if series.quantity == "consumption":
        if consumption is not None:
            raise ValueError(
                "The series is the consumption: pass the PV as `generation=`, not `consumption=`"
            )
        cons, gen, other = series, generation, generation
    else:
        if generation is not None:
            raise ValueError("The series is the generation: pass the household's use as `consumption=`")
        cons, gen, other = consumption, series, consumption
    for x, want in ((cons, "consumption"), (gen, "generation")):
        if x is not None and x.quantity != want:
            raise ValueError(f"The {want} series has quantity {x.quantity!r}")
    if cons is None:
        return (
            None,
            [],
            "Economics left out: the bill needs the household's consumption (`consumption=`); the "
            "generation alone says what the PV made, not what the household paid.",
        )
    try:
        b = p.bill(cons, gen)
    except (ValueError, NotImplementedError) as e:
        return None, [], f"Economics left out: {e}"
    entries: list[_Entry] = []
    if other is not None:
        entries.append(
            ("series", other.quantity, other.provenance or Provenance(source="not declared"), False)
        )
    entries += [("tariff", name, prov, False) for name, prov in p.sources()]
    notes = list(b.notes)
    totals = b.totals()
    if (totals["complete_months"] == 0).any():
        notes.append(
            "No month with every hour measured for some site: its expected monthly bill "
            "(`mean_month`) is not given."
        )
    section = EconomicsSection(
        tariff=p.describe(),
        scheme=b.scheme,
        currency=b.currency,
        monthly=b.monthly,
        by_block=b.by_block,
        totals=totals,
        notes=notes,
        provenance=pd.DataFrame(_provenance_rows([e for e in entries if e[0] == "tariff"])),
    )
    return section, entries, None


def _naive_forecasts(windows: list[Window], site: tuple[float, float] | None, reference: str) -> pd.DataFrame:
    """Forecasts that need no training, from each window's history (causally filled, `CONTEXT` hours).

    Target hour k of a window sits at `issue + k`; the same hour d days earlier is history position
    `CONTEXT - 24 d + k`.
    """
    parts = []
    for w in windows:
        n, x = len(w.timestamps), w.history
        k = np.arange(n)
        lag = {d: x[CONTEXT - 24 * d + k] for d in range(1, 8)}
        f = {
            "unique_id": w.unique_id,
            "ds": w.timestamps,
            "persistence_24h": lag[1],
            "seasonal_168h": lag[7],
            "mean_7d": np.mean([lag[d] for d in range(1, 8)], axis=0),
        }
        if reference == "clear_sky_persistence":
            assert site is not None
            past = w.timestamps[0] - pd.Timedelta(hours=24) + pd.to_timedelta(np.arange(H), unit="h")
            cs_past = physics.clear_sky_ghi(pd.DatetimeIndex(past), *site)
            cs_now = physics.clear_sky_ghi(w.timestamps, *site)
            total = cs_past.sum()
            kc = float(x[-H:].sum()) / float(total) if total > 0 else 0.0
            f["clear_sky_persistence"] = cs_now * kc
            f["_sun"] = cs_now > 0
        parts.append(pd.DataFrame(f))
    fc = pd.concat(parts, ignore_index=True)
    return fc


def _before(task: DayAhead, test_start: pd.Timestamp, days: int) -> DayAhead:
    """The same task over the `days` days before the test, as one fold fitted before them."""
    return DayAhead(
        task.series,
        test_start=test_start - pd.Timedelta(days=days),
        test_end=test_start - pd.Timedelta(days=1),
        refit_days=days,
        context=task.context,
        min_history=task.min_history,
        issue_hour=task.issue_hour,
        covariates=task.covariates,
    )


def _calibration_bands(model: Probabilistic, task: DayAhead, test_start: pd.Timestamp) -> pd.DataFrame:
    """The model's bands (and point, `yhat`) over the `CALIBRATION_DAYS` days before the test (one fold,
    fitted before them): the errors the conformal recalibration learns from, as a running system would have
    them."""
    return rolling_quantiles(model, _before(task, test_start, CALIBRATION_DAYS))


def _past_naive(task: DayAhead, test_start: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """The naive forecasts over the `BIAS_DAYS` before the test, one frame per forecast."""
    windows = _before(task, test_start, BIAS_DAYS).windows()
    if not windows:
        return {}
    fc = _naive_forecasts(windows, None, "persistence_24h")
    return {n: fc[["unique_id", "ds", n]].rename(columns={n: "yhat"}) for n in _NAIVE}


def _corrected_median(
    fc: pd.DataFrame,
    past: dict[str, pd.DataFrame],
    in_median: list[str],
    frame: pd.DataFrame,
    test_start: pd.Timestamp,
) -> pd.DataFrame:
    """Consumption: the median times the actual/forecast factor of its previous `BIAS_DAYS` days
    (`postprocessing.correct_bias`), a row next to the output, not the output. The days before the test use
    the median of the same forecasts there (those that have it), so the first test day is corrected too.

    Why not the output (pilot 2026-10-12 on the benchmark's saved forecasts, houses' consumption, regime A):
    it removes the bias of every median (MBE within 1%), but it lifts the skill only for the median of ~40
    models (+0.194 -> +0.209, the 2026-10-09 pilot). For the medians this library runs it costs skill: naive
    only +0.145 -> +0.113; + LightGBM +0.192 -> +0.175; + TiRex-2, Toto-2.0 and Chronos-2 +0.193 -> +0.186;
    all of them +0.200 -> +0.195. A per-house factor of 14 days is noisy, and only a strongly biased
    median (foundation models, -20%) has more bias to remove than noise to add."""
    have = [n for n in in_median if n in past]
    median = fc[["unique_id", "ds", OUTPUT]].rename(columns={OUTPUT: "yhat"})
    if have:
        p = past[have[0]].rename(columns={"yhat": have[0]})
        for n in have[1:]:
            p = p.merge(past[n].rename(columns={"yhat": n}), on=["unique_id", "ds"], how="outer")
        p = p.assign(yhat=p[have].median(axis=1))[["unique_id", "ds", "yhat"]]
        median = pd.concat([p[p["ds"] < test_start], median], ignore_index=True)
    actual = frame.loc[frame["valid"], ["unique_id", "ds", "y"]]
    out = correct_bias(median, actual, quantity="consumption", days=BIAS_DAYS)
    out = out[out["ds"] >= test_start].rename(columns={"yhat": CORRECTED})
    return fc.merge(out[["unique_id", "ds", CORRECTED]], on=["unique_id", "ds"], how="left")


def _production_hours(
    s: EnergySeries, generation: bool, site: tuple[float, float] | None, before: pd.Timestamp
) -> Any:
    """Hours a band is recalibrated on, known before the test: all for consumption; for generation the sun
    hours (with a site) or the hours of the profile before `before` (night bands are ~0 and their errors
    would fill the calibration with zeros)."""

    def hours(keys: pd.DataFrame) -> np.ndarray | None:
        if not generation:
            return None
        if site is not None:
            return _sun(keys, site, "ds")
        past = s.frame.loc[s.frame["valid"] & (s.frame["ds"] < before)]
        return metrics.evaluated_mask(keys.assign(y=0.0), "profile", profile=past).to_numpy(bool)

    return hours


def _bands(
    raw: dict[str, pd.DataFrame], reference: pd.DataFrame, actual: pd.DataFrame, regimes: dict[str, str]
) -> tuple[pd.DataFrame, list[str]]:
    """Score every band and the 14-day reference on the same evaluated hours (those where all are finite).
    Negative quantiles are cut at 0, as the point forecasts of the benchmark."""
    j = actual[["unique_id", "ds", "y"]]
    for name, q in [("empirical_14d", reference), *raw.items()]:
        renamed = {c: f"{name}|{c}" for c in q.columns if c.startswith("q")}
        j = j.merge(q.rename(columns=renamed), on=["unique_id", "ds"])
    j = j.dropna()
    if j.empty:
        return pd.DataFrame(), ["Bands left out: no evaluated hour where every band exists."]
    y = j["y"].to_numpy()
    scores = {}
    for name in ["empirical_14d", *raw]:
        cols = [c for c in j.columns if c.startswith(f"{name}|q")]
        levels = [float(c.split("|q")[1]) for c in cols]
        scores[name] = metrics.band_scores(y, j[cols].clip(lower=0).to_numpy(), levels)
    base = scores["empirical_14d"]["CRPS"]
    rows, notes = [], []
    for name in [*raw, "empirical_14d"]:
        sc = scores[name]
        c80, c60 = sc.get("coverage_80", np.nan), sc.get("coverage_60", np.nan)
        calibrated = bool(abs(c80 - 0.8) <= 0.05 and abs(c60 - 0.6) <= 0.05)
        rows.append(
            {
                "source": name,
                "regime": regimes.get(name, "A"),
                "coverage_80": c80,
                "coverage_60": c60,
                "width_80": sc.get("width_80", np.nan),
                "CRPS": sc["CRPS"],
                "CRPS_skill": 1 - sc["CRPS"] / base if base > 0 else np.nan,
                "calibrated": calibrated,
                "hours": int(sc["n"]),
            }
        )
    table = pd.DataFrame(rows)
    ok = dict(zip(table["source"], table["calibrated"], strict=True))
    for r in rows:
        name = str(r["source"])
        if name == "empirical_14d" or r["calibrated"]:
            continue
        fixed = ok.get(f"{name}+conformal", False)
        notes.append(
            f"The band of {name} is not calibrated (80% band: {r['coverage_80']:.0%} of the hours, 60%: "
            f"{r['coverage_60']:.0%}): "
            + (f"use {name}+conformal, which is." if fixed else "do not read it as a probability.")
        )
    return table, notes


def _weather_frame(weather: pd.DataFrame, series_ids: list[str]) -> pd.DataFrame:
    """The weather with a `unique_id` per series (repeated when it came without one) and `ds` aware."""
    if "ds" not in weather.columns:
        raise ValueError("weather needs a `ds` column (see io.open_meteo.wide)")
    if getattr(weather["ds"].dt, "tz", None) is None:
        raise ValueError("weather.ds must carry a time zone")
    if "unique_id" in weather.columns:
        return weather.assign(unique_id=weather["unique_id"].astype(str))
    return pd.concat([weather.assign(unique_id=u) for u in series_ids], ignore_index=True)


def _weather_coverage(w: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Per GHI column (each model, then the mean): first and last hour with a value, fraction in [start,
    end]."""
    cols = [c for c in w.columns if c.startswith("ghi_") and c != "ghi_spread"]
    one = w.drop_duplicates("ds").set_index("ds").sort_index()
    inside = one.loc[(one.index >= start) & (one.index <= end)]
    expected = int((end - start) / pd.Timedelta(hours=1)) + 1
    rows = []
    for c in cols:
        ok = inside.index[inside[c].notna()]
        rows.append(
            {
                "source": c.removeprefix("ghi_"),
                "first": ok.min() if len(ok) else pd.NaT,
                "last": ok.max() if len(ok) else pd.NaT,
                "fraction": len(ok) / expected,
            }
        )
    return pd.DataFrame(rows)


def _weather_linear(
    fc: pd.DataFrame,
    w: pd.DataFrame,
    s: EnergySeries,
    site: tuple[float, float] | None,
    test_start: pd.Timestamp,
) -> tuple[pd.DataFrame, str | None]:
    """Regime C for generation: y = a + b x `ghi_mean`, per series, on the sun hours before the test."""
    x_col = "ghi_mean" if "ghi_mean" in w.columns else "ghi"
    if x_col not in w.columns:
        return fc, "Weather forecast without GHI (`ghi_mean` or `ghi`): no regime C forecast."
    data = s.frame.loc[s.frame["valid"], ["unique_id", "ds", "y"]].merge(
        w[["unique_id", "ds", x_col]], on=["unique_id", "ds"]
    )
    target = fc[["unique_id", "ds"]].merge(w[["unique_id", "ds", x_col]], on=["unique_id", "ds"], how="left")
    data["_sun"] = _sun(data, site, x_col)
    target["_sun"] = _sun(target, site, x_col)
    yhat = np.full(len(target), np.nan)
    train = data[(data["ds"] < test_start) & data["_sun"] & data[x_col].notna()]
    for uid, g in train.groupby("unique_id"):
        if len(g) < 48:
            continue
        a, b = np.linalg.lstsq(np.c_[np.ones(len(g)), g[x_col]], g["y"].to_numpy(), rcond=None)[0]
        m = (target["unique_id"] == uid).to_numpy()
        x = target.loc[m, x_col].to_numpy(float)
        # night (no sun) is 0; a sun hour without a forecast stays NaN: a gap is not a zero
        yhat[m] = np.where(target.loc[m, "_sun"], np.clip(a + b * x, 0.0, None), 0.0)
    if np.isnan(yhat).all():
        return fc, "Too few sun hours with a weather forecast before the test (48 per series): no regime C."
    return fc.assign(weather_linear=yhat), None


def _sun(x: pd.DataFrame, site: tuple[float, float] | None, x_col: str) -> np.ndarray:
    """Sun hours: clear sky > 0 with a site; without one, forecast GHI > 0 or missing (unknown is not
    night)."""
    if site is None:
        return (x[x_col].isna() | (x[x_col] > 0)).to_numpy()
    ds = pd.DatetimeIndex(x["ds"])
    uniq = ds.unique()
    cs = pd.Series(physics.clear_sky_ghi(uniq, *site), index=uniq)
    return (cs.reindex(ds).to_numpy() > 0).astype(bool)


def _evaluated(
    actual: pd.DataFrame,
    fc: pd.DataFrame,
    generation: bool,
    site: tuple[float, float] | None,
    test_start: pd.Timestamp,
) -> pd.Series:
    """Hours that count. Consumption: all. Generation: sun hours (with a site) or the training profile."""
    if not generation:
        return pd.Series(True, index=actual.index)
    if site is not None:
        sun = fc.loc[fc["_sun"], ["unique_id", "ds"]].assign(_in=True)
        m = actual[["unique_id", "ds"]].merge(sun, on=["unique_id", "ds"], how="left")
        return pd.Series(m["_in"].fillna(False).astype(bool).to_numpy(), index=actual.index)
    return metrics.evaluated_mask(actual, "profile", profile=actual[actual["ds"] < test_start])


def _quality(s: EnergySeries) -> tuple[pd.DataFrame, list[str]]:
    rows, notes = [], []
    for uid, g in s.frame.groupby("unique_id", sort=True):
        valid = g["valid"].to_numpy(bool)
        gap_runs = _runs(~valid)
        rows.append(
            {
                "series": str(uid),
                "first": g["ds"].min(),
                "last_valid": g.loc[g["valid"], "ds"].max(),
                "steps": len(g),
                "coverage": float(valid.mean()),
                "gaps": len(gap_runs),
                "longest_gap_h": max(gap_runs, default=0) * s.hours_per_step,
            }
        )
    q = pd.DataFrame(rows)
    low = q.loc[q["coverage"] < 0.95, "series"].tolist()
    if low:
        notes.append(f"Coverage below 95% in {len(low)} series: {', '.join(low)}.")
    if not s.ends_together():
        notes.append(
            "The series do not end together: any validation must cut by fold, or later folds re-emit "
            "earlier days (see `DayAhead.check_support`)."
        )
    return q, notes


def _runs(flags: np.ndarray) -> list[int]:
    """Lengths of the runs of True."""
    if not flags.any():
        return []
    padded = np.concatenate([[False], flags, [False]]).astype(int)
    d = np.diff(padded)
    return (np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).tolist()


def _records(df: pd.DataFrame | None) -> list[dict[str, Any]] | None:
    """A table as JSON-ready records (timestamps as ISO text)."""
    if df is None:
        return None
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].map(lambda t: t.isoformat())
    return [{str(k): _plain(v) for k, v in r.items()} for r in out.to_dict(orient="records")]


def _plain(v: Any) -> Any:
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, np.generic):
        return v.item()
    return v


def _table(df: pd.DataFrame) -> str:
    def cell(v: Any) -> str:
        if isinstance(v, float):
            return f"{v:.3f}"
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%d %H:%M")
        return str(v)

    head = "| " + " | ".join(map(str, df.columns)) + " |"
    rule = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])
