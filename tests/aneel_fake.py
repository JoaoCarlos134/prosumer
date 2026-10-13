"""A fake ANEEL CKAN datastore for the tests (no network), and one from the live fixture of 2026-10-12."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prosumer.io import aneel

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "aneel_distributors.json"


class FakeCKAN:
    """`datastore_search` with exact-match filters and limit/offset paging; `package_show` for components."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]], package: list[dict[str, str]] | None = None):
        self.tables, self.package, self.calls = tables, package or [], []

    def __call__(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((url, params))
        if url.endswith("package_show"):
            return {"success": True, "result": {"resources": self.package}}
        assert url == aneel.API + "datastore_search"
        rows = self.tables[params["resource_id"]]
        f = json.loads(params.get("filters", "{}"))
        rows = [r for r in rows if all(r.get(k) == v for k, v in f.items())]
        a, n = int(params["offset"]), int(params["limit"])
        return {"success": True, "result": {"records": rows[a : a + n], "total": len(rows)}}


def from_fixture(year: int = 2026) -> FakeCKAN:
    """ANEEL's API as it answered on 2026-10-12 for Copel, Cemig, Enel SP and Light (an ODbL extract): the
    latest B1 residential vigencias, the bandeiras of 2026-05 to 2026-10 and each one's TUSD_FioB of
    `year`."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return FakeCKAN(
        {
            aneel.TARIFFS: data["tariffs"],
            aneel.BANDEIRAS_MONTHLY: data["bandeiras"],
            "comp": data["components"],
        },
        package=[{"name": f"componentes-tarifarias-{year}.csv", "id": "comp"}],
    )
