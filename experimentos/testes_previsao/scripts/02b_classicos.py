# -*- coding: utf-8 -*-
"""Classicos estatisticos (StatsForecast): AutoARIMA, AutoETS, AutoTheta e MSTL.

Passo T (07/10/2026). Ambiente proprio `~/.venvs/classicos` (ver ambientes/LEIA-ME.md): o
statsforecast traz statsmodels e numba, que nao entram nos quatro ambientes congelados.

Mesmo protocolo das redes: origem movel, ajuste do zero no inicio de cada dobra e janela andando um
dia por vez com o historico real dentro da dobra (`refit=False` no cross_validation, como o
`04_redes_treinadas.py` faz com o NeuralForecast). AutoARIMA no regime B recebe as exogenas de clima,
virando ARIMAX; os outros tres sao univariados e rodam so no regime A.

Uso: python 02b_classicos.py [caso ...] [--regimes A,B] [--modelos AutoETS,MSTL]
Tempos em resultados/tempos_classicos.json; modelos ja feitos sao pulados.
"""
import json
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, AutoETS, AutoTheta, MSTL

from comum import CASOS, EXOG, H, REGIMES, RES, carrega, dobras, grava

ARGS = sys.argv[1:]
CASOS_ARG = [a for a in ARGS if a in CASOS] or list(CASOS)
SO_REGIMES = ARGS[ARGS.index("--regimes") + 1].split(",") if "--regimes" in ARGS else None
SO_MODELOS = ARGS[ARGS.index("--modelos") + 1].split(",") if "--modelos" in ARGS else None
LOG = RES / "tempos_classicos.json"
tempos = json.loads(LOG.read_text()) if LOG.exists() else {}

# season_length=24: o ciclo diario e o que domina a serie horaria. O MSTL leva tambem o semanal.
# Os quatro aceitam so o historico; o AutoARIMA aceita exogenas e por isso vale nos regimes com clima.
def modelos(regime):
    univariados = {
        "AutoETS": lambda: AutoETS(season_length=24),
        "AutoTheta": lambda: AutoTheta(season_length=24),
        "MSTL": lambda: MSTL(season_length=[24, 168], alias="MSTL"),
    }
    # AutoARIMA com os padroes (approximation=False, nmodels=94) levou 54.554 s = 15,2 h so em
    # usinas|A, com DUAS series: faz busca de ordem por maxima verossimilhanca em 94 candidatos sobre
    # uma serie horaria de ~60 mil pontos, cinco vezes (uma por dobra). Inviavel nos outros seis casos.
    # approximation=True troca a verossimilhanca exata por soma de quadrados condicional na SELECAO da
    # ordem (o remedio padrao para serie longa) e as ordens maximas sao limitadas. A ordem escolhida
    # pode diferir da do padrao; a entrada em tempos_classicos.json registra a configuracao usada.
    base = {"AutoARIMA": lambda: AutoARIMA(season_length=24, approximation=True, stepwise=True,
                                           max_p=3, max_q=3, max_P=1, max_Q=1, max_order=5, nmodels=24)}
    return {**base, **univariados} if regime == "A" else base


def prepara(caso, regime):
    """Formato do StatsForecast: unique_id, ds, y (+ exogenas no regime com clima).

    As horas invalidas sao interpoladas: os classicos nao tem mascara de validade, e deixar NaN faria
    o ajuste falhar serie a serie. E a mesma interpolacao que `comum.janelas` usa no historico.
    """
    d = carrega(caso, regime)
    cols = ["unique_id", "ds", "y"] + (EXOG if regime != "A" else [])
    x = d[cols].copy()
    x["y"] = x.groupby("unique_id")["y"].transform(lambda s: s.interpolate(limit_direction="both"))
    if regime != "A":
        for c in EXOG:
            x[c] = x.groupby("unique_id")[c].transform(lambda s: s.interpolate(limit_direction="both"))
    return x.dropna(subset=["y"]).reset_index(drop=True)


def para_janelas(cv, col):
    cv = cv.copy()
    cv["dia"] = cv["ds"].dt.normalize()
    jan, prev = [], []
    for (uid, dia), g in cv.groupby(["unique_id", "dia"]):
        if len(g) == H:
            g = g.sort_values("ds")
            jan.append(dict(unique_id=uid, ds_fut=pd.DatetimeIndex(g["ds"])))
            prev.append(g[col].to_numpy())
    return jan, prev


def roda(nome, fab, caso, regime, df):
    jan, prev = [], []
    for ini, fim in dobras(caso):
        n = (fim.normalize() - ini).days + 1
        sf = StatsForecast(models=[fab()], freq="h", n_jobs=1)
        cv = sf.cross_validation(df=df[df["ds"] <= fim], h=H, n_windows=n, step_size=H, refit=False)
        cv = cv.reset_index() if "unique_id" not in cv.columns else cv
        col = [c for c in cv.columns if c not in ("unique_id", "ds", "cutoff", "y")][0]
        # Recorta a dobra: series que acabam antes das outras fazem o cross_validation recuar e
        # reemitir dias de uma dobra anterior (foi o que a casa H14 causou nas redes).
        cv = cv[(cv["ds"].dt.normalize() >= ini) & (cv["ds"].dt.normalize() <= fim.normalize())]
        j, p = para_janelas(cv, col)
        jan += j
        prev += p
    grava(nome, caso, regime, jan, prev)
    return len(jan)


if __name__ == "__main__":
    for caso in CASOS_ARG:
        for regime in REGIMES[caso]:
            if SO_REGIMES and regime not in SO_REGIMES:
                continue
            df = None
            for nome, fab in modelos(regime).items():
                if SO_MODELOS and nome not in SO_MODELOS:
                    continue
                chave = f"{nome}|{caso}|{regime}"
                if chave in tempos:
                    continue
                if df is None:
                    df = prepara(caso, regime)
                t0 = time.time()
                try:
                    n = roda(nome, fab, caso, regime, df)
                    # Rele o arquivo antes de gravar: dois processos deste script rodando ao mesmo
                    # tempo (ou um relancamento) sobrescreviam as entradas um do outro, porque `tempos`
                    # fica em memoria desde o import. Foi o que apagou AutoETS|casas_* em 08/10 — as
                    # previsoes ficaram no disco, so a anotacao se perdeu.
                    tempos = json.loads(LOG.read_text()) if LOG.exists() else {}
                    tempos[chave] = dict(segundos=round(time.time() - t0, 1), janelas=n,
                                         dobras=len(dobras(caso)), exogenas=(regime != "A"),
                                         config=("AutoARIMA approximation=True max_p=3 max_q=3 "
                                                 "max_P=1 max_Q=1 nmodels=24" if nome == "AutoARIMA" else "padrao"))
                    LOG.write_text(json.dumps(tempos, indent=1))
                    print("OK    %-12s %-10s %s  %5d janelas  %6.0f s"
                          % (nome, caso, regime, n, time.time() - t0), flush=True)
                except Exception as e:
                    print("FALHA %-12s %-10s %s  %s: %s"
                          % (nome, caso, regime, type(e).__name__, str(e)[:250]), flush=True)
