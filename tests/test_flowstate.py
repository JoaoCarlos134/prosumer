"""FlowState (`forecast.FlowState`): the card, the batching, and the E3 parity with the benchmark.

Parity: the library adapter regenerates the benchmark's saved FlowState forecasts
(`resultados/previsoes/FlowState__<case>__A.parquet`, `03_fundacionais.py`) and the 9 quantiles of pilot F2(c)
(`resultados/pilotos/FlowState-quantis__<case>__A.parquet`, `piloto_quantis.py gera FlowState`). Checked on
2026-10-16 (Lactec, CPU, torch 2.11.0+cpu, granite-tsfm 0.3.9): see the docstring of the parity test. By
default the first 32 windows of the houses' consumption (~30 s); `PROSUMER_FULL=1` runs every window of the
three cases.

The model tests need `tsfm_public` (extra `ttm`) and the weights in the Hugging Face cache: they run offline
(`HF_HUB_OFFLINE=1`) and skip otherwise, like the benchmark data tests skip without the data.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # tests never touch the network: the weights come from the cache

import numpy as np
import pandas as pd
import pytest

from prosumer import DayAhead, analyze, data
from prosumer.forecast import FlowState, rolling_quantiles
from prosumer.forecast.foundation import LEVELS, _same_length
from prosumer.protocol import H, Regime, Window

BENCH = Path(__file__).resolve().parents[1] / "experimentos" / "testes_previsao"
CASES = ("casas_cons", "casas_prod", "usinas")
ATOL = 1e-5  # float32 model; seen 4e-7 (kWh), values up to ~10 kWh


def _window(n: int, i: int) -> Window:
    day = pd.Timestamp("2024-03-01", tz="UTC") + pd.Timedelta(days=i)
    return Window(f"s{i}", day, np.full(n, float(i)), pd.date_range(day, periods=H, freq="h"))


def test_card_says_what_it_costs() -> None:
    c = FlowState().card
    assert (c.name, c.license, c.sends_data, c.trains, c.regimes) == (
        "FlowState",
        "Apache-2.0",
        False,
        False,
        (Regime.HISTORY,),
    )
    assert FlowState("r1.1").card.name == "FlowState-r1.1"
    assert FlowState().levels == LEVELS


def test_batches_split_by_history_length_and_keep_the_order() -> None:
    ws = [_window(n, i) for i, n in enumerate([48, 48, 72, 72, 72, 48])]
    runs = list(_same_length(ws))
    assert [[w.unique_id for w in r] for r in runs] == [["s0", "s1"], ["s2", "s3", "s4"], ["s5"]]
    assert list(_same_length([])) == []


class _Fake:
    """Stands in for the model: point = the last value, quantiles = last value + level squared (a skewed band,
    whose weighted mean is not its median); records each batch."""

    def __init__(self) -> None:
        self.batches: list[tuple[int, ...]] = []

    def __call__(self, past_values: Any, **kw: Any) -> Any:
        import torch

        assert kw == {
            "scale_factor": 1.0,
            "prediction_length": H,
            "batch_first": True,
            "prediction_type": "mean",
        }
        self.batches.append(tuple(past_values.shape))
        last = past_values[:, -1, 0]
        point = last[:, None, None].repeat(1, H, 1)
        q = last[:, None, None, None] + torch.tensor(LEVELS)[None, :, None, None] ** 2
        return type("Out", (), {"prediction_outputs": point, "quantile_outputs": q.repeat(1, 1, H, 1)})


def test_mixed_history_lengths_are_forecast_in_order() -> None:
    """The first test days of a short series have less than the full context (what `analyze` gives)."""
    pytest.importorskip("torch")
    m = FlowState()
    m._model = fake = _Fake()
    ws = [_window(n, i) for i, n in enumerate([48, 72, 72, 48])]
    p, q = m.predict(ws), m.predict_quantiles(ws)
    assert p.shape == (4, H) and q.shape == (4, 9, H)
    np.testing.assert_allclose(p[:, 0], [0, 1, 2, 3])
    np.testing.assert_allclose(q[2, :, 5], 2 + np.asarray(LEVELS) ** 2, rtol=1e-6)
    assert fake.batches[:3] == [(1, 48, 1), (2, 72, 1), (1, 48, 1)]


def test_rolling_quantiles_takes_the_models_own_point() -> None:
    """FlowState's point is a weighted mean of its quantiles: `rolling_quantiles` (and so `analyze`) must give
    that, not the 0.5 level, which scores ~0.01 lower on the benchmark."""
    pytest.importorskip("torch")
    m = FlowState()
    m._model = _Fake()
    s = data.example_house(n_series=1, days=20)
    f = rolling_quantiles(m, DayAhead(s, test_start="2024-01-15", test_end="2024-01-17", context=168))
    q = f[[f"q{a:g}" for a in LEVELS]].to_numpy()
    w = 0.5 - np.abs(0.5 - np.asarray(LEVELS))
    np.testing.assert_allclose(f["yhat"], q @ (w / w.sum()), rtol=1e-12)
    assert list(f.columns)[-1] == "yhat" and len(f) == 3 * H
    assert (f["yhat"] - f["q0.5"]).abs().min() > 0.03  # skewed band: the median would be 0.04 lower
    skewed = np.array([[[0.0], [0.0], [0.0], [0.0], [1.0], [5], [5], [5], [5]]])
    assert FlowState.point_from_quantiles(skewed)[0, 0] == pytest.approx(5.5 / 2.5)  # median: 1.0


@pytest.fixture(scope="module")
def model() -> FlowState:
    pytest.importorskip("tsfm_public")
    m = FlowState()
    try:
        m._model = m._load()
    except OSError as e:  # not in the cache, and offline
        pytest.skip(f"FlowState weights not in the Hugging Face cache: {e}")
    return m


def _comum() -> ModuleType:
    sys.path.insert(0, str(BENCH / "scripts"))
    return importlib.import_module("comum")


@pytest.mark.parametrize("case", CASES)
def test_flowstate_regenerates_the_benchmark_and_the_band_pilot(model: FlowState, case: str) -> None:
    """Checked 2026-10-16: every window of the three cases (casas_cons 1820, casas_prod 920, usinas 598; ~44
    min with PROSUMER_FULL=1) gives the saved quantiles and points EXACTLY (max |dif| 0.0; batches of 128 in
    the benchmark's order). The first windows alone form another batch: seen <= 4.2e-7 kWh (64 windows).
    `point_from_quantiles` vs the model's point: <= 8.9e-7 kWh (float64 vs float32 sum)."""
    full = os.environ.get("PROSUMER_FULL") == "1"
    if case != "casas_cons" and not full:
        pytest.skip("set PROSUMER_FULL=1 for every window of the three cases")
    pilot = BENCH / "resultados" / "pilotos" / f"FlowState-quantis__{case}__A.parquet"
    saved_point = BENCH / "resultados" / "previsoes" / f"FlowState__{case}__A.parquet"
    if not (BENCH / "dados" / "casas_horario.parquet").exists() or not pilot.exists():
        pytest.skip("benchmark data or the FlowState band pilot missing")
    comum = _comum()
    task = comum.tarefa(comum.carrega(case), case, contexto=comum.CONTEXTO_FM)
    ws = task.windows()[: None if full else 32]
    tz = comum.FUSO[case]

    q = model.predict_quantiles(ws)
    ours = pd.concat(
        pd.DataFrame({"unique_id": w.unique_id, "ds": w.timestamps, "q": a, "valor": q[i, k]})
        for i, w in enumerate(ws)
        for k, a in enumerate(LEVELS)
    )
    saved = pd.read_parquet(pilot)
    saved["ds"] = saved["ds"].dt.tz_localize(tz)
    m = ours.merge(saved, on=["unique_id", "ds", "q"], how="left", suffixes=("", "_saved"))
    assert len(m) == len(ours) and m["valor_saved"].notna().all()
    if full:
        assert len(saved) == len(ours), "the same series-hours must be forecast"
    np.testing.assert_allclose(m["valor"], m["valor_saved"], rtol=0, atol=ATOL)

    p = model.predict(ws)
    ours_p = pd.concat(
        pd.DataFrame({"unique_id": w.unique_id, "ds": w.timestamps, "yhat": p[i]}) for i, w in enumerate(ws)
    )
    saved_p = pd.read_parquet(saved_point)
    saved_p["ds"] = saved_p["ds"].dt.tz_localize(tz)
    mp = ours_p.merge(
        saved_p[["unique_id", "ds", "yhat"]], on=["unique_id", "ds"], how="left", suffixes=("", "_s")
    )
    assert len(mp) == len(ours_p) and mp["yhat_s"].notna().all()
    if full:
        assert len(saved_p) == len(ours_p)
    np.testing.assert_allclose(mp["yhat"], mp["yhat_s"], rtol=0, atol=ATOL)
    # the point is the weighted mean of the quantiles (as in `rolling_quantiles`, `analyze`), not the median
    pq = FlowState.point_from_quantiles(q)
    np.testing.assert_allclose(pq, p, rtol=0, atol=ATOL)
    assert np.abs(q[:, 4] - p).max() > 1e-3
    dq, dp = (m["valor"] - m["valor_saved"]).abs(), (mp["yhat"] - mp["yhat_s"]).abs()
    print(
        f"FlowState {case}: {len(ws)} windows; quantiles max {dq.max():.2e} mean {dq.mean():.2e}; point max "
        f"{dp.max():.2e} mean {dp.mean():.2e}; point_from_quantiles - point max {np.abs(pq - p).max():.2e}; "
        f"|median - point| max {np.abs(q[:, 4] - p).max():.3f}"
    )


def test_analyze_takes_flowstate_as_a_point_row_and_a_band(model: FlowState) -> None:
    s = data.example_house(n_series=1, days=50)
    r = analyze(s, test_days=7, models=[model])
    assert r.forecast is not None and r.bands is not None
    f = r.forecast.set_index("forecast")
    assert f.loc["FlowState", "regime"] == "A" and np.isfinite(f.loc["FlowState", "skill"])
    assert {"FlowState", "FlowState+conformal"} <= set(r.bands["source"])
