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


# ---------------------------------------------------------------------- horario de verao
# 29/03/2020 (o relogio adianta em Dublin, 01:00 local nao existe) e 25/10/2020 (atrasa, 01:00 local se
# repete): as duas trocas do ano das casas de Dingle.
def _quadro_horario(inicio: str, horas: int, ids: tuple[str, ...] = ("a",)) -> pd.DataFrame:
    ds = pd.date_range(inicio, periods=horas, freq="h")
    return pd.DataFrame(
        {
            "unique_id": np.repeat(ids, horas),
            "ds": np.tile(ds, len(ids)),
            "y": 1.0 + np.arange(horas * len(ids)),
        }
    )


def test_utc_ingenuo_de_lugar_com_horario_de_verao_precisa_de_fuso_origem() -> None:
    # Arquivo em UTC sem fuso, serie de Dublin: ler como hora local cria a hora que nao existe. Antes do
    # conserto isto saia como ValueError cru do pandas.
    q = _quadro_horario("2020-03-28 22:00", 6)
    with pytest.raises(ErroDeContrato, match="fuso_origem='UTC'"):
        SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="consumo", fuso="Europe/Dublin", taxa="h")
    s = SerieEnergia.de_dataframe(
        q, unidade="kWh", grandeza="consumo", fuso="Europe/Dublin", taxa="h", fuso_origem="UTC"
    )
    horas = s.quadro["ds"]
    assert str(horas.dt.tz) == "Europe/Dublin"
    assert len(s) == 6 and horas.is_unique
    assert (horas.diff().dropna() == pd.Timedelta("1h")).all()  # continua de hora em hora, sem buraco
    # 01:00 UTC vira 02:00 de Dublin (horario de verao, UTC+1)
    assert horas.iloc[3].hour == 2 and horas.iloc[3].utcoffset() == pd.Timedelta("1h")


def test_hora_local_repetida_e_resolvida_pela_ordem() -> None:
    # Medidor em hora local: 01:00 aparece duas vezes em 25/10. A primeira e o horario de verao.
    ds = pd.to_datetime(["2020-10-25 00:00", "2020-10-25 01:00", "2020-10-25 01:00", "2020-10-25 02:00"])
    q = pd.DataFrame({"unique_id": "a", "ds": ds, "y": [1.0, 2.0, 3.0, 4.0]})
    s = SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="consumo", fuso="Europe/Dublin", taxa="h")
    assert s.quadro["ds"].is_unique
    assert (s.quadro["ds"].diff().dropna() == pd.Timedelta("1h")).all()
    assert s.quadro["y"].tolist() == [1.0, 2.0, 3.0, 4.0]  # a ordem dos valores nao muda


def test_hora_repetida_resolvida_em_cada_serie_separadamente() -> None:
    # Duas casas no mesmo quadro: a inferencia nao pode misturar as horas de uma com as da outra.
    ds = pd.to_datetime(["2020-10-25 00:00", "2020-10-25 01:00", "2020-10-25 01:00", "2020-10-25 02:00"])
    q = pd.concat([pd.DataFrame({"unique_id": u, "ds": ds, "y": [1.0, 2.0, 3.0, 4.0]}) for u in ("a", "b")])
    s = SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="consumo", fuso="Europe/Dublin", taxa="h")
    for _, g in s.quadro.groupby("unique_id"):
        assert g["ds"].is_unique and len(g) == 4


def test_fuso_ja_declarado_no_dado_so_e_convertido() -> None:
    q = _quadro_horario("2020-03-28 22:00", 6)
    q["ds"] = q["ds"].dt.tz_localize("UTC")
    # fuso_origem e ignorado quando o dado ja tem fuso: o instante absoluto manda.
    s = SerieEnergia.de_dataframe(
        q, unidade="kWh", grandeza="consumo", fuso="Europe/Dublin", taxa="h", fuso_origem="America/Sao_Paulo"
    )
    assert (s.quadro["ds"].dt.tz_convert("UTC") == q["ds"]).all()


def _grade_local_preenchida() -> pd.DataFrame:
    """Hora local de Dublin numa grade sem buraco, como as casas de Dingle: 29/03 01:00 (nao existe) e uma
    linha so em 25/10 01:00 (existiu duas vezes)."""
    ds = pd.concat(
        [
            pd.Series(pd.date_range("2020-03-28 23:00", periods=4, freq="h")),
            pd.Series(pd.date_range("2020-10-24 23:00", periods=4, freq="h")),
        ],
        ignore_index=True,
    )
    return pd.DataFrame({"unique_id": "a", "ds": ds, "y": np.arange(8.0)})


def test_grade_local_preenchida_e_recusada_por_padrao_com_as_duas_sugestoes() -> None:
    with pytest.raises(ErroDeContrato, match="troca_de_horario='descarta'"):
        SerieEnergia.de_dataframe(
            _grade_local_preenchida(), unidade="kWh", grandeza="consumo", fuso="Europe/Dublin", taxa="h"
        )


def test_descarta_tira_so_as_horas_impossiveis_e_avisa() -> None:
    with pytest.warns(UserWarning, match="2 linha"):
        s = SerieEnergia.de_dataframe(
            _grade_local_preenchida(),
            unidade="kWh",
            grandeza="consumo",
            fuso="Europe/Dublin",
            taxa="h",
            troca_de_horario="descarta",
        )
    assert len(s) == 6
    assert 2.0 not in s.quadro["y"].tolist()  # 29/03 01:00
    assert 6.0 not in s.quadro["y"].tolist()  # 25/10 01:00, linha unica de uma hora repetida
    assert s.quadro["ds"].is_unique


def test_coluna_ds_que_nao_e_data_vira_erro_de_contrato() -> None:
    q = pd.DataFrame({"unique_id": ["a"], "ds": ["isto nao e data"], "y": [1.0]})
    with pytest.raises(ErroDeContrato, match="ds"):
        SerieEnergia.de_dataframe(q, unidade="kWh", grandeza="consumo", fuso="UTC", taxa="h")


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
