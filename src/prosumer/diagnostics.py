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
   with the plain BIC the plants got 9 to 11 steps, most of them seasonal). Soiling is a sawtooth (a slow
   decline, a step up at the cleaning), so each segment has its own slope, and the steps are the events.

Pilot (`experimentos/testes_previsao/scripts/piloto_diagnostico.py --biblioteca`, 2026-10-12): on the
benchmark's two plants it found, from hourly AC energy and the site only, every event the 5-minute DC analysis
had found that shows in AC energy, within a month: the Cascavel cleanings of November 2023 (+24%) and
September 2024 (dated 2024-08-12, +10%), and nothing else there; the Curitiba string fault of December 2022
(-17%) and its repair in July 2023 (dated 2023-08-02, +101%). The Curitiba reconfiguration of June 2025 was
seen in the DC string voltages and does not show in AC energy. The penalty factor was chosen on these same two
plants; on the ten PV houses of the Dingle data (one year, no known events) it gives one step in total.
Limits: a roof of several unlike planes fits one plane poorly (Curitiba R2 0.81) and leaves a seasonal
residual that the segmentation reads as extra steps (Curitiba: +27% in February 2024, +19% in December 2024);
the notes then call every step uncertain and report no trend or loss. Telling soiling from shading or a
string fault needs sub-hourly or DC data (not here yet).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from . import physics
from .contracts import EnergySeries

CLEAR_WINDOW_DAYS = 31
CLEAR_QUANTILE = 0.9
CLEAR_RATIO = 0.9
MIN_SEGMENT_DAYS = 15  # clear days per segment (about one to two months)
MAX_BREAKS = 11
PENALTY = 3.0  # multiplies the BIC penalty: the daily index is not independent noise (see `changepoints`)
GOOD_FIT_R2 = 0.85  # below it a single plane does not describe the roof well
STEP_NOTE_PCT = 5.0  # steps smaller than this are not worth a note
TREND_NOTE_PCT = 5.0  # %/year
TILTS = np.arange(0, 61, 5.0)
ROOF_PASSES = 4  # refits of the orientation with the segment levels divided out
AZIMUTHS = np.arange(0, 360, 10.0)  # compass: the whole circle (north-facing roofs in the south)


@dataclass
class Diagnosis:
    """What `diagnose` returns: one table per stage and plain-language notes."""

    orientation: pd.DataFrame  # unique_id, tilt, azimuth, r2, edge (orientation on the edge of the grid)
    index: pd.DataFrame  # unique_id, date, energy, expected, index (clear days only)
    segments: (
        pd.DataFrame
    )  # unique_id, start, end, days, level_start, level_end, trend_pct_per_year, lost_pct
    steps: pd.DataFrame  # unique_id, date, before, after, step_pct, event (|step| >= 5%)
    kwp: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def records(df: pd.DataFrame) -> list[dict[str, Any]]:
            out = df.copy()
            for c in out.columns:
                if pd.api.types.is_datetime64_any_dtype(out[c]):
                    out[c] = out[c].dt.strftime("%Y-%m-%d")
            return [{str(k): _plain(v) for k, v in r.items()} for r in out.to_dict(orient="records")]

        return {
            "orientation": records(self.orientation),
            "segments": records(self.segments),
            "steps": records(self.steps),
            "kwp": dict(self.kwp),
            "notes": list(self.notes),
        }


def _check(series: EnergySeries) -> EnergySeries:
    if series.quantity != "generation":
        raise ValueError(f"Diagnostics are for generation series, not {series.quantity!r}")
    s = series.to_kwh()
    if s.freq != "h":
        raise ValueError(f"Diagnostics need an hourly series, not freq={s.freq!r}; resample first")
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
    g = sun.groupby(["unique_id", "date"])
    d = g.agg(energy=("y", "sum"), cs=("cs", "sum"), missing=("y", lambda v: int(v.isna().sum())))
    return d[(d["missing"] == 0) & (d["cs"] > 0)].drop(columns="missing").reset_index()


def clear_days(
    series: EnergySeries,
    site: tuple[float, float],
    *,
    window_days: int = CLEAR_WINDOW_DAYS,
    quantile: float = CLEAR_QUANTILE,
    ratio: float = CLEAR_RATIO,
) -> pd.DataFrame:
    """Days of each series that were (nearly) cloudless, judged from the production itself.

    Returns `unique_id, date, ratio, top, clear`: `ratio` is the day's energy over the clear-sky GHI of the
    day (only days with every sun hour measured), `top` the `quantile` of that ratio in a centred window of
    `window_days` calendar days, and `clear` = `ratio >= ratio x top`.
    """
    s = _check(series)
    return _clear(_complete_days(_hourly(s, site)), window_days, quantile, ratio)


def _clear(d: pd.DataFrame, window_days: int, quantile: float, ratio: float) -> pd.DataFrame:
    out = []
    for uid, g in d.groupby("unique_id", sort=False):
        r = (g.set_index("date")["energy"] / g.set_index("date")["cs"]).sort_index()
        daily = r.reindex(pd.date_range(r.index.min(), r.index.max(), freq="D"))
        top = daily.rolling(window_days, center=True, min_periods=max(3, window_days // 3)).quantile(quantile)
        t = pd.DataFrame({"unique_id": uid, "date": r.index, "ratio": r.to_numpy()})
        t["top"] = top.reindex(r.index).to_numpy()
        t["clear"] = t["ratio"] >= ratio * t["top"]
        out.append(t)
    if not out:
        return pd.DataFrame(columns=["unique_id", "date", "ratio", "top", "clear"])
    return pd.concat(out, ignore_index=True)


def roof_orientation(
    series: EnergySeries, site: tuple[float, float], *, clear: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Tilt and azimuth (compass bearing) of each series' panels, fitted on its clear days.

    Returns `unique_id, tilt, azimuth, r2, edge`; `edge` is True when the tilt is on the edge of the grid
    (the data do not identify it). A low `r2` (< 0.85) usually means a roof of several planes.
    """
    s = _check(series)
    f = _hourly(s, site)
    if clear is None:
        clear = _clear(_complete_days(f), CLEAR_WINDOW_DAYS, CLEAR_QUANTILE, CLEAR_RATIO)
    return _roof(f, clear, site)


def _orientation(
    f: pd.DataFrame, clear: pd.DataFrame, site: tuple[float, float], level: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Pooled fit on the clear days (`physics.fit_orientation`, whole compass), the production divided by
    `level` (unique_id, date, level) when given."""
    rows = []
    for uid, g in f.groupby("unique_id", sort=False):
        days = clear.loc[(clear["unique_id"] == uid) & clear["clear"], "date"]
        g = g[g["date"].isin(days) & g["y"].notna()]
        if g["date"].nunique() < 5:
            rows.append(dict(unique_id=uid, tilt=np.nan, azimuth=np.nan, r2=np.nan, edge=False))
            continue
        y = g["y"].to_numpy(dtype=float)
        if level is not None:
            lv = level[level["unique_id"] == uid].set_index("date")["level"]
            y = y / lv.reindex(g["date"]).to_numpy(dtype=float)
        sun = physics.mean_sun(pd.DatetimeIndex(g["ds"]), *site)
        r2, tilt, az = physics.fit_orientation(y, g["cs"].to_numpy(), sun, tilts=TILTS, azimuths=AZIMUTHS)
        rows.append(dict(unique_id=uid, tilt=tilt, azimuth=az, r2=r2, edge=bool(tilt == TILTS[-1])))
    return pd.DataFrame(rows, columns=["unique_id", "tilt", "azimuth", "r2", "edge"])


def _roof(f: pd.DataFrame, clear: pd.DataFrame, site: tuple[float, float]) -> pd.DataFrame:
    """Orientation in two passes: pooled, then again with the level of each segment divided out.

    One regression over all the clear days keeps the seasonal amplitude, which is what pins the tilt down; but
    a step in the level (a fault, a cleaning) adds variation no plane explains and pulls the fit (a synthetic
    0.8 -> 0.55 fault: 20 degrees instead of 15, R2 0.84). The next passes divide each clear day by the level
    of its stretch between the large steps found on the previous pass, until the plane stops moving. (Scaling
    each day on its own removes the steps too, but also the seasonal amplitude: on Cascavel it gave 10 degrees
    facing 50 and a false step every April.)
    """
    table = _orientation(f, clear, site)
    for _ in range(ROOF_PASSES):
        index = _index(f, clear, site, {}, table)
        segments, steps = changepoints(index)
        if segments.empty:
            break
        new = _orientation(f, clear, site, _level(index, segments, steps))
        same = np.allclose(
            new[["tilt", "azimuth"]].to_numpy(float),
            table[["tilt", "azimuth"]].to_numpy(float),
            equal_nan=True,
        )
        table = new
        if same:
            break
    return table


def _level(index: pd.DataFrame, segments: pd.DataFrame, steps: pd.DataFrame) -> pd.DataFrame:
    """A step level per clear day (unique_id, date, level), relative to the series' median: constant between
    the steps of at least `STEP_NOTE_PCT`, the median index of each stretch.

    Constant on purpose: the segment lines of a pass with the wrong plane also follow the seasonal residual,
    and dividing those out keeps the wrong plane (a synthetic fault stayed at 20 degrees instead of 15).
    """
    out = []
    for uid, g in index.groupby("unique_id", sort=False):
        st = steps[(steps["unique_id"] == uid) & (steps["step_pct"].abs() >= STEP_NOTE_PCT)]
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
) -> pd.DataFrame:
    """Daily performance index on the clear days of each series.

    `energy` is the day's measured energy (kWh), `expected` the clear-sky irradiation on the panel plane
    (kWh/m2) times `kwp` (kW) when given, and `index` their ratio: a performance ratio against clear sky with
    `kwp`, the effective peak power in kW without it. `orientation`: (tilt, azimuth) for every series, the
    table of `roof_orientation`, or None to fit it.
    """
    s = _check(series)
    f = _hourly(s, site)
    if clear is None:
        clear = _clear(_complete_days(f), CLEAR_WINDOW_DAYS, CLEAR_QUANTILE, CLEAR_RATIO)
    if orientation is None:
        orientation = _roof(f, clear, site)
    return _index(f, clear, site, _kwp(kwp, s.series), orientation)


def _kwp(kwp: float | dict[str, float] | None, ids: list[str]) -> dict[str, float]:
    if kwp is None:
        return {}
    if isinstance(kwp, dict):
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
    best: tuple[float, list[int]] | None = None
    for k in range(1, max_breaks + 2):
        if k * min_size > n:
            break
        f = np.full((k + 1, n + 1), np.inf)
        back = np.zeros((k + 1, n + 1), dtype=int)
        f[0, 0] = 0.0
        for j in range(1, k + 1):
            for e in range(j * min_size, n + 1):
                starts = np.arange((j - 1) * min_size, e - min_size + 1)
                v = f[j - 1, starts] + cost[starts, e]
                i = int(np.argmin(v))
                f[j, e], back[j, e] = v[i], starts[i]
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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Segments and steps of the performance index of each series (the output of `performance_index`).

    Each segment is a straight line in time: `level_start`, `level_end`, `trend_pct_per_year` (slope over the
    segment's mean) and `lost_pct`, how far its mean is below the best segment start of the series (the
    cleanest state seen). `steps` are the jumps between consecutive segments, from the end of one line to the
    start of the next; `event` marks the jumps of at least 5% (the others are changes of slope, the line
    bending, not jumping). `min_days` counts clear days, not calendar days.
    """
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
            sg["lost_pct"] = float(100 * (1 - sg.pop("mean") / best))
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
                    event=bool(abs(pct) >= STEP_NOTE_PCT),
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
) -> Diagnosis:
    """The whole chain: clear days, roof orientation, performance index, change points and notes.

    `kwp`: peak power of each series (one value for all, or per `unique_id`); without it the index is the
    effective peak power. `orientation`: (tilt, azimuth) when known; otherwise fitted per series.
    """
    s = _check(series)
    f = _hourly(s, site)
    clear = _clear(_complete_days(f), CLEAR_WINDOW_DAYS, CLEAR_QUANTILE, CLEAR_RATIO)
    if orientation is None:
        table = _roof(f, clear, site)
    else:
        table = pd.DataFrame(
            [
                dict(unique_id=u, tilt=orientation[0], azimuth=orientation[1], r2=np.nan, edge=False)
                for u in s.series
            ]
        )
    kw = _kwp(kwp, s.series)
    index = _index(f, clear, site, kw, table)
    segments, steps = changepoints(index)
    notes = _notes(table, index, segments, steps, kw, orientation is not None)
    return Diagnosis(orientation=table, index=index, segments=segments, steps=steps, kwp=kw, notes=notes)


def _notes(
    orientation: pd.DataFrame,
    index: pd.DataFrame,
    segments: pd.DataFrame,
    steps: pd.DataFrame,
    kwp: dict[str, float],
    given: bool,
) -> list[str]:
    notes = []
    reliable: dict[str, bool] = {}
    for r in orientation.to_dict(orient="records"):
        uid = str(r["unique_id"])
        if not np.isfinite(r["tilt"]):
            notes.append(f"Series {uid}: too few clear days to fit the roof; no diagnostics.")
            continue
        reliable[uid] = given or (r["r2"] >= GOOD_FIT_R2 and not r["edge"])
        if not given:
            fit = (
                f"Series {uid}: panels fitted at {r['tilt']:.0f} degrees tilt facing {r['azimuth']:.0f} "
                f"degrees (compass; R2 {r['r2']:.2f} on clear days)."
            )
            if r["edge"]:
                fit += " The tilt is on the edge of the grid: it is not identified."
            notes.append(fit)
            if not reliable[uid]:
                notes.append(
                    f"Series {uid}: a single plane does not describe this roof well (several planes, or not "
                    "enough clear days to tell). The index keeps a seasonal swing: steps are uncertain, and "
                    "no trend or loss is reported. Pass the known orientation to diagnose it."
                )
        n_index = int((index["unique_id"] == uid).sum())
        if n_index and n_index < 2 * MIN_SEGMENT_DAYS:
            notes.append(f"Series {uid}: {n_index} clear days, too few to look for changes over time.")
    for r in steps.to_dict(orient="records"):
        pct = float(r["step_pct"])
        if not np.isfinite(pct) or abs(pct) < STEP_NOTE_PCT:
            continue
        uid = str(r["unique_id"])
        when = pd.Timestamp(r["date"]).strftime("%Y-%m-%d")
        if pct > 0:
            what = "a cleaning, a repair or a change to the array"
        else:
            what = "a fault, new shading or a change to the array"
        extra = ""
        if _recurs(steps, r):
            extra += " A step of the same sign comes back at this time of year: it may be seasonal."
        if not reliable.get(uid, False):
            extra += " Uncertain (roof fit, see above)."
        notes.append(f"Series {uid}: clear-day production stepped {pct:+.0f}% around {when}: {what}.{extra}")
    for sid, g in segments.groupby("unique_id", sort=False):
        if not reliable.get(str(sid), False):
            continue
        last = g.iloc[-1]
        trend = float(last["trend_pct_per_year"])
        since = pd.Timestamp(last["start"]).strftime("%Y-%m-%d")
        span = (pd.Timestamp(last["end"]) - pd.Timestamp(last["start"])).days
        # under a year the slope is mostly the season (a clear-sky model is never exact)
        if trend <= -TREND_NOTE_PCT and span >= 365:
            notes.append(
                f"Series {sid}: since {since} the clear-day production falls {-trend:.0f}% a year; soiling "
                "builds up like this (a cleaning shows as a step up)."
            )
        if float(last["lost_pct"]) >= STEP_NOTE_PCT:
            notes.append(
                f"Series {sid}: the latest period is {last['lost_pct']:.0f}% below the best level seen on "
                "clear days."
            )
    if kwp:
        for sid, g in index.groupby("unique_id", sort=False):
            pr = float(g["index"].median())
            if pr > 1.05:
                notes.append(
                    f"Series {sid}: clear-day production is {pr:.2f} x the stated peak power: the kWp is too "
                    "low, or the clock or the site is wrong."
                )
    return notes


def _recurs(steps: pd.DataFrame, r: dict[Any, Any], days: int = 45) -> bool:
    """Another step of the same sign in the same series within `days` of the same day of the year."""
    same = steps[(steps["unique_id"] == r["unique_id"]) & (steps["date"] != r["date"])]
    same = same[np.sign(same["step_pct"]) == np.sign(r["step_pct"])]
    if same.empty:
        return False
    doy = pd.DatetimeIndex(same["date"]).dayofyear.to_numpy()
    d = abs(doy - pd.Timestamp(r["date"]).dayofyear)
    return bool((np.minimum(d, 365 - d) <= days).any())


def _plain(v: Any) -> Any:
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v
