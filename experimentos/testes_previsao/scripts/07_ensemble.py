# -*- coding: utf-8 -*-
"""Ensemble sem escolha a posteriori: mediana, hora a hora, de TODOS os modelos que nao sao referencia.

A regra e fixa antes de olhar o teste (nada de "os 3 melhores"), para nao vazar informacao do teste
para a escolha dos membros. Grava como modelo 'Ensemble-mediana' em cada caso e regime.

Desde 09/10/2026 grava tambem 'Ensemble-mediana-corrigida', SO no consumo das casas: a mesma mediana
multiplicada pelo fator real/previsto dos 14 dias anteriores com dados (minimo 7; antes disso, fator 1;
limitado a 0,5-2,0), por casa. So usa o passado: o fator do dia D sai dos dias ate D-1. E o mesmo
algoritmo de `prosumer.postprocessing.correct_bias` (os scripts do benchmark rodam sem a
biblioteca; um teste confere que os dois dao o mesmo resultado). Na geracao solar a correcao piora
(piloto de 09/10/2026), por isso nao e aplicada la.
"""
import pandas as pd
from comum import PREV, grava, H, DIAGNOSTICOS, carrega

REFERENCIAS = {"persist_24h", "semanal_168h", "media_7d", "persist_ceu_claro", "Ensemble-mediana",
               "Ensemble-mediana-corrigida"}
CORRIGE = {"casas_cons"}            # so consumo
DIAS, MINIMO, LIMITES = 14, 7, (0.5, 2.0)


def corrige_vies(prev, real):
    """prev: unique_id, ds, yhat; real: unique_id, ds, y. Mesma regra de prosumer.postprocessing.correct_bias."""
    j = prev.merge(real, on=["unique_id", "ds"], how="left")
    j["dia"] = j.ds.dt.normalize()
    ok = j.y.notna() & j.yhat.notna()
    d = j[ok].groupby(["unique_id", "dia"])[["y", "yhat"]].sum().sort_index()
    ant = d.groupby(level=0).transform(lambda s: s.shift(1).rolling(DIAS, min_periods=MINIMO).sum())
    fator = (ant.y / ant.yhat).clip(*LIMITES).rename("fator").reset_index()
    p = prev.assign(dia=prev.ds.dt.normalize()).merge(fator, on=["unique_id", "dia"], how="left")
    p["fator"] = p.fator.fillna(1.0)
    return p.assign(yhat=p.yhat * p.fator).drop(columns=["dia", "fator"])


todas = pd.concat([pd.read_parquet(f) for f in PREV.glob("*.parquet")], ignore_index=True)
todas = todas[~todas.modelo.isin(REFERENCIAS) & ~todas.regime.isin(DIAGNOSTICOS)]   # diagnosticos: so 2 modelos
todas["yhat"] = todas.yhat.clip(lower=0)
for (caso, regime), g in todas.groupby(["caso", "regime"]):
    membros = sorted(g.modelo.unique())
    med = g.groupby(["unique_id", "ds"]).yhat.median().reset_index()
    versoes = [("Ensemble-mediana", med)]
    if caso in CORRIGE:
        versoes.append(("Ensemble-mediana-corrigida", corrige_vies(med, carrega(caso)[["unique_id", "ds", "y"]])))
    for nome, v in versoes:
        v = v.assign(dia=v.ds.dt.normalize())
        jan, prev = [], []
        for (u, dia), x in v.groupby(["unique_id", "dia"]):
            if len(x) == H:
                jan.append(dict(unique_id=u, ds_fut=pd.DatetimeIndex(x.ds))); prev.append(x.yhat.to_numpy())
        grava(nome, caso, regime, jan, prev)
    print("%-10s %s  mediana de %d modelos: %s" % (caso, regime, len(membros), ", ".join(membros)))
