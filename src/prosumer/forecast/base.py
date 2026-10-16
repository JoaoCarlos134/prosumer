"""The model interface, its card and the rolling-origin runner."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol

import numpy as np
import pandas as pd

from ..contracts import EnergySeries
from ..protocol import DayAhead, Regime, Window


@dataclass(frozen=True, slots=True)
class ModelCard:
    """What using a model implies, besides its skill."""

    name: str
    family: Literal["naive", "physics", "tree", "network", "foundation", "statistical"]
    license: str  # of the weights/code that run, e.g. "MIT", "Apache-2.0", "CC-BY-NC-4.0"
    device: Literal["cpu", "gpu", "cpu or gpu", "remote"]
    sends_data: bool  # True when the series leaves the machine (a paid API)
    regimes: tuple[Regime, ...]  # which information it can use
    trains: bool  # False: zero-shot or rule; nothing is fitted
    source: str = ""  # paper or package


class Forecaster(Protocol):
    """A day-ahead model. `fit` sees only data strictly before `cutoff`; `predict` returns one row per window,
    as many columns as the window's target hours."""

    card: ModelCard

    def fit(
        self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None
    ) -> None: ...

    def predict(self, windows: list[Window]) -> np.ndarray: ...


def rolling_forecast(model: Forecaster, task: DayAhead) -> pd.DataFrame:
    """Forecast every window of `task` with the rolling origin: at the start of each fold the model is fitted
    from scratch on the series (and covariates) before that day, then forecasts the windows of the fold.

    The cut is made here, not trusted to the model: `fit` receives the series truncated at the fold start, so
    a model that forgets to respect `cutoff` still cannot see the test. Returns `unique_id`, `ds`, `yhat`.
    """
    windows = task.windows()
    out = []
    for fold in task.folds():
        inside = [w for w in windows if fold.start <= w.day <= fold.end]
        if not inside:
            continue
        # covariates go whole: in C they are forecasts issued before each day, in B the declared ceiling
        model.fit(_before(task.series, fold.start), fold.start, task.covariates)
        pred = np.asarray(model.predict(inside), dtype=float)
        if pred.shape[0] != len(inside):
            raise ValueError(f"{model.card.name}: {pred.shape[0]} rows for {len(inside)} windows")
        for w, p in zip(inside, pred, strict=True):
            n = len(w.timestamps)
            if len(p) < n:
                raise ValueError(f"{model.card.name}: {len(p)} values for {n} target hours")
            out.append(pd.DataFrame({"unique_id": w.unique_id, "ds": w.timestamps, "yhat": p[:n]}))
    if not out:
        return pd.DataFrame(columns=["unique_id", "ds", "yhat"])
    return pd.concat(out, ignore_index=True)


class Probabilistic(Forecaster, Protocol):
    """A model that also gives quantiles: `predict_quantiles` -> (windows, levels, target hours), `levels`
    increasing and including 0.5, whose row is the point forecast unless the model also has
    `point_from_quantiles(q) -> (windows, target hours)` (FlowState: its point is a weighted mean of the
    quantiles, not the median)."""

    levels: tuple[float, ...]

    def predict_quantiles(self, windows: list[Window]) -> np.ndarray: ...


def rolling_quantiles(model: Probabilistic, task: DayAhead) -> pd.DataFrame:
    """`rolling_forecast` for the quantiles: one column per level (`q0.1`, ..., `q0.9`), plus `yhat` = the 0.5
    level, or the model's `point_from_quantiles` when it has one. One fit per fold serves both the point
    forecast and the band."""
    windows = task.windows()
    levels = tuple(model.levels)
    point = getattr(model, "point_from_quantiles", None)
    out = []
    for fold in task.folds():
        inside = [w for w in windows if fold.start <= w.day <= fold.end]
        if not inside:
            continue
        model.fit(_before(task.series, fold.start), fold.start, task.covariates)
        q = np.asarray(model.predict_quantiles(inside), dtype=float)
        if q.shape[:2] != (len(inside), len(levels)):
            raise ValueError(f"{model.card.name}: quantiles of shape {q.shape} for {len(inside)} windows")
        p = q[:, levels.index(0.5)] if point is None else np.asarray(point(q), dtype=float)
        for w, qq, pp in zip(inside, q, p, strict=True):
            n = len(w.timestamps)
            cols = {f"q{a:g}": qq[k, :n] for k, a in enumerate(levels)}
            out.append(pd.DataFrame({"unique_id": w.unique_id, "ds": w.timestamps, **cols, "yhat": pp[:n]}))
    if not out:
        return pd.DataFrame(columns=["unique_id", "ds", "yhat", *[f"q{a:g}" for a in levels]])
    return pd.concat(out, ignore_index=True)


def _before(series: EnergySeries, cutoff: pd.Timestamp) -> EnergySeries:
    f = series.frame
    return replace(series, frame=f.loc[f["ds"] < cutoff].reset_index(drop=True))
