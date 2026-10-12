"""Forecast of the coming days (up to weeks), hourly and per day, to plan when to run heavy loads.

`analyze` checks how good a day-ahead forecast would have been on the last days of the data. This module looks
forward: from the end of the data it forecasts each hour of the next `days` days, as far as anything is known.

How (simple on purpose, every step can be explained to the person using it):

- **Generation** (needs the site). The plant is described by two numbers learnt from its own clear days
  (`diagnostics`): the orientation of the panels (or the tilt and azimuth the person gives) and the effective
  peak power `kw_eff` (energy of a clear day / clear-sky irradiation on the panel plane, median of the recent
  clear days). Then, for each hour:
  - *weather*: `kw_eff` x the irradiance on the panel plane computed from the forecast GHI (mean of the
    weather models that reach that hour);
  - *seasonal*: `kw_eff` x the clear-sky irradiance on the panel plane x the typical clearness of that
    calendar month in the data (how much of a clear day an average day of that month gave);
  - *forecast* = seasonal + trust(lead) x (weather - seasonal). The trust of each lead day says how much a
    weather forecast that far ahead is worth more than the season; it falls with the lead and is zero where
    no model reaches (`TRUST`, set by the horizon pilot, `docs/projeto/PILOTOS_F1_F2.md`).
- **Consumption** (no weather): per hour, the mean of the same weekday and hour in the last `weeks` weeks.
  It does not depend on the lead: a household's week repeats; what changes it (holidays, a trip, a new
  appliance) is not in the data.

The low/high columns are ranges, not calibrated intervals: across the weather models (generation, blended by
the same trust with the seasonal 10-90% range of clearness) and across the last `weeks` weeks (consumption).

Beyond the last weather model (~16 days) the generation is only the seasonal expectation: the average day of
that month, not a forecast of that day's weather. It is labelled so (`source = "seasonal"`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from . import physics
from .contracts import EnergySeries
from .diagnostics import (
    CLEAR_QUANTILE,
    CLEAR_RATIO,
    CLEAR_WINDOW_DAYS,
    _clear,
    _complete_days,
    _hourly,
    _index,
    _roof,
)

MAX_DAYS = 35
WEEKS = 4
KW_EFF_DAYS = 60  # clear days of the last 60 days give the effective peak power
MIN_CLEAR = 5
# Trust in the weather forecast per lead day: lead 1 is the day after the forecast is issued (the archive's
# `previous_day1`, the benchmark's day-ahead task); the rest of the issue day itself counts as lead 1.
# PROVISIONAL until the horizon pilot (`piloto_horizonte.py`) measures it: full for the first days, falling
# to zero by day 16.
# fmt: off
TRUST: tuple[float, ...] = (
    1.0, 1.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05,
)
# fmt: on
# An hourly GHI above 1.2 x clear sky + 50 W/m2 is not weather but a broken value: on 2026-10-12 the live
# `meteofrance_seamless` gave up to 2750 W/m2 at Cascavel on its 4th day (clear sky ~990). Brief cloud
# enhancement exceeds clear sky by minutes, not by 20% over a whole hour. The whole model-day is left out.
IMPLAUSIBLE = (1.2, 50.0)
HIGH, MEDIUM = 0.66, 0.33  # trust above which a day is labelled high / medium confidence

Prefer = Literal["high", "low"]


@dataclass
class Outlook:
    """What `forecast_ahead` returns. `hourly`: `unique_id, ds, lead_day, y_hat, low, high, source, n_models`;
    `daily`: per series and day, the totals and a confidence label; `method`: the numbers behind it
    (orientation,
    effective power, clearness by month, trust by lead); `notes`: what the person should know."""

    hourly: pd.DataFrame
    daily: pd.DataFrame
    quantity: str
    unit: str = "kWh"
    method: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly version (timestamps as ISO text)."""

        def records(df: pd.DataFrame) -> list[dict[str, Any]]:
            out = df.copy()
            for c in out.columns:
                if pd.api.types.is_datetime64_any_dtype(out[c]):
                    out[c] = out[c].map(lambda t: t.isoformat())
            return [{str(k): _plain(v) for k, v in r.items()} for r in out.to_dict(orient="records")]

        return {
            "quantity": self.quantity,
            "unit": self.unit,
            "hourly": records(self.hourly),
            "daily": records(self.daily),
            "method": _plain(self.method),
            "notes": list(self.notes),
        }

    def to_markdown(self) -> str:
        """Readable summary: the daily table and the notes."""
        d = self.daily.copy()
        d["date"] = d["date"].dt.strftime("%a %Y-%m-%d")
        cols = ["unique_id", "date", "lead_day", "total", "low", "high", "source", "confidence"]
        lines = [f"# Outlook ({self.quantity}, {self.unit})", "", _table(d[cols].round(2))]
        if self.notes:
            lines += ["", "## Notes", "", *[f"- {n}" for n in self.notes]]
        return "\n".join(lines) + "\n"


def forecast_ahead(
    series: EnergySeries,
    *,
    days: int = 7,
    site: tuple[float, float] | None = None,
    weather: pd.DataFrame | None = None,
    start: str | pd.Timestamp | None = None,
    tilt: float | Mapping[str, float] | None = None,
    azimuth: float | Mapping[str, float] | None = None,
    kwp: float | Mapping[str, float] | None = None,
    weeks: int = WEEKS,
    trust: tuple[float, ...] = TRUST,
) -> Outlook:
    """Hourly forecast of the `days` days after the data end (generation or consumption), with daily totals.

    `site` (latitude, longitude) is required for generation. `weather`: a live forecast from
    `io.open_meteo.fetch_forecast` (long, with `model`) or its `wide` frame; without it a generation forecast
    is the seasonal expectation only. `start`: first forecast day (default: the day after the data end; with a
    weather forecast that starts later, its first day). `tilt`, `azimuth` (degrees, azimuth as a compass
    bearing, 180 = facing south): give them when known, otherwise they are fitted on the clear days; one value
    or one per series. `kwp`: the peak power of the panels, used only when the data have too few clear days to
    learn the effective power. `trust`: weight of the weather forecast per lead day (see the module
    docstring).
    """
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days must be in 1-{MAX_DAYS}")
    s = series.to_kwh()
    if s.freq != "h":
        raise ValueError(f"The outlook needs an hourly series, not freq={s.freq!r}; resample first")
    if s.quantity == "generation" and site is None:
        raise ValueError("A generation forecast needs the site (latitude, longitude)")
    valid = s.frame.loc[s.frame["valid"]]
    if valid.empty:
        raise ValueError("The series has no valid value")
    last = valid["ds"].max()
    w = None if weather is None else _wide(weather, s.tz)
    notes: list[str] = []
    first = (last + pd.Timedelta(hours=1)).normalize() + (
        pd.Timedelta(days=1) if (last + pd.Timedelta(hours=1)).hour else pd.Timedelta(0)
    )
    if start is not None:
        t = pd.Timestamp(start)
        first = (t.tz_localize(s.tz) if t.tzinfo is None else t.tz_convert(s.tz)).normalize()
    elif w is not None and w["ds"].min().normalize() > first:
        notes.append(
            f"The data end on {last.date()}; the forecast starts on {w['ds'].min().date()}, the first day of "
            "the "
            "weather forecast. The days in between are not forecast."
        )
        first = w["ds"].min().normalize()
    end = (first.tz_localize(None) + pd.Timedelta(days=days)).tz_localize(s.tz, nonexistent="shift_forward")
    hours = pd.date_range(first, end, freq="h", inclusive="left")
    issue = _issue_day(w, first)
    lead = (hours.tz_localize(None).normalize() - issue).days.to_numpy()
    if s.quantity == "generation":
        assert site is not None
        hourly, method, more = _generation(s, site, hours, lead, w, tilt, azimuth, kwp, trust)
    else:
        hourly, method, more = _consumption(s, hours, lead, weeks)
        if w is not None:
            more.append("The weather forecast is not used for consumption (the profile of recent weeks is).")
    notes += more
    if lead.max() > len(trust) and s.quantity == "generation":
        notes.append(
            f"Days beyond day {len(trust)} are the seasonal expectation (an average day of the month), not a "
            "forecast of their weather."
        )
    daily = _daily(hourly)
    return Outlook(hourly=hourly, daily=daily, quantity=s.quantity, method=method, notes=notes)


def best_windows(
    outlook: Outlook, hours: int = 3, *, prefer: Prefer | None = None, unique_id: str | None = None
) -> pd.DataFrame:
    """The best block of `hours` consecutive hours of each day to run a heavy load.

    `prefer="high"` (default for generation): the block with the most forecast production; `"low"` (default
    for consumption): the block with the least forecast consumption. Returns `unique_id, date, start, end,
    energy, confidence`; `energy` is the forecast total of the block.
    """
    if not 1 <= hours <= 24:
        raise ValueError("hours must be in 1-24")
    prefer = prefer or ("high" if outlook.quantity == "generation" else "low")
    h = outlook.hourly if unique_id is None else outlook.hourly[outlook.hourly["unique_id"] == unique_id]
    conf = outlook.daily.set_index(["unique_id", "date"])["confidence"]
    rows = []
    for (uid, date), g in h.groupby(["unique_id", h["ds"].dt.tz_localize(None).dt.normalize()], sort=True):
        y = g["y_hat"].to_numpy(dtype=float)
        if len(y) < hours or not np.isfinite(y).any():
            continue
        sums = np.convolve(np.nan_to_num(y), np.ones(hours), mode="valid")
        i = int(np.argmax(sums) if prefer == "high" else np.argmin(sums))
        rows.append(
            {
                "unique_id": uid,
                "date": date,
                "start": g["ds"].iloc[i],
                "end": g["ds"].iloc[i + hours - 1] + pd.Timedelta(hours=1),
                "energy": float(sums[i]),
                "confidence": conf.get((uid, date)),
            }
        )
    return pd.DataFrame(rows, columns=["unique_id", "date", "start", "end", "energy", "confidence"])


# ---------------------------------------------------------------------- generation
def _generation(
    s: EnergySeries,
    site: tuple[float, float],
    hours: pd.DatetimeIndex,
    lead: np.ndarray,
    w: pd.DataFrame | None,
    tilt: float | Mapping[str, float] | None,
    azimuth: float | Mapping[str, float] | None,
    kwp: float | Mapping[str, float] | None,
    trust: tuple[float, ...],
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    notes: list[str] = []
    f = _hourly(s, site)
    days = _complete_days(f)
    clear = _clear(days, CLEAR_WINDOW_DAYS, CLEAR_QUANTILE, CLEAR_RATIO)
    fitted = _roof(f, clear, site) if tilt is None or azimuth is None else None
    sun = physics.mean_sun(hours, *site)
    cs = physics.clear_sky_ghi(hours, *site)
    a = np.array([trust[max(k, 1) - 1] if k <= len(trust) else 0.0 for k in lead])
    ghi, lo_ghi, hi_ghi, n_models, dropped = _weather_at(w, hours, cs)
    if dropped:
        notes.append(
            "Weather model-days left out because their GHI exceeds what the sun can give "
            f"(> {IMPLAUSIBLE[0]} x clear sky + {IMPLAUSIBLE[1]:.0f} W/m2 in some hour): "
            f"{', '.join(dropped)}."
        )
    a = np.where(np.isfinite(ghi), a, 0.0)  # no model reaches the hour: seasonal only
    out: list[pd.DataFrame] = []
    per_series: dict[str, Any] = {}
    method: dict[str, Any] = {"site": list(site), "trust": list(trust), "series": per_series}
    for uid in s.series:
        t, az, how = _orientation(uid, tilt, azimuth, fitted, site)
        if how == "default":
            notes.append(
                f"{uid}: the orientation could not be fitted from the data; assumed tilt {t:.0f} facing "
                f"{az:.0f}. "
                "Give tilt and azimuth for a better forecast."
            )
        idx = _index(f[f["unique_id"] == uid], clear, site, {}, (t, az))
        recent = idx[idx["date"] > idx["date"].max() - pd.Timedelta(days=KW_EFF_DAYS)] if len(idx) else idx
        if len(recent) < MIN_CLEAR:
            recent = idx.tail(15)
        k_src = "clear days"
        if len(recent) >= MIN_CLEAR:
            kw_eff = float(recent["index"].median())
        elif kwp is not None:
            kw_eff, k_src = 0.8 * _per(kwp, uid), "0.8 x kwp (too few clear days)"
            notes.append(f"{uid}: too few clear days to learn the plant; used 80% of the given kWp.")
        else:
            raise ValueError(f"{uid}: too few clear days to learn the plant's power; give kwp")
        clearness = _clearness(days[days["unique_id"] == uid], site, (t, az), kw_eff, s.tz)
        cs_poa = physics.poa_isotropic(cs, sun, t, az) / 1000.0
        month = hours.month.to_numpy()
        med = np.array([clearness["median"].get(m, clearness["fallback"][0]) for m in month])
        p10 = np.array([clearness["p10"].get(m, clearness["fallback"][1]) for m in month])
        p90 = np.array([clearness["p90"].get(m, clearness["fallback"][2]) for m in month])
        seasonal = kw_eff * cs_poa * med
        y_w = _poa(ghi, sun, t, az) * kw_eff
        lo_w, hi_w = _poa(lo_ghi, sun, t, az) * kw_eff, _poa(hi_ghi, sun, t, az) * kw_eff
        y = seasonal + a * (np.nan_to_num(y_w) - seasonal)
        low = kw_eff * cs_poa * p10 + a * (np.nan_to_num(lo_w) - kw_eff * cs_poa * p10)
        high = kw_eff * cs_poa * p90 + a * (np.nan_to_num(hi_w) - kw_eff * cs_poa * p90)
        out.append(
            pd.DataFrame(
                {
                    "unique_id": uid,
                    "ds": hours,
                    "lead_day": lead,
                    "y_hat": np.clip(y, 0, None),
                    "low": np.clip(np.minimum(low, y), 0, None),
                    "high": np.clip(np.maximum(high, y), 0, None),
                    "source": np.where(a > 0, "weather", "seasonal"),
                    "n_models": n_models,
                    "trust": a,
                }
            )
        )
        per_series[uid] = {
            "tilt": t,
            "azimuth": az,
            "orientation": how,
            "kw_eff": kw_eff,
            "kw_eff_from": k_src,
            "clear_days_used": len(recent),
            "clearness_by_month": {int(m): round(v, 3) for m, v in clearness["median"].items()},
        }
    if w is None:
        notes.append("No weather forecast given: every day is the seasonal expectation.")
    return pd.concat(out, ignore_index=True), method, notes


def _orientation(
    uid: str,
    tilt: float | Mapping[str, float] | None,
    azimuth: float | Mapping[str, float] | None,
    fitted: pd.DataFrame | None,
    site: tuple[float, float],
) -> tuple[float, float, str]:
    if tilt is not None and azimuth is not None:
        return _per(tilt, uid), _per(azimuth, uid), "given"
    assert fitted is not None
    row = fitted[fitted["unique_id"] == uid]
    if len(row) and np.isfinite(row["tilt"].iloc[0]):
        t = _per(tilt, uid) if tilt is not None else float(row["tilt"].iloc[0])
        az = _per(azimuth, uid) if azimuth is not None else float(row["azimuth"].iloc[0])
        return t, az, "fitted" if tilt is None and azimuth is None else "given + fitted"
    lat = site[0]
    return min(abs(lat), 30.0), 0.0 if lat < 0 else 180.0, "default"  # facing the equator


def _clearness(
    days: pd.DataFrame, site: tuple[float, float], orientation: tuple[float, float], kw_eff: float, tz: str
) -> dict[str, Any]:
    """Day energy / (kw_eff x clear-sky irradiation on the panel plane): median and 10-90% by calendar "
    "month."""
    if days.empty or kw_eff <= 0:
        return {"median": {}, "p10": {}, "p90": {}, "fallback": (0.7, 0.3, 1.0)}
    d = days.copy()
    start = pd.Timestamp(d["date"].min()).tz_localize(tz)
    stop = (pd.Timestamp(d["date"].max()) + pd.Timedelta(days=1)).tz_localize(tz)
    t = pd.date_range(start, stop, freq="h", inclusive="left")
    sun = physics.mean_sun(t, *site)
    poa = physics.poa_isotropic(physics.clear_sky_ghi(t, *site), sun, *orientation) / 1000.0
    expected = pd.Series(poa).groupby(t.tz_localize(None).normalize()).sum()
    d["r"] = (d["energy"] / (kw_eff * expected.reindex(pd.DatetimeIndex(d["date"])).to_numpy())).clip(0, 1.5)
    d = d[np.isfinite(d["r"])]
    by = d.groupby(pd.DatetimeIndex(d["date"]).month)["r"]
    recent = d[d["date"] > d["date"].max() - pd.Timedelta(days=30)]["r"]
    fb = (
        (float(recent.median()), float(recent.quantile(0.1)), float(recent.quantile(0.9)))
        if len(recent)
        else (0.7, 0.3, 1.0)
    )
    return {
        "median": by.median().to_dict(),
        "p10": by.quantile(0.1).to_dict(),
        "p90": by.quantile(0.9).to_dict(),
        "fallback": fb,
    }


def _weather_at(
    w: pd.DataFrame | None, hours: pd.DatetimeIndex, cs: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Mean, min and max GHI across the models at each hour, the number of models, and the model-days left
    out as physically implausible (see `IMPLAUSIBLE`)."""
    nan = np.full(len(hours), np.nan)
    if w is None:
        return nan, nan, nan, np.zeros(len(hours), dtype=int), []
    x = w.set_index("ds").reindex(hours)
    models = [c for c in x.columns if c.startswith("ghi_") and c not in ("ghi_mean", "ghi_spread")]
    if not models:
        models = [c for c in ("ghi", "ghi_mean") if c in x.columns][:1]
        if not models:
            raise ValueError("The weather frame has no GHI column (`ghi`, `ghi_<model>` or `ghi_mean`)")
    m = x[models].to_numpy(dtype=float, copy=True)
    day = hours.tz_localize(None).normalize()
    bad = m > IMPLAUSIBLE[0] * cs[:, None] + IMPLAUSIBLE[1]
    dropped = []
    for j, name in enumerate(models):
        for d in pd.unique(day[bad[:, j]]):
            m[day == d, j] = np.nan
            dropped.append(f"{name.removeprefix('ghi_')} {pd.Timestamp(d).date()}")
    n = np.isfinite(m).sum(axis=1)
    ok = np.isfinite(m)
    mean = np.where(n > 0, np.where(ok, m, 0).sum(axis=1) / np.maximum(n, 1), np.nan)
    lo = np.where(n > 0, np.where(ok, m, np.inf).min(axis=1), np.nan)
    hi = np.where(n > 0, np.where(ok, m, -np.inf).max(axis=1), np.nan)
    return mean, lo, hi, n, dropped


def _poa(ghi: np.ndarray, sun: pd.DataFrame, tilt: float, azimuth: float) -> np.ndarray:
    ok = np.isfinite(ghi)
    out = np.full(len(ghi), np.nan)
    if ok.any():
        out[ok] = physics.poa_isotropic(np.clip(ghi[ok], 0, None), sun.loc[ok], tilt, azimuth) / 1000.0
    return out


# ---------------------------------------------------------------------- consumption
def _consumption(
    s: EnergySeries, hours: pd.DatetimeIndex, lead: np.ndarray, weeks: int
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    if weeks < 1:
        raise ValueError("weeks must be >= 1")
    notes: list[str] = []
    out = []
    f = s.frame
    for uid in s.series:
        g = f[(f["unique_id"] == uid) & f["valid"]]
        cut = g["ds"].max() - pd.Timedelta(weeks=weeks)
        g = g[g["ds"] > cut]
        key = g["ds"].dt.dayofweek * 24 + g["ds"].dt.hour
        prof = g.groupby(key)["y"].agg(["mean", "min", "max", "size"])
        want = hours.dayofweek * 24 + hours.hour
        p = prof.reindex(want)
        if p["mean"].isna().any():
            # an hour of the week never seen in the window: fall back to the mean of that hour of the day
            by_hour = g.groupby(g["ds"].dt.hour)["y"].agg(["mean", "min", "max"]).reindex(hours.hour)
            for c in ("mean", "min", "max"):
                p[c] = np.where(p[c].isna(), by_hour[c].to_numpy(), p[c].to_numpy())
        if int(prof["size"].min() if len(prof) else 0) < weeks:
            notes.append(f"{uid}: fewer than {weeks} weeks of valid data behind some hours of the profile.")
        out.append(
            pd.DataFrame(
                {
                    "unique_id": uid,
                    "ds": hours,
                    "lead_day": lead,
                    "y_hat": p["mean"].to_numpy(),
                    "low": p["min"].to_numpy(),
                    "high": p["max"].to_numpy(),
                    "source": "profile",
                    "n_models": 0,
                    "trust": np.nan,
                }
            )
        )
    method = {"rule": f"mean of the same weekday and hour over the last {weeks} weeks", "weeks": weeks}
    return pd.concat(out, ignore_index=True), method, notes


# ---------------------------------------------------------------------- shared
def _daily(hourly: pd.DataFrame) -> pd.DataFrame:
    h = hourly.assign(date=hourly["ds"].dt.tz_localize(None).dt.normalize())
    d = (
        h.groupby(["unique_id", "date"], sort=True)
        .agg(
            lead_day=("lead_day", "first"),
            total=("y_hat", "sum"),
            low=("low", "sum"),
            high=("high", "sum"),
            source=("source", lambda v: v.mode().iloc[0]),
            n_models=("n_models", "max"),
            trust=("trust", "max"),
        )
        .reset_index()
    )
    d["confidence"] = np.select(
        [d["source"] == "profile", d["trust"] >= HIGH, d["trust"] >= MEDIUM, d["trust"] > 0],
        ["typical week", "high", "medium", "low"],
        default="seasonal only",
    )
    return d


def _wide(weather: pd.DataFrame, tz: str) -> pd.DataFrame:
    from .io import open_meteo

    w = open_meteo.wide(weather) if "model" in weather.columns else weather.copy()
    if "unique_id" in w.columns:
        w = w.drop(columns="unique_id").drop_duplicates("ds")
    if getattr(w["ds"].dt, "tz", None) is None:
        raise ValueError("weather.ds must be time-zone aware")
    w["ds"] = w["ds"].dt.tz_convert(tz)
    w.attrs = dict(weather.attrs)
    return w


def _issue_day(w: pd.DataFrame | None, first: pd.Timestamp) -> pd.Timestamp:
    """The day the forecast is issued, naive: lead day 1 is the day after it. Taken from the weather download
    (`attrs["issued"]`) when there is one, else the day before `first`."""
    if w is not None and w.attrs.get("issued"):
        issued = pd.Timestamp(w.attrs["issued"]).tz_convert(first.tz)
        return issued.tz_localize(None).normalize()
    return first.tz_localize(None).normalize() - pd.Timedelta(days=1)


def _per(v: float | Mapping[str, float], uid: str) -> float:
    if isinstance(v, Mapping):
        if uid not in v:
            raise ValueError(f"No value for series {uid!r}; give one per series, or one for all")
        return float(v[uid])
    return float(v)


def _plain(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def _table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.to_numpy()]
    return "\n".join([head, sep, *body])


__all__ = ["MAX_DAYS", "TRUST", "Outlook", "best_windows", "forecast_ahead"]
