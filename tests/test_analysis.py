"""The app's single call: the report has every section and its numbers line up with the library."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prosumer import EnergySeries, analysis, data
from prosumer.analysis import analyze


def test_house_report_has_every_section() -> None:
    r = analyze(data.example_house(n_series=2, days=60), test_days=21)
    assert list(r.quality["series"]) == ["house_1", "house_2"]
    assert (r.quality["coverage"] == 1.0).all()
    assert r.summary["reference"] == "persistence_24h"
    assert r.forecast is not None and r.resolution is not None
    f = r.forecast.set_index("forecast")
    assert list(f.index) == ["median", "persistence_24h", "seasonal_168h", "mean_7d"]
    assert f.loc["persistence_24h", "skill"] == pytest.approx(0.0)
    assert f.loc["median", "skill_ci_low"] <= f.loc["median", "skill"] <= f.loc["median", "skill_ci_high"]
    # synthetic houses: lognormal noise around a fixed weekly shape, so averaging days beats yesterday
    assert f.loc["mean_7d", "skill"] > 0
    assert list(r.resolution["level"]) == ["hour", "day_night", "peak_17_21", "day"]
    assert r.summary["test_windows"] == 2 * 21
    assert set(r.pending) == set(analysis.PENDING)


def test_report_serializes_and_renders() -> None:
    r = analyze(data.example_house(n_series=1, days=40), test_days=14)
    json.dumps(r.to_dict())  # the app sends it as JSON
    md = r.to_markdown()
    for title in ("# Analysis", "## Data quality", "## Day-ahead forecast check", "## Not available yet"):
        assert title in md


def test_naive_forecasts_are_the_lagged_values() -> None:
    """Window position arithmetic checked against `data.persistence_forecast`, also when issued at noon."""
    s = data.example_house(n_series=1, days=30)
    for hour in (0, 12):
        task = analysis.DayAhead(
            s, test_start="2024-01-20", test_end="2024-01-25", context=168, issue_hour=hour
        )
        fc = analysis._naive_forecasts(task.windows(), None, "persistence_24h")
        assert (fc["ds"].dt.hour >= hour).all()
        keys = ["unique_id", "ds"]
        for name, lag in (("persistence_24h", 24), ("seasonal_168h", 168)):
            ref = data.persistence_forecast(s, lag_h=lag).rename(columns={"yhat": "expected"})
            m = fc.merge(ref, on=keys)
            assert len(m) == len(fc)
            np.testing.assert_allclose(m[name], m["expected"])


def test_plant_with_site_uses_clear_sky_persistence_and_sun_hours() -> None:
    series, _ = data.example_plant(n_series=1, days=50)
    r = analyze(series, site=(-25.43, -49.27), test_days=14)
    assert r.summary["reference"] == "clear_sky_persistence"
    assert r.forecast is not None
    f = r.forecast.set_index("forecast")
    assert "clear_sky_persistence" in f.index and f.loc["clear_sky_persistence", "skill"] == 0.0
    assert not any("without a site" in n for n in r.notes)


def test_plant_without_site_says_so() -> None:
    series, _ = data.example_plant(n_series=1, days=50)
    r = analyze(series, test_days=14)
    assert r.summary["reference"] == "persistence_24h"
    assert any("without a site" in n for n in r.notes)


def test_quality_notes_gaps_and_series_ending_apart() -> None:
    s = data.with_gaps(data.example_house(n_series=2, days=60), fraction=0.1, seed=2, short_series="house_2")
    r = analyze(s, test_days=14)
    q = r.quality.set_index("series")
    assert (q["coverage"] < 0.95).all() and (q["gaps"] > 0).all()
    assert q.loc["house_2", "last_valid"] < q.loc["house_1", "last_valid"]
    assert any("Coverage below 95%" in n for n in r.notes)
    assert any("do not end together" in n for n in r.notes)


def test_too_short_skips_the_forecast_check_but_keeps_quality() -> None:
    r = analyze(data.example_house(n_series=1, days=10), test_days=7)
    assert r.forecast is None and not r.quality.empty
    assert any("skipped" in n for n in r.notes)


def test_hourly_only() -> None:
    s = data.example_house(n_series=1, days=20, freq="30min")
    with pytest.raises(ValueError, match="hourly"):
        analyze(s)


def test_runs() -> None:
    assert analysis._runs(np.array([False, True, True, False, True])) == [2, 1]
    assert analysis._runs(np.zeros(3, bool)) == []


BENCH = Path(__file__).resolve().parents[1] / "experimentos" / "testes_previsao"


@pytest.mark.skipif(
    not (BENCH / "dados" / "casas_horario.parquet").exists()
    or not (BENCH / "resultados" / "metricas.csv").exists(),
    reason="benchmark data missing",
)
def test_analyze_reproduces_the_benchmark_naive_forecasts_on_the_dingle_houses() -> None:
    """End to end on real data: `analyze` over the last 92 days of the houses' consumption is the benchmark's
    `casas_cons|A` test, and its naive forecasts must give the published rows of `metricas.csv`."""
    c = pd.read_parquet(BENCH / "dados" / "casas_horario.parquet")
    d = c.rename(columns={"casa": "unique_id", "cons_kWh": "y"})[["unique_id", "ds", "y"]]
    d = d[d["ds"] <= "2020-12-31 23:00"]
    s = EnergySeries.from_dataframe(d, unit="kWh", quantity="consumption", tz="Etc/GMT", freq="h")
    r = analyze(s, test_days=92)
    assert (r.summary["test_start"], r.summary["test_end"]) == ("2020-10-01", "2020-12-31")
    assert r.forecast is not None
    ours = r.forecast.set_index("forecast")
    pub = pd.read_csv(BENCH / "resultados" / "metricas.csv", sep=";", decimal=",", encoding="utf-8-sig")
    pub = pub[(pub["caso"] == "casas_cons") & (pub["regime"] == "A")].set_index("modelo")
    for name, model in (
        ("persistence_24h", "persist_24h"),
        ("seasonal_168h", "semanal_168h"),
        ("mean_7d", "media_7d"),
    ):
        for col in ("skill", "nRMSE", "MBE", "R2"):
            assert ours.loc[name, col] == pytest.approx(pub.loc[model, col], abs=1e-12), (name, col)


def _plant_and_weather(days: int = 60) -> tuple[object, pd.DataFrame]:
    series, w = data.example_plant(n_series=2, days=days)
    # a "forecast" equal to the irradiance the generation was built from, as two models that agree
    weather = w[["unique_id", "ds"]].assign(
        ghi_a=w["poa_estimated"], ghi_b=w["poa_estimated"], ghi_mean=w["poa_estimated"], ghi_spread=0.0
    )
    return series, weather


def test_weather_adds_regime_c_and_its_section() -> None:
    series, weather = _plant_and_weather()
    r = analyze(series, site=(-25.43, -49.27), test_days=14, weather=weather)
    assert r.forecast is not None and r.weather is not None and r.resolution is not None
    f = r.forecast.set_index("forecast")
    assert (
        f.loc["weather_linear", "regime"] == "C" and (f.drop(index="weather_linear")["regime"] == "A").all()
    )
    assert f.loc["weather_linear", "skill"] > 0.99  # the generation is linear in this irradiance
    assert f.loc["weather_linear", "skill"] > f.loc["median", "skill"]
    assert list(r.forecast["forecast"])[-1] == "clear_sky_persistence"  # the reference closes the table
    assert set(r.resolution["forecast"]) == {"median", "weather_linear"}
    assert list(r.weather["source"]) == ["a", "b", "mean"] and (r.weather["fraction"] == 1.0).all()
    assert "weather (regimes B and C)" not in r.pending
    assert "## Weather forecast" in r.to_markdown()


def test_weather_without_series_id_is_shared_and_gaps_leave_every_row() -> None:
    series, weather = _plant_and_weather()
    shared = weather[weather["unique_id"] == "plant_1"].drop(columns="unique_id")
    last_day = shared["ds"].max().normalize()
    holed = shared.copy()
    holed.loc[holed["ds"] >= last_day + pd.Timedelta(hours=10), ["ghi_a", "ghi_b", "ghi_mean"]] = np.nan
    full = analyze(series, test_days=14, weather=shared)
    cut = analyze(series, test_days=14, weather=holed)
    assert full.forecast is not None and cut.forecast is not None
    assert "weather_linear" in set(full.forecast["forecast"])
    assert not any("left out" in n for n in full.notes)
    assert any("without a forecast from every model left out of every row" in n for n in cut.notes)
    assert cut.forecast.set_index("forecast").loc["median", "skill"] != pytest.approx(
        full.forecast.set_index("forecast").loc["median", "skill"]
    )


def test_consumption_with_weather_gets_only_the_coverage() -> None:
    s = data.example_house(n_series=1, days=40)
    ds = pd.date_range("2024-01-01", periods=40 * 24, freq="h", tz=s.tz)
    weather = pd.DataFrame({"ds": ds, "ghi_x": 100.0, "ghi_mean": 100.0})
    r = analyze(s, test_days=14, weather=weather)
    assert r.forecast is not None and "weather_linear" not in set(r.forecast["forecast"])
    assert r.weather is not None and list(r.weather["source"]) == ["x", "mean"]


def test_weather_needs_aware_times() -> None:
    series, weather = _plant_and_weather(30)
    with pytest.raises(ValueError, match="time zone"):
        analyze(series, test_days=7, weather=weather.assign(ds=weather["ds"].dt.tz_localize(None)))


def test_models_become_rows_and_history_models_enter_the_median() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from prosumer.forecast import LightGBM, Naive

    s = data.example_house(n_series=2, days=60)
    base = analyze(s, test_days=14)
    r = analyze(s, test_days=14, models=[LightGBM(params={"n_estimators": 50})])
    assert base.forecast is not None and r.forecast is not None
    f = r.forecast.set_index("forecast")
    assert f.loc["LightGBM", "regime"] == "A"
    assert list(r.forecast["forecast"])[:5] == [
        "median",
        "persistence_24h",
        "seasonal_168h",
        "mean_7d",
        "LightGBM",
    ]
    # the median now has four members: it moves, the naive rows do not
    b = base.forecast.set_index("forecast")
    assert f.loc["median", "skill"] != pytest.approx(b.loc["median", "skill"])
    assert f.loc["mean_7d", "skill"] == pytest.approx(b.loc["mean_7d", "skill"])
    with pytest.raises(ValueError, match="Two forecasts"):
        analyze(s, test_days=14, models=[Naive("mean_7d")])


def test_weather_models_are_regime_c_and_need_the_weather() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from prosumer.forecast import LightGBM

    series, weather = _plant_and_weather()
    model = LightGBM(["ghi_mean"], params={"n_estimators": 50}, name="LightGBM-C")
    without = analyze(series, site=(-25.43, -49.27), test_days=14, models=[model])
    assert any("needs a weather forecast" in n for n in without.notes)
    r = analyze(series, site=(-25.43, -49.27), test_days=14, weather=weather, models=[model])
    assert r.forecast is not None and r.resolution is not None
    f = r.forecast.set_index("forecast")
    assert f.loc["LightGBM-C", "regime"] == "C" and f.loc["LightGBM-C", "skill"] > f.loc["median", "skill"]
    assert list(r.forecast["forecast"])[-1] == "clear_sky_persistence"
    assert set(r.resolution["forecast"]) == {"median", "weather_linear", "LightGBM-C"}


def test_bands_section_scores_each_band_against_the_14_day_reference() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from prosumer.forecast import LightGBMQuantile

    s = data.example_house(n_series=2, days=70)
    r = analyze(s, test_days=14, models=[LightGBMQuantile(params={"n_estimators": 60})])
    assert r.bands is not None and r.forecast is not None
    b = r.bands.set_index("source")
    assert list(b.index) == ["LightGBM-quantile", "LightGBM-quantile+conformal", "empirical_14d"]
    assert b.loc["LightGBM-quantile+conformal", "regime"] == "A"
    assert b.loc["empirical_14d", "CRPS_skill"] == 0.0
    assert (b["hours"] == b["hours"].iloc[0]).all()  # every band on the same hours
    assert 0 < b.loc["LightGBM-quantile", "coverage_80"] <= 1
    assert "LightGBM-quantile" in set(r.forecast["forecast"])  # its median is a point row too
    assert "bands (quantiles)" not in r.pending
    assert "### Bands" in r.to_markdown()
    json.dumps(r.to_dict())
