"""Protocolo da previsao do dia seguinte: dobras, janelas e regimes, num lugar so.

Portado de `experimentos/testes_previsao/scripts/comum.py`, que e a versao congelada usada no
benchmark v2. A regra da proposta (secao 6) e que datas de corte, sementes e metricas vivem na
tarefa, nunca no script — entao e aqui que elas moram.

Tarefa: 24 valores horarios do dia seguinte, emitidos as 00:00, com historico ate 23:00 da vespera.
Uma janela por dia de teste; nenhum modelo ve o dia que preve.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from .contratos import SerieEnergia

H = 24  # horizonte: as 24 horas do dia seguinte


class Regime(StrEnum):
    """Que informacao o modelo recebe. Misturar regimes numa tabela engana o leitor.

    O vao entre regimes foi ~10x a diferenca entre algoritmos no benchmark, por isso o regime e
    explicito no tipo e nao um parametro solto.
    """

    HISTORICO = "A"  # so o historico da propria serie
    CLIMA_CONHECIDO = "B"  # + clima do proprio dia: um teto, supoe previsao perfeita
    PREVISAO_REAL = "C"  # + previsao do tempo emitida na vespera: o regime operacional


@dataclass(frozen=True, slots=True)
class Dobra:
    """Uma dobra da origem movel: o modelo e treinado do zero no inicio dela."""

    indice: int
    inicio: pd.Timestamp
    fim: pd.Timestamp  # inclusivo, as 23:00 do ultimo dia

    @property
    def dias(self) -> int:
        return int((self.fim.normalize() - self.inicio.normalize()).days) + 1


@dataclass(frozen=True, slots=True)
class Janela:
    """Um dia a prever: o historico ate a vespera e os instantes do alvo."""

    unique_id: str
    dia: pd.Timestamp
    historico: np.ndarray
    instantes: pd.DatetimeIndex


class DiaSeguinte:
    """A tarefa. Recebe a serie e o corte de teste; entrega dobras, dias e janelas.

    `retreino_dias` e o tamanho da dobra (61 nas usinas, 31 nas casas no benchmark). A origem movel
    existe porque um corte unico escolheria o vencedor errado: no benchmark o ranking entre modelos
    troca de dobra para dobra, mesmo quando a ordem entre regimes nao troca.
    """

    def __init__(
        self,
        serie: SerieEnergia,
        *,
        teste_de: str | pd.Timestamp,
        teste_ate: str | pd.Timestamp | None = None,
        retreino_dias: int = 61,
        contexto: int = 168,
        semente: int = 42,
    ) -> None:
        if retreino_dias < 1:
            raise ValueError("retreino_dias precisa ser >= 1")
        if contexto < H:
            raise ValueError(f"contexto ({contexto} h) precisa cobrir ao menos o horizonte ({H} h)")
        self.serie = serie.em_kwh()
        fuso = self.serie.fuso
        self.inicio = pd.Timestamp(teste_de, tz=fuso).normalize()
        ultimo = self.serie.quadro["ds"].max()
        self.fim = (
            pd.Timestamp(teste_ate, tz=fuso).normalize() if teste_ate is not None else ultimo.normalize()
        )
        if self.fim < self.inicio:
            raise ValueError(f"Fim do teste ({self.fim.date()}) anterior ao inicio ({self.inicio.date()})")
        self.retreino_dias = retreino_dias
        self.contexto = contexto
        self.semente = semente

    # ------------------------------------------------------------------ dobras
    def dobras(self) -> list[Dobra]:
        """Dobras consecutivas de `retreino_dias`; a ultima pode ser mais curta."""
        out: list[Dobra] = []
        a = self.inicio
        i = 1
        while a <= self.fim:
            b = min(a + pd.Timedelta(days=self.retreino_dias - 1), self.fim)
            out.append(Dobra(indice=i, inicio=a, fim=b + pd.Timedelta(hours=H - 1)))
            a = b + pd.Timedelta(days=1)
            i += 1
        return out

    def dobra_de(self, dia: pd.Timestamp) -> Dobra:
        """A dobra a que um dia pertence. Previsao fora da sua dobra e vazamento."""
        for d in self.dobras():
            if d.inicio <= dia <= d.fim:
                return d
        raise ValueError(f"{dia} esta fora do periodo de teste")

    # ------------------------------------------------------------------ dias e janelas
    def dias_teste(self) -> list[tuple[str, pd.Timestamp]]:
        """(serie, dia) com as 24 horas presentes e validas dentro do teste."""
        q = self.serie.quadro
        no_teste = q[(q["ds"] >= self.inicio) & (q["ds"] <= self.fim + pd.Timedelta(hours=H - 1))].copy()
        no_teste["dia"] = no_teste["ds"].dt.normalize()
        g = no_teste.groupby(["unique_id", "dia"])["valido"].agg(["sum", "size"])
        completos = g[(g["sum"] == H) & (g["size"] == H)]
        return [(str(u), pd.Timestamp(d)) for u, d in completos.index]

    def janelas(self) -> list[Janela]:
        """Uma janela por dia de teste, com `contexto` horas de historico antes do dia."""
        por_serie = {u: g.set_index("ds") for u, g in self.serie.quadro.groupby("unique_id")}
        out: list[Janela] = []
        for uid, dia in self.dias_teste():
            g = por_serie[uid]
            hist = g.loc[: dia - pd.Timedelta(hours=1)].tail(self.contexto)
            if len(hist) < self.contexto:
                continue  # inicio da serie: nao ha historico suficiente para esta janela
            y = hist["y"].to_numpy(dtype=float)
            out.append(
                Janela(
                    unique_id=uid,
                    dia=dia,
                    historico=y,
                    instantes=pd.date_range(dia, periods=H, freq="h", tz=self.serie.fuso),
                )
            )
        return out

    # ------------------------------------------------------------------ guardas
    def verifica_suporte(self) -> None:
        """Avisa quando as series nao terminam juntas, o caso que gera vazamento entre dobras.

        Nao e um erro: `casas_cons` tem uma serie curta de verdade. Mas quem gera as janelas a partir
        do fim de CADA serie (como o `cross_validation` do NeuralForecast) vai recuar e reemitir dias
        de dobras anteriores, com um modelo treinado depois deles. Quem chama precisa recortar por
        dobra. Ver `Dobra` e `dobra_de`.
        """
        if not self.serie.termina_junto():
            fins = self.serie.fim_por_serie()
            raise AvisoDeSuporte(
                "Series terminam em instantes diferentes "
                f"({fins.min()} a {fins.max()}): recorte cada dobra por [inicio, fim] "
                "antes de gravar previsoes, senao uma dobra posterior reemite dias de uma anterior."
            )


class AvisoDeSuporte(RuntimeError):
    """As series nao compartilham o mesmo fim; o chamador precisa recortar por dobra."""
