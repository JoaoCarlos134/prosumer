"""Solar physics: checked against geometry with known answers, not against itself."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prosumer import physics

LAT, LON = -24.83, -53.65  # Cascavel (rounded, as in the project)


def _hours(start: str, days: int, tz: str = "America/Sao_Paulo") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=24 * days, freq="h", tz=tz)


def test_noon_zenith_is_latitude_minus_declination() -> None:
    t = pd.date_range("2025-06-21 10:00", "2025-06-21 14:00", freq="1min", tz="America/Sao_Paulo")
    p = physics.solar_position(t, LAT, LON)
    noon = p["cos_zenith"].idxmax()
    dec = p.loc[noon, "declination"]
    assert p.loc[noon, "cos_zenith"] == pytest.approx(np.cos(np.radians(LAT) - dec), abs=1e-4)
    assert abs(p.loc[noon, "hour_angle"]) < np.radians(0.5)  # within 2 min of solar noon
    assert p.loc[noon, "north"] > 0  # southern hemisphere in June: the sun is to the north


def test_the_time_zone_label_does_not_move_the_sun() -> None:
    t = _hours("2025-03-10", 2)
    a = physics.solar_position(t, LAT, LON)["cos_zenith"].to_numpy()
    b = physics.solar_position(t.tz_convert("UTC"), LAT, LON)["cos_zenith"].to_numpy()
    np.testing.assert_allclose(
        a, b, atol=1e-3
    )  # only the date terms differ (wall clock vs UTC, 3 h near equinox)


def test_clear_sky_is_zero_at_night_and_plausible_at_noon() -> None:
    t = _hours("2025-12-21", 1)
    g = physics.clear_sky_ghi(t, LAT, LON)
    assert g[:4].max() == 0.0 and g[22:].max() == 0.0
    assert 900 < g.max() < 1100
    assert int(np.argmax(g)) in (11, 12)


def test_naive_times_are_refused() -> None:
    with pytest.raises(ValueError, match="tz-aware"):
        physics.clear_sky_ghi(pd.date_range("2025-01-01", periods=3, freq="h"), LAT, LON)


def test_horizontal_plane_receives_ghi() -> None:
    t = _hours("2025-09-01", 1)
    sun = physics.mean_sun(t, LAT, LON)
    ghi = physics.clear_sky_ghi(t, LAT, LON) * 0.7
    poa = physics.poa_isotropic(ghi, sun, tilt=0.0, azimuth=0.0)
    up = sun["up"].to_numpy() > 0.02
    np.testing.assert_allclose(poa[up], ghi[up], rtol=1e-9)


def test_east_facing_panel_peaks_in_the_morning() -> None:
    t = _hours("2025-09-01", 1)
    sun = physics.mean_sun(t, LAT, LON)
    ghi = physics.clear_sky_ghi(t, LAT, LON)
    east = physics.poa_isotropic(ghi, sun, tilt=30, azimuth=90)
    west = physics.poa_isotropic(ghi, sun, tilt=30, azimuth=270)
    assert int(np.argmax(east)) < int(np.argmax(west))
    assert east[:12].sum() > west[:12].sum() and west[12:].sum() > east[12:].sum()


def test_fit_orientation_recovers_a_known_roof() -> None:
    t = _hours("2025-01-01", 60)
    sun = physics.mean_sun(t, LAT, LON)
    rng = np.random.default_rng(0)
    ghi = physics.clear_sky_ghi(t, LAT, LON) * rng.uniform(0.3, 1.0, len(t))  # cloudy days: real variety
    y = physics.poa_isotropic(ghi, sun, tilt=20, azimuth=30) * 0.004 + rng.normal(0, 0.02, len(t))
    r2, tilt, az = physics.fit_orientation(
        y, ghi, sun, tilts=np.arange(0, 41, 5.0), azimuths=np.arange(0, 360, 10.0)
    )
    assert r2 > 0.95
    assert tilt == pytest.approx(20, abs=5)
    assert min(abs(az - 30), 360 - abs(az - 30)) <= 10


@pytest.mark.parametrize("name", ["clear_sky_ghi", "mean_sun"])
def test_long_spans_are_remembered_by_their_instants_and_inputs(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`physics.MEMORY` (2026-10-21): the same long span is computed once; another instant, site or zone
    label of the same instants is computed again; a short span is never kept; a caller gets a copy."""
    from collections import OrderedDict

    calls: list[int] = []
    real = getattr(physics, f"_{name}")

    def counted(*a: object, **k: object) -> object:
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(physics, f"_{name}", counted)
    monkeypatch.setattr(physics, "_MEMORY", {"clear_sky": OrderedDict(), "sun": OrderedDict()})
    fn = getattr(physics, name)
    times = _hours("2024-01-01", 60)  # 1440 hours, above MEMORY_MIN_TIMES
    first = fn(times, LAT, LON)
    second = fn(times, LAT, LON)
    assert len(calls) == 1 and np.array_equal(np.asarray(first), np.asarray(second))
    if isinstance(second, pd.DataFrame):
        second.iloc[:, 0] = -1.0
    else:
        second[:] = -1.0
    assert np.array_equal(np.asarray(fn(times, LAT, LON)), np.asarray(first))  # the change did not reach it
    assert len(calls) == 1
    fn(times[1:].append(times[-1:] + pd.Timedelta(hours=1)), LAT, LON)  # one instant moved
    fn(times, LAT + 0.01, LON)
    fn(times.tz_convert("UTC"), LAT, LON)  # the same instants, another label: keyed apart (its index differs)
    assert len(calls) == 4
    fn(_hours("2024-01-01", 2), LAT, LON)
    fn(_hours("2024-01-01", 2), LAT, LON)
    assert len(calls) == 6  # 48 hours: below MEMORY_MIN_TIMES, never kept
