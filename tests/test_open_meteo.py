"""Open-Meteo reader, without the network: a fake API answers, and the saved benchmark archive is the
reference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from prosumer.io import open_meteo as om

SAVED = (
    Path(__file__).resolve().parents[1]
    / "experimentos"
    / "testes_previsao"
    / "dados"
    / "previsao_tempo.parquet"
)


class FakeAPI:
    """Answers like the Previous Runs API (times in GMT) from a function of the UTC hour, and records the
    calls."""

    def __init__(self, values: dict[str, Any]) -> None:
        self.values, self.calls = values, []  # values: model -> f(utc DatetimeIndex) -> {api key: array}

    def __call__(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(params)
        assert params["timezone"] == "GMT"
        t = pd.date_range(
            params["start_date"], pd.Timestamp(params["end_date"]) + pd.Timedelta(hours=23), freq="h"
        )
        block = {k: list(v) for k, v in self.values[params["models"]](t).items()}
        return {"hourly": {"time": [x.strftime("%Y-%m-%dT%H:%M") for x in t], **block}}


def _ramp(t: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    h = np.arange(len(t), dtype=float)
    return {"shortwave_radiation_previous_day1": h, "temperature_2m_previous_day1": 10 * h}


def test_labels_move_to_the_start_of_the_hour_and_temperature_is_averaged() -> None:
    api = FakeAPI({"m": _ramp})
    raw = om.fetch_previous_runs(0, 0, start="2024-06-02", end="2024-06-03", models=["m"], get=api, pause_s=0)
    # the fake starts at 2024-06-01 00:00 UTC (one day of margin): hour k has value k
    k = int(
        (pd.Timestamp("2024-06-02", tz="UTC") - pd.Timestamp("2024-06-01", tz="UTC")) / pd.Timedelta(hours=1)
    )
    first = raw.iloc[0]
    assert first["ds"] == pd.Timestamp("2024-06-02", tz="UTC")
    assert first["ghi"] == k + 1  # the value labelled 01:00 is the mean over 00:00-01:00
    assert first["temperature"] == pytest.approx(10 * (k + 0.5))
    assert len(raw) == 48 and raw["ds"].is_monotonic_increasing
    p = api.calls[0]
    assert p["hourly"] == "shortwave_radiation_previous_day1,temperature_2m_previous_day1"
    assert (p["start_date"], p["end_date"]) == ("2024-06-01", "2024-06-04")


def test_daylight_saving_neither_duplicates_nor_drops_hours() -> None:
    raw = om.fetch_previous_runs(
        52.1,
        -10.2,
        start="2020-10-24",
        end="2020-10-26",
        models=["m"],
        tz="Europe/Dublin",
        get=FakeAPI({"m": _ramp}),
    )
    assert raw["ds"].is_unique
    assert raw["ds"].diff().dropna().eq(pd.Timedelta(hours=1)).all()
    assert len(raw) == 3 * 24 + 1  # 25 October 2020 has 25 hours in Dublin


def test_lead_days_and_variables() -> None:
    def three(t: pd.DatetimeIndex) -> dict[str, np.ndarray]:
        return {"cloud_cover_previous_day3": np.full(len(t), 50.0)}

    api = FakeAPI({"m": three})
    raw = om.fetch_previous_runs(
        0,
        0,
        start="2024-01-02",
        end="2024-01-02",
        models=["m"],
        variables=["cloud_cover"],
        lead_days=3,
        get=api,
    )
    assert list(raw.columns) == ["model", "ds", "cloud_cover"] and (raw["cloud_cover"] == 50).all()
    with pytest.raises(ValueError, match="lead_days"):
        om.fetch_previous_runs(0, 0, start="2024-01-02", end="2024-01-02", lead_days=8, get=api)
    with pytest.raises(ValueError, match="Unknown variables"):
        om.fetch_previous_runs(0, 0, start="2024-01-02", end="2024-01-02", variables=["wind"], get=api)


def test_coverage_finds_the_model_that_starts_late() -> None:
    def late(t: pd.DatetimeIndex) -> dict[str, np.ndarray]:
        v = np.where(t >= pd.Timestamp("2024-01-11"), 100.0, np.nan)
        return {"shortwave_radiation_previous_day1": v, "temperature_2m_previous_day1": v}

    api = FakeAPI({"full": _ramp, "late": late})
    raw = om.fetch_previous_runs(
        0, 0, start="2024-01-01", end="2024-01-20", models=["full", "late"], get=api, pause_s=0
    )
    c = om.coverage(raw).set_index("model")
    assert c.loc["full", "fraction"] == 1.0
    assert c.loc["late", "fraction"] == pytest.approx(0.5, abs=0.01)
    assert c.loc["late", "first"] == pd.Timestamp(
        "2024-01-10 23:00", tz="UTC"
    )  # labelled 11/01 00:00 -> 10/01 23 h


def test_wide_mean_spread_and_series_ids() -> None:
    def const(x: float):  # type: ignore[no-untyped-def]
        return lambda t: {
            "shortwave_radiation_previous_day1": np.full(len(t), x),
            "temperature_2m_previous_day1": np.full(len(t), x / 10),
        }

    raw = om.fetch_previous_runs(
        0,
        0,
        start="2024-01-01",
        end="2024-01-01",
        models=["a", "b"],
        get=FakeAPI({"a": const(100), "b": const(300)}),
    )
    w = om.wide(raw)
    assert {"ghi_a", "ghi_b", "ghi_mean", "ghi_spread", "temperature_mean"} <= set(w.columns)
    assert (w["ghi_mean"] == 200).all() and (w["ghi_spread"] == 100).all()
    both = om.wide(raw, unique_id=["plant_1", "plant_2"])
    assert both.columns[0] == "unique_id" and len(both) == 2 * len(w)


@pytest.mark.skipif(not SAVED.exists(), reason="benchmark archive missing")
def test_reproduces_the_benchmark_conversion_of_the_saved_archive() -> None:
    """The saved regime C archive (local Brazilian time, labels as the API gives them) served by the fake API
    in GMT: the library's conversion must equal `comum.exog_previsao` (shift for GHI, mean of the ends for the
    temperature), hour by hour."""
    P = pd.read_parquet(SAVED)
    P = P[(P["serie"] == "Cascavel") & (P["modelo_nwp"] == "ecmwf_ifs025")].set_index("ds").sort_index()
    P.index = P.index.tz_localize("Etc/GMT+3").tz_convert("UTC").tz_localize(None)

    def saved(t: pd.DatetimeIndex) -> dict[str, np.ndarray]:
        return {
            "shortwave_radiation_previous_day1": P["ghi_prev"].reindex(t).to_numpy(),
            "temperature_2m_previous_day1": P["temp_prev"].reindex(t).to_numpy(),
        }

    raw = om.fetch_previous_runs(
        -24.83,
        -53.65,
        start="2025-08-01",
        end="2025-12-31",
        models=["ecmwf_ifs025"],
        tz="Etc/GMT+3",
        get=FakeAPI({"ecmwf_ifs025": saved}),
    ).set_index("ds")
    local = P.copy()
    local.index = local.index.tz_localize("UTC").tz_convert("Etc/GMT+3")
    ghi = local["ghi_prev"].shift(-1).reindex(raw.index)
    tmp = ((local["temp_prev"] + local["temp_prev"].shift(-1)) / 2).reindex(raw.index)
    np.testing.assert_array_equal(raw["ghi"].to_numpy(), ghi.to_numpy())
    np.testing.assert_allclose(raw["temperature"].to_numpy(), tmp.to_numpy(), rtol=0, atol=1e-12)
    assert raw["ghi"].notna().all()


class FakeForecastAPI:
    """Answers like the live Forecast API: `past_days` before and `forecast_days` from 00 UTC of today, each
    model with values only up to its horizon (in hours from 00 UTC of today)."""

    def __init__(self, horizons: dict[str, int]) -> None:
        self.horizons, self.calls = horizons, []

    def __call__(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        assert url == om.FORECAST_URL
        self.calls.append(params)
        today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
        t = pd.date_range(
            today - pd.Timedelta(days=params["past_days"]),
            today + pd.Timedelta(days=params["forecast_days"]) - pd.Timedelta(hours=1),
            freq="h",
        )
        lead = (t - today) / pd.Timedelta(hours=1)
        ok = lead <= self.horizons[params["models"]]
        ghi = [float(i % 24) * 50 if k else None for i, k in enumerate(ok)]
        temp = [15.0 if k else None for k in ok]
        return {
            "hourly": {
                "time": [x.strftime("%Y-%m-%dT%H:%M") for x in t],
                "shortwave_radiation": ghi,
                "temperature_2m": temp,
            }
        }


def test_live_forecast_from_today_with_each_models_horizon() -> None:
    api = FakeForecastAPI({"long": 16 * 24, "short": 4 * 24})
    f = om.fetch_forecast(0, 0, days=10, models=["long", "short"], tz="America/Sao_Paulo", get=api, pause_s=0)
    today = pd.Timestamp.now(tz="America/Sao_Paulo").normalize()
    assert f["ds"].min() == today
    assert f["ds"].max() == today + pd.Timedelta(days=10) - pd.Timedelta(hours=1)
    assert f.groupby("model").size().eq(240).all()  # hourly, no hour duplicated or dropped
    cov = om.coverage(f).set_index("model")["fraction"]
    assert cov["long"] == 1.0
    assert 0.3 < cov["short"] < 0.6  # the short model stops after ~4 of the 10 days
    w = om.wide(f)
    late = w["ds"] > today + pd.Timedelta(days=6)
    assert w.loc[late, "ghi_short"].isna().all()
    np.testing.assert_array_equal(w.loc[late, "ghi_mean"], w.loc[late, "ghi_long"])  # mean of the models left
    assert "issued" in f.attrs and f.attrs["provenance"].license == "CC-BY-4.0"
    assert all(c["timezone"] == "GMT" for c in api.calls)
    with pytest.raises(ValueError):
        om.fetch_forecast(0, 0, days=17, get=api)


def test_live_forecast_label_convention_matches_the_archive() -> None:
    api = FakeForecastAPI({"m": 16 * 24})
    f = om.fetch_forecast(0, 0, days=2, models=["m"], tz="UTC", get=api, pause_s=0)
    # the API labels a radiation value by the end of its hour: the hour starting at h gets the label h+1
    first = f.iloc[0]
    assert first["ds"].hour == 0 and first["ghi"] == 50.0
