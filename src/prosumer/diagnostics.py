"""Diagnostics of a PV series from its energy alone: how well it performs on clear days, and when that
changed.

Most prosumers have only what the inverter logs: energy per hour, no irradiance sensor, often no roof
geometry. The project's original analyses used 5-minute DC current and voltage and a known roof
(`legado/ia_solar/analise/`); this module keeps what still works with hourly AC energy and a site:

1. **Clear days, without a sensor** (`clear_days`): the day's energy over the clear-sky irradiance of the day,
   clear when it reaches 0.9 x the 90th percentile of a centred 31-day window. The series says itself which
   days were cloudless; soiling moves the level slowly, the window follows it.
2. **Roof orientation** (`roof_orientation`): on clear days the production follows the clear-sky irradiance on
   the panel plane, so `physics.fit_orientation` (whole compass) finds the plane; the next passes divide out
   the level between the large steps, so that a fault or a cleaning does not bend the fit.
3. **Performance index** (`performance_index`): each clear day's energy over its expected energy on that
   plane. With the peak power (`kwp`) it is a performance ratio against clear sky (a healthy array is
   ~0.75-0.85); without it, the effective peak power in kW.
4. **Change points** (`changepoints`): the index as a straight line per segment, the segments chosen by
   exact dynamic programming and a BIC with 3 x its usual penalty (the daily index is not independent noise:
   with the plain BIC the plants got 9 and 11 steps, most of them seasonal). Soiling is a sawtooth (a slow
   decline, a step up at the cleaning), so each segment has its own slope, and the steps are the events.

Pilot (`experimentos/testes_previsao/scripts/piloto_diagnostico.py --biblioteca`, 2026-10-12, details in
`docs/projeto/PILOTOS_F1_F2.md`): the gate, written before the run, asked for five events the 5-minute DC
analysis had found on the benchmark's two plants. With the penalty factor 3 it finds four, within a month: the
Cascavel cleanings of November 2023 (+24%) and September 2024 (dated 2024-08-12, +10%), and nothing else
there; the Curitiba string fault of December 2022 (-17%) and its repair in July 2023 (dated 2023-08-02). It
misses the Curitiba reconfiguration of June 2025, which factor 2 finds (+15%, 2025-07-29) at the cost of three
more steps on the plants and eight on the ten PV houses of the Dingle data (none known there; factor 3 gives
one). The factor was chosen on these same plants and houses. Limits: a roof of several unlike planes fits one
plane poorly (Curitiba R2 0.81) and leaves a seasonal residual that the segmentation reads as extra steps
(Curitiba: +27% in February 2024, +19% in December 2024), and step sizes there are not reliable; the notes
then call every step uncertain and report no trend or loss. Telling soiling from shading or a string fault
needs sub-hourly or DC data (not here yet).

**Tuning.** Every threshold below is a keyword argument of `diagnose` (and of `roof_orientation` and
`performance_index`; `analyze(diagnostics_options={...})` passes them through), with the module constant as
its default. Where each default comes from:

- CHOSEN on the project's own sites: `penalty` (the factor sweep above, on the two plants in Parana, Brazil,
  checked for false alarms on the ten PV houses of Dingle, Ireland). Elsewhere it is an assumption; no site
  that did not serve to choose it has checked it yet.
- SET BY HAND on those two plants for the pilot, never swept and not checked elsewhere: the clear-day rule
  (`clear_window_days`, `clear_quantile`, `clear_ratio`), the segment size (`min_segment_days`,
  `max_breaks`) and `good_fit_r2` (the two plants fall either side of it: Cascavel 0.93, Curitiba 0.81).
- Generic, not fitted to any data: what is worth a note (`step_note_pct`, `trend_note_pct`), the search grid
  (`tilts` 0-60 degrees, `azimuths` the whole compass), `dead_level` and `roof_passes`.

The default tilt grid stops at 60 degrees: panels on a facade or a balcony rail (up to 90) need a wider one,
e.g. `tilts=np.arange(0, 91, 5.0)`. Whatever the grid, a fit on its steepest tilt is reported as on the edge
(not identified; `Diagnosis.orientation.edge`), except at 90 degrees, which, like 0 (flat), is a physical
limit and so a possible answer. Widen the grid for panels that may be that steep, not to chase a better R2.
"""

from __future__ import annotations

import hashlib
import itertools
import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from typing import Any, cast

import numpy as np
import pandas as pd

from . import physics
from .contracts import EnergySeries
from .i18n import Note, translate

# The defaults of the tuning arguments (see "Tuning" above for where each comes from).
CLEAR_WINDOW_DAYS = 31  # set by hand on the two plants: days of the centred window of the clear-day rule
CLEAR_QUANTILE = 0.9  # set by hand on the two plants: the window's quantile a clear day is compared with
CLEAR_RATIO = 0.9  # set by hand on the two plants: a clear day reaches this share of that quantile
MIN_SEGMENT_DAYS = 15  # set by hand: clear days per segment (about one to two months)
MAX_BREAKS = 11  # set by hand: up to 12 segments
# CHOSEN on the two plants and the ten Dingle PV houses (factors 1, 2, 3, 4, 6 swept, see above): multiplies
# the BIC penalty, the daily index is not independent noise (see `changepoints`)
PENALTY = 3.0
# set by hand (Cascavel 0.93, Curitiba 0.81 fall either side): below it one plane does not describe the roof
GOOD_FIT_R2 = 0.85
STEP_NOTE_PCT = 5.0  # generic: steps smaller than this are not worth a note
TREND_NOTE_PCT = 5.0  # generic: %/year
TILTS = np.arange(0, 61, 5.0)  # generic grid; no facade or balcony panels (see "Tuning")
DEAD_LEVEL = 0.05  # generic: relative level below which a stretch counts as dead in the refit
ROOF_PASSES = 4  # generic: refits of the orientation with the segment levels divided out
AZIMUTHS = np.arange(0, 360, 10.0)  # generic: the whole compass (north-facing roofs in the south)
VERTICAL = 90.0  # a fit at this tilt is not "on the edge": nothing steeper exists


@dataclass(frozen=True)
class _Knobs:
    """The tuning arguments of `diagnose`, carried together through the private steps."""

    clear_window_days: int = CLEAR_WINDOW_DAYS
    clear_quantile: float = CLEAR_QUANTILE
    clear_ratio: float = CLEAR_RATIO
    dead_level: float = DEAD_LEVEL
    tilts: tuple[float, ...] = tuple(float(t) for t in TILTS)
    azimuths: tuple[float, ...] = tuple(float(a) for a in AZIMUTHS)
    roof_passes: int = ROOF_PASSES
    min_segment_days: int = MIN_SEGMENT_DAYS
    max_breaks: int = MAX_BREAKS
    penalty: float = PENALTY
    step_note_pct: float = STEP_NOTE_PCT
    good_fit_r2: float = GOOD_FIT_R2
    trend_note_pct: float = TREND_NOTE_PCT

    def __post_init__(self) -> None:
        for name in ("tilts", "azimuths"):
            grid = tuple(float(v) for v in np.asarray(getattr(self, name), dtype=float).ravel())
            if not grid or not np.isfinite(grid).all():
                raise ValueError(f"{name} must be a non-empty grid of finite degrees")
            object.__setattr__(self, name, grid)
        if not all(0 <= t <= VERTICAL for t in self.tilts):
            raise ValueError("tilts must be within 0-90 degrees")
        checks = {
            "clear_window_days >= 1": self.clear_window_days >= 1,
            "0 < clear_quantile <= 1": 0 < self.clear_quantile <= 1,
            "clear_ratio > 0": self.clear_ratio > 0,
            "dead_level >= 0": self.dead_level >= 0,
            "roof_passes >= 0": self.roof_passes >= 0,
            "min_segment_days >= 2": self.min_segment_days >= 2,
            "max_breaks >= 0": self.max_breaks >= 0,
            "penalty > 0": self.penalty > 0,
            "step_note_pct >= 0": self.step_note_pct >= 0,
            "trend_note_pct >= 0": self.trend_note_pct >= 0,
            "0 <= good_fit_r2 <= 1": 0 <= self.good_fit_r2 <= 1,
        }
        bad = [rule for rule, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"Diagnostics options out of range: {', '.join(bad)}")

    def edge(self, tilt: float) -> bool:
        """The fit is on the steepest tilt of the grid: not identified (unless 90, a physical limit)."""
        steepest = max(self.tilts)
        return bool(tilt == steepest and steepest < VERTICAL)


_DEFAULT = _Knobs()
OPTIONS = tuple(f.name for f in fields(_Knobs))  # the tuning keyword arguments, by name


def _knobs(options: Mapping[str, Any]) -> _Knobs:
    """The tuning arguments from a mapping of their names (`analyze(diagnostics_options=...)`)."""
    unknown = sorted(set(options) - set(OPTIONS))
    if unknown:
        raise ValueError(f"Unknown diagnostics options {unknown}; the options are {list(OPTIONS)}")
    return _Knobs(**options)


@dataclass
class Diagnosis:
    """What `diagnose` returns: one table per stage and plain-language notes.

    `to_dict` leaves out the daily `index` table (hundreds of rows per series): the app plots it from
    `Diagnosis.index`. `edge` flags only the steepest tilt of the grid; a fit at 0 degrees is a flat roof,
    and one at 90 (with a grid that reaches it) a vertical panel, both possible answers.
    """

    # unique_id, tilt, azimuth, r2, edge (orientation on the edge of the grid), reliable (good enough for the
    # steps, a trend and a loss to be reported: given, or fitted with good_fit_r2 and not on the edge)
    orientation: pd.DataFrame
    index: pd.DataFrame  # unique_id, date, energy, expected, index (clear days only)
    # unique_id, start, end, days, level_start, level_end, trend_pct_per_year, lost_pct, trend_reported and
    # loss_reported (True where the notes report them: a series' last period only)
    segments: pd.DataFrame
    steps: pd.DataFrame  # unique_id, date, before, after, step_pct, event (|step| >= 5%)
    kwp: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self, lang: str | None = "en") -> dict[str, Any]:
        """JSON-friendly version (dates as text); `lang`: the language of the notes, "en" or "pt"
        (`prosumer.i18n`), None keeps each one a `Note`."""

        def records(df: pd.DataFrame) -> list[dict[str, Any]]:
            out = df.copy()
            for c in out.columns:
                if pd.api.types.is_datetime64_any_dtype(out[c]):
                    out[c] = out[c].dt.strftime("%Y-%m-%d")
            return [{str(k): _plain(v) for k, v in r.items()} for r in out.to_dict(orient="records")]

        out = {
            "orientation": records(self.orientation),
            "segments": records(self.segments),
            "steps": records(self.steps),
            "kwp": dict(self.kwp),
            "notes": list(self.notes),
        }
        return out if lang is None else cast(dict[str, Any], translate(out, lang))


def _check(series: EnergySeries) -> EnergySeries:
    if series.quantity != "generation":
        raise ValueError(f"Diagnostics are for generation series, not {series.quantity!r}")
    s = series.to_kwh()
    if s.freq != "h":
        raise ValueError(
            f"Diagnostics need an hourly series, not freq={s.freq!r}; use `series.resample('h')`"
        )
    return s


def _hourly(s: EnergySeries, site: tuple[float, float]) -> pd.DataFrame:
    """Long frame with y (NaN where invalid), the clear-sky GHI and the local date."""
    f = s.frame[["unique_id", "ds", "y", "valid"]].copy()
    f["y"] = f["y"].where(f["valid"])
    times = pd.DatetimeIndex(f["ds"].unique())
    cs = pd.Series(physics.clear_sky_ghi(times, *site), index=times)
    f["cs"] = cs.reindex(pd.DatetimeIndex(f["ds"])).to_numpy()
    f["date"] = pd.DatetimeIndex(f["ds"]).tz_localize(None).normalize()
    return f


def _complete_days(f: pd.DataFrame) -> pd.DataFrame:
    """Per series and day: energy and clear-sky total over the days with every sun hour measured."""
    sun = f[f["cs"] > 0]
    g = sun.assign(_missing=sun["y"].isna()).groupby(["unique_id", "date"])
    d = g.agg(energy=("y", "sum"), cs=("cs", "sum"), missing=("_missing", "sum"))
    return d[(d["missing"] == 0) & (d["cs"] > 0)].drop(columns="missing").reset_index()


def clear_days(
    series: EnergySeries,
    site: tuple[float, float],
    *,
    window_days: int = CLEAR_WINDOW_DAYS,
    quantile: float = CLEAR_QUANTILE,
    ratio: float = CLEAR_RATIO,
    dead_level: float = DEAD_LEVEL,
) -> pd.DataFrame:
    """Days of each series that were (nearly) cloudless, judged from the production itself.

    Returns `unique_id, date, ratio, top, clear`: `ratio` is the day's energy over the clear-sky GHI of the
    day (only days with every sun hour measured), `top` the `quantile` of that ratio in a centred window of
    `window_days` calendar days, and `clear` = `ratio >= ratio x top`. A stretch whose `top` is below
    `dead_level` x the series' usual `top` (its 95% quantile) is dead (an inverter off) and has no clear day.
    The defaults were set by hand on the two plants of the pilot (module docstring, "Tuning").
    """
    s = _check(series)
    k = _Knobs(
        clear_window_days=window_days, clear_quantile=quantile, clear_ratio=ratio, dead_level=dead_level
    )
    return _clear_k(_complete_days(_hourly(s, site)), k)


def _clear_k(d: pd.DataFrame, k: _Knobs) -> pd.DataFrame:
    return _clear(d, k.clear_window_days, k.clear_quantile, k.clear_ratio, dead_level=k.dead_level)


def _clear(
    d: pd.DataFrame, window_days: int, quantile: float, ratio: float, *, dead_level: float = DEAD_LEVEL
) -> pd.DataFrame:
    out = []
    for uid, g in d.groupby("unique_id", sort=False):
        r = (g.set_index("date")["energy"] / g.set_index("date")["cs"]).sort_index()
        daily = r.reindex(pd.date_range(r.index.min(), r.index.max(), freq="D"))
        top = daily.rolling(window_days, center=True, min_periods=max(3, window_days // 3)).quantile(quantile)
        t = pd.DataFrame({"unique_id": uid, "date": r.index, "ratio": r.to_numpy()})
        t["top"] = top.reindex(r.index).to_numpy()
        # a stretch where even the best days produce ~nothing (dead inverter) has no clear days: 0 >= 0.9 x 0
        alive = (
            t["top"] >= dead_level * float(np.nanquantile(t["top"], 0.95))
            if t["top"].notna().any()
            else False
        )
        t["clear"] = (t["ratio"] >= ratio * t["top"]) & alive & (t["ratio"] > 0)
        out.append(t)
    if not out:
        return pd.DataFrame(columns=["unique_id", "date", "ratio", "top", "clear"])
    return pd.concat(out, ignore_index=True)


def roof_orientation(
    series: EnergySeries, site: tuple[float, float], *, clear: pd.DataFrame | None = None, **options: Any
) -> pd.DataFrame:
    """Tilt and azimuth (compass bearing) of each series' panels, fitted on its clear days.

    Returns `unique_id, tilt, azimuth, r2, edge`; `edge` is True when the tilt is on the steepest tilt of the
    grid below 90 degrees (the data do not identify it). A low `r2` (< 0.85) usually means a roof of several
    planes. `options`: the tuning keyword arguments of `diagnose` (`tilts`, `azimuths`, `penalty`, ...); the
    fit uses the clear days, and its passes the change points, that they give.
    """
    k = _knobs(options)
    s = _check(series)
    f = _hourly(s, site)
    if clear is None:
        clear = _clear_k(_complete_days(f), k)
    return _roof(f, clear, site, k)


def _orientation(
    f: pd.DataFrame,
    clear: pd.DataFrame,
    site: tuple[float, float],
    level: pd.DataFrame | None = None,
    k: _Knobs = _DEFAULT,
) -> pd.DataFrame:
    """Pooled fit on the clear days (`physics.fit_orientation` over the grid of `k`), the production divided
    by `level` (unique_id, date, level) when given."""
    rows = []
    for uid, g in f.groupby("unique_id", sort=False):
        days = clear.loc[(clear["unique_id"] == uid) & clear["clear"], "date"]
        g = g[g["date"].isin(days) & g["y"].notna()]
        if g["date"].nunique() < 5:
            rows.append(dict(unique_id=uid, tilt=np.nan, azimuth=np.nan, r2=np.nan, edge=False))
            continue
        if level is not None:
            lv = level[level["unique_id"] == uid].set_index("date")["level"].reindex(g["date"])
            # a day whose stretch produced ~nothing (a dead inverter) says nothing about the plane
            alive = (lv > k.dead_level).to_numpy()
            g = g[alive]
            y = g["y"].to_numpy(dtype=float) / lv.to_numpy(dtype=float)[alive]
        else:
            y = g["y"].to_numpy(dtype=float)
        if g["date"].nunique() < 5 or not np.nanstd(y) > 0:  # all zero, or constant: no shape to fit
            rows.append(dict(unique_id=uid, tilt=np.nan, azimuth=np.nan, r2=np.nan, edge=False))
            continue
        sun = physics.mean_sun(pd.DatetimeIndex(g["ds"]), *site)
        r2, tilt, az = physics.fit_orientation(
            y, g["cs"].to_numpy(), sun, tilts=np.asarray(k.tilts), azimuths=np.asarray(k.azimuths)
        )
        rows.append(dict(unique_id=uid, tilt=tilt, azimuth=az, r2=r2, edge=k.edge(tilt)))
    return pd.DataFrame(rows, columns=["unique_id", "tilt", "azimuth", "r2", "edge"])


ROOF_MEMORY = 4  # roof fits remembered by their inputs (`_roof`)
_ROOFS: OrderedDict[tuple[Any, ...], pd.DataFrame] = OrderedDict()
_ROOFS_LOCK = threading.Lock()


def _fingerprint(frame: pd.DataFrame) -> tuple[int, tuple[str, ...], bytes]:
    """Rows, columns and a 128-bit digest of every value: equal frames, equal fingerprints."""
    rows = pd.util.hash_pandas_object(frame, index=False).to_numpy()
    return (
        len(frame),
        tuple(map(str, frame.columns)),
        hashlib.blake2b(rows.tobytes(), digest_size=16).digest(),
    )


def _roof(
    f: pd.DataFrame, clear: pd.DataFrame, site: tuple[float, float], k: _Knobs = _DEFAULT
) -> pd.DataFrame:
    """`_fit_roof`, remembered: the last `ROOF_MEMORY` fits are kept by a fingerprint of their inputs, so
    `forecast_ahead` and `diagnose` on the same series (the app runs both) fit the roof once, ~2.5 s on seven
    years of hourly data. A copy is returned: the remembered table cannot be changed by a caller."""
    key = (_fingerprint(f), _fingerprint(clear), tuple(map(float, site)), k)
    with _ROOFS_LOCK:
        hit = _ROOFS.get(key)
        if hit is not None:
            _ROOFS.move_to_end(key)
            return hit.copy()
    table = _fit_roof(f, clear, site, k)
    with _ROOFS_LOCK:
        _ROOFS[key] = table.copy()
        while len(_ROOFS) > ROOF_MEMORY:
            _ROOFS.popitem(last=False)
    return table


def _fit_roof(
    f: pd.DataFrame, clear: pd.DataFrame, site: tuple[float, float], k: _Knobs = _DEFAULT
) -> pd.DataFrame:
    """Orientation in two passes: pooled, then again with the level of each segment divided out.

    One regression over all the clear days keeps the seasonal amplitude, which is what pins the tilt down; but
    a step in the level (a fault, a cleaning) adds variation no plane explains and pulls the fit (a synthetic
    0.8 -> 0.55 fault: 20 degrees instead of 15, R2 0.84). The next passes divide each clear day by the level
    of its stretch between the large steps found on the previous pass, until the plane stops moving. (Scaling
    each day on its own removes the steps too, but also the seasonal amplitude: on Cascavel it gave 10 degrees
    facing 50 and a false step every April.)
    """
    table = _orientation(f, clear, site, k=k)
    for _ in range(k.roof_passes):
        index = _index(f, clear, site, {}, table)
        segments, steps = _changepoints(index, k)
        if segments.empty:
            break
        new = _orientation(f, clear, site, _level(index, segments, steps, k.step_note_pct), k)
        # a refit that failed (no finite R2) keeps the previous pass for that series
        failed = ~np.isfinite(new["r2"].to_numpy(dtype=float)) & np.isfinite(
            table["r2"].to_numpy(dtype=float)
        )
        new.loc[failed] = table.loc[failed].to_numpy()
        same = np.allclose(
            new[["tilt", "azimuth"]].to_numpy(float),
            table[["tilt", "azimuth"]].to_numpy(float),
            equal_nan=True,
        )
        table = new
        if same:
            break
    return table


def _level(
    index: pd.DataFrame, segments: pd.DataFrame, steps: pd.DataFrame, step_pct: float = STEP_NOTE_PCT
) -> pd.DataFrame:
    """A step level per clear day (unique_id, date, level), relative to the series' median: constant between
    the steps of at least `step_pct`, the median index of each stretch.

    Constant on purpose: the segment lines of a pass with the wrong plane also follow the seasonal residual,
    and dividing those out keeps the wrong plane (a synthetic fault stayed at 20 degrees instead of 15).
    """
    out = []
    for uid, g in index.groupby("unique_id", sort=False):
        st = steps[(steps["unique_id"] == uid) & (steps["step_pct"].abs() >= step_pct)]
        dates = pd.DatetimeIndex(g["date"])
        stretch = np.searchsorted(pd.DatetimeIndex(st["date"]).sort_values(), dates, side="right")
        med = g.groupby(stretch)["index"].transform("median").to_numpy(dtype=float)
        out.append(
            pd.DataFrame({"unique_id": uid, "date": g["date"].to_numpy(), "level": med / np.median(med)})
        )
    if not out:
        return pd.DataFrame(columns=["unique_id", "date", "level"])
    return pd.concat(out, ignore_index=True)


def performance_index(
    series: EnergySeries,
    site: tuple[float, float],
    *,
    kwp: float | dict[str, float] | None = None,
    orientation: pd.DataFrame | tuple[float, float] | None = None,
    clear: pd.DataFrame | None = None,
    **options: Any,
) -> pd.DataFrame:
    """Daily performance index on the clear days of each series (`kwp` per series must cover them all).

    `energy` is the day's measured energy (kWh), `expected` the clear-sky irradiation on the panel plane
    (kWh/m2) times `kwp` (kW) when given, and `index` their ratio: a performance ratio against clear sky with
    `kwp`, the effective peak power in kW without it. `orientation`: (tilt, azimuth) for every series, the
    table of `roof_orientation`, or None to fit it. `options`: the tuning keyword arguments of `diagnose`
    (the clear-day rule, the tilt grid, ...).
    """
    k = _knobs(options)
    s = _check(series)
    f = _hourly(s, site)
    if clear is None:
        clear = _clear_k(_complete_days(f), k)
    if orientation is None:
        orientation = _roof(f, clear, site, k)
    return _index(f, clear, site, _kwp(kwp, s.series), orientation)


def _kwp(kwp: float | dict[str, float] | None, ids: list[str]) -> dict[str, float]:
    if kwp is None:
        return {}
    if isinstance(kwp, dict):
        # all or none: a partial map would mix a performance ratio and an effective kW in one column
        missing = [u for u in ids if u not in {str(k) for k in kwp}]
        if missing:
            raise ValueError(f"kwp has no value for series {missing}; give one per series, or none")
        return {str(k): float(v) for k, v in kwp.items()}
    return {u: float(kwp) for u in ids}


def _index(
    f: pd.DataFrame,
    clear: pd.DataFrame,
    site: tuple[float, float],
    kwp: dict[str, float],
    orientation: pd.DataFrame | tuple[float, float],
) -> pd.DataFrame:
    out = []
    for uid, g in f.groupby("unique_id", sort=False):
        if isinstance(orientation, tuple):
            tilt, az = orientation
        else:
            row = orientation[orientation["unique_id"] == uid]
            if row.empty or not np.isfinite(row["tilt"].iloc[0]):
                continue
            tilt, az = float(row["tilt"].iloc[0]), float(row["azimuth"].iloc[0])
        days = clear.loc[(clear["unique_id"] == uid) & clear["clear"], "date"]
        g = g[g["date"].isin(days)]
        if g.empty:
            continue
        sun = physics.mean_sun(pd.DatetimeIndex(g["ds"]), *site)
        poa = physics.poa_isotropic(g["cs"].to_numpy(), sun, tilt, az) / 1000.0
        d = g.assign(poa=poa).groupby("date").agg(energy=("y", "sum"), expected=("poa", "sum")).reset_index()
        d["expected"] *= kwp.get(str(uid), 1.0)
        d = d[d["expected"] > 0]
        d.insert(0, "unique_id", uid)
        d["index"] = d["energy"] / d["expected"]
        out.append(d)
    if not out:
        return pd.DataFrame(columns=["unique_id", "date", "energy", "expected", "index"])
    return pd.concat(out, ignore_index=True)


def _line_costs(t: np.ndarray, y: np.ndarray) -> np.ndarray:
    """SSE of the least-squares line on every segment [a, b), from cumulative sums."""
    n = len(y)
    c = [np.concatenate([[0.0], np.cumsum(v)]) for v in (np.ones(n), t, y, t * t, t * y, y * y)]
    cost = np.full((n + 1, n + 1), np.inf)
    for a in range(n):
        b = np.arange(a + 2, n + 1)
        s0, s1, sy, s2, sty, syy = (v[b] - v[a] for v in c)
        stt = s2 - s1**2 / s0
        sxy = sty - s1 * sy / s0
        ssy = syy - sy**2 / s0
        fit = np.where(stt > 1e-12, sxy**2 / np.where(stt > 1e-12, stt, 1.0), 0.0)
        cost[a, b] = np.maximum(ssy - fit, 0.0)
    return cost


def _segment(t: np.ndarray, y: np.ndarray, min_size: int, max_breaks: int, penalty: float) -> list[int]:
    """Break positions of the BIC-best piecewise-linear fit (exact dynamic programming)."""
    n = len(y)
    cost = _line_costs(t, y)
    # f[j, e]: least SSE of the first e points in j lines; back[j, e]: where the last line starts. A row does
    # not depend on how many lines the whole fit has, so the rows are filled once for the largest k and
    # shared by every k below.
    top = min(max_breaks + 1, n // min_size)
    f = np.full((top + 1, n + 1), np.inf)
    back = np.zeros((top + 1, n + 1), dtype=int)
    f[0, 0] = 0.0
    for j in range(1, top + 1):
        # every end e at once: v[s, e] = f[j-1, s] + cost[s, e] over the starts s, with the starts too late
        # for e (s > e - min_size) set to inf; argmin keeps the first (earliest) start on ties
        lo, ends = (j - 1) * min_size, np.arange(j * min_size, n + 1)
        starts = np.arange(lo, n - min_size + 1)
        v = f[j - 1, starts, None] + cost[lo : n - min_size + 1, j * min_size :]
        v[starts[:, None] > ends[None, :] - min_size] = np.inf
        i = np.argmin(v, axis=0)
        f[j, ends], back[j, ends] = v[i, np.arange(len(ends))], starts[i]
    best: tuple[float, list[int]] | None = None
    for k in range(1, top + 1):
        breaks, e = [], n
        for j in range(k, 0, -1):
            e = int(back[j, e])
            breaks.append(e)
        sse = max(float(f[k, n]), 1e-12 * n)
        bic = n * np.log(sse / n) + penalty * (3 * k - 1) * np.log(
            n
        )  # k lines (2 each) + k - 1 break positions
        if best is None or bic < best[0]:
            best = (bic, sorted(b for b in breaks if b > 0))
    return [] if best is None else best[1]


def changepoints(
    index: pd.DataFrame,
    *,
    min_days: int = MIN_SEGMENT_DAYS,
    max_breaks: int = MAX_BREAKS,
    penalty: float = PENALTY,
    step_note_pct: float = STEP_NOTE_PCT,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Segments and steps of the performance index of each series (the output of `performance_index`).

    Each segment is a straight line in time: `level_start`, `level_end`, `trend_pct_per_year` (slope over the
    segment's mean) and `lost_pct`, how far its mean is below the best segment start of the series (the
    cleanest state seen). `steps` are the jumps between consecutive segments, from the end of one line to the
    start of the next; `event` marks the jumps of at least `step_note_pct` (5%; the others are changes of
    slope, the line bending, not jumping). `min_days` counts clear days, not calendar days; up to
    `max_breaks` breaks. `penalty` multiplies the BIC's penalty: the default 3 was CHOSEN on the project's
    two plants and ten Dingle houses (module docstring); a lower one finds at least as many breaks.
    """
    k = _Knobs(min_segment_days=min_days, max_breaks=max_breaks, penalty=penalty, step_note_pct=step_note_pct)
    return _changepoints(index, k)


def _changepoints(index: pd.DataFrame, k: _Knobs) -> tuple[pd.DataFrame, pd.DataFrame]:
    min_days, max_breaks, penalty = k.min_segment_days, k.max_breaks, k.penalty
    seg_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    for uid, g in index.groupby("unique_id", sort=False):
        g = g.dropna(subset=["index"]).sort_values("date")
        if len(g) < 2 * min_days:
            continue
        dates = pd.DatetimeIndex(g["date"])
        t = ((dates - dates[0]).days / 365.25).to_numpy(dtype=float)
        y = g["index"].to_numpy(dtype=float)
        breaks = _segment(t, y, min_days, max_breaks, penalty)
        edges = [0, *breaks, len(y)]
        segs: list[dict[str, Any]] = []
        for a, b in itertools.pairwise(edges):
            slope, base = np.polyfit(t[a:b], y[a:b], 1)
            segs.append(
                dict(
                    unique_id=uid,
                    start=dates[a],
                    end=dates[b - 1],
                    days=b - a,
                    level_start=float(base + slope * t[a]),
                    level_end=float(base + slope * t[b - 1]),
                    trend_pct_per_year=float(100 * slope / y[a:b].mean()),
                    mean=float(y[a:b].mean()),
                )
            )
        best = max(sg["level_start"] for sg in segs)
        for sg in segs:
            mean = sg.pop("mean")
            sg["lost_pct"] = float(100 * (1 - mean / best)) if best > 0 else np.nan
        seg_rows += segs
        for i, b in enumerate(breaks):
            before, after = float(segs[i]["level_end"]), float(segs[i + 1]["level_start"])
            pct = float(100 * (after / before - 1)) if before > 0 else np.nan
            step_rows.append(
                dict(
                    unique_id=uid,
                    date=dates[b],
                    before=before,
                    after=after,
                    step_pct=pct,
                    event=bool(abs(pct) >= k.step_note_pct),
                )
            )
    segments = pd.DataFrame(
        seg_rows,
        columns=[
            "unique_id",
            "start",
            "end",
            "days",
            "level_start",
            "level_end",
            "trend_pct_per_year",
            "lost_pct",
        ],
    )
    steps = pd.DataFrame(step_rows, columns=["unique_id", "date", "before", "after", "step_pct", "event"])
    return segments, steps


def diagnose(
    series: EnergySeries,
    site: tuple[float, float],
    *,
    kwp: float | dict[str, float] | None = None,
    orientation: tuple[float, float] | None = None,
    clear_window_days: int = CLEAR_WINDOW_DAYS,
    clear_quantile: float = CLEAR_QUANTILE,
    clear_ratio: float = CLEAR_RATIO,
    dead_level: float = DEAD_LEVEL,
    tilts: Sequence[float] | np.ndarray = TILTS,
    azimuths: Sequence[float] | np.ndarray = AZIMUTHS,
    roof_passes: int = ROOF_PASSES,
    min_segment_days: int = MIN_SEGMENT_DAYS,
    max_breaks: int = MAX_BREAKS,
    penalty: float = PENALTY,
    step_note_pct: float = STEP_NOTE_PCT,
    good_fit_r2: float = GOOD_FIT_R2,
    trend_note_pct: float = TREND_NOTE_PCT,
) -> Diagnosis:
    """The whole chain: clear days, roof orientation, performance index, change points and notes.

    `kwp`: peak power of each series (one value for all, or per `unique_id`); without it the index is the
    effective peak power. `orientation`: (tilt, azimuth) when known; otherwise fitted per series.

    The tuning arguments (module docstring, "Tuning", says where each default comes from):

    - clear days (`clear_days`): `clear_window_days`, `clear_quantile`, `clear_ratio` (set by hand on the
      pilot's two plants) and `dead_level` (generic);
    - the roof (`roof_orientation`): the search grid `tilts` (0-60 degrees; widen it, up to 90, for facade
      or balcony panels; a fit on its steepest tilt below 90 is reported as on the edge, not identified) and
      `azimuths` (the whole compass), and `roof_passes`, the refits with the levels between steps divided out
      (generic);
    - change points (`changepoints`): `min_segment_days`, `max_breaks` (set by hand), `penalty` (CHOSEN on
      the project's two plants and ten Dingle houses) and `step_note_pct`, the smallest step that is an event
      (generic); they also steer the roof passes;
    - the notes: `good_fit_r2` (set by hand; below it, or on the edge, steps are uncertain and no trend or
      loss is reported) and `trend_note_pct` (%/year, generic).
    """
    k = _Knobs(
        clear_window_days=clear_window_days,
        clear_quantile=clear_quantile,
        clear_ratio=clear_ratio,
        dead_level=dead_level,
        tilts=tuple(tilts),
        azimuths=tuple(azimuths),
        roof_passes=roof_passes,
        min_segment_days=min_segment_days,
        max_breaks=max_breaks,
        penalty=penalty,
        step_note_pct=step_note_pct,
        good_fit_r2=good_fit_r2,
        trend_note_pct=trend_note_pct,
    )
    s = _check(series)
    f = _hourly(s, site)
    clear = _clear_k(_complete_days(f), k)
    if orientation is None:
        table = _roof(f, clear, site, k)
    else:
        table = pd.DataFrame(
            [
                dict(unique_id=u, tilt=orientation[0], azimuth=orientation[1], r2=np.nan, edge=False)
                for u in s.series
            ]
        )
    kw = _kwp(kwp, s.series)
    index = _index(f, clear, site, kw, table)
    segments, steps = _changepoints(index, k)
    notes = _notes(table, index, segments, steps, kw, orientation is not None, k)
    table, segments = _flag(table, segments, orientation is not None, k)
    return Diagnosis(orientation=table, index=index, segments=segments, steps=steps, kwp=kw, notes=notes)


def _reported(
    orientation: pd.DataFrame, segments: pd.DataFrame, given: bool, k: _Knobs = _DEFAULT
) -> tuple[dict[str, bool], set[str], set[str]]:
    """What the notes report, per series: whether the roof is known well enough for steps, a trend and a
    loss to mean anything (`reliable`: given, or fitted with `good_fit_r2` and not on the edge), and the
    series whose latest period has a trend worth a note (a fall of `trend_note_pct` a year over at least a
    year: under a year the slope is mostly the season, a clear-sky model is never exact) and a loss worth one
    (`step_note_pct` below the best level)."""
    reliable = {
        str(r["unique_id"]): bool(
            np.isfinite(r["tilt"]) and (given or (r["r2"] >= k.good_fit_r2 and not r["edge"]))
        )
        for r in orientation.to_dict(orient="records")
    }
    trend: set[str] = set()
    loss: set[str] = set()
    for sid, g in segments.groupby("unique_id", sort=False):
        if not reliable.get(str(sid), False):
            continue
        last = g.iloc[-1]
        span = (pd.Timestamp(last["end"]) - pd.Timestamp(last["start"])).days
        if float(last["trend_pct_per_year"]) <= -k.trend_note_pct and span >= 365:
            trend.add(str(sid))
        if float(last["lost_pct"]) >= k.step_note_pct:
            loss.add(str(sid))
    return reliable, trend, loss


def _flag(
    orientation: pd.DataFrame, segments: pd.DataFrame, given: bool, k: _Knobs
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The tables with what the notes report, for a page that shows numbers instead of the notes:
    `orientation.reliable`, and `segments.trend_reported` / `loss_reported` (only ever on a series' last
    period)."""
    reliable, trend, loss = _reported(orientation, segments, given, k)
    orientation = orientation.assign(reliable=[reliable.get(str(u), False) for u in orientation["unique_id"]])
    last = ~segments["unique_id"].duplicated(keep="last")
    uid = segments["unique_id"].astype(str)
    segments = segments.assign(
        trend_reported=(last & uid.isin(trend)).astype(bool),
        loss_reported=(last & uid.isin(loss)).astype(bool),
    )
    return orientation, segments


def _notes(
    orientation: pd.DataFrame,
    index: pd.DataFrame,
    segments: pd.DataFrame,
    steps: pd.DataFrame,
    kwp: dict[str, float],
    given: bool,
    k: _Knobs = _DEFAULT,
) -> list[str]:
    notes: list[str] = []
    reliable, trend_noted, loss_noted = _reported(orientation, segments, given, k)
    for r in orientation.to_dict(orient="records"):
        uid = str(r["unique_id"])
        if not np.isfinite(r["tilt"]):
            notes.append(Note("Series {uid}: too few clear days to fit the roof; no diagnostics.", uid=uid))
            continue
        if not given:
            fit = {"uid": uid, "tilt": r["tilt"], "azimuth": r["azimuth"], "r2": r["r2"]}
            notes.append(
                Note(
                    "Series {uid}: panels fitted at {tilt:.0f} degrees tilt facing {azimuth:.0f} degrees "
                    "(compass; R2 {r2:.2f} on clear days). The tilt is on the edge of the grid: it is not "
                    "identified.",
                    **fit,
                )
                if r["edge"]
                else Note(
                    "Series {uid}: panels fitted at {tilt:.0f} degrees tilt facing {azimuth:.0f} degrees "
                    "(compass; R2 {r2:.2f} on clear days).",
                    **fit,
                )
            )
            if not reliable[uid]:
                notes.append(
                    Note(
                        "Series {uid}: a single plane does not describe this roof well (several planes, or "
                        "not enough clear days to tell). The index keeps a seasonal swing: steps are "
                        "uncertain, and no trend or loss is reported. Pass the known orientation to diagnose "
                        "it.",
                        uid=uid,
                    )
                )
        n_index = int((index["unique_id"] == uid).sum())
        if n_index and n_index < 2 * k.min_segment_days:
            notes.append(
                Note(
                    "Series {uid}: {n} clear days, too few to look for changes over time.", uid=uid, n=n_index
                )
            )
    for r in steps.to_dict(orient="records"):
        pct = float(r["step_pct"])
        if not np.isfinite(pct) or abs(pct) < k.step_note_pct:
            continue
        uid = str(r["unique_id"])
        what = _STEP_UP if pct > 0 else _STEP_DOWN
        said: list[str] = [
            Note(
                "Series {uid}: clear-day production stepped {pct:+.0f}% around {when}: {what}.",
                uid=uid,
                pct=pct,
                when=pd.Timestamp(r["date"]).date(),
                what=what,
            )
        ]
        if _recurs(steps, r, step_pct=k.step_note_pct):
            said.append(Note("A step of the same sign comes back at this time of year: it may be seasonal."))
        if not reliable.get(uid, False):
            said.append(Note("Uncertain (roof fit, see above)."))
        notes.append(Note.join(said, " ") if len(said) > 1 else said[0])
    for sid, g in segments.groupby("unique_id", sort=False):
        last = g.iloc[-1]
        trend = float(last["trend_pct_per_year"])
        since = pd.Timestamp(last["start"]).date()
        if str(sid) in trend_noted:
            notes.append(
                Note(
                    "Series {uid}: since {since} the clear-day production falls {pct:.0f}% a year; soiling "
                    "builds up like this (a cleaning shows as a step up).",
                    uid=sid,
                    since=since,
                    pct=-trend,
                )
            )
        if str(sid) in loss_noted:
            notes.append(
                Note(
                    "Series {uid}: the latest period is {pct:.0f}% below the best level seen on clear days.",
                    uid=sid,
                    pct=last["lost_pct"],
                )
            )
    if kwp:
        for sid, g in index.groupby("unique_id", sort=False):
            pr = float(g["index"].median())
            if pr > 1.05:
                notes.append(
                    Note(
                        "Series {uid}: clear-day production is {pr:.2f} x the stated peak power: the kWp is "
                        "too low, or the clock or the site is wrong.",
                        uid=sid,
                        pr=pr,
                    )
                )
    return notes


# what a step of the clear-day production usually is, up or down
_STEP_UP = Note("a cleaning, a repair or a change to the array")
_STEP_DOWN = Note("a fault, new shading or a change to the array")


def _recurs(steps: pd.DataFrame, r: dict[Any, Any], days: int = 45, step_pct: float = STEP_NOTE_PCT) -> bool:
    """Another step of the same sign in the same series within `days` of the same day of the year."""
    same = steps[(steps["unique_id"] == r["unique_id"]) & (steps["date"] != r["date"])]
    same = same[(np.sign(same["step_pct"]) == np.sign(r["step_pct"])) & (same["step_pct"].abs() >= step_pct)]
    if same.empty:
        return False
    doy = pd.DatetimeIndex(same["date"]).day_of_year.to_numpy()
    d = abs(doy - pd.Timestamp(r["date"]).day_of_year)
    return bool((np.minimum(d, 365 - d) <= days).any())


def _plain(v: Any) -> Any:
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v
