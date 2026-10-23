"""The site's backend (`server/api.py`, `server/demo.py`): the API over `prosumer.app.run`, with no network.

Run from `webapp/`:  python -m pytest tests
The outside calls are the library's test fakes (`tests/test_app.py` of the library: a fake weather forecast,
the ANEEL fixture); `api.SERVICES` takes them.
"""

from __future__ import annotations

import datetime as dt
import importlib
import io
import json
import socket
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # server/
sys.path.insert(0, str(HERE.parent.parent / "tests"))  # the library's tests: its fakes

from server import api, demo, launch  # noqa: E402

from test_app import SITE, _consumption_csv, _services  # noqa: E402

TODAY = dt.date(2026, 10, 23)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(api, "SERVICES", _services("2026-10-01"))
    return TestClient(api.app)


def _run(client: TestClient, request: dict[str, Any], lang: str = "en", **files: tuple[str, bytes]) -> Any:
    return client.post(
        "/api/run",
        data={"request": json.dumps(request), "lang": lang},
        files={q: (name, data, "text/csv") for q, (name, data) in files.items()},
    )


def test_info_says_what_the_form_offers(client: TestClient) -> None:
    info = client.get("/api/info").json()
    assert info["languages"] == ["en", "pt"]
    assert info["max_days"] >= 7
    assert "lightgbm" in info["models"]["sets"]
    assert "GD II" in info["brazil"]["gd"]
    assert info["demo"]["license"] == "CC0-1.0"


def test_a_consumption_file_runs_and_the_kept_result_comes_back_in_portuguese(client: TestClient) -> None:
    r = _run(
        client,
        {**SITE, "models": "naive", "days": 3},
        consumption=("conta.csv", _consumption_csv("2026-08-01", 61)),
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["lang"] == "en" and not p["meta"]["demo"] and p["meta"]["files"] == {"consumption": "conta.csv"}
    assert set(p["result"]["outlooks"]) == {"consumption"}
    en_log = p["result"]["log"]
    pt = client.get(f"/api/result/{p['id']}", params={"lang": "pt"}).json()
    assert pt["id"] == p["id"] and pt["lang"] == "pt"
    assert pt["result"]["log"] != en_log and any("Consumo" in line for line in pt["result"]["log"])


def test_a_request_the_library_refuses_is_a_400_in_the_persons_language(client: TestClient) -> None:
    files = {"consumption": ("conta.csv", _consumption_csv("2026-08-01", 61))}
    r = _run(client, {**SITE, "days": 99}, "pt", **files)
    assert r.status_code == 400
    assert "days deve estar entre 1 e 35" in r.json()["error"]
    assert _run(client, {**SITE, "days": 99}, "en", **files).json()["error"].startswith("days must be")


def test_a_request_that_is_not_a_json_object_is_a_400(client: TestClient) -> None:
    assert client.post("/api/run", data={"request": "{nope"}).status_code == 400
    assert client.post("/api/run", data={"request": "[1, 2]"}).status_code == 400


def test_a_result_no_longer_kept_is_a_404(client: TestClient) -> None:
    assert client.get("/api/result/000000000000").status_code == 404


def test_the_demo_covers_the_365_days_before_today_on_the_2020_wall_clock_hours() -> None:
    f = demo.frame(TODAY)
    utc = pd.DatetimeIndex(f["time"]).tz_localize("UTC")
    wall = utc.tz_convert(demo.TZ)
    assert wall[0] == pd.Timestamp(TODAY - dt.timedelta(days=365), tz=demo.TZ)
    assert wall[-1] == pd.Timestamp(TODAY, tz=demo.TZ) - pd.Timedelta(hours=1)
    assert ((utc[1:] - utc[:-1]) == pd.Timedelta(hours=1)).all()  # hourly, no gap, on a UTC clock
    src = demo._source()
    naive = wall.tz_localize(None)
    for i in np.linspace(0, len(f) - 1, 400).astype(int):
        back = [naive[i] - k * demo.WEEKS_52 for k in range(1, 12)]
        back = [b for b in back if src.index.min() <= b <= src.index.max()]
        assert back, naive[i]
        assert back[0].weekday() == naive[i].weekday()  # whole weeks: the same weekday
        assert f["consumption_kWh"].iloc[i] == src.loc[back[0], "consumption_kWh"]
        assert f["production_kWh"].iloc[i] == src.loc[back[0], "production_kWh"]


def test_the_demo_files_read_back_as_the_frame() -> None:
    files = demo.files(TODAY)
    assert set(files) == {"generation", "consumption"}
    text, name = files["consumption"]
    assert name == "dingle_H1_consumption.csv"
    back = pd.read_csv(io.BytesIO(text))
    assert list(back.columns) == ["time (UTC)", "consumption (kWh)"]
    assert len(back) == 365 * 24


def test_the_demo_runs_with_its_price(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    today = pd.Timestamp.now(tz=demo.TZ).date()
    monkeypatch.setattr(
        demo.pd.Timestamp, "now", classmethod(lambda cls, tz=None: pd.Timestamp(today, tz=tz))
    )
    monkeypatch.setattr(
        api, "SERVICES", _services(today.isoformat())
    )  # the same day for both (no midnight race)
    r = client.post("/api/demo", data={"lang": "en", "models": "naive"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["meta"]["demo"] and p["meta"]["source"]["license"] == "CC0-1.0"
    assert set(p["result"]["outlooks"]) == {"generation", "consumption"}
    assert p["result"]["windows_by_cost"]
    assert p["result"]["report"]["economics"]["currency"] == "EUR"


def test_a_demo_file_downloads_and_an_unknown_one_is_a_404(client: TestClient) -> None:
    r = client.get("/api/demo/generation.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0] == "time (UTC),production (kWh)"
    assert client.get("/api/demo/weather.csv").status_code == 404


def test_the_page_is_a_503_until_it_is_built(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(api, "DIST", tmp_path)
    r = client.get("/")
    assert r.status_code == 503 and "npm run build" in r.text
    (tmp_path / "index.html").write_text("<p>page</p>")
    r = client.get("/next-days")  # any path the page owns
    assert r.status_code == 200 and r.text == "<p>page</p>" and r.headers["cache-control"] == "no-store"


def test_the_launcher_takes_the_next_port_when_one_is_taken() -> None:
    first = launch.free_port(50100)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind((launch.HOST, first))
        held.listen()
        assert launch.free_port(first) > first
    assert launch.free_port(first) == first  # free again


def test_the_standalone_folder_finds_the_page_and_the_demo_beside_the_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)  # as PyInstaller sets it
    try:
        importlib.reload(demo)
        importlib.reload(api)
        assert tmp_path / "web" / "dist" == api.DIST
        assert tmp_path / "server" / "demo" / "dingle_H1_2020.csv" == demo.SOURCE
    finally:
        monkeypatch.undo()
        importlib.reload(demo)
        importlib.reload(api)
    assert demo.SOURCE.is_file() and HERE.parent / "web" / "dist" == api.DIST
