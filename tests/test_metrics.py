"""Metrics: checked against values known by construction, not against "looks right".

This is where synthetic data is worth more than real data: you can build a forecast with an exact
skill and require the metric to recover that number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prosumer import data, metrics


def _frame(y: list[float], yhat: list[float], *, start: str = "2024-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(y), freq="h", tz="UTC")
    return pd.DataFrame({"unique_id": "a", "ds": idx, "y": y, "yhat": yhat})


def test_perfect_forecast_has_zero_error_and_r2_one() -> None:
    df = _frame([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])
    m = metrics.metrics(df)
    assert m["nMAE"] == pytest.approx(0.0)
    assert m["nRMSE"] == pytest.approx(0.0)
    assert m["MBE"] == pytest.approx(0.0)
    assert m["R2"] == pytest.approx(1.0)


def test_bias_has_known_sign_and_magnitude() -> None:
    """Underforecasting by 20% must show as MBE -0.2: it was the foundation models' consumption bias."""
    y = [1.0, 2.0, 3.0, 4.0]
    df = _frame(y, [v * 0.8 for v in y])
    m = metrics.metrics(df)
    assert m["MBE"] == pytest.approx(-0.2)
    assert m["nMAE"] == pytest.approx(0.2)


def test_skill_zero_when_equal_to_reference() -> None:
    df = _frame([1.0, 2.0, 3.0, 4.0], [1.1, 2.1, 3.1, 4.1])
    ref = _frame([1.0, 2.0, 3.0, 4.0], [1.1, 2.1, 3.1, 4.1])
    assert metrics.skill(df, ref) == pytest.approx(0.0)


def test_skill_half_when_the_error_halves() -> None:
    """skill = 1 - RMSE/RMSE_ref; half the error gives exactly 0.5."""
    y = [0.0, 0.0, 0.0, 0.0]
    df = _frame(y, [0.5, -0.5, 0.5, -0.5])
    ref = _frame(y, [1.0, -1.0, 1.0, -1.0])
    # A zero mean of y would break normalisation, but skill does not depend on it.
    assert metrics.skill(df, ref) == pytest.approx(0.5)


def test_skill_negative_when_worse_than_reference() -> None:
    y = [0.0, 0.0]
    assert metrics.skill(_frame(y, [2.0, -2.0]), _frame(y, [1.0, -1.0])) == pytest.approx(-1.0)


def test_metrics_refuse_zero_mean() -> None:
    """Normalising by a zero mean would give a silent infinity."""
    with pytest.raises(ValueError, match="Mean of the actual"):
        metrics.metrics(_frame([0.0, 0.0], [1.0, 1.0]))


def test_align_uses_only_common_finite_hours() -> None:
    """Two models evaluated on different hours look comparable and are not."""
    actual = pd.DataFrame(
        {
            "unique_id": "a",
            "ds": pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC"),
            "y": [1.0, 2.0, 3.0, 4.0],
        }
    )
    fc = actual[["unique_id", "ds"]].assign(yhat=[1.0, np.nan, 3.0, 4.0])
    ref = actual[["unique_id", "ds"]].assign(yhat=[1.0, 2.0, 3.0, np.nan])
    m, rr = metrics.align(fc, actual, ref)
    assert len(m) == 2 and len(rr) == 2
    assert m["ds"].tolist() == rr["ds"].tolist()


def test_align_fails_instead_of_comparing_nothing() -> None:
    actual = pd.DataFrame(
        {"unique_id": "a", "ds": pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"), "y": [1.0, 2.0]}
    )
    fc = actual[["unique_id", "ds"]].assign(yhat=[np.nan, np.nan])
    with pytest.raises(ValueError, match="No finite hours"):
        metrics.align(fc, actual, actual[["unique_id", "ds"]].assign(yhat=[1.0, 2.0]))


def test_align_refuses_duplicate_key() -> None:
    actual = pd.DataFrame(
        {"unique_id": "a", "ds": pd.to_datetime(["2024-01-01"] * 2, utc=True), "y": [1.0, 2.0]}
    )
    fc = actual[["unique_id", "ds"]].assign(yhat=[1.0, 2.0])
    with pytest.raises(Exception, match=r"one_to_one|merge|unique"):
        metrics.align(fc, actual, fc)


def test_skill_ci_contains_the_point_and_is_deterministic() -> None:
    series = data.example_house(n_series=2, days=60)
    actual = series.valid_only()[["unique_id", "ds", "y"]]
    fc = data.perfect_forecast(series)
    fc = fc.assign(yhat=fc["yhat"] * 0.9)
    ref = data.persistence_forecast(series)
    m, rr = metrics.align(fc, actual, ref.dropna())
    s = metrics.skill(m, rr)
    lo, hi = metrics.skill_ci95(m, rr, seed=42)
    assert lo <= s <= hi
    assert (lo, hi) == metrics.skill_ci95(m, rr, seed=42), "the same seed must give the same CI"


def test_holm_never_lowers_p_and_keeps_order() -> None:
    p = [0.001, 0.02, 0.3, 0.7]
    a = metrics.holm(p)
    assert np.all(a >= np.array(p)), "an adjusted p can never be below the original"
    assert np.all(np.diff(a) >= 0), "Holm keeps the order"
    assert np.all(a <= 1.0)


def test_holm_with_empty_list() -> None:
    assert metrics.holm([]).size == 0


def test_dm_does_not_reject_identical_models() -> None:
    """Identical models have zero difference: p = 1, not a division by zero."""
    series = data.example_house(n_series=1, days=60)
    actual = series.valid_only()[["unique_id", "ds", "y"]]
    fc = data.perfect_forecast(series).assign(yhat=lambda d: d["yhat"] * 0.9)
    m, _ = metrics.align(fc, actual, fc)
    e = metrics.squared_errors(m)
    diff, stat, p = metrics.diebold_mariano(e, e)
    assert (diff, stat, p) == (0.0, 0.0, 1.0)


def test_dm_detects_the_worse_model() -> None:
    """Positive sign = the first errs more. With 3x the error, it must be significant."""
    series = data.example_house(n_series=1, days=90)
    actual = series.valid_only()[["unique_id", "ds", "y"]]
    good = data.perfect_forecast(series).assign(yhat=lambda d: d["yhat"] * 0.95)
    bad = data.perfect_forecast(series).assign(yhat=lambda d: d["yhat"] * 0.85)
    mg, _ = metrics.align(good, actual, good)
    mb, _ = metrics.align(bad, actual, bad)
    diff, stat, p = metrics.diebold_mariano(metrics.squared_errors(mb), metrics.squared_errors(mg))
    assert diff > 0 and stat > 0 and p < 0.05


def test_daily_r2_is_nan_with_a_single_day() -> None:
    """With one day the daily totals do not vary: R2 is undefined, and NaN is the honest answer."""
    m = metrics.metrics(_frame([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]))
    assert np.isnan(m["R2_daily"])
    assert m["R2"] == pytest.approx(1.0)  # the hourly one is still defined


def test_daily_r2_defined_with_several_days() -> None:
    """With days of different energy the daily R2 exists again."""
    y = [1.0] * 24 + [5.0] * 24
    m = metrics.metrics(_frame(y, y))
    assert m["R2_daily"] == pytest.approx(1.0)


def test_evaluated_mask_rules() -> None:
    import pandas as pd
    import pytest

    from prosumer.metrics import evaluated_mask

    ds = pd.Series(pd.date_range("2024-01-01", periods=48, freq="h"))
    y = ds.dt.hour.map(lambda h: 1.0 if 9 <= h <= 15 else 0.0)
    f = pd.DataFrame({"ds": ds, "y": y, "poa_ceu_claro": ds.dt.hour.map(lambda h: 100.0 if 7 <= h <= 17 else 0.0)})
    assert evaluated_mask(f, "all").all()
    assert evaluated_mask(f, "sun").sum() == 2 * 11
    assert evaluated_mask(f, "profile").sum() == 2 * 7
    # the profile can come from another period (e.g. training): here one where only noon generates
    other = f.assign(y=(f["ds"].dt.hour == 12).astype(float))
    assert evaluated_mask(f, "profile", profile=other).sum() == 2
    with pytest.raises(ValueError):
        evaluated_mask(f, "night")
