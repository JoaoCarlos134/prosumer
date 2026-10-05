# -*- coding: utf-8 -*-
"""Ensemble sem escolha a posteriori: mediana, hora a hora, de TODOS os modelos que nao sao referencia.

A regra e fixa antes de olhar o teste (nada de "os 3 melhores"), para nao vazar informacao do teste
para a escolha dos membros. Grava como modelo 'Ensemble-mediana' em cada caso e regime.
"""
import pandas as pd
from comum import PREV, grava, H, DIAGNOSTICOS

REFERENCIAS = {"persist_24h", "semanal_168h", "media_7d", "persist_ceu_claro", "Ensemble-mediana"}
todas = pd.concat([pd.read_parquet(f) for f in PREV.glob("*.parquet")], ignore_index=True)
todas = todas[~todas.modelo.isin(REFERENCIAS) & ~todas.regime.isin(DIAGNOSTICOS)]   # diagnosticos: so 2 modelos
todas["yhat"] = todas.yhat.clip(lower=0)
for (caso, regime), g in todas.groupby(["caso", "regime"]):
    membros = sorted(g.modelo.unique())
    med = g.groupby(["unique_id", "ds"]).yhat.median().reset_index()
    med["dia"] = med.ds.dt.normalize()
    jan, prev = [], []
    for (u, dia), x in med.groupby(["unique_id", "dia"]):
        if len(x) == H:
            jan.append(dict(unique_id=u, ds_fut=pd.DatetimeIndex(x.ds))); prev.append(x.yhat.to_numpy())
    grava("Ensemble-mediana", caso, regime, jan, prev)
    print("%-10s %s  mediana de %d modelos: %s" % (caso, regime, len(membros), ", ".join(membros)))
