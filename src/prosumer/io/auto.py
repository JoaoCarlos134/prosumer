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
3. an energy column is read as a COUNTER when its values say so, never its name (a "total" column can be
   either). Within days (resets aside) a counter's falls add up to at most half its rises, in sum and in count
   (dips at the resolution are small; energy per interval rises and falls by the same amount every day), and
   it rises by at least two of its own steps a day (median; a load that steps up twice in a week does not).
   If it also falls back at the change of day it is a daily counter, restarting at midnight (an inverter's
   "energy today": Growatt's `E-Today`), otherwise a register; each step is then the difference of two
   readings (`meter.read_table(kind="cumulative")`). A file of a single day whose values do not sit far above
   their own range (one morning of PV rises like a daily counter) is AMBIGUOUS: an error asks for `kind=`.
   The thresholds (half, two steps, the single-day rule) were set by hand on a real Growatt export and on the
   cases of the review of 2026-10-17 (coarse 1 kWh registers, hourly registers, 19 readings, a wobbling
   daily counter, a load stepping up, a morning of PV). Found on that Growatt export: read as the energy of
   each row, its `E-Today (kWh)` gave ~1,000 kWh a day from a 3 kW system.

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

import numpy as np
import pandas as pd

from ..contracts import DstPolicy, EnergySeries, Quantity, Unit
from ..i18n import Note
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
            raise ValueError(
                Note(
                    "No column of dates and times found among {cols}; give the time column's name", cols=cols
                )
            )
    elif time_column not in cols:
        raise ValueError(
            Note("Column {column!r} not in the file; it has {cols}", column=time_column, cols=cols)
        )
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
            raise ValueError(
                Note("Column {column!r} not in the file; it has {cols}", column=value_column, cols=cols)
            )
        hit = next((d for d in cands if d["column"] == value_column), {"unit": ""})
        return Sniffed(
            "table",
            Note("column {column!r} as given", column=value_column),
            time_column,
            value_column,
            hit["unit"] or None,
            None,
            units_row,
            cands,
        )
    pool = [d for d in cands if d["status"] == "candidate"]
    for rule, keep in (
        (Note("an energy unit"), lambda d: d["unit"] in _ENERGY_UNITS.values()),
        (Note("a power unit"), lambda d: d["unit"] in _POWER_UNITS.values()),
        (Note("a name of energy"), lambda d: bool(_ENERGY_NAME.search(fronius.normalise(d["column"])))),
    ):
        hits = [d for d in pool if keep(d)]
        if len(hits) > 1:  # prefer the plain total over per-channel columns (MPP1, L2, string 3)
            plain = [d for d in hits if not _CHANNEL_TAG.search(fronius.normalise(d["column"]))]
            hits = plain or hits
        if len(hits) == 1:
            d = hits[0]
            return Sniffed(
                "table",
                Note("column {column!r}: the only one with {rule}", column=d["column"], rule=rule),
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
                Note(
                    "Several columns could be the energy ({names}, all with {rule}); give the energy "
                    "column's name",
                    names=names,
                    rule=rule,
                )
            )
    if len(others) == 1 and pool:
        d = pool[0]
        return Sniffed(
            "table",
            Note("column {column!r}: the only value column", column=d["column"]),
            time_column,
            d["column"],
            d["unit"] or None,
            None,
            units_row,
            cands,
        )
    raise ValueError(
        Note(
            "No energy column recognised among {others} (looked for an energy or power unit, or a name such "
            "as energy, production, consumption); give the energy column's name",
            others=others,
        )
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
                name, Note("recognised as a Fronius Solar.web export (two header rows, units in brackets)")
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
    resets: meter.Resets | None = None,
) -> EnergySeries:
    """An `EnergySeries` (kWh) from a file of unknown layout: `sniff`, then the format's reader.

    Anything given (`time_column`, `value_column`, `unit`, `kind`, and for a counter `resets`) wins over the
    guess. `site` (generation,
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
            resets=resets,
        )
    except ValueError as e:
        if "shorter than the data's step" in str(e):
            native = pd.Timedelta(str(e).split("step (")[-1].split(")")[0])
            every = Note("day") if native == pd.Timedelta(days=1) else native
            raise ValueError(
                Note(
                    "{file} has one value per {every}, coarser than the {freq!r} steps asked for: export the "
                    "detailed data (5- or 15-minute or hourly; in Fronius Solar.web, the 5-minute 'minuto' "
                    "export) instead of the daily totals.",
                    file=path.name,
                    every=every,
                    freq=freq,
                )
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
    resets: meter.Resets | None = None,
) -> EnergySeries:
    if found.format == "solarweb":
        if quantity != "generation":
            raise ValueError(
                Note("A Fronius Solar.web export holds the inverter's production: quantity='generation'")
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
        return _noted(s, Note("format: {why}", why=found.why))
    sniffed, assumed = unit or found.unit, False
    if sniffed is None:
        sniffed, assumed = "kWh", True
    if sniffed not in ("kWh", "Wh", "kW", "W"):
        raise ValueError(
            Note(
                "Unit {unit!r} is not read yet (kWh, Wh, kW or W); convert the column or give unit=",
                unit=sniffed,
            )
        )
    u = cast(Unit, sniffed)
    frame, _ = meter._load(path, sep=sep, encoding=encoding, sheet=sheet, skiprows=0)
    frame.columns = [str(c).strip() for c in frame.columns]
    if found.units_row:
        frame = frame.iloc[1:].reset_index(drop=True)
    assert found.time_column is not None and found.value_column is not None
    k, extra = kind, []
    if u in _ENERGY_UNITS.values() and kind in (None, "cumulative"):
        counter = _counter_kind(frame[found.time_column], frame[found.value_column], decimal)
        if kind is None and counter is not None:
            k = "cumulative"
            extra.append(
                Note("its values only grow within each day and restart at midnight: read as a daily counter")
                if counter == "daily"
                else Note("its values only grow: read as a register (counter)")
            )
        if resets is None:
            resets = "restart" if counter == "daily" else "invalid"
    k = k or ("power" if u in _POWER_UNITS.values() else "interval")
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
        resets=resets or "invalid",
    )
    if site is not None and quantity == "generation":
        out, _n = _tables.zero_at_night(s.frame, s.freq, site)
        s = EnergySeries.from_dataframe(
            out, unit="kWh", quantity=quantity, tz=s.tz, freq=s.freq, provenance=s.provenance
        )
    if found.units_row:
        extra.append(Note("a units row under the header was dropped"))
    if assumed:
        extra.append(Note("unit not stated in the file: kWh assumed"))
    how = Note("file {file}: {why}, unit {unit}, kind {kind}", file=path.name, why=found.why, unit=u, kind=k)
    return _noted(s, Note.join([how, *extra]) if extra else how)


COUNTER_MIN_READINGS = 6
COUNTER_FALL_SHARE = 0.5  # within days, falls <= half the rises (sum and count): set by hand (rule 3)
COUNTER_STEPS_PER_DAY = 2  # a counter rises by at least two of its own steps a day (median): set by hand


def _counter_kind(times: pd.Series, values: pd.Series, decimal: str | None) -> str | None:
    """'daily' (a counter that restarts every day), 'register' (one that only grows) or None (the rows are the
    energy of each interval), from the values alone (module docstring, rule 3). Raises `ValueError` when a
    single day cannot tell a counter from energy per interval."""
    t = _tables.parse_times(times)
    v = _tables.to_number(values, decimal or _tables.guess_decimal([values]))
    ok = (t.notna() & v.notna()).to_numpy()
    if ok.sum() < COUNTER_MIN_READINGS:
        return None
    r = pd.DataFrame({"t": pd.DatetimeIndex(t[ok]), "v": v[ok].to_numpy(dtype=float)}).sort_values("t")
    when = pd.DatetimeIndex(r["t"])
    x = r["v"].to_numpy(dtype=float)
    d = np.diff(x)
    days = when.normalize()
    same = np.asarray(days[1:] == days[:-1])
    up = d[d > 0]
    if len(up) == 0:  # constant (or all zero): no growth to count
        return None
    typical = float(np.median(up))
    reset = (d < -10 * typical) | ((d < 0) & (x[1:] <= 0.5 * x[:-1]) & (x[:-1] >= 5 * typical))
    inside = d[same & ~reset]
    rise, fall = float(inside[inside > 0].sum()), float(-inside[inside < 0].sum())
    n_rise, n_fall = int((inside > 0).sum()), int((inside < 0).sum())
    if n_rise == 0 or fall > COUNTER_FALL_SHARE * rise or n_fall > COUNTER_FALL_SHARE * n_rise:
        return None
    growth = pd.Series(x).groupby(np.asarray(days)).agg(lambda g: g.max() - g.min())
    if float(growth.median()) < COUNTER_STEPS_PER_DAY * typical:
        return None
    per_day = pd.Series(1, index=np.asarray(days)).groupby(level=0).size()
    if (per_day >= 2).sum() < 2 and not np.min(x) > np.max(x) - np.min(x):
        raise ValueError(
            Note(
                "The energy column only rises in this file: a counter (each step = the difference of two "
                "readings) or the energy of each interval (one rising morning of PV) look alike in a single "
                "day. Give kind='cumulative' or kind='interval'."
            )
        )
    changes = ~same
    if changes.any() and np.mean(d[changes] < 0) >= 0.8:
        return "daily"
    return "register"


def _noted(s: EnergySeries, text: str) -> EnergySeries:
    """`text` first in the provenance notes, each part kept apart (`Note.join`: the app shows the first)."""
    p = s.provenance
    if p is None:
        return s
    new = replace(p, notes=Note.join([*_parts(text), *_parts(p.notes)]) if p.notes else text)
    return EnergySeries.from_dataframe(
        s.frame, unit=s.unit, quantity=s.quantity, tz=s.tz, freq=s.freq, provenance=new
    )


def _parts(text: str) -> list[str]:
    return text.parts if isinstance(text, Note) else [text]


__all__ = ["FORMATS", "Sniffed", "read_energy", "sniff"]
