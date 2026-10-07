"""Regressao contra o benchmark v2: a biblioteca tem de reproduzir os numeros publicados.

Recalcula, a partir das previsoes gravadas em `experimentos/testes_previsao/resultados/previsoes/`, todas
as linhas de `resultados/metricas.csv` (o que o TCC relata) usando `prossumidor.metricas`, e exige
igualdade numerica. E o criterio da etapa E3 da proposta ("diferenca <= 0,005 de skill") virando teste;
aqui a tolerancia e de arredondamento de ponto flutuante, porque as contas sao as mesmas.

O IC 95% fica com tolerancia maior de proposito: o `05_avalia.py` usa um unico gerador para todos os
modelos (o IC de cada um depende da ordem em que os arquivos foram lidos), e a biblioteca semeia cada
chamada. A diferenca observada e de ~0,005.

Os dados sao de terceiros (usinas) e ficam so no repositorio privado: sem eles, o modulo inteiro e pulado.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prossumidor import metricas as pm

BENCH = Path(__file__).resolve().parents[1] / "experimentos" / "testes_previsao"
DADOS, RES = BENCH / "dados", BENCH / "resultados"
PREV = RES / "previsoes"

pytestmark = pytest.mark.skipif(
    not (RES / "metricas.csv").exists() or not (DADOS / "usinas_horario.parquet").exists(),
    reason="dados do benchmark ausentes (ficam so no repositorio privado)",
)

# Copia congelada de comum.CASOS e 05_avalia.REF.
CASOS = {
    "usinas": ("2025-08-01", "2026-05-31 23:00"),
    "casas_prod": ("2020-10-01", "2020-12-31 23:00"),
    "casas_cons": ("2020-10-01", "2020-12-31 23:00"),
}
REF = {"usinas": "persist_ceu_claro", "casas_prod": "persist_24h", "casas_cons": "persist_24h"}
CHAVES = ["unique_id", "ds"]
METRICAS = ["nMAE", "nRMSE", "MBE", "RMSE", "nMAE_diario", "R2", "R2_diario"]


def _le_metricas() -> pd.DataFrame:
    if not (RES / "metricas.csv").exists():
        return pd.DataFrame(columns=["caso", "modelo", "regime"])
    return pd.read_csv(RES / "metricas.csv", sep=";", decimal=",", encoding="utf-8-sig")


PUBLICADO = _le_metricas()
COMBINACOES = list(PUBLICADO[["caso", "modelo", "regime"]].itertuples(index=False, name=None))


@cache
def real_avaliado(caso: str) -> pd.DataFrame:
    """Alvo nas horas avaliadas. Copia de `05_avalia.real` + `comum.carrega` (regime A).

    TODO(E2): quando a mascara de horas avaliadas for portada para `prossumidor.protocolo`, trocar esta
    copia pela funcao da biblioteca; o teste passa a cobrir tambem a mascara.
    """
    ini, fim = CASOS[caso]
    if caso == "usinas":
        d = pd.read_parquet(DADOS / "usinas_horario.parquet").rename(columns={"serie": "unique_id"})
        d["y"] = d["y_Wh"] / 1000.0
    else:
        c = pd.read_parquet(DADOS / "casas_horario.parquet")
        col = "prod_kWh" if caso == "casas_prod" else "cons_kWh"
        d = c.rename(columns={"casa": "unique_id", col: "y"})
        if caso == "casas_prod":  # 10 das 20 casas nao tem FV
            com_fv = d.groupby("unique_id")["y"].sum()
            d = d[d["unique_id"].isin(com_fv[com_fv > 0].index)]
    d = d[(d["ds"] <= fim) & (d["ds"] >= ini)].copy()
    if caso == "usinas":
        d["avalia"] = d["poa_ceu_claro"] > 0
    elif caso == "casas_prod":
        perfil = d.groupby(d["ds"].dt.hour)["y"].mean()
        d["avalia"] = d["ds"].dt.hour.map(perfil > 0.01 * perfil.max()).astype(bool)
    else:
        d["avalia"] = True
    return d.loc[d["avalia"], [*CHAVES, "y"]].reset_index(drop=True)


def _previsao(modelo: str, caso: str, regime: str) -> pd.DataFrame:
    p = pd.read_parquet(PREV / f"{modelo}__{caso}__{regime}.parquet")[[*CHAVES, "yhat"]]
    return p.assign(yhat=p["yhat"].clip(lower=0))  # previsao negativa vira zero (05_avalia)


@cache
def referencia(caso: str) -> pd.DataFrame:
    """A referencia e sempre a do regime A, inclusive para comparar os regimes B e C."""
    return _previsao(REF[caso], caso, "A").merge(real_avaliado(caso), on=CHAVES, validate="one_to_one")


def _alinhado(caso: str, modelo: str, regime: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pm.alinha(_previsao(modelo, caso, regime), real_avaliado(caso), referencia(caso))


def _publicado(caso: str, modelo: str, regime: str) -> pd.Series:
    linha = PUBLICADO[(PUBLICADO.caso == caso) & (PUBLICADO.modelo == modelo) & (PUBLICADO.regime == regime)]
    assert len(linha) == 1, f"{modelo}/{caso}/{regime} aparece {len(linha)} vezes em metricas.csv"
    return linha.iloc[0]


def test_ha_o_que_comparar() -> None:
    # Guarda contra o teste parametrizado "passar" vazio se o CSV mudar de formato.
    assert len(COMBINACOES) >= 100
    assert set(PUBLICADO.caso) == set(CASOS)


@pytest.mark.parametrize(("caso", "modelo", "regime"), COMBINACOES, ids=lambda v: str(v))
def test_reproduz_metricas_publicadas(caso: str, modelo: str, regime: str) -> None:
    m, ref = _alinhado(caso, modelo, regime)
    pub = _publicado(caso, modelo, regime)
    assert len(m) == pub.horas, "numero de horas avaliadas mudou"
    obtido = pm.metricas(m) | {"skill": pm.skill(m, ref)}
    for nome in [*METRICAS, "skill"]:
        assert obtido[nome] == pytest.approx(pub[nome], rel=1e-9, abs=1e-12), nome


# O IC e caro (1000 reamostragens): confere uma amostra, um por caso e regime principal.
AMOSTRA_IC = [
    ("usinas", "TiRex-2", "A"),
    ("usinas", "LightGBM", "B"),
    ("usinas", "LightGBM", "C"),
    ("casas_prod", "TiRex-2", "A"),
    ("casas_cons", "LightGBM", "A"),
]


@pytest.mark.parametrize(("caso", "modelo", "regime"), AMOSTRA_IC, ids=lambda v: str(v))
def test_ic95_proximo_do_publicado(caso: str, modelo: str, regime: str) -> None:
    m, ref = _alinhado(caso, modelo, regime)
    pub = _publicado(caso, modelo, regime)
    lo, hi = pm.skill_ic95(m, ref)
    assert lo < pm.skill(m, ref) < hi
    assert np.allclose([lo, hi], [pub.skill_ic95_inf, pub.skill_ic95_sup], atol=0.01)
