"""Forecasts that need no training: the benchmark's references."""

from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import pandas as pd

from ..contracts import EnergySeries
from ..protocol import Regime, Window
from .base import ModelCard

Kind = Literal["persistence_24h", "seasonal_168h", "mean_7d"]
_LAGS: dict[str, list[int]] = {"persistence_24h": [1], "seasonal_168h": [7], "mean_7d": [1, 2, 3, 4, 5, 6, 7]}


class Naive:
    """Same hour yesterday (`persistence_24h`), a week ago (`seasonal_168h`) or the mean of the last 7 days.

    Reads the window's history (causally filled). Target hour k of a window sits at `issue + k`; the same hour
    d days earlier is history position `len(history) - 24 d + k`. It needs 24 d hours of history; with less
    the value is NaN.
    """

    def __init__(self, kind: Kind = "persistence_24h") -> None:
        if kind not in _LAGS:
            raise ValueError(f"kind must be one of {sorted(_LAGS)}, not {kind!r}")
        self.kind = kind
        self.card = ModelCard(
            name=kind,
            family="naive",
            license="n/a",
            device="cpu",
            sends_data=False,
            regimes=(Regime.HISTORY,),
            trains=False,
        )

    def fit(self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None) -> None:
        """Nothing to fit."""

    def predict(self, windows: list[Window]) -> np.ndarray:
        n = max(len(w.timestamps) for w in windows)
        out = np.full((len(windows), n), np.nan)
        for i, w in enumerate(windows):
            k = np.arange(len(w.timestamps))
            lagged = []
            for d in _LAGS[self.kind]:
                pos = len(w.history) - 24 * d + k
                v = np.full(len(k), np.nan)
                ok = pos >= 0
                v[ok] = w.history[pos[ok]]
                lagged.append(v)
            out[i, : len(k)] = np.mean(lagged, axis=0)
        return out


class EmpiricalQuantiles:
    """The naive band: quantiles of the same hour over the last `days` days (at least `min_days` measured).

    It is the reference a band must beat (pilot F2(c)): causal, needs no training, and calibrated only as far
    as the recent past looks like tomorrow. Reads the RAW history (gaps are left out, not filled), so the
    window needs `24 * days` hours of history. `predict` is its median.
    """

    def __init__(
        self,
        levels: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
        *,
        days: int = 14,
        min_days: int = 7,
    ) -> None:
        if 0.5 not in levels or sorted(levels) != list(levels):
            raise ValueError("levels must be increasing and include 0.5")
        self.levels, self.days, self.min_days = tuple(levels), days, min_days
        self.card = ModelCard(
            name=f"empirical_{days}d",
            family="naive",
            license="n/a",
            device="cpu",
            sends_data=False,
            regimes=(Regime.HISTORY,),
            trains=False,
        )

    def fit(self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None) -> None:
        """Nothing to fit."""

    def predict(self, windows: list[Window]) -> np.ndarray:
        return self.predict_quantiles(windows)[:, self.levels.index(0.5), :]

    def predict_quantiles(self, windows: list[Window]) -> np.ndarray:
        """Shape (windows, levels, target hours)."""
        n = max(len(w.timestamps) for w in windows)
        out = np.full((len(windows), len(self.levels), n), np.nan)
        for i, w in enumerate(windows):
            raw = w.history if w.history_valid is None else np.where(w.history_valid, w.history, np.nan)
            k = np.arange(len(w.timestamps))
            lags = np.full((self.days, len(k)), np.nan)
            for d in range(1, self.days + 1):
                pos = len(raw) - 24 * d + k
                ok = pos >= 0
                lags[d - 1, ok] = raw[pos[ok]]
            enough = np.sum(np.isfinite(lags), axis=0) >= self.min_days
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN hours: masked by `enough`
                q = np.nanquantile(lags, self.levels, axis=0)  # (levels, hours)
            out[i, :, : len(k)] = np.where(enough, q, np.nan)
        return out
