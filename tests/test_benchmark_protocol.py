"""The benchmark's protocol now comes from the library: it must give EXACTLY what the frozen v2 code gave.

Step E2/E3 of the plan: `experimentos/testes_previsao/scripts/comum.py` stopped implementing folds, test days and
windows itself and calls `prosumer.protocol`. The functions below are verbatim copies of the v2 implementation that
produced every published forecast (comum.py up to 2026-10-11); they are the reference and must never be edited.
Equality is checked on the real data of the three cases, in every regime with covariates, with the long context of
the foundation models and the short one of the trained networks.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "experimentos" / "testes_previsao" / "scripts"
pytestmark = pytest.mark.skipif(not (SCRIPTS.parent / "dados").exists(), reason="benchmark data not present")


@pytest.fixture(scope="module")
def comum():  # type: ignore[no-untyped-def]
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("comum")


# ---------------------------------------------------------------- frozen v2 reference (do not edit)
H = 24
EXOG = ["poa_ceu_claro", "ghi_horario", "poa_estimada", "temp_ar_horaria"]
REFIT_DIAS = {"usinas": 61, "casas_prod": 31, "casas_cons": 31}
CASOS = {
    "usinas": dict(ini="2025-08-01", fim="2026-05-31 23:00"),
    "casas_prod": dict(ini="2020-10-01", fim="2020-12-31 23:00"),
    "casas_cons": dict(ini="2020-10-01", fim="2020-12-31 23:00"),
}


def _dobras_v2(caso):  # type: ignore[no-untyped-def]
    ini, fim = pd.Timestamp(CASOS[caso]["ini"]), pd.Timestamp(CASOS[caso]["fim"]).normalize()
    out, a = [], ini
    while a <= fim:
        b = min(a + pd.Timedelta(days=REFIT_DIAS[caso] - 1), fim)
        out.append((a, b + pd.Timedelta("23h")))
        a = b + pd.Timedelta(days=1)
    return out


def _dias_teste_v2(d, caso):  # type: ignore[no-untyped-def]
    t = d[(d.ds >= CASOS[caso]["ini"]) & (d.ds <= CASOS[caso]["fim"])].copy()
    t["dia"] = t.ds.dt.normalize()
    ok = t.groupby(["unique_id", "dia"]).y.agg(lambda s: s.notna().sum() == H and len(s) == H)
    return [k for k, v in ok.items() if v]


def _janelas_v2(d, caso, contexto, exog=False):  # type: ignore[no-untyped-def]
    out = []
    series = {u: g.set_index("ds") for u, g in d.groupby("unique_id")}
    for uid, dia in _dias_teste_v2(d, caso):
        g = series[uid]
        hist = g.loc[: dia - pd.Timedelta("1h")].tail(contexto)
        w = dict(
            unique_id=uid,
            dia=dia,
            ds_fut=pd.date_range(dia, periods=H, freq="h"),
            y=hist.y.interpolate(limit_direction="both").fillna(0.0).to_numpy(np.float32),
        )
        if exog:
            fut = g.loc[dia : dia + pd.Timedelta("23h")]
            w["x_pass"] = {c: hist[c].to_numpy(np.float32) for c in EXOG}
            w["x_fut"] = {c: fut[c].to_numpy(np.float32) for c in EXOG}
        out.append(w)
    return out


# ---------------------------------------------------------------- equality
@pytest.mark.parametrize("caso", ["usinas", "casas_prod", "casas_cons"])
def test_folds_are_identical(comum, caso) -> None:  # type: ignore[no-untyped-def]
    assert comum.dobras(caso) == _dobras_v2(caso)


@pytest.mark.parametrize(
    ("caso", "regime", "contexto"),
    [
        ("usinas", "A", 1024),
        ("usinas", "B", 1024),
        ("usinas", "C", 168),
        ("casas_prod", "A", 1024),
        ("casas_prod", "B", 168),
        ("casas_cons", "A", 1024),
        ("casas_cons", "B", 168),
    ],
)
def test_test_days_and_windows_are_identical(comum, caso, regime, contexto) -> None:  # type: ignore[no-untyped-def]
    d = comum.carrega(caso, regime)
    assert comum.dias_teste(d, caso) == _dias_teste_v2(d, caso)
    exog = regime != "A"
    novo = comum.janelas(d, caso, contexto=contexto, exog=exog)
    velho = _janelas_v2(d, caso, contexto, exog=exog)
    assert len(novo) == len(velho)
    for a, b in zip(novo, velho, strict=True):
        assert (a["unique_id"], a["dia"]) == (b["unique_id"], b["dia"])
        assert a["ds_fut"].equals(b["ds_fut"])
        assert a["y"].dtype == b["y"].dtype
        np.testing.assert_array_equal(a["y"], b["y"])
        if exog:
            for parte in ("x_pass", "x_fut"):
                assert a[parte].keys() == b[parte].keys()
                for c in EXOG:
                    np.testing.assert_array_equal(a[parte][c], b[parte][c])


def _real_v2(comum, caso):  # type: ignore[no-untyped-def]
    d = comum.carrega(caso)
    d = d[(d.ds >= CASOS[caso]["ini"])]
    if caso == "usinas":
        d["avalia"] = d.poa_ceu_claro > 0
    elif caso == "casas_prod":
        perfil = d.groupby(d.ds.dt.hour).y.mean()
        d["avalia"] = d.ds.dt.hour.map(perfil > 0.01 * perfil.max())
    else:
        d["avalia"] = True
    return d[["unique_id", "ds", "y", "avalia"]]


def _normaliza_v2(df, corte, colunas):  # type: ignore[no-untyped-def]
    out, parametros = df.copy(), {}
    for uid, g in df.groupby("unique_id", sort=False):
        valido = g.ds < corte
        if "available_mask" in g:
            valido &= g.available_mask > 0
        treino = g.loc[valido, colunas]
        if treino.empty or not np.isfinite(treino.to_numpy(float)).all():
            raise ValueError(f"Treino vazio ou nao finito para normalizacao: {uid}")
        media = treino.mean()
        desvio = treino.std(ddof=0).replace(0, 1.0)
        out.loc[g.index, colunas] = (g[colunas] - media) / desvio
        parametros[uid] = {c: (float(media[c]), float(desvio[c])) for c in colunas}
    return out, parametros


@pytest.mark.parametrize("caso", ["usinas", "casas_prod", "casas_cons"])
def test_evaluated_hours_are_identical(comum, caso) -> None:  # type: ignore[no-untyped-def]
    av = importlib.import_module("05_avalia")
    novo, velho = av.real(caso), _real_v2(comum, caso)
    pd.testing.assert_frame_equal(novo.reset_index(drop=True), velho.reset_index(drop=True), check_dtype=False)
    assert novo.avalia.dtype == bool


@pytest.mark.parametrize(("caso", "regime"), [("usinas", "B"), ("casas_cons", "A")])
def test_standardization_is_identical(comum, caso, regime) -> None:  # type: ignore[no-untyped-def]
    d = comum.carrega(caso, regime)
    cols = ["y"] + (EXOG if regime != "A" else [])
    d = d.assign(available_mask=d.y.notna().astype(float), y=d.y.fillna(0.0))
    corte = pd.Timestamp(CASOS[caso]["ini"]) - pd.Timedelta(hours=720)
    a, pa = comum.normaliza_por_treino(d, corte, cols)
    b, pb = _normaliza_v2(d, corte, cols)
    pd.testing.assert_frame_equal(a, b)
    assert pa == pb
