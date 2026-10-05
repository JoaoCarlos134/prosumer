# -*- coding: utf-8 -*-
"""Monta a base unica de modelagem com os dois sites.

Regras aplicadas aqui (para que o script de modelos nao precise repeti-las):
  * apenas registros diurnos
  * sem as colunas que sao o proprio alvo reescrito (vazamento)
  * fora os registros acima da potencia nominal do inversor
  * irradiancia horaria da NASA POWER ja rebaixada para 5 min: poa_ceu_claro x kc_horario
"""
import numpy as np, pandas as pd, json, sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]            # base_modelagem/
AMBAS = BASE / "ambas_usinas"
sys.path.insert(0, str(BASE.parent / "analise" / "comum" / "scripts"))
from caminhos import caminho                                # frames de 5 min da analise

def prep(frame, meta, site, cap_kwp, kw_ac, extra=None):
    f = pd.read_parquet(frame); f["ts"] = pd.to_datetime(f.timestamp)
    f = f[f.cosz > 0]
    f = f[f.p_ac.notna() & (f.p_ac >= 0) & (f.p_ac <= kw_ac*1000)]
    out = pd.DataFrame(dict(
        site=site,
        data_hora=f.ts.values,
        ano=f.ts.dt.year.values, mes=f.ts.dt.month.values, dia_do_ano=f.doy.values,
        hora_solar=f.solar_time.values,
        elevacao_solar=f.elev.values,
        cos_zenite=f.cosz.values,
        poa_ceu_claro=f.poa_cs.values,
        kc_horario=f.h_kc.values if "h_kc" in f else np.nan,
        ghi_horario=f.h_ALLSKY_SFC_SW_DWN.values if "h_ALLSKY_SFC_SW_DWN" in f else np.nan,
        dni_horario=f.h_ALLSKY_SFC_SW_DNI.values if "h_ALLSKY_SFC_SW_DNI" in f else np.nan,
        temp_ar_horaria=f.h_T2M.values if "h_T2M" in f else np.nan,
        vento_horario=f.h_WS2M.values if "h_WS2M" in f else np.nan,
        kt_diario=f.d_Kt.values,
        ghi_diario=f.d_H.values if "d_H" in f else f.d_ALLSKY_SFC_SW_DWN.values,
        temp_ar_diaria=f.d_T2M.values,
        umidade_diaria=f.d_RH2M.values,
        vento_diario=f.d_WS2M.values,
        chuva_diaria=f.d_PRECTOTCORR.values,
        nuvens_diaria=f.d_CLOUD_AMT.values,
        aerossol_diario=f.d_AOD_55.values,
        potencia_ca_W=f.p_ac.values,
    ))
    out["poa_estimada"] = out.poa_ceu_claro * out.kc_horario
    out["pot_nominal_kWp"] = cap_kwp
    out["pot_inversor_kW"] = kw_ac
    # indice de desempenho e estado de sujeira (media movel de 30 dias, defasada)
    pi = np.where(out.poa_ceu_claro > 50, out.potencia_ca_W/(cap_kwp*1000*out.poa_ceu_claro/1000), np.nan)
    out["indice_desempenho"] = pi
    s = pd.Series(pi, index=pd.to_datetime(out.data_hora)).resample("D").median()
    s = s.rolling(30, min_periods=10).median().shift(1)
    out["estado_sujeira"] = pd.to_datetime(out.data_hora).dt.normalize().map(s).values
    if extra: out = out.join(extra)
    return out

A = prep(caminho("frame5h.parquet"), caminho("meta.json"), "Cascavel", 3.96, 4.0)
print("Cascavel:", A.shape)

R = pd.read_parquet(caminho("curitiba_frame5.parquet")); R["ts"] = pd.to_datetime(R.timestamp)
MR = json.load(open(caminho("curitiba_meta.json")))
R = R[(R.cosz > 0) & R.p_ac.notna() & (R.p_ac >= 0) & (R.p_ac <= 12000)]
B = pd.DataFrame(dict(
    site="Curitiba", data_hora=R.ts.values, ano=R.ts.dt.year.values, mes=R.ts.dt.month.values,
    dia_do_ano=R.doy.values, hora_solar=R.solar_time.values, elevacao_solar=R.elev.values,
    cos_zenite=R.cosz.values, poa_ceu_claro=R.poa_cs.values, kc_horario=R.h_kc.values,
    ghi_horario=R.h_ALLSKY_SFC_SW_DWN.values, dni_horario=R.h_ALLSKY_SFC_SW_DNI.values,
    temp_ar_horaria=R.h_T2M.values, vento_horario=R.h_WS2M.values,
    kt_diario=R.d_Kt.values, ghi_diario=R.d_ALLSKY_SFC_SW_DWN.values,
    temp_ar_diaria=R.d_T2M.values, umidade_diaria=R.d_RH2M.values, vento_diario=R.d_WS2M.values,
    chuva_diaria=R.d_PRECTOTCORR.values, nuvens_diaria=R.d_CLOUD_AMT.values,
    aerossol_diario=R.d_AOD_55.values, potencia_ca_W=R.p_ac.values,
    ))
B["poa_estimada"] = B.poa_ceu_claro*B.kc_horario
B["pot_nominal_kWp"] = MR["cap_total_kwp"]; B["pot_inversor_kW"] = 12.0
pi = np.where(B.poa_ceu_claro > 50, B.potencia_ca_W/(MR["cap_total_kwp"]*1000*B.poa_ceu_claro/1000), np.nan)
B["indice_desempenho"] = pi
s = pd.Series(pi, index=pd.to_datetime(B.data_hora)).resample("D").median().rolling(30, min_periods=10).median().shift(1)
B["estado_sujeira"] = pd.to_datetime(B.data_hora).dt.normalize().map(s).values
print("Curitiba:", B.shape)

base = pd.concat([A, B], ignore_index=True).sort_values(["site","data_hora"]).reset_index(drop=True)
ORD = ["site","data_hora","ano","mes","dia_do_ano","hora_solar","elevacao_solar","cos_zenite",
       "poa_ceu_claro","kc_horario","poa_estimada","ghi_horario","dni_horario",
       "temp_ar_horaria","vento_horario","kt_diario","ghi_diario","temp_ar_diaria","umidade_diaria",
       "vento_diario","chuva_diaria","nuvens_diaria","aerossol_diario","estado_sujeira",
       "pot_nominal_kWp","pot_inversor_kW","indice_desempenho","potencia_ca_W"]
base = base[ORD]
base.to_parquet(AMBAS / "base_modelagem_5min.parquet", index=False, compression="zstd")
print("\nbase_modelagem_5min.parquet", base.shape)

# versao horaria, leve o bastante para abrir no Excel
h = base.copy()
h["hora"] = pd.to_datetime(h.data_hora).dt.floor("h")
num = [c for c in ORD if c not in ("site","data_hora")]
hh = h.groupby(["site","hora"])[num].mean().reset_index().rename(columns={"hora":"data_hora"})
hh["n_intervalos"] = h.groupby(["site","hora"]).size().values
hh.to_csv(AMBAS / "base_modelagem_horaria.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
hh.to_parquet(AMBAS / "base_modelagem_horaria.parquet", index=False, compression="zstd")
print("base_modelagem_horaria.csv", hh.shape)

import os
for f_ in ["base_modelagem_5min.parquet","base_modelagem_horaria.csv","base_modelagem_horaria.parquet"]:
    print("  %-38s %.1f MB" % (f_, os.path.getsize(AMBAS / f_)/1e6))
print("\nregistros por site:"); print(base.groupby("site").size().to_string())
print("\nfaltantes por coluna (%):")
print((100*base.isna().mean()).round(2).to_string())
