"""Hourly weather of the day itself from NASA POWER (point API): regime B, a ceiling, not a forecast.

What it is: satellite-derived irradiance (CERES SYN1deg) and reanalysis meteorology (MERRA-2) for a point,
hour by hour, published days to months after the fact. Giving a model these values for the day it forecasts
is giving it a PERFECT weather forecast: in the benchmark that is regime B, the ceiling that regime C (the
real day-ahead forecast, `io.open_meteo`) is measured against. Never use it as an input of an operational
forecast: on the day the forecast is issued these values do not exist yet.

Conventions of the result (the library's: `ds` aware, interval values labelled by the START of the hour):
- times are requested in UTC (`time-standard=UTC`) and converted to `tz`, so daylight saving never
  duplicates or drops an hour. POWER's other option, "LST", is a fixed offset per 15-degree longitude band
  (UTC-4 at -53.65, not the UTC-3 of the local clock), easy to misread;
- an hourly value is read as labelled by the hour it starts (the documentation only says "average values"
  per hour): the value stamped 13 UTC is the mean over [13:00, 14:00) UTC, so no shift is applied. The
  benchmark's Cascavel inputs agree: the project's alignment study
  (`legado/ia_solar/analise/cascavel/scripts/h1_align.py`, data stamped in LST = UTC-4 at that longitude)
  found the best match of the inverter's clock at -55 min, i.e. clock hour h <-> stamp h-1 LST = UTC h+3,
  which is this convention in the plant's UTC-3; on the saved benchmark inputs the Cascavel GHI also
  correlates best with the clear-sky curve at lag 0. Caveat: the Curitiba script reused the same -55 min,
  but there LST = UTC-3 (other band), and its saved GHI correlates best with clear sky one hour LATER
  (checked 2026-10-11): this module would not reproduce the benchmark's Curitiba hours. No raw POWER
  download was kept, so there is no hour-by-hour parity test (unlike `open_meteo`);
- the fill value (-999, or the one the response header declares) becomes NaN.

Units: irradiance in W/m2 (hourly mean), temperature in degC, wind in m/s, humidity in %.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

import numpy as np
import pandas as pd

from ..provenance import NASA_POWER_CITATION, Provenance, attach, today
from . import _http

URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
FILL_VALUE = -999.0
MAX_PARAMETERS = 15  # the API rejects more per request

# name in the result -> POWER parameter
VARIABLES: dict[str, str] = {
    "ghi": "ALLSKY_SFC_SW_DWN",
    "clear_sky_ghi": "CLRSKY_SFC_SW_DWN",
    "dni": "ALLSKY_SFC_SW_DNI",
    "dhi": "ALLSKY_SFC_SW_DIFF",
    "clearness_index": "ALLSKY_KT",
    "temperature": "T2M",
    "dew_point": "T2MDEW",
    "relative_humidity": "RH2M",
    "wind_speed": "WS2M",
    "wind_speed_10m": "WS10M",
    "pressure": "PS",
    "precipitation": "PRECTOTCORR",
    "cloud_cover": "CLOUD_AMT",
}

Getter = Callable[[str, dict[str, Any]], dict[str, Any]]


def fetch_hourly(
    lat: float,
    lon: float,
    *,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    variables: Iterable[str] = ("ghi", "clear_sky_ghi", "temperature"),
    tz: str = "UTC",
    community: str = "RE",
    chunk_days: int = 366,
    get: Getter | None = None,
    pause_s: float = 1.0,
) -> pd.DataFrame:
    """Download hourly POWER data for one point; `start` and `end` are local dates in `tz` (inclusive).

    Returns a frame with `ds` (aware, in `tz`, start of the hour) and one column per variable, every hour of
    the period present (NaN where POWER has no value: `coverage` summarizes them). Long periods are split in
    requests of at most `chunk_days` days. `get(url, params)` returns the decoded JSON; the default uses
    urllib (with `truststore` when installed). Tests pass a fake one.

    The coordinates are sent to NASA: round them first if the site is private (the project rounds the plants
    to 2 decimals; POWER's grid is ~0.5 degree anyway).
    """
    names = list(variables)
    unknown = set(names) - set(VARIABLES)
    if unknown:
        raise ValueError(f"Unknown variables {sorted(unknown)}; known: {sorted(VARIABLES)}")
    if not names or len(names) > MAX_PARAMETERS:
        raise ValueError(f"Ask for 1 to {MAX_PARAMETERS} variables per call (the API limit)")
    if chunk_days < 1:
        raise ValueError("chunk_days must be >= 1")
    get = get or _http.get_json
    api = {VARIABLES[n]: n for n in names}
    lo = pd.Timestamp(pd.Timestamp(start).date(), tz=tz)
    hi = pd.Timestamp(pd.Timestamp(end).date(), tz=tz) + pd.Timedelta(hours=23)
    if hi < lo:
        raise ValueError("end is before start")
    # UTC dates that contain the local period (the time zone moves the ends by up to a day)
    d0 = lo.tz_convert("UTC").normalize().tz_localize(None)
    d1 = hi.tz_convert("UTC").normalize().tz_localize(None)
    parts = []
    first = True
    for a in pd.date_range(d0, d1, freq=f"{chunk_days}D"):
        b = min(a + pd.Timedelta(days=chunk_days - 1), d1)
        if not first and pause_s:
            time.sleep(pause_s)  # be gentle with a free service
        first = False
        params = {
            "parameters": ",".join(api),
            "community": community,
            "latitude": lat,
            "longitude": lon,
            "start": a.strftime("%Y%m%d"),
            "end": b.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": "UTC",
        }
        parts.append(parse_hourly(get(URL, params), api, tz=tz))
    out = pd.concat(parts, ignore_index=True).drop_duplicates("ds").set_index("ds").sort_index()
    grid = pd.date_range(lo, hi, freq="h", name="ds")
    return attach(out.reindex(grid)[names].reset_index(), provenance(community))


def provenance(community: str = "RE", retrieved: str | None = None) -> Provenance:
    """Where a POWER hourly download comes from: NASA open data (CC0 under NASA's data use guidance, no
    restriction on use), cited with POWER's two references (checked on 2026-10-11, see `prosumer.provenance`).
    `fetch_hourly` attaches it to its result (`frame.attrs["provenance"]`)."""
    date = retrieved or today()
    return Provenance(
        source=f"NASA POWER hourly point API (community {community}; CERES SYN1deg, MERRA-2)",
        license="CC0-1.0",
        citation=NASA_POWER_CITATION.format(date=date.replace("-", "/")),
        url="https://power.larc.nasa.gov/",
        retrieved=date,
        notes="NASA asks to be cited and told of publications and redistribution "
        "(larc-power-project@mail.nasa.gov); the weather of the day itself: regime B, not a forecast",
    )


def parse_hourly(response: dict[str, Any], api: dict[str, str], *, tz: str) -> pd.DataFrame:
    """Turn a POWER JSON response (`time-standard=UTC`) into `ds` + one column per variable.

    `api` maps the POWER parameter to the result's name (`{"ALLSKY_SFC_SW_DWN": "ghi"}`). Keys are
    "YYYYMMDDHH" in UTC, each the start of its hour; the fill value becomes NaN.
    """
    if response.get("messages") and "properties" not in response:
        raise RuntimeError(f"NASA POWER: {response['messages']}")
    block = response["properties"]["parameter"]
    fill = float(response.get("header", {}).get("fill_value", FILL_VALUE))
    missing = set(api) - set(block)
    if missing:
        raise RuntimeError(f"NASA POWER did not return {sorted(missing)} (not available hourly?)")
    stamps = sorted(set().union(*(block[k].keys() for k in api)))
    ds = pd.DatetimeIndex(pd.to_datetime(stamps, format="%Y%m%d%H")).tz_localize("UTC").tz_convert(tz)
    out = pd.DataFrame({"ds": ds})
    for key, name in api.items():
        v = np.array([block[key].get(s, np.nan) for s in stamps], dtype=float)
        v[np.isclose(v, fill)] = np.nan
        out[name] = v
    return out


def coverage(
    frame: pd.DataFrame,
    *,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Per variable: first and last hour with a value and the fraction of hours with one in [start, end].

    POWER's hourly product lags real time by days to months (the benchmark's series ended on 2026-05-31 for
    that reason): check the end before choosing the test period.
    """
    tz = frame["ds"].dt.tz
    lo = frame["ds"].min() if start is None else _aware(start, tz)
    hi = frame["ds"].max() if end is None else _aware(end, tz) + pd.Timedelta(hours=23)
    inside = frame[(frame["ds"] >= lo) & (frame["ds"] <= hi)]
    expected = len(pd.date_range(lo, hi, freq="h"))
    rows = []
    for v in (c for c in frame.columns if c != "ds"):
        ok = inside.loc[inside[v].notna(), "ds"]
        rows.append(
            {
                "variable": v,
                "first": ok.min() if len(ok) else pd.NaT,
                "last": ok.max() if len(ok) else pd.NaT,
                "fraction": len(ok) / expected if expected else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _aware(value: str | pd.Timestamp, tz: Any) -> pd.Timestamp:
    t = pd.Timestamp(value)
    return t.tz_localize(tz) if t.tzinfo is None else t.tz_convert(tz)


__all__ = [
    "FILL_VALUE",
    "MAX_PARAMETERS",
    "URL",
    "VARIABLES",
    "coverage",
    "fetch_hourly",
    "parse_hourly",
    "provenance",
]
