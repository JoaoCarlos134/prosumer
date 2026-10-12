"""The app's single call: `analyze(series) -> Report`.

The TCC app (last step of the plan) receives the user's data and returns a complete analysis. This module
defines that entry point now, while the library is still small, because it fixes what each module must hand
back: a section of the report, with numbers and plain-language notes. Today it covers what the library can
already do without training anything:

- **quality**: coverage, gaps and the series that end on different dates (the leakage case of the benchmark);
  for generation with a site, the clock checked against the sun (`quality.clock_offset`);
- **forecast check**: the day-ahead task of the benchmark (`DayAhead`) on the last `test_days` of the data,
  with the naive forecasts that need no training (same as yesterday, same day last week, mean of the last 7
  days) and their MEDIAN as the output (the library never picks "the best model": section 5c of the proposal),
  scored against the benchmark's reference, with a day-bootstrap CI and the metrics at several resolutions.

Every report also lists its inputs (`Report.provenance`: the series, the weather, each model) with source,
licence and citation, and notes what has no known licence, is for non-commercial use only or sends the data
out, so the app can say what an analysis used and under what terms.

The sections that need modules not written yet (weather, trained and foundation models, diagnostics,
economics) are listed in `Report.pending`, so the app can show what is missing instead of silently
leaving it out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd

from . import metrics, physics
from .contracts import EnergySeries
from .forecast import EmpiricalQuantiles, Forecaster, Probabilistic, rolling_forecast, rolling_quantiles
from .postprocessing import conformal_quantiles
from .protocol import DayAhead, H, Regime, Window
from .provenance import Provenance
from .provenance import of as provenance_of
from .quality import clock_notes, clock_offset

CONTEXT = 168  # one week of history: the longest naive forecast looks 7 days back
OUTPUT = "median"
CALIBRATION_DAYS = 28  # forecasts before the test that recalibrate each band (conformal)

PENDING = {
    "weather (regimes B and C)": "pass `weather=io.open_meteo.wide(...)` (Open-Meteo, several models)",
    "trained and foundation models": "needs the `forecast` module (adapters with metadata): step E2",
    "bands (quantiles)": "pass a model with quantiles, e.g. `models=[forecast.LightGBMQuantile()]`",
    "diagnostics": "soiling, string faults, shading: step E4",
    "economics": "time-of-use tariffs and the Brazilian module: step E6",
}


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
    # where each input came from and its licence: the series, the weather and each model (see `_provenance`)
    provenance: pd.DataFrame | None = None
    pending: dict[str, str] = field(default_factory=lambda: dict(PENDING))

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly version (timestamps as ISO text, tables as lists of records)."""

        def records(df: pd.DataFrame | None) -> list[dict[str, Any]] | None:
            if df is None:
                return None
            out = df.copy()
            for c in out.columns:
                if pd.api.types.is_datetime64_any_dtype(out[c]):
                    out[c] = out[c].map(lambda t: t.isoformat())
            return [{str(k): _plain(v) for k, v in r.items()} for r in out.to_dict(orient="records")]

        return {
            "summary": {k: _plain(v) for k, v in self.summary.items()},
            "quality": records(self.quality),
            "notes": list(self.notes),
            "forecast": records(self.forecast),
            "resolution": records(self.resolution),
            "weather": records(self.weather),
            "bands": records(self.bands),
            "clock": records(self.clock),
            "provenance": records(self.provenance),
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
                "forecast issued the day before.",
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
    """
    if test_days < 2:
        raise ValueError("test_days must be >= 2: the confidence interval resamples days")
    s = series.to_kwh()
    if s.freq != "h":
        raise ValueError(f"The day-ahead check needs an hourly series, not freq={s.freq!r}; resample first")
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
    clock = None
    if s.quantity == "generation" and site is not None:
        clock = clock_offset(s, site)
        notes.extend(clock_notes(clock))

    first = frame["ds"].min().normalize()
    if test_start - first < pd.Timedelta(hours=CONTEXT):
        notes.append(
            f"Forecast check skipped: it needs {CONTEXT // 24} days of history "
            f"before the {test_days} test days."
        )
        sources, source_notes = _provenance(s, None, ())
        return Report(
            summary=summary, quality=quality, notes=notes + source_notes, clock=clock, provenance=sources
        )

    task = DayAhead(
        s, test_start=test_start, test_end=end, refit_days=test_days, context=CONTEXT, issue_hour=issue_hour
    )
    windows = task.windows()
    if not windows:
        notes.append("Forecast check skipped: no test day has all its target hours measured.")
        sources, source_notes = _provenance(s, None, ())
        return Report(
            summary=summary, quality=quality, notes=notes + source_notes, clock=clock, provenance=sources
        )

    generation = s.quantity == "generation"
    reference = "clear_sky_persistence" if generation and site is not None else "persistence_24h"
    fc = _naive_forecasts(windows, site, reference)
    actual = frame.loc[frame["valid"], ["unique_id", "ds", "y"]]
    keep = _evaluated(actual, fc, generation, site, test_start)
    actual = actual.loc[keep]
    regimes = {OUTPUT: "A", **dict.fromkeys(_NAIVE, "A"), reference: "A"}
    weather_table = None
    w = None if weather is None else _weather_frame(weather, s.series)
    bands_raw: dict[str, pd.DataFrame] = {}
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
            qf = rolling_quantiles(cast(Probabilistic, model), task_m)  # one fit: point = the 0.5 level
            bands_raw[name] = qf.drop(columns="yhat")
            bands_past[name] = _calibration_bands(cast(Probabilistic, model), task_m, test_start)
            out = qf[["unique_id", "ds", "yhat"]]
        else:
            out = rolling_forecast(model, task_m)
        fc = fc.merge(out.rename(columns={"yhat": name}), on=["unique_id", "ds"], how="left")
        regimes[name] = "A" if history_only else "C"
    # the output: median of every regime A forecast (the naive ones and the A models; not the reference alone)
    in_median = [
        *_NAIVE,
        *[n for n, r in regimes.items() if r == "A" and n not in (OUTPUT, reference, *_NAIVE)],
    ]
    fc[OUTPUT] = fc[in_median].median(axis=1)
    if w is not None:
        weather_table = _weather_coverage(w, frame["ds"].min(), end + pd.Timedelta(hours=H - 1))
        if generation:
            fc, note = _weather_linear(fc, w, s, site, test_start)
            if note:
                notes.append(note)
            else:
                regimes["weather_linear"] = "C"
    # common support: every row on the hours where every forecast exists (a gap in one drops the hour for all)
    missing = fc.loc[fc[list(regimes)].isna().any(axis=1), ["unique_id", "ds"]].assign(_drop=True)
    flagged = actual.merge(missing, on=["unique_id", "ds"], how="left")["_drop"].fillna(False).to_numpy(bool)
    actual = actual.loc[~flagged]
    if flagged.any():
        notes.append(
            f"{int(flagged.sum())} test hours without a forecast from every model left out of every row."
        )
    ref = fc[["unique_id", "ds", reference]].rename(columns={reference: "yhat"})
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
                OUTPUT,
                *_NAIVE,
                *[n for n, r in regimes.items() if r == "A" and n != reference],
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
            for n in [OUTPUT, *[n for n, r in regimes.items() if r == "C"]]
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
        hours_of = _production_hours(s, generation, site, test_start - pd.Timedelta(days=CALIBRATION_DAYS))
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
    }
    if generation and site is None:
        notes.append(
            "Generation without a site: the reference is 'same as yesterday', weaker than the clear-sky "
            "persistence of the benchmark. Pass site=(lat, lon) for the benchmark's reference."
        )
    bias = float(table.loc[table["forecast"] == OUTPUT, "MBE"].to_numpy(float)[0])
    if abs(bias) > 0.05:
        notes.append(f"The output is biased by {bias:+.0%} of the mean (MBE).")
    pending = dict(PENDING)
    if weather is not None:
        pending.pop("weather (regimes B and C)")
    if bands is not None:
        pending.pop("bands (quantiles)")
    used = [m for m in models if m.card.name in regimes]
    sources, source_notes = _provenance(s, weather, used)
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
        pending=pending,
        provenance=sources,
    )


# ---------------------------------------------------------------------- pieces
_NAIVE = ("persistence_24h", "seasonal_168h", "mean_7d")
_PROVENANCE_SHOWN = ("role", "name", "license", "sends_data", "source", "citation", "retrieved", "conditions")


def _provenance(
    s: EnergySeries, weather: pd.DataFrame | None, models: Sequence[Forecaster]
) -> tuple[pd.DataFrame, list[str]]:
    """One row per input of the analysis (the series, the weather when given, each model that ran) with its
    source and licence, and the notes the app must show: unknown licences, non-commercial terms and models
    that send the data out. The built-in naive forecasts are rules of this library and need no row."""
    undeclared = Provenance(source="not declared")
    entries: list[tuple[str, str, Provenance, bool]] = [
        ("series", s.quantity, s.provenance or undeclared, False)
    ]
    if weather is not None:
        entries.append(("weather", "weather forecast", provenance_of(weather) or undeclared, False))
    for m in models:
        c = m.card
        card = Provenance(source=c.source or "not declared", license=c.license)
        entries.append(("model", c.name, card, c.sends_data))
    rows = [
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


def _calibration_bands(model: Probabilistic, task: DayAhead, test_start: pd.Timestamp) -> pd.DataFrame:
    """The model's bands over the `CALIBRATION_DAYS` days before the test (one fold, fitted before them): the
    errors the conformal recalibration learns from, as a running system would have them."""
    start = test_start - pd.Timedelta(days=CALIBRATION_DAYS)
    past = DayAhead(
        task.series,
        test_start=start,
        test_end=test_start - pd.Timedelta(days=1),
        refit_days=CALIBRATION_DAYS,
        context=task.context,
        min_history=task.min_history,
        issue_hour=task.issue_hour,
        covariates=task.covariates,
    )
    return rolling_quantiles(model, past).drop(columns="yhat")


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
