"""prosumer.economics (international core) on small hand-made sites whose bill can be worked out by hand."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from prosumer import EnergySeries, economics
from prosumer.economics import Tariff
from prosumer.outlook import Outlook

TZ = "Etc/GMT+3"


def _series(values: np.ndarray, start: str, quantity: str, uid: str = "site") -> EnergySeries:
    ds = pd.date_range(start, periods=len(values), freq="h", tz=TZ)
    return EnergySeries.from_dataframe(
        pd.DataFrame({"unique_id": uid, "ds": ds, "y": values}),
        unit="kWh",
        quantity=quantity,  # type: ignore[arg-type]
        tz=TZ,
        freq="h",
    )


def _site(days: int, pv_kwh: float, start: str = "2025-01-01") -> tuple[EnergySeries, EnergySeries]:
    """1 kWh of load every hour; `pv_kwh` of PV in each of the hours 10-13."""
    hours = days * 24
    load = np.ones(hours)
    pv = np.where(np.isin(np.arange(hours) % 24, [10, 11, 12, 13]), pv_kwh, 0.0)
    return _series(load, start, "consumption"), _series(pv, start, "generation")


TOU = Tariff(
    prices={"peak": 0.40, "day": 0.20, "night": 0.10},
    weekday={h: "peak" if 17 <= h < 21 else "day" if 7 <= h < 17 else "night" for h in range(24)},
    weekend=dict.fromkeys(range(24), "night"),
    export_price=0.05,
    fixed=10.0,
)


def test_flat_tariff_without_pv_is_energy_times_price_plus_fixed() -> None:
    load, _ = _site(59, 0)  # January and February 2025
    b = economics.bill(load, tariff=Tariff.flat(0.25, fixed=5.0))
    m = b.monthly.set_index("month")
    assert m.loc["2025-01-01", "grid_import"] == pytest.approx(31 * 24)
    assert m.loc["2025-02-01", "total"] == pytest.approx(28 * 24 * 0.25 + 5.0)
    assert (m["export"] == 0).all() and (m["coverage"] == 1).all()
    assert "hour by hour" in b.notes[0]


def test_flows_net_hour_by_hour() -> None:
    load, pv = _site(1, 3.0)
    f = economics.flows(load, pv)
    assert f["self_consumption"].sum() == pytest.approx(4.0)
    assert f["grid_import"].sum() == pytest.approx(20.0)
    assert f["export"].sum() == pytest.approx(8.0)


def test_net_metering_offsets_the_month_then_banks_and_spends_credits() -> None:
    load, pv = _site(59, 10.0)  # export 36 kWh/day > import 20 kWh/day
    b = economics.bill(load, pv, tariff=Tariff.flat(0.25), scheme="net_metering")
    m = b.monthly.set_index("month")
    jan = m.loc["2025-01-01"]
    assert jan["compensated"] == pytest.approx(20 * 31)
    assert jan["credit_new"] == pytest.approx(16 * 31)
    assert jan["total"] == pytest.approx(0.0)
    assert m.loc["2025-02-01", "credit_balance"] == pytest.approx(16 * 59)

    # a cloudy February spends January's credits
    load2, pv2 = _site(59, 10.0)
    f = pv2.frame.copy()
    f.loc[f["ds"] >= pd.Timestamp("2025-02-01", tz=TZ), "y"] = 0.0
    pv2 = EnergySeries.from_dataframe(f, unit="kWh", quantity="generation", tz=TZ, freq="h")
    feb = economics.bill(load2, pv2, tariff=Tariff.flat(0.25)).monthly.iloc[1]
    assert feb["credit_used"] == pytest.approx(min(16 * 31, 24 * 28))
    assert feb["total"] == pytest.approx((24 * 28 - min(16 * 31, 24 * 28)) * 0.25)


def test_net_metering_with_time_of_use_offsets_the_dearest_block_first() -> None:
    load, pv = _site(1, 3.0, start="2025-01-06")  # a Monday; 8 kWh exported in the "day" block
    b = economics.bill(load, pv, tariff=TOU, scheme="net_metering")
    blocks = b.by_block.set_index("block")
    # import: peak 4, day 10 - 4 (the PV hours are self-consumed) = 6, night 10; export 8 in "day"
    assert blocks.loc["peak", "grid_import"] == pytest.approx(4)
    assert blocks.loc["day", "grid_import"] == pytest.approx(6)
    assert blocks.loc["night", "grid_import"] == pytest.approx(10)
    # 6 kWh offset in "day", the 2 left over offset "peak": left to pay 2 peak + 10 night
    m = b.monthly.iloc[0]
    assert m["compensated"] == pytest.approx(8)
    assert m["energy_cost"] == pytest.approx(2 * 0.40 + 10 * 0.10)
    assert m["total"] == pytest.approx(2 * 0.40 + 10 * 0.10 + 10.0)


def test_net_billing_and_self_consumption() -> None:
    load, pv = _site(1, 3.0, start="2025-01-06")
    nb = economics.bill(load, pv, tariff=TOU, scheme="net_billing").monthly.iloc[0]
    imports = 4 * 0.40 + 6 * 0.20 + 10 * 0.10
    assert nb["energy_cost"] == pytest.approx(imports)
    assert nb["export_value"] == pytest.approx(8 * 0.05)
    assert nb["total"] == pytest.approx(imports - 8 * 0.05 + 10)
    sc = economics.bill(load, pv, tariff=TOU, scheme="self_consumption").monthly.iloc[0]
    assert sc["total"] == pytest.approx(imports + 10)


def test_credits_expire_after_credit_months() -> None:
    load, pv = _site(31, 10.0)
    f = pv.frame.copy()
    f["y"] = 0.0
    dark = EnergySeries.from_dataframe(f, unit="kWh", quantity="generation", tz=TZ, freq="h")
    # 100 kWh banked "in December"; with credit_months=1 they are gone in January
    b = economics.bill(load, dark, tariff=Tariff.flat(0.2), initial_credit=100.0, credit_months=1)
    m = b.monthly.iloc[0]
    assert m["credit_expired"] == pytest.approx(100)
    assert m["credit_used"] == 0
    assert any("expired" in n for n in b.notes)
    kept = economics.bill(load, dark, tariff=Tariff.flat(0.2), initial_credit=100.0).monthly.iloc[0]
    assert kept["credit_used"] == pytest.approx(100)


def test_weekend_holiday_and_split_hours() -> None:
    t = Tariff(
        prices={"a": 1.0, "b": 3.0},
        weekday={h: ({"a": 0.5, "b": 0.5} if h == 17 else "b" if h > 17 else "a") for h in range(24)},
        weekend=dict.fromkeys(range(24), "a"),
        holidays={date(2025, 1, 1)},
    )
    ds = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-01-02 17:00", tz=TZ),  # Thursday, split hour
            pd.Timestamp("2025-01-02 19:00", tz=TZ),
            pd.Timestamp("2025-01-04 19:00", tz=TZ),  # Saturday
            pd.Timestamp("2025-01-01 19:00", tz=TZ),  # holiday
        ]
    )
    assert t.price(ds).tolist() == pytest.approx([2.0, 3.0, 1.0, 1.0])
    with pytest.raises(ValueError, match="miss hours"):
        Tariff(prices={"a": 1.0}, weekday={0: "a"})
    with pytest.raises(ValueError, match="no price"):
        Tariff(prices={"a": 1.0}, weekday=dict.fromkeys(range(24), "z"))
    with pytest.raises(ValueError, match="add up to 1"):
        Tariff(prices={"a": 1.0, "b": 1.0}, weekday={h: {"a": 0.5, "b": 0.6} for h in range(24)})


def test_missing_hours_are_left_out_not_zeroed() -> None:
    load, pv = _site(31, 3.0)
    f = load.frame.copy()
    f.loc[f.index[:24], "y"] = np.nan
    holed = EnergySeries.from_dataframe(f, unit="kWh", quantity="consumption", tz=TZ, freq="h")
    b = economics.bill(holed, pv, tariff=Tariff.flat(0.2), scheme="self_consumption")
    m = b.monthly.iloc[0]
    assert m["coverage"] == pytest.approx(30 / 31)
    assert m["grid_import"] == pytest.approx(20 * 30)
    assert any("coverage" in n for n in b.notes)


def test_pairing_and_errors() -> None:
    load, pv = _site(2, 3.0)
    renamed = EnergySeries.from_dataframe(
        pv.frame.assign(unique_id="other"), unit="kWh", quantity="generation", tz=TZ, freq="h"
    )
    assert economics.flows(load, renamed)["generation"].sum() == pytest.approx(24)  # one each: paired
    two = EnergySeries.from_dataframe(
        pd.concat([load.frame, load.frame.assign(unique_id="b")]),
        unit="kWh",
        quantity="consumption",
        tz=TZ,
        freq="h",
    )
    f = economics.flows(two, pv)  # "b" has no PV: zero generation
    assert f.groupby("unique_id")["generation"].sum().to_dict() == {"b": 0.0, "site": 24.0}
    with pytest.raises(ValueError, match="without a consumption"):
        economics.flows(two, renamed)
    with pytest.raises(ValueError, match="scheme"):
        economics.bill(load, tariff=Tariff.flat(0.2), scheme="feed_in")  # type: ignore[arg-type]


def test_bill_serialises() -> None:
    load, pv = _site(3, 3.0)
    b = economics.bill(load, pv, tariff=TOU)
    json.dumps(b.to_dict())
    assert "| site | 2025-01 |" in b.to_markdown()


# ---------------------------------------------------------------------- cheapest windows
def _outlook(quantity: str, values: np.ndarray, start: str = "2025-01-06") -> Outlook:
    ds = pd.date_range(start, periods=len(values), freq="h", tz=TZ)
    hourly = pd.DataFrame({"unique_id": "site", "ds": ds, "y_hat": values})
    daily = pd.DataFrame(
        {
            "unique_id": "site",
            "date": pd.date_range(start, periods=len(values) // 24, freq="D"),
            "confidence": "high",
        }
    )
    return Outlook(hourly=hourly, daily=daily, quantity=quantity)


def test_cheapest_windows_follow_the_sun_unless_credits_are_one_to_one() -> None:
    sun = np.where(np.isin(np.arange(48) % 24, [10, 11, 12]), 3.0, 0.0)
    gen = _outlook("generation", sun)
    flat = Tariff.flat(0.30, export_price=0.05)
    w = economics.cheapest_windows(flat, generation=gen, hours=3, kw=2.0, scheme="self_consumption", top=1)
    assert len(w) == 2 and (w["start"].dt.hour == 10).all()
    assert w["cost"].iloc[0] == pytest.approx(0.0) and w["pv_kwh"].iloc[0] == pytest.approx(6.0)
    nb = economics.cheapest_windows(flat, generation=gen, hours=3, kw=2.0, scheme="net_billing", top=1)
    assert nb["cost"].iloc[0] == pytest.approx(6 * 0.05)
    # 1:1 net metering: a PV kWh used is a credit not earned, every window costs the same
    nm = economics.cheapest_windows(flat, generation=gen, hours=3, kw=2.0, scheme="net_metering", top=None)
    assert np.allclose(nm["cost"], 6 * 0.30)


def test_cheapest_windows_with_time_of_use_and_household_load() -> None:
    sun = np.where(np.isin(np.arange(24), [10, 11, 12]), 1.5, 0.0)
    load = np.full(24, 0.5)
    w = economics.cheapest_windows(
        TOU,
        generation=_outlook("generation", sun),
        consumption=_outlook("consumption", load),
        hours=2,
        kw=1.0,
        scheme="self_consumption",
        top=None,
    )
    best = w[w["rank"] == 1].iloc[0]
    assert best["start"].hour in (10, 11)  # surplus 1 kWh/h covers the load fully
    assert best["cost"] == pytest.approx(0.0)
    night = w[w["start"].dt.hour == 0].iloc[0]
    assert night["cost"] == pytest.approx(2 * 0.10)
    assert set(w["confidence"]) == {"high"}
    with pytest.raises(ValueError, match="outlook"):
        economics.cheapest_windows(TOU)
    with pytest.raises(ValueError, match="quantity"):
        economics.cheapest_windows(TOU, generation=_outlook("consumption", load))


def test_cheapest_windows_skip_unknown_hours_and_broken_runs() -> None:
    sun = np.where(np.isin(np.arange(24), [10, 11, 12]), 3.0, 0.0)
    unknown = sun.copy()
    unknown[2] = np.nan  # an hour of unknown forecast is not free PV
    flat = Tariff.flat(0.30)
    w = economics.cheapest_windows(
        flat, generation=_outlook("generation", unknown), hours=3, scheme="self_consumption", top=None
    )
    assert not set(w["start"].dt.hour) & {0, 1, 2}  # every block that contains hour 2 is out
    assert w[w["rank"] == 1]["start"].dt.hour.iloc[0] == 10
    assert sorted(w["rank"]) == list(range(1, len(w) + 1))
    # a missing row (hour 6): no 3-h block may span the hole
    o = _outlook("generation", sun)
    o.hourly = o.hourly.drop(index=6).reset_index(drop=True)
    w2 = economics.cheapest_windows(flat, generation=o, hours=3, scheme="self_consumption", top=None)
    assert ((w2["end"] - w2["start"]) == pd.Timedelta(hours=3)).all()
    assert not set(w2["start"].dt.hour) & {4, 5, 6}


def test_generation_series_starting_later_is_unknown_and_noted() -> None:
    load, pv = _site(31, 3.0)
    late = EnergySeries.from_dataframe(
        pv.frame[pv.frame["ds"] >= pd.Timestamp("2025-01-11", tz=TZ)],
        unit="kWh",
        quantity="generation",
        tz=TZ,
        freq="h",
    )
    b = economics.bill(load, late, tariff=Tariff.flat(0.2))
    assert b.monthly.iloc[0]["coverage"] == pytest.approx(21 / 31)
    assert b.hourly["generation_missing"].sum() == 240
    assert any("no generation row" in n for n in b.notes)
