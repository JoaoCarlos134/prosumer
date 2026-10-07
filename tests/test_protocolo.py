"""Protocolo: dobras, janelas e a guarda contra o vazamento que os dados reais produziram."""

from __future__ import annotations

from itertools import pairwise

import pandas as pd
import pytest

from prossumidor import dados
from prossumidor.protocolo import AvisoDeSuporte, DiaSeguinte, H, Regime


@pytest.fixture
def usina() -> object:
    serie, _ = dados.exemplo_usina(series=2, inicio="2024-01-01", dias=120)
    return serie


def test_dobras_cobrem_o_teste_sem_sobreposicao(usina: object) -> None:
    t = DiaSeguinte(usina, teste_de="2024-03-01", teste_ate="2024-04-29", retreino_dias=20)
    d = t.dobras()
    assert [x.dias for x in d] == [20, 20, 20]
    assert d[0].inicio == pd.Timestamp("2024-03-01", tz=usina.fuso)  # type: ignore[attr-defined]
    for a, b in pairwise(d):
        assert a.fim < b.inicio, "dobras nao podem se sobrepor: sobreposicao e vazamento"
    assert d[-1].fim.normalize() == pd.Timestamp("2024-04-29", tz=usina.fuso)  # type: ignore[attr-defined]


def test_ultima_dobra_pode_ser_mais_curta(usina: object) -> None:
    t = DiaSeguinte(usina, teste_de="2024-03-01", teste_ate="2024-03-25", retreino_dias=10)
    assert [x.dias for x in t.dobras()] == [10, 10, 5]


def test_dobra_de_atribui_cada_dia_a_uma_so_dobra(usina: object) -> None:
    t = DiaSeguinte(usina, teste_de="2024-03-01", teste_ate="2024-04-09", retreino_dias=20)
    for dia in pd.date_range("2024-03-01", "2024-04-09", freq="D", tz=usina.fuso):  # type: ignore[attr-defined]
        d = t.dobra_de(dia)
        assert d.inicio <= dia <= d.fim


def test_dobra_de_recusa_dia_fora_do_teste(usina: object) -> None:
    t = DiaSeguinte(usina, teste_de="2024-03-01", teste_ate="2024-03-10")
    with pytest.raises(ValueError, match="fora do periodo"):
        t.dobra_de(pd.Timestamp("2024-02-01", tz=usina.fuso))  # type: ignore[attr-defined]


def test_janelas_tem_horizonte_e_contexto_certos(usina: object) -> None:
    t = DiaSeguinte(usina, teste_de="2024-03-01", teste_ate="2024-03-05", contexto=168)
    js = t.janelas()
    assert js, "deveria haver janelas"
    for j in js:
        assert len(j.instantes) == H
        assert len(j.historico) == 168
        assert j.instantes[0] == j.dia
        # O historico termina antes do dia previsto: nenhum modelo ve o dia que preve.
        assert j.instantes[0] > j.dia - pd.Timedelta(hours=1)


def test_janela_nao_usa_o_dia_que_preve(usina: object) -> None:
    """A garantia central do protocolo, verificada no valor e nao so na forma."""
    t = DiaSeguinte(usina, teste_de="2024-03-01", teste_ate="2024-03-02", contexto=48)
    q = usina.quadro.set_index(["unique_id", "ds"])["y"]  # type: ignore[attr-defined]
    for j in t.janelas():
        esperado = [
            float(q.loc[(j.unique_id, ts)])
            for ts in pd.date_range(j.dia - pd.Timedelta(hours=48), periods=48, freq="h", tz=usina.fuso)  # type: ignore[attr-defined]
        ]
        assert j.historico.tolist() == pytest.approx(esperado)


def test_contexto_menor_que_horizonte_e_recusado(usina: object) -> None:
    with pytest.raises(ValueError, match="horizonte"):
        DiaSeguinte(usina, teste_de="2024-03-01", contexto=12)


def test_fim_antes_do_inicio_e_recusado(usina: object) -> None:
    with pytest.raises(ValueError, match="anterior"):
        DiaSeguinte(usina, teste_de="2024-04-01", teste_ate="2024-03-01")


def test_verifica_suporte_avisa_quando_serie_termina_antes() -> None:
    """A regressao do benchmark: a casa H14 acaba 20 dias antes e o recorte por dobra passa a importar.

    Sem recorte, o gerador de janelas conta a partir do fim de CADA serie, recua, e reemite dias de
    uma dobra anterior com um modelo treinado depois deles.
    """
    serie = dados.exemplo_casa(series=3, inicio="2024-01-01", dias=120)
    t_ok = DiaSeguinte(serie, teste_de="2024-03-01", teste_ate="2024-04-09", retreino_dias=20)
    t_ok.verifica_suporte()  # nao levanta: todas terminam juntas

    curta = dados.com_buracos(serie, fracao=0.0, serie_curta="casa_2", dias_a_menos=20)
    t_ruim = DiaSeguinte(curta, teste_de="2024-03-01", teste_ate="2024-04-09", retreino_dias=20)
    with pytest.raises(AvisoDeSuporte, match="recorte cada dobra"):
        t_ruim.verifica_suporte()


def test_dias_teste_ignora_dia_incompleto() -> None:
    """Um dia com buraco nao entra: 24 horas validas ou nada."""
    serie = dados.exemplo_casa(series=1, inicio="2024-01-01", dias=40)
    t_cheio = DiaSeguinte(serie, teste_de="2024-02-01", teste_ate="2024-02-05", retreino_dias=10)
    n_cheio = len(t_cheio.dias_teste())

    x = serie.quadro.copy()
    alvo = (x["ds"] >= pd.Timestamp("2024-02-03 10:00", tz=serie.fuso)) & (
        x["ds"] < pd.Timestamp("2024-02-03 12:00", tz=serie.fuso)
    )
    x.loc[alvo, ["y", "valido"]] = [None, False]
    furado = dados.SerieEnergia.de_dataframe(
        x, unidade=serie.unidade, grandeza=serie.grandeza, fuso=serie.fuso, taxa=serie.taxa
    )
    t_furado = DiaSeguinte(furado, teste_de="2024-02-01", teste_ate="2024-02-05", retreino_dias=10)
    assert len(t_furado.dias_teste()) == n_cheio - 1


def test_regimes_sao_explicitos() -> None:
    """O regime e parte do resultado: misturar A com B numa tabela engana o leitor."""
    assert Regime.HISTORICO.value == "A"
    assert Regime.CLIMA_CONHECIDO.value == "B"
    assert Regime.PREVISAO_REAL.value == "C"
