# -*- coding: utf-8 -*-
"""F2(a) do plano: combinar varias previsoes do tempo (NWP) no regime C das usinas, com o LightGBM.

Pergunta: o que falta no regime C e qualidade da previsao do tempo (B-curto x B nao e significativo). Varios
modelos numericos erram de formas diferentes; dar todos ao LightGBM (e o espalhamento entre eles, um indicador
de incerteza) melhora a previsao do dia seguinte?

Variantes, fixadas ANTES de ver o teste (dados de 08b_previsao_tempo_extra.py, mesmo horario e mesma conversao do
regime C: rotulo h+1 -> hora h, poa = poa_ceu_claro x indice de claridade do GHI previsto):
- `LightGBM-C-ifs`: o regime C do benchmark refeito aqui (so ECMWF IFS). Tem de reproduzir o LightGBM|C gravado:
  o script confere e para se nao bater (garante que a diferenca vem so das variaveis novas).
- `LightGBM-C-multi`: IFS + GFS + ICON (os do plano com arquivo completo desde 07/03/2024): GHI e POA previstos de
  cada um, mais a media e o desvio da POA entre os tres. Mesmo treino do C.
- `LightGBM-C-multi6`: IFS + GFS + ICON + Meteo-France + GEM + CMA (todos com arquivo completo). Mesmo treino.
- `LightGBM-C-aifs`: IFS + ECMWF AIFS (o modelo de IA do ECMWF), so com treino desde 18/02/2025 (o arquivo do
  AIFS comeca em 17/02/2025), e o par `LightGBM-C-ifs-curto` (so IFS, o mesmo treino curto) para separar o
  efeito do AIFS do efeito do treino mais curto.
Mesmos atributos, hiperparametros e origem movel do LightGBM do benchmark. Buracos de um NWP ficam NaN (o
LightGBM aceita).
Comparacao: skill contra a persistencia de ceu claro nas horas avaliadas do benchmark e Diebold-Mariano de cada
variante contra o seu par (multi x ifs; aifs x ifs-curto). Portao (plano): skill +0,02 ou mais.
Previsoes em resultados/pilotos/ (regime C) para o piloto_comum.py ranquear contra o benchmark.

Uso: python piloto_multi_nwp.py   (ambiente previsao, CPU, alguns minutos)
"""
import importlib
import json
import time

import numpy as np
import pandas as pd

from comum import DADOS, EXOG, H, PREV, carrega, dias_teste, dobras, ghi_ceu_claro
from piloto_comum import PILOTOS, grava_piloto

R = importlib.import_module("02_referencias")
AV = importlib.import_module("05_avalia")
INICIO_AIFS = pd.Timestamp("2025-02-18")
CAL = ["h", "dow", "doy_sin", "doy_cos", "serie_cod"]
LAGS = ["y_d1", "y_d2", "y_d7", "y_media7", "tot_d1", "tot_media7"]


def com_nwp(d, modelos):
    """Acrescenta ghi_<m> e poa_<m> de cada NWP, com a conversao do comum.exog_previsao."""
    P = pd.concat([pd.read_parquet(DADOS / "previsao_tempo.parquet"), pd.read_parquet(DADOS / "previsao_tempo_extra.parquet")])
    partes = []
    for uid, g in d.groupby("unique_id", sort=False):
        g = g.set_index("ds").copy()
        cs = ghi_ceu_claro(uid, g.index).where(lambda x: x > 20)
        for m in modelos:
            p = P[(P.serie == uid) & (P.modelo_nwp == m)].set_index("ds").sort_index()
            ghi = p.ghi_prev.shift(-1).reindex(g.index)
            kc = (ghi / cs).clip(0, 1.3)
            g[f"ghi_{m}"] = ghi.where(g.poa_ceu_claro > 0, 0.0)
            g[f"poa_{m}"] = (g.poa_ceu_claro * kc).where(g.poa_ceu_claro > 0, 0.0)
        partes.append(g.reset_index())
    out = pd.concat(partes, ignore_index=True)
    poas = [f"poa_{m}" for m in modelos]
    out["poa_media"], out["poa_desvio"] = out[poas].mean(axis=1), out[poas].std(axis=1)
    return out


VARIANTES = {  # nome: (NWP alem do IFS, inicio do treino)
    "LightGBM-C-ifs": ([], None),
    "LightGBM-C-multi": (["gfs_seamless", "icon_seamless"], None),
    "LightGBM-C-multi6": (["gfs_seamless", "icon_seamless", "meteofrance_seamless", "gem_seamless", "cma_grapes_global"], None),
    "LightGBM-C-aifs": (["ecmwf_aifs025_single"], INICIO_AIFS),
    "LightGBM-C-ifs-curto": ([], INICIO_AIFS),
}
PARES = {"LightGBM-C-multi": "LightGBM-C-ifs", "LightGBM-C-multi6": "LightGBM-C-ifs", "LightGBM-C-aifs": "LightGBM-C-ifs-curto"}

if __name__ == "__main__":
    caso, t0 = "usinas", time.time()
    todos = sorted({m for v, _ in VARIANTES.values() for m in v})
    d = com_nwp(carrega(caso, "C"), ["ecmwf_ifs025"] + todos)
    R.EXOG = EXOG + [c for c in d.columns if c.startswith(("ghi_", "poa_")) and c not in EXOG]  # matrizes extras
    t = R.tabela_features(d, caso)
    teste = pd.DataFrame(dias_teste(d, caso), columns=["unique_id", "dia"])
    tt = teste.merge(t, on=["unique_id", "dia"], how="left").sort_values(["unique_id", "dia", "h"]).reset_index(drop=True)
    jan = [dict(unique_id=u, ds_fut=pd.date_range(dia, periods=H, freq="h"))
           for u, dia in tt[["unique_id", "dia"]].drop_duplicates().itertuples(index=False)]
    prev = {}
    for nome, (extras, inicio) in VARIANTES.items():
        cols = CAL + LAGS + ["persist_ceu_claro"] + EXOG
        if extras:
            cols += [f"{k}_{m}" for m in extras for k in ("ghi", "poa")] + ["poa_media", "poa_desvio"]
            # media/desvio entre IFS e os extras desta variante (recalculados so com eles)
            poas = ["poa_ecmwf_ifs025"] + [f"poa_{m}" for m in extras]
            for tab in (t, tt):
                tab["poa_media"], tab["poa_desvio"] = tab[poas].mean(axis=1), tab[poas].std(axis=1)
        p = np.full(len(tt), np.nan)
        for ini, fim in dobras(caso):
            treino = t[(t.dia < ini) & t.y.notna() & ((t.dia >= inicio) if inicio is not None else True)]
            m = ((tt.dia >= ini) & (tt.dia <= fim)).to_numpy()
            p[m] = R.lgbm(treino, tt[m], cols)
        prev[nome] = p
        grava_piloto(nome, caso, "C", jan, p.reshape(-1, H))
        print(f"  {nome}: {len(cols)} atributos, {time.time() - t0:.0f} s", flush=True)

    # 1. o C refeito tem de bater com o LightGBM|C gravado no benchmark
    b = pd.read_parquet(PREV / "LightGBM__usinas__C.parquet").set_index(["unique_id", "ds"]).yhat
    k = tt.set_index(["unique_id", "ds"]).index
    dif = float(np.nanmax(np.abs(b.reindex(k).to_numpy() - prev["LightGBM-C-ifs"])))
    print(f"  conferencia LightGBM-C-ifs x LightGBM|C do benchmark: max |dif| = {dif:.2e}", flush=True)
    if dif > 1e-6:
        raise SystemExit("o C refeito nao reproduz o benchmark: parar e entender antes de comparar")

    # 2. skill e DM nas horas avaliadas do benchmark
    base = AV.real(caso)
    base = base[base.avalia].set_index(["unique_id", "ds"]).y
    ref = pd.read_parquet(PREV / f"{AV.REF[caso]}__{caso}__A.parquet").set_index(["unique_id", "ds"]).yhat
    S = {n: pd.Series(np.clip(p, 0, None), index=k) for n, p in prev.items()}
    idx = base.index.intersection(ref.dropna().index)
    for s in S.values():
        idx = idx.intersection(s.dropna().index)
    rmse = lambda s: float(np.sqrt(np.mean((s.loc[idx] - base.loc[idx]) ** 2)))
    r_ref = rmse(ref)
    res = {n: dict(skill=round(1 - rmse(s) / r_ref, 4)) for n, s in S.items()}
    e = lambda s: (s.loc[idx] - base.loc[idx]) ** 2
    for n, par in PARES.items():
        _, _, pval = AV.diebold_mariano(e(S[n]), e(S[par]))
        res[n].update(par=par, ganho=round(res[n]["skill"] - res[par]["skill"], 4), dm_p_vs_par=round(float(pval), 4),
                      portao=bool(res[n]["skill"] - res[par]["skill"] >= 0.02))
    out = dict(caso=caso, regime="C", horas=int(len(idx)), conferencia_max_dif=dif, variantes=res)
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo["multi-NWP|usinas|C"] = out
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"OK multi-NWP | {time.time() - t0:.0f} s", flush=True)
