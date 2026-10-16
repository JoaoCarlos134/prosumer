"""Forecasting models behind one interface, each with a card saying what it costs to use.

A model is anything with a `card`, `fit(series, cutoff, covariates)` and `predict(windows)`.
`rolling_forecast` runs it with the benchmark's protocol: retrained from scratch at the start of each fold, on
data before the fold only, and asked for the fold's windows. The output is a long frame (`unique_id`, `ds`,
`yhat`) that `metrics.align` takes.

The card exists because the choice of a model is rarely only about skill (section 5c of the proposal): the
best models of the benchmark run on CPU, some licences forbid commercial use (TimesFM-3), and a paid API sends
the user's data away (TimeGPT). The app shows the card next to each row.
"""

from __future__ import annotations

from .base import Forecaster, ModelCard, Probabilistic, rolling_forecast, rolling_quantiles
from .foundation import Chronos2, FlowState, TiRex2, Toto2
from .lightgbm import LightGBM, LightGBMQuantile
from .naive import EmpiricalQuantiles, Naive

__all__ = [
    "Chronos2",
    "EmpiricalQuantiles",
    "FlowState",
    "Forecaster",
    "LightGBM",
    "LightGBMQuantile",
    "ModelCard",
    "Naive",
    "Probabilistic",
    "TiRex2",
    "Toto2",
    "rolling_forecast",
    "rolling_quantiles",
]
