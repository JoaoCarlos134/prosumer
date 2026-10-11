"""The app's single call: `analyze(series) -> Report`.

The TCC app (last step of the plan) receives the user's data and returns a complete analysis. This module
defines that entry point now, while the library is still small, because it fixes what each module must hand
back: a section of the report, with numbers and plain-language notes. Today it covers what the library can
already do without training anything:

- **quality**: coverage, gaps and the series that end on different dates (the leakage case of the benchmark);
- **forecast check**: the day-ahead task of the benchmark (`DayAhead`) on the last `test_days` of the data,
  with the naive forecasts that need no training (same as yesterday, same day last week, mean of the last 7
  days) and their MEDIAN as the output (the library never picks "the best model": section 5c of the proposal),
  scored against the benchmark's reference, with a day-bootstrap CI and the metrics at several resolutions.

The sections that need modules not written yet (weather, trained and foundation models, diagnostics,
economics) are listed in `Report.pending`, so the app can show what is missing instead of silently
leaving it out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from . import metrics, physics
from .contracts import EnergySeries
from .protocol import DayAhead, H, Window

CONTEXT = 168  # one week of history: the longest naive forecast looks 7 days back
OUTPUT = "median"

PENDING = {
    "weather (regimes B and C)": "needs the `io` module (Open-Meteo with several weather models): step E2",
    "trained and foundation models": "needs the `forecast` module (adapters with metadata): step E2",
    "bands (quantiles)": "`metrics.band_scores` exists; the quantile sources come with `forecast`: step E2",
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
    resolution: pd.DataFrame | None = None  # the output (median) at each resolution
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
            return [{k: _plain(v) for k, v in r.items()} for r in out.to_dict(orient="records")]

        return {
            "summary": {k: _plain(v) for k, v in self.summary.items()},
            "quality": records(self.quality),
            "notes": list(self.notes),
            "forecast": records(self.forecast),
            "resolution": records(self.resolution),
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
        if self.notes:
            lines += ["", "## Notes", "", *[f"- {n}" for n in self.notes]]
        if self.forecast is not None:
            lines += [
                "",
                "## Day-ahead forecast check",
                "",
                f"Test: {s['test_start']} to {s['test_end']}, issued at {s['issue_hour']:02d}:00, "
                f"{s['test_windows']} series-days. Skill against `{s['reference']}` (0 = same as it). "
                f"Output: the {OUTPUT} of the forecasts.",
                "",
                _table(self.forecast),
            ]
        if self.resolution is not None:
            lines += ["", f"### The output ({OUTPUT}) at several resolutions", "", _table(self.resolution)]
        lines += ["", "## Not available yet", "", *[f"- **{k}**: {v}" for k, v in self.pending.items()]]
        return "\n".join(lines) + "\n"


def analyze(
    series: EnergySeries,
    *,
    site: tuple[float, float] | None = None,
    test_days: int = 28,
    issue_hour: int = 0,
    levels: dict[str, metrics.Level] | None = None,
) -> Report:
    """Quality and a day-ahead forecast check of `series`, as one report.

    `site`: (latitude, longitude) of a generation series. With it the reference is clear-sky persistence and
    only the hours with sun count, as in the benchmark's plants; without it the reference is "same as
    yesterday" and the hours count by the training profile. `test_days`: the last days of the data used as the
    test. `issue_hour`: as in `DayAhead` (12 = the evening issued at noon). `levels`: resolutions of
    `metrics.by_resolution` (default: hour, day/night, evening peak, day; `metrics.by_blocks` for a tariff).
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

    first = frame["ds"].min().normalize()
    if test_start - first < pd.Timedelta(hours=CONTEXT):
        notes.append(
            f"Forecast check skipped: it needs {CONTEXT // 24} days of history "
            f"before the {test_days} test days."
        )
        return Report(summary=summary, quality=quality, notes=notes)

    task = DayAhead(
        s, test_start=test_start, test_end=end, refit_days=test_days, context=CONTEXT, issue_hour=issue_hour
    )
    windows = task.windows()
    if not windows:
        notes.append("Forecast check skipped: no test day has all its target hours measured.")
        return Report(summary=summary, quality=quality, notes=notes)

    generation = s.quantity == "generation"
    reference = "clear_sky_persistence" if generation and site is not None else "persistence_24h"
    fc = _naive_forecasts(windows, site, reference)
    actual = frame.loc[frame["valid"], ["unique_id", "ds", "y"]]
    keep = _evaluated(actual, fc, generation, site, test_start)
    actual = actual.loc[keep]
    ref = fc[["unique_id", "ds", reference]].rename(columns={reference: "yhat"})
    rows = []
    aligned_output = aligned_ref = None
    for name in [OUTPUT, *[c for c in _NAIVE if c in fc.columns]]:
        m, r = metrics.align(fc[["unique_id", "ds", name]].rename(columns={name: "yhat"}), actual, ref)
        row = {"forecast": name, "skill": metrics.skill(m, r)}
        try:
            row["skill_ci_low"], row["skill_ci_high"] = metrics.skill_ci95(m, r)
        except ValueError:
            row["skill_ci_low"] = row["skill_ci_high"] = float("nan")
        mm = metrics.metrics(m)
        row.update(nRMSE=mm["nRMSE"], MBE=mm["MBE"], R2=mm["R2"], R2_daily=mm["R2_daily"])
        rows.append(row)
        if name == OUTPUT:
            aligned_output, aligned_ref = m, r
    if reference not in _NAIVE:
        m, r = metrics.align(ref, actual, ref)
        mm = metrics.metrics(m)
        rows.append(
            {"forecast": reference, "skill": 0.0, "skill_ci_low": 0.0, "skill_ci_high": 0.0}
            | {k: mm[k] for k in ("nRMSE", "MBE", "R2", "R2_daily")}
        )
    table = pd.DataFrame(rows)
    assert aligned_output is not None and aligned_ref is not None
    resolution = metrics.by_resolution(aligned_output, aligned_ref, levels)

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
    bias = float(table.set_index("forecast").loc[OUTPUT, "MBE"])
    if abs(bias) > 0.05:
        notes.append(f"The output is biased by {bias:+.0%} of the mean (MBE).")
    return Report(summary=summary, quality=quality, notes=notes, forecast=table, resolution=resolution)


# ---------------------------------------------------------------------- pieces
_NAIVE = ("persistence_24h", "seasonal_168h", "mean_7d")


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
            kc = x[-H:].sum() / total if total > 0 else 0.0
            f["clear_sky_persistence"] = cs_now * kc
            f["_sun"] = cs_now > 0
        parts.append(pd.DataFrame(f))
    fc = pd.concat(parts, ignore_index=True)
    fc[OUTPUT] = fc[list(_NAIVE)].median(axis=1)
    return fc


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
