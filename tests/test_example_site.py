"""The example site's backend (examples/site_local/app.py), without the network: consumption with the
coordinates and the time zone typed needs neither geocoding nor a weather forecast."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

APP = Path(__file__).resolve().parents[1] / "examples" / "site_local" / "app.py"


def _app():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("site_app", APP)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_consumption_page_from_a_brazilian_csv() -> None:
    idx = pd.date_range("2024-01-01", periods=6 * 7 * 24, freq="h")
    y = 0.3 + np.where((idx.hour >= 18) & (idx.hour < 21), 1.0, 0.0)
    text = pd.DataFrame({"data": idx.strftime("%d/%m/%Y %H:%M"), "consumo": y}).to_csv(
        index=False, sep=";", decimal=","
    )
    form = {
        "quantity": "consumption",
        "latitude": "-25.43",
        "longitude": "-49.27",
        "timezone": "America/Sao_Paulo",
        "days": "7",
        "load_hours": "2",
    }
    page = _app().forecast_page(form, text.encode("utf-8"))
    assert "Forecast of your consumption" in page
    assert page.count("typical week") >= 14  # 7 days in the table and 7 in the best windows
    assert "18:00" not in page.split("Best 2 hours")[1].split("</table>")[0]  # never in the evening peak
