"""Read an energy file without being told its format: `sniff` says what it is, `read_energy` reads it.

The person who uploads a file usually does not know its layout, and the layouts differ by brand: an inverter
portal's export (Fronius Solar.web: two header rows, units in brackets, current, voltage and energy columns
for each device), a smart meter's load profile (time and kWh), a logger's table of average power. Picking a
column by its position is wrong as soon as there are more than two: on a real Solar.web export the second
column is the AC current in amperes, and a forecast built on it came out 30 times too large without any
error (seen on 2026-10-16).

So the choice is made by what each column says it is, and an ambiguous file is an error that lists the
candidates, never a guess:

1. a known export format is read by its own reader (`FORMATS`: today Fronius Solar.web; another brand is one
   more `(detector, reader)` pair, the core never assumes a brand);
2. any other table: the time column is the first one whose cells parse as times; a units row right under the
   header is recognised (`[kWh]`, `(Wh)`, `kW`) and dropped; the energy column is the one with an energy unit
   (kWh, Wh, MWh: rows are energies) or, failing that, a power unit (kW, W: rows are average powers), in its
   header or in the units row; a column whose name says current, voltage, power factor, frequency,
   temperature, irradiance or kWh/kWp is never chosen. Several candidates: the one whose name says energy
   (production, consumption, energy, in English, Portuguese, Spanish or German) and carries no channel tag
   (MPP1, L2, string 3); still several: `ValueError` with the list. A table of exactly a time and one value
   column takes that column, with the unit given or, when nothing says it, kWh with a note.

Whatever was chosen goes in the provenance notes (`series.provenance.notes`) and is returned by `sniff`, so
an app can show it ("read `Energia` in Wh from a Fronius Solar.web export").
"""

from __future__ import annotations

import io as _io
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast

import pandas as pd

from ..contracts import DstPolicy, EnergySeries, Quantity, Unit
from . import _tables, fronius, meter
from ._tables import Label

_ENERGY_UNITS = {"kwh": "kWh", "wh": "Wh", "mwh": "MWh"}
_POWER_UNITS = {"kw": "kW", "w": "W"}
# a unit written in a header: "Energy (kWh)", "Energia [Wh]", "consumo_kwh", "kWh"
_UNIT_IN_NAME = re.compile(r"(?:^|[\s\[(_\-/])(mwh|kwh|wh|kw|w)(?:$|[\s\])_\-])", re.IGNORECASE)
_NOT_ENERGY = re.compile(
    r"corrente|current|strom|corriente|voltag|tensao|tension|voltage|spannung|fator|factor|faktor|reativ|"
    r"reactiv|blind|aparente|apparent|schein|frequen|temperat|irradi|radiac|radiation|kwp|"
    r"rendimento especifico|specific yield|spezifisch|cos phi|soc|state of charge",
)
_ENERGY_NAME = re.compile(
    r"energ|produc|produz|produção|producao|generat|gerac|geraç|yield|ertrag|erzeug|consum|verbrauch|"
    r"import|export|injec|injeç|load|carga|kwh|\bwh\b|pv|fotovolt|photovolt|solar",
)
_CHANNEL_TAG = re.compile(r"\bmpp ?\d|\bl ?[123]\b|\bstring ?\d|\bphase ?\d|\bfase ?\d|\bpv ?\d")
_SAMPLE_ROWS = 60


@dataclass(frozen=True)
class Sniffed:
    """What a file was taken to be. `format`: "solarweb" or "table"; `time_column`, `value_column`, `unit`,
    `kind` (meter.read_table's), `units_row` (a row of units under the header was dropped); `candidates`:
    the value columns considered, with the unit found and why each was kept or left out; `why`: one line."""

    format: str
    why: str
    time_column: str | None = None
    value_column: str | None = None
    unit: str | None = None
    kind: str | None = None
    units_row: bool = False
    candidates: list[dict[str, str]] = field(default_factory=list)


def _is_solarweb(head: pd.DataFrame) -> bool:
    if head.shape[0] < 3:
        return False
    top = [str(v) for v in head.iloc[0] if v is not None and str(v) != "nan"]
    names = [fronius.canonical(fronius._split_header(v)[0]) for v in top]
    devices = sum("|" in v for v in top)
    units = [str(v).strip() for v in head.iloc[1] if v is not None and str(v).strip() not in ("", "nan")]
    bracketed = sum(u.startswith("[") and u.endswith("]") for u in units)
    energy = any(n in fronius.ENERGY_NAMES for n in names)
    return "time" in names and energy and (devices > 0 or bracketed >= len(units) / 2)


# (detector on the first rows as text cells without a header, reader); first match wins
FORMATS: list[tuple[str, Callable[[pd.DataFrame], bool]]] = [("solarweb", _is_solarweb)]


def _head(path: Path, *, sep: str | None, encoding: str | None, sheet: str | int) -> pd.DataFrame:
    """The first rows as raw cells (no header), enough to recognise a format."""
    if _tables.is_excel(path):
        _tables.require_openpyxl("Excel files")
        return pd.read_excel(path, sheet_name=sheet, header=None, nrows=_SAMPLE_ROWS, dtype=object)
    text = _tables.read_text(path, encoding)
    lines = "\n".join(text.splitlines()[: _SAMPLE_ROWS + 1])
    return pd.read_csv(
        _io.StringIO(lines),
        sep=sep or _tables.sniff_separator(lines),
        header=None,
        dtype=str,
        keep_default_na=False,
        engine="python",
    )


def _unit_of(text: str) -> str | None:
    t = str(text).strip().strip("[]()").strip()
    low = t.lower()
    if low in _ENERGY_UNITS:
        return _ENERGY_UNITS[low]
    if low in _POWER_UNITS:
        return _POWER_UNITS[low]
    m = _UNIT_IN_NAME.search(str(text))
    if m and "/" not in str(text)[m.end(1) : m.end(1) + 1]:  # kWh/kWp is a yield, not an energy
        u = m.group(1).lower()
        return _ENERGY_UNITS.get(u) or _POWER_UNITS.get(u)
    return None


def _times_ok(values: pd.Series) -> float:
    """Share of the non-empty cells that read as times; plain numbers never do (a reading, not a date)."""
    v = values[values.astype(str).str.strip().ne("")].reset_index(drop=True)
    if v.empty:
        return 0.0
    numeric = _tables.to_number(v, ",").notna() | _tables.to_number(v, ".").notna()
    v = v[~numeric]
    if v.empty:
        return 0.0
    try:
        ok = _tables.parse_times(v.reset_index(drop=True)).notna().sum()
    except (ValueError, OverflowError, pd.errors.OutOfBoundsDatetime):
        return 0.0
    return float(ok / len(numeric))


def _sniff_table(frame: pd.DataFrame, *, time_column: str | None, value_column: str | None) -> Sniffed:
    cols = [str(c) for c in frame.columns]
    head = frame.head(_SAMPLE_ROWS)
    if time_column is None:
        scores = {c: _times_ok(head[c].iloc[1:]) for c in cols}
        time_column = next((c for c in cols if scores[c] >= 0.8), None)
        if time_column is None:
            raise ValueError(f"No column of dates and times found among {cols}; give the time column's name")
    first = head[time_column].iloc[0] if len(head) else None
    units_row = bool(
        len(head) > 1
        and _times_ok(pd.Series([first])) == 0.0
        and sum(_unit_of(head[c].iloc[0]) is not None for c in cols if c != time_column) >= 1
    )
    units = {c: (str(head[c].iloc[0]) if units_row else "") for c in cols}
    others = [c for c in cols if c != time_column]
    cands: list[dict[str, str]] = []
    for c in others:
        name = fronius.normalise(c)
        unit = _unit_of(units[c]) if units_row and _unit_of(units[c]) else _unit_of(c)
        if _NOT_ENERGY.search(name) or (units_row and "/" in units[c]):
            cands.append({"column": c, "unit": unit or "", "status": "left out: not an energy quantity"})
            continue
        if unit is None and not _ENERGY_NAME.search(name) and len(others) > 1:
            cands.append({"column": c, "unit": "", "status": "left out: neither a unit nor a name of energy"})
            continue
        cands.append({"column": c, "unit": unit or "", "status": "candidate"})
    if value_column is not None:
        if value_column not in cols:
            raise ValueError(f"Column {value_column!r} not in the file; it has {cols}")
        hit = next((d for d in cands if d["column"] == value_column), {"unit": ""})
        return Sniffed(
            "table",
            f"column {value_column!r} as given",
            time_column,
            value_column,
            hit["unit"] or None,
            None,
            units_row,
            cands,
        )
    pool = [d for d in cands if d["status"] == "candidate"]
    for rule, keep in (
        ("an energy unit", lambda d: d["unit"] in _ENERGY_UNITS.values()),
        ("a power unit", lambda d: d["unit"] in _POWER_UNITS.values()),
        ("a name of energy", lambda d: bool(_ENERGY_NAME.search(fronius.normalise(d["column"])))),
    ):
        hits = [d for d in pool if keep(d)]
        if len(hits) > 1:  # prefer the plain total over per-channel columns (MPP1, L2, string 3)
            plain = [d for d in hits if not _CHANNEL_TAG.search(fronius.normalise(d["column"]))]
            hits = plain or hits
        if len(hits) == 1:
            d = hits[0]
            return Sniffed(
                "table",
                f"column {d['column']!r}: the only one with {rule}",
                time_column,
                d["column"],
                d["unit"] or None,
                None,
                units_row,
                cands,
            )
        if len(hits) > 1:
            names = [d["column"] for d in hits]
            raise ValueError(
                f"Several columns could be the energy ({names}, all with {rule}); "
                "give the energy column's name"
            )
    if len(others) == 1 and pool:
        d = pool[0]
        return Sniffed(
            "table",
            f"column {d['column']!r}: the only value column",
            time_column,
            d["column"],
            d["unit"] or None,
            None,
            units_row,
            cands,
        )
    raise ValueError(
        f"No energy column recognised among {others} (looked for an energy or power unit, or a name such as "
        "energy, production, consumption); give the energy column's name"
    )


def sniff(
    source: str | Path,
    *,
    time_column: str | None = None,
    value_column: str | None = None,
    sep: str | None = None,
    encoding: str | None = None,
    sheet: str | int = 0,
) -> Sniffed:
    """What `source` is and which columns `read_energy` would read (see the module docstring)."""
    path = Path(source)
    head = _head(path, sep=sep, encoding=encoding, sheet=sheet)
    for name, detect in FORMATS:
        if time_column is None and value_column is None and detect(head):
            return Sniffed(
                name, "recognised as a Fronius Solar.web export (two header rows, units in brackets)"
            )
    frame = pd.DataFrame(head.iloc[1:].to_numpy(), columns=[str(c).strip() for c in head.iloc[0]])
    return _sniff_table(frame, time_column=time_column, value_column=value_column)


def read_energy(
    source: str | Path,
    *,
    tz: str,
    quantity: Quantity = "generation",
    time_column: str | None = None,
    value_column: str | None = None,
    unit: Unit | None = None,
    kind: meter.Kind | None = None,
    freq: str | None = "h",
    label: Label = "start",
    site: tuple[float, float] | None = None,
    source_tz: str | None = None,
    dst: DstPolicy = "raise",
    sep: str | None = None,
    decimal: str | None = None,
    encoding: str | None = None,
    sheet: str | int = 0,
) -> EnergySeries:
    """An `EnergySeries` (kWh) from a file of unknown layout: `sniff`, then the format's reader.

    Anything given (`time_column`, `value_column`, `unit`, `kind`) wins over the guess. `site` (generation,
    Solar.web): steps without sun become valid zeros. Several devices in one export come out as several
    series. Raises `ValueError` when the energy column is ambiguous or absent, with the columns found.
    """
    path = Path(source)
    found = sniff(
        path, time_column=time_column, value_column=value_column, sep=sep, encoding=encoding, sheet=sheet
    )
    try:
        return _read(
            path,
            found,
            tz=tz,
            quantity=quantity,
            unit=unit,
            kind=kind,
            freq=freq,
            label=label,
            site=site,
            source_tz=source_tz,
            dst=dst,
            sep=sep,
            decimal=decimal,
            encoding=encoding,
            sheet=sheet,
        )
    except ValueError as e:
        if "shorter than the data's step" in str(e):
            native = pd.Timedelta(str(e).split("step (")[-1].split(")")[0])
            every = "day" if native == pd.Timedelta(days=1) else f"{native}"
            raise ValueError(
                f"{path.name} has one value per {every}, coarser than the "
                f"{freq!r} steps asked for: export the detailed data (5- or 15-minute or hourly; in Fronius "
                "Solar.web, the 5-minute 'minuto' export) instead of the daily totals."
            ) from e
        raise


def _read(
    path: Path,
    found: Sniffed,
    *,
    tz: str,
    quantity: Quantity,
    unit: Unit | None,
    kind: meter.Kind | None,
    freq: str | None,
    label: Label,
    site: tuple[float, float] | None,
    source_tz: str | None,
    dst: DstPolicy,
    sep: str | None,
    decimal: str | None,
    encoding: str | None,
    sheet: str | int,
) -> EnergySeries:
    if found.format == "solarweb":
        if quantity != "generation":
            raise ValueError(
                "A Fronius Solar.web export holds the inverter's production: quantity='generation'"
            )
        s = fronius.read_solarweb(
            path,
            tz=tz,
            freq=freq or "h",
            label=label,
            site=site,
            dst=dst,
            sep=sep,
            decimal=decimal,
            encoding=encoding,
            source_tz=source_tz,
        )
        return _noted(s, f"format: {found.why}")
    sniffed, note = unit or found.unit, ""
    if sniffed is None:
        sniffed, note = "kWh", "; unit not stated in the file: kWh assumed"
    if sniffed not in ("kWh", "Wh", "kW", "W"):
        raise ValueError(
            f"Unit {sniffed!r} is not read yet (kWh, Wh, kW or W); convert the column or give unit="
        )
    u = cast(Unit, sniffed)
    k = kind or ("power" if u in _POWER_UNITS.values() else "interval")
    frame, _ = meter._load(path, sep=sep, encoding=encoding, sheet=sheet, skiprows=0)
    frame.columns = [str(c).strip() for c in frame.columns]
    if found.units_row:
        frame = frame.iloc[1:].reset_index(drop=True)
    assert found.time_column is not None and found.value_column is not None
    s = meter.read_table(
        frame,
        time_column=found.time_column,
        value_columns=found.value_column,
        tz=tz,
        unit=u,
        quantity=quantity,
        freq=freq,
        kind=k,
        label=label,
        decimal=decimal,
        dst=dst,
        source_tz=source_tz,
    )
    if site is not None and quantity == "generation":
        out, _n = _tables.zero_at_night(s.frame, s.freq, site)
        s = EnergySeries.from_dataframe(
            out, unit="kWh", quantity=quantity, tz=s.tz, freq=s.freq, provenance=s.provenance
        )
    dropped = "; a units row under the header was dropped" if found.units_row else ""
    return _noted(s, f"file {path.name}: {found.why}, unit {u}, kind {k}{dropped}{note}")


def _noted(s: EnergySeries, text: str) -> EnergySeries:
    p = s.provenance
    if p is None:
        return s
    new = replace(p, notes=f"{text}; {p.notes}" if p.notes else text)
    return EnergySeries.from_dataframe(
        s.frame, unit=s.unit, quantity=s.quantity, tz=s.tz, freq=s.freq, provenance=new
    )


__all__ = ["FORMATS", "Sniffed", "read_energy", "sniff"]
