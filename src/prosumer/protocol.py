"""Day-ahead forecasting protocol: folds, windows and regimes, in one place.

Ported from `experimentos/testes_previsao/scripts/comum.py`, the frozen version used in the v2
benchmark. The proposal's rule (section 6) is that cut-off dates, seeds and metrics live in the task,
never in the script, so this is where they live.

Task: 24 hourly values for the next day, issued at 00:00, with history up to 23:00 of the previous day.
One window per test day; no model sees the day it forecasts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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
    """One day to forecast: the history up to the previous day and the target timestamps."""

    unique_id: str
    day: pd.Timestamp
    history: np.ndarray
    timestamps: pd.DatetimeIndex


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
    ) -> None:
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

    # ------------------------------------------------------------------ folds
    def folds(self) -> list[Fold]:
        """Consecutive folds of `refit_days`; the last one may be shorter."""
        out: list[Fold] = []
        a = self.start
        i = 1
        while a <= self.end:
            b = min(a + pd.Timedelta(days=self.refit_days - 1), self.end)
            out.append(Fold(index=i, start=a, end=b + pd.Timedelta(hours=H - 1)))
            a = b + pd.Timedelta(days=1)
            i += 1
        return out

    def fold_of(self, day: pd.Timestamp) -> Fold:
        """The fold a day belongs to. A forecast outside its fold is leakage."""
        for f in self.folds():
            if f.start <= day <= f.end:
                return f
        raise ValueError(f"{day} is outside the test period")

    # ------------------------------------------------------------------ days and windows
    def test_days(self) -> list[tuple[str, pd.Timestamp]]:
        """(series, day) pairs with all 24 hours present and valid inside the test."""
        q = self.series.frame
        in_test = q[(q["ds"] >= self.start) & (q["ds"] <= self.end + pd.Timedelta(hours=H - 1))].copy()
        in_test["day"] = in_test["ds"].dt.normalize()
        g = in_test.groupby(["unique_id", "day"])["valid"].agg(["sum", "size"])
        complete = g[(g["sum"] == H) & (g["size"] == H)]
        return [(str(u), pd.Timestamp(d)) for u, d in complete.index]

    def windows(self) -> list[Window]:
        """One window per test day, with `context` hours of history before the day."""
        per_series = {u: g.set_index("ds") for u, g in self.series.frame.groupby("unique_id")}
        out: list[Window] = []
        for uid, day in self.test_days():
            g = per_series[uid]
            hist = g.loc[: day - pd.Timedelta(hours=1)].tail(self.context)
            if len(hist) < self.context:
                continue  # start of the series: not enough history for this window
            y = hist["y"].to_numpy(dtype=float)
            out.append(
                Window(
                    unique_id=uid,
                    day=day,
                    history=y,
                    timestamps=pd.date_range(day, periods=H, freq="h", tz=self.series.tz),
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


class SupportError(RuntimeError):
    """The series do not share the same end; the caller must cut by fold."""
