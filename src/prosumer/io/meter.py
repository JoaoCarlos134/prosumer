"""Generic reader for meter exports and any other table of energy or power readings (CSV or Excel).

Meter exports have no standard format, so nothing is assumed that the caller can say instead: which column
holds the time, which hold values, the unit, and what kind of value each row is:

- `kind="interval"`: energy of each interval (kWh or Wh per row), the usual load-profile export;
- `kind="cumulative"`: a register (the kWh counter) read at each timestamp. The energy of [t, t + step) is the
  next reading minus this one; readings are placed on a regular grid at their own step, so a missing reading
  leaves the steps around it invalid (the energy of the gap is known only in total, and spreading it would
  invent a profile). A NEGATIVE difference (the counter was reset, rolled over or replaced) is made invalid,
  not corrected, and counted in the provenance notes;
- `kind="power"`: the AVERAGE power (W or kW) over each interval, turned into energy by the step's duration.
  Instantaneous power samples are not averages; read them only if the step is short against the variation.

For "interval" and "power", `label` says whether a timestamp marks the start (default) or the end of its
interval: exports differ, and many label the end (00:15 = the energy of 00:00-00:15). If unsure, look at
where the daily profile peaks, or check a generation series with `prosumer.quality.clock_offset`.

The result is in kWh, `ds` = start of each step in `tz`, one series per value column. With `freq` the native
steps are SUMMED into steps of `freq`, valid when at least `min_coverage` of them exist. CSV files: the
separator (`;`, `,`, tab, `|`) and the decimal mark (Brazilian exports write `;` and `1.234,5`) are guessed
unless given; the day-first or month-first order of text dates is guessed too (`dayfirst`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from ..contracts import DstPolicy, EnergySeries, Quantity, Unit
from ..provenance import UNKNOWN, Provenance
from . import _tables
from ._tables import Label

Kind = Literal["interval", "cumulative", "power"]
_ENERGY: dict[str, float] = {"kWh": 1.0, "Wh": 1e-3}
_POWER: dict[str, float] = {"kW": 1.0, "W": 1e-3}


def _load(
    source: str | Path | pd.DataFrame,
    *,
    sep: str | None,
    encoding: str | None,
    sheet: str | int,
    skiprows: int,
) -> tuple[pd.DataFrame, str]:
    if isinstance(source, pd.DataFrame):
        return source.copy(), "table given in memory"
    path = Path(source)
    if _tables.is_excel(path):
        _tables.require_openpyxl("meter tables")
        frame = pd.read_excel(path, sheet_name=sheet, skiprows=skiprows, dtype=object, engine="openpyxl")
        return frame, path.name
    frame, _ = _tables.read_csv_text(path, sep=sep, encoding=encoding, skiprows=skiprows)
    return frame, path.name


def read_table(
    source: str | Path | pd.DataFrame,
    *,
    time_column: str,
    value_columns: str | Sequence[str],
    tz: str,
    unit: Unit,
    quantity: Quantity = "consumption",
    freq: str | None = None,
    kind: Kind = "interval",
    label: Label = "start",
    names: Mapping[str, str] | Sequence[str] | None = None,
    min_coverage: float = 11 / 12,
    step: str | None = None,
    decimal: str | None = None,
    sep: str | None = None,
    dayfirst: bool | None = None,
    sheet: str | int = 0,
    skiprows: int = 0,
    encoding: str | None = None,
    dst: DstPolicy = "raise",
    source_tz: str | None = None,
) -> EnergySeries:
    """An energy series (kWh) from a meter export or any table with a time column and value columns.

    - `source`: a CSV/Excel file or a DataFrame already in memory;
    - `time_column`, `value_columns`: the column names (one series per value column; `names` renames them,
      as a mapping or a list in the same order);
    - `tz`: the time zone of the result and, by default, of naive times (wall-clock time); times written with
      an offset are converted; `source_tz`: the zone of naive times when it differs (e.g. "UTC" for a logger
      that writes UTC: its file has no gap or repeat at the daylight saving changes);
    - `unit`: of the values: kWh or Wh for "interval" and "cumulative", kW or W for "power";
    - `kind`, `label`: see the module docstring;
    - `freq`: output step (sum); None keeps the native step, which is inferred unless `step` is given;
    - `decimal`, `sep`, `dayfirst`: None guesses them; `sheet`, `skiprows`, `encoding`: where the table is.
    """
    if kind in ("interval", "cumulative") and unit not in _ENERGY:
        hint = " (use kind='power' for W/kW)" if unit in _POWER else ""
        raise ValueError(f"kind={kind!r} needs an energy unit (kWh, Wh), not {unit!r}{hint}")
    if kind == "power" and unit not in _POWER:
        raise ValueError(f"kind='power' needs a power unit (kW, W), not {unit!r}")
    if kind not in ("interval", "cumulative", "power"):
        raise ValueError("kind must be 'interval', 'cumulative' or 'power'")
    cols = [value_columns] if isinstance(value_columns, str) else list(value_columns)
    frame, origin = _load(source, sep=sep, encoding=encoding, sheet=sheet, skiprows=skiprows)
    frame.columns = [str(c).strip() for c in frame.columns]
    missing = {time_column, *cols} - set(frame.columns)
    if missing:
        raise ValueError(f"Columns {sorted(missing)} not in the table; it has {list(frame.columns)}")
    times = _tables.parse_times(frame[time_column], dayfirst=dayfirst)
    unparsed = int(times.isna().sum() - frame[time_column].map(_blank).sum())
    keep = times.notna()
    frame, times = frame[keep], times[keep]
    dec = decimal or _tables.guess_decimal(frame[c] for c in cols)
    long = pd.concat(
        [
            pd.DataFrame(
                {"unique_id": c, "time": times.to_numpy(), "y": _tables.to_number(frame[c], dec).to_numpy()}
            )
            for c in cols
        ],
        ignore_index=True,
    )
    long["time"] = (
        pd.to_datetime(long["time"]) if not isinstance(times.dtype, pd.DatetimeTZDtype) else long["time"]
    )
    long["ds"] = _tables.localize(long["time"], long["unique_id"], tz, dst, source_tz)
    long = long[long["ds"].notna()]
    dup = long.duplicated(["unique_id", "ds"], keep="first")
    n_dup = int(dup.sum())
    long = long[~dup].sort_values(["unique_id", "ds"], kind="stable")
    native = pd.Timedelta(step) if step else _tables.infer_step(long)
    resets = 0
    if kind == "cumulative":
        parts = []
        for uid, g in long.groupby("unique_id", sort=False):
            s = g.set_index("ds")["y"]
            grid = pd.date_range(s.index[0], s.index[-1], freq=native)
            r = s.reindex(grid)
            d = r.shift(-1) - r
            neg = d < 0
            resets += int(neg.sum())
            d[neg] = np.nan
            parts.append(
                pd.DataFrame({"unique_id": uid, "ds": grid[:-1], "y": d.to_numpy()[:-1] * _ENERGY[unit]})
            )
        long = pd.concat(parts, ignore_index=True)
    else:
        factor = _ENERGY[unit] if kind == "interval" else _POWER[unit] * native.total_seconds() / 3600.0
        long = long.assign(ds=_tables.shift_label(long["ds"], label, native), y=long["y"] * factor)
    out_freq = freq or _freq_alias(native)
    out = _tables.aggregate(
        long[["unique_id", "ds", "y"]], native=native, freq=out_freq, min_coverage=min_coverage
    )
    rename = _tables.names_for(cols, names, "value columns")
    out["unique_id"] = out["unique_id"].map(rename)
    notes = [
        f"kind={kind}, unit={unit}"
        + (f", timestamps read as the {label.upper()} of each interval" if kind != "cumulative" else ""),
        f"native step {native}",
        f"{n_dup} duplicate timestamp(s) dropped, first kept",
    ]
    if kind == "cumulative":
        notes.append(f"{resets} negative register difference(s) (reset/rollover) made invalid")
    if unparsed:
        notes.append(f"{unparsed} row(s) with an unreadable time left out")
    if out_freq != _freq_alias(native):
        notes.append(f"a step is valid with >= {min_coverage:.3g} of its native steps")
    prov = Provenance(source=f"meter table: {origin}", license=UNKNOWN, notes="; ".join(notes))
    return EnergySeries.from_dataframe(
        out, unit="kWh", quantity=quantity, tz=tz, freq=out_freq, provenance=prov
    )


def _blank(v: object) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip().lower() in _tables.NA_TOKENS


def _freq_alias(native: pd.Timedelta) -> str:
    """A pandas alias for a fixed step ("15min", "h", "30s")."""
    seconds = int(native.total_seconds())
    if seconds % 3600 == 0:
        return "h" if seconds == 3600 else f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}min"
    return f"{seconds}s"


__all__ = ["Kind", "read_table"]
