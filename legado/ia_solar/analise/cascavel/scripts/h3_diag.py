# -*- coding: utf-8 -*-
"""Hourly POWER made the 5-minute model worse. Is that the data, or my join?
Test the alignment properly (aggregate, don't sample) and score hourly data on an
hourly task, which is the resolution it actually lives at."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

H = pd.read_csv(caminho("nasa_power_hourly.csv"), index_col=0, parse_dates=True)
f = pd.read_parquet(caminho("frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
f["night"] = f.cosz <= 0
d = f[f.p_ac.notna() & (f.p_ac <= 4000)].copy()

# ---- 1. alignment by AGGREGATION, scanned at 5-minute resolution ----
print("--- aligning by binning the plant into POWER's hours (not point sampling) ---")
best = None
for off in range(-105, 16, 5):
    key = (d.ts + pd.Timedelta(minutes=off)).dt.floor("h")
    agg = d.groupby(key).p_ac.mean()
    j = pd.concat([agg.rename("plant"), H.ALLSKY_SFC_SW_DWN.rename("ghi")], axis=1).dropna()
    if len(j) < 5000: continue
    r = j.plant.corr(j.ghi)
    if best is None or r > best[0]: best = (r, off, len(j))
    if off % 15 == 0: print("   offset %+4d min   r = %.4f   n=%d" % (off, r, len(j)))
print("\n  best: %+d min, r = %.4f over %d hours" % (best[1], best[0], best[2]))
OFF = best[1]

# ---- 2. does POWER's hourly irradiance actually track the plant, hour by hour? ----
key = (d.ts + pd.Timedelta(minutes=OFF)).dt.floor("h")
hp = d.groupby(key).agg(p=("p_ac","mean"), n=("p_ac","size"), elev=("elev","mean"),
                        poa_cs=("poa_cs","mean"), pi=("pi","median"))
hp = hp[hp.n >= 10]
J = hp.join(H, how="inner").dropna(subset=["ALLSKY_SFC_SW_DWN"])
J = J[J.elev > 5]
print("\n--- hourly agreement, daylight hours only (n=%d) ---" % len(J))
print("  r(POWER hourly GHI , plant hourly mean power) = %.4f" % J.p.corr(J.ALLSKY_SFC_SW_DWN))
print("  r(modelled clear-sky POA, plant)              = %.4f" % J.p.corr(J.poa_cs))
J["poa_h"] = J.ALLSKY_SFC_SW_DWN * (J.poa_cs/J.poa_cs.where(J.poa_cs>0)).fillna(1)
print("  r(POWER hourly DNI , plant)                   = %.4f" % J.p.corr(J.ALLSKY_SFC_SW_DNI))
# implied hourly performance ratio: how noisy is POWER hour to hour?
J["pr_h"] = J.p/(3.96*J.ALLSKY_SFC_SW_DWN.replace(0,np.nan))
print("\n  implied hourly PR from POWER: median %.3f, IQR %.3f-%.3f, CV %.3f"
      % (J.pr_h.median(), J.pr_h.quantile(.25), J.pr_h.quantile(.75), J.pr_h.std()/J.pr_h.mean()))
J["pr_cs"] = J.p/(3.96*J.poa_cs.replace(0,np.nan))
print("  same against the clear-sky model: median %.3f, IQR %.3f-%.3f, CV %.3f"
      % (J.pr_cs.median(), J.pr_cs.quantile(.25), J.pr_cs.quantile(.75), J.pr_cs.std()/J.pr_cs.mean()))

# ---- 3. score hourly data on an HOURLY task ----
print("\n--- modelling at hourly resolution (the native resolution of the data) ---")
dayly = f[~f.night & f.p_ac.notna() & (f.p_ac <= 4000)].copy()
k2 = (dayly.ts + pd.Timedelta(minutes=OFF)).dt.floor("h")
A = dayly.groupby(k2).agg(
    p=("p_ac","mean"), elev=("elev","mean"), cosz=("cosz","mean"), cos_inc=("cos_inc","mean"),
    poa_cs=("poa_cs","mean"), solar_time=("solar_time","mean"), doy=("doy","mean"),
    sol_az=("sol_az","mean"), n=("p_ac","size"),
    d_Kt=("d_Kt","first"), d_H=("d_H","first"), d_poa=("d_poa","first"), d_T2M=("d_T2M","first"),
    d_RH2M=("d_RH2M","first"), d_WS2M=("d_WS2M","first"), d_CLOUD_AMT=("d_CLOUD_AMT","first"),
    d_PRECTOTCORR=("d_PRECTOTCORR","first"), d_AOD_55=("d_AOD_55","first"))
A = A[A.n >= 8].join(H.add_prefix("h_"), how="left")
A["h_kc"] = A.h_ALLSKY_SFC_SW_DWN/A.h_CLRSKY_SFC_SW_DWN.replace(0,np.nan)
A = A[A.elev > 3]
GEO = ["elev","cosz","cos_inc","sol_az","solar_time","doy","poa_cs"]
DAY = ["d_Kt","d_H","d_poa","d_T2M","d_RH2M","d_WS2M","d_CLOUD_AMT","d_PRECTOTCORR","d_AOD_55"]
HR  = ["h_ALLSKY_SFC_SW_DWN","h_CLRSKY_SFC_SW_DWN","h_ALLSKY_SFC_SW_DNI","h_ALLSKY_SFC_SW_DIFF",
       "h_kc","h_T2M","h_RH2M","h_WS2M","h_CLOUD_AMT","h_AOD_55"]
S = pd.Timestamp("2025-08-01")
tr, te = A[A.index < S], A[A.index >= S]
print("  hourly train %d, test %d" % (len(tr), len(te)))
def run(lab, feats):
    sub = tr.dropna(subset=feats+["p"])
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=.08,
                                      min_samples_leaf=20, random_state=0).fit(sub[feats], sub.p)
    t2 = te.dropna(subset=feats+["p"])
    p = np.clip(m.predict(t2[feats]),0,None)
    print("  %-34s n_te=%5d  R2 %.4f  MAE %6.1f W" % (lab, len(t2), r2_score(t2.p,p), mean_absolute_error(t2.p,p)))
    return r2_score(t2.p,p)
r_geo = run("geometry only", GEO)
r_day = run("geometry + daily weather", GEO+DAY)
r_hr  = run("geometry + hourly weather", GEO+HR)
r_all = run("geometry + hourly + daily", GEO+HR+DAY)
print("\n  hourly weather vs daily weather, on the hourly task: %+.1f pp R2"
      % (100*(r_hr-r_day)))
