"""Metricas em varias resolucoes e correcao de vies: valores conhecidos por construcao."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prossumidor import metricas, posprocessamento


def _dias(n_dias: int, *, series: tuple[str, ...] = ("a",), inicio: str = "2024-01-01") -> pd.DataFrame:
    ds = pd.date_range(inicio, periods=24 * n_dias, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    partes = [pd.DataFrame({"unique_id": u, "ds": ds, "y": 1.0 + rng.random(len(ds))}) for u in series]
    return pd.concat(partes, ignore_index=True)


# ---------------------------------------------------------------------- por_resolucao
def test_previsao_perfeita_e_perfeita_em_todo_nivel() -> None:
    y = _dias(10)
    prev = y.assign(yhat=y["y"])
    ref = y.assign(yhat=y["y"] * 1.3)
    r = metricas.por_resolucao(prev, ref).set_index("nivel")
    assert list(r.index) == ["hora", "dia_noite", "pico_17_21", "dia"]
    assert np.allclose(r["skill"], 1.0) and np.allclose(r["R2"], 1.0) and np.allclose(r["nRMSE"], 0.0)


def test_erro_que_se_cancela_no_dia_some_no_total_do_dia() -> None:
    # +0,5 nas horas pares e -0,5 nas impares: erro por hora, zero no total do dia.
    y = _dias(10)
    sinal = np.where(y["ds"].dt.hour % 2 == 0, 0.5, -0.5)
    prev = y.assign(yhat=y["y"] + sinal)
    ref = y.assign(yhat=y["y"] * 1.2)
    r = metricas.por_resolucao(prev, ref).set_index("nivel")
    assert r.loc["hora", "skill"] < 1.0
    assert r.loc["dia", "skill"] == pytest.approx(1.0)
    assert r.loc["dia", "nRMSE"] == pytest.approx(0.0, abs=1e-12)


def test_vies_proporcional_e_o_mesmo_em_todo_nivel() -> None:
    y = _dias(8)
    prev = y.assign(yhat=y["y"] * 0.8)  # 20% abaixo em toda hora
    r = metricas.por_resolucao(prev, y.assign(yhat=y["y"])).set_index("nivel")
    assert np.allclose(r["MBE"], -0.2)


def test_contagem_de_blocos_por_nivel() -> None:
    y = _dias(5, series=("a", "b"))
    r = metricas.por_resolucao(y.assign(yhat=y["y"]), y.assign(yhat=y["y"] + 1)).set_index("nivel")
    assert r.loc["hora", "blocos"] == 5 * 24 * 2
    assert r.loc["dia_noite", "blocos"] == 5 * 2 * 2
    assert r.loc["pico_17_21", "blocos"] == 5 * 2
    assert r.loc["dia", "blocos"] == 5 * 2


def test_blocos_incompletos_sao_recusados() -> None:
    with pytest.raises(ValueError, match="horas"):
        metricas.por_blocos({h: "ponta" for h in range(18, 21)})


def test_tarifa_branca_como_blocos_proprios() -> None:
    # Exemplo de uso brasileiro: ponta 18-21 h, intermediario 17 h e 21 h, fora de ponta o resto.
    branca = {h: "fora" for h in range(24)} | {17: "inter", 21: "inter"} | {h: "ponta" for h in range(18, 21)}
    y = _dias(3)
    r = metricas.por_resolucao(
        y.assign(yhat=y["y"]), y.assign(yhat=y["y"] + 1), {"branca": metricas.por_blocos(branca)}
    )
    assert r.loc[0, "blocos"] == 3 * 3


# ---------------------------------------------------------------------- corrige_vies
def _consumo_com_vies(n_dias: int, fator_real: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    y = _dias(n_dias)
    return y.assign(yhat=y["y"] / fator_real)[["unique_id", "ds", "yhat"]], y


def test_vies_constante_e_removido_depois_do_minimo_de_dias() -> None:
    prev, real = _consumo_com_vies(30, fator_real=1.25)  # previsao 20% abaixo
    c = posprocessamento.corrige_vies(prev, real, grandeza="consumo", dias=14, minimo=7)
    dia = c["ds"].dt.normalize()
    primeiros = dia < dia.min() + pd.Timedelta(days=7)
    assert (c.loc[primeiros, "fator"] == 1.0).all()  # sem historico suficiente: nao corrige
    j = c.merge(real, on=["unique_id", "ds"])
    assert np.allclose(j.loc[~primeiros.to_numpy(), "yhat"], j.loc[~primeiros.to_numpy(), "y"])


def test_correcao_nao_usa_o_proprio_dia() -> None:
    prev, real = _consumo_com_vies(20, fator_real=1.1)
    a = posprocessamento.corrige_vies(prev, real, grandeza="consumo")
    alterado = real.copy()
    ultimo = alterado["ds"].dt.normalize() == alterado["ds"].dt.normalize().max()
    alterado.loc[ultimo, "y"] *= 10  # muda so o ultimo dia
    b = posprocessamento.corrige_vies(prev, alterado, grandeza="consumo")
    assert np.allclose(a.loc[ultimo.to_numpy(), "yhat"], b.loc[ultimo.to_numpy(), "yhat"])


def test_fator_e_limitado() -> None:
    prev, real = _consumo_com_vies(20, fator_real=10.0)
    c = posprocessamento.corrige_vies(prev, real, grandeza="consumo", limites=(0.5, 2.0))
    assert c["fator"].max() == pytest.approx(2.0)


def test_geracao_e_bloqueada_por_padrao() -> None:
    prev, real = _consumo_com_vies(10, fator_real=1.1)
    with pytest.raises(ValueError, match="geracao"):
        posprocessamento.corrige_vies(prev, real, grandeza="geracao")
    assert len(posprocessamento.corrige_vies(prev, real, grandeza="geracao", permitir_geracao=True)) == len(
        prev
    )
