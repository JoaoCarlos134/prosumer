"""The example site's backend (examples/site_local/app.py), without the network: consumption with the
coordinates and the time zone typed needs neither geocoding nor a weather forecast; a Brazilian tariff comes
from a fake ANEEL that answers with the fixture of 2026-10-12."""

from __future__ import annotations

import importlib.util
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
}


def _section(page: str, title: str) -> str:
    return page.split(title)[1].split("</table>")[0]


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
    assert "your flat price" in page


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


def test_gd_ii_pv_page_in_march_gets_its_fio_b(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review F1: a production outlook in March 2027. Copel's Fio B of 2026 starts on 24/6/2026, the 2027
    file is not published (the fixture has 2026 only): steps 6 and 7's price must still be built, from the
    previous year's file, with notes for what was assumed."""
    from prosumer import Outlook, economics

    app = _app()
    monkeypatch.setattr(app, "ANEEL_GET", from_fixture())
    ds = pd.date_range("2027-03-08", periods=3 * 24, freq="h", tz="America/Sao_Paulo")
    sun = np.where(np.isin(ds.hour, [10, 11, 12]), 3.0, 0.0)
    out = Outlook(
        hourly=pd.DataFrame({"unique_id": "mine", "ds": ds, "y_hat": sun}),
        daily=pd.DataFrame(
            {"unique_id": "mine", "date": pd.date_range("2027-03-08", periods=3), "confidence": "high"}
        ),
        quantity="generation",
    )
    form = {"price": "brazil", "icms": "19", "pis_cofins": "9.25", "gd": "GD II"}
    pricing = app._pricing(form, out, [])
    assert any("2027" in n for n in pricing.book.notes)  # the 2027 components file is missing: a note
    w = economics.windows_by_cost(pricing, generation=out, hours=3, kw=2.0, top=1)
    assert len(w) == 3 and (w["start"].dt.hour == 10).all()
    assert any("No bandeira published for 2027-03" in n for n in w.attrs["notes"])


def test_form_numbers_take_a_decimal_comma_and_peak_hours_are_checked() -> None:
    """Review F4."""
    app = _app()
    out = type("O", (), {"quantity": "consumption"})()
    flat = app._pricing(
        {"price": "flat", "flat_price": "0,30", "export_price": "0,05", "fixed": "7,5"}, out, []
    )
    assert flat.tariff.export_price == pytest.approx(0.05) and flat.tariff.fixed == pytest.approx(7.5)
    tou = {"price": "tou", "peak_price": "0.5", "offpeak_price": "0.2"}
    for bad in ("17:30-20:30", "18-18", "evening"):
        with pytest.raises(ValueError, match="whole hours"):
            app._pricing(tou | {"peak_hours": bad}, out, [])
    night = app._pricing(tou | {"peak_hours": "22-6"}, out, [])  # wraps past midnight
    assert night.tariff.weekday[23] == "peak" and night.tariff.weekday[6] == "off_peak"
    with pytest.raises(ValueError, match="not a number"):
        app._pricing({"price": "flat", "flat_price": "0.3", "fixed": "five"}, out, [])


def test_brazilian_tariff_needs_the_taxes_and_says_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    monkeypatch.setattr(app, "ANEEL_GET", from_fixture())
    with pytest.raises(ValueError, match="ICMS"):
        app.forecast_page(FORM | {"price": "brazil", "pis_cofins": "9.25"}, _csv("2026-07-01", 92))

    def offline(url: str, params: dict[str, Any]) -> dict[str, Any]:
        raise OSError("no network")

    monkeypatch.setattr(app, "ANEEL_GET", offline)
    form = FORM | {"price": "brazil", "icms": "19", "pis_cofins": "9.25"}
    with pytest.raises(ValueError, match="Could not download Copel"):
        app.forecast_page(form, _csv("2026-07-01", 92))
