"""Shared machinery of the file readers (`io.fronius`, `io.meter`): reading text tables whose separator and
decimal mark are not declared, parsing numbers and timestamps written in local conventions, putting wall-clock
times in a time zone, and aggregating short steps into longer ones with a coverage rule.

The coverage rule is the benchmark's (`experimentos/testes_previsao/scripts/01_prepara_dados.py`): an hour of
the plants was valid with at least 11 of its 12 five-minute records. A step with fewer is kept as a row with
`y` = NaN and `valid` = False, never as the partial sum: a gap is not a zero.
"""

from __future__ import annotations

import io
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from ..contracts import DstPolicy, _localize, step
from ..i18n import Note

Label = Literal["start", "end"]
LABEL_NAME = {"start": Note("START"), "end": Note("END")}  # as the readers' notes name the label

NA_TOKENS = frozenset({"", "n/a", "na", "nan", "-", "--", "null", "none", "#n/a", "n.a."})
_SEPARATORS = ("\t", ";", "|", ",")  # order of preference when several are consistent
_COMMA_DECIMAL = re.compile(r"^[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+),\d+$")
_POINT_DECIMAL = re.compile(r"^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d+$")
_OFFSET = re.compile(r"(?:Z|[+-]\d\d:?\d\d)$")
DOTTED_FORMATS = ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S")  # Fronius Solar.web, many European meters


# ---------------------------------------------------------------------- text files
def read_text(path: Path, encoding: str | None = None) -> str:
    """The file as text: `encoding` if given, else UTF-8 (with or without BOM), else Windows-1252 (the
    usual encoding of Brazilian and European exports)."""
    raw = path.read_bytes()
    if encoding:
        return raw.decode(encoding)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def sniff_separator(text: str, skiprows: int = 0) -> str:
    """The column separator: the first of tab, `;`, `|`, `,` that appears the same (non-zero) number of times
    in every one of the first lines; failing that, the most frequent one. `;` comes before `,` because a file
    separated by `;` usually writes numbers with a decimal comma, which makes the comma count vary."""
    lines = [ln for ln in text.splitlines()[skiprows:] if ln.strip()][:30]
    if not lines:
        return ","
    for sep in _SEPARATORS:
        counts = {ln.count(sep) for ln in lines}
        if len(counts) == 1 and counts.pop() > 0:
            return sep
    return max(_SEPARATORS, key=lambda s: sum(ln.count(s) for ln in lines))


def read_csv_text(
    path: Path, *, sep: str | None, encoding: str | None, skiprows: int = 0, header: int | None = 0
) -> tuple[pd.DataFrame, str]:
    """A CSV read as text cells (nothing converted yet) and the separator used."""
    text = read_text(path, encoding)
    sep = sep or sniff_separator(text, skiprows)
    frame = pd.read_csv(
        io.StringIO(text),
        sep=sep,
        dtype=str,
        keep_default_na=False,
        header=header,
        skiprows=skiprows,
        skip_blank_lines=True,
        engine="python",
    )
    return frame, sep


def require_openpyxl(what: str) -> None:
    try:
        import openpyxl  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise ImportError(
            f"Reading {what} from Excel needs openpyxl: pip install 'prosumer[fronius]' (or openpyxl). "
            "Exporting the file as CSV also works."
        ) from e


def is_excel(path: Path) -> bool:
    return path.suffix.lower() in (".xlsx", ".xlsm", ".xltx", ".xltm")


# ---------------------------------------------------------------------- numbers
def guess_decimal(columns: Iterable[pd.Series]) -> str:
    """ "," when some text cell looks like a number with a decimal comma (`12,5`, `1.234,5`) and none like one
    with a decimal point; "." otherwise."""
    comma = point = False
    for col in columns:
        if pd.api.types.is_numeric_dtype(col):
            continue
        txt = col.dropna().astype(str).str.strip()
        comma = comma or bool(txt.str.match(_COMMA_DECIMAL).any())
        point = point or bool(txt.str.match(_POINT_DECIMAL).any())
    return "," if comma and not point else "."


def to_number(values: pd.Series, decimal: str = ".") -> pd.Series:
    """Floats from cells that may be numbers, text numbers in `decimal` convention (thousands marks removed),
    or a missing-value token (`n/a`, empty, `-`, ...): those become NaN. Anything else that does not parse
    also becomes NaN."""
    if pd.api.types.is_numeric_dtype(values) and not pd.api.types.is_bool_dtype(values):
        return values.astype(float)
    txt = values.map(lambda v: "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v))
    txt = txt.str.strip().str.replace(" ", "", regex=False).str.replace(" ", "", regex=False)
    na = txt.str.lower().isin(NA_TOKENS)
    if decimal == ",":
        txt = txt.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        txt = txt.str.replace(",", "", regex=False)
    out = pd.to_numeric(txt.where(~na), errors="coerce")
    return out.astype(float)


# ---------------------------------------------------------------------- times
def parse_times(values: pd.Series, *, dayfirst: bool | None = None, formats: Sequence[str] = ()) -> pd.Series:
    """Datetimes from cells that may already be datetimes (Excel) or text.

    Text is tried, in order, against `formats`, the dotted day-first formats (`dd.MM.yyyy HH:mm[:ss]`, unless
    `dayfirst` is False) and ISO 8601; what is left is parsed with `dayfirst`. With `dayfirst=None` both
    readings are tried and the one that parses more cells, then leaves fewer steps backwards in file order,
    wins (a meter logs forwards; `01/02 ... 13/02` only parses day-first). Text with a UTC offset (`Z`,
    `-03:00`) gives aware times. Cells that do not parse become NaT.
    """
    if pd.api.types.is_datetime64_any_dtype(values):
        return values
    is_dt = values.map(lambda v: isinstance(v, (pd.Timestamp, np.datetime64)) or hasattr(v, "isoformat"))
    txt = values.where(~is_dt).map(
        lambda v: "" if v is None or (isinstance(v, float) and math.isnan(v)) else v
    )
    txt = txt.astype(str).str.strip()
    blank = is_dt | txt.str.lower().isin(NA_TOKENS)
    if (~blank & txt.str.contains(_OFFSET)).any():
        out = pd.to_datetime(txt.where(~blank), utc=True, format="ISO8601", errors="coerce")
        mixed = pd.to_datetime(txt.where(~blank & out.isna()), utc=True, format="mixed", errors="coerce")
        return out.fillna(mixed)
    out = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    if is_dt.any():
        out[is_dt] = pd.to_datetime(values[is_dt].astype(object)).astype("datetime64[ns]")
    tried = [*formats, *(DOTTED_FORMATS if dayfirst is not False else ()), "ISO8601"]
    for fmt in tried:
        todo = ~blank & out.isna()
        if not todo.any():
            break
        out[todo] = pd.to_datetime(txt[todo], format=fmt, errors="coerce")
    todo = ~blank & out.isna()
    if todo.any():
        options = [dayfirst] if dayfirst is not None else [True, False]
        best: pd.Series | None = None
        best_key: tuple[int, int] | None = None
        for df in options:
            p = pd.to_datetime(txt[todo], dayfirst=df, format="mixed", errors="coerce")
            trial = out.copy()
            trial[todo] = p
            ok = trial.dropna()
            key = (int(trial[~blank].isna().sum()), int((ok.diff().dt.total_seconds() < 0).sum()))
            if best_key is None or key < best_key:
                best, best_key = trial, key
        assert best is not None
        out = best
    return out


def localize(
    times: pd.Series, ids: pd.Series, tz: str, dst: DstPolicy, source_tz: str | None = None
) -> pd.Series:
    """Aware times in `tz`: aware ones are converted, naive ones are read as wall-clock time in `source_tz`
    (default `tz`; e.g. "UTC" for a logger that writes UTC) and converted to `tz` (daylight saving resolved as
    in `EnergySeries.from_dataframe`)."""
    if isinstance(times.dtype, pd.DatetimeTZDtype):
        return times.dt.tz_convert(tz)
    return _localize(times, tz, source_tz or tz, ids, dst)


def infer_step(frame: pd.DataFrame) -> pd.Timedelta:
    """The most common positive spacing between consecutive timestamps of each series (`unique_id`, `ds`)."""
    diffs = frame.sort_values(["unique_id", "ds"]).groupby("unique_id")["ds"].diff().dropna()
    diffs = diffs[diffs > pd.Timedelta(0)]
    if diffs.empty:
        raise ValueError(Note("Cannot infer the time step (fewer than two distinct timestamps); pass step="))
    return pd.Timedelta(diffs.mode().iloc[0])


def names_for(
    ids: Sequence[str], names: Mapping[str, str] | Sequence[str] | None, what: str
) -> dict[str, str]:
    """Map each id to its output name: unchanged, by a mapping (unknown keys raise), or by position."""
    if names is None:
        return {i: i for i in ids}
    if isinstance(names, Mapping):
        unknown = set(names) - set(ids)
        if unknown:
            raise ValueError(f"names= has {sorted(unknown)}, not among the {what}: {list(ids)}")
        return {i: str(names.get(i, i)) for i in ids}
    if isinstance(names, str) or len(names) != len(ids):
        raise ValueError(f"names= must have one name per {what[:-1]} ({len(ids)}: {list(ids)})")
    return {i: str(n) for i, n in zip(ids, names, strict=True)}


# ---------------------------------------------------------------------- aggregation
def aggregate(frame: pd.DataFrame, *, native: pd.Timedelta, freq: str, min_coverage: float) -> pd.DataFrame:
    """Sum the steps of `frame` (`unique_id`, `ds` aware = start of each native step, `y`) into steps of
    `freq`, on a complete grid from the first to the last step of each series.

    A step is valid when the native steps with a value cover at least `min_coverage` of it (the number of
    native steps it should hold is counted on the clock, so a 23-hour or 25-hour day of a daylight saving
    change is handled); otherwise `y` is NaN and `valid` False.
    """
    if not 0 < min_coverage <= 1:
        raise ValueError("min_coverage must be in (0, 1]")
    target = step(freq)
    if target < native:
        raise ValueError(
            Note(
                "freq={freq!r} is shorter than the data's step ({native}): cannot split energy",
                freq=freq,
                native=native,
            )
        )
    pad = math.ceil((target + pd.Timedelta(hours=1)) / native)
    parts = []
    for uid, g in frame.groupby("unique_id", sort=False):
        s = g.set_index("ds")["y"].sort_index()
        grid = pd.date_range(s.index[0] - pad * native, s.index[-1] + pad * native, freq=native)
        expected = pd.Series(1.0, index=grid).resample(freq).count()
        r = s.resample(freq)
        total = r.sum(min_count=1)
        cov = r.count() / expected.reindex(total.index)
        ok = (cov >= min_coverage - 1e-9) & total.notna()
        parts.append(
            pd.DataFrame(
                {"unique_id": uid, "ds": total.index, "y": total.where(ok).to_numpy(), "valid": ok.to_numpy()}
            )
        )
    return pd.concat(parts, ignore_index=True)


def zero_at_night(out: pd.DataFrame, freq: str, site: tuple[float, float]) -> tuple[pd.DataFrame, int]:
    """Steps without sun at `site` (clear-sky GHI zero over the whole step) that came out invalid become 0 and
    valid: an inverter sleeps at night and logs nothing, but it generated nothing. The benchmark did the same
    with its clear-sky plane-of-array irradiance. Returns the frame and how many steps were filled."""
    from ..physics import clear_sky_ghi

    times = pd.DatetimeIndex(out["ds"])
    span = step(freq)
    cs = clear_sky_ghi(times, site[0], site[1], interval=f"{int(span.total_seconds())}s", samples=12)
    fill = (cs <= 0) & ~out["valid"].to_numpy()
    out = out.copy()
    out.loc[fill, "y"] = 0.0
    out.loc[fill, "valid"] = True
    return out, int(fill.sum())


def shift_label(ds: pd.Series, label: Label, native: pd.Timedelta) -> pd.Series:
    """Timestamps that mark the END of their interval moved to its start (the library's convention)."""
    if label == "start":
        return ds
    if label == "end":
        return ds - native
    raise ValueError("label must be 'start' or 'end'")
