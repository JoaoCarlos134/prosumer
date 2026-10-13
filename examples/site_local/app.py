"""A deliberately crude local web page for `prosumer`: upload a CSV, say where it is, get the next days.

Run it (from the repository root, with the library installed in the environment):

    python examples/site_local/app.py          # then open http://127.0.0.1:8000

Nothing but the Python standard library and `prosumer`: no web framework, no JavaScript. The whole backend is
the function `forecast_page` below, in numbered steps that map one to one to library calls:

    1. read the CSV                 -> prosumer.io.meter.read_table
    2. where is it                  -> prosumer.io.geocode.geocode / round_site / timezone_at
    3. the weather of the next days -> prosumer.io.open_meteo.fetch_forecast
    4. the forecast                 -> prosumer.forecast_ahead
    5. when to run heavy loads      -> prosumer.best_windows
    6. the same, by cost            -> prosumer.economics.windows_by_cost      (with a price)
    7. the monthly bill of the data -> Plan.bill / brazil.Setup.bill, .totals() (with a price, consumption)

The price comes from the form (`_pricing`): a flat price, a simple time-of-use price, or a Brazilian
distributor's tarifa convencional downloaded from ANEEL's open data (`brazil.TariffBook.from_aneel`) with the
ICMS and PIS/COFINS the person types.

Privacy: the file never leaves this machine. Only the address (to Nominatim, if you type one instead of
coordinates), the coordinates rounded to 2 decimals (to Open-Meteo, for the weather) and, for a Brazilian
tariff, the distributor's name (to ANEEL) go out. The free Open-Meteo API is for non-commercial use.
"""

from __future__ import annotations

import html
import io
import traceback
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd

import prosumer
from prosumer import economics
from prosumer.economics import brazil
from prosumer.io import geocode, meter, open_meteo
from prosumer.provenance import Provenance, of

HERE = Path(__file__).resolve().parent
HOST, PORT = "127.0.0.1", 8000
ANEEL_GET = None  # the HTTP getter of io.aneel (None: the live API); the tests put a fake ANEEL here
DISTRIBUTORS = {  # ANEEL's SigAgente -> what the person knows it as
    "COPEL-DIS": "Copel (PR)",
    "CEMIG-D": "Cemig (MG)",
    "ELETROPAULO": "Enel SP",
    "LIGHT SESA": "Light (RJ)",
}


# ---------------------------------------------------------------------- the backend: seven steps
def forecast_page(form: dict[str, str], csv: bytes) -> str:
    """Form fields + CSV bytes -> the result page (HTML). Each step adds a line to `log`, shown below."""
    log: list[str] = []
    credits: list = []  # where each piece of outside data came from, shown at the end (licences require it)
    quantity = form.get("quantity") or "generation"

    # 1. Read the CSV. Without column names: the first column is the time, the second the energy.
    table = pd.read_csv(io.BytesIO(csv), sep=None, engine="python")
    time_col = form.get("time_column") or table.columns[0]
    value_col = form.get("value_column") or table.columns[1]

    # 2. Where. Typed coordinates win; otherwise the address is geocoded and the first match is used.
    if form.get("latitude") and form.get("longitude"):
        lat, lon = float(form["latitude"]), float(form["longitude"])
        log.append(f"Site typed: {lat}, {lon}.")
    elif form.get("address"):
        found = geocode.geocode(form["address"], limit=1)
        if found.empty:
            raise ValueError(f"Address not found: {form['address']!r}. Type the coordinates instead.")
        lat, lon = float(found["latitude"].to_numpy()[0]), float(found["longitude"].to_numpy()[0])
        log.append(f"Address found: {found.loc[0, 'name']}.")
        credits.append(of(found))
    else:
        raise ValueError("Give an address or the latitude and longitude.")
    site = geocode.round_site(lat, lon)  # ~1 km: enough for the weather and the sun
    tz = form.get("timezone") or geocode.timezone_at(*site)
    log.append(f"Site used (rounded): {site[0]}, {site[1]}; time zone {tz}.")

    series = meter.read_table(
        table,
        time_column=time_col,
        value_columns=value_col,
        names=["mine"],
        tz=tz,
        unit=form.get("unit") or "kWh",  # type: ignore[arg-type]
        quantity=quantity,  # type: ignore[arg-type]
        kind=form.get("kind") or "interval",  # type: ignore[arg-type]
        freq="h",
    )
    span = series.frame["ds"]
    log.append(f"Read {len(series.frame)} hours, {span.min():%Y-%m-%d} to {span.max():%Y-%m-%d}.")

    # 3. The weather of the next days (only generation uses it). Up to 16 days: the API's limit.
    days = int(form.get("days") or 7)
    weather = None
    if quantity == "generation":
        weather = open_meteo.fetch_forecast(*site, days=min(days, open_meteo.MAX_FORECAST_DAYS), tz=tz)
        log.append(f"Weather forecast downloaded: {weather['model'].nunique()} models.")
        credits.append(of(weather))

    # 4. The forecast. Tilt, azimuth and kWp are optional: without them the library learns them from the data.
    def number(key: str) -> float | None:
        return float(form[key]) if form.get(key) else None

    tilt, azimuth, kwp = number("tilt"), number("azimuth"), number("kwp")
    out = prosumer.forecast_ahead(
        series, days=days, site=site, weather=weather, tilt=tilt, azimuth=azimuth, kwp=kwp
    )

    # 5. When to run a heavy load: the best block of hours of each day.
    hours = int(form.get("load_hours") or 3)
    windows = prosumer.best_windows(out, hours)

    money = Money()
    pricing = _pricing(form, out, credits)  # the price typed in the form, or None
    if pricing is not None:
        money.tariff = pricing.describe()
        # 6. The same by cost: the cheapest block of each day for a load of `kw` kW, with its confidence.
        money.kw = float(form.get("load_kw") or 2.0)
        outlooks = {"generation": out} if quantity == "generation" else {"consumption": out}
        money.windows = economics.windows_by_cost(pricing, **outlooks, hours=hours, kw=money.kw, top=1)
        money.notes += money.windows.attrs["notes"]

        # 7. The bill of each month of your data (the bill needs what the household used: consumption only).
        if quantity == "consumption":
            try:
                bill = pricing.bill(series)
                money.monthly, money.totals = bill.monthly, bill.totals()
                money.notes += bill.notes
            except (ValueError, NotImplementedError) as e:  # e.g. no tariff in force on the data's dates
                money.notes.append(f"No bill for your data: {e}")
        else:
            money.notes.append("The monthly bill needs your consumption: upload it to see what you pay.")

    return _render(out, windows, hours, log, [c for c in credits if c is not None], money)


class Money:
    """What steps 6 and 7 found, for the page (empty when no price was given)."""

    def __init__(self) -> None:
        self.tariff = ""
        self.kw = 0.0
        self.windows: pd.DataFrame | None = None
        self.monthly: pd.DataFrame | None = None
        self.totals: pd.DataFrame | None = None
        self.notes: list[str] = []


def _pricing(form: dict[str, str], out: prosumer.Outlook, credits: list) -> economics.Pricing | None:
    """The form's price as a `Pricing`: `economics.Plan` (flat or time-of-use) or `brazil.Setup` (ANEEL)."""
    kind = form.get("price") or "none"
    if kind == "none":
        return None

    def number(key: str, what: str) -> float:
        if not form.get(key):
            raise ValueError(f"Give {what}.")
        return float(form[key].replace(",", "."))

    if kind == "brazil":
        agent = form.get("distributor") or "COPEL-DIS"
        icms = number("icms", "the ICMS rate of your bill (%)") / 100  # user inputs: no table by state
        pis = number("pis_cofins", "the PIS/COFINS rate of your bill (%)") / 100
        gd = (form.get("gd") or None) if out.quantity == "generation" else None  # GD: only with PV
        years = (
            sorted(set(out.hourly["ds"].dt.year)) if out.quantity == "generation" and gd == "GD II" else []
        )
        try:
            book = brazil.TariffBook.from_aneel(
                agent, icms=icms, pis_cofins=pis, fio_b_years=years, extend_last=True, get=ANEEL_GET
            )
        except (OSError, RuntimeError) as e:  # offline, or ANEEL's API down
            raise ValueError(
                f"Could not download {DISTRIBUTORS.get(agent, agent)}'s tariffs from ANEEL's open data "
                f"({e}). "
                "Check the internet connection, or choose a flat or time-of-use price instead."
            ) from e
        credits.extend(book.provenance)
        return brazil.Setup(
            book=book,
            connection=form.get("connection") or "bifasico_3",
            gd=gd,  # type: ignore[arg-type]
            cosip=float(form.get("cosip") or 0),
        )
    currency = form.get("currency") or "EUR"
    export = float(form.get("export_price") or 0)
    fixed = float(form.get("fixed") or 0)
    scheme = form.get("scheme") or "net_metering"
    if kind == "flat":
        tariff = economics.Tariff.flat(
            number("flat_price", "the price per kWh"),
            export_price=export,
            fixed=fixed,
            currency=currency,
            name="your flat price",
        )
    elif kind == "tou":
        a, b = (int(x) for x in (form.get("peak_hours") or "17-21").split("-"))
        peak = {h for h in range(24) if (a <= h < b if a < b else h >= a or h < b)}
        tariff = economics.Tariff(
            prices={
                "peak": number("peak_price", "the peak price"),
                "off_peak": number("offpeak_price", "the off-peak price"),
            },
            weekday={h: "peak" if h in peak else "off_peak" for h in range(24)},
            weekend=dict.fromkeys(range(24), "off_peak"),  # no peak on Saturdays and Sundays
            export_price=export,
            fixed=fixed,
            currency=currency,
            name=f"your time-of-use price (peak {a:02d}:00-{b:02d}:00 on weekdays)",
        )
    else:
        raise ValueError(f"Unknown price kind {kind!r}")
    return economics.Plan(tariff, scheme=scheme)  # type: ignore[arg-type]


# ---------------------------------------------------------------------- HTML (plain tables, no script)
def _render(
    out: prosumer.Outlook, windows: pd.DataFrame, hours: int, log: list[str], credits: list, money: Money
) -> str:
    daily = out.daily
    top = max(float(daily["high"].max()), 1e-9)
    rows = []
    for _, d in daily.iterrows():
        bar = int(300 * d["total"] / top)
        rows.append(
            f"<tr><td>{d['date']:%a %d %b %Y}</td><td>{d['lead_day']}</td>"
            f"<td>{d['total']:.1f}</td><td>{d['low']:.1f} - {d['high']:.1f}</td>"
            f"<td>{html.escape(str(d['confidence']))}</td>"
            f"<td><span class=bar style='width:{bar}px'></span></td></tr>"
        )
    best = "".join(
        f"<tr><td>{w['date']:%a %d %b %Y}</td><td>{w['start']:%H:%M} - {w['end']:%H:%M}</td>"
        f"<td>{w['energy']:.1f}</td><td>{html.escape(str(w['confidence']))}</td></tr>"
        for _, w in windows.iterrows()
    )
    hourly = out.hourly.assign(ds=out.hourly["ds"].dt.strftime("%Y-%m-%d %H:%M"))
    hourly = hourly[["ds", "lead_day", "y_hat", "low", "high", "source", "n_models"]].round(3)
    what = "production" if out.quantity == "generation" else "consumption"
    pick = "most production" if out.quantity == "generation" else "least consumption"
    method = html.escape(str(out.method.get("series", out.method)))
    return _page(
        f"""
<h1>Forecast of your {what}, kWh</h1>
<p><a href="/">New forecast</a></p>
<h2>Per day</h2>
<table><tr><th>Day</th><th>Lead</th><th>Total</th><th>Range</th><th>Confidence</th><th></th></tr>
{"".join(rows)}</table>
<p class=small>{_range_note(out.quantity)}</p>
<h2>Best {hours} hours of each day for a heavy load ({pick})</h2>
<table><tr><th>Day</th><th>Hours</th><th>kWh in the block</th><th>Confidence</th></tr>{best}</table>
{_money(money, hours)}
<h2>Notes</h2><ul>{"".join(f"<li>{html.escape(n)}</li>" for n in out.notes + money.notes + log)}</ul>
<h2>What the library learnt</h2><pre>{method}</pre>
<h2>Data sources</h2><ul>{"".join(f"<li>{t}</li>" for t in dict.fromkeys(map(_credit, credits)))}</ul>
<details><summary>Every hour</summary>{hourly.to_html(index=False)}</details>
"""
    )


def _money(money: Money, hours: int) -> str:
    """The cheapest block of each day by cost (next to the best one by energy) and the monthly bill."""
    if money.windows is None:
        return ""
    cur = html.escape(str(money.windows["currency"].iloc[0])) if len(money.windows) else ""
    cheap = "".join(
        f"<tr><td>{w['date']:%a %d %b %Y}</td><td>{w['start']:%H:%M} - {w['end']:%H:%M}</td>"
        f"<td>{w['cost']:.2f}</td><td>{w['grid_kwh']:.1f}</td><td>{w['pv_kwh']:.1f}</td>"
        f"<td>{html.escape(str(w['confidence']))}</td></tr>"
        for _, w in money.windows.iterrows()
    )
    parts = [
        f"<h2>Cheapest {hours} hours of each day for a {money.kw:g} kW load, by expected cost</h2>",
        f"<p class=small>Price: {html.escape(money.tariff)}.</p>",
        f"<table><tr><th>Day</th><th>Hours</th><th>Cost, {cur}</th><th>kWh from the grid</th>"
        f"<th>kWh from your PV</th><th>Confidence</th></tr>{cheap}</table>",
    ]
    if money.monthly is not None and money.totals is not None:
        m = money.monthly
        rows = "".join(
            f"<tr><td>{r['month']:%Y-%m}</td><td>{r['consumption']:.0f}</td><td>{r['total']:.2f}</td>"
            f"<td>{r['coverage']:.0%}</td></tr>"
            for _, r in m.iterrows()
        )
        t = money.totals.iloc[0]
        expected = (
            f"Expected monthly bill: <b>{t['mean_month']:.2f} {cur}</b> (mean of the "
            f"{int(t['complete_months'])} complete month(s) of your data)."
            if t["complete_months"] > 0
            else "No month of your data is complete, so there is no expected monthly bill."
        )
        parts += [
            "<h2>Your bill, month by month (from your data)</h2>",
            f"<p>{expected}</p>",
            f"<table><tr><th>Month</th><th>kWh</th><th>Bill, {cur}</th><th>Hours measured</th></tr>{rows}"
            "</table>",
        ]
    return "\n".join(parts)


def _credit(c: Provenance) -> str:
    """A data source for the page: its citation (or source), its licence and conditions."""
    text = c.citation or c.source
    if c.license_known and c.license != "n/a":
        text += f" Licence: {c.license}." + (f" {c.notes}." if c.notes else "")
    elif c.notes:
        text += f": {c.notes}."
    return html.escape(text)


def _range_note(quantity: str) -> str:
    if quantity == "generation":
        return (
            "Range: across the weather models and the usual spread of the season (not a calibrated "
            "interval). Confidence is the measured skill at that many days ahead (two plants in Brazil): "
            "high for days 1-3, medium 4-6, low on day 7; from day 8 the weather forecasts showed no skill, "
            "so the day is only the season's average."
        )
    return (
        "Range: the lowest and highest of the same hour in the last weeks. A household's week repeats, so "
        "every day ahead is equally (un)certain: holidays, trips or a new appliance are not in the data."
    )


def _page(body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>prosumer: next days</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:1em auto;padding:0 16px}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:2px 6px;text-align:right}}
.bar{{display:inline-block;height:10px;background:#e8a317}} .small{{font-size:85%;color:#555}}
pre{{white-space:pre-wrap}}</style></head><body>{body}</body></html>"""


# ---------------------------------------------------------------------- the web server (standard library)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # the form
        self._send(200, (HERE / "index.html").read_text(encoding="utf-8"))

    def do_POST(self) -> None:  # the form was sent: split it into fields and the file, run the backend
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        head = f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode()
        message = BytesParser(policy=default).parsebytes(head + raw)
        form, csv = {}, b""
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            payload = part.get_payload(decode=True)
            data = payload if isinstance(payload, bytes) else b""
            if name == "csv":
                csv = data
            elif name:
                form[str(name)] = data.decode("utf-8").strip()
        try:
            self._send(200, forecast_page(form, csv))
        except Exception as e:  # show the error on the page: this is a local tool, not a public site
            msg = html.escape(f"{type(e).__name__}: {e}")
            detail = html.escape(traceback.format_exc())
            body = f"<h1>Could not forecast</h1><p>{msg}</p><p><a href='/'>Back</a></p><pre>{detail}</pre>"
            self._send(400, _page(body))

    def _send(self, code: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"Open http://{HOST}:{PORT} (Ctrl+C to stop)")
    HTTPServer((HOST, PORT), Handler).serve_forever()
