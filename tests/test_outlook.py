"""prosumer.outlook on synthetic plants and households whose future is known."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from prosumer import EnergySeries, outlook, physics
from test_diagnostics import SITE, TZ, _plant, _series


def _weather(
    hours: pd.DatetimeIndex, kc: np.ndarray, models: dict[str, int], issued: pd.Timestamp
) -> pd.DataFrame:
    """Long frame like `fetch_forecast`: each model gives the true GHI up to its horizon (hours)."""
    cs = physics.clear_sky_ghi(hours, *SITE)
    parts = []
    for m, horizon in models.items():
        ghi = np.where(np.arange(len(hours)) < horizon, cs * kc, np.nan)
        parts.append(pd.DataFrame({"model": m, "ds": hours, "ghi": ghi}))
    w = pd.concat(parts, ignore_index=True)
    w.attrs["issued"] = issued.isoformat()
    return w


def _future(days: int, seed: int = 9) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """The 'true' next days of `_plant(0.8)` (kWp 4, tilt 15, azimuth 20): hours, clouds and energy."""
    rng = np.random.default_rng(seed)
    hours = pd.date_range(
        "2024-01-01", periods=days * 24, freq="h", tz=TZ
    )  # _plant(730 days) ends 2023-12-31
    kc = np.repeat(rng.uniform(0.2, 1.0, days), 24)
    sun = physics.mean_sun(hours, *SITE)
    truth = 4.0 * physics.poa_isotropic(physics.clear_sky_ghi(hours, *SITE) * kc, sun, 15, 20) / 1000 * 0.8
    return hours, kc, truth


def test_seasonal_only_learns_the_plant() -> None:
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=7, site=SITE)
    m = o.method["series"]["p1"]
    assert m["orientation"] == "fitted"
    assert abs(m["tilt"] - 15) <= 5 and abs(((m["azimuth"] - 20 + 180) % 360) - 180) <= 20
    assert m["kw_eff"] == pytest.approx(3.2, rel=0.05)  # kWp 4 x level 0.8
    assert len(o.hourly) == 7 * 24 and o.hourly["ds"].min() == pd.Timestamp("2024-01-01", tz=TZ)
    assert (o.hourly["source"] == "seasonal").all()
    assert (o.daily["confidence"] == "seasonal only").all()
    assert (o.hourly["low"] <= o.hourly["y_hat"]).all() and (o.hourly["y_hat"] <= o.hourly["high"]).all()
    # an average January day: between the cloudiest and the clearest synthetic days (0.2-1 of clear sky)
    _, _, truth = _future(7)
    clear_day = truth.reshape(7, 24).sum(axis=1).max() / 1.0
    assert 0.3 * clear_day < o.daily["total"].mean() < 1.0 * clear_day * 1.1


def test_perfect_weather_gives_the_truth_on_trusted_days() -> None:
    hours, kc, truth = _future(10)
    issued = pd.Timestamp("2023-12-31 20:00", tz=TZ)
    w = _weather(hours, kc, {"long": 10 * 24, "short": 3 * 24}, issued)
    full = (1.0,) * 10  # the mechanics with full trust; the measured defaults are checked below
    o = outlook.forecast_ahead(
        _series(_plant(0.8)), days=10, site=SITE, weather=w, tilt=15, azimuth=20, trust=full
    )
    assert o.method["series"]["p1"]["orientation"] == "given"
    d = o.daily
    true_days = truth.reshape(10, 24).sum(axis=1)
    first3 = d["lead_day"] <= 3  # trust 1: the forecast is the weather's
    np.testing.assert_allclose(d.loc[first3, "total"], true_days[:3], rtol=0.03)
    assert (d.loc[first3, "confidence"] == "high").all()
    assert list(d["n_models"]) == [2, 2, 2] + [1] * 7  # the short model stops after 3 days
    # with the measured defaults: weather to lead 7, labels from the pilot's skill, seasonal after
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=10, site=SITE, weather=w, tilt=15, azimuth=20)
    d = o.daily
    assert d["confidence"].tolist() == ["high"] * 3 + ["medium"] * 3 + ["low"] + ["seasonal only"] * 3
    assert (d.loc[d["lead_day"] >= 8, "source"] == "seasonal").all()
    assert max(outlook.TRUST) == 1.0 and len(outlook.TRUST) == len(outlook.SKILL) == 7  # capped at 1


def test_beyond_the_last_model_is_seasonal_and_says_so() -> None:
    hours, kc, _ = _future(20)
    w = _weather(hours, kc, {"m": 16 * 24}, pd.Timestamp("2023-12-31 20:00", tz=TZ))
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=20, site=SITE, weather=w)
    tail = o.daily[o.daily["lead_day"] > 16]
    assert len(tail) == 4 and (tail["source"] == "seasonal").all()
    assert any("seasonal expectation" in n for n in o.notes)


def test_weather_that_starts_after_the_data_end() -> None:
    hours, kc, _ = _future(12)
    later = hours[48:]
    w = _weather(later, kc[48:], {"m": 10 * 24}, pd.Timestamp("2024-01-02 06:00", tz=TZ))
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=5, site=SITE, weather=w)
    assert o.daily["date"].min() == pd.Timestamp("2024-01-03")
    assert o.daily["lead_day"].tolist() == [1, 2, 3, 4, 5]
    assert any("not forecast" in n for n in o.notes)


def test_consumption_repeats_the_recent_weeks() -> None:
    idx = pd.date_range("2020-08-10", periods=10 * 7 * 24, freq="h", tz="Europe/Dublin")
    week = (idx.dayofweek.to_numpy() >= 5) * 0.5 + np.where((idx.hour >= 18) & (idx.hour < 21), 1.0, 0.2)
    s = EnergySeries.from_dataframe(
        pd.DataFrame({"unique_id": "H1", "ds": idx, "y": week}),
        unit="kWh",
        quantity="consumption",
        tz="Europe/Dublin",
        freq="h",
    )
    o = outlook.forecast_ahead(s, days=14)
    h = o.hourly
    want = (h["ds"].dt.dayofweek >= 5) * 0.5 + np.where(
        (h["ds"].dt.hour >= 18) & (h["ds"].dt.hour < 21), 1.0, 0.2
    )
    np.testing.assert_allclose(h["y_hat"], want)
    assert (o.daily["confidence"] == "typical week").all()
    # the October clock change: 2020-10-25 has 25 hours in Dublin and is still one day
    oct25 = o.daily[o.daily["date"] == pd.Timestamp("2020-10-25")]
    assert len(oct25) == 1 and (h["ds"].dt.tz_localize(None).dt.normalize() == "2020-10-25").sum() == 25
    b = outlook.best_windows(o, 3)
    assert (b["start"].dt.hour.isin(range(0, 16))).all()  # lowest use: never the 18-21 h peak
    assert len(b) == 14


def test_best_windows_for_generation_is_midday() -> None:
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=3, site=SITE)
    b = outlook.best_windows(o, 3)
    assert len(b) == 3
    assert b["start"].dt.hour.between(9, 12).all()
    assert (b["end"] - b["start"] == pd.Timedelta(hours=3)).all()


def test_report_forms_and_errors() -> None:
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=2, site=SITE)
    json.dumps(o.to_dict())
    assert "| unique_id |" in o.to_markdown()
    s = _series(_plant(0.8))
    with pytest.raises(ValueError, match="site"):
        outlook.forecast_ahead(s)
    with pytest.raises(ValueError):
        outlook.forecast_ahead(s, site=SITE, days=0)
    with pytest.raises(ValueError):
        outlook.forecast_ahead(s, site=SITE, tilt={"other": 10}, azimuth=0)


def test_too_few_clear_days_needs_kwp() -> None:
    s = _series(_plant(0.8, days=3))
    with pytest.raises(ValueError, match="kwp"):
        outlook.forecast_ahead(s, site=SITE, tilt=15, azimuth=20)
    o = outlook.forecast_ahead(s, site=SITE, tilt=15, azimuth=20, kwp=4.0)
    assert o.method["series"]["p1"]["kw_eff"] == pytest.approx(3.2)


def test_a_model_day_with_impossible_sun_is_left_out() -> None:
    hours, kc, truth = _future(3)
    w = _weather(hours, kc, {"good": 3 * 24, "broken": 3 * 24}, pd.Timestamp("2023-12-31 20:00", tz=TZ))
    broken = (w["model"] == "broken") & (w["ds"].dt.day == 2)
    # like meteofrance_seamless on its 4th day (2026-10-12): far above clear sky. A wrong value that stays
    # below the physical limit cannot be told from weather and is not caught.
    cs = physics.clear_sky_ghi(pd.DatetimeIndex(w.loc[broken, "ds"]), *SITE)
    w.loc[broken, "ghi"] = 2.5 * cs
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=3, site=SITE, weather=w, tilt=15, azimuth=20)
    np.testing.assert_allclose(o.daily["total"], truth.reshape(3, 24).sum(axis=1), rtol=0.03)
    assert o.daily["n_models"].tolist() == [2, 1, 1]  # left out from its first broken day to the end
    assert any("broken from 2024-01-02" in n for n in o.notes)


def test_an_unidentified_roof_is_flagged() -> None:
    """Review finding (2026-10-12): the old test passed through `or tilt < 30` and never reached the note."""
    f = _plant(0.8)
    rng = np.random.default_rng(3)
    f["y"] *= rng.uniform(0.2, 1.0, len(f))  # hour-to-hour noise no single plane explains: R2 well below 0.85
    o = outlook.forecast_ahead(_series(f), days=2, site=SITE)
    assert any("unreliable" in n for n in o.notes)
    clean = outlook.forecast_ahead(_series(_plant(0.8)), days=2, site=SITE)
    assert not any("unreliable" in n for n in clean.notes)


def test_weather_in_another_zone_starting_late_in_the_local_day() -> None:
    """Review finding: weather in UTC from 00 UTC (21:00 in Sao Paulo) made a 'high' day of 3 hours."""
    hours, kc, _ = _future(6)
    utc = pd.date_range("2024-01-03 00:00", periods=4 * 24, freq="h", tz="UTC")
    local_day = utc.tz_convert(TZ).tz_localize(None).normalize()
    kc_utc = pd.Series(kc, index=hours.tz_localize(None).normalize()).groupby(level=0).first()
    k = kc_utc.reindex(local_day).to_numpy()
    w = pd.DataFrame({"model": "m", "ds": utc, "ghi": physics.clear_sky_ghi(utc, *SITE) * k})
    w.attrs["issued"] = "2024-01-02T23:00:00+00:00"
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=3, site=SITE, weather=w)
    assert o.daily["date"].min() == pd.Timestamp("2024-01-03")  # 2024-01-02 21:00 local is not a full day
    assert any("covers in full" in n for n in o.notes)
    assert any("measured on two plants" in n for n in o.notes)


def test_a_day_partly_past_the_horizon_is_not_labelled_by_its_best_hour() -> None:
    hours, kc, _ = _future(3)
    w = _weather(
        hours, kc, {"m": 24 + 11}, pd.Timestamp("2023-12-31 20:00", tz=TZ)
    )  # stops at 11:00 of day 2
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=3, site=SITE, weather=w)
    d2 = o.daily.iloc[1]
    assert 0 < d2["trust"] < 1.0  # mean over the sun hours, about half of them with weather
    assert o.daily.iloc[2]["confidence"] == "seasonal only"


def test_unknown_hours_are_never_a_load_window() -> None:
    idx = pd.date_range("2020-08-10", periods=5 * 7 * 24, freq="h", tz="Etc/GMT")
    y = np.where(idx.hour == 3, np.nan, 1.0 + (idx.hour >= 18))
    s = EnergySeries.from_dataframe(
        pd.DataFrame({"unique_id": "H", "ds": idx, "y": y}),
        unit="kWh",
        quantity="consumption",
        tz="Etc/GMT",
        freq="h",
    )
    o = outlook.forecast_ahead(s, days=2)
    b = outlook.best_windows(o, 1)
    assert not (b["start"].dt.hour == 3).any()
    assert (o.daily["missing_hours"] == 1).all()
    assert any("no forecast" in n for n in o.notes)


def test_silent_fallbacks_now_say_so() -> None:
    hours, kc, _ = _future(3)
    w = _weather(hours, kc, {"m": 0}, pd.Timestamp("2023-12-31 20:00", tz=TZ))  # every value NaN
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=3, site=SITE, weather=w)
    assert any("covers none" in n for n in o.notes)
    o = outlook.forecast_ahead(_series(_plant(0.8)), days=2, site=SITE, start="2023-12-30")
    assert any("not forecasts" in n for n in o.notes)


# ---------------------------------------------------------------- declared tuning (nothing tuned in hiding)
def test_tuning_arguments_default_to_the_old_constants_and_take_effect() -> None:
    """The numbers measured or set by hand on the Parana plants are arguments now (2026-10-16): the defaults
    give the same outlook as before, and each one changes what it should."""
    hours, kc, _ = _future(10)
    w = _weather(hours, kc, {"long": 10 * 24, "short": 3 * 24}, pd.Timestamp("2023-12-31 20:00", tz=TZ))
    s = _series(_plant(0.8))
    base = outlook.forecast_ahead(s, days=10, site=SITE, weather=w, tilt=15, azimuth=20)
    same = outlook.forecast_ahead(
        s,
        days=10,
        site=SITE,
        weather=w,
        tilt=15,
        azimuth=20,
        skill=outlook.SKILL,
        confidence=(outlook.HIGH, outlook.MEDIUM),
        implausible=outlook.IMPLAUSIBLE,
        kw_eff_days=(outlook.KW_EFF_DAYS, outlook.KW_EFF_FALLBACK_DAYS),
        min_month_days=outlook.MIN_MONTH_DAYS,
        kwp_share=outlook.KWP_SHARE,
    )
    pd.testing.assert_frame_equal(base.hourly, same.hourly)
    pd.testing.assert_frame_equal(base.daily, same.daily)
    assert base.method["skill"] == list(outlook.SKILL)

    # confidence thresholds: everything with skill >= 0.2 is "high"
    loose = outlook.forecast_ahead(
        s, days=10, site=SITE, weather=w, tilt=15, azimuth=20, confidence=(0.19, 0.1)
    )
    assert loose.daily["confidence"].tolist() == ["high"] * 7 + ["seasonal only"] * 3
    # own skill per lead: the labels follow it, and the note on the Parana measurements goes away
    mine = outlook.forecast_ahead(
        s, days=10, site=SITE, weather=w, tilt=15, azimuth=20, trust=(1.0,) * 7, skill=(0.3,) * 7
    )
    assert set(mine.daily["confidence"].iloc[:7]) == {"medium"}
    assert not any("measured on two plants" in n for n in mine.notes)
    assert any("measured on two plants" in n for n in base.notes)

    with pytest.raises(ValueError, match="confidence"):
        outlook.forecast_ahead(s, site=SITE, confidence=(0.2, 0.3))
    with pytest.raises(ValueError, match="kw_eff_days"):
        outlook.forecast_ahead(s, site=SITE, kw_eff_days=(120, 60))
    with pytest.raises(ValueError, match="kwp_share"):
        outlook.forecast_ahead(s, site=SITE, kwp_share=0)


def test_kwp_share_and_implausible_limit_are_arguments() -> None:
    s = _series(_plant(0.8, days=3))
    o = outlook.forecast_ahead(s, site=SITE, tilt=15, azimuth=20, kwp=4.0, kwp_share=0.75)
    assert o.method["series"]["p1"]["kw_eff"] == pytest.approx(3.0)
    assert any("used 75% of the given kWp" in n for n in o.notes)

    hours, kc, _ = _future(3)
    w = _weather(hours, kc, {"good": 3 * 24, "broken": 3 * 24}, pd.Timestamp("2023-12-31 20:00", tz=TZ))
    broken = (w["model"] == "broken") & (w["ds"].dt.day == 2)
    w.loc[broken, "ghi"] = 2.5 * physics.clear_sky_ghi(pd.DatetimeIndex(w.loc[broken, "ds"]), *SITE)
    lax = outlook.forecast_ahead(
        _series(_plant(0.8)), days=3, site=SITE, weather=w, tilt=15, azimuth=20, implausible=(3.0, 50.0)
    )
    assert lax.daily["n_models"].tolist() == [2, 2, 2]  # 2.5 x clear sky passes a limit of 3 x


def test_a_15_minute_logger_is_summed_into_hours() -> None:
    """Most meters and loggers outside our samples are 15-minute or finer: the outlook takes them as is."""
    f = _plant(0.8, days=200)
    quarters = []
    for k in range(4):  # each hour split into four equal quarters
        q = f.assign(ds=f["ds"] + pd.Timedelta(minutes=15 * k), y=f["y"] / 4)
        quarters.append(q)
    q = pd.concat(quarters, ignore_index=True)
    s15 = EnergySeries.from_dataframe(q, unit="kWh", quantity="generation", tz=TZ, freq="15min")
    o15 = outlook.forecast_ahead(s15, days=3, site=SITE, tilt=15, azimuth=20)
    o1 = outlook.forecast_ahead(_series(f), days=3, site=SITE, tilt=15, azimuth=20)
    pd.testing.assert_frame_equal(o15.daily, o1.daily)
    assert any("steps of 15min: summed into hours" in n for n in o15.notes)
