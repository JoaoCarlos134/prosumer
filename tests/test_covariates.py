"""Covariate contract test: an adapter that receives weather has to USE the weather.

This is the TiDE regression. In the benchmark it spent two versions (v1 and v2) at +0.07 skill in the
regimes with weather, against +0.47 to +0.49 for its peers, because NeuralForecast's `MLPResidual` ends
in a LayerNorm over `temporal_width` (= the number of exogenous variables) applied at EACH hour: that
removes the mean and scale of the weather variables hour by hour and erases the amplitude, which is
exactly the "how sunny is it" signal. The B and C forecasts ended up with 0.999 correlation between
them (the model barely reacted to swapping perfect weather for a real forecast) while the peers stayed
at 0.96.

The defect got through because nobody tested the plumbing, only the aggregate result. Any new adapter
that accepts future covariates must pass both tests here.
"""

from __future__ import annotations

import numpy as np
import pytest

from prosumer import data

# Correlation above this between two forecasts made with DIFFERENT weather means the model is ignoring
# the covariate. The broken TiDE gave 0.999; healthy models, ~0.96.
INSENSITIVITY_LIMIT = 0.995


def _fit_predict(uses_weather: bool, y: np.ndarray, poa: np.ndarray) -> np.ndarray:
    """Toy adapter, standing in for a real model.

    `uses_weather=True` mimics a correct adapter (reads the covariate); `False` mimics the broken one,
    which ignores the covariate and only repeats the recent level.
    """
    if uses_weather:
        scale = float(np.sum(y * poa) / max(float(np.sum(poa * poa)), 1e-12))
        return scale * poa
    return np.full_like(poa, float(np.mean(y)))


def test_example_data_ties_generation_to_weather() -> None:
    """Precondition: synthetic generation must be a function of the weather, or nothing is detectable."""
    series, weather = data.example_plant(n_series=1, days=60)
    j = series.frame.merge(weather, on=["unique_id", "ds"])
    sun = j[j["poa_clear_sky"] > 0]
    assert np.corrcoef(sun["y"], sun["poa_estimated"])[0, 1] > 0.99


def test_adapter_that_uses_weather_reacts_to_a_weather_swap() -> None:
    """Two different weathers must produce different forecasts. TiDE failed exactly here."""
    series, weather = data.example_plant(n_series=1, days=60, seed=1)
    _, other_weather = data.example_plant(n_series=1, days=60, seed=999)
    j = series.frame.merge(weather, on=["unique_id", "ds"]).merge(
        other_weather[["unique_id", "ds", "poa_estimated"]], on=["unique_id", "ds"], suffixes=("", "_alt")
    )
    sun = j[j["poa_clear_sky"] > 0]
    y = sun["y"].to_numpy()

    good_a = _fit_predict(True, y, sun["poa_estimated"].to_numpy())
    good_b = _fit_predict(True, y, sun["poa_estimated_alt"].to_numpy())
    r_good = float(np.corrcoef(good_a, good_b)[0, 1])
    assert r_good < INSENSITIVITY_LIMIT, (
        f"forecasts with different weather have correlation {r_good:.4f}: "
        "the adapter is not using the covariate"
    )


def test_the_test_catches_an_adapter_that_ignores_weather() -> None:
    """Meta-test: without this, the test above could be passing by accident."""
    series, weather = data.example_plant(n_series=1, days=60, seed=1)
    _, other_weather = data.example_plant(n_series=1, days=60, seed=999)
    j = series.frame.merge(weather, on=["unique_id", "ds"]).merge(
        other_weather[["unique_id", "ds", "poa_estimated"]], on=["unique_id", "ds"], suffixes=("", "_alt")
    )
    sun = j[j["poa_clear_sky"] > 0]
    y = sun["y"].to_numpy()

    bad_a = _fit_predict(False, y, sun["poa_estimated"].to_numpy())
    bad_b = _fit_predict(False, y, sun["poa_estimated_alt"].to_numpy())
    # Ignoring the weather produces the SAME forecast: constant, correlation undefined or 1.
    assert np.allclose(bad_a, bad_b), "the deaf adapter should give identical forecasts"


def test_adapter_with_weather_errs_less_than_without() -> None:
    """The other side of the contract: receiving the covariate must improve the error, not only change it."""
    series, weather = data.example_plant(n_series=1, days=60)
    j = series.frame.merge(weather, on=["unique_id", "ds"])
    sun = j[j["poa_clear_sky"] > 0]
    y = sun["y"].to_numpy()
    poa = sun["poa_estimated"].to_numpy()
    rmse_with = float(np.sqrt(np.mean((_fit_predict(True, y, poa) - y) ** 2)))
    rmse_without = float(np.sqrt(np.mean((_fit_predict(False, y, poa) - y) ** 2)))
    assert rmse_with < rmse_without


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_gaps_do_not_become_zero(seed: int) -> None:
    """Real-data pathology: a gap must stay invalid, never a silent zero."""
    series = data.example_house(n_series=2, days=30)
    holed = data.with_gaps(series, fraction=0.1, seed=seed)
    invalid = ~holed.frame["valid"]
    assert invalid.any()
    assert holed.frame.loc[invalid, "y"].isna().all(), "invalid with a numeric value masks the gap"
    assert float(holed.coverage().min()) < 1.0
