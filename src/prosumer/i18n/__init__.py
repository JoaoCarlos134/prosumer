"""The person-facing text in English or Portuguese: notes, log lines and error messages.

Every text this library writes for the person (a note of a report or an outlook, a line of the app's log,
the message of an error the person's own file or answers can cause) is a `Note`: a `str` whose text is the
English one, so anything that reads notes as text keeps working, and that also keeps its template and the
values that filled it. `translate` renders a note, or every note inside a list or a mapping, in another
language; `Report.to_dict(lang=)`, `Outlook.to_dict(lang=)` and `app.Result.to_dict(lang=)` call it on their
whole output, and `message(error, lang)` gives an error's text.

The English template is the key: the Portuguese catalog (`i18n.pt.PT`) maps each template to its translation,
with the same placeholders. Rendered in Portuguese, numbers take the decimal comma (and the point between
thousands where the template groups them, `{x:,.0f}`), dates are day/month/year and a month (a monthly
`pandas.Period`) month/year; a time step (a `timedelta`) reads "15 min" or "1 day" in either language. A
placeholder filled with a `Note` (a fragment: "later", the reason a check was skipped) is rendered in the
same language, as is an error whose message is a `Note`, and a list holding notes or months is joined with
commas (a list of plain texts, such as column names, keeps Python's brackets). A template made only of
placeholders and punctuation (`Note.join`) needs no translation. A template missing from the catalog falls
back to English; `strict=True` raises instead (the tests use it, and a test checks that every template in the
code is in the catalog).

Not translated, by design: identifiers and codes (table columns, forecast names, the `source` and
`confidence` values, units, request fields), names (series, distributors, data sources), the licences and
citations of the provenance (kept in their source's words), the `to_markdown` texts, and the messages of
errors only a programmer can cause (a wrong argument of a library function).
"""

from __future__ import annotations

import datetime as _dt
import numbers
import string
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

LANGS = ("en", "pt")
_SWAP = str.maketrans({".": ",", ",": "."})  # 1,234.5 -> 1.234,5


class Note(str):
    """A text for the person: the English text, plus the template and the values that make it.

    `Note("Coverage below 95% in {n} series: {names}.", n=2, names="a, b")` is the string "Coverage below 95%
    in 2 series: a, b."; `.text("pt")` renders it in Portuguese (module docstring). The template is written as
    an f-string would be, with named placeholders only.
    """

    template: str
    params: dict[str, Any]

    def __new__(cls, template: str, /, **params: Any) -> Note:
        self = super().__new__(cls, _render(template, params, "en", strict=False))
        self.template = template
        self.params = params
        return self

    def __reduce__(self) -> tuple[Any, ...]:  # copy and pickle keep the template, not only the text
        return (_rebuild, (self.template, self.params))

    def text(self, lang: str = "en", *, strict: bool = False) -> str:
        """The note in `lang` (one of `LANGS`), as a plain `str`."""
        _check(lang)
        if lang == "en":
            return str(self)
        return _render(self.template, self.params, lang, strict)

    @classmethod
    def join(cls, items: Iterable[str], sep: str = "; ") -> Note:
        """The items one after the other, `sep` between them; each item that is a `Note` is translated."""
        items = list(items)
        sep = sep.replace("{", "{{").replace("}", "}}")
        template = sep.join(f"{{p{i}}}" for i in range(len(items)))
        return cls(template, **{f"p{i}": x for i, x in enumerate(items)})

    @property
    def parts(self) -> list[Any]:
        """The items of a `join`, in order; any other note alone."""
        names = [f for _, f, _, _ in string.Formatter().parse(self.template) if f is not None]
        if names and names == [f"p{i}" for i in range(len(names))] and _neutral(self.template):
            return [self.params[n] for n in names]
        return [self]


def _rebuild(template: str, params: dict[str, Any]) -> Note:
    return Note(template, **params)


def translate(x: Any, lang: str, *, strict: bool = False) -> Any:
    """`x` with every `Note` in it rendered in `lang` as a plain `str`: a note, an error, or the notes inside
    lists, tuples and mappings (their keys too), recursively; anything else is returned as it is."""
    _check(lang)
    if isinstance(x, Note):
        return x.text(lang, strict=strict)
    if isinstance(x, Mapping):
        return {translate(k, lang, strict=strict): translate(v, lang, strict=strict) for k, v in x.items()}
    if isinstance(x, list):
        return [translate(v, lang, strict=strict) for v in x]
    if isinstance(x, tuple):
        return tuple(translate(v, lang, strict=strict) for v in x)
    if isinstance(x, BaseException):
        return message(x, lang, strict=strict)
    return x


def message(error: BaseException, lang: str = "en", *, strict: bool = False) -> str:
    """The text of `error` in `lang`: translated when its message is a `Note`, `str(error)` otherwise."""
    note = as_note(error)
    return note.text(lang, strict=strict) if isinstance(note, Note) else note


def as_note(error: BaseException | str) -> str:
    """The message of an error or a warning as a `Note` when it was raised with one (`str(error)` would
    keep only the English text), else as `str`; a `str` as it is."""
    if isinstance(error, str):
        return error
    args = error.args
    if len(args) == 1 and isinstance(args[0], Note):
        return args[0]
    return str(error)


def replace(x: str, old: str, new: str) -> str:
    """`x.replace(old, new)` that keeps a `Note` a `Note` (the replacement is made in its values)."""
    if not isinstance(x, Note):
        return x.replace(old, new)
    params = {k: replace(v, old, new) if isinstance(v, str) else v for k, v in x.params.items()}
    return Note(x.template, **params)


def frame(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """`pd.DataFrame(rows)`, with each column that holds a `Note` kept as plain objects: pandas 3 turns a text
    column into its string type, which keeps only the English text."""
    import pandas as pd

    rows = list(rows)  # read twice below: a generator would be empty the second time
    out = pd.DataFrame(rows)
    for c in out.columns:
        values = [r.get(c) for r in rows]
        if any(isinstance(v, Note) for v in values):
            out[c] = pd.Series(values, index=out.index, dtype=object)
    return out


def catalog(lang: str) -> Mapping[str, str]:
    """The templates of `lang`, keyed by the English template (empty for English)."""
    _check(lang)
    if lang == "pt":
        from .pt import PT

        return PT
    return {}


def placeholders(template: str) -> set[str]:
    """The names of the placeholders of a template."""
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def _neutral(template: str) -> bool:
    """Only placeholders, spaces and punctuation: the same in every language."""
    return not any(c.isalpha() for literal, _, _, _ in string.Formatter().parse(template) for c in literal)


def _check(lang: str) -> None:
    if lang not in LANGS:
        raise ValueError(f"lang must be one of {list(LANGS)}, not {lang!r}")


def _render(template: str, params: Mapping[str, Any], lang: str, strict: bool) -> str:
    if lang != "en" and not _neutral(template):
        target = catalog(lang).get(template)
        if target is None:
            if strict:
                raise KeyError(f"No {lang!r} translation of {template!r}")
            target = template
        template = target
    return _Formatter(lang, strict).vformat(template, (), params)


class _Formatter(string.Formatter):
    def __init__(self, lang: str, strict: bool) -> None:
        self.lang, self.strict = lang, strict

    def convert_field(self, value: Any, conversion: str | None) -> Any:
        if conversion == "s" and isinstance(value, Note):
            return value
        return super().convert_field(value, conversion)

    def format_field(self, value: Any, format_spec: str) -> str:
        if isinstance(value, Note):
            return format(value.text(self.lang, strict=self.strict), format_spec)
        if isinstance(value, BaseException):
            return format(message(value, self.lang, strict=self.strict), format_spec)
        if isinstance(value, list | tuple) and any(isinstance(v, Note) or _is_month(v) for v in value):
            return format(", ".join(self.format_field(v, "") for v in value), format_spec)
        if _is_month(value) and not format_spec:
            y, m = value.year, value.month
            return f"{m:02d}/{y:04d}" if self.lang == "pt" else f"{y:04d}-{m:02d}"
        if isinstance(value, _dt.timedelta) and not format_spec:
            return _duration(value, self.lang)
        if self.lang != "en":
            if isinstance(value, numbers.Number) and not isinstance(value, bool):
                return format(value, format_spec).translate(_SWAP)
            if isinstance(value, _dt.date) and not format_spec:
                try:
                    if isinstance(value, _dt.datetime):
                        return value.strftime("%d/%m/%Y %H:%M")
                    return value.strftime("%d/%m/%Y")
                except ValueError:  # NaT
                    pass
        return format(value, format_spec)


def _is_month(value: Any) -> bool:
    """A monthly `pandas.Period` (`Period("2026-02", "M")`): 2026-02 in English, 02/2026 in Portuguese."""
    return type(value).__name__ == "Period" and str(getattr(value, "freqstr", "")) == "M"


_UNITS = {"en": ("day", "days"), "pt": ("dia", "dias")}


def _duration(td: _dt.timedelta, lang: str) -> str:
    """A time step for the person: "1 day", "15 min", "1 h 30 min" (pandas writes "0 days 00:15:00")."""
    seconds = int(td.total_seconds())
    if seconds <= 0 or seconds != td.total_seconds():
        return str(td)
    days, rest = divmod(seconds, 86400)
    h, rest = divmod(rest, 3600)
    m, sec = divmod(rest, 60)
    one, many = _UNITS[lang]
    parts = [f"{days} {one if days == 1 else many}"] if days else []
    parts += [f"{v} {u}" for v, u in ((h, "h"), (m, "min"), (sec, "s")) if v]
    return " ".join(parts)


__all__ = ["LANGS", "Note", "as_note", "catalog", "frame", "message", "placeholders", "replace", "translate"]
