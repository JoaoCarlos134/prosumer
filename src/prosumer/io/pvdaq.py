"""NREL PVDAQ: measured data of real PV systems in the USA, public under CC BY 4.0.

PVDAQ (Photovoltaic Data Acquisition, doi:10.25984/1846021) publishes the time series of ~1,800 systems:
NREL's research arrays, commercial roofs and homes, many inverter brands, several climates. The metadata say
what a user's export rarely says: the orientation of each mount (tilt, azimuth), the inverter, and whether a
stamp marks the start, the centre or the end of its interval. That makes it the library's test bed away from
the project's own sites (Parana, Dingle): the roof fit, the clock checks and the clear-day rule can be checked
against the truth.

Shape of the files (checked on 2026-10-16 in the public bucket, `oedi-data-lake`):

- `pvdaq/csv/pvdata/system_id=<id>/year=<y>/month=<m>/day=<d>/system_<id>__date_<y>_<mm>_<dd>.csv`: one file
  per system and day, `measured_on` (local time of the logger, without a zone) and one column per sensor
  named `<sensor_name>__<metric_id>`, WITHOUT units (on system 50: `ac_power__752` in W, `dc_power__751`,
  `poa_irradiance__750` in W/m2, module and inverter temperatures, DC and AC voltages and currents). Systems
  differ in sensors and step (1 minute on NREL's arrays, 5 or 15 minutes elsewhere).
- the systems taken from PVOutput (ids >= 10000) have only daily totals per year
  (`<id>_ac_<start>_<end>.csv`): not enough for an hourly analysis, and refused with that message.
- `pvdaq/csv/system_metadata/<id>_system_metadata.json`: system, site (latitude, longitude, climate), mounts
  (tilt, azimuth as a compass bearing), inverters (`time_interval` L/C/R), metrics (units, on some systems).
- `pvdaq/csv/systems_<yyyymmdd>.csv` (the newest; the undated `systems.csv` is a 2022 list without time
  zones): one row per system with `timezone_or_utc_offset`, either a zone name
  ("America/New_York") or a fixed offset in hours WEST of UTC ("7" = UTC-7, no daylight saving: NREL's Golden
  arrays). The documentation warns that `measured_on` "could include DST": `quality.clock_offset` tells.

Data are CC BY 4.0: cite "NREL PVDAQ public datasets, doi:10.25984/1846021" when sharing results. This module
only reads; the bucket is public (no account), listed with the S3 REST API.
"""

from __future__ import annotations

import io as _io
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from ..contracts import EnergySeries, Unit
from ..provenance import Provenance
from . import _http, meter
from ._tables import Label

BUCKET = "https://oedi-data-lake.s3.amazonaws.com"
LICENSE = "CC-BY-4.0"
CITATION = "NREL PVDAQ public datasets (Photovoltaic Data Acquisition), doi:10.25984/1846021"
URL = "https://data.openei.org/submissions/4568"
_S3 = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_DAY_FILE = re.compile(r"system_(\d+)__date_(\d{4})_(\d{2})_(\d{2})\.csv$")
_LABEL: dict[str, Label] = {"L": "start", "R": "end"}

Getter = Callable[[str], bytes]


def zone(value: str | float | int) -> str:
    """The time zone of a PVDAQ `timezone_or_utc_offset`: a zone name as is, a number of hours west of UTC
    as a fixed offset (`"7"` -> `"Etc/GMT+7"`, i.e. UTC-7 all year)."""
    text = str(value).strip()
    try:
        hours = float(text)
    except ValueError:
        return text
    if hours != int(hours) or not -14 <= hours <= 14:
        raise ValueError(f"Unexpected PVDAQ time zone offset {value!r}")
    h = int(hours)
    return "Etc/GMT" if h == 0 else f"Etc/GMT{'+' if h > 0 else '-'}{abs(h)}"


def label_of(time_interval: str | None) -> Label | None:
    """Where a PVDAQ stamp sits in its interval (`time_interval` of the inverter or meter): "L" = start,
    "R" = end; "C" (centre) and unknown return None (the reader then takes the start and says so)."""
    return _LABEL.get((time_interval or "").strip().upper())


def read_days(
    sources: Iterable[str | Path | pd.DataFrame],
    *,
    tz: str,
    column: str = "ac_power",
    unit: Unit = "W",
    kind: meter.Kind = "power",
    label: Label = "start",
    freq: str | None = "h",
    name: str = "pvdaq",
    min_coverage: float = 11 / 12,
    provenance: Provenance | None = None,
) -> EnergySeries:
    """A generation series (kWh) from PVDAQ day files (paths or frames already read).

    `column`: the sensor, by its name before `__<metric_id>` (default the AC power, `ac_power`, read as
    average power in `unit` per step); a name that matches no column or several is an error that lists the
    columns. `tz`: the zone of `measured_on` (`zone(...)` of the systems list). `label`: "start" or "end" of
    the interval (`label_of` the inverter's `time_interval`). `freq`: output step (default hourly; None keeps
    the native step). Steps without a value count as missing, never as zero.
    """
    frames = [s if isinstance(s, pd.DataFrame) else pd.read_csv(s) for s in sources]
    if not frames:
        raise ValueError("No PVDAQ file given")
    data = pd.concat(frames, ignore_index=True)
    if "measured_on" not in data.columns:
        raise ValueError(
            "This PVDAQ file has no `measured_on` time column: the systems taken from PVOutput keep only "
            f"daily totals ({list(data.columns)[:4]}...), too coarse for an hourly analysis."
        )
    wanted = [c for c in data.columns if c.split("__")[0] == column]
    if len(wanted) != 1:
        found = [c for c in data.columns if c not in ("measured_on", "system_id")]
        raise ValueError(
            f"{'No' if not wanted else 'Several'} PVDAQ column(s) for {column!r} ({wanted or ''}); "
            f"the file has {found}"
        )
    prov = provenance or Provenance(source="NREL PVDAQ", license=LICENSE, citation=CITATION, url=URL)
    s = meter.read_table(
        data,
        time_column="measured_on",
        value_columns=wanted[0],
        tz=tz,
        unit=unit,
        quantity="generation",
        freq=freq,
        kind=kind,
        label=label,
        names=[name],
        min_coverage=min_coverage,
    )
    notes = f"PVDAQ column {wanted[0]} ({kind}, {unit}), stamps read as the {label.upper()} of each interval"
    p = s.provenance
    prov = replace(prov, notes="; ".join(x for x in (prov.notes, notes, p.notes if p else "") if x))
    return EnergySeries.from_dataframe(
        s.frame, unit="kWh", quantity="generation", tz=tz, freq=s.freq, provenance=prov
    )


# ---------------------------------------------------------------------- the public bucket
def _get(get: Getter | None) -> Getter:
    return get or (lambda url: _http.get_bytes(url, timeout=120.0))


def list_keys(prefix: str, *, get: Getter | None = None) -> list[str]:
    """Every object key under `prefix` in the bucket (S3 ListObjectsV2, followed page by page)."""
    keys: list[str] = []
    token: str | None = None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        root = ET.fromstring(_get(get)(f"{BUCKET}/?{urllib.parse.urlencode(params)}"))
        keys += [k.text or "" for k in root.iter(f"{_S3}Key")]
        more = root.find(f"{_S3}IsTruncated")
        token_el = root.find(f"{_S3}NextContinuationToken")
        if more is None or more.text != "true" or token_el is None:
            return keys
        token = token_el.text


def metadata(system_id: int, *, get: Getter | None = None) -> dict[str, Any]:
    """The system's metadata JSON (system, site, mounts, inverters, metrics)."""
    body = _get(get)(f"{BUCKET}/pvdaq/csv/system_metadata/{int(system_id)}_system_metadata.json")
    out: dict[str, Any] = json.loads(body)
    return out


def systems(*, get: Getter | None = None) -> pd.DataFrame:
    """The newest list of systems (`pvdaq/csv/systems_<yyyymmdd>.csv`): location, time zone, kW, climate,
    orientation, period."""
    dated = sorted(k for k in list_keys("pvdaq/csv/systems_", get=get) if re.search(r"_\d{8}\.csv$", k))
    if not dated:
        raise ValueError("No dated PVDAQ systems list in the bucket (pvdaq/csv/systems_<yyyymmdd>.csv)")
    return pd.read_csv(_io.BytesIO(_get(get)(f"{BUCKET}/{dated[-1]}")))


def fetch(
    system_id: int,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    tz: str | None = None,
    column: str = "ac_power",
    unit: Unit = "W",
    kind: meter.Kind = "power",
    label: Label | None = None,
    freq: str | None = "h",
    cache_dir: str | os.PathLike[str] | None = None,
    get: Getter | None = None,
) -> EnergySeries:
    """Download the day files of `system_id` between `start` and `end` (dates, inclusive) and read them.

    Day files are kept in the cache (`cache_dir`, default `$PROSUMER_DATA` or `~/.cache/prosumer`, subfolder
    `pvdaq/<id>`) and never downloaded twice. `tz`: default from the metadata (`timezone_code`) or the
    systems list. `label`: default from the first inverter's `time_interval` ("L" start, "R" end; else start,
    noted in the provenance). The series is named `pvdaq_<id>`.
    """
    sid = int(system_id)
    meta = metadata(sid, get=get)
    if tz is None:
        tz = meta.get("System", {}).get("timezone_code") or None
        if not tz:
            row = systems(get=get).query("system_id == @sid")
            if row.empty:
                raise ValueError(f"PVDAQ system {sid} is not in the systems list; pass tz=")
            tz = zone(row["timezone_or_utc_offset"].iloc[0])
    inv: dict[str, Any] = next(iter(meta.get("Inverters", {}).values()), {})
    note = ""
    if label is None:
        found = label_of(inv.get("time_interval"))
        label = found or "start"
        if found is None:
            note = f"time_interval {inv.get('time_interval')!r} of the inverter: stamps taken as the START"
    days = pd.date_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize(), freq="D")
    folder = _cache_root(cache_dir) / "pvdaq" / str(sid)
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for month in sorted({(d.year, d.month) for d in days}):
        prefix = f"pvdaq/csv/pvdata/system_id={sid}/year={month[0]}/month={month[1]}/"
        local = sorted(folder.glob(f"system_{sid}__date_{month[0]}_{month[1]:02d}_*.csv"))
        want = {d.strftime("%Y_%m_%d") for d in days if (d.year, d.month) == month}
        have = {
            m.group(2) + "_" + m.group(3) + "_" + m.group(4) for f in local if (m := _DAY_FILE.search(f.name))
        }
        if not want <= have:
            for key in list_keys(prefix, get=get):
                m = _DAY_FILE.search(key)
                if m is None or f"{m.group(2)}_{m.group(3)}_{m.group(4)}" not in want:
                    continue
                target = folder / key.rsplit("/", 1)[-1]
                if not target.exists():
                    target.write_bytes(_get(get)(f"{BUCKET}/{key}"))
        files += [
            f
            for f in sorted(folder.glob(f"system_{sid}__date_{month[0]}_{month[1]:02d}_*.csv"))
            if (m := _DAY_FILE.search(f.name)) and f"{m.group(2)}_{m.group(3)}_{m.group(4)}" in want
        ]
    if not files:
        raise ValueError(
            f"PVDAQ system {sid} has no day files between {days[0].date()} and {days[-1].date()} in the "
            "public bucket (systems from PVOutput have only daily totals)"
        )
    site = meta.get("Site", {})
    prov = Provenance(
        source=f"NREL PVDAQ system {sid} ({site.get('location', '?')})",
        license=LICENSE,
        citation=CITATION,
        url=URL,
        notes=note,
    )
    return read_days(
        files,
        tz=tz,
        column=column,
        unit=unit,
        kind=kind,
        label=label,
        freq=freq,
        name=f"pvdaq_{sid}",
        provenance=prov,
    )


def site_of(meta: dict[str, Any]) -> dict[str, Any]:
    """What the analysis needs from the metadata: latitude, longitude, kW, and the first mount's tilt and
    azimuth (compass bearing, 180 = south) when given."""
    site, system = meta.get("Site", {}), meta.get("System", {})
    mount: dict[str, Any] = next(iter(meta.get("Mount", {}).values()), {})

    def num(v: Any) -> float | None:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        return x

    return {
        "latitude": num(site.get("latitude")),
        "longitude": num(site.get("longitude")),
        "kw": num(system.get("power")),
        "tilt": num(mount.get("tilt")),
        "azimuth": num(mount.get("azimuth")),
        "tracking": str(mount.get("tracking", "")).lower() in ("t", "true", "1"),
        "climate": site.get("climate_type"),
    }


def _cache_root(cache_dir: str | os.PathLike[str] | None) -> Path:
    if cache_dir is not None:
        return Path(cache_dir)
    env = os.environ.get("PROSUMER_DATA")
    return Path(env) if env else Path.home() / ".cache" / "prosumer"


__all__ = [
    "BUCKET",
    "CITATION",
    "LICENSE",
    "fetch",
    "label_of",
    "list_keys",
    "metadata",
    "read_days",
    "site_of",
    "systems",
    "zone",
]
