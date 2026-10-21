"""The example site (examples/site_local/app.py), a thin shell over `prosumer.app.run`, without the network:
what the shell does itself (the form as a request, the page) is tested here; `run` has its own tests
(`test_app`, `test_i18n`). Consumption with the coordinates and the time zone typed needs neither geocoding
nor a weather forecast; a Brazilian tariff comes from a fake ANEEL with the fixture of 2026-10-12."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from aneel_fake import from_fixture

APP = Path(__file__).resolve().parents[1] / "examples" / "site_local" / "app.py"
GROSS = 1 / (1 - 0.19 - 0.0925)


def _app():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("site_app", APP)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _csv(start: str, days: int) -> bytes:
    """A Brazilian meter export: day-first dates, `;` and decimal comma; 0.3 kWh an hour, 1.3 at 18-20 h."""
    idx = pd.date_range(start, periods=days * 24, freq="h")
    y = 0.3 + np.where((idx.hour >= 18) & (idx.hour < 21), 1.0, 0.0)
    text = pd.DataFrame({"data": idx.strftime("%d/%m/%Y %H:%M"), "consumo": y}).to_csv(
        index=False, sep=";", decimal=","
    )
    return text.encode("utf-8")


FORM = {
    "quantity": "consumption",
    "latitude": "-25.43",
    "longitude": "-49.27",
    "timezone": "America/Sao_Paulo",
    "days": "7",
    "load_hours": "2",
    "models": "naive",  # the page's test, not the forecast check's: the fastest models
}


def _section(page: str, title: str) -> str:
    return page.split(title)[1].split("</table>")[0]


def test_energy_column_is_chosen_by_name_and_unit_not_position() -> None:
    # regression (2026-10-16): the page took "column 2 = energy"; on a real Solar.web export column 2 is
    # the AC current, and the forecast came out ~30x too large without any error
    idx = pd.date_range("2024-01-01", periods=42 * 24, freq="h")
    y = 0.3 + np.where((idx.hour >= 18) & (idx.hour < 21), 1.0, 0.0)
    text = pd.DataFrame(
        {"data": idx.strftime("%d/%m/%Y %H:%M"), "Tensao (V)": 220.0, "Consumo (kWh)": y}
    ).to_csv(index=False, sep=";", decimal=",")
    page = _app().forecast_page(FORM, text.encode("utf-8"), "medidor.csv")
    assert "Consumo (kWh)" in page and "the only one with an energy unit" in page
    day = _section(page, "<h2>Per day</h2>")
    totals = [float(r.split("</td><td>")[2]) for r in day.split("<tr><td>")[1:]]
    assert totals and all(abs(t - (21 * 0.3 + 3 * 1.3)) < 0.01 for t in totals)


def test_empty_upload_says_so() -> None:
    with pytest.raises(ValueError, match="No file was received"):
        _app().forecast_page(FORM, b"")


def test_consumption_page_from_a_brazilian_csv() -> None:
    page = _app().forecast_page(FORM, _csv("2024-01-01", 6 * 7))
    assert "Forecast of your consumption" in page
    assert page.count("typical week") >= 14  # 7 days in the table and 7 in the best windows
    assert "18:00" not in _section(page, "Best 2 hours")  # never in the evening peak
    assert "by expected cost" not in page  # no price given: energy only


def test_flat_price_adds_the_cheapest_hours_and_the_monthly_bill() -> None:
    """A 2 kW load for 2 h at 0.30 a kWh costs 1.20 whenever it runs (no PV). January 2024 is the only
    complete month: 31 x (24 x 0.3 + 3 x 1.0) kWh x 0.30 = 94.86."""
    form = FORM | {"price": "flat", "flat_price": "0.30", "load_kw": "2", "currency": "EUR"}
    page = _app().forecast_page(form, _csv("2024-01-01", 6 * 7))
    cheap = _section(page, "Cheapest 2 hours of each day for a 2 kW load")
    assert cheap.count("<td>1.20</td>") == 7 and cheap.count("typical week") == 7
    assert "Expected monthly bill: <b>94.86 EUR</b> (mean of the 1 complete month(s)" in page
    assert "<td>2024-02</td>" in page  # the partial month is listed, not averaged
    assert "Price: flat" in page


def test_time_of_use_price_keeps_the_load_out_of_the_peak() -> None:
    form = FORM | {
        "price": "tou",
        "peak_price": "0.50",
        "offpeak_price": "0.20",
        "peak_hours": "17-21",
        "load_kw": "1",
    }
    page = _app().forecast_page(form, _csv("2024-01-01", 6 * 7))
    cheap = _section(page, "Cheapest 2 hours")
    assert cheap.count("<td>0.40</td>") == 7  # 2 h x 1 kW at the off-peak price
    assert "peak 17:00-21:00 on weekdays" in page


def test_load_power_accepts_a_decimal_comma() -> None:
    form = FORM | {"price": "flat", "flat_price": "0,30", "load_kw": "1,5"}
    page = _app().forecast_page(form, _csv("2024-01-01", 42))
    cheap = _section(page, "Cheapest 2 hours of each day for a 1.5 kW load")
    assert cheap.count("<td>0.90</td>") == 7


def test_brazilian_tariff_from_aneel_with_typed_taxes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Copel conventional (TUSD 457.17 + TE 310.85 R$/MWh from 24/6/2026), ICMS 19% and PIS/COFINS 9.25%
    typed: in October 2026 (green flag) a 2 h x 2 kW load costs 4 x 0.76802 / 0.7175 R$."""
    app = _app()
    monkeypatch.setattr(app, "ANEEL_GET", from_fixture())
    form = FORM | {"price": "brazil", "distributor": "COPEL-DIS", "icms": "19", "pis_cofins": "9,25"}
    page = app.forecast_page(form, _csv("2026-07-01", 92))
    cheap = _section(page, "Cheapest 2 hours")
    assert cheap.count(f"<td>{4 * (457.17 + 310.85) / 1000 * GROSS:.2f}</td>") == 7
    assert "Expected monthly bill: <b>" in page and "BRL" in page
    assert "ODbL-1.0" in page and "Agência Nacional de Energia Elétrica" in page  # ANEEL attribution
    assert "ICMS 19.00%" in page  # the typed rates are named as the person's input
    assert "COSIP" in page  # not included unless typed


def test_the_form_becomes_the_request_of_app_run() -> None:
    """Only the fields of the price's kind are sent, taxes typed in % become fractions, blank boxes stay
    blank for `app.run` to ignore (a web form sends every box)."""
    site = _app()
    form = FORM | {"price": "brazil", "icms": "19", "pis_cofins": "9,25", "flat_price": "", "gd": "GD II"}
    form |= {"currency": "", "distributor": "CEMIG-D", "cosip": ""}
    request = site._request(form)
    assert request["price"] == {
        "kind": "brazil",
        "distributor": "CEMIG-D",
        "gd": "GD II",
        "cosip": "",
        "icms": pytest.approx(0.19),
        "pis_cofins": pytest.approx(0.0925),
    }
    assert "quantity" not in request and request["days"] == "7"
    assert "price" not in site._request(FORM | {"price": "none", "flat_price": "0.3"})
    tou = site._request(FORM | {"price": "tou", "peak_hours": "22-6", "flat_price": "0.3", "icms": "19"})
    assert tou["price"] == {"kind": "tou", "peak_hours": "22-6"}
    # regression 2026-10-21: the box asks for %, the messages said "a fraction" (app.run's own words)
    for icms, said in (("", "Give the ICMS rate of your bill, in %"), ("19%", "not a number (type it in %"),
                       ("120", "is in %, between 0 and 100")):  # fmt: skip
        with pytest.raises(ValueError, match=re.escape(said)):
            site._request(FORM | {"price": "brazil", "icms": icms, "pis_cofins": "9.25"})


def test_a_bill_that_cannot_be_made_says_why_not_upload_the_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression 2026-10-21: with the consumption sent, a bill that failed (no tariff in force on the data's
    first months: the fixture has Copel's vigencia from 24/6/2026 only) told the person to upload it."""
    site = _app()
    monkeypatch.setattr(site, "ANEEL_GET", from_fixture())
    form = FORM | {"price": "brazil", "icms": "19", "pis_cofins": "9.25", "gd": "GD II"}
    page = site.forecast_page(form, _csv("2026-01-01", 273))
    assert "upload it" not in page
    assert "No bill for your data. Economics left out:" in page and "tariff in force on" in page


def test_brazilian_tariff_needs_the_taxes_and_says_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    monkeypatch.setattr(app, "ANEEL_GET", from_fixture())
    with pytest.raises(ValueError, match="ICMS"):
        app.forecast_page(FORM | {"price": "brazil", "pis_cofins": "9.25"}, _csv("2026-07-01", 92))

    def offline(url: str, params: dict[str, Any]) -> dict[str, Any]:
        raise OSError("no network")

    monkeypatch.setattr(app, "ANEEL_GET", offline)
    form = FORM | {"price": "brazil", "icms": "19", "pis_cofins": "9.25"}
    with pytest.raises(ValueError, match="Could not download COPEL-DIS's tariffs"):
        app.forecast_page(form, _csv("2026-07-01", 92))
