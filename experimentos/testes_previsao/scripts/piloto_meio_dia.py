# -*- coding: utf-8 -*-
"""F2(d) do plano: atualizar a previsao do pico da noite (17-21 h) ao MEIO-DIA, com a manha de hoje ja medida.

Pergunta: uma bateria ou um controle de carga decide o pico da noite (tarifa mais cara) e pode decidir as
12:00, nao as 00:00. Quanto as 12 horas da manha de hoje melhoram a previsao das 17-21 h?

Desenho (fixado antes de ver o teste), consumo das casas, regime A, horas 17, 18, 19 e 20 (o bloco
pico_17_21 do 05b):
- `00h`: LightGBM global treinado so nessas horas, com os atributos do benchmark (02_referencias), emitido
  as 00:00 como no benchmark. Isola o efeito de treinar so no pico.
- `12h`: o mesmo, mais o que se sabe as 12:00: as 12 horas de hoje (0-11 h), o total da manha de hoje e a razao
  manha de hoje / manha de ontem.
Mesmos hiperparametros do LightGBM do benchmark; origem movel do benchmark.
Comparacao nas mesmas (casa, hora) de teste: skill contra o "igual a ontem" (persist_24h) nessas horas; tambem
o LightGBM, o Ensemble-mediana-corrigida e o Timer-XL-84m (o 1o no bloco do pico em 05b) do benchmark, emitidos
as 00:00 e recortados nas mesmas horas.
Diebold-Mariano (05_avalia) do `12h` contra o melhor emitido as 00:00.
Portao (plano): skill +0,02 ou mais no pico sobre o melhor das 00:00.

Uso: python piloto_meio_dia.py [caso]   (ambiente previsao, CPU, ~2 min; padrao casas_cons)
"""
import importlib
import json
import sys
import time

import numpy as np
import pandas as pd

from comum import PREV, carrega, dias_teste, dobras
from piloto_comum import PILOTOS

R = importlib.import_module("02_referencias")
AV = importlib.import_module("05_avalia")
PICO = [17, 18, 19, 20]
BASE = ["h", "dow", "doy_sin", "doy_cos", "serie_cod", "y_d1", "y_d2", "y_d7", "y_media7", "tot_d1", "tot_media7"]
MANHA = [f"hoje_h{k}" for k in range(12)] + ["manha_hoje", "manha_razao"]


def com_manha(t, d):
    blocos = []
    for uid, g in d.groupby("unique_id", sort=False):
        Y = R.matriz(g, "y")
        m = pd.DataFrame({f"hoje_h{k}": Y[k] for k in range(12)})
        m["manha_hoje"] = Y.loc[:, :11].sum(axis=1, min_count=10)
        m["manha_razao"] = (m.manha_hoje / m.manha_hoje.shift(1)).replace([np.inf, -np.inf], np.nan)
        blocos.append(m.rename_axis("dia").reset_index().assign(unique_id=uid))
    return t.merge(pd.concat(blocos, ignore_index=True), on=["unique_id", "dia"], how="left")


def recorte(modelo, caso):
    p = pd.read_parquet(PREV / f"{modelo}__{caso}__A.parquet")
    p = p[p.ds.dt.hour.isin(PICO)]
    return p.set_index(["unique_id", "ds"]).yhat.clip(lower=0)


if __name__ == "__main__":
    caso = next((a for a in sys.argv[1:] if a in ("casas_cons", "casas_prod", "usinas")), "casas_cons")
    t0 = time.time()
    d = carrega(caso)
    t = com_manha(R.tabela_features(d, caso), d)
    t = t[t.h.isin(PICO)]
    teste = pd.DataFrame(dias_teste(d, caso), columns=["unique_id", "dia"]).merge(t, on=["unique_id", "dia"])
    for v in ("00h", "12h"):
        teste[v] = np.nan
    for ini, fim in dobras(caso):
        tr = t[(t.dia < ini) & t.y.notna()]
        sel = (teste.dia >= ini) & (teste.dia <= fim)
        teste.loc[sel, "00h"] = R.lgbm(tr, teste[sel], BASE)
        teste.loc[sel, "12h"] = R.lgbm(tr, teste[sel], BASE + MANHA)
    teste = teste.set_index(["unique_id", "ds"])
    real = teste.y
    prev = {"LightGBM-pico-00h": teste["00h"].clip(lower=0), "LightGBM-pico-12h": teste["12h"].clip(lower=0),
            "LightGBM (benchmark, 00h)": recorte("LightGBM", caso),
            "Ensemble-mediana-corrigida (benchmark, 00h)": recorte("Ensemble-mediana-corrigida", caso),
            "Timer-XL-84m (benchmark, 00h)": recorte("Timer-XL-84m", caso)}
    ref = recorte(AV.REF[caso], caso)
    idx = real.dropna().index
    for s in list(prev.values()) + [ref]:
        idx = idx.intersection(s.dropna().index)
    rmse = lambda p: float(np.sqrt(np.mean((p.loc[idx] - real.loc[idx]) ** 2)))
    r_ref = rmse(ref)
    res = {n: dict(skill_pico=round(1 - rmse(p) / r_ref, 4),
                   MBE=round(float((p.loc[idx] - real.loc[idx]).mean() / real.loc[idx].mean()), 4)) for n, p in prev.items()}
    melhor = max((n for n in res if n != "LightGBM-pico-12h"), key=lambda n: res[n]["skill_pico"])
    e = lambda p: (p.loc[idx] - real.loc[idx]) ** 2
    _, _, pval = AV.diebold_mariano(e(prev["LightGBM-pico-12h"]), e(prev[melhor]))
    out = dict(caso=caso, horas=int(len(idx)), horas_do_pico=PICO, modelos=res, melhor_00h=melhor,
               ganho=round(res["LightGBM-pico-12h"]["skill_pico"] - res[melhor]["skill_pico"], 4),
               dm_p_12h_vs_melhor_00h=round(float(pval), 4))
    out["portao"] = bool(out["ganho"] >= 0.02)
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo[f"meio-dia|{caso}|A"] = out
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"OK meio-dia | {time.time() - t0:.0f} s", flush=True)
