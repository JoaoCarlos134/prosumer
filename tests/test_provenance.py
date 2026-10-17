"""Provenance: every input of an analysis says where it came from and under what licence, and the report shows
it. Synthetic data and fake APIs only: no network."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from prosumer import Provenance, analyze, data
from prosumer import provenance as prov
from prosumer.contracts import EnergySeries
from prosumer.forecast import ModelCard
from prosumer.io import nasa_power as npw
from prosumer.io import open_meteo as om
from prosumer.protocol import Regime, Window


# ---------------------------------------------------------------------- the record
def test_licence_flags() -> None:
    assert not Provenance("x").license_known
    assert not Provenance("x", license=" Unknown ").license_known
    assert Provenance("x", license="n/a").license_known
    assert Provenance("x", license="CC-BY-NC-4.0").non_commercial
    assert Provenance("x", license="CC-BY-4.0", notes="free API: non-commercial use only").non_commercial
    assert not Provenance("x", license="CC0-1.0").non_commercial
    assert Provenance("x", license="MIT").to_dict()["license"] == "MIT"


def test_of_reads_series_frames_and_json_dicts() -> None:
    p = Provenance("somewhere", license="CC0-1.0", retrieved="2026-10-11")
    frame = prov.attach(pd.DataFrame({"a": [1.0]}), p)
    assert prov.of(frame) == p  # stored as a dict since 2026-10-17 (parquet), rebuilt on read
    assert prov.of(frame.copy()) == p  # pandas keeps attrs through a copy
    assert prov.of(pd.DataFrame({"a": [1.0]})) is None
    from_json = pd.DataFrame({"a": [1.0]})
    from_json.attrs["provenance"] = json.loads(json.dumps(p.to_dict()))
    assert prov.of(from_json) == p
    s = data.example_house(n_series=1, days=10)
    assert prov.of(s) is s.provenance


# ---------------------------------------------------------------------- series
def test_synthetic_series_say_so_and_operations_keep_it() -> None:
    house = data.example_house(n_series=1, days=10, seed=3)
    assert house.provenance is not None and house.provenance.license == "n/a"
    assert "example_house(seed=3)" in house.provenance.source
    plant, weather = data.example_plant(n_series=1, days=10)
    assert plant.provenance is not None and "synthetic" in plant.provenance.source
    assert prov.of(weather) is not None
    # derived series keep it
    in_wh = replace(house, frame=house.frame.assign(y=house.frame["y"] * 1000), unit="Wh")
    assert in_wh.to_kwh().provenance == house.provenance
    assert data.with_gaps(house, fraction=0.1).provenance == house.provenance


def test_from_dataframe_takes_it_and_defaults_to_none() -> None:
    raw = pd.DataFrame(
        {"unique_id": "a", "ds": pd.date_range("2024-01-01", periods=3, freq="h"), "y": [1.0, 2.0, 3.0]}
    )
    plain = EnergySeries.from_dataframe(raw, unit="kWh", quantity="consumption", tz="UTC", freq="h")
    assert plain.provenance is None
    p = Provenance("my meter", license="proprietary")
    tagged = EnergySeries.from_dataframe(
        raw, unit="kWh", quantity="consumption", tz="UTC", freq="h", provenance=p
    )
    assert tagged.provenance is p
    assert tagged.frame.equals(plain.frame)


def test_dingle_houses_carry_cc0_and_the_citation(tmp_path: Any) -> None:
    # the original CSV layout, one house, two hours of minutes
    t = pd.date_range("2020-01-01 00:01", periods=120, freq="min")
    body = pd.DataFrame(
        {"date": t.strftime("%Y-%m-%d %H:%M:%S"), "Consumption(Wh)": 2.0, "Production(Wh)": 0.0}
    )
    body.to_csv(tmp_path / "H1_Wh.csv", index=False)
    s = data.dingle_houses(houses=[1], path=tmp_path)
    assert s.provenance == data.DINGLE_PROVENANCE
    assert s.provenance.license == "CC0-1.0" and s.provenance.citation == data.DINGLE_CITATION


# ---------------------------------------------------------------------- readers
def test_open_meteo_download_and_wide_carry_cc_by() -> None:
    def get(url: str, params: dict[str, Any]) -> dict[str, Any]:
        t = pd.date_range(
            params["start_date"], pd.Timestamp(params["end_date"]) + pd.Timedelta(hours=23), freq="h"
        )
        return {
            "hourly": {
                "time": [x.strftime("%Y-%m-%dT%H:%M") for x in t],
                "shortwave_radiation_previous_day1": [1.0] * len(t),
            }
        }

    raw = om.fetch_previous_runs(
        0, 0, start="2024-06-02", end="2024-06-02", models=["m1", "m2"], variables=["ghi"], get=get, pause_s=0
    )
    p = prov.of(raw)
    assert p is not None and p.license == "CC-BY-4.0" and p.non_commercial
    assert "m1, m2" in p.source and "previous_day1" in p.source and p.retrieved
    assert "Open-Meteo.com" in p.citation
    assert prov.of(om.wide(raw)) == p
    assert prov.of(om.wide(raw, unique_id=["a", "b"])) == p
    assert prov.of(om.wide(raw.copy().assign(model="m"), unique_id="a")) == p


def test_nasa_power_download_carries_cc0_and_the_power_reference() -> None:
    def get(url: str, params: dict[str, Any]) -> dict[str, Any]:
        t = pd.date_range(
            pd.Timestamp(params["start"]), pd.Timestamp(params["end"]) + pd.Timedelta(hours=23), freq="h"
        )
        block = {k: {f"{x:%Y%m%d%H}": 1.0 for x in t} for k in params["parameters"].split(",")}
        return {"header": {"fill_value": -999.0}, "properties": {"parameter": block}}

    out = npw.fetch_hourly(0, 0, start="2025-08-01", end="2025-08-01", variables=["ghi"], get=get, pause_s=0)
    p = prov.of(out)
    assert p is not None and p.license == "CC0-1.0" and not p.non_commercial
    assert "POWER" in p.citation and p.retrieved is not None and p.retrieved.replace("-", "/") in p.citation
    fixed = npw.provenance(retrieved="2026-01-02")
    assert "2026/01/02" in fixed.citation


# ---------------------------------------------------------------------- the report
class _Leaky:
    """A history-only model that 'sends the data out' and has no declared licence: mean of the last day."""

    card = ModelCard(
        name="leaky",
        family="foundation",
        license="unknown",
        device="remote",
        sends_data=True,
        regimes=(Regime.HISTORY,),
        trains=False,
        source="a paid API",
    )

    def fit(self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None) -> None:
        pass

    def predict(self, windows: list[Window]) -> np.ndarray:
        return np.vstack([np.full(len(w.timestamps), float(np.mean(w.history[-24:]))) for w in windows])


def test_report_lists_every_input_and_renders_it() -> None:
    s = data.example_house(n_series=1, days=40)
    r = analyze(s, test_days=14)
    assert r.provenance is not None
    assert list(r.provenance["role"]) == ["series"] and r.provenance["license"].iloc[0] == "n/a"
    assert not any("Licence unknown" in n for n in r.notes)
    d = r.to_dict()
    json.dumps(d)
    assert d["provenance"][0]["source"] == s.provenance.source  # type: ignore[union-attr]
    md = r.to_markdown()
    assert "## Data sources and licences" in md and "example_house" in md


def test_unknown_licence_non_commercial_weather_and_leaky_model_are_noted() -> None:
    raw = pd.DataFrame(
        {"unique_id": "a", "ds": pd.date_range("2024-01-01", periods=40 * 24, freq="h", tz="UTC")}
    ).assign(y=lambda d: 1.0 + (d["ds"].dt.hour == 19) + np.random.default_rng(0).random(len(d)))
    s = EnergySeries.from_dataframe(raw, unit="kWh", quantity="consumption", tz="UTC", freq="h")
    weather = prov.attach(
        pd.DataFrame({"ds": raw["ds"], "ghi_x": 100.0, "ghi_mean": 100.0}),
        om.provenance(["x"], retrieved="2026-10-11"),
    )
    base = analyze(s, test_days=14)
    r = analyze(s, test_days=14, weather=weather, models=[_Leaky()])
    assert r.provenance is not None
    t = r.provenance.set_index("role")
    assert list(r.provenance["role"]) == ["series", "weather", "model"]
    assert t.loc["series", "license"] == "unknown" and t.loc["series", "source"] == "not declared"
    assert t.loc["weather", "license"] == "CC-BY-4.0" and t.loc["weather", "retrieved"] == "2026-10-11"
    assert bool(t.loc["model", "sends_data"]) and t.loc["model", "name"] == "leaky"
    unknown = [n for n in r.notes if n.startswith("Licence unknown")]
    assert len(unknown) == 1 and "series (consumption)" in unknown[0] and "model (leaky)" in unknown[0]
    assert any("non-commercial" in n and "weather" in n for n in r.notes)
    assert any("outside this machine: leaky" in n for n in r.notes)
    # the base report notes the undeclared series too, and no number moved because of provenance
    assert any(n.startswith("Licence unknown") for n in base.notes)
    assert base.forecast is not None and r.forecast is not None
    b, f = base.forecast.set_index("forecast"), r.forecast.set_index("forecast")
    assert f.loc["mean_7d", "skill"] == pytest.approx(b.loc["mean_7d", "skill"])


def test_numbers_do_not_depend_on_provenance() -> None:
    s = data.example_house(n_series=2, days=40)
    bare = replace(s, provenance=None)
    a, b = analyze(s, test_days=14), analyze(bare, test_days=14)
    assert a.forecast is not None and b.forecast is not None
    pd.testing.assert_frame_equal(a.forecast, b.forecast)
    pd.testing.assert_frame_equal(a.quality, b.quality)


def test_short_series_still_reports_its_provenance() -> None:
    r = analyze(data.example_house(n_series=1, days=5), test_days=3)
    assert r.forecast is None and r.provenance is not None and len(r.provenance) == 1


def test_frames_with_provenance_can_be_saved_to_parquet(tmp_path: Path) -> None:
    """Regression (2026-10-17): `attach` put the Provenance object in `attrs`, and pandas writes `attrs` into
    a parquet file as JSON: `fetch_hourly(...).to_parquet(...)` raised TypeError. Now a dict, read back by
    `of`."""
    p = Provenance(source="NASA POWER", license="CC0-1.0", citation="cite me", retrieved="2026-10-17")
    frame = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"), "ghi": 1.0})
    f = prov.attach(frame, p)
    path = tmp_path / "w.parquet"
    f.to_parquet(path)
    back = pd.read_parquet(path)
    assert prov.of(back) == p and prov.of(f) == p
    assert prov.of(f.copy()) == p  # pandas keeps attrs through copies
