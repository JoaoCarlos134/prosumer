# -*- coding: utf-8 -*-
"""F2(f) do plano: modelo DIRETO para o total do dia no consumo, contra somar as 24 previsoes horarias.

Pergunta: para quem decide pelo total do dia (fatura, orcamento de energia), vale um modelo feito para o total,
ou basta somar a previsao horaria? A soma herda o vies e o ruido de 24 previsoes; um modelo direto ve so o que
importa para o total (nivel recente, dia da semana, estacao), mas tem 24 vezes menos linhas para aprender.

Modelo direto (fixado antes de ver o teste): LightGBM global, uma linha por (casa, dia). Atributos, todos
conhecidos as 00:00: totais dos 7 dias anteriores, media de 7 e de 28 dias, desvio de 7 dias, total do mesmo dia
da semana anterior, dia da semana, estacao (seno/cosseno do dia do ano) e a casa (categorica). Hiperparametros
menores que os do LightGBM horario (5.400 linhas, nao 130 mil): 300 arvores, taxa 0,03, 15 folhas, 20 por folha.
Origem movel do benchmark (refaz no inicio de cada dobra, so com dias anteriores).

Comparacao, nos MESMOS (casa, dia) de teste: skill do total do dia = 1 - RMSE/RMSE da referencia somada (o
"igual a ontem", persist_24h, a referencia horaria do consumo). Somados das previsoes gravadas do benchmark:
LightGBM, Ensemble-mediana, Ensemble-mediana-corrigida (a 1a por hora) e Timer-XL-84m (o 1o no total do dia em
05b). Diebold-Mariano (05_avalia) do direto contra o melhor somado, sobre o erro quadratico diario.
Portao (plano): skill +0,02 ou mais sobre o melhor somado.

Uso: python piloto_total_dia.py [caso]   (ambiente previsao, CPU, ~1 min; padrao casas_cons)
"""
import importlib
import json
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from comum import PREV, carrega, dias_teste, dobras
from piloto_comum import PILOTOS

R = importlib.import_module("02_referencias")
AV = importlib.import_module("05_avalia")
SOMADOS = ["LightGBM", "Ensemble-mediana", "Ensemble-mediana-corrigida", "Timer-XL-84m"]
COLS = [f"tot_d{k}" for k in range(1, 8)] + ["tot_media7", "tot_media28", "tot_desvio7", "dow", "doy_sin", "doy_cos",
                                            "serie_cod"]


def tabela_dias(d):
    blocos = []
    for k, (uid, g) in enumerate(d.groupby("unique_id", sort=False)):
        tot = R.matriz(g, "y").sum(axis=1, min_count=24)       # so dias com as 24 horas validas
        f = pd.DataFrame({f"tot_d{j}": tot.shift(j) for j in range(1, 8)})
        f["tot_media7"] = tot.shift(1).rolling(7, min_periods=5).mean()
        f["tot_media28"] = tot.shift(1).rolling(28, min_periods=20).mean()
        f["tot_desvio7"] = tot.shift(1).rolling(7, min_periods=5).std()
        f["y"], f["unique_id"], f["serie_cod"] = tot, uid, k
        blocos.append(f.rename_axis("dia").reset_index())
    t = pd.concat(blocos, ignore_index=True)
    t["dow"] = t.dia.dt.dayofweek
    t["doy_sin"], t["doy_cos"] = np.sin(2 * np.pi * t.dia.dt.dayofyear / 365.25), np.cos(2 * np.pi * t.dia.dt.dayofyear / 365.25)
    return t


def somado(modelo, caso):
    p = pd.read_parquet(PREV / f"{modelo}__{caso}__A.parquet")
    p["yhat"] = p.yhat.clip(lower=0)
    s = p.groupby(["unique_id", p.ds.dt.normalize()]).yhat.agg(["sum", "count"])
    return s.loc[s["count"] == 24, "sum"]


if __name__ == "__main__":
    caso = next((a for a in sys.argv[1:] if a in ("casas_cons", "casas_prod", "usinas")), "casas_cons")
    t0 = time.time()
    d = carrega(caso)
    t = tabela_dias(d)
    teste = pd.DataFrame(dias_teste(d, caso), columns=["unique_id", "dia"]).merge(t, on=["unique_id", "dia"])
    teste["direto"] = np.nan
    for ini, fim in dobras(caso):
        tr = t[(t.dia < ini) & t.y.notna()]
        m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=20,
                              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=42, verbose=-1)
        m.fit(tr[COLS], tr.y, categorical_feature=["serie_cod"])
        sel = (teste.dia >= ini) & (teste.dia <= fim)
        teste.loc[sel, "direto"] = m.predict(teste.loc[sel, COLS])
    teste = teste.rename(columns={"dia": "ds"}).set_index(["unique_id", "ds"])
    real = teste.y
    prev = {"direto (LightGBM do total)": teste.direto.clip(lower=0)}
    prev.update({f"soma {m}": somado(m, caso) for m in SOMADOS})
    ref = somado(AV.REF[caso], caso)
    idx = real.index
    for s in list(prev.values()) + [ref]:
        idx = idx.intersection(s.dropna().index)
    rmse = lambda p: float(np.sqrt(np.mean((p.loc[idx] - real.loc[idx]) ** 2)))
    r_ref = rmse(ref)
    res = {n: dict(skill_dia=round(1 - rmse(p) / r_ref, 4), MBE=round(float((p.loc[idx] - real.loc[idx]).mean() / real.loc[idx].mean()), 4))
           for n, p in prev.items()}
    melhor = max((n for n in res if n.startswith("soma")), key=lambda n: res[n]["skill_dia"])
    e = lambda p: ((p.loc[idx] - real.loc[idx]) ** 2)
    dif, est, pval = AV.diebold_mariano(e(prev["direto (LightGBM do total)"]), e(prev[melhor]))
    out = dict(caso=caso, casa_dias=int(len(idx)), modelos=res, melhor_somado=melhor,
               ganho=round(res["direto (LightGBM do total)"]["skill_dia"] - res[melhor]["skill_dia"], 4),
               dm_p_direto_vs_melhor_somado=round(float(pval), 4))
    out["portao"] = bool(out["ganho"] >= 0.02)
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo[f"total-do-dia|{caso}|A"] = out
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"OK total do dia | {time.time() - t0:.0f} s", flush=True)
