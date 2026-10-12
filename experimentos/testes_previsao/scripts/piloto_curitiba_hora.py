# -*- coding: utf-8 -*-
"""Piloto: o clima da NASA de Curitiba esta 1 h atrasado? Quanto isso custa no regime B das usinas?

Achado de 11/10/2026 (`prosumer.quality.clock_offset`): o `ghi_horario` de Curitiba casa com o ceu claro 1 h
DEPOIS em todos os meses de 2021-2026 (Cascavel: 0). Causa provavel: o 01_prepara_dados alinhou as duas usinas
com os -55 min achados para Cascavel, mas a hora solar local (LST) da NASA e UTC-4 em Cascavel e UTC-3 em
Curitiba. Aqui: o LightGBM do benchmark (biblioteca, = o gravado ate 3,5e-18) no regime B das usinas, com as
exogenas da NASA de Curitiba (ghi_horario, poa_estimada, temp_ar_horaria) ADIANTADAS 1 h, contra o gravado.
O ceu claro (poa_ceu_claro) sai da posicao do sol e nao muda. Nada vai para previsoes/ nem para o metricas.csv.

Uso (ambiente da biblioteca): python piloto_curitiba_hora.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

import comum
from piloto_comum import PILOTOS, avalia_piloto, grava_piloto
from prosumer import metrics as pm
from prosumer.forecast import LightGBM, rolling_forecast

NASA = ["ghi_horario", "poa_estimada", "temp_ar_horaria"]


VARIANTES = {  # nome: (regime, colunas de Curitiba, deslocamento em horas; -1 = adianta, +1 = atrasa)
    "LightGBM-B-curitiba-1h": ("B", NASA, -1),  # NASA no relogio verdadeiro do sol
    "LightGBM-B-curitiba-ceuclaro+1h": ("B", ["poa_ceu_claro"], +1),  # ceu claro no relogio da usina
    "LightGBM-C-curitiba+1h": ("C", comum.EXOG, +1),  # previsao e ceu claro no relogio da usina
}


def carrega_corrigido(caso, regime, cols, k):
    d = comum.carrega(caso, regime)
    c = d.unique_id == "Curitiba"
    for col in cols:  # k = -1: o valor de ds passa a ser o rotulado ds+1; k = +1: o rotulado ds-1
        d.loc[c, col] = d.loc[c].groupby("unique_id")[col].shift(-k).to_numpy()
    d[cols] = d[cols].ffill().bfill()  # a hora da ponta fica sem vizinho
    return d


def por_usina(nome, regime):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
    import test_benchmark_regression as T
    p = pd.read_parquet((PILOTOS if nome in VARIANTES else comum.PREV) / f"{nome}__usinas__{regime}.parquet")
    p = p[["unique_id", "ds", "yhat"]]
    p["yhat"] = p.yhat.clip(lower=0)
    m, r = pm.align(p, T.evaluated_actual("usinas"), T.reference("usinas"))
    return {u: round(pm.skill(m[m.unique_id == u], r[r.unique_id == u]), 4) for u in ("Cascavel", "Curitiba")} | {
        "juntas": round(pm.skill(m, r), 4)}


if __name__ == "__main__":
    pedidas = [a for a in sys.argv[1:] if a in VARIANTES] or list(VARIANTES)
    for nome in pedidas:
        regime, cols, k = VARIANTES[nome]
        task = comum.tarefa(carrega_corrigido("usinas", regime, cols, k), "usinas", contexto=168, exog=True)
        fc = rolling_forecast(LightGBM(comum.EXOG, clear_sky="poa_ceu_claro"), task)
        grupos = fc.assign(dia=fc.ds.dt.normalize()).groupby(["unique_id", "dia"], sort=False)
        jan = [dict(unique_id=u, ds_fut=g.ds.dt.tz_localize(None).to_numpy()) for (u, _), g in grupos]
        grava_piloto(nome, "usinas", regime, jan, [g.yhat.to_numpy() for _, g in grupos])
        res = {"gravado": por_usina("LightGBM", regime), "variante": por_usina(nome, regime)}
        print(nome, json.dumps(res), flush=True)
        avalia_piloto(nome, "usinas", regime, extra=res)
