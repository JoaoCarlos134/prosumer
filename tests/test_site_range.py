"""The per-site daily range of the outlook (`outlook.site_range`, version 0.7.0): the V11-b pilot's rule."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from prosumer import outlook
from test_diagnostics import SITE, _plant, _series


def _today(days: int = 3, total: float = 50.0, low: float = 45.0, high: float = 55.0) -> outlook.Outlook:
    """An outlook issued on 2026-06-30 for the next `days` days, default range [low, high]."""
    dates = pd.date_range("2026-07-01", periods=days, freq="D")
    daily = pd.DataFrame(
        {
            "unique_id": "pv",
            "date": dates,
            "lead_day": np.arange(1, days + 1),
            "total": total,
            "low": low,
            "high": high,
            "source": "weather",
            "confidence": "high",
        }
    )
    return outlook.Outlook(hourly=pd.DataFrame(), daily=daily, quantity="generation")


def _pairs(r: np.ndarray, lead: int = 1, last: str = "2026-06-30", total: float = 50.0) -> pd.DataFrame:
    """Past pairs of one lead day, one per day ending on `last`, with scaled errors r (default width 10)."""
    dates = pd.date_range(end=last, periods=len(r), freq="D")
    return pd.DataFrame(
        {
            "unique_id": "pv",
            "date": dates,
            "lead_day": lead,
            "total": total,
            "low": total - 5,
            "high": total + 5,
            "actual": total + 10 * np.asarray(r, float),
        }
    )


def test_the_rule_is_the_pilots_order_statistics() -> None:
    """n = 30 errors: the floor(0.1 x 31) = 3rd and the ceil(0.9 x 31) = 28th smallest, each edge from the
    forecast, in units of the default width (10 kWh here)."""
    r = np.linspace(-1.0, 1.0, 30)
    rng = np.random.default_rng(1)
    o = outlook.site_range(_today(1), _pairs(rng.permutation(r)))
    row = o.daily.iloc[0]
    k_lo, k_hi = math.floor(0.1 * 31), math.ceil(0.9 * 31)
    assert (k_lo, k_hi) == (3, 28)
    assert row["low"] == pytest.approx(50 + 10 * r[k_lo - 1])
    assert row["high"] == pytest.approx(50 + 10 * r[k_hi - 1])
    assert row["range"] == "site" and row["range_pairs"] == 30
    assert (row["default_low"], row["default_high"]) == (45.0, 55.0)
    assert any("comes from this site's own errors" in n for n in o.notes)


def test_each_edge_moves_on_its_own() -> None:
    """A site that always produces more than forecast: both edges above the forecast's default ones."""
    o = outlook.site_range(_today(1), _pairs(np.linspace(0.5, 1.5, 40)))
    row = o.daily.iloc[0]
    assert row["low"] > 50 and row["high"] > row["low"]


def test_too_few_pairs_keeps_the_default_and_says_so() -> None:
    o = outlook.site_range(_today(2), _pairs(np.zeros(29)))
    assert (o.daily["range"] == "default").all()
    assert (o.daily["low"] == 45).all() and (o.daily["high"] == 55).all()
    assert any("Too few past forecasts" in n for n in o.notes)


def test_only_pairs_known_on_the_issue_day_and_inside_the_window() -> None:
    """30 pairs of lead day 2 end on the issue day; a day after it, or older than 60 days, is not used."""
    issue = pd.Timestamp("2026-06-30")
    known = _pairs(np.zeros(30), lead=2)
    future = _pairs(np.full(5, 3.0), lead=2, last="2026-07-05")  # after the issue day: must not count
    old = _pairs(np.full(5, -3.0), lead=2, last=str((issue - pd.Timedelta(days=60)).date()))
    o = outlook.site_range(_today(2), pd.concat([old, known, future]))
    day2 = o.daily[o.daily["lead_day"] == 2].iloc[0]
    assert day2["range_pairs"] == 30
    assert day2["low"] == pytest.approx(50) and day2["high"] == pytest.approx(50)
    # lead day 1 has no pairs of its own: the default range
    assert o.daily[o.daily["lead_day"] == 1].iloc[0]["range"] == "default"


def test_the_range_is_cut_at_zero() -> None:
    o = outlook.site_range(_today(1, total=2.0, low=1.0, high=3.0), _pairs(np.linspace(-9, 0, 30), total=2.0))
    assert o.daily.iloc[0]["low"] == 0.0


def test_a_recalibrated_outlook_stores_the_default_range_for_later() -> None:
    """Fed back as past pairs, a recalibrated day is measured in units of its DEFAULT width, not its own."""
    first = outlook.site_range(_today(1), _pairs(np.linspace(-2, 2, 30)))
    saved = first.daily.assign(actual=60.0)
    pairs = outlook.past_pairs(saved)
    assert pairs.iloc[0]["low"] == 45.0 and pairs.iloc[0]["high"] == 55.0


def test_it_holds_eight_days_in_ten_where_the_default_holds_fewer() -> None:
    """Errors twice as wide as the default range: the default holds ~38% of days, the site range ~80%."""
    rng = np.random.default_rng(7)
    n_days = 400
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    actual = 50 + rng.normal(0, 8, n_days)
    hist = pd.DataFrame(
        {"unique_id": "pv", "date": dates, "lead_day": 1, "total": 50.0, "low": 45.0, "high": 55.0}
    ).assign(actual=actual)
    inside_site, inside_default = [], []
    for i in range(100, n_days):
        day = dates[i]
        today = outlook.Outlook(
            hourly=pd.DataFrame(),
            daily=hist.iloc[[i]].drop(columns="actual").reset_index(drop=True),
            quantity="generation",
        )
        o = outlook.site_range(today, hist.iloc[:i])
        row = o.daily.iloc[0]
        assert row["date"] == day and row["range"] == "site"
        inside_site.append(row["low"] <= actual[i] <= row["high"])
        inside_default.append(45 <= actual[i] <= 55)
    assert np.mean(inside_default) < 0.5
    assert 0.74 <= np.mean(inside_site) <= 0.88


def test_forecast_ahead_takes_look_backs_days_as_past_pairs() -> None:
    """31 checked days at lead day 1 (look_back) recalibrate day 1 of the outlook; days 2-3 stay default."""
    s = _series(_plant(0.8))
    back = outlook.look_back(s, days=31, site=SITE, tilt=15, azimuth=20)
    o = outlook.forecast_ahead(s, days=3, site=SITE, tilt=15, azimuth=20, past=back)
    assert o.daily["range"].tolist() == ["site", "default", "default"]
    assert o.daily.iloc[0]["range_pairs"] == 31
    plain = outlook.forecast_ahead(s, days=3, site=SITE, tilt=15, azimuth=20)
    np.testing.assert_allclose(o.daily["total"], plain.daily["total"])  # the forecast itself is unchanged
    assert "range" not in plain.daily.columns  # without `past` the output is as before, plus one note
    assert any("too narrow until 30 days" in n for n in plain.notes)
    assert any("too narrow until 30 days" in n for n in o.notes)  # days 2-3 still use the default range
    assert o.to_dict(lang="pt")["notes"]  # every new note renders in Portuguese


def test_bad_arguments_are_messages() -> None:
    with pytest.raises(ValueError, match="levels"):
        outlook.site_range(_today(1), _pairs(np.zeros(30)), levels=(0.9, 0.1))
    with pytest.raises(ValueError, match="lack the columns"):
        outlook.site_range(_today(1), _pairs(np.zeros(30)).drop(columns="actual"))
