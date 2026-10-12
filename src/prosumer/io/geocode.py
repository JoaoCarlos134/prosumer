"""From an address or place name to coordinates, and the rounding that keeps a home private.

Two free services, no key, standard library only:

- `"nominatim"` (OpenStreetMap, the default): understands street addresses ("Strand Street, Dingle, Ireland").
  Its usage policy (https://operations.osmfoundation.org/policies/nominatim/, read 2026-10-12) asks for a
  `User-Agent` that identifies the application, at most one request a second, no bulk geocoding, and the
  attribution "Data (c) OpenStreetMap contributors, ODbL 1.0".
- `"open-meteo"` (GeoNames): place names and postal codes only. Checked on 2026-10-12: "Dingle" came back
  first as a town in the Philippines and a street address returned nothing, so always show the candidates
  (name, region, country) and let the person pick.

The query itself is sent to the service. `round_site` cuts the coordinates to 2 decimals (~1 km), which is
plenty for a weather forecast and the sun's position and does not point at one house: round before sending
the site anywhere else (the project's own rule for its plants).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import pandas as pd

from ..provenance import Provenance, attach, today

Provider = Literal["nominatim", "open-meteo"]
Getter = Callable[[str, dict[str, Any]], Any]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEZONE_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "prosumer (https://github.com/JoaoCarlos134/prosumer)"
COLUMNS = ["name", "latitude", "longitude", "region", "country", "timezone", "source"]


def geocode(
    query: str,
    *,
    provider: Provider = "nominatim",
    limit: int = 5,
    language: str = "en",
    user_agent: str = USER_AGENT,
    get: Getter | None = None,
) -> pd.DataFrame:
    """Candidate places for `query`, best first: `name, latitude, longitude, region, country, timezone,
    source`.

    `timezone` comes only from Open-Meteo (None from Nominatim). An empty frame means nothing matched.
    `get(url, params)` returns the decoded JSON; tests pass a fake one. The frame carries its provenance
    (`prosumer.provenance.of`).
    """
    if not query.strip():
        raise ValueError("Empty query")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if provider == "nominatim":
        params: dict[str, Any] = {"q": query, "format": "jsonv2", "limit": limit, "addressdetails": 1}
        params["accept-language"] = language
        raw = (get or _getter(user_agent))(NOMINATIM_URL, params)
        rows = [_nominatim(r) for r in raw or []]
        prov = Provenance(
            source="Nominatim (OpenStreetMap) geocoding",
            license="ODbL-1.0",
            citation="Data (c) OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright",
            url="https://nominatim.org/",
            retrieved=today(),
            notes="usage policy: identify the application, at most 1 request/s, no bulk geocoding",
        )
    elif provider == "open-meteo":
        params = {"name": query, "count": limit, "language": language, "format": "json"}
        raw = (get or _getter(user_agent))(OPEN_METEO_URL, params)
        rows = [_open_meteo(r) for r in (raw or {}).get("results", [])]
        prov = Provenance(
            source="Open-Meteo Geocoding API (GeoNames)",
            license="CC-BY-4.0",
            citation="Geocoding by Open-Meteo.com, data from GeoNames (CC BY 4.0)",
            url="https://open-meteo.com/en/docs/geocoding-api",
            retrieved=today(),
            notes="free API: non-commercial use only (https://open-meteo.com/en/terms)",
        )
    else:
        raise ValueError(f"provider must be 'nominatim' or 'open-meteo', not {provider!r}")
    out = pd.DataFrame(rows, columns=COLUMNS).head(limit)
    return attach(out, prov)


def round_site(lat: float, lon: float, decimals: int = 2) -> tuple[float, float]:
    """(lat, lon) rounded to `decimals` places (2 = ~1 km): enough for the weather and the sun, not a "
    "house."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Not a site: latitude {lat}, longitude {lon}")
    return round(float(lat), decimals), round(float(lon), decimals)


def timezone_at(lat: float, lon: float, *, get: Getter | None = None) -> str:
    """IANA time zone of a site (e.g. "America/Sao_Paulo"), asked of the Open-Meteo forecast API with
    `timezone=auto` (Nominatim gives none). Needed to read a meter file whose times are local wall-clock
    times."""
    params = {"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1, "daily": "sunrise"}
    raw = (get or _getter(USER_AGENT))(TIMEZONE_URL, params)
    tz = (raw or {}).get("timezone")
    if not tz:
        raise RuntimeError(f"No time zone returned for ({lat}, {lon})")
    return str(tz)


def _nominatim(r: dict[str, Any]) -> dict[str, Any]:
    a = r.get("address") or {}
    region = a.get("state") or a.get("county") or a.get("region")
    return {
        "name": r.get("display_name") or r.get("name"),
        "latitude": float(r["lat"]),
        "longitude": float(r["lon"]),
        "region": region,
        "country": a.get("country"),
        "timezone": None,
        "source": "nominatim",
    }


def _open_meteo(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": r.get("name"),
        "latitude": float(r["latitude"]),
        "longitude": float(r["longitude"]),
        "region": r.get("admin1"),
        "country": r.get("country"),
        "timezone": r.get("timezone"),
        "source": "open-meteo",
    }


def _getter(user_agent: str) -> Getter:  # pragma: no cover - network
    import json
    import urllib.parse

    from . import _http

    def get(url: str, params: dict[str, Any]) -> Any:
        body = _http.get_bytes(
            url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": user_agent}, timeout=60
        )
        return json.loads(body)

    return get


__all__ = ["COLUMNS", "NOMINATIM_URL", "OPEN_METEO_URL", "USER_AGENT", "geocode", "round_site", "timezone_at"]
