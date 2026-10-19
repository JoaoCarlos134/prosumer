"""The app's backend in one call: the person's files and a few answers in, everything a page shows out.

An app on top of the library (the TCC's TypeScript site, the example site, a notebook) should only render:
`run(request, files)` does the work in the library's own steps and returns a `Result` whose `to_dict()` is
JSON-ready. The steps, each one library call:

    1. where is it                  -> io.geocode.geocode / round_site / timezone_at (or the typed site)
    2. read each file               -> io.read_energy (layout recognised; energy by name and unit)
    3. the weather of the next days -> io.open_meteo.fetch_forecast (generation only)
    4. the next days                -> forecast_ahead, for each file
    5. when to run a heavy load     -> best_windows (and economics.windows_by_cost with a price)
    6. the analysis of the data     -> analyze (quality, clock, diagnostics, forecast check; with a price and
                                       the consumption, the bill with and without the PV)
    7. what the pages plot          -> `Result.charts`: the daily energy of each file, the test hours of the
                                       forecast check, the clear-day performance of a PV file

`files` maps "generation" and/or "consumption" to (bytes, file name): with both, the bill nets the PV against
the household's use hour by hour and the report has the savings.

The request is a plain mapping (`Request.from_dict`, unknown keys are an error):

- `address` or `latitude` + `longitude` (rounded to ~1 km before anything is sent anywhere); `timezone`
  (default: asked of Open-Meteo for the site); `file_times` "local" (default) or "UTC";
- reading: `time_column`, `value_column`, `unit`, `kind` (when the guess needs help; generation and
  consumption files are read with the same hints);
- the next days: `days` (1-35; the weather reaches 16), `tilt`, `azimuth`, `kwp` (optional: learnt from the
  data otherwise), `load_hours` (3), `load_kw` (2.0);
- `test_days` of the forecast check (28); `models`, the forecasts its median takes: "lightgbm" (default: the
  three naive rules and LightGBM, seconds on a CPU), "naive" (the naive rules only, the fastest) or "all"
  (also the four zero-shot foundation models that are installed: minutes on a CPU, and torch). Measured on the
  benchmark (pilot of 2026-10-16), the median of the naive rules alone ranked 29th to 36th of ~50; with
  LightGBM, 10th to 19th; with the foundation models too, 4th or 5th. A model whose extra is not installed is
  left out with a note;
- `price` (optional): `{"kind": "flat", "price", "export_price", "fixed", "currency", "scheme"}`,
  `{"kind": "tou", "peak_hours": "17-21", "peak_price", "offpeak_price", ...}` (weekends off-peak) or
  `{"kind": "brazil", "distributor": "COPEL-DIS", "icms", "pis_cofins" (fractions, as read on a bill),
  "connection", "gd", "cosip", "modality", "peak_start"}` (ANEEL's open data; GD only with a PV file).

Privacy: the files never leave the machine. Out go only the address (to Nominatim, if typed instead of the
coordinates), the rounded coordinates (to Open-Meteo) and, for a Brazilian price, the distributor's name (to
ANEEL); the free Open-Meteo API is for non-commercial use. `Services` replaces those calls (tests, a cache, an
offline app).
"""

from __future__ import annotations

import json
import math
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from . import economics as econ
from .analysis import Report, analyze
from .contracts import EnergySeries, Quantity
from .economics import brazil
from .forecast import Chronos2, FlowState, Forecaster, LightGBM, TiRex2, Toto2
from .io import geocode as geo
from .io import open_meteo, read_energy
from .outlook import MAX_DAYS, Outlook, best_windows, forecast_ahead
from .provenance import Provenance, of

QUANTITIES: tuple[Quantity, ...] = ("generation", "consumption")
PRICE_KINDS = ("flat", "tou", "brazil")
MODEL_SETS = ("lightgbm", "naive", "all")
# the zero-shot models of `models="all"`: (name, the module its extra installs, the adapter)
FOUNDATION: tuple[tuple[str, str, Callable[[], Forecaster]], ...] = (
    ("Chronos-2", "chronos", Chronos2),
    ("TiRex-2", "tirex2", TiRex2),
    ("Toto-2.0", "toto2", Toto2),
    ("FlowState", "tsfm_public", FlowState),
)
Files = Mapping[str, tuple[bytes, str]]


@dataclass(frozen=True)
class Services:
    """The outside calls of `run`, replaceable: geocoding, the site's time zone, the live weather forecast and
    a Brazilian distributor's tariff book."""

    geocode: Callable[..., pd.DataFrame] = geo.geocode
    timezone_at: Callable[..., str] = geo.timezone_at
    weather: Callable[..., pd.DataFrame] = open_meteo.fetch_forecast
    tariff_book: Callable[..., brazil.TariffBook] = brazil.TariffBook.from_aneel


@dataclass(frozen=True)
class Request:
    """What the person answered (module docstring). Build it with `from_dict` from the page's JSON."""

    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    file_times: Literal["local", "UTC"] = "local"
    time_column: str | None = None
    value_column: str | None = None
    unit: str | None = None
    kind: str | None = None
    days: int = 7
    tilt: float | None = None
    azimuth: float | None = None
    kwp: float | None = None
    load_hours: int = 3
    load_kw: float = 2.0
    test_days: int = 28
    models: str = "lightgbm"
    price: Mapping[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Request:
        """From JSON: empty strings are "not given", numbers may come as text (a decimal comma too)."""
        names = {f.name: f for f in fields(cls)}
        unknown = sorted(set(d) - set(names))
        if unknown:
            raise ValueError(f"Unknown request fields {unknown}; the fields are {list(names)}")
        out: dict[str, Any] = {}
        for k, v in d.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            if k in ("latitude", "longitude", "tilt", "azimuth", "kwp", "load_kw"):
                out[k] = _number(v, k)
            elif k in ("days", "load_hours", "test_days"):
                x = _number(v, k)
                if x != int(x):
                    raise ValueError(f"{k} must be a whole number, not {v!r}")
                out[k] = int(x)
            elif k == "price":
                if not isinstance(v, Mapping):
                    raise ValueError("price must be an object, e.g. {'kind': 'flat', 'price': 0.8}")
                out[k] = dict(v)
            else:
                out[k] = str(v).strip()
        r = cls(**out)
        r.check()
        return r

    def check(self) -> None:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Give both the latitude and the longitude, or an address")
        if self.latitude is None and not self.address:
            raise ValueError("Give an address or the latitude and longitude")
        if self.file_times not in ("local", "UTC"):
            raise ValueError("file_times must be 'local' or 'UTC'")
        if not 1 <= self.days <= MAX_DAYS:
            raise ValueError(f"days must be in 1-{MAX_DAYS}")
        if not 1 <= self.load_hours <= 24:
            raise ValueError("load_hours must be in 1-24")
        if self.load_kw <= 0:
            raise ValueError("load_kw must be positive")
        if self.test_days < 2:
            raise ValueError("test_days must be >= 2")
        if self.models not in MODEL_SETS:
            raise ValueError(f"models must be one of {list(MODEL_SETS)}")
        if self.price is not None and self.price.get("kind") not in PRICE_KINDS:
            raise ValueError(f"price.kind must be one of {list(PRICE_KINDS)}")


@dataclass
class Result:
    """Everything the page shows; `to_dict()` is JSON-ready (timestamps ISO, tables as lists of records)."""

    site: dict[str, Any]
    read: dict[str, dict[str, Any]]
    outlooks: dict[str, Outlook]
    windows: pd.DataFrame
    report: Report
    windows_by_cost: pd.DataFrame | None = None
    pricing: str | None = None
    # what the pages plot: "history_<file>" (unique_id, date, energy, measured_hours: each day of the file),
    # "check" (`Report.hourly`: the test hours, measured and forecast), "performance" (`Diagnosis.index`: the
    # clear days of a PV file, energy, expected and their ratio)
    charts: dict[str, pd.DataFrame] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    credits: list[Provenance] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Strict-JSON-ready: NaN and infinities become None (a browser's JSON.parse rejects NaN)."""
        out = {
            "site": self.site,
            "read": self.read,
            "outlooks": {k: o.to_dict() for k, o in self.outlooks.items()},
            "windows": _records(self.windows),
            "windows_by_cost": None if self.windows_by_cost is None else _records(self.windows_by_cost),
            "pricing": self.pricing,
            "charts": {k: _records(v) for k, v in self.charts.items()},
            "report": self.report.to_dict(),
            "notes": list(self.notes),
            "log": list(self.log),
            "credits": [c.to_dict() for c in self.credits],
        }
        result: dict[str, Any] = _json(out)
        return result

    def to_json(self, **kwargs: Any) -> str:
        """`to_dict` as strict JSON text (`allow_nan=False`: it raises rather than write `NaN`)."""
        return json.dumps(self.to_dict(), allow_nan=False, ensure_ascii=False, **kwargs)


def run(
    request: Request | Mapping[str, Any],
    files: Files,
    *,
    services: Services | None = None,
) -> Result:
    """The whole analysis of the person's files (module docstring). Raises `ValueError` with a message for the
    person (no file, no site, an ambiguous column, a tariff that cannot be downloaded)."""
    req = request if isinstance(request, Request) else Request.from_dict(request)
    req.check()
    svc = services or Services()
    unknown = sorted(set(files) - set(QUANTITIES))
    if unknown:
        raise ValueError(f"Files are keyed by {list(QUANTITIES)}, not {unknown}")
    given = {q: files[q] for q in QUANTITIES if q in files and files[q][0]}
    if not given:
        raise ValueError("No file was received: send the generation or the consumption file (or both).")
    log: list[str] = []
    credits: list[Provenance] = []

    # 1. Where. Typed coordinates win; otherwise the address is geocoded and the first match is used.
    if req.latitude is not None and req.longitude is not None:
        lat, lon, found_name = req.latitude, req.longitude, None
        log.append(f"Site typed: {lat}, {lon}.")
    else:
        found = svc.geocode(req.address, limit=1)
        if found.empty:
            raise ValueError(f"Address not found: {req.address!r}. Type the coordinates instead.")
        lat, lon = float(found["latitude"].to_numpy()[0]), float(found["longitude"].to_numpy()[0])
        found_name = str(found["name"].to_numpy()[0])
        log.append(f"Address found: {found_name}.")
        _credit(credits, of(found))
    site = geo.round_site(lat, lon)
    tz = req.timezone or svc.timezone_at(*site)
    log.append(f"Site used (rounded): {site[0]}, {site[1]}; time zone {tz}.")

    # 2. Read each file: layout recognised, energy column by name and unit, never by position.
    series: dict[str, EnergySeries] = {}
    read: dict[str, dict[str, Any]] = {}
    for q, (data, name) in given.items():
        s = _read(data, name, q, req, site, tz)
        series[q] = s
        span = s.frame["ds"]
        how = s.provenance.notes.split("; ")[0] if s.provenance else ""
        read[q] = {
            "file": name,
            "how": how,
            "hours": len(s.frame),
            "start": span.min(),
            "end": span.max(),
            "measured": float(s.frame["valid"].mean()),
            "series": s.series,
        }
        log.append(
            f"{q.capitalize()}: read {how}; {len(s.frame)} hours, {s.frame['valid'].mean():.0%} measured."
        )

    # 3. The weather of the next days (generation only). Up to 16 days: the API's limit.
    weather = None
    if "generation" in series:
        weather = svc.weather(*site, days=min(req.days, open_meteo.MAX_FORECAST_DAYS), tz=tz)
        log.append(f"Weather forecast downloaded: {weather['model'].nunique()} models.")
        _credit(credits, of(weather))

    # 4. The next days, for each file.
    outlooks = {
        q: forecast_ahead(
            s,
            days=req.days,
            site=site,
            weather=weather if q == "generation" else None,
            tilt=req.tilt,
            azimuth=req.azimuth,
            kwp=req.kwp,
        )
        for q, s in series.items()
    }
    main = "generation" if "generation" in outlooks else "consumption"

    # 5. When to run a heavy load: the best block of each day (most sun, or least use without PV).
    windows = best_windows(outlooks[main], req.load_hours)
    notes: list[str] = []
    pricing = _pricing(req.price, outlooks, svc, credits, notes) if req.price else None
    by_cost = None
    if pricing is not None:
        by_cost = econ.windows_by_cost(
            pricing,
            generation=outlooks.get("generation"),
            consumption=outlooks.get("consumption"),
            hours=req.load_hours,
            kw=req.load_kw,
            top=1,
        )
        notes += list(by_cost.attrs.get("notes", []))

    # 6. The analysis of the data: with a price and the consumption, the bill (and with PV, the savings).
    kw: dict[str, Any] = {}
    if pricing is not None:
        kw["economics"] = pricing
        if main == "generation" and "consumption" in series:
            kw["consumption"] = series["consumption"]
    models = _models(req.models, notes)
    report = analyze(series[main], site=site, kwp=req.kwp, test_days=req.test_days, models=models, **kw)
    if models:
        log.append(f"Forecast check with the naive rules and {', '.join(m.card.name for m in models)}.")

    # 7. What the pages plot.
    charts = {f"history_{q}": _daily(s) for q, s in series.items()}
    if report.hourly is not None:
        charts["check"] = report.hourly
    if report.diagnostics is not None:
        charts["performance"] = report.diagnostics.index
    return Result(
        site={"latitude": site[0], "longitude": site[1], "timezone": tz, "address_found": found_name},
        read=read,
        outlooks=outlooks,
        windows=windows,
        report=report,
        windows_by_cost=by_cost,
        pricing=None if pricing is None else pricing.describe(),
        charts=charts,
        notes=notes,
        log=log,
        credits=credits,
    )


# ---------------------------------------------------------------------- pieces
def _models(choice: str, notes: list[str]) -> list[Forecaster]:
    """The forecasters the forecast check adds to the naive rules (`Request.models`); a model whose extra is
    not installed is left out with a note."""
    if choice == "naive":
        return []
    out: list[Forecaster] = []
    if find_spec("lightgbm") and find_spec("sklearn"):
        out.append(LightGBM())
    else:
        notes.append(
            "LightGBM is not installed (`pip install prosumer[lightgbm]`): left out of the forecast check."
        )
    if choice == "all":
        for name, module, make in FOUNDATION:
            if find_spec(module):
                out.append(make())
            else:
                notes.append(f"{name} is not installed (its extra, see the install notes): left out.")
    return out


def _daily(s: EnergySeries) -> pd.DataFrame:
    """Each day of a file: the energy of its measured hours and how many hours were measured."""
    f = s.frame.assign(date=s.frame["ds"].dt.tz_localize(None).dt.normalize())
    f = f.assign(y=f["y"].where(f["valid"]))
    g = f.groupby(["unique_id", "date"], sort=True)
    return pd.DataFrame(
        {"energy": g["y"].sum(min_count=1), "measured_hours": g["valid"].sum().astype(int)}
    ).reset_index()


def _read(data: bytes, name: str, q: str, req: Request, site: tuple[float, float], tz: str) -> EnergySeries:
    suffix = Path(name).suffix.lower()
    suffix = suffix if suffix in (".csv", ".txt", ".xlsx") else ".csv"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{q}{suffix}"
        path.write_bytes(data)
        s = read_energy(
            path,
            tz=tz,
            quantity=cast(Quantity, q),
            time_column=req.time_column,
            value_column=req.value_column,
            unit=req.unit,  # type: ignore[arg-type]
            kind=req.kind,  # type: ignore[arg-type]
            freq="h",
            site=site if q == "generation" else None,  # the inverter sleeps at night: zeros
            source_tz="UTC" if req.file_times == "UTC" else None,
        )
    if s.provenance is not None:  # the temporary path means nothing to the person: their file name instead
        from dataclasses import replace

        s = EnergySeries.from_dataframe(
            s.frame,
            unit=s.unit,
            quantity=s.quantity,
            tz=s.tz,
            freq=s.freq,
            provenance=replace(
                s.provenance,
                source=s.provenance.source.replace(path.name, name),
                notes=s.provenance.notes.replace(path.name, name),
            ),
        )
    return s


def _pricing(
    price: Mapping[str, Any],
    outlooks: Mapping[str, Outlook],
    svc: Services,
    credits: list[Provenance],
    notes: list[str],
) -> econ.Pricing:
    """The request's price as a `Pricing`: `economics.Plan` (flat or time-of-use) or `brazil.Setup`."""
    p = dict(price)
    kind = p.pop("kind")
    with_pv = "generation" in outlooks

    def num(key: str, what: str, default: float | None = None) -> float:
        v = p.pop(key, None)
        if v is None or (isinstance(v, str) and not v.strip()):
            if default is None:
                raise ValueError(f"Give {what}.")
            return default
        return _number(v, what)

    if kind == "brazil":
        agent = str(p.pop("distributor", "COPEL-DIS"))
        icms = num("icms", "the ICMS rate of your bill (a fraction, e.g. 0.19)")
        pis = num("pis_cofins", "the PIS/COFINS rate of your bill (a fraction, e.g. 0.0925)")
        if icms >= 1 or pis >= 1:
            raise ValueError("ICMS and PIS/COFINS are fractions (0.19 for 19%)")
        gd = p.pop("gd", None) if with_pv else None
        modality = str(p.pop("modality", brazil.CONVENTIONAL))
        peak_start = p.pop("peak_start", None)
        connection = p.pop("connection", "bifasico_3")
        cosip = num("cosip", "the COSIP", 0.0)
        years: list[int] = []
        if with_pv and gd == "GD II":
            ds = outlooks["generation"].hourly["ds"]
            years = sorted({y + k for y in set(ds.dt.year) for k in (-1, 0)})  # Fio B from the adjustment day
        _no_more(p, "price")
        try:
            book = svc.tariff_book(agent, icms=icms, pis_cofins=pis, fio_b_years=years, extend_last=True)
        except (OSError, RuntimeError) as e:  # offline, or ANEEL's API down
            raise ValueError(
                f"Could not download {agent}'s tariffs from ANEEL's open data ({e}). Check the connection, "
                "or give a flat or time-of-use price instead."
            ) from e
        credits.extend(book.provenance)
        notes.extend(book.notes)
        return brazil.Setup(
            book=book,
            connection=connection,
            gd=gd,
            modality=modality,
            peak_start=peak_start,
            cosip=cosip,
        )
    currency = str(p.pop("currency", "EUR"))
    export = num("export_price", "the export price", 0.0)
    fixed = num("fixed", "the fixed charge", 0.0)
    scheme = str(p.pop("scheme", "net_metering"))
    if kind == "flat":
        tariff = econ.Tariff.flat(
            num("price", "the price per kWh"), export_price=export, fixed=fixed, currency=currency
        )
    else:
        a, b = _peak_hours(str(p.pop("peak_hours", "17-21")))
        peak = {h for h in range(24) if (a <= h < b if a < b else h >= a or h < b)}
        tariff = econ.Tariff(
            prices={
                "peak": num("peak_price", "the peak price"),
                "off_peak": num("offpeak_price", "the off-peak price"),
            },
            weekday={h: "peak" if h in peak else "off_peak" for h in range(24)},
            weekend=dict.fromkeys(range(24), "off_peak"),
            export_price=export,
            fixed=fixed,
            currency=currency,
            name=f"time-of-use (peak {a:02d}:00-{b:02d}:00 on weekdays)",
        )
    _no_more(p, "price")
    return econ.Plan(tariff, scheme=scheme)  # type: ignore[arg-type]


def _peak_hours(text: str) -> tuple[int, int]:
    """'17-21' -> (17, 21): whole hours, start-end; the end may wrap past midnight ('22-6')."""
    m = re.fullmatch(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", text)
    a, b = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    if not m or not (0 <= a <= 23 and 0 <= b <= 24) or a == b % 24:
        raise ValueError(f"Peak hours {text!r}: give whole hours as start-end on a 24 h clock, e.g. 17-21")
    return a, b


def _number(v: Any, what: str) -> float:
    if isinstance(v, bool):
        raise ValueError(f"{what}: {v!r} is not a number")
    if isinstance(v, int | float):
        return float(v)
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"{what}: {v!r} is not a number") from None


def _no_more(rest: Mapping[str, Any], what: str) -> None:
    if rest:
        raise ValueError(f"Unknown {what} fields {sorted(rest)}")


def _credit(credits: list[Provenance], p: Provenance | None) -> None:
    if p is not None and p not in credits:
        credits.append(p)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): v for k, v in r.items()} for r in df.to_dict(orient="records")]


def _json(v: Any) -> Any:
    """Recursively JSON-ready: timestamps ISO, numpy scalars Python, NaN/inf/NaT None, tuples lists."""
    if isinstance(v, Mapping):
        return {str(k): _json(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_json(x) for x in v]
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if v is pd.NaT:
        return None
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, pd.Timedelta):
        return v.isoformat()
    return v


__all__ = ["MODEL_SETS", "PRICE_KINDS", "QUANTITIES", "Request", "Result", "Services", "run"]
