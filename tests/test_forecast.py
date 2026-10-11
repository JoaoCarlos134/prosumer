"""The forecast interface: the runner cuts the data by fold, the naive models read the right hours."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prosumer import DayAhead, data
from prosumer.contracts import EnergySeries
from prosumer.forecast import Naive, rolling_forecast
from prosumer.forecast.base import ModelCard
from prosumer.protocol import Regime, Window


class Spy:
    """Records what `fit` saw; forecasts the last value seen in training, so leakage would show."""

    card = ModelCard("spy", "naive", "n/a", "cpu", False, (Regime.HISTORY,), trains=True)

    def __init__(self) -> None:
        self.cuts: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def fit(self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None) -> None:
        self.cuts.append((cutoff, series.frame["ds"].max()))

    def predict(self, windows: list[Window]) -> np.ndarray:
        return np.zeros((len(windows), 24))


def test_runner_fits_once_per_fold_on_data_before_it() -> None:
    s = data.example_house(n_series=2, days=60)
    task = DayAhead(s, test_start="2024-02-01", test_end="2024-02-29", refit_days=10, context=168)
    spy = Spy()
    out = rolling_forecast(spy, task)
    assert [c for c, _ in spy.cuts] == [f.start for f in task.folds()]
    for cutoff, last_seen in spy.cuts:
        assert last_seen < cutoff, "the model saw data from its own fold"
    assert len(out) == len(task.windows()) * 24
    assert list(out.columns) == ["unique_id", "ds", "yhat"]


def test_runner_refuses_a_forecast_of_the_wrong_shape() -> None:
    class Short(Spy):
        def predict(self, windows: list[Window]) -> np.ndarray:
            return np.zeros((len(windows), 12))

    s = data.example_house(n_series=1, days=30)
    with pytest.raises(ValueError, match="values for 24 target hours"):
        rolling_forecast(Short(), DayAhead(s, test_start="2024-01-20", test_end="2024-01-22"))


@pytest.mark.parametrize(("kind", "lag"), [("persistence_24h", 24), ("seasonal_168h", 168)])
def test_naive_matches_the_lagged_series(kind: str, lag: int) -> None:
    s = data.example_house(n_series=2, days=30)
    for hour in (0, 12):
        task = DayAhead(s, test_start="2024-01-20", test_end="2024-01-25", context=168, issue_hour=hour)
        fc = rolling_forecast(Naive(kind), task)  # type: ignore[arg-type]
        ref = data.persistence_forecast(s, lag_h=lag).rename(columns={"yhat": "expected"})
        m = fc.merge(ref, on=["unique_id", "ds"])
        assert len(m) == len(fc) and (fc["ds"].dt.hour >= hour).all()
        np.testing.assert_allclose(m["yhat"], m["expected"])


def test_naive_mean_7d_and_short_history() -> None:
    s = data.example_house(n_series=1, days=30)
    w = DayAhead(s, test_start="2024-01-20", test_end="2024-01-20", context=168).windows()[0]
    expected = np.mean([w.history[168 - 24 * d : 168 - 24 * d + 24] for d in range(1, 8)], axis=0)
    np.testing.assert_allclose(Naive("mean_7d").predict([w])[0], expected)
    short = Window(w.unique_id, w.day, w.history[-48:], w.timestamps)
    assert np.isnan(Naive("seasonal_168h").predict([short])).all()
    with pytest.raises(ValueError, match="kind"):
        Naive("yesterday")  # type: ignore[arg-type]


def test_lightgbm_card_and_runs_on_synthetic_data() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from prosumer.forecast import LightGBM

    s = data.example_house(n_series=2, days=60)
    task = DayAhead(s, test_start="2024-02-20", test_end="2024-02-29", refit_days=5, context=168)
    m = LightGBM(params={"n_estimators": 30})
    assert m.card.regimes == (Regime.HISTORY,) and m.card.device == "cpu" and not m.card.sends_data
    fc = rolling_forecast(m, task)
    assert len(fc) == len(task.windows()) * 24 and fc["yhat"].notna().all()
    with pytest.raises(NotImplementedError, match="whole days"):
        rolling_forecast(m, DayAhead(s, test_start="2024-02-20", test_end="2024-02-22", issue_hour=12))
