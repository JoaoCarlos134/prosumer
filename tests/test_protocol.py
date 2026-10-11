"""Protocol: folds, windows and the guard against the leakage the real data produced."""

from __future__ import annotations

import dataclasses
from itertools import pairwise

import pandas as pd
import pytest

from prosumer import data
from prosumer.protocol import DayAhead, H, Regime, SupportError


@pytest.fixture
def plant() -> object:
    series, _ = data.example_plant(n_series=2, start="2024-01-01", days=120)
    return series


def test_folds_cover_the_test_without_overlap(plant: object) -> None:
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-04-29", refit_days=20)
    f = t.folds()
    assert [x.days for x in f] == [20, 20, 20]
    assert f[0].start == pd.Timestamp("2024-03-01", tz=plant.tz)  # type: ignore[attr-defined]
    for a, b in pairwise(f):
        assert a.end < b.start, "folds must not overlap: overlap is leakage"
    assert f[-1].end.normalize() == pd.Timestamp("2024-04-29", tz=plant.tz)  # type: ignore[attr-defined]


def test_last_fold_may_be_shorter(plant: object) -> None:
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-25", refit_days=10)
    assert [x.days for x in t.folds()] == [10, 10, 5]


def test_fold_of_assigns_each_day_to_exactly_one_fold(plant: object) -> None:
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-04-09", refit_days=20)
    for day in pd.date_range("2024-03-01", "2024-04-09", freq="D", tz=plant.tz):  # type: ignore[attr-defined]
        f = t.fold_of(day)
        assert f.start <= day <= f.end


def test_fold_of_refuses_day_outside_the_test(plant: object) -> None:
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-10")
    with pytest.raises(ValueError, match="outside the test"):
        t.fold_of(pd.Timestamp("2024-02-01", tz=plant.tz))  # type: ignore[attr-defined]


def test_windows_have_the_right_horizon_and_context(plant: object) -> None:
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-05", context=168)
    ws = t.windows()
    assert ws, "there should be windows"
    for w in ws:
        assert len(w.timestamps) == H
        assert len(w.history) == 168
        assert w.timestamps[0] == w.day
        # The history ends before the forecast day: no model sees the day it forecasts.
        assert w.timestamps[0] > w.day - pd.Timedelta(hours=1)


def test_window_does_not_use_the_day_it_forecasts(plant: object) -> None:
    """The protocol's central guarantee, checked on the values and not only on the shape."""
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-02", context=48)
    q = plant.frame.set_index(["unique_id", "ds"])["y"]  # type: ignore[attr-defined]
    for w in t.windows():
        expected = [
            float(q.loc[(w.unique_id, ts)])
            for ts in pd.date_range(w.day - pd.Timedelta(hours=48), periods=48, freq="h", tz=plant.tz)  # type: ignore[attr-defined]
        ]
        assert w.history.tolist() == pytest.approx(expected)


def test_context_shorter_than_horizon_is_refused(plant: object) -> None:
    with pytest.raises(ValueError, match="horizon"):
        DayAhead(plant, test_start="2024-03-01", context=12)


def test_end_before_start_is_refused(plant: object) -> None:
    with pytest.raises(ValueError, match="before its start"):
        DayAhead(plant, test_start="2024-04-01", test_end="2024-03-01")


def test_check_support_raises_when_a_series_ends_early() -> None:
    """The benchmark regression: house H14 ends 20 days earlier and cutting by fold starts to matter.

    Without the cut, the window generator counts from the end of EACH series, steps back and re-emits
    days of an earlier fold with a model trained after them.
    """
    series = data.example_house(n_series=3, start="2024-01-01", days=120)
    t_ok = DayAhead(series, test_start="2024-03-01", test_end="2024-04-09", refit_days=20)
    t_ok.check_support()  # does not raise: all end together

    short = data.with_gaps(series, fraction=0.0, short_series="house_2", days_short=20)
    t_bad = DayAhead(short, test_start="2024-03-01", test_end="2024-04-09", refit_days=20)
    with pytest.raises(SupportError, match="cut each fold"):
        t_bad.check_support()


def test_test_days_skips_incomplete_day() -> None:
    """A day with a gap does not count: 24 valid hours or nothing."""
    series = data.example_house(n_series=1, start="2024-01-01", days=40)
    t_full = DayAhead(series, test_start="2024-02-01", test_end="2024-02-05", refit_days=10)
    n_full = len(t_full.test_days())

    x = series.frame.copy()
    target = (x["ds"] >= pd.Timestamp("2024-02-03 10:00", tz=series.tz)) & (
        x["ds"] < pd.Timestamp("2024-02-03 12:00", tz=series.tz)
    )
    x.loc[target, ["y", "valid"]] = [None, False]
    holed = data.EnergySeries.from_dataframe(
        x, unit=series.unit, quantity=series.quantity, tz=series.tz, freq=series.freq
    )
    t_holed = DayAhead(holed, test_start="2024-02-01", test_end="2024-02-05", refit_days=10)
    assert len(t_holed.test_days()) == n_full - 1


def test_regimes_are_explicit() -> None:
    """The regime is part of the result: mixing A with B in one table misleads the reader."""
    assert Regime.HISTORY.value == "A"
    assert Regime.KNOWN_WEATHER.value == "B"
    assert Regime.REAL_FORECAST.value == "C"


# ---------------------------------------------------------------- gaps, covariates and standalone folds
# (2026-10-11)
def _holed(seed: int = 3) -> object:
    series = data.example_house(n_series=2, start="2024-01-01", days=60)
    return data.with_gaps(series, fraction=0.02, seed=seed)  # ~60% of the days stay complete


def test_causal_fill_uses_only_the_window_history() -> None:
    """Gaps are filled from the window's own history: changing the forecast day (or later) changes nothing."""
    holed = _holed()
    t = DayAhead(
        holed, test_start="2024-02-20", test_end="2024-02-25", refit_days=10, context=72, min_history=0
    )
    before = {(w.unique_id, w.day): w.history.copy() for w in t.windows()}
    x = holed.frame.copy()  # type: ignore[attr-defined]
    # data of the LAST test day and after: no window may change (the 25th's history ends on the 24th at 23:00)
    later = x["ds"] >= pd.Timestamp("2024-02-25", tz=holed.tz)  # type: ignore[attr-defined]
    x.loc[later & x["valid"], "y"] = 999.0
    future_changed = data.EnergySeries.from_dataframe(
        x, unit="kWh", quantity="consumption", tz=holed.tz, freq="h"
    )  # type: ignore[attr-defined]
    t2 = DayAhead(future_changed, test_start="2024-02-20", test_end="2024-02-25", refit_days=10, context=72)
    ws = t2.windows()
    assert ws and any(not w.history_valid.all() for w in ws), "needs windows with gaps to mean anything"  # type: ignore[union-attr]
    for w in ws:
        assert w.history.tolist() == pytest.approx(before[(w.unique_id, w.day)].tolist())


def test_filled_history_has_no_nan_and_keeps_the_mask() -> None:
    t = DayAhead(_holed(), test_start="2024-02-20", test_end="2024-02-29", refit_days=10, context=168)
    ws = t.windows()
    assert ws
    assert all(not pd.isna(w.history).any() for w in ws)
    assert any(not w.history_valid.all() for w in ws), "the test data must have gaps inside some window"  # type: ignore[union-attr]
    for w in ws:
        assert w.history_valid is not None and len(w.history_valid) == len(w.history)


def test_fill_none_keeps_the_gaps() -> None:
    t = DayAhead(
        _holed(), test_start="2024-02-20", test_end="2024-02-29", refit_days=10, context=168, fill="none"
    )
    for w in t.windows():
        assert (pd.isna(w.history) == ~w.history_valid).all()  # type: ignore[operator]


def test_covariates_split_into_past_and_future(plant: object) -> None:
    f = plant.frame  # type: ignore[attr-defined]
    cov = f[["unique_id", "ds"]].assign(hour=f["ds"].dt.hour.astype(float))
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-03", context=48, covariates=cov)
    for w in t.windows():
        assert w.future_covariates["hour"].tolist() == list(range(24))
        assert len(w.past_covariates["hour"]) == 48
        assert w.past_covariates["hour"][-1] == 23.0


def test_naive_covariates_are_refused(plant: object) -> None:
    f = plant.frame  # type: ignore[attr-defined]
    cov = f[["unique_id"]].assign(ds=f["ds"].dt.tz_localize(None), hour=1.0)
    with pytest.raises(ValueError, match="time zone"):
        DayAhead(plant, test_start="2024-03-01", covariates=cov)


def test_min_history_decides_short_windows(plant: object) -> None:
    short_default = DayAhead(plant, test_start="2024-01-02", test_end="2024-01-03", context=168).windows()
    assert short_default == [], "by default a window needs the whole context"
    taken = DayAhead(
        plant, test_start="2024-01-02", test_end="2024-01-03", context=168, min_history=0
    ).windows()
    assert taken and len(taken[0].history) == 24


def test_standalone_folds_match_the_task(plant: object) -> None:
    from prosumer.protocol import folds

    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-04-29", refit_days=20)
    assert [(f.start, f.end) for f in t.folds()] == [
        (f.start.tz_localize(plant.tz), f.end.tz_localize(plant.tz))  # type: ignore[attr-defined]
        for f in folds("2024-03-01", "2024-04-29", 20)
    ]
    with pytest.raises(ValueError):
        folds("2024-03-01", "2024-03-02", 0)


def test_standardization_ignores_everything_after_the_cutoff(plant: object) -> None:
    from prosumer.protocol import standardize_by_training

    f = plant.frame.copy()  # type: ignore[attr-defined]
    cut = pd.Timestamp("2024-03-01", tz=plant.tz)  # type: ignore[attr-defined]
    a, pa = standardize_by_training(f, cut, ["y"])
    g = f.copy()
    g.loc[g["ds"] >= cut, "y"] = 1e6
    _, pb = standardize_by_training(g, cut, ["y"])
    assert pa == pb, "the test period must not move the scale"
    train = a[a["ds"] < cut]
    assert train.groupby("unique_id")["y"].mean().abs().max() < 1e-9


def test_standardization_skips_gaps_and_refuses_empty_training() -> None:
    from prosumer.protocol import standardize_by_training

    holed = data.with_gaps(data.example_house(n_series=1, days=20), fraction=0.1, seed=1)
    x = holed.frame.assign(
        y=holed.frame["y"].fillna(-1e6)
    )  # a gap with a garbage value: the mask must hide it
    cut = x["ds"].max()
    _, p = standardize_by_training(x, cut, ["y"])
    clean = holed.valid_only()
    assert p["house_1"]["y"][0] == pytest.approx(
        clean.loc[clean["ds"] < cut, "y"].mean()
    )  # cutoff is exclusive
    with pytest.raises(ValueError, match="Empty"):
        standardize_by_training(x, x["ds"].min(), ["y"])


def test_issue_hour_zero_is_the_benchmark_task(plant: object) -> None:
    a = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-05", context=48).windows()
    b = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-05", context=48, issue_hour=0).windows()
    assert [(w.unique_id, w.day, w.history.tolist()) for w in a] == [
        (w.unique_id, w.day, w.history.tolist()) for w in b
    ]


def test_issue_at_noon_sees_the_morning_and_forecasts_the_rest(plant: object) -> None:
    """F2(d): issued at 12:00, the history ends at 11:00 of the same day and the target is 12:00-23:00."""
    t = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-03", context=48, issue_hour=12)
    q = plant.frame.set_index(["unique_id", "ds"])["y"]  # type: ignore[attr-defined]
    ws = t.windows()
    assert ws
    for w in ws:
        assert len(w.timestamps) == H - 12
        assert w.timestamps[0] == w.day + pd.Timedelta(hours=12)
        assert w.timestamps[-1] == w.day + pd.Timedelta(hours=23)
        last_seen = w.day + pd.Timedelta(hours=11)
        assert w.history[-1] == pytest.approx(float(q.loc[(w.unique_id, last_seen)]))


def test_issue_hour_only_needs_the_target_hours_valid(plant: object) -> None:
    """A gap in the morning does not drop the day when the forecast is issued after it."""
    frame = plant.frame.copy()  # type: ignore[attr-defined]
    day = pd.Timestamp("2024-03-02", tz=plant.tz)  # type: ignore[attr-defined]
    frame.loc[frame["ds"] == day + pd.Timedelta(hours=3), "valid"] = False
    s = dataclasses.replace(plant, frame=frame)  # type: ignore[type-var]
    uid = frame["unique_id"].iloc[0]
    at_0 = DayAhead(s, test_start="2024-03-01", test_end="2024-03-03").test_days()
    at_12 = DayAhead(s, test_start="2024-03-01", test_end="2024-03-03", issue_hour=12).test_days()
    assert (uid, day) in at_12
    assert (uid, day) not in at_0


def test_issue_hour_out_of_range_is_refused(plant: object) -> None:
    with pytest.raises(ValueError, match="issue_hour"):
        DayAhead(plant, test_start="2024-03-01", issue_hour=24)


def test_test_dates_may_carry_a_time_zone(plant: object) -> None:
    tz = plant.tz  # type: ignore[attr-defined]
    naive = DayAhead(plant, test_start="2024-03-01", test_end="2024-03-05")
    aware = DayAhead(
        plant, test_start=pd.Timestamp("2024-03-01", tz=tz), test_end=pd.Timestamp("2024-03-05", tz=tz)
    )
    assert (naive.start, naive.end) == (aware.start, aware.end)
