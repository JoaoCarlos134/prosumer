"""Forecast post-processing: adjustments applied AFTER the model, without retraining it.

Two adjustments, each decided by a pilot on the benchmark: causal conformal recalibration of quantile bands
(`conformal_quantiles`, below) and causal bias correction for consumption (2026-10-09): foundation models
forecast the median of a skewed distribution and underestimate the houses' consumption by ~20%.
Multiplying the day's forecast by the actual/forecast factor of the previous days brings that bias below
1% and lifts the median of all models from +0.191 to +0.207 skill. On SOLAR GENERATION the same
correction makes things worse by up to -0.10 (the weather changes from one day to the next and the factor
becomes noise); so it is blocked for generation, and enabling it requires an explicit request.
"""

from __future__ import annotations

import numpy as np
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


def conformal_quantiles(
    quantiles: pd.DataFrame,
    actual: pd.DataFrame,
    *,
    days: int = 28,
    min_days: int = 7,
    hours: pd.Series | None = None,
    lower: float | None = 0.0,
) -> pd.DataFrame:
    """Quantile band recalibrated on its own recent errors, using ONLY the past (causal conformal).

    For day D and each level a: the scores r = (y - q_a) / w over the `days` days before D (all series
    pooled; D never enters its own calibration), w = the row's widest band (q_max - q_min); then
    q_a(D) += quantile_a(r) x w. A band that was too narrow widens, one too wide narrows, a biased one shifts;
    scaling by w keeps a band of ~0 width (night on PV) at ~0. Before `min_days` days with errors, the day
    is left as it came. Crossed quantiles are sorted and, with `lower`, cut at it (energy is not negative).

    Decided by a pilot on the benchmark's bands (2026-10-11, `piloto_conformal.py`, 11 source/case/regime
    combinations, 28 days): calibrated (80% and 60% bands within +-5 points) in 10 of 11 against 7 of 11
    before, including all four that failed (LightGBM-quantile on the houses' PV: 80% band 0.651 -> 0.814,
    and in regime C 0.741 -> 0.810; Chronos-2 too wide in regime C 0.837/0.654 -> 0.804/0.605); CRPS
    better on average. The one miss: a band already calibrated that went 3 points over (TimesFM-3 PV).
    One shift per level and pair-wise conformal (CQR) were also tried: pair-wise cannot narrow a band whose
    errors pile up at 0 (Chronos-2 in C did not move).

    `quantiles`: unique_id, ds and one column per level (`q0.1`, ..., as `rolling_quantiles` returns; other
    columns are kept, `yhat` untouched). `actual`: unique_id, ds, y (measured hours). `hours`: boolean,
    aligned with `quantiles`, the hours that calibrate and are adjusted (e.g. the sun hours of PV, so the
    night does not fill the calibration with zeros); default all. Adds a `conformal` column: True where the
    day was recalibrated.
    """
    if days < 1 or not 1 <= min_days <= days:
        raise ValueError("Requires 1 <= min_days <= days")
    cols = [c for c in quantiles.columns if c.startswith("q")]
    levels = [float(c[1:]) for c in cols]
    if not cols or any(not 0 < a < 1 for a in levels):
        raise ValueError("quantiles needs columns q<level>, levels in (0, 1)")
    cols = [c for _, c in sorted(zip(levels, cols, strict=True))]
    levels = sorted(levels)
    out = quantiles.copy()
    q = out[cols].to_numpy(float)
    if lower is not None:
        q = np.clip(q, lower, None)
    q = np.sort(q, axis=1)
    y = out[KEYS].merge(actual[[*KEYS, "y"]], on=KEYS, how="left", validate="one_to_one")["y"].to_numpy(float)
    day = out["ds"].dt.normalize().to_numpy()
    width = q[:, -1] - q[:, 0]
    use = np.ones(len(out), bool) if hours is None else np.asarray(hours, bool)
    usable = use & (width > _EPS)
    known = usable & np.isfinite(y)
    adjusted = q.copy()
    done = np.zeros(len(out), bool)
    for d in np.unique(day):
        cal = known & (day < d) & (day >= d - np.timedelta64(days, "D"))
        if len(np.unique(day[cal])) < min_days:
            continue
        target = (day == d) & usable
        done |= day == d
        r = (y[cal, None] - q[cal]) / width[cal, None]
        shift = np.array([np.quantile(r[:, k], a) for k, a in enumerate(levels)])
        adjusted[target] = q[target] + shift * width[target, None]
    if lower is not None:
        adjusted = np.clip(adjusted, lower, None)
    out[cols] = np.sort(adjusted, axis=1)
    out["conformal"] = done
    return out


_EPS = 1e-6
