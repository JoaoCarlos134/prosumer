"""Pos-processamento das previsoes: ajustes aplicados DEPOIS do modelo, sem retreina-lo.

Hoje: correcao de vies causal para o consumo. Decidida por um piloto sobre o benchmark (09/10/2026):
os modelos fundacionais preveem a mediana de uma distribuicao assimetrica e subestimam o consumo das
casas em ~20%. Multiplicar a previsao do dia pelo fator real/previsto dos dias anteriores leva esse vies
a <1% e sobe a mediana de todos os modelos de +0,191 para +0,207 de skill. Na GERACAO SOLAR a mesma
correcao piora ate -0,10 (o clima muda de um dia para o outro e o fator vira ruido); por isso ela vem
bloqueada para geracao, e liberar exige pedir explicitamente.
"""

from __future__ import annotations

import pandas as pd

CHAVES = ["unique_id", "ds"]


def corrige_vies(
    previsao: pd.DataFrame,
    real: pd.DataFrame,
    *,
    grandeza: str,
    dias: int = 14,
    minimo: int = 7,
    limites: tuple[float, float] = (0.5, 2.0),
    permitir_geracao: bool = False,
) -> pd.DataFrame:
    """Previsao corrigida pelo vies recente de cada serie, usando SO o passado.

    Fator do dia D = soma do real / soma do previsto nos `dias` dias anteriores com dados (no minimo
    `minimo`; antes disso, fator 1), limitado a `limites`. So entram as horas em que real e previsto
    existem. O dia D nunca entra no proprio fator: e o que um sistema saberia as 00:00 de D.

    `previsao`: unique_id, ds, yhat. `real`: unique_id, ds, y. Devolve a previsao com `yhat` corrigido e
    a coluna `fator`.
    """
    if grandeza == "geracao" and not permitir_geracao:
        raise ValueError(
            "Correcao de vies bloqueada para geracao: no benchmark ela piorou a geracao solar em ate -0,10 "
            "de skill. Passe permitir_geracao=True so se tiver medido que ajuda no seu caso."
        )
    if dias < 1 or not 1 <= minimo <= dias:
        raise ValueError("Precisa de 1 <= minimo <= dias")
    p = previsao[[*CHAVES, "yhat"]].copy()
    j = p.merge(real[[*CHAVES, "y"]], on=CHAVES, how="left")
    j["dia"] = j["ds"].dt.normalize()
    ok = j["y"].notna() & j["yhat"].notna()
    d = j[ok].groupby(["unique_id", "dia"])[["y", "yhat"]].sum().sort_index()
    anteriores = d.groupby(level=0).transform(lambda s: s.shift(1).rolling(dias, min_periods=minimo).sum())
    fator = (anteriores["y"] / anteriores["yhat"]).clip(*limites).rename("fator")
    p["dia"] = p["ds"].dt.normalize()
    p = p.merge(fator.reset_index(), on=["unique_id", "dia"], how="left")
    p["fator"] = p["fator"].fillna(1.0)
    p["yhat"] = p["yhat"] * p["fator"]
    return p.drop(columns="dia")
