"""Metrics at several resolutions and bias correction: values known by construction."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prosumer import metrics, postprocessing


def _days(n_days: int, *, series: tuple[str, ...] = ("a",), start: str = "2024-01-01") -> pd.DataFrame:
    ds = pd.date_range(start, periods=24 * n_days, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    parts = [pd.DataFrame({"unique_id": u, "ds": ds, "y": 1.0 + rng.random(len(ds))}) for u in series]
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------- by_resolution
def test_perfect_forecast_is_perfect_at_every_level() -> None:
    y = _days(10)
    fc = y.assign(yhat=y["y"])
    ref = y.assign(yhat=y["y"] * 1.3)
    r = metrics.by_resolution(fc, ref).set_index("level")
    assert list(r.index) == ["hour", "day_night", "peak_17_21", "day"]
    assert np.allclose(r["skill"], 1.0) and np.allclose(r["R2"], 1.0) and np.allclose(r["nRMSE"], 0.0)


def test_error_that_cancels_within_the_day_vanishes_in_the_daily_total() -> None:
    # +0.5 on even hours and -0.5 on odd ones: hourly error, zero in the daily total.
    y = _days(10)
    sign = np.where(y["ds"].dt.hour % 2 == 0, 0.5, -0.5)
    fc = y.assign(yhat=y["y"] + sign)
    ref = y.assign(yhat=y["y"] * 1.2)
    r = metrics.by_resolution(fc, ref).set_index("level")
    assert r.loc["hour", "skill"] < 1.0
    assert r.loc["day", "skill"] == pytest.approx(1.0)
    assert r.loc["day", "nRMSE"] == pytest.approx(0.0, abs=1e-12)


def test_proportional_bias_is_the_same_at_every_level() -> None:
    y = _days(8)
    fc = y.assign(yhat=y["y"] * 0.8)  # 20% below at every hour
    r = metrics.by_resolution(fc, y.assign(yhat=y["y"])).set_index("level")
    assert np.allclose(r["MBE"], -0.2)


def test_block_count_per_level() -> None:
    y = _days(5, series=("a", "b"))
    r = metrics.by_resolution(y.assign(yhat=y["y"]), y.assign(yhat=y["y"] + 1)).set_index("level")
    assert r.loc["hour", "blocks"] == 5 * 24 * 2
    assert r.loc["day_night", "blocks"] == 5 * 2 * 2
    assert r.loc["peak_17_21", "blocks"] == 5 * 2
    assert r.loc["day", "blocks"] == 5 * 2


def test_incomplete_blocks_are_refused() -> None:
    with pytest.raises(ValueError, match="hours"):
        metrics.by_blocks({h: "peak" for h in range(18, 21)})


def test_tarifa_branca_as_custom_blocks() -> None:
    # Brazilian use: peak 18-21 h, intermediate 17 h and 21 h, off-peak the rest.
    branca = {h: "off" for h in range(24)} | {17: "inter", 21: "inter"} | {h: "peak" for h in range(18, 21)}
    y = _days(3)
    r = metrics.by_resolution(
        y.assign(yhat=y["y"]), y.assign(yhat=y["y"] + 1), {"branca": metrics.by_blocks(branca)}
    )
    assert r.loc[0, "blocks"] == 3 * 3


# ---------------------------------------------------------------------- correct_bias
def _biased_consumption(n_days: int, true_factor: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    y = _days(n_days)
    return y.assign(yhat=y["y"] / true_factor)[["unique_id", "ds", "yhat"]], y


def test_constant_bias_is_removed_after_the_minimum_days() -> None:
    fc, actual = _biased_consumption(30, true_factor=1.25)  # forecast 20% below
    c = postprocessing.correct_bias(fc, actual, quantity="consumption", days=14, min_days=7)
    day = c["ds"].dt.normalize()
    first = day < day.min() + pd.Timedelta(days=7)
    assert (c.loc[first, "factor"] == 1.0).all()  # not enough history: no correction
    j = c.merge(actual, on=["unique_id", "ds"])
    assert np.allclose(j.loc[~first.to_numpy(), "yhat"], j.loc[~first.to_numpy(), "y"])


def test_correction_does_not_use_the_day_itself() -> None:
    fc, actual = _biased_consumption(20, true_factor=1.1)
    a = postprocessing.correct_bias(fc, actual, quantity="consumption")
    changed = actual.copy()
    last = changed["ds"].dt.normalize() == changed["ds"].dt.normalize().max()
    changed.loc[last, "y"] *= 10  # change only the last day
    b = postprocessing.correct_bias(fc, changed, quantity="consumption")
    assert np.allclose(a.loc[last.to_numpy(), "yhat"], b.loc[last.to_numpy(), "yhat"])


def test_factor_is_bounded() -> None:
    fc, actual = _biased_consumption(20, true_factor=10.0)
    c = postprocessing.correct_bias(fc, actual, quantity="consumption", bounds=(0.5, 2.0))
    assert c["factor"].max() == pytest.approx(2.0)


def test_generation_is_blocked_by_default() -> None:
    fc, actual = _biased_consumption(10, true_factor=1.1)
    with pytest.raises(ValueError, match="generation"):
        postprocessing.correct_bias(fc, actual, quantity="generation")
    allowed = postprocessing.correct_bias(fc, actual, quantity="generation", allow_generation=True)
    assert len(allowed) == len(fc)
