"""prosumer.app.run, the app's backend in one call, offline (fake geocoding, weather and ANEEL)."""

from __future__ import annotations

import json
from functools import partial
from typing import Any

import numpy as np
import pandas as pd
import pytest

from aneel_fake import from_fixture
from prosumer import app, data, physics
from prosumer.economics import brazil
from prosumer.provenance import Provenance, attach

TZ = "America/Sao_Paulo"
SITE = {"latitude": -25.43, "longitude": -49.27, "timezone": TZ}


def _consumption_csv(start: str, days: int) -> bytes:
    """A Brazilian meter export: day-first dates, `;` and decimal comma; ~0.35 kWh/h, ~1.35 at 18-20 h."""
    idx = pd.date_range(start, periods=days * 24, freq="h")
    noise = np.random.default_rng(1).uniform(0.0, 0.1, len(idx))  # an exact repeat skips the forecast check
    y = np.round(0.3 + noise + np.where((idx.hour >= 18) & (idx.hour < 21), 1.0, 0.0), 3)
    text = pd.DataFrame({"data": idx.strftime("%d/%m/%Y %H:%M"), "consumo (kWh)": y}).to_csv(
        index=False, sep=";", decimal=","
    )
    return text.encode("utf-8")


def _pv_csv(start: str, days: int) -> bytes:
    pv, _ = data.example_plant(n_series=1, days=days, start=start, tz=TZ)
    f = pv.frame
    text = pd.DataFrame({"time": f["ds"].dt.strftime("%Y-%m-%d %H:%M"), "Energy (kWh)": f["y"]}).to_csv(
        index=False
    )
    return text.encode("utf-8")


def _weather(first_day: str) -> Any:
    """A fake `open_meteo.fetch_forecast`: two models, the clear sky x 0.7, from `first_day` on."""

    def fetch(lat: float, lon: float, *, days: int, tz: str) -> pd.DataFrame:
        ds = pd.date_range(pd.Timestamp(first_day, tz=tz), periods=days * 24, freq="h")
        ghi = physics.clear_sky_ghi(ds, lat, lon) * 0.7
        parts = [pd.DataFrame({"model": m, "ds": ds, "ghi": ghi, "temperature": 20.0}) for m in ("a", "b")]
        w = pd.concat(parts, ignore_index=True)
        w.attrs["issued"] = (pd.Timestamp(first_day, tz=tz) - pd.Timedelta(hours=3)).isoformat()
        return attach(w, Provenance(source="fake weather", license="CC-BY-4.0"))

    return fetch


def _services(first_day: str = "2024-03-01") -> app.Services:
    def no_network(*a: Any, **k: Any) -> Any:
        raise AssertionError("the network was called")

    return app.Services(
        geocode=no_network,
        timezone_at=no_network,
        weather=_weather(first_day),
        tariff_book=partial(brazil.TariffBook.from_aneel, get=from_fixture()),
    )


def test_consumption_only() -> None:
    files = {"consumption": (_consumption_csv("2024-01-01", 42), "medidor.csv")}
    r = app.run({**SITE, "days": "7", "load_hours": "2"}, files, services=_services())
    assert set(r.outlooks) == {"consumption"} and len(r.outlooks["consumption"].daily) == 7
    assert r.read["consumption"]["file"] == "medidor.csv" and "consumo (kWh)" in r.read["consumption"]["how"]
    assert (r.windows["start"].dt.hour != 18).all()  # never in the evening peak
    assert r.report.forecast is not None and r.windows_by_cost is None
    d = json.loads(r.to_json())  # strict JSON: no NaN anywhere
    assert d["site"]["timezone"] == TZ and d["outlooks"]["consumption"]["daily"]
    assert d["report"]["forecast"] and d["windows"]


def test_pv_and_consumption_with_a_price_give_the_bill_and_the_savings() -> None:
    files = {
        "generation": (_pv_csv("2024-01-01", 60), "inverter.csv"),
        "consumption": (_consumption_csv("2024-01-01", 60), "meter.csv"),
    }
    price = {"kind": "flat", "price": "0,80", "export_price": 0.1, "currency": "BRL", "scheme": "net_billing"}
    r = app.run({**SITE, "price": price, "days": 3}, files, services=_services())
    assert set(r.outlooks) == {"generation", "consumption"}
    econ = r.report.economics
    assert econ is not None and (econ.totals["savings"] > 0).all()
    assert r.windows_by_cost is not None and len(r.windows_by_cost) >= 1
    assert any(c.source == "fake weather" for c in r.credits)
    assert r.outlooks["generation"].daily["source"].eq("weather").all()
    json.loads(r.to_json())


def test_brazilian_price_from_aneel() -> None:
    files = {"consumption": (_consumption_csv("2026-08-01", 61), "conta.csv")}
    price = {"kind": "brazil", "distributor": "COPEL-DIS", "icms": "0,19", "pis_cofins": 0.0925}
    r = app.run({**SITE, "price": price}, files, services=_services())
    econ = r.report.economics
    assert econ is not None and econ.currency == "BRL" and len(econ.monthly) == 2
    assert r.pricing is not None and "COPEL-DIS" in r.pricing
    assert any("ANEEL" in c.source for c in r.credits)
    with pytest.raises(ValueError, match="fractions"):
        app.run({**SITE, "price": {**price, "icms": 19}}, files, services=_services())


def test_address_is_geocoded_and_rounded() -> None:
    def geocode(query: str, limit: int = 5) -> pd.DataFrame:
        found = pd.DataFrame(
            {"name": ["Curitiba, Parana, Brazil"], "latitude": [-25.4284], "longitude": [-49.2733]}
        )
        return attach(found, Provenance(source="fake geocoder", license="ODbL-1.0"))

    svc = app.Services(
        geocode=geocode,
        timezone_at=lambda lat, lon: TZ,
        weather=_weather("2024-03-01"),
        tariff_book=_services().tariff_book,
    )
    files = {"consumption": (_consumption_csv("2024-01-01", 42), "m.csv")}
    r = app.run({"address": "Curitiba"}, files, services=svc)
    assert r.site == {
        "latitude": -25.43,
        "longitude": -49.27,
        "timezone": TZ,
        "address_found": "Curitiba, Parana, Brazil",
    }
    assert any(c.source == "fake geocoder" for c in r.credits)


def test_requests_that_cannot_run_say_why() -> None:
    files = {"consumption": (_consumption_csv("2024-01-01", 42), "m.csv")}
    svc = _services()
    with pytest.raises(ValueError, match="No file was received"):
        app.run(SITE, {"consumption": (b"", "m.csv")}, services=svc)
    with pytest.raises(ValueError, match="Unknown request fields"):
        app.run({**SITE, "dayz": 3}, files, services=svc)
    with pytest.raises(ValueError, match="both the latitude and the longitude"):
        app.run({"latitude": 1.0}, files, services=svc)
    with pytest.raises(ValueError, match=r"price\.kind"):
        app.run({**SITE, "price": {"kind": "free"}}, files, services=svc)
    with pytest.raises(ValueError, match="Unknown price fields"):
        app.run({**SITE, "price": {"kind": "flat", "price": 0.8, "colour": "red"}}, files, services=svc)
    with pytest.raises(ValueError, match="keyed by"):
        app.run(SITE, {"pv": files["consumption"]}, services=svc)
    with pytest.raises(ValueError, match="Peak hours"):
        app.run(
            {**SITE, "price": {"kind": "tou", "peak_hours": "25-3", "peak_price": 1, "offpeak_price": 0.5}},
            files,
            services=svc,
        )
