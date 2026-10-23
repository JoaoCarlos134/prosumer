"""Solar physics in plain numpy: sun position, clear-sky irradiance and irradiance on the panel plane.

Until 2026-10-11 the project had four copies of this (`legado/.../solar.py`, the benchmark's
`comum.ghi_ceu_claro`, `piloto_geometria.py` and a placeholder in `data`). This module replaces them. It is
numpy only on purpose: pvlib (with NREL's SPA, more accurate) is an optional extra, and the frozen benchmark
environments do not have it.

Conventions
- Times are tz-aware. The hour angle comes from UTC; the date terms (day of year and the fractional year
  of the Spencer series) use the wall clock of the given time zone, exactly as the v2 benchmark did. Passing
  UTC times gives the textbook form; the difference grows with the UTC offset: about 0.05 degree of
  declination for 3 h near the equinox (cos(zenith) changes by < 1e-3), negligible for hourly energy.
- Interval values (hourly energy, hourly irradiance) are labelled by the START of the interval and computed as
  the mean of `samples` instants at the middle of equal sub-intervals (12 x 5 min for an hour).
- Azimuth is a compass bearing: 0 = north, 90 = east, 180 = south, 270 = west (pvlib's convention). Tilt in
  degrees from horizontal. The legacy `solar.py` measured azimuth from the south (180 = north): convert before
  comparing.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import numpy as np
import pandas as pd

SOLAR_CONSTANT = 1367.0  # W/m2


def _instants(times: pd.DatetimeIndex, interval: pd.Timedelta, samples: int) -> pd.DatetimeIndex:
    """Mid-points of `samples` equal sub-intervals inside each [t, t + interval)."""
    if times.tz is None:
        raise ValueError("times must be tz-aware (the hour angle needs UTC)")
    sub = interval / samples
    offsets = pd.to_timedelta(np.arange(samples) * sub.value + sub.value // 2, unit="ns").to_numpy()
    utc = times.tz_convert("UTC").tz_localize(None).to_numpy()  # naive: datetime64, never object
    return pd.DatetimeIndex((utc[:, None] + offsets[None, :]).ravel()).tz_localize("UTC").tz_convert(times.tz)


def solar_position(times: pd.DatetimeIndex, lat: float, lon: float) -> pd.DataFrame:
    """Instantaneous sun position (Spencer series). Columns: `day_of_year`, `declination` and `hour_angle`
    (radians), `cos_zenith` and the unit sun vector `east`, `north`, `up` (zero below the horizon is NOT
    applied here). `lon` is negative west of Greenwich."""
    local = times
    n = local.day_of_year.to_numpy()
    g = 2 * np.pi / 365 * (n - 1 + (local.hour.to_numpy() - 12) / 24)
    eot = 229.18 * (
        0.000075
        + 0.001868 * np.cos(g)
        - 0.032077 * np.sin(g)
        - 0.014615 * np.cos(2 * g)
        - 0.040849 * np.sin(2 * g)
    )
    dec = (
        0.006918
        - 0.399912 * np.cos(g)
        + 0.070257 * np.sin(g)
        - 0.006758 * np.cos(2 * g)
        + 0.000907 * np.sin(2 * g)
        - 0.002697 * np.cos(3 * g)
        + 0.00148 * np.sin(3 * g)
    )
    # minutes since local midnight converted to UTC by the offset, not wrapped at 24 h: same angle, and the
    # exact arithmetic of the v2 benchmark (so its clear-sky inputs stay bit-identical)
    offset = (
        (local.tz_localize(None) - local.tz_convert("UTC").tz_localize(None)) / pd.Timedelta(minutes=1)
    ).to_numpy()
    minutes = (local.hour.to_numpy() * 60 - offset) + local.minute.to_numpy() + local.second.to_numpy() / 60
    w = np.radians((minutes + eot + 4 * lon) / 4 - 180)
    la = np.radians(lat)
    up = np.sin(la) * np.sin(dec) + np.cos(la) * np.cos(dec) * np.cos(w)
    return pd.DataFrame(
        {
            "day_of_year": n,
            "declination": dec,
            "hour_angle": w,
            "cos_zenith": up,
            "east": -np.cos(dec) * np.sin(w),
            "north": np.cos(la) * np.sin(dec) - np.sin(la) * np.cos(dec) * np.cos(w),
            "up": up,
        },
        index=times,
    )


# the last results of `clear_sky_ghi` and `mean_sun` on long time spans, by their inputs: one app run asks
# for the same 60,000 hours from the reader, the next days and the diagnostics
MEMORY = 6
MEMORY_MIN_TIMES = 1000  # shorter spans are cheap to recompute (and would push the long ones out)
_MEMORY: dict[str, OrderedDict[tuple[Any, ...], Any]] = {"clear_sky": OrderedDict(), "sun": OrderedDict()}
_MEMORY_LOCK = threading.Lock()
_T = TypeVar("_T", np.ndarray, pd.DataFrame)


def _remembered(kind: str, times: pd.DatetimeIndex, key: tuple[Any, ...], compute: Callable[[], _T]) -> _T:
    """`compute()`, or a copy of its remembered result for the same `times` (every instant and the zone) and
    `key`; a remembered frame takes the caller's `times` as its index (its name and freq may differ)."""
    if len(times) < MEMORY_MIN_TIMES:
        return compute()
    ints = np.ascontiguousarray(times.asi8)  # type: ignore[attr-defined]
    stamp = hashlib.blake2b(ints.tobytes(), digest_size=16).digest()
    full = (len(times), str(times.dtype), stamp, *key)  # the dtype carries the zone and the unit
    cache = _MEMORY[kind]
    with _MEMORY_LOCK:
        hit = cache.get(full)
        if hit is not None:
            cache.move_to_end(full)
            out = hit.copy()
            if isinstance(out, pd.DataFrame):
                out.index = times
            return out
    out = compute()
    with _MEMORY_LOCK:
        cache[full] = out.copy()
        while len(cache) > MEMORY:
            cache.popitem(last=False)
    return out


def clear_sky_ghi(
    times: pd.DatetimeIndex, lat: float, lon: float, *, interval: str = "1h", samples: int = 12
) -> np.ndarray:
    """Clear-sky global horizontal irradiance (Haurwitz), mean over each interval, W/m2.

    Haurwitz needs only the zenith angle: GHI = 1098 cos z exp(-0.059 / cos z). It is the model the project
    used for the clear-sky persistence reference and for the clear-sky index of the weather forecast (regime
    C). The last results on long spans are remembered (`MEMORY`).
    """
    span = pd.Timedelta(interval)
    key = (float(lat), float(lon), span, int(samples))
    return _remembered("clear_sky", times, key, lambda: _clear_sky_ghi(times, lat, lon, span, samples))


def _clear_sky_ghi(
    times: pd.DatetimeIndex, lat: float, lon: float, span: pd.Timedelta, samples: int
) -> np.ndarray:
    inst = _instants(times, span, samples)
    cz = solar_position(inst, lat, lon)["cos_zenith"].to_numpy()
    czp = np.clip(cz, 1e-3, None)
    ghi = np.where(cz > 0, 1098.0 * czp * np.exp(-0.059 / czp), 0.0).reshape(len(times), samples)
    # compensated (Kahan) sum, the algorithm of pandas' grouped mean used by the benchmark: bit-identical
    # results
    total, comp = np.zeros(len(times)), np.zeros(len(times))
    for k in range(samples):
        y = ghi[:, k] - comp
        t = total + y
        comp = (t - total) - y
        total = t
    return total / samples


def mean_sun(
    times: pd.DatetimeIndex, lat: float, lon: float, *, interval: str = "1h", samples: int = 12
) -> pd.DataFrame:
    """Mean over each interval of the sun vector while the sun is up (`east`, `north`, `up`), plus
    `day_of_year`.

    The mean of `up` is the mean cos(zenith) counting the night as zero, which is what an hourly energy sees.
    The last results on long spans are remembered (`MEMORY`).
    """
    span = pd.Timedelta(interval)
    key = (float(lat), float(lon), span, int(samples))
    return _remembered("sun", times, key, lambda: _mean_sun(times, lat, lon, span, samples))


def _mean_sun(
    times: pd.DatetimeIndex, lat: float, lon: float, span: pd.Timedelta, samples: int
) -> pd.DataFrame:
    p = solar_position(_instants(times, span, samples), lat, lon)
    above = (p["up"].to_numpy() > 0)[:, None]
    v = (p[["east", "north", "up"]].to_numpy() * above).reshape(len(times), samples, 3).mean(axis=1)
    out = pd.DataFrame(v, index=times, columns=["east", "north", "up"])
    out["day_of_year"] = p["day_of_year"].to_numpy().reshape(len(times), samples)[:, 0]
    return out


def erbs_diffuse_fraction(kt: np.ndarray) -> np.ndarray:
    """Diffuse fraction of GHI from the clearness index (Erbs, Klein and Duffie, 1982)."""
    kt = np.asarray(kt, dtype=float)
    return np.where(
        kt <= 0.22,
        1 - 0.09 * kt,
        np.where(kt <= 0.8, 0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4, 0.165),
    )


def poa_isotropic(
    ghi: np.ndarray, sun: pd.DataFrame, tilt: float, azimuth: float, *, albedo: float = 0.2
) -> np.ndarray:
    """Irradiance on a tilted plane from measured GHI: Erbs split + isotropic sky (Liu-Jordan) + ground
    reflection.

    `sun` is the output of `mean_sun` for the same intervals. Tilt and azimuth in degrees (azimuth as a
    compass bearing). Simple on purpose: with one GHI channel there is nothing to feed a richer sky model.
    """
    return _poa_on(_PoaParts.of(ghi, sun, albedo), tilt, azimuth)


@dataclass(frozen=True)
class _PoaParts:
    """What `poa_isotropic` computes whatever the plane: the sun vectors, the Erbs split of the GHI and the
    ground term, so a grid search (`fit_orientation`) computes them once, not once per plane."""

    vectors: np.ndarray  # east, north, up of the sun
    sunny: np.ndarray  # cos zenith > 0.02: the beam counts
    cos_zenith: np.ndarray  # where `sunny`, else 1 (the divisor of the beam's tilt factor)
    beam: np.ndarray
    diffuse: np.ndarray
    ground: np.ndarray  # albedo x GHI

    @classmethod
    def of(cls, ghi: np.ndarray, sun: pd.DataFrame, albedo: float) -> _PoaParts:
        ghi = np.asarray(ghi, dtype=float)
        cz = np.clip(sun["up"].to_numpy(), 0, None)
        doy = sun["day_of_year"].to_numpy()
        i0 = SOLAR_CONSTANT * (1 + 0.033 * np.cos(2 * np.pi * doy / 365)) * cz
        kt = np.where(i0 > 10, np.clip(ghi / np.where(i0 > 10, i0, 1), 0, 1), 0)
        diffuse = ghi * erbs_diffuse_fraction(kt)
        return cls(
            vectors=sun[["east", "north", "up"]].to_numpy(),
            sunny=cz > 0.02,
            cos_zenith=np.where(cz > 0.02, cz, 1),
            beam=np.clip(ghi - diffuse, 0, None),
            diffuse=diffuse,
            ground=albedo * ghi,
        )


def _poa_on(parts: _PoaParts, tilt: float, azimuth: float) -> np.ndarray:
    """`poa_isotropic` on one plane from its plane-independent parts (the same arithmetic, in the same
    order: bit-identical)."""
    b, g = np.radians(tilt), np.radians(azimuth)
    normal = np.array([np.sin(b) * np.sin(g), np.sin(b) * np.cos(g), np.cos(b)])
    ci = np.clip(parts.vectors @ normal, 0, None)
    rb = np.where(parts.sunny, ci / parts.cos_zenith, 0)
    return parts.beam * rb + parts.diffuse * (1 + np.cos(b)) / 2 + parts.ground * (1 - np.cos(b)) / 2


def fit_orientation(
    y: np.ndarray,
    ghi: np.ndarray,
    sun: pd.DataFrame,
    *,
    tilts: np.ndarray | None = None,
    azimuths: np.ndarray | None = None,
    min_ghi: float = 50.0,
) -> tuple[float, float, float]:
    """Panel orientation that best explains the production: grid search for the max R2 between `y` and the
    POA.

    Returns (R2, tilt, azimuth). Only intervals with GHI above `min_ghi` and finite `y` count. A result on the
    edge of the grid means the data do not identify the orientation (the house pilot of 2026-10-11 hit 60
    degrees in 8 of 10 houses with one shared weather station): report it, do not extend the grid until it
    "fits".
    """
    tilts = np.arange(0, 61, 5.0) if tilts is None else np.asarray(tilts, dtype=float)
    # the whole circle: a grid of 90..270 (east through south to west) silently misses every north-facing
    # roof of the southern hemisphere (Cascavel, 13 degrees facing 25, came out 5 degrees facing east)
    azimuths = np.arange(0, 360, 10.0) if azimuths is None else np.asarray(azimuths, dtype=float)
    y, ghi = np.asarray(y, dtype=float), np.asarray(ghi, dtype=float)
    ok = np.isfinite(y) & (ghi > min_ghi)
    s = sun.loc[ok] if isinstance(sun, pd.DataFrame) else sun
    parts = _PoaParts.of(ghi[ok], s, 0.2)  # what does not depend on the plane, once
    best = (-1.0, 0.0, 180.0)
    for t in tilts:
        for a in azimuths if t > 0 else [180.0]:
            p = _poa_on(parts, t, a)
            r2 = float(np.corrcoef(p, y[ok])[0, 1] ** 2)
            if r2 > best[0]:
                best = (r2, float(t), float(a))
    return best
