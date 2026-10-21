"""Quality checks that need physics: the clock of a generation series checked against the sun.

A PV series carries its own clock check: the panel produces only while the sun is up, and the sun's position
is known for any place and time (`physics`). A series whose timestamps are off shows production at the wrong
hours of the day. The usual causes, all seen in real monitoring exports:

- the file is in UTC (or the logger's standard time) but was read as local time: a constant offset of the
  UTC offset (+3 h for a Brazilian plant exported in UTC);
- the logger ignores daylight saving time while the declared time zone has it (or the reverse): the offset
  is 0 in one part of the year and +-1 h in the other, so it shows up only month by month;
- the energy of [10:00, 11:00) labelled 11:00 (interval END) where the library expects the START: +1 h.
  The check cannot tell this from a one-hour clock error; the fix (shift the labels) is the same.

How it works (`clock_offset`): per series and per period, the mean production profile over the hours of the
day is shifted by k steps (k = -max_shift .. +max_shift) and compared (Pearson correlation) with the
clear-sky irradiance profile of the same days and hours at the site. The orientation of the panels is not
known, and an east- or west-facing roof skews the profile by up to about an hour, so every shift is scored
against a small set of plane orientations (flat, 20 and 40 degrees, eight compass directions) and the best
one counts. The estimated offset is the k with the highest score. The confidence comes from the days: the
share of complete days whose own best shift agrees with the period's (`agreement`).

Only generation series: a consumption profile has no physical clock to compare with.

The sun check has two blind spots: it resolves whole steps only (an hourly series 30 min late comes out as a
noisy 0 or +1 depending on the month), and the roof's unknown orientation can mimic up to about an hour of
offset. `clock_offset_weather` closes both when an irradiance series is available (measured or forecast, e.g.
`io.open_meteo.wide`): it lines up the CLOUDS, not the daily shape. Both series lose their mean hourly profile
of the month (what is left is the passing weather of each day), and the correlation of the two anomalies is
computed for each shift; the peak, refined between steps by a parabola, is the offset in fractions of a step.
The orientation drops out (it scales the anomaly, it does not move it in time). Found on the benchmark's
Curitiba plant (2026-10-12): about +0.5 h against a forecast whose clock is right, where the sun check gave
-1 to +2 h depending on the month.

Tuning (every threshold is an argument; `analyze(clock_options=..., clock_weather_options=...)` passes them).
None was chosen on the project's data; they are generic statistical conventions, declared here so a user can
see them: `min_agreement` (0.5: a period is confident when most of its complete days pick its offset),
`min_days` (7 for the sun, 14 for the weather), the daylight mask of the weather check (`daylight_share`,
steps whose mean of the month is above 5% of the month's peak: the night and the first minutes of the day
carry no cloud signal), the interval of the weather offset (`interval`, 90% by resampling days) and the widest
interval still called confident (`max_interval_h`, 1 h).
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from . import physics
from .contracts import EnergySeries, step
from .i18n import Note

By = Literal["month"] | None

# plane orientations (tilt, azimuth as a compass bearing) the profile is compared with
DEFAULT_ORIENTATIONS: tuple[tuple[float, float], ...] = (
    (0.0, 180.0),
    *[(t, float(a)) for t in (20.0, 40.0) for a in range(0, 360, 45)],
)
MIN_AGREEMENT = 0.5  # share of the days that must pick the period's offset for it to be `confident`
DAYLIGHT_SHARE = 0.05  # weather check: steps whose monthly mean is above this share of the month's peak
INTERVAL = 0.90  # weather check: coverage of the bootstrap interval of the offset


def clock_offset(
    series: EnergySeries,
    site: tuple[float, float],
    *,
    max_shift_h: float = 12,
    by: By = "month",
    min_days: int = 7,
    orientations: tuple[tuple[float, float], ...] = DEFAULT_ORIENTATIONS,
    min_agreement: float = MIN_AGREEMENT,
) -> pd.DataFrame:
    """Clock offset of each generation series, against the sun at `site` = (latitude, longitude).

    Returns one row per series and period: the whole series (`period` = "all") and, with `by="month"`, each
    calendar month (local time) with at least `min_days` days of data. Columns:

    - `offset_h`: how many hours LATE the labels are relative to the sun (multiple of the step). +3 means the
      production labelled 15:00 happened at 12:00 local solar time; fix with `ds - offset_h hours`.
    - `centroid_shift_h`: the continuous version (circular centroid of the production profile minus that of
      the best-fitting clear-sky profile, in hours): also catches a half-step label offset.
    - `score`, `score_zero`: correlation with the clear-sky profile at the best shift and at shift 0.
    - `days`: days with data in the period; `agreement`: share of the complete days (every step valid, some
      production) whose own best shift equals `offset_h`; `confident`: `days >= min_days` and `agreement >=
      min_agreement` (0.5). A cloudy, short or very noisy period comes out not confident instead of with a
      wrong answer.

    A DST problem shows up as confident months with different offsets (see `clock_notes`).
    """
    if series.quantity != "generation":
        raise ValueError(f"The clock check needs a generation series, not {series.quantity!r}")
    if not 0 < min_agreement <= 1:
        raise ValueError("min_agreement must be in (0, 1]")
    lat, lon = site
    st = step(series.freq)
    spd = pd.Timedelta(days=1) / st
    if spd != int(spd) or spd < 2:
        raise ValueError(f"The step must divide a day into several intervals, not {series.freq!r}")
    spd = int(spd)
    max_k = min(round(pd.Timedelta(hours=max_shift_h) / st), spd // 2)
    shifts = np.arange(-max_k, max_k + 1)
    hours_per_step = st.total_seconds() / 3600

    v = series.frame.loc[series.frame["valid"] & series.frame["y"].notna(), ["unique_id", "ds", "y"]]
    if v.empty:
        return _empty()
    times = pd.DatetimeIndex(v["ds"].unique()).sort_values()
    interval = f"{int(st.total_seconds())}s"
    sun = physics.mean_sun(times, lat, lon, interval=interval)
    ghi = physics.clear_sky_ghi(times, lat, lon, interval=interval)
    clear = pd.DataFrame(
        np.column_stack([physics.poa_isotropic(ghi, sun, t, a) for t, a in orientations]), index=times
    )

    rows = []
    for uid, g in v.groupby("unique_id", sort=True):
        ds = pd.DatetimeIndex(g["ds"])
        wall = ds.tz_localize(None)
        date = wall.normalize()
        pos = ((wall - date) / st).to_numpy().astype(int)
        cells = pd.DataFrame({"date": date, "pos": pos, "y": g["y"].to_numpy(float)})
        cs = clear.reindex(ds).to_numpy()
        periods: list[tuple[str, np.ndarray]] = [("all", np.ones(len(g), bool))]
        if by == "month":
            month = wall.strftime("%Y-%m").to_numpy()
            periods += [(str(m), month == m) for m in np.unique(month)]
        for name, sel in periods:
            row = _fit(cells[sel], cs[sel], spd, shifts, hours_per_step)
            if row is None or (name != "all" and row["days"] < min_days):
                continue
            row["confident"] = bool(row["days"] >= min_days and row["agreement"] >= min_agreement)
            rows.append({"unique_id": str(uid), "period": name, **row})
    return pd.DataFrame(rows) if rows else _empty()


def clock_notes(table: pd.DataFrame) -> list[str]:
    """Plain-language notes from `clock_offset`: only for a confident non-zero offset or an offset that
    changes between confident months (daylight saving time)."""
    notes: list[str] = []
    for uid, g in table.groupby("unique_id", sort=True):
        months = g[(g["period"] != "all") & g["confident"]]
        found = sorted(set(months["offset_h"].tolist()))
        if len(found) > 1:
            per = [
                Note(
                    "{h:+g} h in {months}",
                    h=h,
                    months=", ".join(months.loc[months["offset_h"] == h, "period"]),
                )
                for h in found
            ]
            notes.append(
                Note(
                    "Series {uid}: the clock offset against the sun changes over the year ({per}). A logger "
                    "that ignores daylight saving time (or a file in standard time read in a zone with it) "
                    "does this: check the time zone of the export.",
                    uid=uid,
                    per=per,
                )
            )
            continue
        whole = g[g["period"] == "all"]
        if whole.empty:
            continue
        r = whole.iloc[0]
        if r["confident"] and r["offset_h"] != 0:
            notes.append(
                Note(
                    "Series {uid}: production happens {hours:g} h {side} than the sun at the site "
                    "({agree:.0%} of the days agree). Usually a file in UTC read as local time, a wrong time "
                    "zone or, for +1 h, values labelled by the END of the interval: shift the timestamps by "
                    "{shift:+g} h after checking the source.",
                    uid=uid,
                    hours=abs(r["offset_h"]),
                    side=_LATER if r["offset_h"] > 0 else _EARLIER,
                    agree=r["agreement"],
                    shift=-r["offset_h"],
                )
            )
    return notes


_LATER, _EARLIER = Note("later"), Note("earlier")


def clock_offset_weather(
    series: EnergySeries,
    weather: pd.DataFrame,
    *,
    column: str = "ghi",
    max_shift_h: float = 6,
    by: By = "month",
    min_days: int = 14,
    max_interval_h: float = 1.0,
    n_boot: int = 200,
    seed: int = 0,
    daylight_share: float = DAYLIGHT_SHARE,
    interval: float = INTERVAL,
) -> pd.DataFrame:
    """Clock offset of each generation series against an irradiance series, to a fraction of a step.

    `weather`: `ds` (with a time zone, values labelled by the START of the interval, as the library's readers
    return them), `column` (irradiance, W/m2) and optionally `unique_id` (one weather per series; without it
    the same for all). A day-ahead forecast works: its cloud timing is imprecise day by day, but not late on
    average. Returns one row per series and period (`"all"`, and each month with `by="month"`):

    - `offset_h`: hours the production labels are LATE relative to the weather (fix: `ds - offset_h`);
      continuous, from the correlation peak refined between steps;
    - `low_h`, `high_h`: the `interval` (90%) interval of `offset_h` by resampling days;
    - `corr`, `corr_zero`: correlation of the anomalies at the best whole-step shift and at 0;
    - `days`: days with daylight hours in both; `confident`: `days >= min_days` and the interval no wider than
      `max_interval_h`.

    Daylight steps: those whose mean of the month is above `daylight_share` (5%) of that month's peak.
    """
    if series.quantity != "generation":
        raise ValueError(f"The clock check needs a generation series, not {series.quantity!r}")
    if "ds" not in weather.columns or column not in weather.columns:
        raise ValueError(f"weather needs `ds` and {column!r} columns")
    if getattr(weather["ds"].dt, "tz", None) is None:
        raise ValueError("weather.ds must carry a time zone")
    if not 0 <= daylight_share < 1:
        raise ValueError("daylight_share must be in [0, 1)")
    if not 0 < interval < 1:
        raise ValueError("interval must be in (0, 1)")
    st = step(series.freq)
    spd = pd.Timedelta(days=1) / st
    if spd != int(spd) or spd < 2:
        raise ValueError(f"The step must divide a day into several intervals, not {series.freq!r}")
    max_k = max(1, min(round(pd.Timedelta(hours=max_shift_h) / st), int(spd) // 2))
    shifts = np.arange(-max_k, max_k + 1)
    hours_per_step = st.total_seconds() / 3600
    rng = np.random.default_rng(seed)

    v = series.frame.loc[series.frame["valid"] & series.frame["y"].notna(), ["unique_id", "ds", "y"]]
    w = weather.assign(ds=weather["ds"].dt.tz_convert(series.tz))
    rows = []
    for uid, g in v.groupby("unique_id", sort=True):
        wu = w[w["unique_id"].astype(str) == str(uid)] if "unique_id" in w.columns else w
        x = wu.dropna(subset=[column]).drop_duplicates("ds").set_index("ds")[column].astype(float)
        if x.empty:
            continue
        y = pd.Series(g["y"].to_numpy(float), index=pd.DatetimeIndex(g["ds"]))
        ya, day_y = _anomaly(y, daylight_share)
        xa, _ = _anomaly(x, daylight_share)
        times = pd.DatetimeIndex(y.index)
        wall = times.tz_localize(None)
        month = wall.strftime("%Y-%m").to_numpy()
        date = wall.normalize().to_numpy()
        # x shifted by k steps: a series late by k lines up with the weather k steps BEFORE
        xk = np.stack([xa.reindex(times - int(k) * st).to_numpy() for k in shifts])  # (K, n)
        periods: list[tuple[str, np.ndarray]] = [("all", np.ones(len(y), bool))]
        if by == "month":
            periods += [(str(m), month == m) for m in np.unique(month)]
        for name, sel in periods:
            row = _fit_weather(
                ya.to_numpy()[sel], xk[:, sel], date[sel], day_y[sel], shifts, rng, n_boot, interval
            )
            if row is None or (name != "all" and row["days"] < min_days):
                continue
            for c in ("offset_h", "low_h", "high_h"):
                row[c] *= hours_per_step
            row["confident"] = bool(
                row["days"] >= min_days and row["high_h"] - row["low_h"] <= max_interval_h
            )
            rows.append({"unique_id": str(uid), "period": name, **row})
    cols = ["unique_id", "period", "offset_h", "low_h", "high_h", "corr", "corr_zero", "days", "confident"]
    return pd.DataFrame(rows, columns=cols)


def clock_weather_notes(table: pd.DataFrame, min_offset_h: float = 0.25) -> list[str]:
    """A note per series whose whole-series offset against the weather is confident, at least `min_offset_h`
    and with an interval that excludes 0."""
    notes: list[str] = []
    for r in table[table["period"] == "all"].to_dict(orient="records"):
        off, low, high = float(r["offset_h"]), float(r["low_h"]), float(r["high_h"])
        if not r["confident"] or abs(off) < min_offset_h or low <= 0 <= high:
            continue
        notes.append(
            Note(
                "Series {uid}: the production follows the clouds {hours:.1f} h {side} than the weather data "
                "(90% interval {low:+.1f} to {high:+.1f} h). A fraction of an hour usually means intervals "
                "labelled by their end or a logger clock that drifted; check the source before using the "
                "weather as an input.",
                uid=r["unique_id"],
                hours=abs(off),
                side=_LATER if off > 0 else _EARLIER,
                low=low,
                high=high,
            )
        )
    return notes


# ---------------------------------------------------------------------- pieces
def _anomaly(s: pd.Series, daylight_share: float = DAYLIGHT_SHARE) -> tuple[pd.Series, np.ndarray]:
    """The series minus its mean profile of the month (local wall clock), and the daylight mask: steps whose
    mean of the month is above `daylight_share` of that month's peak."""
    wall = pd.DatetimeIndex(s.index).tz_localize(None)
    key = [wall.strftime("%Y-%m"), wall.hour * 60 + wall.minute]
    mean = s.groupby(key).transform("mean")
    peak = mean.groupby(wall.strftime("%Y-%m")).transform("max")
    return s - mean, (mean > daylight_share * peak).to_numpy()


def _fit_weather(
    ya: np.ndarray,
    xk: np.ndarray,
    date: np.ndarray,
    day: np.ndarray,
    shifts: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
    interval: float = INTERVAL,
) -> dict[str, float | int] | None:
    """Offset (in steps) from the anomaly correlation, with a day bootstrap. Sums per day and shift are kept
    so each resample is a weighted sum, not a new pass over the hours."""
    ok = day[None] & np.isfinite(ya)[None] & np.isfinite(xk)  # (K, n)
    dates, d_idx = np.unique(date, return_inverse=True)
    if not ok.any():
        return None
    n_days = len(dates)
    stats = np.zeros((len(shifts), n_days, 6))  # n, sx, sy, sxx, syy, sxy
    for i in range(len(shifts)):
        m = ok[i]
        a, b, d = xk[i, m], ya[m], d_idx[m]
        for j, val in enumerate((np.ones_like(a), a, b, a * a, b * b, a * b)):
            stats[i, :, j] = np.bincount(d, weights=val, minlength=n_days)
    used = stats[:, :, 0].max(axis=0) > 0
    if used.sum() < 2:
        return None

    def offset(weights: np.ndarray) -> tuple[float, np.ndarray]:
        t = np.einsum("d,kdj->kj", weights, stats)
        n, sx, sy, sxx, syy, sxy = t.T
        with np.errstate(invalid="ignore", divide="ignore"):
            r = (n * sxy - sx * sy) / np.sqrt((n * sxx - sx * sx) * (n * syy - sy * sy))
        k = int(np.nanargmax(np.where(np.isnan(r), -np.inf, r)))
        delta = 0.0
        if 0 < k < len(r) - 1:  # parabola through the peak and its neighbours
            den = r[k - 1] - 2 * r[k] + r[k + 1]
            if den < 0:
                delta = float(np.clip(0.5 * (r[k - 1] - r[k + 1]) / den, -0.5, 0.5))
        return float(shifts[k] + delta), r

    est, r = offset(np.ones(n_days))
    idx = np.flatnonzero(used)
    boot = [
        offset(np.bincount(rng.choice(idx, len(idx)), minlength=n_days).astype(float))[0]
        for _ in range(n_boot)
    ]
    zero = int(np.flatnonzero(shifts == 0)[0])
    return {
        "offset_h": est,
        # rounded so the default 0.9 gives exactly the 0.05 and 0.95 quantiles (1 - 0.9 is not 0.1 in floats)
        "low_h": float(np.quantile(boot, round((1 - interval) / 2, 12))),
        "high_h": float(np.quantile(boot, round((1 + interval) / 2, 12))),
        "corr": float(np.nanmax(r)),
        "corr_zero": float(r[zero]),
        "days": int(used.sum()),
    }


def _fit(
    cells: pd.DataFrame, cs: np.ndarray, spd: int, shifts: np.ndarray, hours_per_step: float
) -> dict[str, float | int] | None:
    """Best shift for one series in one period. `cells`: date, pos, y; `cs`: clear-sky per orientation."""
    dates, d_idx = np.unique(cells["date"].to_numpy(), return_inverse=True)
    n_days, n_o = len(dates), cs.shape[1]
    pos = cells["pos"].to_numpy()
    # the day the clock falls back repeats a wall-clock hour: the later row wins, for production and clear
    # sky alike, so the comparison stays consistent
    ok = (pos >= 0) & (pos < spd)
    p = np.full((n_days, spd), np.nan)
    c = np.full((n_o, n_days, spd), np.nan)
    p[d_idx[ok], pos[ok]] = cells["y"].to_numpy(float)[ok]
    c[:, d_idx[ok], pos[ok]] = cs[ok].T
    if not np.nansum(p) > 0:
        return None
    # production shifted EARLIER by k steps: a series late by k lines up with the clear sky at k
    idx = (np.arange(spd)[None, :] + shifts[:, None]) % spd  # (K, spd)
    pk = p[:, idx].transpose(1, 0, 2)  # (K, days, spd)
    # the clear sky is NaN exactly where the production is: one mask per shift, the same for every orientation
    both = (~np.isnan(pk) & ~np.isnan(p)[None]).astype(float)  # (K, days, spd)
    n = both.sum(axis=1)  # (K, spd)
    with np.errstate(invalid="ignore", divide="ignore"):
        prof_p = np.nansum(pk * both, axis=1) / n  # (K, spd)
        prof_c = np.einsum("kds,ods->oks", both, np.nan_to_num(c)) / n[None]  # (O, K, spd)
    score = _corr(prof_p[None], prof_c)  # (O, K)
    best_o = np.where(np.isnan(score), -np.inf, score).argmax(axis=0)  # (K,)
    by_k = score[best_o, np.arange(len(shifts))]
    if np.isnan(by_k).all():
        return None
    k = int(np.nanargmax(by_k))
    zero = int(np.flatnonzero(shifts == 0)[0])

    complete = ~np.isnan(p).any(axis=1) & (np.nansum(p, axis=1) > 0)
    if complete.any():
        day = np.full((len(shifts), int(complete.sum())), -np.inf)
        for co in c[:, complete]:  # one orientation at a time: memory stays (K, days, spd)
            r = _corr(pk[:, complete], co[None])
            day = np.maximum(day, np.where(np.isnan(r), -np.inf, r))
        agreement = float(np.mean(day.argmax(axis=0) == k))
    else:
        agreement = float("nan")
    o = best_o[k]
    return {
        "offset_h": float(shifts[k] * hours_per_step),
        "centroid_shift_h": ((_centroid(prof_p[zero]) - _centroid(prof_c[o, zero]) + spd / 2) % spd - spd / 2)
        * hours_per_step,
        "score": float(by_k[k]),
        "score_zero": float(by_k[zero]),
        "days": int(np.sum(~np.isnan(p).all(axis=1))),
        "agreement": agreement,
    }


def _corr(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pearson correlation along the last axis, NaN where either side is constant."""
    a = a - a.mean(axis=-1, keepdims=True)
    b = b - b.mean(axis=-1, keepdims=True)
    den = np.sqrt((a * a).sum(axis=-1) * (b * b).sum(axis=-1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, (a * b).sum(axis=-1) / den, np.nan)


def _centroid(profile: np.ndarray) -> float:
    """Circular centroid of a daily profile, in steps (0 .. len)."""
    n = len(profile)
    ang = 2 * np.pi * (np.arange(n) + 0.5) / n
    w = np.clip(np.nan_to_num(profile), 0, None)
    return float(np.angle(np.sum(w * np.exp(1j * ang))) % (2 * np.pi) / (2 * np.pi) * n - 0.5)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "unique_id",
            "period",
            "offset_h",
            "centroid_shift_h",
            "score",
            "score_zero",
            "days",
            "agreement",
            "confident",
        ]
    )
