"""Regression against the v2 benchmark: the library must reproduce the published numbers.

Recomputes, from the forecasts saved in `experimentos/testes_previsao/resultados/previsoes/`, every row
of `resultados/metricas.csv` (what the thesis reports) using `prosumer.metrics`, and requires numerical
equality. It is the proposal's step E3 criterion ("difference <= 0.005 skill") turned into a test; here
the tolerance is floating-point rounding, because the computations are the same.

The 95% CI has a looser tolerance on purpose: `05_avalia.py` uses a single generator for every model
(each one's CI depends on the order the files were read), and the library seeds each call. The observed
difference is ~0.005.

The benchmark files keep their Portuguese names and columns (caso, modelo, regime, nMAE_diario...): they
are frozen data. The plant data belongs to third parties and lives only in the private repository:
without it, the whole module is skipped.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prosumer import metrics as pm

BENCH = Path(__file__).resolve().parents[1] / "experimentos" / "testes_previsao"
DATA, RES = BENCH / "dados", BENCH / "resultados"
FORECASTS = RES / "previsoes"

pytestmark = pytest.mark.skipif(
    not (RES / "metricas.csv").exists() or not (DATA / "usinas_horario.parquet").exists(),
    reason="benchmark data missing (it lives only in the private repository)",
)

# Frozen copy of comum.CASOS and 05_avalia.REF.
CASES = {
    "usinas": ("2025-08-01", "2026-05-31 23:00"),
    "casas_prod": ("2020-10-01", "2020-12-31 23:00"),
    "casas_cons": ("2020-10-01", "2020-12-31 23:00"),
}
REF = {"usinas": "persist_ceu_claro", "casas_prod": "persist_24h", "casas_cons": "persist_24h"}
KEYS = ["unique_id", "ds"]
# column in metricas.csv -> key returned by prosumer.metrics.metrics
METRICS = {
    "nMAE": "nMAE",
    "nRMSE": "nRMSE",
    "MBE": "MBE",
    "RMSE": "RMSE",
    "nMAE_diario": "nMAE_daily",
    "R2": "R2",
    "R2_diario": "R2_daily",
}


def _read_metrics() -> pd.DataFrame:
    if not (RES / "metricas.csv").exists():
        return pd.DataFrame(columns=["caso", "modelo", "regime"])
    return pd.read_csv(RES / "metricas.csv", sep=";", decimal=",", encoding="utf-8-sig")


PUBLISHED = _read_metrics()
COMBINATIONS = list(PUBLISHED[["caso", "modelo", "regime"]].itertuples(index=False, name=None))


@cache
def evaluated_actual(case: str) -> pd.DataFrame:
    """Target on the evaluated hours: `comum.carrega` (regime A) re-read here + the LIBRARY's
    `evaluated_mask`.

    The mask comes from `prosumer.metrics.evaluated_mask` (ported 2026-10-11), so this test now covers it too;
    `tests/test_benchmark_protocol.py` checks it against the frozen v2 copy of `05_avalia.real`.
    """
    start, end = CASES[case]
    if case == "usinas":
        d = pd.read_parquet(DATA / "usinas_horario.parquet").rename(columns={"serie": "unique_id"})
        d["y"] = d["y_Wh"] / 1000.0
    else:
        c = pd.read_parquet(DATA / "casas_horario.parquet")
        col = "prod_kWh" if case == "casas_prod" else "cons_kWh"
        d = c.rename(columns={"casa": "unique_id", col: "y"})
        if case == "casas_prod":  # 10 of the 20 houses have no PV
            with_pv = d.groupby("unique_id")["y"].sum()
            d = d[d["unique_id"].isin(with_pv[with_pv > 0].index)]
    d = d[(d["ds"] <= end) & (d["ds"] >= start)].copy()
    d["evaluated"] = pm.evaluated_mask(
        d, {"usinas": "sun", "casas_prod": "profile", "casas_cons": "all"}[case]
    )
    return d.loc[d["evaluated"], [*KEYS, "y"]].reset_index(drop=True)


def _forecast(model: str, case: str, regime: str) -> pd.DataFrame:
    p = pd.read_parquet(FORECASTS / f"{model}__{case}__{regime}.parquet")[[*KEYS, "yhat"]]
    return p.assign(yhat=p["yhat"].clip(lower=0))  # negative forecasts become zero (05_avalia)


@cache
def reference(case: str) -> pd.DataFrame:
    """The reference is always regime A's, including when comparing regimes B and C."""
    return _forecast(REF[case], case, "A").merge(evaluated_actual(case), on=KEYS, validate="one_to_one")


def _aligned(case: str, model: str, regime: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pm.align(_forecast(model, case, regime), evaluated_actual(case), reference(case))


def _published(case: str, model: str, regime: str) -> pd.Series:
    row = PUBLISHED[(PUBLISHED.caso == case) & (PUBLISHED.modelo == model) & (PUBLISHED.regime == regime)]
    assert len(row) == 1, f"{model}/{case}/{regime} appears {len(row)} times in metricas.csv"
    return row.iloc[0]


def test_there_is_something_to_compare() -> None:
    # Guard against the parametrised test "passing" empty if the CSV changes format.
    assert len(COMBINATIONS) >= 100
    assert set(PUBLISHED.caso) == set(CASES)


@pytest.mark.parametrize(("case", "model", "regime"), COMBINATIONS, ids=lambda v: str(v))
def test_reproduces_published_metrics(case: str, model: str, regime: str) -> None:
    m, ref = _aligned(case, model, regime)
    pub = _published(case, model, regime)
    assert len(m) == pub.horas, "number of evaluated hours changed"
    got = pm.metrics(m) | {"skill": pm.skill(m, ref)}
    for column, key in [*METRICS.items(), ("skill", "skill")]:
        assert got[key] == pytest.approx(pub[column], rel=1e-9, abs=1e-12), column


# The CI is expensive (1000 resamples): check a sample, one per case and main regime.
CI_SAMPLE = [
    ("usinas", "TiRex-2", "A"),
    ("usinas", "LightGBM", "B"),
    ("usinas", "LightGBM", "C"),
    ("casas_prod", "TiRex-2", "A"),
    ("casas_cons", "LightGBM", "A"),
]


@pytest.mark.parametrize(("case", "model", "regime"), CI_SAMPLE, ids=lambda v: str(v))
def test_ci95_close_to_published(case: str, model: str, regime: str) -> None:
    m, ref = _aligned(case, model, regime)
    pub = _published(case, model, regime)
    lo, hi = pm.skill_ci95(m, ref)
    assert lo < pm.skill(m, ref) < hi
    assert np.allclose([lo, hi], [pub.skill_ic95_inf, pub.skill_ic95_sup], atol=0.01)


def test_real_houses_load_in_dublin_time() -> None:
    """The 20 houses are in Dublin local time on a gap-free grid (checked 2026-10-07 by the ~1 h jump in
    the timing of PV generation on 29/03). Before the fix they broke with pandas' raw ValueError."""
    from prosumer import EnergySeries

    c = pd.read_parquet(DATA / "casas_horario.parquet")
    q = c.rename(columns={"casa": "unique_id", "cons_kWh": "y"})[["unique_id", "ds", "y"]]
    with pytest.warns(UserWarning, match="40 row"):  # 29/03 01:00 and 25/10 01:00 in each of the 20
        s = EnergySeries.from_dataframe(
            q, unit="kWh", quantity="consumption", tz="Europe/Dublin", freq="h", dst="drop"
        )
    assert len(s) == len(q) - 40 and len(s.series) == 20
    for _, g in s.frame.groupby("unique_id"):
        steps = g["ds"].diff().dropna().value_counts()
        # all hourly, except the 3 h gap left by the dropped row of 25/10
        assert steps.get(pd.Timedelta("1h")) == len(g) - 2
        assert steps.get(pd.Timedelta("3h")) == 1


@pytest.mark.parametrize("regime", ["A", "B"])
def test_benchmark_corrected_median_is_the_library_one(regime: str) -> None:
    """07_ensemble.py repeats the algorithm of postprocessing.correct_bias (it runs without the library).
    Both must give the same forecast, or the published number is not what the library delivers."""
    from prosumer import postprocessing

    med = pd.read_parquet(FORECASTS / f"Ensemble-mediana__casas_cons__{regime}.parquet")[[*KEYS, "yhat"]]
    saved = pd.read_parquet(FORECASTS / f"Ensemble-mediana-corrigida__casas_cons__{regime}.parquet")[
        [*KEYS, "yhat"]
    ]
    c = pd.read_parquet(DATA / "casas_horario.parquet").rename(columns={"casa": "unique_id", "cons_kWh": "y"})
    actual = c.loc[c["ds"] <= CASES["casas_cons"][1], [*KEYS, "y"]]
    lib = postprocessing.correct_bias(med, actual, quantity="consumption")
    j = saved.merge(lib, on=KEYS, suffixes=("_bench", "_lib"), validate="one_to_one")
    assert len(j) == len(saved) == len(med)
    assert np.allclose(j["yhat_bench"], j["yhat_lib"], rtol=1e-12, atol=1e-12)
