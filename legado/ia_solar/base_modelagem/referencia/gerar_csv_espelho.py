# -*- coding: utf-8 -*-
"""Gera o CSV espelho do parquet (mesmas linhas, mesmas colunas) e uma amostra
pequena para inspecao rapida."""
import pandas as pd, numpy as np, os

from pathlib import Path
BASE = str(Path(__file__).resolve().parents[1])           # base_modelagem/

for usina, pasta in [("Cascavel", "cascavel"), ("Curitiba", "curitiba")]:
    dst = os.path.join(BASE, pasta)
    pq  = os.path.join(dst, "base_%s_5min.parquet" % usina)
    p = pd.read_parquet(pq)

    # 1. espelho exato
    csv = os.path.join(dst, "base_%s_5min.csv" % usina)
    p.to_csv(csv, index=False, sep=";", decimal=",", encoding="utf-8-sig")

    # confere o ida-e-volta
    v = pd.read_csv(csv, sep=";", decimal=",", encoding="utf-8-sig", parse_dates=["data_hora"])
    num = [c for c in p.columns if pd.api.types.is_numeric_dtype(p[c])]
    ok_lin = len(v) == len(p)
    ok_col = list(v.columns) == list(p.columns)
    dif = float(np.nanmax([np.nanmax(np.abs(v[c].values - p[c].values)) for c in num]))
    print("%s" % usina)
    print("   base_%s_5min.csv        %7d linhas  %6.1f MB   linhas iguais: %s  colunas iguais: %s  maior diferenca: %.2e"
          % (usina, len(v), os.path.getsize(csv)/1e6, ok_lin, ok_col, dif))

    # 2. amostra pequena: 6 dias representativos, do mais nublado ao mais limpo
    d = p.copy(); d["dia"] = pd.to_datetime(d.data_hora).dt.date
    porc = d.groupby("dia").kt_diario.first().dropna()
    alvos = porc.quantile([0.05, 0.30, 0.50, 0.70, 0.90, 0.98]).values
    dias = [porc.sub(a).abs().idxmin() for a in alvos]
    dias = list(dict.fromkeys(dias))
    am = d[d.dia.isin(dias)].drop(columns=["dia"])
    amc = os.path.join(dst, "amostra_%s_5min.csv" % usina)
    am.to_csv(amc, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    print("   amostra_%s_5min.csv     %7d linhas  %6.2f MB   %d dias: %s"
          % (usina, len(am), os.path.getsize(amc)/1e6, len(dias),
             ", ".join("%s (Kt %.2f)" % (x, porc[x]) for x in sorted(dias))))
