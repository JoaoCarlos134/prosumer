"""Dados de exemplo sinteticos, gerados por codigo.

Por que gerador e nao arquivo: as series reais do projeto sao de terceiros e nao tem consentimento
para publicacao (ver CLAUDE.md e PROPOSTA_BIBLIOTECA.md secao 8). Um gerador com semente fixa resolve
o problema de licenca, nao incha o repositorio, e — o que importa mais para o teste — permite pedir
exatamente a patologia que se quer exercitar.

O que estes dados servem para testar: fisica (contra o valor fechado), protocolo (dobras, janelas,
suporte), contratos (valido x invalido) e encanamento de covariaveis. O que eles NAO servem para
testar: se um modelo preve bem. Uma serie gerada de um processo conhecido e facil ou dificil do jeito
errado; o ranking entre modelos so faz sentido nos dados reais, e esses numeros ficam congelados em
`experimentos/testes_previsao/resultados/`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .contratos import SerieEnergia, passo

FUSO_PADRAO = "America/Sao_Paulo"


def _ceu_claro(indice: pd.DatetimeIndex, *, pico: float) -> np.ndarray:
    """Sino diurno simples: meio-seno entre 6h e 18h, zero a noite.

    Nao e um modelo de ceu claro de verdade (o de verdade esta em `fisica`, com Haurwitz e a geometria
    solar); aqui basta uma forma diurna plausivel e deterministica.
    """
    h = indice.hour + indice.minute / 60.0
    dia = np.clip(np.sin(np.pi * (h - 6.0) / 12.0), 0.0, None)
    return pico * dia


def exemplo_usina(
    *,
    series: int = 2,
    inicio: str = "2024-01-01",
    dias: int = 120,
    taxa: str = "h",
    pico_kwh: float = 3.0,
    semente: int = 42,
    nebulosidade: float = 0.35,
    fuso: str = FUSO_PADRAO,
) -> tuple[SerieEnergia, pd.DataFrame]:
    """Geracao FV sintetica e o clima correspondente.

    Devolve (serie, clima). O clima e o que um regime B ou C receberia: `poa_ceu_claro` (geometria,
    sempre conhecida) e `poa_estimada` (ceu claro x indice de ceu claro do dia). A geracao e
    construida COMO FUNCAO do `poa_estimada`, de proposito: isso torna possivel testar se um adaptador
    realmente usa a covariavel que recebeu — foi assim que o TiDE passou duas versoes ignorando o
    clima sem ninguem notar.
    """
    rng = np.random.default_rng(semente)
    idx = pd.date_range(inicio, periods=dias * _passos_por_dia(taxa), freq=taxa, tz=fuso)
    quadros, climas = [], []
    for i in range(series):
        uid = f"usina_{i + 1}"
        claro = _ceu_claro(idx, pico=pico_kwh * (1.0 + 0.5 * i))
        # Um kc por dia, nao por hora: a nebulosidade e persistente dentro do dia.
        dias_idx = idx.normalize()
        kc_dia = pd.Series(
            rng.uniform(1.0 - nebulosidade, 1.0, size=dias_idx.nunique()), index=dias_idx.unique()
        )
        kc = dias_idx.map(kc_dia.to_dict()).to_numpy(dtype=float)
        poa = claro * kc
        y = poa * 0.95  # eficiencia constante: a relacao fica exata e testavel
        quadros.append(pd.DataFrame({"unique_id": uid, "ds": idx, "y": y}))
        climas.append(
            pd.DataFrame({"unique_id": uid, "ds": idx, "poa_ceu_claro": claro, "poa_estimada": poa})
        )
    serie = SerieEnergia.de_dataframe(
        pd.concat(quadros, ignore_index=True),
        unidade="kWh",
        grandeza="geracao",
        fuso=fuso,
        taxa=taxa,
    )
    return serie, pd.concat(climas, ignore_index=True)


def exemplo_casa(
    *,
    series: int = 3,
    inicio: str = "2024-01-01",
    dias: int = 90,
    taxa: str = "h",
    media_kwh: float = 0.4,
    semente: int = 7,
    fuso: str = FUSO_PADRAO,
) -> SerieEnergia:
    """Consumo residencial sintetico: dois picos diarios, fim de semana mais alto, ruido log-normal.

    O ruido e assimetrico de proposito. O consumo real tem picos curtos e altos, e foi por isso que os
    modelos fundacionais ficaram com vies de ~-20% nos dados reais: eles preveem a mediana. Uma serie
    com ruido simetrico esconderia esse comportamento.
    """
    rng = np.random.default_rng(semente)
    idx = pd.date_range(inicio, periods=dias * _passos_por_dia(taxa), freq=taxa, tz=fuso)
    h = idx.hour + idx.minute / 60.0
    forma = 0.5 + np.exp(-0.5 * ((h - 8) / 1.6) ** 2) + 1.4 * np.exp(-0.5 * ((h - 19) / 2.0) ** 2)
    fds = np.where(idx.dayofweek >= 5, 1.25, 1.0)
    quadros = []
    for i in range(series):
        base = media_kwh * (0.8 + 0.4 * i) * forma * fds
        y = base * rng.lognormal(mean=0.0, sigma=0.35, size=len(idx))
        quadros.append(pd.DataFrame({"unique_id": f"casa_{i + 1}", "ds": idx, "y": y}))
    return SerieEnergia.de_dataframe(
        pd.concat(quadros, ignore_index=True),
        unidade="kWh",
        grandeza="consumo",
        fuso=fuso,
        taxa=taxa,
    )


def com_buracos(
    serie: SerieEnergia,
    *,
    fracao: float = 0.02,
    semente: int = 0,
    serie_curta: str | None = None,
    dias_a_menos: int = 20,
) -> SerieEnergia:
    """Introduz as patologias que os dados reais tem, para o teste poder exercita-las.

    - `fracao`: passos sem registro (y nulo, `valido` False) — buraco nao e zero.
    - `serie_curta`: faz uma das series terminar `dias_a_menos` antes das outras. E o caso da casa
      H14 nos dados reais, que fez o `cross_validation` reemitir dias de uma dobra anterior com um
      modelo treinado depois deles. Qualquer protocolo novo deve ser testado contra isto.
    """
    if not 0.0 <= fracao < 1.0:
        raise ValueError("fracao precisa estar em [0, 1)")
    rng = np.random.default_rng(semente)
    x = serie.quadro.copy()
    if fracao > 0:
        alvo = rng.random(len(x)) < fracao
        x.loc[alvo, "y"] = np.nan
        x.loc[alvo, "valido"] = False
    if serie_curta is not None:
        if serie_curta not in set(x["unique_id"]):
            raise ValueError(f"serie '{serie_curta}' nao existe: {sorted(set(x['unique_id']))}")
        corte = x.loc[x["unique_id"] == serie_curta, "ds"].max() - pd.Timedelta(days=dias_a_menos)
        fora = (x["unique_id"] == serie_curta) & (x["ds"] > corte)
        x = x.loc[~fora].reset_index(drop=True)
    return SerieEnergia.de_dataframe(
        x, unidade=serie.unidade, grandeza=serie.grandeza, fuso=serie.fuso, taxa=serie.taxa
    )


def previsao_perfeita(serie: SerieEnergia) -> pd.DataFrame:
    """Previsao igual ao real: skill 1 por construcao. Util para checar o sinal das metricas."""
    v = serie.apenas_validos()
    return v[["unique_id", "ds"]].assign(yhat=v["y"].to_numpy())


def previsao_persistencia(serie: SerieEnergia, *, atraso_h: int = 24) -> pd.DataFrame:
    """A referencia "igual a ontem": o valor do mesmo horario `atraso_h` antes."""
    v = serie.apenas_validos().sort_values(["unique_id", "ds"], kind="stable")
    partes = []
    for uid, g in v.groupby("unique_id"):
        s = g.set_index("ds")["y"]
        partes.append(
            pd.DataFrame(
                {
                    "unique_id": uid,
                    "ds": s.index,
                    "yhat": s.shift(atraso_h, freq="h").reindex(s.index).to_numpy(),
                }
            )
        )
    return pd.concat(partes, ignore_index=True)


def _passos_por_dia(taxa: str) -> int:
    return int(pd.Timedelta(days=1) / passo(taxa))
