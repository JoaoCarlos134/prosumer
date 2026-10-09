"""Protocol: folds, windows and the guard against the leakage the real data produced."""

from __future__ import annotations

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
