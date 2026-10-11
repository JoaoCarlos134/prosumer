"""Day-ahead forecasting protocol: folds, windows and regimes, in one place.

Ported from `experimentos/testes_previsao/scripts/comum.py`, the frozen version used in the v2
benchmark. The proposal's rule (section 6) is that cut-off dates, seeds and metrics live in the task,
never in the script, so this is where they live.

Task: 24 hourly values for the next day, issued at 00:00, with history up to 23:00 of the previous day.
One window per test day; no model sees the day it forecasts. `issue_hour` moves the issue time into the day
itself (pilot F2(d): the evening peak issued at 12:00 with the morning already measured); the target is then
the hours of the day from `issue_hour` to 23:00 and the history ends one hour before it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

import numpy as np
import pandas as pd

from .contracts import EnergySeries

H = 24  # horizon: the 24 hours of the next day


class Regime(StrEnum):
    """What information the model receives. Mixing regimes in one table misleads the reader.

    The gap between regimes was ~10x the difference between algorithms in the benchmark, which is why
    the regime is explicit in the type and not a loose parameter.
    """

    HISTORY = "A"  # only the series' own history
    KNOWN_WEATHER = "B"  # + the weather of the day itself: a ceiling, assumes a perfect forecast
    REAL_FORECAST = "C"  # + the weather forecast issued the day before: the operational regime


@dataclass(frozen=True, slots=True)
class Fold:
    """One fold of the rolling origin: the model is trained from scratch at its start."""

    index: int
    start: pd.Timestamp
    end: pd.Timestamp  # inclusive, 23:00 of the last day

    @property
    def days(self) -> int:
        return int((self.end.normalize() - self.start.normalize()).days) + 1


@dataclass(frozen=True, slots=True)
class Window:
    """One day to forecast: the history up to the previous day and the target timestamps.

    `history` is what a model receives: with `fill="causal"` (the default) the gaps are interpolated using
    only this window's own history, so nothing from the forecast day or later leaks in. `history_valid` keeps
    which steps were really measured, so a model that handles gaps itself (or a quality report) still sees
    them. `past_covariates` and `future_covariates` hold the covariates (regimes B and C) over the history and
    over the target hours, by column name; empty without covariates. `timestamps` has `24 - issue_hour` hours.
    """

    unique_id: str
    day: pd.Timestamp
    history: np.ndarray
    timestamps: pd.DatetimeIndex
    history_valid: np.ndarray | None = None
    past_covariates: dict[str, np.ndarray] = field(default_factory=dict)
    future_covariates: dict[str, np.ndarray] = field(default_factory=dict)


class DayAhead:
    """The task. Takes the series and the test cut-off; yields folds, days and windows.

    `refit_days` is the fold length (61 for the plants, 31 for the houses in the benchmark). The rolling
    origin exists because a single cut would pick the wrong winner: in the benchmark the ranking between
    models changes from fold to fold, even when the order between regimes does not.
    """

    def __init__(
        self,
        series: EnergySeries,
        *,
        test_start: str | pd.Timestamp,
        test_end: str | pd.Timestamp | None = None,
        refit_days: int = 61,
        context: int = 168,
        seed: int = 42,
        covariates: pd.DataFrame | None = None,
        fill: Literal["causal", "none"] = "causal",
        min_history: int | None = None,
        issue_hour: int = 0,
    ) -> None:
        """`covariates`: long frame (`unique_id`, `ds` in the series' time zone, one column per covariate).
        `fill`: "causal" interpolates the gaps of each window's history from that history alone (linear, the
        ends repeat the nearest value, a history with no valid value becomes 0), as the v2 benchmark did;
        "none" leaves NaN. `min_history`: windows with less history are skipped; default = `context` (the
        benchmark used 0: a window takes whatever history exists). `issue_hour` (0-23): hour of the forecast
        day at which the forecast is issued; 0 is the benchmark's task. Only the hours from it to 23:00 are
        forecast, and only they must be valid for the day to count as a test day."""
        if not 0 <= issue_hour < H:
            raise ValueError(f"issue_hour must be in 0-{H - 1}, not {issue_hour}")
        if refit_days < 1:
            raise ValueError("refit_days must be >= 1")
        if context < H:
            raise ValueError(f"context ({context} h) must cover at least the horizon ({H} h)")
        self.series = series.to_kwh()
        tz = self.series.tz
        self.start = pd.Timestamp(test_start, tz=tz).normalize()
        last = self.series.frame["ds"].max()
        self.end = pd.Timestamp(test_end, tz=tz).normalize() if test_end is not None else last.normalize()
        if self.end < self.start:
            raise ValueError(f"Test end ({self.end.date()}) is before its start ({self.start.date()})")
        self.refit_days = refit_days
        self.context = context
        self.seed = seed
        if fill not in ("causal", "none"):
            raise ValueError(f"fill must be 'causal' or 'none', not {fill!r}")
        self.fill = fill
        self.issue_hour = issue_hour
        self.min_history = context if min_history is None else min_history
        self.covariates = None
        if covariates is not None:
            missing = {"unique_id", "ds"} - set(covariates.columns)
            if missing:
                raise ValueError(f"covariates without columns {sorted(missing)}")
            cov = covariates.copy()
            cov["unique_id"] = cov["unique_id"].astype(str)
            if getattr(cov["ds"].dt, "tz", None) is None:
                raise ValueError("covariates.ds must carry the series' time zone (it is naive)")
            self.covariates = cov

    # ------------------------------------------------------------------ folds
    def folds(self) -> list[Fold]:
        """Consecutive folds of `refit_days`; the last one may be shorter."""
        return folds(self.start, self.end, self.refit_days)

    def fold_of(self, day: pd.Timestamp) -> Fold:
        """The fold a day belongs to. A forecast outside its fold is leakage."""
        for f in self.folds():
            if f.start <= day <= f.end:
                return f
        raise ValueError(f"{day} is outside the test period")

    # ------------------------------------------------------------------ days and windows
    def test_days(self) -> list[tuple[str, pd.Timestamp]]:
        """(series, day) pairs whose target hours (24 when issued at 00:00) are all present and valid."""
        q = self.series.frame
        in_test = q[(q["ds"] >= self.start) & (q["ds"] <= self.end + pd.Timedelta(hours=H - 1))].copy()
        in_test = in_test[in_test["ds"].dt.hour >= self.issue_hour]
        in_test["day"] = in_test["ds"].dt.normalize()
        n = H - self.issue_hour
        g = in_test.groupby(["unique_id", "day"])["valid"].agg(["sum", "size"])
        complete = g[(g["sum"] == n) & (g["size"] == n)]
        return [(str(u), pd.Timestamp(d)) for u, d in complete.index]

    def windows(self) -> list[Window]:
        """One window per test day, with up to `context` hours of history before the issue time."""
        per_series = {u: g.set_index("ds") for u, g in self.series.frame.groupby("unique_id")}
        cov = (
            {}
            if self.covariates is None
            else {
                u: g.drop(columns="unique_id").set_index("ds")
                for u, g in self.covariates.groupby("unique_id")
            }
        )
        out: list[Window] = []
        for uid, day in self.test_days():
            g = per_series[uid]
            issue = day + pd.Timedelta(hours=self.issue_hour)
            hist = g.loc[: issue - pd.Timedelta(hours=1)].tail(self.context)
            if len(hist) < self.min_history:
                continue  # start of the series: not enough history for this window
            valid = hist["valid"].to_numpy(dtype=bool)
            y = hist["y"].where(hist["valid"])
            if self.fill == "causal":
                # only this window's history is touched: the day forecast and later never enter the
                # interpolation
                y = y.interpolate(limit_direction="both").fillna(0.0)
            past: dict[str, np.ndarray] = {}
            future: dict[str, np.ndarray] = {}
            if uid in cov:
                c = cov[uid]
                past = {k: c[k].reindex(hist.index).to_numpy() for k in c.columns}
                fut = c.loc[issue : day + pd.Timedelta(hours=H - 1)]
                future = {k: fut[k].to_numpy() for k in c.columns}
            out.append(
                Window(
                    unique_id=uid,
                    day=day,
                    history=y.to_numpy(dtype=float),
                    timestamps=pd.date_range(issue, periods=H - self.issue_hour, freq="h", tz=self.series.tz),
                    history_valid=valid,
                    past_covariates=past,
                    future_covariates=future,
                )
            )
        return out

    # ------------------------------------------------------------------ guards
    def check_support(self) -> None:
        """Raise when the series do not end together, the case that causes leakage between folds.

        It is not a data error: `casas_cons` really has one short series. But whoever generates the
        windows from the end of EACH series (as NeuralForecast's `cross_validation` does) will step back
        and re-emit days from earlier folds, with a model trained after them. The caller must cut by
        fold. See `Fold` and `fold_of`.
        """
        if not self.series.ends_together():
            ends = self.series.end_per_series()
            raise SupportError(
                "Series end at different timestamps "
                f"({ends.min()} to {ends.max()}): cut each fold by [start, end] "
                "before saving forecasts, or a later fold re-emits days of an earlier one."
            )


def folds(start: str | pd.Timestamp, end: str | pd.Timestamp, refit_days: int) -> list[Fold]:
    """Folds of the rolling origin between two days (inclusive), without needing the series.

    The model is retrained at the start of each fold with data before it; the last fold may be shorter.
    Time zone: that of `start`/`end` (naive stays naive).
    """
    if refit_days < 1:
        raise ValueError("refit_days must be >= 1")
    a, last = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    out: list[Fold] = []
    i = 1
    while a <= last:
        b = min(a + pd.Timedelta(days=refit_days - 1), last)
        out.append(Fold(index=i, start=a, end=b + pd.Timedelta(hours=H - 1)))
        a = b + pd.Timedelta(days=1)
        i += 1
    return out


def standardize_by_training(
    frame: pd.DataFrame, cutoff: pd.Timestamp, columns: list[str], *, mask_column: str | None = "valid"
) -> tuple[pd.DataFrame, dict[str, dict[str, tuple[float, float]]]]:
    """Standardize each series with the mean and deviation of its TRAINING rows only (before `cutoff`).

    Port of the benchmark's `normaliza_por_treino` (step v2): the scaler that NeuralForecast offered fitted on
    the whole frame, test included, so changing a test value changed the scale of everything. Here nothing at
    or after `cutoff` (validation and test) enters the statistics. Rows where `mask_column` is false or zero
    (gaps) are left out too; pass `mask_column=None` when there is no mask. A zero deviation becomes 1.

    Returns the standardized frame and, per series, `{column: (mean, std)}` to invert the forecast.
    Raises if a series has no finite training rows.
    """
    out, params = frame.copy(), {}
    for uid, g in frame.groupby("unique_id", sort=False):
        keep = g["ds"] < cutoff
        if mask_column is not None and mask_column in g:
            keep &= g[mask_column].astype(float) > 0
        train = g.loc[keep, columns]
        if train.empty or not np.isfinite(train.to_numpy(float)).all():
            raise ValueError(f"Empty or non-finite training rows for standardization: {uid}")
        mean = train.mean()
        std = train.std(ddof=0).replace(0, 1.0)
        out.loc[g.index, columns] = (g[columns] - mean) / std
        params[str(uid)] = {c: (float(mean[c]), float(std[c])) for c in columns}
    return out, params


class SupportError(RuntimeError):
    """The series do not share the same end; the caller must cut by fold."""
