"""Clock check of a generation series against the sun (`prosumer.quality`)."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from prosumer import EnergySeries, analyze, data, physics
from prosumer.quality import clock_notes, clock_offset, clock_offset_weather, clock_weather_notes

SITE = (-24.83, -53.65)  # rounded, as everywhere in the project
TZ = "America/Sao_Paulo"


def _pv(
    *,
    tz: str = TZ,
    site: tuple[float, float] = SITE,
    days: int = 120,
    start: str = "2024-01-01",
    tilt: float = 20.0,
    azimuth: float = 0.0,
    seed: int = 0,
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Physical PV: clear sky x a daily clear-sky index on a tilted plane, with 10% hourly noise."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", tz=tz)
    ghi = physics.clear_sky_ghi(idx, *site) * np.repeat(rng.uniform(0.3, 1.0, days), 24)
    y = physics.poa_isotropic(ghi, physics.mean_sun(idx, *site), tilt, azimuth) / 1000
    return idx, np.clip(y * (1 + 0.1 * rng.standard_normal(len(idx))), 0, None)


def _series(ds: pd.DatetimeIndex | pd.Series, y: np.ndarray, tz: str = TZ, **kw: str) -> EnergySeries:
    frame = pd.DataFrame({"unique_id": "pv", "ds": ds, "y": y})
    return EnergySeries.from_dataframe(frame, unit="kWh", quantity="generation", tz=tz, freq="h", **kw)


def _whole(table: pd.DataFrame) -> pd.Series:
    return table[table["period"] == "all"].iloc[0]


@pytest.mark.parametrize("azimuth", [0.0, 90.0, 270.0])
def test_correct_clock_gives_zero_whatever_the_orientation(azimuth: float) -> None:
    idx, y = _pv(azimuth=azimuth, tilt=30.0)
    t = clock_offset(_series(idx, y), SITE)
    assert (t["offset_h"] == 0).all() and t["confident"].all()
    assert abs(_whole(t)["centroid_shift_h"]) < 0.3
    assert clock_notes(t) == []


@pytest.mark.parametrize("hours", [1, -3])
def test_shifted_series_is_detected(hours: int) -> None:
    idx, y = _pv()
    t = clock_offset(_series(idx + pd.Timedelta(hours=hours), y), SITE)
    r = _whole(t)
    assert r["offset_h"] == hours and r["confident"]
    assert (t["offset_h"] == hours).all()
    assert r["centroid_shift_h"] == pytest.approx(hours, abs=0.3)
    (note,) = clock_notes(t)
    assert f"shift the timestamps by {-hours:+d} h" in note


def test_utc_file_read_as_local_time_is_plus_three_hours() -> None:
    idx, y = _pv()
    utc_wall = idx.tz_convert("UTC").tz_localize(None)  # what a UTC export looks like
    t = clock_offset(_series(utc_wall, y), SITE)  # read as local (Sao Paulo) time
    assert _whole(t)["offset_h"] == 3


def test_logger_without_daylight_saving_shows_up_month_by_month() -> None:
    site = (52.14, -10.27)  # the Dingle peninsula (public CC0 houses), rounded
    idx, y = _pv(tz="Europe/Dublin", site=site, days=365, azimuth=180.0)
    # logged in GMT all year, read as Dublin local time: one hour early in summer, right in winter
    gmt_wall = idx.tz_convert("UTC").tz_localize(None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # the hour that does not exist in spring is dropped
        s = _series(gmt_wall, y, tz="Europe/Dublin", dst="drop")
    t = clock_offset(s, site)
    month = t[t["confident"] & (t["period"] != "all")].set_index("period")["offset_h"]
    assert month["2024-01"] == 0 and month["2024-12"] == 0
    assert month["2024-06"] == -1 and month["2024-08"] == -1
    (note,) = clock_notes(t)
    assert "changes over the year" in note and "-1 h" in note and "+0 h" in note
    # the correct series in the same zone is right in every month
    assert (clock_offset(_series(idx, y, tz="Europe/Dublin"), site)["offset_h"] == 0).all()


def test_noise_is_not_confident_and_gives_no_note() -> None:
    idx = pd.date_range("2024-01-01", periods=60 * 24, freq="h", tz=TZ)
    y = np.random.default_rng(1).uniform(0, 1, len(idx))
    t = clock_offset(_series(idx, y), SITE)
    assert not t["confident"].any()
    assert clock_notes(t) == []


def test_consumption_is_refused() -> None:
    with pytest.raises(ValueError, match="generation"):
        clock_offset(data.example_house(days=10), SITE)


def test_analyze_reports_the_clock_and_notes_an_offset() -> None:
    s, _ = data.example_plant()
    r = analyze(s, site=(-25.43, -49.27), test_days=14)
    assert r.clock is not None and (r.clock["offset_h"] == 0).all()
    assert not any("clock" in n or "than the sun" in n for n in r.notes)
    assert "### Clock against the sun" in r.to_markdown()
    assert r.to_dict()["clock"]

    idx, y = _pv(days=40)
    late = analyze(_series(idx + pd.Timedelta(hours=2), y), site=SITE, test_days=7)
    assert any("2 h later than the sun" in n for n in late.notes)
    assert analyze(s, test_days=14).clock is None  # no site, no clock check


# ------------------------------------------------------------ clock against the weather (clouds)
def _cloudy(days: int = 90, tilt: float = 20.0, azimuth: float = 0.0, seed: int = 2):
    """5-min truth: clear sky x a cloud index with ~1 h memory; returns the 5-min GHI and PV (true clock)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-03-01", periods=days * 288, freq="5min", tz=TZ)
    e = rng.standard_normal(len(idx))
    k = np.empty(len(idx))
    k[0] = 0.0
    for i in range(1, len(idx)):  # AR(1), time constant ~1 h
        k[i] = 0.92 * k[i - 1] + 0.4 * e[i]
    kt = np.clip(0.65 + 0.25 * k, 0.05, 1.0)
    ghi = physics.clear_sky_ghi(idx, *SITE, interval="300s") * kt
    pv = physics.poa_isotropic(ghi, physics.mean_sun(idx, *SITE, interval="300s"), tilt, azimuth) / 1000
    return pd.Series(ghi, idx), pd.Series(pv, idx)


def _hourly(s: pd.Series, late_min: int = 0) -> pd.Series:
    """Hourly mean labelled by the START, with the labels `late_min` minutes late."""
    return s.shift(late_min // 5).resample("h").mean().dropna()


def _weather(ghi: pd.Series, noise: float = 0.15, seed: int = 3) -> pd.DataFrame:
    """A forecast-like hourly GHI: the true clouds with multiplicative noise."""
    h = _hourly(ghi)
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"ds": h.index, "ghi": h.to_numpy() * (1 + noise * rng.standard_normal(len(h)))})


@pytest.mark.parametrize("late_min", [0, 30, -60])
def test_weather_clock_finds_fractions_of_an_hour(late_min: int) -> None:
    ghi, pv = _cloudy()
    h = _hourly(pv, late_min)
    t = clock_offset_weather(_series(h.index, h.to_numpy()), _weather(ghi))
    r = _whole(t)
    assert r["offset_h"] == pytest.approx(late_min / 60, abs=0.15)
    assert r["confident"] and r["low_h"] <= late_min / 60 + 0.15 and r["high_h"] >= late_min / 60 - 0.15
    notes = clock_weather_notes(t)
    if late_min == 0:
        assert notes == []
    else:
        (note,) = notes
        assert f"{abs(late_min) / 60:.1f} h {'later' if late_min > 0 else 'earlier'}" in note


def test_weather_clock_ignores_the_orientation() -> None:
    """A west-facing roof skews the daily shape (the sun check's blind spot), not the timing of the clouds."""
    ghi, pv = _cloudy(azimuth=270.0, tilt=40.0)
    h = _hourly(pv)
    r = _whole(clock_offset_weather(_series(h.index, h.to_numpy()), _weather(ghi)))
    assert abs(r["offset_h"]) < 0.15 and r["confident"]


def test_weather_clock_without_clouds_is_not_confident() -> None:
    """Clear sky as the 'weather' has no passing clouds to line up: no confident answer, no note."""
    _, pv = _cloudy(days=60)
    h = _hourly(pv)
    idx = h.index
    clear = pd.DataFrame({"ds": idx, "ghi": physics.clear_sky_ghi(idx, *SITE)})
    t = clock_offset_weather(_series(idx, h.to_numpy()), clear)
    assert not t["confident"].any() and clock_weather_notes(t) == []


def test_weather_clock_checks_its_inputs() -> None:
    ghi, pv = _cloudy(days=10)
    h = _hourly(pv)
    s = _series(h.index, h.to_numpy())
    w = _weather(ghi)
    with pytest.raises(ValueError, match="generation"):
        clock_offset_weather(data.example_house(days=10), w)
    with pytest.raises(ValueError, match="time zone"):
        clock_offset_weather(s, w.assign(ds=w["ds"].dt.tz_localize(None)))
    with pytest.raises(ValueError, match="'ghi_mean'"):
        clock_offset_weather(s, w, column="ghi_mean")


def test_analyze_reports_the_clock_against_the_weather() -> None:
    ghi, pv = _cloudy(days=60)
    h = _hourly(pv, 30)
    w = _weather(ghi).rename(columns={"ghi": "ghi_mean"})
    r = analyze(_series(h.index, h.to_numpy()), site=SITE, test_days=7, weather=w)
    assert r.clock_weather is not None
    assert _whole(r.clock_weather)["offset_h"] == pytest.approx(0.5, abs=0.15)
    assert any("follows the clouds 0.5 h later" in n for n in r.notes)
    assert "### Clock against the weather" in r.to_markdown()
    assert r.to_dict()["clock_weather"]
    assert analyze(_series(h.index, h.to_numpy()), site=SITE, test_days=7).clock_weather is None


# ------------------------------------------------------------ declared thresholds (nothing tuned in hiding)
def test_clock_thresholds_are_arguments_with_the_old_defaults() -> None:
    """`min_agreement`, `daylight_share` and `interval` were constants; as arguments their defaults give the
    same table, and a different value changes it."""
    from prosumer import quality

    assert (quality.MIN_AGREEMENT, quality.DAYLIGHT_SHARE, quality.INTERVAL) == (0.5, 0.05, 0.90)
    idx, y = _pv(days=60, seed=4)
    noisy = y * np.random.default_rng(5).uniform(0.2, 1.8, len(y))  # some days disagree
    s = _series(idx + pd.Timedelta(hours=1), noisy)
    base = clock_offset(s, SITE)
    pd.testing.assert_frame_equal(base, clock_offset(s, SITE, min_agreement=0.5))
    assert base["agreement"].between(0.3, 0.95).any()
    for m in (0.3, 0.7, 0.95):
        t = clock_offset(s, SITE, min_agreement=m)
        assert (t["confident"] == ((t["days"] >= 7) & (t["agreement"] >= m))).all()
    with pytest.raises(ValueError, match="min_agreement"):
        clock_offset(s, SITE, min_agreement=0)

    ghi, pv = _cloudy(days=40)
    h = _hourly(pv, 30)
    sw, w = _series(h.index, h.to_numpy()), _weather(ghi)
    t = clock_offset_weather(sw, w)
    pd.testing.assert_frame_equal(t, clock_offset_weather(sw, w, daylight_share=0.05, interval=0.9))
    narrow = _whole(clock_offset_weather(sw, w, interval=0.5))
    assert narrow["high_h"] - narrow["low_h"] < _whole(t)["high_h"] - _whole(t)["low_h"]
    assert _whole(clock_offset_weather(sw, w, daylight_share=0.5))["days"] <= _whole(t)["days"]
    with pytest.raises(ValueError, match="interval"):
        clock_offset_weather(sw, w, interval=1.0)


def test_analyze_passes_the_clock_options_by_name() -> None:
    idx, y = _pv(days=40)
    s = _series(idx + pd.Timedelta(hours=2), y)
    r = analyze(s, site=SITE, test_days=7, clock_options={"by": None})
    assert list(r.clock["period"]) == ["all"]  # no month rows
    with pytest.raises(ValueError, match="Unknown clock_options"):
        analyze(s, site=SITE, test_days=7, clock_options={"site": SITE})
    with pytest.raises(ValueError, match="Unknown clock_weather_options"):
        analyze(s, site=SITE, test_days=7, clock_weather_options={"column": "ghi"})
