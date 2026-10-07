"""Contratos de dados: o que entra, o que e recusado, e o que a mascara de validade preserva."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prossumidor import dados
from prossumidor.contratos import ErroDeContrato, SerieEnergia


def test_aceita_quadro_minimo() -> None:
    q = pd.DataFrame(
        {
            "unique_id": ["a", "a"],
            "ds": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"]),
            "y": [1.0, 2.0],
        }
    )
    s = SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="geracao", fuso="UTC", taxa="h")
    assert s.series == ["a"]
    assert bool(s.quadro["valido"].all())


def test_recusa_quadro_sem_coluna_obrigatoria() -> None:
    q = pd.DataFrame({"unique_id": ["a"], "ds": pd.to_datetime(["2024-01-01"])})
    with pytest.raises(ErroDeContrato, match="obrigatorias"):
        SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="geracao", fuso="UTC", taxa="h")


def test_recusa_quadro_vazio() -> None:
    with pytest.raises(ErroDeContrato, match="vazia"):
        SerieEnergia.de_dataframe(
            pd.DataFrame(columns=["unique_id", "ds", "y"]),
            unidade="kWh",
            grandeza="geracao",
            fuso="UTC",
            taxa="h",
        )


def test_recusa_chave_duplicada() -> None:
    """(unique_id, ds) repetido e o sintoma do vazamento entre dobras; tem de falhar na porta."""
    q = pd.DataFrame(
        {"unique_id": ["a", "a"], "ds": pd.to_datetime(["2024-01-01 00:00"] * 2), "y": [1.0, 1.5]}
    )
    with pytest.raises(ErroDeContrato):
        SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="geracao", fuso="UTC", taxa="h")


def test_nan_viraria_invalido_e_nao_zero() -> None:
    """Buraco e zero nao sao a mesma coisa: o inversor zera a noite e nao registra nada quando cai."""
    q = pd.DataFrame(
        {
            "unique_id": ["a"] * 3,
            "ds": pd.date_range("2024-01-01", periods=3, freq="h"),
            "y": [1.0, np.nan, 0.0],
        }
    )
    s = SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="geracao", fuso="UTC", taxa="h")
    assert s.quadro["valido"].tolist() == [True, False, True]
    assert len(s.apenas_validos()) == 2
    assert s.cobertura()["a"] == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    ("unidade", "taxa", "esperado"),
    [("kWh", "h", 1.0), ("Wh", "h", 1e-3), ("kW", "h", 1.0), ("kW", "30min", 0.5), ("W", "30min", 5e-4)],
)
def test_conversao_para_kwh(unidade: str, taxa: str, esperado: float) -> None:
    """Potencia precisa ser multiplicada pela duracao do passo; energia nao."""
    q = pd.DataFrame({"unique_id": ["a"], "ds": pd.to_datetime(["2024-01-01"]), "y": [1.0]})
    s = SerieEnergia.de_dataframe(q, unidade=unidade, grandeza="geracao", fuso="UTC", taxa=taxa)  # type: ignore[arg-type]
    assert s.em_kwh().quadro["y"].iloc[0] == pytest.approx(esperado)
    assert s.em_kwh().unidade == "kWh"


def test_fuso_ingenuo_e_interpretado_no_fuso_declarado() -> None:
    q = pd.DataFrame({"unique_id": ["a"], "ds": pd.to_datetime(["2024-01-01 12:00"]), "y": [1.0]})
    s = SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="geracao", fuso="America/Sao_Paulo", taxa="h")
    assert str(s.quadro["ds"].dt.tz) == "America/Sao_Paulo"
    assert s.quadro["ds"].iloc[0].hour == 12


def test_fim_por_serie_detecta_serie_curta() -> None:
    """O caso da casa H14: uma serie acaba antes e quem monta dobras precisa saber."""
    serie = dados.exemplo_casa(series=3, dias=40)
    assert serie.termina_junto()
    curta = dados.com_buracos(serie, fracao=0.0, serie_curta="casa_2", dias_a_menos=20)
    assert not curta.termina_junto()
    fins = curta.fim_por_serie()
    assert (fins["casa_1"] - fins["casa_2"]).days == 20


@settings(max_examples=25, deadline=None)
@given(n=st.integers(min_value=1, max_value=50), fator=st.floats(min_value=0.1, max_value=1e4))
def test_conversao_wh_para_kwh_e_sempre_milesimo(n: int, fator: float) -> None:
    """Propriedade: converter Wh para kWh divide por mil, qualquer que seja o valor."""
    q = pd.DataFrame(
        {"unique_id": ["a"] * n, "ds": pd.date_range("2024-01-01", periods=n, freq="h"), "y": [fator] * n}
    )
    s = SerieEnergia.de_dataframe(q, unidade="Wh", grandeza="geracao", fuso="UTC", taxa="h")
    assert np.allclose(s.em_kwh().quadro["y"].to_numpy(), fator / 1000.0)
