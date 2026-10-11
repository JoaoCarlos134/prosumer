"""Forecasts that need no training: the benchmark's references."""

from __future__ import annotations

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
