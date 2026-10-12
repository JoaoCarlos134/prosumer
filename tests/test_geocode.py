"""Geocoding without the network: fake answers in each service's format."""

from __future__ import annotations

from typing import Any

import pytest

from prosumer.io import geocode as g
from prosumer.provenance import of


def _nominatim(url: str, params: dict[str, Any]) -> Any:
    assert url == g.NOMINATIM_URL and params["format"] == "jsonv2"
    return [
        {
            "display_name": "Strand Street, Dingle, County Kerry, Ireland",
            "lat": "52.1392961",
            "lon": "-10.2766109",
            "address": {"county": "County Kerry", "state": "Munster", "country": "Ireland"},
        }
    ]


def _open_meteo(url: str, params: dict[str, Any]) -> Any:
    assert url == g.OPEN_METEO_URL
    return {
        "results": [
            {"name": "Dingle", "latitude": 10.9995, "longitude": 122.6711, "country": "Philippines"},
            {
                "name": "Dingle",
                "latitude": 52.14,
                "longitude": -10.27,
                "country": "Ireland",
                "admin1": "Munster",
                "timezone": "Europe/Dublin",
            },
        ]
    }


def test_nominatim_address() -> None:
    c = g.geocode("Strand Street, Dingle", get=_nominatim)
    assert list(c.columns) == g.COLUMNS
    assert c.loc[0, "latitude"] == pytest.approx(52.1392961)
    assert c.loc[0, "region"] == "Munster" and c.loc[0, "country"] == "Ireland"
    p = of(c)
    assert p is not None and p.license == "ODbL-1.0"


def test_open_meteo_returns_every_candidate_for_the_person_to_pick() -> None:
    c = g.geocode("Dingle", provider="open-meteo", get=_open_meteo)
    assert list(c["country"]) == ["Philippines", "Ireland"]  # the first match is not always the right one
    assert c.loc[1, "timezone"] == "Europe/Dublin"
    assert g.geocode("Dingle", provider="open-meteo", limit=1, get=_open_meteo).shape[0] == 1


def test_nothing_found_and_bad_input() -> None:
    assert g.geocode("nowhere", get=lambda u, p: []).empty
    assert g.geocode("nowhere", provider="open-meteo", get=lambda u, p: {}).empty
    with pytest.raises(ValueError):
        g.geocode("  ")
    with pytest.raises(ValueError):
        g.geocode("x", provider="google", get=_nominatim)  # type: ignore[arg-type]


def test_round_site_and_timezone() -> None:
    assert g.round_site(52.1392961, -10.2766109) == (52.14, -10.28)
    with pytest.raises(ValueError):
        g.round_site(95, 0)
    assert g.timezone_at(52.14, -10.28, get=lambda u, p: {"timezone": "Europe/Dublin"}) == "Europe/Dublin"
    with pytest.raises(RuntimeError):
        g.timezone_at(0, 0, get=lambda u, p: {})
