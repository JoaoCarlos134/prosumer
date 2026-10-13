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
