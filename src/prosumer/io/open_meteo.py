"""Weather forecasts from several models (Open-Meteo): the archive of past day-ahead forecasts (Previous Runs
API, `fetch_previous_runs`) and the live forecast for the coming days (`fetch_forecast`).

Why several: in the benchmark the gap between regime C (the real forecast) and B (the weather of the day
itself) is the quality of the weather forecast, not the training (B-short x B was not significant). Pilot
F2(a) gave the LightGBM six models and their spread and it passed the median of all models (+0.373 against
+0.330 with ECMWF IFS alone). Each model errs differently, and the spread between them says how uncertain the
day is.

What `previous_day1` is: the value the model forecast ONE DAY BEFORE for that hour, the forecast that existed
at 00:00 of the day (`lead_days` changes it). The archive starts at different dates per model: 2024-01-19 for
ICON, Meteo-France, GEM and CMA; ~2024-03-06 for ECMWF IFS; 2025-01-03 for UKMO and 2025-02-17 for ECMWF AIFS
(checked 2026-10-11 at the benchmark's plants); JMA has no `previous_day1`. Hence `coverage`: a model that
starts after the training period begins cannot be compared on the same footing.

Conventions of the result (the same as the benchmark's `comum.exog_previsao`, which this module replaces):
- the API labels a radiation value by the END of its hour (the mean over the preceding hour): it is moved to
  the start, so `ds` = h covers [h, h+1);
- temperature is instantaneous: the hour gets the mean of its two ends;
- times are requested in UTC and converted to `tz`, so daylight saving never duplicates or drops an hour.

Checked live on 2026-10-11 against the benchmark's download (Cascavel, ECMWF IFS and GFS, 240 hours): GHI
identical; temperature 0.1-0.2 degC apart in every hour, with either time-zone setting: the archive itself was
revised. Keep the downloaded file of a published result; a new download reproduces it only approximately.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any

import pandas as pd

from ..provenance import OPEN_METEO_CITATION, Provenance, attach, today

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MAX_FORECAST_DAYS = 16  # the API's limit; most models stop earlier (see `HORIZON_DAYS`)

# name in the result -> (API variable, "interval" = mean over the preceding hour | "instant")
VARIABLES: dict[str, tuple[str, str]] = {
    "ghi": ("shortwave_radiation", "interval"),
    "temperature": ("temperature_2m", "instant"),
    "cloud_cover": ("cloud_cover", "instant"),
}
# The pilot's six models with a complete archive since the start of the benchmark's regime C.
DEFAULT_MODELS = (
    "ecmwf_ifs025",
    "gfs_seamless",
    "icon_seamless",
    "meteofrance_seamless",
    "gem_seamless",
    "cma_grapes_global",
)

# How far ahead each model reaches in the live API, in days from 00 UTC of the request day (measured on
# 2026-10-12 at the Dingle houses: last hour with a GHI value). The mean of the models therefore rests on
# fewer models as the lead grows: past ~5 days only IFS, GFS, GEM and ICON remain, past ~10 only IFS and GFS.
HORIZON_DAYS = {
    "ecmwf_ifs025": 15.0,
    "gfs_seamless": 16.0,
    "icon_seamless": 8.0,
    "meteofrance_seamless": 4.75,
    "gem_seamless": 10.5,
    "cma_grapes_global": 5.5,
}

Getter = Callable[[str, dict[str, Any]], dict[str, Any]]


def fetch_previous_runs(
    lat: float,
    lon: float,
    *,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    models: Iterable[str] = DEFAULT_MODELS,
    variables: Iterable[str] = ("ghi", "temperature"),
    lead_days: int = 1,
    tz: str = "UTC",
    get: Getter | None = None,
    pause_s: float = 1.0,
) -> pd.DataFrame:
    """Download the forecasts each model issued `lead_days` before, one request per model.

    Returns a long frame: `model`, `ds` (aware, in `tz`, interval start), one column per variable. Hours
    without a forecast stay NaN (`coverage` summarizes them). `start` and `end` are dates (inclusive).
    `get(url, params)` returns the decoded JSON; the default uses urllib (with `truststore` when installed,
    for proxies that inspect TLS). Tests pass a fake one: nothing here needs the network to be tested.

    The coordinates are sent to Open-Meteo: round them first if the site is private.
    """
    if not 1 <= lead_days <= 7:
        raise ValueError("lead_days must be in 1-7 (the API archives previous_day1 to previous_day7)")
    names = list(variables)
    unknown = set(names) - set(VARIABLES)
    if unknown:
        raise ValueError(f"Unknown variables {sorted(unknown)}; known: {sorted(VARIABLES)}")
    get = get or _get
    api = {VARIABLES[n][0] + f"_previous_day{lead_days}": n for n in names}
    a, b = pd.Timestamp(start), pd.Timestamp(end)
    parts = []
    for i, model in enumerate(models):
        if i and pause_s:
            time.sleep(pause_s)  # the free API limits the request rate
        params = {
            "latitude": lat,
            "longitude": lon,
            "models": model,
            # one day of margin on each side: the label shift and the time zone move the ends by a few hours
            "start_date": (a - pd.Timedelta(days=1)).date().isoformat(),
            "end_date": (b + pd.Timedelta(days=1)).date().isoformat(),
            "hourly": ",".join(api),
            "timezone": "GMT",
        }
        parts.append(parse_hourly(get(URL, params)["hourly"], api, tz=tz).assign(model=model))
    out = pd.concat(parts, ignore_index=True)
    lo = pd.Timestamp(a.date(), tz=tz)
    hi = pd.Timestamp(b.date(), tz=tz) + pd.Timedelta(hours=23)
    out = out[(out["ds"] >= lo) & (out["ds"] <= hi)]
    result = out[["model", "ds", *names]].reset_index(drop=True)
    return attach(result, provenance([str(m) for m in pd.unique(result["model"])], lead_days))


def fetch_forecast(
    lat: float,
    lon: float,
    *,
    days: int = MAX_FORECAST_DAYS,
    models: Iterable[str] = DEFAULT_MODELS,
    variables: Iterable[str] = ("ghi", "temperature"),
    tz: str = "UTC",
    get: Getter | None = None,
    pause_s: float = 1.0,
) -> pd.DataFrame:
    """Download the live forecast of each model for today and the next `days - 1` days, one request per model.

    Same long frame and conventions as `fetch_previous_runs` (`model`, `ds` aware in `tz` and labelling the
    start of its hour, one column per variable), from 00:00 of today in `tz`. Each model stops at its own
    horizon (`HORIZON_DAYS`); its later hours are NaN, and `coverage` or `wide` (the mean uses the models with
    a value) show it. `frame.attrs["issued"]` keeps the UTC time of the download: the lead of an hour is
    counted from it.

    Forecast skill falls with the lead, cloud cover above all: beyond about a week a single model's hourly
    GHI says little more than the season does. `prosumer.outlook` decides how much to trust each lead.

    The coordinates are sent to Open-Meteo: round them first if the site is private.
    """
    if not 1 <= days <= MAX_FORECAST_DAYS:
        raise ValueError(f"days must be in 1-{MAX_FORECAST_DAYS} (the API's limit)")
    names = list(variables)
    unknown = set(names) - set(VARIABLES)
    if unknown:
        raise ValueError(f"Unknown variables {sorted(unknown)}; known: {sorted(VARIABLES)}")
    get = get or _get
    api = {VARIABLES[n][0]: n for n in names}
    issued = pd.Timestamp.now(tz="UTC").floor("min")
    parts = []
    for i, model in enumerate(models):
        if i and pause_s:
            time.sleep(pause_s)
        params = {
            "latitude": lat,
            "longitude": lon,
            "models": model,
            # one day of margin: the time zone moves the ends by a few hours
            "past_days": 1,
            "forecast_days": min(days + 1, MAX_FORECAST_DAYS),
            "hourly": ",".join(api),
            "timezone": "GMT",
        }
        parts.append(parse_hourly(get(FORECAST_URL, params)["hourly"], api, tz=tz).assign(model=model))
    out = pd.concat(parts, ignore_index=True)
    lo = issued.tz_convert(tz).normalize()
    out = out[(out["ds"] >= lo) & (out["ds"] < lo + pd.Timedelta(days=days))]
    result = attach(
        out[["model", "ds", *names]].reset_index(drop=True),
        forecast_provenance([str(m) for m in pd.unique(out["model"])]),
    )
    result.attrs["issued"] = issued.isoformat()
    return result


def forecast_provenance(models: Iterable[str], retrieved: str | None = None) -> Provenance:
    """Where a live forecast download comes from (same licence and terms as the archive, see `provenance`)."""
    return Provenance(
        source=f"Open-Meteo Forecast API: {', '.join(models)}",
        license="CC-BY-4.0",
        citation=OPEN_METEO_CITATION,
        url="https://open-meteo.com/en/docs",
        retrieved=retrieved or today(),
        notes="free API: non-commercial use only (https://open-meteo.com/en/terms); commercial use needs "
        "their paid API",
    )


def provenance(models: Iterable[str], lead_days: int = 1, retrieved: str | None = None) -> Provenance:
    """Where a Previous Runs download comes from: CC BY 4.0 data, free API for non-commercial use only
    (licence and terms checked on 2026-10-11, see `prosumer.provenance`). `fetch_previous_runs` attaches it to
    its result (`frame.attrs["provenance"]`) and `wide` carries it over; attach it yourself to a frame read
    back from a file (`prosumer.provenance.attach`), with the date it was downloaded."""
    return Provenance(
        source=f"Open-Meteo Previous Runs API, previous_day{lead_days}: {', '.join(models)}",
        license="CC-BY-4.0",
        citation=OPEN_METEO_CITATION,
        url="https://open-meteo.com/en/docs/previous-runs-api",
        retrieved=retrieved or today(),
        notes="free API: non-commercial use only (https://open-meteo.com/en/terms); commercial use needs "
        "their paid API",
    )


def parse_hourly(
    hourly: dict[str, list[Any]], api: dict[str, str], *, tz: str, source_tz: str = "UTC"
) -> pd.DataFrame:
    """Turn the API's `hourly` block into the library's convention (see the module docstring).

    `api` maps the API key to the result's name (`{"shortwave_radiation_previous_day1": "ghi"}`). `source_tz`:
    the time zone the API wrote `time` in (the `timezone` request parameter).
    """
    t = pd.to_datetime(pd.Series(hourly["time"]))
    t = t.dt.tz_localize(source_tz) if t.dt.tz is None else t
    grid = pd.date_range(t.min(), t.max(), freq="h")
    out = pd.DataFrame(index=grid[:-1].tz_convert(tz))  # the last label closes the last hour
    for key, name in api.items():
        s = pd.Series(
            pd.to_numeric(pd.Series(hourly[key]), errors="coerce").to_numpy(float), index=t.to_numpy()
        )
        s = s[~s.index.duplicated()].reindex(grid)
        kind = VARIABLES[name][1]
        # interval: label h+1 -> the hour that starts at h; instant: mean of the two ends of the hour
        v = s.shift(-1) if kind == "interval" else (s + s.shift(-1)) / 2
        out[name] = v.iloc[:-1].to_numpy()
    return out.rename_axis("ds").reset_index()


def coverage(
    frame: pd.DataFrame,
    *,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    variable: str = "ghi",
) -> pd.DataFrame:
    """Per model: first and last hour with a value and the fraction of hours with one in [start, end].

    Read it before combining models: one that starts after the training period begins either shortens the
    training of every model combined with it or enters with gaps (pilot F2(a) kept the AIFS apart for that
    reason).
    """
    rows = []
    for model, g in frame.groupby("model", sort=False):
        lo = g["ds"].min() if start is None else _aware(start, g["ds"].dt.tz)
        hi = g["ds"].max() if end is None else _aware(end, g["ds"].dt.tz) + pd.Timedelta(hours=23)
        inside = g[(g["ds"] >= lo) & (g["ds"] <= hi)]
        ok = inside.loc[inside[variable].notna(), "ds"]
        expected = int((hi - lo) / pd.Timedelta(hours=1)) + 1
        rows.append(
            {
                "model": model,
                "first": ok.min() if len(ok) else pd.NaT,
                "last": ok.max() if len(ok) else pd.NaT,
                "fraction": len(ok) / expected if expected > 0 else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def wide(frame: pd.DataFrame, *, unique_id: str | Iterable[str] | None = None) -> pd.DataFrame:
    """One row per hour: a column per model and variable (`ghi_<model>`), plus their mean and spread.

    `<variable>_mean` and `<variable>_spread` (standard deviation across the models with a value that hour)
    are the pilot's inputs. With `unique_id` the rows are repeated for each series id, the shape
    `DayAhead(covariates=...)` takes: one site's weather for the series measured there.
    """
    names = [c for c in frame.columns if c in VARIABLES]
    w = frame.pivot_table(index="ds", columns="model", values=names, dropna=False, sort=False)
    w.columns = ["_".join(map(str, c)) for c in w.columns]
    for v in names:
        cols = [c for c in w.columns if c.startswith(f"{v}_") and not c.endswith(("_mean", "_spread"))]
        w[f"{v}_mean"] = w[cols].mean(axis=1)
        w[f"{v}_spread"] = w[cols].std(axis=1, ddof=0)
    w = w.sort_index().reset_index()
    if unique_id is not None:
        ids = [unique_id] if isinstance(unique_id, str) else list(unique_id)
        w = pd.concat([w.assign(unique_id=u) for u in ids], ignore_index=True)[["unique_id", *w.columns]]
    w.attrs = dict(frame.attrs)  # the provenance of the download, when it carries one
    return w


# ---------------------------------------------------------------------- transport
def _get(url: str, params: dict[str, Any], *, tries: int = 3, timeout: float = 300.0) -> dict[str, Any]:
    ctx = None
    try:  # pragma: no cover - depends on the machine
        import ssl

        import truststore

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        pass
    q = url + "?" + urllib.parse.urlencode(params)
    for k in range(tries):  # pragma: no cover - network
        try:
            with urllib.request.urlopen(q, timeout=timeout, context=ctx) as r:
                data: dict[str, Any] = json.loads(r.read().decode("utf-8"))
            if data.get("error"):
                raise RuntimeError(f"Open-Meteo: {data.get('reason')}")
            return data
        except (OSError, TimeoutError):
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))
    raise AssertionError("unreachable")  # pragma: no cover


def _aware(value: str | pd.Timestamp, tz: Any) -> pd.Timestamp:
    t = pd.Timestamp(value)
    return t.tz_localize(tz) if t.tzinfo is None else t.tz_convert(tz)


__all__ = [
    "DEFAULT_MODELS",
    "FORECAST_URL",
    "HORIZON_DAYS",
    "MAX_FORECAST_DAYS",
    "URL",
    "VARIABLES",
    "coverage",
    "fetch_forecast",
    "fetch_previous_runs",
    "forecast_provenance",
    "parse_hourly",
    "provenance",
    "wide",
]
