# -*- coding: utf-8 -*-
"""F2(b) do plano: estimar a inclinacao e a direcao de cada telhado pelos dados e usar a irradiancia NO PLANO
do painel (POA) no regime B da FV das casas.

Hoje o B das casas da a todas as 10 casas o mesmo GHI medido no plano HORIZONTAL (a orientacao dos paineis nao e
publicada; ver comum.py). Um painel virado para leste rende de manha, um para oeste de tarde: no outono-inverno
irlandes (o teste, out-dez) o sol esta baixo e a diferenca entre horizontal e plano inclinado e grande.

Metodo (o do legado/ia_solar/.../a1_geometry.py, levado para dados horarios):
- posicao do sol em Dingle (52,14 N, 10,27 O; a localizacao exata das casas nao e publicada), 12 amostras de 5 min
  por hora, em UTC (as casas estao na hora local de Dublin, com horario de verao);
- GHI medido separado em direta e difusa pela correlacao de Erbs; transposicao isotropica (Liu-Jordan), albedo 0,2;
- por casa e por dobra, SO COM DADOS ANTERIORES a dobra: grade de inclinacao 0-60 graus (passo 5) e azimute
  90-270 graus (passo 10, 180 = sul); escolhe o par de maior R2 entre a producao horaria e a POA (horas com
  GHI > 50 W/m2 e producao valida). Fixado antes de ver o teste.
Variantes no regime B (casas_prod), mesma origem movel e mesmos hiperparametros do benchmark:
- `LightGBM-B-horizontal`: o B do benchmark refeito aqui; tem de reproduzir o LightGBM|casas_prod|B gravado;
- `LightGBM-B-poa`: poa_ceu_claro e poa_estimada no plano estimado de cada casa (o resto igual);
- `linear_fisico-B-poa`: energia = a + b x POA, por casa (o linear_fisico do benchmark e sobre o horizontal).
Portao (plano): skill +0,02 ou mais sobre o par horizontal. A geometria escolhida por casa e dobra fica no resumo.

Uso: python piloto_geometria.py   (ambiente previsao, CPU, alguns minutos)
Depois: python piloto_comum.py LightGBM-B-poa casas_prod B   (ambiente da biblioteca)
"""
import importlib
import json
import time

import numpy as np
import pandas as pd

from comum import DADOS, EXOG, H, PREV, carrega, dias_teste, dobras
from piloto_comum import PILOTOS, grava_piloto

R = importlib.import_module("02_referencias")
AV = importlib.import_module("05_avalia")
LAT, LON = 52.14, -10.27
INCL = np.arange(0, 61, 5.0)
AZIM = np.arange(90, 271, 10.0)
CAL = ["h", "dow", "doy_sin", "doy_cos", "serie_cod"]
LAGS = ["y_d1", "y_d2", "y_d7", "y_media7", "tot_d1", "tot_media7"]


def geometria_solar(ds_local):
    """Media horaria do vetor do sol (leste, norte, cima, so acima do horizonte) e de cos(z), a partir de 5 min."""
    utc = (pd.DatetimeIndex(ds_local).tz_localize("Europe/Dublin", ambiguous=True, nonexistent="shift_forward")
           .tz_convert("UTC").tz_localize(None))
    t = (utc.values[:, None] + (np.arange(12) * 5 + 2.5).astype("timedelta64[m]")[None, :].astype("timedelta64[ns]"))
    t = pd.DatetimeIndex(t.ravel())
    n = t.dayofyear.to_numpy(); g = 2 * np.pi / 365 * (n - 1 + (t.hour.to_numpy() - 12) / 24)
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    dec = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
           - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    w = np.radians((t.hour.to_numpy() * 60 + t.minute.to_numpy() + t.second.to_numpy() / 60 + eot + 4 * LON) / 4 - 180)
    la = np.radians(LAT)
    cima = np.sin(la) * np.sin(dec) + np.cos(la) * np.cos(dec) * np.cos(w)
    leste = -np.cos(dec) * np.sin(w)
    norte = np.cos(la) * np.sin(dec) - np.sin(la) * np.cos(dec) * np.cos(w)
    acima = cima > 0
    v = np.stack([leste * acima, norte * acima, cima * acima], -1).reshape(len(ds_local), 12, 3)
    return v.mean(1), (n.reshape(-1, 12)[:, 0])


def poa(ghi, sol, doy, beta, gamma):
    """POA isotropica (Erbs + Liu-Jordan) para inclinacao beta e azimute gamma (graus, 180 = sul)."""
    b, gm = np.radians(beta), np.radians(gamma)
    normal = np.array([np.sin(b) * np.sin(gm), np.sin(b) * np.cos(gm), np.cos(b)])
    cz = np.clip(sol[:, 2], 0, None)
    ci = np.clip(sol @ normal, 0, None)          # media horaria de cos(incidencia), ja com o sol acima do horizonte
    i0 = 1367 * (1 + 0.033 * np.cos(2 * np.pi * doy / 365)) * cz
    kt = np.where(i0 > 10, np.clip(ghi / np.where(i0 > 10, i0, 1), 0, 1), 0)
    kd = np.where(kt <= 0.22, 1 - 0.09 * kt, np.where(kt <= 0.8, 0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3
                                                     + 12.336 * kt**4, 0.165))
    dif = ghi * kd
    rb = np.where(cz > 0.02, ci / np.where(cz > 0.02, cz, 1), 0)
    return np.clip(ghi - dif, 0, None) * rb + dif * (1 + np.cos(b)) / 2 + 0.2 * ghi * (1 - np.cos(b)) / 2


def melhor_geometria(y, ghi, sol, doy):
    ok = np.isfinite(y) & (ghi > 50)
    melhor = (-1.0, 0.0, 180.0)
    for beta in INCL:
        for gamma in (AZIM if beta > 0 else [180.0]):
            p = poa(ghi[ok], sol[ok], doy[ok], beta, gamma)
            r2 = np.corrcoef(p, y[ok])[0, 1] ** 2
            if r2 > melhor[0]:
                melhor = (float(r2), float(beta), float(gamma))
    return melhor


if __name__ == "__main__":
    caso, t0 = "casas_prod", time.time()
    d = carrega(caso, "B")
    clima = pd.read_parquet(DADOS / "clima_casas_horario.parquet").set_index("ds")
    sol_h, doy_h = geometria_solar(clima.index)
    sol = pd.DataFrame(sol_h, index=clima.index, columns=["e", "n", "u"]); sol["doy"] = doy_h
    t = R.tabela_features(d, caso)        # o B horizontal do benchmark
    teste = pd.DataFrame(dias_teste(d, caso), columns=["unique_id", "dia"])
    tt = teste.merge(t, on=["unique_id", "dia"], how="left").sort_values(["unique_id", "dia", "h"]).reset_index(drop=True)
    jan = [dict(unique_id=u, ds_fut=pd.date_range(dia, periods=H, freq="h"))
           for u, dia in tt[["unique_id", "dia"]].drop_duplicates().itertuples(index=False)]
    cols = CAL + LAGS + ["persist_ceu_claro"] + EXOG
    prev = {n: np.full(len(tt), np.nan) for n in ("LightGBM-B-horizontal", "LightGBM-B-poa", "linear_fisico-B-poa")}
    escolhas = {}
    for ini, fim in dobras(caso):
        # geometria por casa com os dados anteriores a dobra
        dd = []
        for uid, g in d.groupby("unique_id", sort=False):
            g = g.set_index("ds")
            s = sol.reindex(g.index)
            tr = g.index < ini
            r2, beta, gamma = melhor_geometria(g.y.to_numpy()[tr], g.ghi_horario.to_numpy()[tr],
                                               s[["e", "n", "u"]].to_numpy()[tr], s.doy.to_numpy()[tr])
            escolhas.setdefault(uid, {})[str(ini.date())] = dict(inclinacao=beta, azimute=gamma, R2=round(r2, 4))
            sv, dv = s[["e", "n", "u"]].to_numpy(), s.doy.to_numpy()
            g = g.copy()
            g["poa_estimada"] = poa(g.ghi_horario.to_numpy(), sv, dv, beta, gamma)
            g["poa_ceu_claro"] = poa(clima.ghi_ceu_claro.reindex(g.index).to_numpy(), sv, dv, beta, gamma)
            dd.append(g.reset_index())
        tp = R.tabela_features(pd.concat(dd, ignore_index=True), caso)
        ttp = tt[["unique_id", "dia", "h"]].merge(tp, on=["unique_id", "dia", "h"], how="left")
        m = ((tt.dia >= ini) & (tt.dia <= fim)).to_numpy()
        prev["LightGBM-B-horizontal"][m] = R.lgbm(t[(t.dia < ini) & t.y.notna()], tt[m], cols)
        trp = tp[(tp.dia < ini) & tp.y.notna()]
        prev["LightGBM-B-poa"][m] = R.lgbm(trp, ttp[m], cols)
        prev["linear_fisico-B-poa"][m] = R.linear_fisico(trp, ttp[m]).to_numpy()
        print(f"  dobra {ini.date()}: " + ", ".join(f"{u} {v[str(ini.date())]['inclinacao']:.0f}/{v[str(ini.date())]['azimute']:.0f}"
                                                   for u, v in escolhas.items()), flush=True)
    for n, p in prev.items():
        grava_piloto(n, caso, "B", jan, p.reshape(-1, H))

    b = pd.read_parquet(PREV / "LightGBM__casas_prod__B.parquet").set_index(["unique_id", "ds"]).yhat
    k = tt.set_index(["unique_id", "ds"]).index
    dif = float(np.nanmax(np.abs(b.reindex(k).to_numpy() - prev["LightGBM-B-horizontal"])))
    print(f"  conferencia LightGBM-B-horizontal x LightGBM|casas_prod|B: max |dif| = {dif:.2e}", flush=True)
    if dif > 1e-6:
        raise SystemExit("o B refeito nao reproduz o benchmark: parar e entender antes de comparar")

    base = AV.real(caso)
    base = base[base.avalia].set_index(["unique_id", "ds"]).y
    ref = pd.read_parquet(PREV / f"{AV.REF[caso]}__{caso}__A.parquet").set_index(["unique_id", "ds"]).yhat
    lf = pd.read_parquet(PREV / "linear_fisico__casas_prod__B.parquet").set_index(["unique_id", "ds"]).yhat
    S = {n: pd.Series(np.clip(p, 0, None), index=k) for n, p in prev.items()}
    S["linear_fisico (benchmark, horizontal)"] = lf.clip(lower=0)
    idx = base.index.intersection(ref.dropna().index)
    for s in S.values():
        idx = idx.intersection(s.dropna().index)
    rmse = lambda s: float(np.sqrt(np.mean((s.loc[idx] - base.loc[idx]) ** 2)))
    r_ref = rmse(ref)
    res = {n: dict(skill=round(1 - rmse(s) / r_ref, 4)) for n, s in S.items()}
    e = lambda s: (s.loc[idx] - base.loc[idx]) ** 2
    for n, par in {"LightGBM-B-poa": "LightGBM-B-horizontal", "linear_fisico-B-poa": "linear_fisico (benchmark, horizontal)"}.items():
        _, _, pval = AV.diebold_mariano(e(S[n]), e(S[par]))
        res[n].update(par=par, ganho=round(res[n]["skill"] - res[par]["skill"], 4), dm_p_vs_par=round(float(pval), 4),
                      portao=bool(res[n]["skill"] - res[par]["skill"] >= 0.02))
    out = dict(caso=caso, regime="B", horas=int(len(idx)), conferencia_max_dif=dif, variantes=res, geometria=escolhas)
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo["geometria-telhado|casas_prod|B"] = out
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "geometria"}, indent=1, ensure_ascii=False))
    print(f"OK geometria | {time.time() - t0:.0f} s", flush=True)
