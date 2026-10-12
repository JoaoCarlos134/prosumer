"""Fronius Solar.web exports ("export data"): the inverter's 5-minute records as a generation series.

The layout, known from the project's two plants (parsers in `legado/ia_solar/analise/*/scripts/merge_*.py`):
- one workbook per year (`.xlsx`, sometimes several sheets), or the same table as CSV;
- row 1: the column names in the language of the Solar.web account, each followed by `| <device> (<n>)`
  (e.g. `Energia | Primo 4.0-1 (1)`), except the time column (`Data e horário`);
- row 2: the units (`dd.MM.yyyy HH:mm`, `Wh`, `A`, `V`, `kWh/kWp`, ...);
- from row 3: one row per 5 minutes, local wall-clock time, energy in Wh per interval, `n/a` or an empty cell
  where the inverter logged nothing (always at night: it sleeps);
- consecutive yearly files overlap at the boundary: the same timestamp appears in both.

Column names are recognised in Portuguese, English and German through a small alias table (`ALIASES`). It
is a best effort, written from the Portuguese exports the project has; anything not recognised keeps a
snake_case version of its own name, and `energy_column=` picks the energy column explicitly.

THE LABEL CONVENTION IS NOT CONFIRMED. Whether a Fronius timestamp marks the START or the END of its 5-minute
interval is not documented in the export, and the project never settled it: the benchmark read it as the
start (it summed 10:00 ... 10:55 into the hour 10:00), which is `label="start"`, the default. The overlap at
the year boundary fits either reading. On real data, check it: `prosumer.quality.clock_offset` (against the
sun, needs the site) and `prosumer.quality.clock_offset_weather` (against measured or forecast irradiance, to
a fraction of an hour) estimate the offset of the result; an offset of about +5 minutes with
`label="start"` says the stamps mark the end, and `label="end"` fixes it.

The result is in kWh, `ds` = start of each step in `tz`. A step is valid when at least `min_coverage` of its
5-minute records exist (11 of 12 per hour by default, the benchmark's rule); otherwise it is NaN and invalid.
At night the inverter logs nothing, so night hours come out invalid; pass `site=(lat, lon)` to turn the steps
without sun into valid zeros (the benchmark did the same).
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from ..contracts import DstPolicy, EnergySeries
from ..provenance import UNKNOWN, Provenance
from . import _tables
from ._tables import Label

SOURCE = "Fronius Solar.web export"

_Q_CURRENT = r"(?:corrente|current|strom)"
_Q_VOLTAGE = r"(?:voltagem|tensao|voltage|spannung)"
_SIDE = r"(?P<side>ca|ac|cc|dc)"
_TAG = r"(?P<tag>l ?\d+|mpp ?\d+)"

# (regex on the normalised name: lower case, no accents, '-', '_' and '/' as spaces) -> canonical name;
# `{side}` and `{tag}` are filled from the match (e.g. "dc_current_mpp1").
ALIASES: list[tuple[str, str]] = [
    (
        r"data e horario|data e hora|data hora|date and time|date time|datum und uhrzeit|datum|zeit"
        r"|timestamp",
        "time",
    ),
    (r"energia|energy|energie|energia produzida|produced energy", "energy"),
    (r"(?:energia|energy|energie) mpp ?(?P<n>\d+)", "energy_mpp{n}"),
    (
        r"producao fotovoltaica|producao pv|pv production|photovoltaic production|pv produktion"
        r"|photovoltaik produktion|pv erzeugung",
        "pv_production",
    ),
    (r"rendimento especifico|specific yield|spezifischer ertrag", "specific_yield"),
    (rf"{_Q_CURRENT} {_SIDE} {_TAG}", "{side}_current_{tag}"),
    (rf"{_SIDE} {_Q_CURRENT} {_TAG}", "{side}_current_{tag}"),
    (rf"{_Q_VOLTAGE} {_SIDE} {_TAG}", "{side}_voltage_{tag}"),
    (rf"{_SIDE} {_Q_VOLTAGE} {_TAG}", "{side}_voltage_{tag}"),
    (r"fator de potencia|power factor|leistungsfaktor|cos phi", "power_factor"),
    (r"potencia aparente|apparent power|scheinleistung", "apparent_power"),
    (r"potencia reativa|reactive power|blindleistung", "reactive_power"),
    (r"potencia|potencia ativa|power|active power|leistung|wirkleistung", "power"),
]
_ALIASES = [(re.compile(rf"^(?:{p})$"), name) for p, name in ALIASES]
_SIDES = {"ca": "ac", "ac": "ac", "cc": "dc", "dc": "dc"}
# energy units the reader converts to kWh
ENERGY_UNITS = {"wh": 1e-3, "kwh": 1.0, "mwh": 1e3}
ENERGY_NAMES = ("energy", "pv_production")  # tried in this order when energy_column is not given


def normalise(text: str) -> str:
    """Lower case, accents removed, `-`, `_`, `/`, `.` and repeated spaces turned into one space."""
    t = unicodedata.normalize("NFKD", str(text))
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return re.sub(r"[\s\-_/.]+", " ", t).strip()


def canonical(name: str) -> str:
    """The English snake_case name of a Solar.web column (`Corrente CC MPP1` -> `dc_current_mpp1`); a name
    outside `ALIASES` is returned as its own snake_case."""
    n = normalise(name)
    for rx, out in _ALIASES:
        m = rx.match(n)
        if m:
            g = {k: v for k, v in m.groupdict().items() if v is not None}
            if "side" in g:
                g["side"] = _SIDES[g["side"]]
            if "tag" in g:
                g["tag"] = g["tag"].replace(" ", "")
            return out.format(**g)
    return re.sub(r"[^0-9a-z]+", "_", n).strip("_") or "column"


def _unit_suffix(unit: str) -> str:
    u = str(unit).strip()
    if u in ("", "1", "-", "nan", "None"):
        return ""
    return re.sub(r"[^0-9A-Za-z]+", "_", u.replace("%", "pct")).strip("_")


def _split_header(text: object) -> tuple[str, str]:
    """`Energia | Primo 4.0-1 (1)` -> (`Energia`, `Primo 4.0-1 (1)`); no `|` -> device ""."""
    s = "" if text is None or (isinstance(text, float) and np.isnan(text)) else str(text)
    base, _, device = s.partition("|")
    return base.strip(), device.strip()


def _paths(paths: str | Path | Iterable[str | Path]) -> list[Path]:
    if isinstance(paths, (str, Path)):
        return [Path(paths)]
    out = [Path(p) for p in paths]
    if not out:
        raise ValueError("No file given")
    return out


def _tables_of(path: Path, *, sep: str | None, encoding: str | None) -> list[tuple[str, pd.DataFrame]]:
    """(sheet name, cells without header) of each sheet; a CSV is one table named ""."""
    if _tables.is_excel(path):
        _tables.require_openpyxl("Fronius Solar.web exports")
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object, engine="openpyxl")
        return [(str(k), v) for k, v in sheets.items()]
    frame, _ = _tables.read_csv_text(path, sep=sep, encoding=encoding, header=None)
    return [("", frame)]


def read_solarweb_raw(
    paths: str | Path | Iterable[str | Path],
    *,
    sep: str | None = None,
    decimal: str | None = None,
    encoding: str | None = None,
) -> pd.DataFrame:
    """Every column of Solar.web exports, one row per device and timestamp, for diagnostics.

    Columns: `time` (naive, the wall-clock time as written), `device` (the header suffix, e.g.
    `Primo 4.0-1 (1)`; "" for columns without one), one column per quantity named `<canonical>_<unit>`
    (`energy_Wh`, `dc_current_mpp1_A`, `dc_voltage_mpp1_V`, `specific_yield_kWh_kWp`, `power_factor`, ...),
    `file`, `sheet`, `row` (1-based, as in the spreadsheet) and `duplicate` (True for a device and time
    already seen in an earlier row, in the order the files are given: the overlap between yearly files).
    Missing values (`n/a`, empty) are NaN. Nothing else is cleaned.

    `frame.attrs` holds `columns` (a table: column, canonical name, original header, unit) and
    `unparsed_rows` (rows with values but a time that did not parse; they are left out). CSV files: the
    separator and the decimal mark are guessed unless given.
    """
    rows: list[pd.DataFrame] = []
    columns: dict[str, dict[str, str]] = {}
    unparsed = 0
    for path in _paths(paths):
        for sheet, cells in _tables_of(path, sep=sep, encoding=encoding):
            if len(cells) < 3:
                continue
            header = [_split_header(v) for v in cells.iloc[0]]
            units = [
                "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip()
                for v in cells.iloc[1]
            ]
            names = [canonical(b) if b else "" for b, _ in header]
            if "time" not in names:
                raise ValueError(
                    f"{path.name} {sheet}: no date/time column in the first row ({[b for b, _ in header]}); "
                    "is this a Solar.web export with its two header rows?"
                )
            it = names.index("time")
            body = cells.iloc[2:].reset_index(drop=True)
            body = body[
                ~body.map(lambda v: str(v).strip().lower() in _tables.NA_TOKENS or v is None).all(axis=1)
            ]
            times = _tables.parse_times(body.iloc[:, it], dayfirst=True)
            bad = times.isna()
            unparsed += int(bad.sum())
            body, times = body[~bad], times[~bad]
            numeric = [j for j in range(cells.shape[1]) if j != it and header[j][0]]
            dec = decimal or _tables.guess_decimal(body.iloc[:, j] for j in numeric)
            for device in dict.fromkeys(header[j][1] for j in numeric):
                part = {"time": times.to_numpy(), "device": device}
                for j in (j for j in numeric if header[j][1] == device):
                    suffix = _unit_suffix(units[j])
                    key = f"{names[j]}_{suffix}" if suffix else names[j]
                    columns.setdefault(key, {"name": names[j], "header": header[j][0], "unit": units[j]})
                    values = _tables.to_number(body.iloc[:, j], dec).to_numpy()
                    part[key] = (
                        values if key not in part else np.where(np.isnan(part[key]), values, part[key])
                    )
                frame = pd.DataFrame(part)
                frame["file"], frame["sheet"] = path.name, sheet
                frame["row"] = body.index.to_numpy() + 3
                rows.append(frame)
    if not rows:
        raise ValueError("No data rows found in the files given")
    out = pd.concat(rows, ignore_index=True)
    lead = ["time", "device"]
    tail = ["file", "sheet", "row"]
    out = out[lead + [c for c in out.columns if c not in lead + tail] + tail]
    out["time"] = pd.to_datetime(out["time"])
    out["duplicate"] = out.duplicated(["device", "time"], keep="first")
    out.attrs["columns"] = pd.DataFrame(
        [{"column": k, **v} for k, v in columns.items()], columns=["column", "name", "header", "unit"]
    )
    out.attrs["unparsed_rows"] = unparsed
    return out


def _energy_columns(table: pd.DataFrame, energy_column: str | None) -> list[str]:
    """The raw columns holding the energy, matched by column, canonical name or original header."""
    if energy_column is not None:
        want = normalise(energy_column)
        hit = table[
            (table["column"] == energy_column)
            | (table["name"] == energy_column)
            | (table["header"].map(normalise) == want)
        ]
        if hit.empty:
            raise ValueError(
                f"energy_column={energy_column!r} not found; columns: {table['column'].tolist()}"
            )
        return hit["column"].tolist()
    for name in ENERGY_NAMES:
        hit = table[(table["name"] == name) & table["unit"].str.lower().isin(ENERGY_UNITS)]
        if not hit.empty:
            return hit["column"].tolist()
    raise ValueError(
        f"No energy column recognised (looked for {ENERGY_NAMES} in Wh/kWh); pass energy_column=, "
        f"one of {table['header'].tolist()}"
    )


def read_solarweb(
    paths: str | Path | Iterable[str | Path],
    *,
    tz: str,
    freq: str = "h",
    energy_column: str | None = None,
    names: Mapping[str, str] | Sequence[str] | None = None,
    label: Label = "start",
    min_coverage: float = 11 / 12,
    site: tuple[float, float] | None = None,
    step: str | None = None,
    dst: DstPolicy = "raise",
    sep: str | None = None,
    decimal: str | None = None,
    encoding: str | None = None,
) -> EnergySeries:
    """Generation series (kWh per `freq` step) from Solar.web exports of ONE site, one series per device.

    - `paths`: one file or several (the yearly exports, in any order); timestamps repeated across files are
      kept once (the first, in the order given) and counted in the provenance notes, with how many of them
      disagree on the energy;
    - `tz`: the time zone of the wall-clock times in the file (the one set in the Solar.web account);
    - `freq`: the output step; the 5-minute energies are SUMMED, and a step is valid with at least
      `min_coverage` of its records (11 of 12 per hour by default);
    - `energy_column`: the column to read, by its original name (`Energia`), canonical name (`energy`) or raw
      column (`energy_Wh`); by default the first of `energy`, `pv_production` in Wh or kWh;
    - `names`: the `unique_id` of each device, as a mapping from the device label (`Primo 4.0-1 (1)`) or a
      list in order of appearance; by default the device label;
    - `label`: "start" (default, the benchmark's reading) or "end": whether a timestamp marks the start or the
      end of its 5-minute interval. NOT confirmed for Fronius: see the module docstring and check with
      `prosumer.quality.clock_offset` / `clock_offset_weather`;
    - `site`: (lat, lon); steps without sun become valid zeros instead of invalid (the inverter does not log
      at night);
    - `step`: the native step, inferred from the data (5 minutes) by default; `dst` as in
      `EnergySeries.from_dataframe`.
    """
    raw = read_solarweb_raw(paths, sep=sep, decimal=decimal, encoding=encoding)
    table = raw.attrs["columns"]
    keys = _energy_columns(table, energy_column)
    energy = pd.Series(np.nan, index=raw.index)
    for key in keys:
        unit = str(table.loc[table["column"] == key, "unit"].iloc[0]).lower()
        if unit not in ENERGY_UNITS:
            raise ValueError(f"Column {key!r} has unit {unit!r}, not an energy (Wh, kWh, MWh)")
        energy = energy.fillna(raw[key] * ENERGY_UNITS[unit])
    x = pd.DataFrame({"unique_id": raw["device"], "time": raw["time"], "y": energy, "dup": raw["duplicate"]})
    kept = x[~x["dup"]]
    devices = [
        d for d in dict.fromkeys(kept["unique_id"]) if kept.loc[kept["unique_id"] == d, "y"].notna().any()
    ]
    if not devices:
        raise ValueError("The energy column has no value in any row")
    dropped = sorted(set(kept["unique_id"]) - set(devices))
    if dropped:
        warnings.warn(f"Devices without any energy value left out: {dropped}", UserWarning, stacklevel=2)
    n_dup = int(x["dup"].sum())
    first = kept.set_index(["unique_id", "time"])["y"]
    later = x[x["dup"]].set_index(["unique_id", "time"])["y"]
    a, b = first.reindex(later.index).to_numpy(), later.to_numpy()
    conflicts = int((~(np.isclose(a, b) | (np.isnan(a) & np.isnan(b)))).sum())
    kept = kept[kept["unique_id"].isin(devices)].sort_values(["unique_id", "time"], kind="stable")
    kept = kept.assign(ds=_tables.localize(kept["time"], kept["unique_id"], tz, dst))
    kept = kept[kept["ds"].notna()]
    native = pd.Timedelta(step) if step else _tables.infer_step(kept)
    kept = kept.assign(ds=_tables.shift_label(kept["ds"], label, native))
    out = _tables.aggregate(
        kept[["unique_id", "ds", "y"]], native=native, freq=freq, min_coverage=min_coverage
    )
    night = 0
    if site is not None:
        out, night = _tables.zero_at_night(out, freq, site)
    rename = _tables.names_for(devices, names, "devices")
    out["unique_id"] = out["unique_id"].map(rename)
    files = list(dict.fromkeys(raw["file"]))
    notes = [
        "the owner's own data",
        f"timestamps read as the {label.upper()} of each {native} interval (convention not confirmed: check "
        "with prosumer.quality.clock_offset)",
        f"{n_dup} duplicate timestamp(s) dropped, first kept ({conflicts} with a different energy)",
        f"a step is valid with >= {min_coverage:.3g} of its records",
    ]
    if raw.attrs["unparsed_rows"]:
        notes.append(f"{raw.attrs['unparsed_rows']} row(s) with an unreadable time left out")
    if site is not None:
        notes.append(f"{night} step(s) without sun set to zero")
    prov = Provenance(
        source=f"{SOURCE}: {', '.join(files)} (devices: {', '.join(rename[d] for d in devices)})",
        license=UNKNOWN,
        notes="; ".join(notes),
    )
    return EnergySeries.from_dataframe(
        out, unit="kWh", quantity="generation", tz=tz, freq=freq, provenance=prov
    )


__all__ = [
    "ALIASES",
    "ENERGY_NAMES",
    "ENERGY_UNITS",
    "SOURCE",
    "canonical",
    "normalise",
    "read_solarweb",
    "read_solarweb_raw",
]
