"""Metricas e testes de significancia da previsao.

Portado de `experimentos/testes_previsao/scripts/05_avalia.py` (protocolo v2). Convencao de
verificacao solar deterministica de Yang et al. (2020): erros normalizados pela media do real nas
horas avaliadas, e skill contra uma referencia declarada.

Duas decisoes vieram dos resultados e estao embutidas de proposito:

- **Vies junto do erro.** Os fundacionais subestimam o consumo em ~20% porque preveem a mediana; um
  RMSE bom escondia isso. `metricas()` sempre devolve MBE.
- **Suporte comum.** Modelo, alvo e referencia sao pareados nas MESMAS horas finitas antes de
  qualquer conta. Sem isso, dois modelos avaliados em horas diferentes aparecem comparaveis e nao sao.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

CHAVES = ["unique_id", "ds"]


def alinha(
    previsao: pd.DataFrame, real: pd.DataFrame, referencia: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pareia alvo, modelo e referencia nas horas em que os tres sao finitos.

    Devolve (modelo, referencia) com o mesmo indice e a mesma ordem, prontos para comparacao pareada.
    Levanta se nao sobrar nada: silenciosamente comparar conjuntos vazios e pior que falhar.
    """
    r = referencia[[*CHAVES, "yhat"]].rename(columns={"yhat": "yhat_ref"})
    m = previsao.merge(real, on=CHAVES, validate="one_to_one").merge(r, on=CHAVES, validate="one_to_one")
    m = m.loc[m[["y", "yhat", "yhat_ref"]].abs().lt(np.inf).all(axis=1)]  # finito: NaN e inf saem
    m = m.sort_values(CHAVES, kind="stable").reset_index(drop=True)
    if m.empty:
        raise ValueError("Sem horas finitas em comum entre modelo, alvo e referencia")
    ref = m[[*CHAVES, "y", "yhat_ref"]].rename(columns={"yhat_ref": "yhat"})
    return m.drop(columns="yhat_ref"), ref


def metricas(df: pd.DataFrame) -> dict[str, float]:
    """nMAE, nRMSE, MBE, RMSE e R2, horarios e por energia diaria.

    `df` precisa ter as colunas `y`, `yhat`, `unique_id` e `ds`, e ja estar restrito as horas avaliadas.
    """
    e = df["yhat"] - df["y"]
    mu = df["y"].mean()
    if not np.isfinite(mu) or mu == 0:
        raise ValueError("Media do real nula ou nao finita: metricas normalizadas ficariam sem sentido")
    dia = df.assign(dia=df["ds"].dt.normalize()).groupby(["unique_id", "dia"])[["y", "yhat"]].sum()
    ed = dia["yhat"] - dia["y"]
    return {
        "nMAE": float(e.abs().mean() / mu),
        "nRMSE": float(np.sqrt((e**2).mean()) / mu),
        "MBE": float(e.mean() / mu),
        "RMSE": float(np.sqrt((e**2).mean())),
        "nMAE_diario": float(ed.abs().mean() / dia["y"].mean()),
        "R2": float(1 - (e**2).sum() / ((df["y"] - mu) ** 2).sum()),
        "R2_diario": _r2(ed, dia["y"]),
    }


def _r2(erro: pd.Series, real: pd.Series) -> float:
    """R2 que devolve NaN quando o real nao varia, em vez de dividir por zero.

    Acontece de verdade com um unico dia de teste (ou totais diarios identicos): nesse caso o R2 nao
    esta definido, e um NaN explicito e mais honesto que um -inf vindo de um aviso engolido.
    """
    var = float(((real - real.mean()) ** 2).sum())
    if var == 0.0:
        return float("nan")
    return float(1 - (erro**2).sum() / var)


def skill(df: pd.DataFrame, referencia: pd.DataFrame) -> float:
    """1 - RMSE/RMSE_referencia. Zero = igual a referencia; negativo = pior que ela."""
    e = df["yhat"].to_numpy() - df["y"].to_numpy()
    er = referencia["yhat"].to_numpy() - referencia["y"].to_numpy()
    base = np.sqrt((er**2).mean())
    if base == 0:
        raise ValueError("Referencia com erro zero: skill seria infinito")
    return float(1 - np.sqrt((e**2).mean()) / base)


def skill_ic95(
    df: pd.DataFrame, referencia: pd.DataFrame, *, reamostragens: int = 1000, semente: int = 42
) -> tuple[float, float]:
    """IC 95% do skill reamostrando DIAS INTEIROS, nao horas.

    Reamostrar horas trataria horas do mesmo dia como independentes, o que elas nao sao (a nebulosidade
    e o erro duram o dia). O bootstrap por dia e o que da um IC honesto.
    """
    rng = np.random.default_rng(semente)
    k = df["unique_id"].astype(str) + "|" + df["ds"].dt.normalize().astype(str)
    se = ((df["yhat"] - df["y"]) ** 2).groupby(k.values).agg(["sum", "count"])
    sr = (
        pd.Series(((referencia["yhat"].to_numpy() - df["y"].to_numpy()) ** 2), index=df.index)
        .groupby(k.values)
        .sum()
    )
    n = len(se)
    if n < 2:
        raise ValueError("Menos de dois dias: nao da para estimar IC por bootstrap de dias")
    idx = rng.integers(0, n, size=(reamostragens, n))
    a, c, r = se["sum"].to_numpy(), se["count"].to_numpy(), sr.to_numpy()
    s = 1 - np.sqrt(a[idx].sum(1) / c[idx].sum(1)) / np.sqrt(r[idx].sum(1) / c[idx].sum(1))
    lo, hi = np.percentile(s, [2.5, 97.5])
    return float(lo), float(hi)


def diebold_mariano(e1: pd.Series, e2: pd.Series) -> tuple[float, float, float]:
    """Diebold-Mariano por dia entre dois modelos. Devolve (perda extra relativa, estatistica, p).

    `e1` e `e2` sao erros quadraticos indexados por (unique_id, ds). Perda media por dia, variancia
    de Newey-West com defasagem floor(T^(1/3)), correcao de Harvey-Leybourne-Newbold e t de Student
    com T-1 graus. Diferenca positiva = o primeiro erra mais.

    Uma nao rejeicao NAO prova equivalencia, e o "melhor" costuma ser escolhido no mesmo teste: isto e
    um filtro de leitura, nao um teste de superioridade.
    """
    j = pd.concat([e1.rename("a"), e2.rename("b")], axis=1, join="inner").dropna()
    if j.empty:
        raise ValueError("Sem horas em comum entre os dois modelos")
    dias = pd.DatetimeIndex(j.index.get_level_values("ds")).normalize()
    d = (j["a"] - j["b"]).groupby(dias).mean().sort_index().to_numpy()
    T = len(d)
    if T < 10 or np.allclose(d, 0):
        return 0.0, 0.0, 1.0
    db = float(d.mean())
    x = d - db
    L = int(np.floor(T ** (1 / 3)))
    # Newey-West: variancia de longo prazo da diferenca de perda, com defasagem floor(T^(1/3)).
    v = float(x @ x / T + 2 * sum((1 - lag / (L + 1)) * (x[lag:] @ x[:-lag]) / T for lag in range(1, L + 1)))
    est = db / np.sqrt(max(v, 1e-30) / T) * np.sqrt((T - 1) / T)
    return float(db / j["b"].mean()), float(est), float(2 * stats.t.sf(abs(est), T - 1))


def holm(p: list[float] | np.ndarray) -> np.ndarray:
    """p ajustado por Holm, na ordem de entrada. Sem isso, comparar N modelos infla o falso positivo."""
    p = np.asarray(p, dtype=float)
    if p.size == 0:
        return p
    o = np.argsort(p)
    m = len(p)
    adj = np.maximum.accumulate((m - np.arange(m)) * p[o]).clip(max=1.0)
    out = np.empty(m)
    out[o] = adj
    return out


def erros_quadraticos(df: pd.DataFrame) -> pd.Series:
    """Erros quadraticos indexados por (unique_id, ds), no formato que o `diebold_mariano` espera."""
    return pd.Series(
        ((df["yhat"] - df["y"]) ** 2).to_numpy(),
        index=pd.MultiIndex.from_arrays([df["unique_id"], df["ds"]], names=CHAVES),
    )
