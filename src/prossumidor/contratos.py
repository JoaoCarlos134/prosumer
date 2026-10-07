"""Contratos de dados: nenhuma funcao da biblioteca aceita um DataFrame cru.

O principio vem da PROPOSTA_BIBLIOTECA.md (secao 6): toda serie carrega unidade, fuso, taxa de
amostragem e mascara de validade. A `SerieEnergia` embrulha o DataFrame com esses quatro metadados e
valida a forma com pandera na construcao, uma vez. Depois disso as funcoes podem confiar na estrutura.

A mascara de validade existe porque, nos dados reais do projeto, buraco e zero nao sao a mesma coisa:
o inversor registra zero a noite (valido) e nao registra nada quando cai (invalido). Guardar o NaN e
perder a diferenca entre "nao gerou" e "nao sabemos"; por isso `valido` e uma coluna, nao uma convencao.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import pandas as pd
import pandera.pandas as pa

Unidade = Literal["kWh", "Wh", "kW", "W"]
Grandeza = Literal["geracao", "consumo", "irradiancia", "temperatura"]

# Fatores para kWh/kW. A biblioteca converte para kWh na fronteira e trabalha so nessa unidade.
_PARA_QUILO: dict[str, float] = {"kWh": 1.0, "Wh": 1e-3, "kW": 1.0, "W": 1e-3}


def esquema(fuso: str) -> pa.DataFrameSchema:
    """Esquema da serie longa para um fuso concreto.

    E funcao do fuso de proposito: o `DatetimeTZDtype` do pandas exige um `tz`, e o fuso faz parte do
    contrato. Validar contra o fuso declarado pega serie que chegou em outro fuso (ou ingenua) em vez
    de deixar passar e errar a hora de ponta mais tarde.
    """
    return pa.DataFrameSchema(
        {
            "unique_id": pa.Column(str, nullable=False, description="identificador da serie"),
            "ds": pa.Column(pd.DatetimeTZDtype(tz=fuso), nullable=False, description="inicio do intervalo"),
            "y": pa.Column(float, nullable=True, description="valor no intervalo, na unidade declarada"),
            "valido": pa.Column(bool, nullable=False, description="False onde o medidor nao registrou"),
        },
        strict=False,
        coerce=True,
        unique=["unique_id", "ds"],
        name="SerieEnergia",
        ordered=False,
    )


class ErroDeContrato(ValueError):
    """Erro de contrato de dados: a serie nao atende ao esquema ou aos metadados exigidos."""


@dataclass(frozen=True, slots=True)
class SerieEnergia:
    """Serie temporal com unidade, fuso, taxa e mascara de validade.

    Construir com `SerieEnergia.de_dataframe` para validar; o construtor nao revalida, de proposito,
    para que operacoes internas possam reusar `replace()` sem custo.
    """

    quadro: pd.DataFrame
    unidade: Unidade
    grandeza: Grandeza
    fuso: str
    taxa: str  # alias de frequencia do pandas: "h", "5min", "D"

    # ------------------------------------------------------------------ construcao
    @classmethod
    def de_dataframe(
        cls,
        quadro: pd.DataFrame,
        *,
        unidade: Unidade,
        grandeza: Grandeza,
        fuso: str,
        taxa: str,
        coluna_valor: str = "y",
        fuso_origem: str | None = None,
    ) -> SerieEnergia:
        """Valida e embrulha. `coluna_valor` permite ler um quadro cujo valor nao se chama `y`.

        `fuso_origem` diz em que fuso estao os instantes SEM fuso (ingenuos) do quadro; o padrao e o
        proprio `fuso`. Existe porque e comum o arquivo vir em UTC e a serie ser de um lugar com horario
        de verao: as casas de Dingle vem em UTC e sao de `Europe/Dublin`. Ler esses instantes como hora
        local cria horas que nao existem (o adianto do relogio). Nesse caso: `fuso="Europe/Dublin",
        fuso_origem="UTC"`. Instantes que ja tem fuso so sao convertidos, e `fuso_origem` e ignorado.
        """
        if quadro.empty:
            raise ErroDeContrato("Serie vazia: nao da para inferir nem validar nada")
        x = quadro.rename(columns={coluna_valor: "y"}).copy()
        faltando = {"unique_id", "ds", "y"} - set(x.columns)
        if faltando:
            raise ErroDeContrato(f"Colunas obrigatorias ausentes: {sorted(faltando)}")
        if "valido" not in x.columns:
            # Sem mascara explicita, o unico default defensavel e "NaN e invalido, o resto e valido".
            x["valido"] = x["y"].notna()
        x["unique_id"] = x["unique_id"].astype(str)
        x["ds"] = _com_fuso(x["ds"], fuso, fuso_origem or fuso, x["unique_id"])
        try:
            validado = esquema(fuso).validate(x, lazy=True)
        except (pa.errors.SchemaError, pa.errors.SchemaErrors) as e:
            raise ErroDeContrato(f"Serie fora do contrato: {e}") from e
        ordenado = validado.sort_values(["unique_id", "ds"], kind="stable").reset_index(drop=True)
        return cls(quadro=ordenado, unidade=unidade, grandeza=grandeza, fuso=fuso, taxa=taxa)

    # ------------------------------------------------------------------ metadados
    @property
    def series(self) -> list[str]:
        """Identificadores presentes, em ordem estavel."""
        return sorted(self.quadro["unique_id"].unique().tolist())

    @property
    def horas_por_passo(self) -> float:
        """Duracao de um passo em horas; usado para converter potencia em energia."""
        return passo(self.taxa).total_seconds() / 3600.0

    def __len__(self) -> int:
        return len(self.quadro)

    # ------------------------------------------------------------------ operacoes
    def em_kwh(self) -> SerieEnergia:
        """Converte para kWh. Potencia (kW, W) e multiplicada pela duracao do passo."""
        if self.unidade == "kWh":
            return self
        fator = _PARA_QUILO[self.unidade]
        if self.unidade in ("kW", "W"):
            fator *= self.horas_por_passo
        x = self.quadro.copy()
        x["y"] = x["y"] * fator
        return replace(self, quadro=x, unidade="kWh")

    def apenas_validos(self) -> pd.DataFrame:
        """Quadro so com as linhas que o medidor registrou. Use quando o NaN nao pode virar zero."""
        return self.quadro.loc[self.quadro["valido"]].reset_index(drop=True)

    def cobertura(self) -> pd.Series:
        """Fracao de passos validos por serie: o numero que vai no relatorio de qualidade."""
        return self.quadro.groupby("unique_id")["valido"].mean()

    def fim_por_serie(self) -> pd.Series:
        """Ultimo instante valido de cada serie.

        Existe porque series que terminam em datas diferentes quebram protocolos de validacao: foi
        exatamente o que aconteceu no benchmark (a casa H14 acaba 20 dias antes das outras 19 e o
        `cross_validation` reemitiu dias de uma dobra anterior). Quem monta dobras deve olhar isto.
        """
        v = self.apenas_validos()
        return v.groupby("unique_id")["ds"].max()

    def termina_junto(self) -> bool:
        """True se todas as series acabam no mesmo instante valido."""
        fins = self.fim_por_serie()
        return bool(fins.empty or (fins == fins.iloc[0]).all())


def passo(taxa: str) -> pd.Timedelta:
    """Duracao de um passo a partir do alias de frequencia do pandas ("h", "5min", "D").

    Levanta para frequencias de duracao variavel (mes, ano): nao existe "quantas horas tem um mes",
    e converter potencia em energia com elas daria um numero errado em silencio.
    """
    offset = pd.tseries.frequencies.to_offset(taxa)
    if offset is None:
        raise ErroDeContrato(f"Taxa invalida: {taxa!r}")
    try:
        return pd.Timedelta(nanoseconds=offset.nanos)
    except (AttributeError, ValueError) as e:
        raise ErroDeContrato(f"Taxa de duracao variavel nao serve como passo: {taxa!r}") from e


def _com_fuso(ds: pd.Series, fuso: str, origem: str, ids: pd.Series) -> pd.Series:
    """Garante datetime com fuso. Instantes ingenuos sao lidos em `origem` e convertidos para `fuso`.

    Horario de verao, quando `origem` tem um:
    - hora repetida (o relogio atrasa): resolvida pela ordem, serie a serie; a primeira ocorrencia e o
      horario de verao. Exige que cada serie esteja em ordem cronologica, como um medidor grava.
    - hora que nao existe (o relogio adianta): nenhum medidor em hora local grava nela, entao o mais
      provavel e o arquivo estar em UTC. Vira `ErroDeContrato` com essa sugestao, nunca o ValueError cru
      do pandas: foi o que aconteceu com as casas de Dingle declaradas como `Europe/Dublin`.
    """
    try:
        d = pd.to_datetime(ds)
    except (ValueError, TypeError) as e:
        raise ErroDeContrato(f"Coluna ds nao e de datas: {e}") from e
    if isinstance(d.dtype, pd.DatetimeTZDtype):
        return d.dt.tz_convert(fuso)
    try:
        return d.dt.tz_localize(origem).dt.tz_convert(fuso)
    except ValueError:
        pass  # alguma hora de troca de horario: resolve serie a serie abaixo
    partes = []
    for uid, g in d.groupby(ids, sort=False):
        try:
            partes.append(g.dt.tz_localize(origem, ambiguous="infer", nonexistent="raise"))
        except ValueError as e:
            raise ErroDeContrato(
                f"Serie {uid!r}: instantes impossiveis no fuso {origem!r} por causa do horario de verao "
                f"({e}). Se o arquivo esta em UTC, passe fuso_origem='UTC'. Se esta em hora local, confira "
                "se a serie esta em ordem cronologica e sem a hora repetida faltando."
            ) from e
    return pd.concat(partes).reindex(d.index).dt.tz_convert(fuso)
