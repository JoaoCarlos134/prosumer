"""Data contracts: what gets in, what is refused, and what the validity mask preserves."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prosumer import data
from prosumer.contracts import ContractError, EnergySeries


def test_accepts_minimal_frame() -> None:
    q = pd.DataFrame(
        {
            "unique_id": ["a", "a"],
            "ds": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"]),
            "y": [1.0, 2.0],
        }
    )
    s = EnergySeries.from_dataframe(q, unit="kWh", quantity="generation", tz="UTC", freq="h")
    assert s.series == ["a"]
    assert bool(s.frame["valid"].all())


def test_refuses_frame_without_required_column() -> None:
    q = pd.DataFrame({"unique_id": ["a"], "ds": pd.to_datetime(["2024-01-01"])})
    with pytest.raises(ContractError, match="required"):
        EnergySeries.from_dataframe(q, unit="kWh", quantity="generation", tz="UTC", freq="h")


def test_refuses_empty_frame() -> None:
    with pytest.raises(ContractError, match="Empty"):
        EnergySeries.from_dataframe(
            pd.DataFrame(columns=["unique_id", "ds", "y"]),
            unit="kWh",
            quantity="generation",
            tz="UTC",
            freq="h",
        )


def test_refuses_duplicate_key() -> None:
    """A repeated (unique_id, ds) is the symptom of leakage between folds; it must fail at the door."""
    q = pd.DataFrame(
        {"unique_id": ["a", "a"], "ds": pd.to_datetime(["2024-01-01 00:00"] * 2), "y": [1.0, 1.5]}
    )
    with pytest.raises(ContractError):
        EnergySeries.from_dataframe(q, unit="kWh", quantity="generation", tz="UTC", freq="h")


def test_nan_becomes_invalid_not_zero() -> None:
    """A gap and a zero are not the same: the inverter logs zero at night and nothing when it goes down."""
    q = pd.DataFrame(
        {
            "unique_id": ["a"] * 3,
            "ds": pd.date_range("2024-01-01", periods=3, freq="h"),
            "y": [1.0, np.nan, 0.0],
        }
    )
    s = EnergySeries.from_dataframe(q, unit="kWh", quantity="generation", tz="UTC", freq="h")
    assert s.frame["valid"].tolist() == [True, False, True]
    assert len(s.valid_only()) == 2
    assert s.coverage()["a"] == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    ("unit", "freq", "expected"),
    [("kWh", "h", 1.0), ("Wh", "h", 1e-3), ("kW", "h", 1.0), ("kW", "30min", 0.5), ("W", "30min", 5e-4)],
)
def test_conversion_to_kwh(unit: str, freq: str, expected: float) -> None:
    """Power must be multiplied by the step duration; energy must not."""
    q = pd.DataFrame({"unique_id": ["a"], "ds": pd.to_datetime(["2024-01-01"]), "y": [1.0]})
    s = EnergySeries.from_dataframe(q, unit=unit, quantity="generation", tz="UTC", freq=freq)  # type: ignore[arg-type]
    assert s.to_kwh().frame["y"].iloc[0] == pytest.approx(expected)
    assert s.to_kwh().unit == "kWh"


def test_naive_timestamps_are_read_in_the_declared_tz() -> None:
    q = pd.DataFrame({"unique_id": ["a"], "ds": pd.to_datetime(["2024-01-01 12:00"]), "y": [1.0]})
    s = EnergySeries.from_dataframe(q, unit="kWh", quantity="generation", tz="America/Sao_Paulo", freq="h")
    assert str(s.frame["ds"].dt.tz) == "America/Sao_Paulo"
    assert s.frame["ds"].iloc[0].hour == 12


# ---------------------------------------------------------------------- daylight saving time
# 2020-03-29 (the clock springs forward in Dublin, 01:00 local does not exist) and 2020-10-25 (falls back,
# 01:00 local repeats): the two changes in the year of the Dingle houses.
def _hourly_frame(start: str, hours: int, ids: tuple[str, ...] = ("a",)) -> pd.DataFrame:
    ds = pd.date_range(start, periods=hours, freq="h")
    return pd.DataFrame(
        {
            "unique_id": np.repeat(ids, hours),
            "ds": np.tile(ds, len(ids)),
            "y": 1.0 + np.arange(hours * len(ids)),
        }
    )


def test_naive_utc_from_a_dst_place_needs_source_tz() -> None:
    # File in UTC without a time zone, Dublin series: reading it as local time creates the missing hour.
    # Before the fix this came out as pandas' raw ValueError.
    q = _hourly_frame("2020-03-28 22:00", 6)
    with pytest.raises(ContractError, match="source_tz='UTC'"):
        EnergySeries.from_dataframe(q, unit="kWh", quantity="consumption", tz="Europe/Dublin", freq="h")
    s = EnergySeries.from_dataframe(
        q, unit="kWh", quantity="consumption", tz="Europe/Dublin", freq="h", source_tz="UTC"
    )
    hours = s.frame["ds"]
    assert str(hours.dt.tz) == "Europe/Dublin"
    assert len(s) == 6 and hours.is_unique
    assert (hours.diff().dropna() == pd.Timedelta("1h")).all()  # still hourly, no gap
    # 01:00 UTC becomes 02:00 in Dublin (summer time, UTC+1)
    assert hours.iloc[3].hour == 2 and hours.iloc[3].utcoffset() == pd.Timedelta("1h")


def test_repeated_local_hour_is_resolved_by_order() -> None:
    # Meter on local time: 01:00 appears twice on 25/10. The first one is summer time.
    ds = pd.to_datetime(["2020-10-25 00:00", "2020-10-25 01:00", "2020-10-25 01:00", "2020-10-25 02:00"])
    q = pd.DataFrame({"unique_id": "a", "ds": ds, "y": [1.0, 2.0, 3.0, 4.0]})
    s = EnergySeries.from_dataframe(q, unit="kWh", quantity="consumption", tz="Europe/Dublin", freq="h")
    assert s.frame["ds"].is_unique
    assert (s.frame["ds"].diff().dropna() == pd.Timedelta("1h")).all()
    assert s.frame["y"].tolist() == [1.0, 2.0, 3.0, 4.0]  # the order of the values does not change


def test_repeated_hour_is_resolved_in_each_series_separately() -> None:
    # Two houses in the same frame: inference must not mix one's hours with the other's.
    ds = pd.to_datetime(["2020-10-25 00:00", "2020-10-25 01:00", "2020-10-25 01:00", "2020-10-25 02:00"])
    q = pd.concat([pd.DataFrame({"unique_id": u, "ds": ds, "y": [1.0, 2.0, 3.0, 4.0]}) for u in ("a", "b")])
    s = EnergySeries.from_dataframe(q, unit="kWh", quantity="consumption", tz="Europe/Dublin", freq="h")
    for _, g in s.frame.groupby("unique_id"):
        assert g["ds"].is_unique and len(g) == 4


def test_tz_already_in_the_data_is_only_converted() -> None:
    q = _hourly_frame("2020-03-28 22:00", 6)
    q["ds"] = q["ds"].dt.tz_localize("UTC")
    # source_tz is ignored when the data already has a time zone: the absolute instant rules.
    s = EnergySeries.from_dataframe(
        q, unit="kWh", quantity="consumption", tz="Europe/Dublin", freq="h", source_tz="America/Sao_Paulo"
    )
    assert (s.frame["ds"].dt.tz_convert("UTC") == q["ds"]).all()


def _filled_local_grid() -> pd.DataFrame:
    """Dublin local time on a gap-free grid, like the Dingle houses: 29/03 01:00 (does not exist) and a
    single row at 25/10 01:00 (existed twice)."""
    ds = pd.concat(
        [
            pd.Series(pd.date_range("2020-03-28 23:00", periods=4, freq="h")),
            pd.Series(pd.date_range("2020-10-24 23:00", periods=4, freq="h")),
        ],
        ignore_index=True,
    )
    return pd.DataFrame({"unique_id": "a", "ds": ds, "y": np.arange(8.0)})


def test_filled_local_grid_is_refused_by_default_with_both_suggestions() -> None:
    with pytest.raises(ContractError, match="dst='drop'"):
        EnergySeries.from_dataframe(
            _filled_local_grid(), unit="kWh", quantity="consumption", tz="Europe/Dublin", freq="h"
        )


def test_drop_removes_only_the_impossible_hours_and_warns() -> None:
    with pytest.warns(UserWarning, match="2 row"):
        s = EnergySeries.from_dataframe(
            _filled_local_grid(),
            unit="kWh",
            quantity="consumption",
            tz="Europe/Dublin",
            freq="h",
            dst="drop",
        )
    assert len(s) == 6
    assert 2.0 not in s.frame["y"].tolist()  # 29/03 01:00
    assert 6.0 not in s.frame["y"].tolist()  # 25/10 01:00, single row of a repeated hour
    assert s.frame["ds"].is_unique


def test_ds_column_that_is_not_dates_becomes_contract_error() -> None:
    q = pd.DataFrame({"unique_id": ["a"], "ds": ["this is not a date"], "y": [1.0]})
    with pytest.raises(ContractError, match="ds"):
        EnergySeries.from_dataframe(q, unit="kWh", quantity="consumption", tz="UTC", freq="h")


def test_end_per_series_detects_short_series() -> None:
    """The H14 case: one series ends earlier and whoever builds folds needs to know."""
    series = data.example_house(n_series=3, days=40)
    assert series.ends_together()
    short = data.with_gaps(series, fraction=0.0, short_series="house_2", days_short=20)
    assert not short.ends_together()
    ends = short.end_per_series()
    assert (ends["house_1"] - ends["house_2"]).days == 20


@settings(max_examples=25, deadline=None)
@given(n=st.integers(min_value=1, max_value=50), value=st.floats(min_value=0.1, max_value=1e4))
def test_wh_to_kwh_is_always_one_thousandth(n: int, value: float) -> None:
    """Property: converting Wh to kWh divides by one thousand, whatever the value."""
    q = pd.DataFrame(
        {"unique_id": ["a"] * n, "ds": pd.date_range("2024-01-01", periods=n, freq="h"), "y": [value] * n}
    )
    s = EnergySeries.from_dataframe(q, unit="Wh", quantity="generation", tz="UTC", freq="h")
    assert np.allclose(s.to_kwh().frame["y"].to_numpy(), value / 1000.0)
