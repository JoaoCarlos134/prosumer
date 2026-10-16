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
    no model reaches (`TRUST`, measured by the horizon pilot, see below).
- **Consumption** (no weather): per hour, the mean of that hour over the last `weeks` x 7 days of the same
  kind as the forecast day (weekday or weekend).
  It does not depend on the lead: a household's week repeats; what changes it (holidays, a trip, a new
  appliance) is not in the data.

The low/high columns are ranges, not calibrated intervals: across the weather models (generation, blended by
the same trust with the seasonal 10-90% range of clearness) and across the days of the profile (consumption).

Beyond lead 7 the generation is only the seasonal expectation (the pilot found no skill in the weather
there): the average day of that month, not a forecast of that day's weather. It is labelled so
(`source = "seasonal"`).

**What the horizon pilot measured** (`piloto_horizonte.py`, 2026-10-12, `docs/projeto/PILOTOS_F1_F2.md`):

- Generation, the two Parana plants, archived forecasts of 6 models issued 1-7 days ahead, test Aug/2025 to
  May/2026: the weather forecast beats the seasonal expectation on the daily total at every lead 1-7 at both
  plants (DM p < 0.001, Cascavel lead 7 p 0.0002); the daily skill falls from ~+0.49 (lead 1) to ~+0.20 (lead
  7). `TRUST` holds the fitted shrink factors a_1..a_7, pooled over the two plants, capped at 1 after the
  review (above 1 at leads 1-3 in the calibration, below 1 on the test). Leads 8-15 (one run a day, Apr-May
  2026 only, no calibration): no lead showed skill, and lead 15 (GFS alone) was worse than the season at
  Cascavel, so the weather is not used beyond lead 7. Two months of one season do not prove there is none.
- At lead 1, on the benchmark's hours: +0.325 against clear-sky persistence (the weather forecast alone, which
  is what a factor of 1 gives), a statistical tie with the benchmark's LightGBM in regime C (+0.330, DM p
  0.88) and below the median of the benchmark's models (+0.367). It is the method that is simple to explain,
  not the best available.
- Consumption, 20 Dingle houses, leads 1-14: the weekday/weekend profile of the last 4 weeks beat "same as the
  last day" at every lead (mean hourly skill +0.234) and the same-weekday mean of 4 weeks (+0.187).
- Still different from the pilot, on purpose: the roof is fitted on all the data at forecast time (the pilot
  fitted it once before its test); a model with impossible GHI is dropped from that day to the end of the
  forecast (the pilot dropped it for the day only); the live API's mix of models by lead is not the archive's
  the factors were fitted on (Meteo-France only to lead 3 there, no ICON at lead 7); one set of factors for
  every site, pooled over the two plants (per plant they differ by up to 0.1 at lead 1); the rest of the issue
  day (lead 0) uses lead 1's factor.
- Not measured: the thresholds of the confidence labels (they follow the measured skill, `SKILL`), a roof the
  person types in, other climates than Parana's.

**Tuning.** Every number above is an argument of `forecast_ahead`, with these defaults and origins:
`trust` and `skill` (MEASURED by the horizon pilot on the two Parana plants: elsewhere an assumption, and the
notes say so), `confidence` (0.40 / 0.25: set by hand so leads 1-3 read "high" and 4-6 "medium" with the
measured skill), `implausible` (1.2 x clear sky + 50 W/m2: physical, generic), `kw_eff_days` (60, else 120
days: the pilot's rule, set by hand), `min_month_days` (5: set by hand), `kwp_share` (0.8: a generic
performance ratio when no clear day is recent) and the clear-day rule `clear_window_days`, `clear_quantile`,
`clear_ratio` (shared with `diagnostics`, set by hand on the same plants).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import numpy as np
import pandas as pd

from . import physics
from .contracts import EnergySeries
from .diagnostics import (
    CLEAR_QUANTILE,
    CLEAR_RATIO,
    CLEAR_WINDOW_DAYS,
    GOOD_FIT_R2,
    _clear,
    _complete_days,
    _hourly,
    _index,
    _roof,
)

MAX_DAYS = 35
WEEKS = 4
KW_EFF_DAYS = 60  # clear days of the 60 days before the data end give the effective peak power ...
KW_EFF_FALLBACK_DAYS = 120  # ... or of the 120 days if there is none (the horizon pilot's rule)
MIN_MONTH_DAYS = 5  # days of the same month in earlier years for the typical clearness, else the last 30 days
# Shrink factor of the weather forecast toward the seasonal expectation per lead day. Lead 1 is the day after
# the forecast is issued (the archive's `previous_day1`); the rest of the issue day is lead 0 and uses lead
# 1's value. Fitted (least squares, before the test) by the horizon pilot on the two plants, leads 1-7; zero
# after. CAPPED AT 1 (decided after the review of the pilot, 2026-10-12, so post hoc): the fitted 1.08, 1.07
# and 1.05 at leads 1-3 did not hold on the test (fitted there, every factor is below 1) and cost 0.007-0.009
# of skill against the plain weather forecast; a factor above 1 would push the forecast past the weather.
TRUST: tuple[float, ...] = (1.0, 1.0, 1.0, 0.9158, 0.9058, 0.8550, 0.7854)
# Daily-total skill against the seasonal expectation at each lead (same pilot, mean of the two plants; leads
# 1-3 are the plain weather forecast's, `fisico`, since the factor is 1 there): what a day's confidence label
# says. A day only partly covered by the weather gets it in proportion.
SKILL: tuple[float, ...] = (0.496, 0.439, 0.408, 0.392, 0.344, 0.274, 0.199)
# An hourly GHI above 1.2 x clear sky + 50 W/m2 is not weather but a broken value: on 2026-10-12 the live
# `meteofrance_seamless` gave up to 2750 W/m2 at Cascavel on its 4th day (clear sky ~990). Brief cloud
# enhancement exceeds clear sky by minutes, not by 20% over a whole hour. The fault looked systematic in the
# lead (2-2.8x the other models from lead 3), and a cloudy day under the limit cannot be caught, so the model
# is left out from that day to the end of the forecast.
IMPLAUSIBLE = (1.2, 50.0)
HIGH, MEDIUM = 0.40, 0.25  # skill from which a day is labelled high / medium confidence (leads 1-3 / 4-6)
KWP_SHARE = 0.8  # effective power as a share of the given kWp when no recent clear day teaches it


@dataclass(frozen=True)
class _Tuning:
    """The tuning arguments of `forecast_ahead` (module docstring, "Tuning"), passed to the pieces."""

    skill: tuple[float, ...] = SKILL
    confidence: tuple[float, float] = (HIGH, MEDIUM)
    implausible: tuple[float, float] = IMPLAUSIBLE
    kw_eff_days: tuple[int, int] = (KW_EFF_DAYS, KW_EFF_FALLBACK_DAYS)
    min_month_days: int = MIN_MONTH_DAYS
    kwp_share: float = KWP_SHARE
    clear_window_days: int = CLEAR_WINDOW_DAYS
    clear_quantile: float = CLEAR_QUANTILE
    clear_ratio: float = CLEAR_RATIO

    def check(self) -> _Tuning:
        hi, mid = self.confidence
        if not 0 < mid <= hi:
            raise ValueError("confidence must be (high, medium) with 0 < medium <= high")
        if len(self.kw_eff_days) != 2 or not 0 < self.kw_eff_days[0] <= self.kw_eff_days[1]:
            raise ValueError("kw_eff_days must be (days, fallback days) with 0 < days <= fallback")
        if not 0 < self.kwp_share <= 1.5:
            raise ValueError("kwp_share must be in (0, 1.5]")
        if self.min_month_days < 1 or self.clear_window_days < 10:
            raise ValueError("min_month_days must be >= 1 and clear_window_days >= 10")
        if not 0 < self.clear_quantile <= 1 or not 0 < self.clear_ratio <= 1:
            raise ValueError("clear_quantile and clear_ratio must be in (0, 1]")
        if self.implausible[0] <= 0:
            raise ValueError("implausible must be (factor > 0, offset in W/m2)")
        return replace(self, kw_eff_days=(int(self.kw_eff_days[0]), int(self.kw_eff_days[1])))


_DEFAULT = _Tuning()

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
    skill: tuple[float, ...] = SKILL,
    confidence: tuple[float, float] = (HIGH, MEDIUM),
    implausible: tuple[float, float] = IMPLAUSIBLE,
    kw_eff_days: tuple[int, int] = (KW_EFF_DAYS, KW_EFF_FALLBACK_DAYS),
    min_month_days: int = MIN_MONTH_DAYS,
    kwp_share: float = KWP_SHARE,
    clear_window_days: int = CLEAR_WINDOW_DAYS,
    clear_quantile: float = CLEAR_QUANTILE,
    clear_ratio: float = CLEAR_RATIO,
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

    The other tuning arguments (module docstring, "Tuning", says where each default comes from): `skill`, the
    daily skill per lead day behind the confidence labels; `confidence` = (high, medium), the skill from which
    a day is labelled high or medium; `implausible` = (factor, W/m2), the GHI above factor x clear sky +
    W/m2 that drops a weather model; `kw_eff_days` = (days, fallback days) of clear days behind the effective
    power; `min_month_days`, days of the same month in earlier years for the season; `kwp_share`, the share of
    `kwp` used when no recent clear day teaches the power; `clear_window_days`, `clear_quantile`,
    `clear_ratio`, the clear-day rule.
    """
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days must be in 1-{MAX_DAYS}")
    tune = _Tuning(
        skill=tuple(skill),
        confidence=(float(confidence[0]), float(confidence[1])),
        implausible=(float(implausible[0]), float(implausible[1])),
        kw_eff_days=(kw_eff_days[0], kw_eff_days[1]),
        min_month_days=min_month_days,
        kwp_share=kwp_share,
        clear_window_days=clear_window_days,
        clear_quantile=clear_quantile,
        clear_ratio=clear_ratio,
    ).check()
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
        if first <= last:
            notes.append(
                f"The outlook starts on {first.date()}, before the data end ({last.date()}): those days are "
                "already in the data, so they are not forecasts and say nothing about skill."
            )
    elif w is not None and s.quantity == "generation" and _first_full_day(w["ds"]) > first:
        covered = _first_full_day(w["ds"])
        notes.append(
            f"The data end on {last.date()}; the forecast starts on {covered.date()}, the first local day "
            "the weather forecast covers in full. The days in between are not forecast."
        )
        first = covered
    end = (first.tz_localize(None) + pd.Timedelta(days=days)).tz_localize(s.tz, nonexistent="shift_forward")
    hours = pd.date_range(first, end, freq="h", inclusive="left")
    issue = _issue_day(w, first)
    lead = (hours.tz_localize(None).normalize() - issue).days.to_numpy()
    if s.quantity == "generation":
        assert site is not None
        hourly, method, more = _generation(s, site, hours, lead, w, tilt, azimuth, kwp, trust, tune)
    else:
        hourly, method, more = _consumption(s, hours, lead, weeks)
        if w is not None:
            more.append("The weather forecast is not used for consumption (the profile of recent weeks is).")
        more.append(
            "The consumption profile (weekdays and weekends apart, last 4 weeks) beat 'same as the last day' "
            "at every lead 1-14 on 20 Dingle houses (autumn 2020); a holiday, a trip or a new appliance is "
            "not in it."
        )
    notes += more
    if s.quantity == "generation" and w is not None:
        if (hourly["source"] == "weather").any():
            if tuple(trust) == TRUST or tune.skill == SKILL:
                notes.append(
                    "How much the weather forecast is trusted at each lead day, and the confidence labels, "
                    "were measured on two plants in Parana (Brazil), Aug/2025 to May/2026; elsewhere they "
                    "are an assumption (`trust=` and `skill=` change them)."
                )
        else:
            notes.append(
                "The weather forecast covers none of these hours: every day is the seasonal expectation."
            )
    if lead.max() > len(trust) and s.quantity == "generation":
        notes.append(
            f"Days beyond day {len(trust)} are the seasonal expectation (an average day of the month), not a "
            "forecast of their weather: beyond a week the weather forecasts showed no skill in the pilot."
        )
    daily = _daily(hourly, tune.confidence)
    gaps = daily[daily["missing_hours"] > 0]
    if len(gaps):
        notes.append(
            f"{int(gaps['missing_hours'].sum())} hours have no forecast (never seen in the recent data) and "
            "are left out of the daily totals and of the load windows."
        )
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
        if len(y) < hours:
            continue
        sums = np.convolve(np.nan_to_num(y), np.ones(hours), mode="valid")
        gaps = np.convolve(~np.isfinite(y), np.ones(hours), mode="valid") > 0
        if gaps.all():
            continue
        sums = np.where(gaps, np.nan, sums)  # a block with an hour of unknown forecast is not a candidate
        i = int(np.nanargmax(sums) if prefer == "high" else np.nanargmin(sums))
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
    tune: _Tuning = _DEFAULT,
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    notes: list[str] = []
    f = _hourly(s, site)
    days = _complete_days(f)
    clear = _clear(days, tune.clear_window_days, tune.clear_quantile, tune.clear_ratio)
    fitted = _roof(f, clear, site) if tilt is None or azimuth is None else None
    causal = _clear_trailing(days, tune)  # the horizon pilot's clear days: window ending on the day
    sun = physics.mean_sun(hours, *site)
    cs = physics.clear_sky_ghi(hours, *site)
    a = np.array([trust[max(k, 1) - 1] if k <= len(trust) else 0.0 for k in lead])
    sk = np.array([tune.skill[max(k, 1) - 1] if k <= len(tune.skill) else 0.0 for k in lead])
    ghi, lo_ghi, hi_ghi, n_models, dropped = _weather_at(w, hours, cs, tune.implausible)
    if dropped:
        notes.append(
            "Weather models left out from the first day their GHI exceeds what the sun can give "
            f"(> {tune.implausible[0]:g} x clear sky + {tune.implausible[1]:.0f} W/m2 in some hour): "
            f"{', '.join(dropped)}."
        )
    a = np.where(np.isfinite(ghi), a, 0.0)  # no model reaches the hour: seasonal only
    sk = np.where(a > 0, sk, 0.0)
    out: list[pd.DataFrame] = []
    per_series: dict[str, Any] = {}
    method: dict[str, Any] = {
        "site": list(site),
        "trust": list(trust),
        "skill": list(tune.skill),
        "series": per_series,
    }
    for uid in s.series:
        t, az, how = _orientation(uid, tilt, azimuth, fitted, site)
        if how in ("fitted", "given + fitted") and fitted is not None:
            row = fitted[fitted["unique_id"] == uid].iloc[0]
            if bool(row["edge"]) or float(row["r2"]) < GOOD_FIT_R2:
                notes.append(
                    f"{uid}: the roof fitted from the data is unreliable (tilt {row['tilt']:.0f}, "
                    f"R2 {row['r2']:.2f}; a tilt on the edge of the search or R2 < {GOOD_FIT_R2} means "
                    "the data do not identify it). Give the tilt and azimuth if you know them."
                )
        if how == "default":
            notes.append(
                f"{uid}: the orientation could not be fitted from the data; assumed tilt {t:.0f} facing "
                f"{az:.0f}. "
                "Give tilt and azimuth for a better forecast."
            )
        idx = _index(f[f["unique_id"] == uid], causal, site, {}, (t, az))
        g = f[(f["unique_id"] == uid) & f["y"].notna()]
        anchor = pd.Timestamp(g["date"].max()) + pd.Timedelta(days=1)  # issue = the day after the data
        k_dates = pd.DatetimeIndex(idx["date"]).to_numpy()
        k_vals = idx["index"].to_numpy(dtype=float)
        kw_eff = float(_kw_at(k_dates, k_vals, np.array([anchor.to_datetime64()]), tune.kw_eff_days)[0])
        used, k_src = _window_count(k_dates, anchor, tune.kw_eff_days)
        if not np.isfinite(kw_eff):
            if kwp is None:
                raise ValueError(
                    f"{uid}: no clear day in the {tune.kw_eff_days[1]} days before the data end to learn "
                    "the plant's power; give kwp"
                )
            share = tune.kwp_share
            kw_eff, k_src = share * _per(kwp, uid), f"{share:g} x kwp (no recent clear day)"
            notes.append(f"{uid}: no recent clear day to learn the plant; used {share:.0%} of the given kWp.")
        clearness = _clearness(
            days[days["unique_id"] == uid], site, (t, az), (k_dates, k_vals), anchor, s.tz, hours, tune
        )
        cs_poa = physics.poa_isotropic(cs, sun, t, az) / 1000.0
        med, p10, p90 = clearness["median"], clearness["p10"], clearness["p90"]
        if clearness["note"]:
            notes.append(f"{uid}: {clearness['note']}")
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
                    "skill": sk,
                    "sun": cs > 0,
                }
            )
        )
        per_series[uid] = {
            "tilt": t,
            "azimuth": az,
            "orientation": how,
            "kw_eff": kw_eff,
            "kw_eff_from": k_src,
            "clear_days_used": used,
            "clearness": clearness["summary"],
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


def _clear_trailing(days: pd.DataFrame, tune: _Tuning = _DEFAULT) -> pd.DataFrame:
    """Clear days judged with a window of `clear_window_days` that ENDS on the day (the horizon pilot's causal
    rule; `diagnostics` centres the window): ratio >= `clear_ratio` (0.9) x the window's `clear_quantile`
    (90%) quantile."""
    out = []
    for uid, g in days.groupby("unique_id", sort=False):
        r = (g.set_index("date")["energy"] / g.set_index("date")["cs"]).sort_index()
        full = r.reindex(pd.date_range(r.index.min(), r.index.max(), freq="D"))
        top = full.rolling(tune.clear_window_days, min_periods=10).quantile(tune.clear_quantile)
        t = pd.DataFrame({"unique_id": uid, "date": r.index, "ratio": r.to_numpy()})
        t["top"] = top.reindex(r.index).to_numpy()
        t["clear"] = (t["ratio"] >= tune.clear_ratio * t["top"]) & (t["ratio"] > 0)
        out.append(t)
    if not out:
        return pd.DataFrame(columns=["unique_id", "date", "ratio", "top", "clear"])
    return pd.concat(out, ignore_index=True)


def _kw_at(
    dates: np.ndarray,
    values: np.ndarray,
    at: np.ndarray,
    windows: tuple[int, int] = (KW_EFF_DAYS, KW_EFF_FALLBACK_DAYS),
) -> np.ndarray:
    """Effective power for an issue on each day of `at`: the median clear-day index of the `windows[0]` (60)
    days before it, else of the `windows[1]` (120) days, else NaN (the pilot's `kw_eff_por_emissao`)."""
    order = np.argsort(dates)
    d, v = dates[order], values[order]
    out = np.full(len(at), np.nan)
    for i, t in enumerate(at):
        for days in windows:
            a = np.searchsorted(d, t - np.timedelta64(days, "D"))
            b = np.searchsorted(d, t)
            if b > a:
                out[i] = np.median(v[a:b])
                break
    return out


def _window_count(
    dates: np.ndarray, anchor: pd.Timestamp, windows: tuple[int, int] = (KW_EFF_DAYS, KW_EFF_FALLBACK_DAYS)
) -> tuple[int, str]:
    """How many clear days gave the effective power, and from which window."""
    for days in windows:
        lo = (anchor - pd.Timedelta(days=days)).to_datetime64()
        n = int(((dates >= lo) & (dates < anchor.to_datetime64())).sum())
        if n:
            return n, f"median of the clear days of the {days} days before the data end"
    return 0, "none"


def _clearness(
    days: pd.DataFrame,
    site: tuple[float, float],
    orientation: tuple[float, float],
    kw: tuple[np.ndarray, np.ndarray],
    anchor: pd.Timestamp,
    tz: str,
    hours: pd.DatetimeIndex,
    tune: _Tuning = _DEFAULT,
) -> dict[str, Any]:
    """Typical clearness at each forecast hour, as the horizon pilot's climatology: the clearness of a past
    day is its energy / (the effective power at that day, from the clear days before it, x its clear-sky
    irradiation on the panel plane); for each forecast month, the median (and 10-90%) over the same calendar
    month of EARLIER years when there are at least `min_month_days` (5) such days, else over the 30 days
    before the data end."""
    nan = np.full(len(hours), np.nan)
    if days.empty:
        note = "no complete day to learn the season"
        return {"median": nan, "p10": nan, "p90": nan, "note": note, "summary": {}}
    d = days.sort_values("date").copy()
    start = pd.Timestamp(d["date"].min()).tz_localize(tz)
    stop = (pd.Timestamp(d["date"].max()) + pd.Timedelta(days=1)).tz_localize(tz)
    t = pd.date_range(start, stop, freq="h", inclusive="left")
    sun = physics.mean_sun(t, *site)
    poa = physics.poa_isotropic(physics.clear_sky_ghi(t, *site), sun, *orientation) / 1000.0
    expected = pd.Series(poa).groupby(t.tz_localize(None).normalize()).sum()
    when = pd.DatetimeIndex(d["date"])
    kw_day = _kw_at(*kw, when.to_numpy(), tune.kw_eff_days)
    d["r"] = d["energy"].to_numpy() / (kw_day * expected.reindex(when).to_numpy())
    d = d[np.isfinite(d["r"])]
    when = pd.DatetimeIndex(d["date"])
    last30 = d.loc[(when >= anchor - pd.Timedelta(days=30)) & (when < anchor), "r"]
    if len(last30):
        fallback = (float(last30.median()), float(last30.quantile(0.1)), float(last30.quantile(0.9)))
    else:
        fallback = (np.nan, np.nan, np.nan)
    out = {"median": nan.copy(), "p10": nan.copy(), "p90": nan.copy()}
    summary: dict[str, Any] = {}
    note = ""
    local = hours.tz_localize(None)
    ym = local.year.to_numpy() * 100 + local.month.to_numpy()
    for code in np.unique(ym):
        year, month = int(code) // 100, int(code) % 100
        pos = np.flatnonzero(ym == code)
        same = d.loc[(when.month == month) & (when.year < year), "r"]
        if len(same) >= tune.min_month_days:
            vals = (float(same.median()), float(same.quantile(0.1)), float(same.quantile(0.9)))
            src = f"{len(same)} days of the same month in earlier years"
        else:
            vals, src = fallback, f"the {len(last30)} days before the data end"
        for key, v in zip(("median", "p10", "p90"), vals, strict=True):
            out[key][pos] = v
        summary[f"{year}-{month:02d}"] = {"median": round(vals[0], 3), "from": src}
        if not np.isfinite(vals[0]):
            note = "too little history to learn the season: some days have no seasonal expectation"
    return {**out, "note": note, "summary": summary}


def _weather_at(
    w: pd.DataFrame | None,
    hours: pd.DatetimeIndex,
    cs: np.ndarray,
    implausible: tuple[float, float] = IMPLAUSIBLE,
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
    bad = m > implausible[0] * cs[:, None] + implausible[1]
    dropped = []
    for j, name in enumerate(models):
        if bad[:, j].any():
            d0 = day[bad[:, j]].min()
            m[day >= d0, j] = np.nan
            dropped.append(f"{name.removeprefix('ghi_')} from {pd.Timestamp(d0).date()}")
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
        # the horizon pilot's `perfil_dia_util`: that hour on the days of the same kind (weekday or weekend)
        key = (g["ds"].dt.dayofweek >= 5).astype(int) * 24 + g["ds"].dt.hour
        prof = g.groupby(key)["y"].agg(["mean", "min", "max", "size"])
        want = (hours.dayofweek >= 5).astype(int) * 24 + hours.hour
        p = prof.reindex(want)
        if p["mean"].isna().any():
            # an hour never seen on that kind of day in the window: fall back to the mean of that hour
            by_hour = g.groupby(g["ds"].dt.hour)["y"].agg(["mean", "min", "max"]).reindex(hours.hour)
            for c in ("mean", "min", "max"):
                p[c] = np.where(p[c].isna(), by_hour[c].to_numpy(), p[c].to_numpy())
        if int(prof["size"].min() if len(prof) else 0) < 2 * weeks:  # 2 weekend days a week
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
                    "skill": np.nan,
                    "sun": True,
                }
            )
        )
    method = {
        "rule": f"mean of the same hour over the last {weeks} weeks, weekdays and weekends apart",
        "weeks": weeks,
    }
    return pd.concat(out, ignore_index=True), method, notes


# ---------------------------------------------------------------------- shared
def _daily(hourly: pd.DataFrame, confidence: tuple[float, float] = (HIGH, MEDIUM)) -> pd.DataFrame:
    """Per series and day. Generation is labelled over its sun hours only (the night says nothing):
    `trust` and `skill` are their means (`skill`: the pilot's daily skill at that lead, 0 without weather),
    `n_models` the fewest models behind any of them, `source` "weather" when at least half of them have a
    weather forecast; the confidence follows the mean skill, so a day only partly covered by the weather is
    not labelled by its best hour. `missing_hours`: hours with no forecast (not in the totals)."""
    h = hourly.assign(
        date=hourly["ds"].dt.tz_localize(None).dt.normalize(),
        weather=(hourly["source"] == "weather").astype(float),
        missing=hourly["y_hat"].isna().astype(int),
    )
    sun = h[h["sun"]]
    keys = ["unique_id", "date"]
    d = (
        h.groupby(keys, sort=True)
        .agg(
            lead_day=("lead_day", "first"),
            total=("y_hat", "sum"),
            low=("low", "sum"),
            high=("high", "sum"),
            missing_hours=("missing", "sum"),
        )
        .reset_index()
    )
    by_sun = sun.groupby(keys).agg(
        trust=("trust", "mean"),
        skill=("skill", "mean"),
        n_models=("n_models", "min"),
        weather=("weather", "mean"),
    )
    d = d.merge(by_sun.reset_index(), on=keys, how="left")
    profile = hourly.groupby(["unique_id"])["source"].first().eq("profile")
    is_profile = d["unique_id"].map(profile).fillna(False).astype(bool)
    d["source"] = np.where(is_profile, "profile", np.where(d["weather"] >= 0.5, "weather", "seasonal"))
    d["n_models"] = d["n_models"].fillna(0).astype(int)
    d["confidence"] = np.select(
        [is_profile, d["skill"] >= confidence[0], d["skill"] >= confidence[1], d["skill"] > 0],
        ["typical week", "high", "medium", "low"],
        default="seasonal only",
    )
    cols = ["unique_id", "date", "lead_day", "total", "low", "high", "source", "n_models", "trust", "skill"]
    return d[[*cols, "confidence", "missing_hours"]]


def _first_full_day(ds: pd.Series) -> pd.Timestamp:
    """The first local day whose midnight is in `ds` (a frame that starts at 21:00 covers that day only in
    part)."""
    t0 = pd.Timestamp(ds.min())
    day = t0.normalize()
    return day if t0 == day else day + pd.Timedelta(days=1)


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


__all__ = ["MAX_DAYS", "SKILL", "TRUST", "Outlook", "best_windows", "forecast_ahead"]
