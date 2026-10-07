"""Metricas: conferidas contra valores conhecidos por construcao, nao contra "parece certo".

E aqui que os dados sinteticos valem mais que os reais: da para montar uma previsao com skill exato
e exigir que a metrica recupere aquele numero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prossumidor import dados, metricas


def _quadro(y: list[float], yhat: list[float], *, inicio: str = "2024-01-01") -> pd.DataFrame:
    idx = pd.date_range(inicio, periods=len(y), freq="h", tz="UTC")
    return pd.DataFrame({"unique_id": "a", "ds": idx, "y": y, "yhat": yhat})


def test_previsao_perfeita_tem_erro_zero_e_r2_um() -> None:
    df = _quadro([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])
    m = metricas.metricas(df)
    assert m["nMAE"] == pytest.approx(0.0)
    assert m["nRMSE"] == pytest.approx(0.0)
    assert m["MBE"] == pytest.approx(0.0)
    assert m["R2"] == pytest.approx(1.0)


def test_vies_tem_sinal_e_magnitude_conhecidos() -> None:
    """Subprever 20% tem de aparecer como MBE -0,2: foi o vies dos fundacionais no consumo."""
    y = [1.0, 2.0, 3.0, 4.0]
    df = _quadro(y, [v * 0.8 for v in y])
    m = metricas.metricas(df)
    assert m["MBE"] == pytest.approx(-0.2)
    assert m["nMAE"] == pytest.approx(0.2)


def test_skill_zero_quando_igual_a_referencia() -> None:
    df = _quadro([1.0, 2.0, 3.0, 4.0], [1.1, 2.1, 3.1, 4.1])
    ref = _quadro([1.0, 2.0, 3.0, 4.0], [1.1, 2.1, 3.1, 4.1])
    assert metricas.skill(df, ref) == pytest.approx(0.0)


def test_skill_meio_quando_o_erro_cai_a_metade() -> None:
    """skill = 1 - RMSE/RMSE_ref; metade do erro da exatamente 0,5."""
    y = [0.0, 0.0, 0.0, 0.0]
    df = _quadro(y, [0.5, -0.5, 0.5, -0.5])
    ref = _quadro(y, [1.0, -1.0, 1.0, -1.0])
    # y medio zero quebraria a normalizacao, mas o skill nao depende dela.
    assert metricas.skill(df, ref) == pytest.approx(0.5)


def test_skill_negativo_quando_pior_que_a_referencia() -> None:
    y = [0.0, 0.0]
    assert metricas.skill(_quadro(y, [2.0, -2.0]), _quadro(y, [1.0, -1.0])) == pytest.approx(-1.0)


def test_metricas_recusam_media_zero() -> None:
    """Normalizar por media zero daria infinito silencioso."""
    with pytest.raises(ValueError, match="Media do real"):
        metricas.metricas(_quadro([0.0, 0.0], [1.0, 1.0]))


def test_alinha_usa_so_horas_comuns_e_finitas() -> None:
    """Dois modelos avaliados em horas diferentes parecem comparaveis e nao sao."""
    real = pd.DataFrame(
        {
            "unique_id": "a",
            "ds": pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC"),
            "y": [1.0, 2.0, 3.0, 4.0],
        }
    )
    prev = real[["unique_id", "ds"]].assign(yhat=[1.0, np.nan, 3.0, 4.0])
    ref = real[["unique_id", "ds"]].assign(yhat=[1.0, 2.0, 3.0, np.nan])
    m, rr = metricas.alinha(prev, real, ref)
    assert len(m) == 2 and len(rr) == 2
    assert m["ds"].tolist() == rr["ds"].tolist()


def test_alinha_falha_em_vez_de_comparar_vazio() -> None:
    real = pd.DataFrame(
        {"unique_id": "a", "ds": pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"), "y": [1.0, 2.0]}
    )
    prev = real[["unique_id", "ds"]].assign(yhat=[np.nan, np.nan])
    with pytest.raises(ValueError, match="Sem horas finitas"):
        metricas.alinha(prev, real, real[["unique_id", "ds"]].assign(yhat=[1.0, 2.0]))


def test_alinha_recusa_chave_duplicada() -> None:
    real = pd.DataFrame(
        {"unique_id": "a", "ds": pd.to_datetime(["2024-01-01"] * 2, utc=True), "y": [1.0, 2.0]}
    )
    prev = real[["unique_id", "ds"]].assign(yhat=[1.0, 2.0])
    with pytest.raises(Exception, match=r"one_to_one|merge|unique"):
        metricas.alinha(prev, real, prev)


def test_ic_do_skill_contem_o_ponto_e_e_deterministico() -> None:
    serie = dados.exemplo_casa(series=2, dias=60)
    real = serie.apenas_validos()[["unique_id", "ds", "y"]]
    prev = dados.previsao_perfeita(serie)
    prev = prev.assign(yhat=prev["yhat"] * 0.9)
    ref = dados.previsao_persistencia(serie)
    m, rr = metricas.alinha(prev, real, ref.dropna())
    s = metricas.skill(m, rr)
    lo, hi = metricas.skill_ic95(m, rr, semente=42)
    assert lo <= s <= hi
    assert (lo, hi) == metricas.skill_ic95(m, rr, semente=42), "mesma semente tem de dar o mesmo IC"


def test_holm_nao_reduz_p_e_preserva_a_ordem() -> None:
    p = [0.001, 0.02, 0.3, 0.7]
    a = metricas.holm(p)
    assert np.all(a >= np.array(p)), "p ajustado nunca pode ser menor que o original"
    assert np.all(np.diff(a) >= 0), "Holm preserva a ordem"
    assert np.all(a <= 1.0)


def test_holm_com_lista_vazia() -> None:
    assert metricas.holm([]).size == 0


def test_dm_nao_rejeita_modelos_identicos() -> None:
    """Modelos iguais tem diferenca zero: p = 1, e nao uma divisao por zero."""
    serie = dados.exemplo_casa(series=1, dias=60)
    real = serie.apenas_validos()[["unique_id", "ds", "y"]]
    prev = dados.previsao_perfeita(serie).assign(yhat=lambda d: d["yhat"] * 0.9)
    m, _ = metricas.alinha(prev, real, prev)
    e = metricas.erros_quadraticos(m)
    dif, est, p = metricas.diebold_mariano(e, e)
    assert (dif, est, p) == (0.0, 0.0, 1.0)


def test_dm_detecta_o_modelo_pior() -> None:
    """Sinal positivo = o primeiro erra mais. Com erro 3x, tem de ser significativo."""
    serie = dados.exemplo_casa(series=1, dias=90)
    real = serie.apenas_validos()[["unique_id", "ds", "y"]]
    bom = dados.previsao_perfeita(serie).assign(yhat=lambda d: d["yhat"] * 0.95)
    ruim = dados.previsao_perfeita(serie).assign(yhat=lambda d: d["yhat"] * 0.85)
    mb, _ = metricas.alinha(bom, real, bom)
    mr, _ = metricas.alinha(ruim, real, ruim)
    dif, est, p = metricas.diebold_mariano(metricas.erros_quadraticos(mr), metricas.erros_quadraticos(mb))
    assert dif > 0 and est > 0 and p < 0.05


def test_r2_diario_e_nan_com_um_unico_dia() -> None:
    """Com um dia so os totais diarios nao variam: R2 nao esta definido, e NaN e a resposta honesta."""
    m = metricas.metricas(_quadro([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]))
    assert np.isnan(m["R2_diario"])
    assert m["R2"] == pytest.approx(1.0)  # o horario continua definido


def test_r2_diario_definido_com_varios_dias() -> None:
    """Com dias de energia diferente o R2 diario volta a existir."""
    y = [1.0] * 24 + [5.0] * 24
    m = metricas.metricas(_quadro(y, y))
    assert m["R2_diario"] == pytest.approx(1.0)
