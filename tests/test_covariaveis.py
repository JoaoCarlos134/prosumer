"""Teste de contrato das covariaveis: um adaptador que recebe clima tem de USAR o clima.

Esta e a regressao do TiDE. No benchmark ele ficou duas versoes (v1 e v2) com skill +0,07 nos regimes
com clima, contra +0,47 a +0,49 dos pares, porque o `MLPResidual` do NeuralForecast termina num
LayerNorm sobre `temporal_width` (= o numero de exogenas) aplicado em CADA hora: isso tira media e
escala das variaveis de clima hora a hora e apaga a amplitude, que e exatamente o sinal de "quanto sol
faz". As previsoes de B e C ficaram com correlacao 0,999 entre si — o modelo quase nao reagia a troca
de clima perfeito por previsao real — enquanto os pares ficavam em 0,96.

O defeito passou porque ninguem testava o encanamento, so o resultado agregado. Qualquer adaptador
novo que aceite covariaveis futuras deve passar nos dois testes daqui.
"""

from __future__ import annotations

import numpy as np
import pytest

from prossumidor import dados

# Correlacao acima disto entre duas previsoes feitas com climas DIFERENTES significa que o modelo
# esta ignorando a covariavel. O TiDE defeituoso dava 0,999; os modelos sadios, ~0,96.
LIMITE_INSENSIBILIDADE = 0.995


def _ajusta_preve(usa_clima: bool, y: np.ndarray, poa: np.ndarray) -> np.ndarray:
    """Adaptador de brinquedo, no lugar de um modelo real.

    `usa_clima=True` imita um adaptador correto (le a covariavel); `False` imita o defeituoso, que
    ignora a covariavel e so repete o nivel recente.
    """
    if usa_clima:
        escala = float(np.sum(y * poa) / max(float(np.sum(poa * poa)), 1e-12))
        return escala * poa
    return np.full_like(poa, float(np.mean(y)))


def test_dados_de_exemplo_ligam_geracao_ao_clima() -> None:
    """Pre-condicao do teste: a geracao sintetica tem de ser funcao do clima, senao nada se detecta."""
    serie, clima = dados.exemplo_usina(series=1, dias=60)
    j = serie.quadro.merge(clima, on=["unique_id", "ds"])
    sol = j[j["poa_ceu_claro"] > 0]
    assert np.corrcoef(sol["y"], sol["poa_estimada"])[0, 1] > 0.99


def test_adaptador_que_usa_clima_reage_a_troca_de_clima() -> None:
    """Dois climas diferentes tem de produzir previsoes diferentes. O TiDE falhava exatamente aqui."""
    serie, clima = dados.exemplo_usina(series=1, dias=60, semente=1)
    _, clima_outro = dados.exemplo_usina(series=1, dias=60, semente=999)
    j = serie.quadro.merge(clima, on=["unique_id", "ds"]).merge(
        clima_outro[["unique_id", "ds", "poa_estimada"]], on=["unique_id", "ds"], suffixes=("", "_alt")
    )
    sol = j[j["poa_ceu_claro"] > 0]
    y = sol["y"].to_numpy()

    bom_a = _ajusta_preve(True, y, sol["poa_estimada"].to_numpy())
    bom_b = _ajusta_preve(True, y, sol["poa_estimada_alt"].to_numpy())
    r_bom = float(np.corrcoef(bom_a, bom_b)[0, 1])
    assert r_bom < LIMITE_INSENSIBILIDADE, (
        f"previsoes com climas diferentes tem correlacao {r_bom:.4f}: "
        "o adaptador nao esta usando a covariavel"
    )


def test_o_teste_pega_um_adaptador_que_ignora_o_clima() -> None:
    """Meta-teste: sem isto, o teste acima poderia estar sempre passando por acidente."""
    serie, clima = dados.exemplo_usina(series=1, dias=60, semente=1)
    _, clima_outro = dados.exemplo_usina(series=1, dias=60, semente=999)
    j = serie.quadro.merge(clima, on=["unique_id", "ds"]).merge(
        clima_outro[["unique_id", "ds", "poa_estimada"]], on=["unique_id", "ds"], suffixes=("", "_alt")
    )
    sol = j[j["poa_ceu_claro"] > 0]
    y = sol["y"].to_numpy()

    ruim_a = _ajusta_preve(False, y, sol["poa_estimada"].to_numpy())
    ruim_b = _ajusta_preve(False, y, sol["poa_estimada_alt"].to_numpy())
    # Ignorar o clima produz a MESMA previsao: constante, correlacao indefinida ou 1.
    assert np.allclose(ruim_a, ruim_b), "o adaptador surdo deveria dar previsoes identicas"


def test_adaptador_com_clima_erra_menos_que_sem_clima() -> None:
    """O outro lado do contrato: receber a covariavel tem de melhorar o erro, nao so mudar a saida."""
    serie, clima = dados.exemplo_usina(series=1, dias=60)
    j = serie.quadro.merge(clima, on=["unique_id", "ds"])
    sol = j[j["poa_ceu_claro"] > 0]
    y = sol["y"].to_numpy()
    poa = sol["poa_estimada"].to_numpy()
    rmse_com = float(np.sqrt(np.mean((_ajusta_preve(True, y, poa) - y) ** 2)))
    rmse_sem = float(np.sqrt(np.mean((_ajusta_preve(False, y, poa) - y) ** 2)))
    assert rmse_com < rmse_sem


@pytest.mark.parametrize("semente", [0, 1, 2])
def test_buracos_nao_viram_zero(semente: int) -> None:
    """Patologia dos dados reais: buraco tem de ficar invalido, nunca zero silencioso."""
    serie = dados.exemplo_casa(series=2, dias=30)
    furada = dados.com_buracos(serie, fracao=0.1, semente=semente)
    invalidos = ~furada.quadro["valido"]
    assert invalidos.any()
    assert furada.quadro.loc[invalidos, "y"].isna().all(), "invalido com valor numerico mascara o buraco"
    assert float(furada.cobertura().min()) < 1.0
