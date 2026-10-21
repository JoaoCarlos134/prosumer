"""A deliberately crude local web page for `prosumer`: upload a CSV, say where it is, get the next days.

Run it (from the repository root, with the library installed in the environment):

    python examples/site_local/app.py          # then open http://127.0.0.1:8000

Nothing but the Python standard library and `prosumer`: no web framework, no JavaScript. The backend is one
library call, `prosumer.app.run` (its docstring lists its seven steps: where, read, weather, the next days,
the best hours, the analysis, the charts); this file only turns the form into its request (`_request`) and
its `Result` into HTML (`_render`). The TCC's site does the same in TypeScript.

The price comes from the form: a flat price, a simple time-of-use price, or a Brazilian distributor's tarifa
convencional downloaded from ANEEL's open data with the ICMS and PIS/COFINS the person types (in %, as on the
bill).

Privacy: the file never leaves this machine. Only the address (to Nominatim, if you type one instead of
coordinates), the coordinates rounded to 2 decimals (to Open-Meteo, for the weather) and, for a Brazilian
tariff, the distributor's name (to ANEEL) go out. The free Open-Meteo API is for non-commercial use.
"""

from __future__ import annotations

import html
import traceback
from email.parser import BytesParser
from email.policy import default
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import prosumer
from prosumer import app
from prosumer.economics import brazil
from prosumer.provenance import Provenance

HERE = Path(__file__).resolve().parent
HOST, PORT = "127.0.0.1", 8000
ANEEL_GET = None  # the HTTP getter of io.aneel (None: the live API); the tests put a fake ANEEL here
# the form's fields that `app.run` takes as they are (the price fields depend on the kind of price)
PLAIN = (
    "address", "latitude", "longitude", "timezone", "file_times", "time_column", "value_column", "unit",
    "kind", "days", "tilt", "azimuth", "kwp", "load_hours", "load_kw", "models",
)  # fmt: skip
PRICE_FIELDS = {
    "flat": {"flat_price": "price", "export_price": "export_price", "fixed": "fixed", "currency": "currency",
             "scheme": "scheme"},
    "tou": {"peak_hours": "peak_hours", "peak_price": "peak_price", "offpeak_price": "offpeak_price",
            "export_price": "export_price", "fixed": "fixed", "currency": "currency", "scheme": "scheme"},
    "brazil": {"distributor": "distributor", "connection": "connection", "gd": "gd", "cosip": "cosip"},
}  # fmt: skip


# ---------------------------------------------------------------------- the backend: one library call
def forecast_page(form: dict[str, str], csv: bytes, filename: str = "data.csv") -> str:
    """Form fields + file bytes -> the result page (HTML)."""
    quantity = form.get("quantity") or "generation"
    services = app.Services(tariff_book=partial(brazil.TariffBook.from_aneel, get=ANEEL_GET))
    request = app.Request.from_dict(_request(form))  # its errors are messages for the person
    result = app.run(request, {quantity: (csv, filename)}, services=services)
    return _render(result, request)


def _request(form: dict[str, str]) -> dict[str, Any]:
    """The form as `app.run`'s request: blank boxes are "not given" there; the price keeps only the fields
    of its kind, and the Brazilian taxes typed in % become the fractions the library takes."""
    request: dict[str, Any] = {k: form[k] for k in PLAIN if k in form}
    kind = form.get("price") or "none"
    if kind == "none":
        return request
    price: dict[str, Any] = {"kind": kind}
    price |= {new: form[old] for old, new in PRICE_FIELDS.get(kind, {}).items() if old in form}
    if kind == "brazil":
        price |= {k: _percent(form.get(k, "")) for k in ("icms", "pis_cofins")}
    request["price"] = price
    return request


def _percent(text: str) -> float | str:
    """'19' or '9,25' (%) -> 0.19, 0.0925; anything else as it is, for `app.run` to say what is wrong."""
    try:
        return float(text.strip().replace(",", ".")) / 100
    except ValueError:
        return text


# ---------------------------------------------------------------------- HTML (plain tables, no script)
def _render(r: app.Result, request: app.Request) -> str:
    out = next(iter(r.outlooks.values()))
    hours = request.load_hours
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
        for _, w in r.windows.iterrows()
    )
    hourly = out.hourly.assign(ds=out.hourly["ds"].dt.strftime("%Y-%m-%d %H:%M"))
    hourly = hourly[["ds", "lead_day", "y_hat", "low", "high", "source", "n_models"]].round(3)
    what = "production" if out.quantity == "generation" else "consumption"
    pick = "most production" if out.quantity == "generation" else "least consumption"
    method = html.escape(str(out.method.get("series", out.method)))
    notes = [*out.notes, *r.notes]
    return _page(
        f"""
<h1>Forecast of your {what}, kWh</h1>
<p><a href="/">New forecast</a></p>
<h2>What was read and learnt</h2>
<ul>{"".join(f"<li>{html.escape(line)}</li>" for line in r.log)}</ul>
{_learnt(out)}
<h2>Per day</h2>
<table><tr><th>Day</th><th>Lead</th><th>Total</th><th>Range</th><th>Confidence</th><th></th></tr>
{"".join(rows)}</table>
<p class=small>{_range_note(out.quantity)}</p>
<h2>Best {hours} hours of each day for a heavy load ({pick})</h2>
<table><tr><th>Day</th><th>Hours</th><th>kWh in the block</th><th>Confidence</th></tr>{best}</table>
{_money(r, hours, request.load_kw)}
<h2>Notes</h2><ul>{"".join(f"<li>{html.escape(n)}</li>" for n in notes)}</ul>
<h2>Analysis of your data</h2>
{_markdown(r.report.to_markdown())}
<details><summary>Every number the forecast used</summary><pre>{method}</pre></details>
<h2>Data sources</h2><ul>{"".join(f"<li>{t}</li>" for t in dict.fromkeys(map(_credit, r.credits)))}</ul>
<details><summary>Every hour</summary>{hourly.to_html(index=False)}</details>
"""
    )


def _money(r: app.Result, hours: int, kw: float) -> str:
    """The cheapest block of each day by cost (next to the best one by energy) and the monthly bill."""
    if r.windows_by_cost is None:
        return ""
    w = r.windows_by_cost
    cur = html.escape(str(w["currency"].iloc[0])) if len(w) else ""
    cheap = "".join(
        f"<tr><td>{x['date']:%a %d %b %Y}</td><td>{x['start']:%H:%M} - {x['end']:%H:%M}</td>"
        f"<td>{x['cost']:.2f}</td><td>{x['grid_kwh']:.1f}</td><td>{x['pv_kwh']:.1f}</td>"
        f"<td>{html.escape(str(x['confidence']))}</td></tr>"
        for _, x in w.iterrows()
    )
    parts = [
        f"<h2>Cheapest {hours} hours of each day for a {kw:g} kW load, by expected cost</h2>",
        f"<p class=small>Price: {html.escape(str(r.pricing))}.</p>",
        f"<table><tr><th>Day</th><th>Hours</th><th>Cost, {cur}</th><th>kWh from the grid</th>"
        f"<th>kWh from your PV</th><th>Confidence</th></tr>{cheap}</table>",
    ]
    econ = r.report.economics
    if econ is None:
        parts.append("<p>The monthly bill needs your consumption: upload it to see what you pay.</p>")
        return "\n".join(parts)
    rows = "".join(
        f"<tr><td>{m['month']:%Y-%m}</td><td>{m['consumption']:.0f}</td><td>{m['total']:.2f}</td>"
        f"<td>{m['coverage']:.0%}</td></tr>"
        for _, m in econ.monthly.iterrows()
    )
    t = econ.totals.iloc[0]
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
        f"<ul>{''.join(f'<li>{html.escape(n)}</li>' for n in econ.notes)}</ul>",
    ]
    return "\n".join(parts)


def _learnt(out: prosumer.Outlook) -> str:
    """One readable line per series: the plant the forecast is built on (a wrong file shows up here)."""
    lines = []
    for uid, m in out.method.get("series", {}).items():
        if "kw_eff" in m:
            lines.append(
                f"{html.escape(str(uid))}: panels {m['tilt']:.0f} degrees facing {m['azimuth']:.0f} "
                "(compass, "
                f"{html.escape(str(m['orientation']))}); effective peak power <b>{m['kw_eff']:.2f} kW</b> "
                f"({html.escape(str(m['kw_eff_from']))}). A home system is a few kW: a much larger number "
                "means the file's column was not energy."
            )
    return "".join(f"<p>{t}</p>" for t in lines)


def _markdown(md: str) -> str:
    """The report's Markdown as plain HTML: headings, lists, tables, paragraphs (no library needed)."""
    out: list[str] = []
    table: list[list[str]] = []

    def flush() -> None:
        if table:
            head, *body = [r for r in table if not all(set(c) <= set("-: ") for c in r)]
            out.append("<table><tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr>")
            out.extend("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in body)
            out.append("</table>")
            table.clear()

    for line in md.splitlines():
        s = line.strip()
        if s.startswith("|"):
            table.append([html.escape(c.strip()) for c in s.strip("|").split("|")])
            continue
        flush()
        if s.startswith("#"):
            level = min(len(s) - len(s.lstrip("#")) + 2, 5)
            out.append(f"<h{level}>{html.escape(s.lstrip('#').strip())}</h{level}>")
        elif s.startswith(("- ", "* ")):
            out.append(f"<li>{html.escape(s[2:])}</li>")
        elif s:
            out.append(f"<p>{html.escape(s)}</p>")
    flush()
    return "\n".join(out)


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
        form, csv, filename = {}, b"", "data.csv"
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            payload = part.get_payload(decode=True)
            data = payload if isinstance(payload, bytes) else b""
            if name == "csv":
                csv, filename = data, part.get_filename() or filename
            elif name:
                form[str(name)] = data.decode("utf-8").strip()
        try:
            self._send(200, forecast_page(form, csv, filename))
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
