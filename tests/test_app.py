"""prosumer.app.run, the app's backend in one call, offline (fake geocoding, weather and ANEEL)."""

from __future__ import annotations

import io
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


def test_a_misspelt_connection_is_a_message_before_any_download() -> None:
    # regression 2026-10-21: "bifasico" crashed `run` with a bare KeyError from the bill
    files = {"consumption": (_consumption_csv("2026-08-01", 61), "conta.csv")}
    price = {"kind": "brazil", "icms": "0,19", "pis_cofins": 0.0925, "connection": "bifasico"}

    def no_download(*a: Any, **k: Any) -> Any:
        raise AssertionError("ANEEL was called")

    svc = app.Services(geocode=None, timezone_at=None, weather=None, tariff_book=no_download)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="connection must be one of"):
        app.run({**SITE, "price": price}, files, services=svc)
    r = app.run(
        {**SITE, "models": "naive", "price": {**price, "connection": "40"}}, files, services=_services()
    )
    assert r.report.economics is not None and "40 kWh" in str(r.pricing)


def test_a_pv_file_dead_through_the_test_days_skips_only_the_forecast_check() -> None:
    # regression 2026-10-21: an inverter dead in the last `test_days` raised "Mean of the actual values is
    # zero" from the metrics and the whole page was lost
    f = pd.read_csv(io.BytesIO(_pv_csv("2024-01-01", 60)))
    f.iloc[-28 * 24 :, 1] = 0.0
    files = {"generation": (f.to_csv(index=False).encode(), "inverter.csv")}
    r = app.run({**SITE, "models": "naive"}, files, services=_services())
    assert r.report.forecast is None and r.report.diagnostics is not None
    assert any(
        n.startswith("Forecast check skipped: every test hour it would score is zero") for n in r.report.notes
    )
    f.loc[f.index[pd.to_datetime(f["time"]).dt.hour == 12][-1], "Energy (kWh)"] = 0.5  # one hour is enough
    files = {"generation": (f.to_csv(index=False).encode(), "inverter.csv")}
    assert app.run({**SITE, "models": "naive"}, files, services=_services()).report.forecast is not None


def test_blank_price_fields_are_not_given_and_gd_without_pv_is_ignored() -> None:
    # regressions 2026-10-21: a web form sends every box, blank ones as "": `currency: ""` became the
    # currency and `scheme: ""` an error; and `gd` with a consumption file only was an "Unknown price field"
    files = {"consumption": (_consumption_csv("2026-07-01", 61), "conta.csv")}
    flat = {"kind": "flat", "price": "0,8", "currency": "", "scheme": " ", "export_price": "", "fixed": None}
    r = app.run({**SITE, "models": "naive", "price": flat}, files, services=_services())
    assert r.report.economics is not None and r.report.economics.currency == "EUR"
    price = {"kind": "brazil", "icms": 0.19, "pis_cofins": 0.0925, "gd": "GD II", "peak_start": ""}
    r = app.run({**SITE, "models": "naive", "price": price}, files, services=_services())
    assert r.report.economics is not None and "no GD class" in str(r.pricing)


def test_failed_downloads_are_messages_for_the_person() -> None:
    def offline(*a: Any, **k: Any) -> Any:
        raise OSError("no route to host")

    files = {"generation": (_pv_csv("2024-01-01", 30), "inverter.csv")}
    base = _services()
    cases = [
        ({"address": "Curitiba"}, {"geocode": offline}, "Could not look the address up"),
        (SITE | {"timezone": None}, {"timezone_at": offline}, "Could not find the site's time zone"),
        (SITE, {"weather": offline}, "Could not download the weather forecast from Open-Meteo"),
    ]
    for request, broken, message in cases:
        svc = app.Services(**{**base.__dict__, **broken})
        with pytest.raises(ValueError, match=message):
            app.run(request, files, services=svc)


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


def test_forecast_check_runs_lightgbm_by_default_and_the_naive_rules_on_request() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    files = {"consumption": (_consumption_csv("2024-01-01", 60), "m.csv")}
    r = app.run(SITE, files, services=_services())
    assert r.report.forecast is not None and "LightGBM" in set(r.report.forecast["forecast"])
    assert any("LightGBM" in line for line in r.log)
    naive = app.run({**SITE, "models": "naive"}, files, services=_services())
    assert naive.report.forecast is not None and "LightGBM" not in set(naive.report.forecast["forecast"])
    assert any("naive forecasts only" in n for n in naive.report.notes)
    with pytest.raises(ValueError, match="models must be one of"):
        app.run({**SITE, "models": "best"}, files, services=_services())


def test_a_model_that_is_not_installed_is_left_out_with_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "find_spec", lambda name: None)
    notes: list[str] = []
    assert app._models("all", notes) == []
    assert len(notes) == 5 and "LightGBM is not installed" in notes[0]


def test_charts_carry_what_the_pages_plot() -> None:
    files = {
        "generation": (_pv_csv("2024-01-01", 60), "inverter.csv"),
        "consumption": (_consumption_csv("2024-01-01", 60), "meter.csv"),
    }
    r = app.run({**SITE, "days": 3, "models": "naive"}, files, services=_services())
    assert set(r.charts) == {"history_generation", "history_consumption", "check", "performance"}
    h = r.charts["history_consumption"]
    assert len(h) == 60 and (h["measured_hours"] == 24).all()
    assert h["energy"].between(24 * 0.3 + 3, 24 * 0.4 + 3).all()  # ~0.35 kWh/h plus 1 kWh at 18-20 h
    check = r.charts["check"]
    assert {"y", "evaluated", "median", "clear_sky_persistence"} <= set(check.columns)
    assert check["ds"].min() >= pd.Timestamp(r.report.summary["test_start"], tz=TZ)
    assert not r.charts["performance"].empty
    d = json.loads(r.to_json())
    assert len(d["charts"]["check"]) == len(check) and d["charts"]["history_generation"][0]["date"]


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
