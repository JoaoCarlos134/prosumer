"""Forecast post-processing: adjustments applied AFTER the model, without retraining it.

Today: causal bias correction for consumption. Decided by a pilot on the benchmark (2026-10-09):
foundation models forecast the median of a skewed distribution and underestimate the houses'
consumption by ~20%. Multiplying the day's forecast by the actual/forecast factor of the previous days
brings that bias below 1% and lifts the median of all models from +0.191 to +0.207 skill. On SOLAR
GENERATION the same correction makes things worse by up to -0.10 (the weather changes from one day to
the next and the factor becomes noise); so it is blocked for generation, and enabling it requires an
explicit request.
"""

from __future__ import annotations

import pandas as pd

KEYS = ["unique_id", "ds"]


def correct_bias(
    forecast: pd.DataFrame,
    actual: pd.DataFrame,
    *,
    quantity: str,
    days: int = 14,
    min_days: int = 7,
    bounds: tuple[float, float] = (0.5, 2.0),
    allow_generation: bool = False,
) -> pd.DataFrame:
    """Forecast corrected by each series' recent bias, using ONLY the past.

    Factor for day D = sum of actual / sum of forecast over the `days` previous days with data (at least
    `min_days`; before that, factor 1), clipped to `bounds`. Only hours where both actual and forecast
    exist count. Day D never enters its own factor: it is what a system would know at 00:00 of D.

    `forecast`: unique_id, ds, yhat. `actual`: unique_id, ds, y. Returns the forecast with `yhat`
    corrected and a `factor` column.
    """
    if quantity == "generation" and not allow_generation:
        raise ValueError(
            "Bias correction is blocked for generation: in the benchmark it worsened solar generation by "
            "up to -0.10 skill. Pass allow_generation=True only if you measured that it helps in your case."
        )
    if days < 1 or not 1 <= min_days <= days:
        raise ValueError("Requires 1 <= min_days <= days")
    p = forecast[[*KEYS, "yhat"]].copy()
    j = p.merge(actual[[*KEYS, "y"]], on=KEYS, how="left")
    j["day"] = j["ds"].dt.normalize()
    ok = j["y"].notna() & j["yhat"].notna()
    d = j[ok].groupby(["unique_id", "day"])[["y", "yhat"]].sum().sort_index()
    previous = d.groupby(level=0).transform(lambda s: s.shift(1).rolling(days, min_periods=min_days).sum())
    factor = (previous["y"] / previous["yhat"]).clip(*bounds).rename("factor")
    p["day"] = p["ds"].dt.normalize()
    p = p.merge(factor.reset_index(), on=["unique_id", "day"], how="left")
    p["factor"] = p["factor"].fillna(1.0)
    p["yhat"] = p["yhat"] * p["factor"]
    return p.drop(columns="day")
