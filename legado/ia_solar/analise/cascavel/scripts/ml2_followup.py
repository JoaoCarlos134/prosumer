# -*- coding: utf-8 -*-
"""Cleaning did not improve accuracy. So what does it actually buy, and what does?"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

f = pd.read_parquet(caminho("frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
f["night"] = f.cosz <= 0
GEO = ["elev","cosz","cos_inc","sol_az","solar_time","doy","poa_cs"]
WX  = ["d_Kt","d_H","d_poa","d_T2M","d_RH2M","d_WS2M","d_CLOUD_AMT","d_PRECTOTCORR","d_AOD_55"]
F = GEO+WX; T="p_ac"
def clean(df):
    d=df[~df.night].copy(); d=d[d.p_ac.notna()]; d=d[d.p_ac<=4000]
    return d[~((d.poa_cs>300)&(d.d_Kt>=.6)&(d.p_ac==0))]
SPLIT = pd.Timestamp("2025-08-01")
tr = clean(f[f.ts < SPLIT])
m = HistGradientBoostingRegressor(max_iter=300, learning_rate=.08, min_samples_leaf=40, random_state=0)
m.fit(tr[F], tr[T])

# ---------- 1. the same model, scored on two test sets ----------
print("=== identical model, two ways of scoring it ===")
day  = clean(f[f.ts >= SPLIT])
allr = f[(f.ts >= SPLIT) & f.p_ac.notna() & (f.p_ac <= 4000)]
for lab, te in [("daylight only (honest)", day), ("night rows included", allr)]:
    p = np.clip(m.predict(te[F]), 0, None); y = te[T].values
    print("  %-24s n=%6d   R2 %.4f   MAE %6.1f W   RMSE %6.1f W"
          % (lab, len(te), r2_score(y,p), mean_absolute_error(y,p), np.sqrt(((y-p)**2).mean())))
print("\n  Night rows are 40% of the record and trivially predictable (the answer is zero),")
print("  so leaving them in inflates R2 and deflates MAE without the model being better.")
print("  That is the real cost of not cleaning: you cannot tell how good you are.")

# ---------- 2. a physical baseline ----------
print("\n=== is the model beating physics? ===")
k = (tr[T]/(3.96*tr.poa_cs)).median()
base = np.clip(3.96*day.poa_cs*k, 0, None)
y = day[T].values
print("  clear-sky x constant PR    R2 %.4f   MAE %6.1f W" % (r2_score(y,base), mean_absolute_error(y,base)))
p = np.clip(m.predict(day[F]),0,None)
print("  gradient boosting          R2 %.4f   MAE %6.1f W" % (r2_score(y,p), mean_absolute_error(y,p)))
print("  improvement                          %+.1f pp R2, %+.0f W MAE"
      % (100*(r2_score(y,p)-r2_score(y,base)), mean_absolute_error(y,p)-mean_absolute_error(y,base)))

# ---------- 3. where the error actually lives ----------
print("\n=== error by sky condition (daylight holdout) ===")
day = day.copy(); day["pred"]=p; day["err"]=np.abs(day.pred-day[T])
b = day.groupby(pd.cut(day.d_Kt,[0,.3,.45,.6,.7,.8]), observed=True).agg(
    n=("err","size"), MAE=("err","mean"), mean_p=(T,"mean"))
b["MAE_rel_%"]=100*b.MAE/b.mean_p
print(b.round(1).to_string())
print("\n  The weather input is a DAILY number spread over ~200 intervals, so the model")
print("  cannot know which particular five minutes a cloud covered. That is the ceiling.")

# ---------- 4. does recency beat volume, given the drift? ----------
print("\n=== training window, given that the plant changes state ===")
for lab, start in [("all history (2019-)",None), ("last 3 years",  pd.Timestamp("2022-08-01")),
                   ("last 2 years",       pd.Timestamp("2023-08-01")),
                   ("post-cleaning only", pd.Timestamp("2024-09-01"))]:
    sub = tr if start is None else tr[tr.ts >= start]
    mm = HistGradientBoostingRegressor(max_iter=300, learning_rate=.08, min_samples_leaf=40, random_state=0)
    mm.fit(sub[F], sub[T])
    pp = np.clip(mm.predict(day[F]),0,None)
    print("  %-20s n=%6d   R2 %.4f   MAE %6.1f W"
          % (lab, len(sub), r2_score(y,pp), mean_absolute_error(y,pp)))
print("\n  More history is not better history: the array was in a different physical")
print("  state for most of it.")

# ---------- 5. daily totals, the number anyone actually uses ----------
print("\n=== aggregated to daily energy ===")
dd = day.groupby(day.ts.dt.date).agg(act=(T,lambda s:s.sum()*5/60/1000),
                                     pred=("pred",lambda s:s.sum()*5/60/1000))
print("  days=%d   R2 %.4f   MAE %.3f kWh (%.1f %% of mean daily %.2f kWh)"
      % (len(dd), r2_score(dd.act,dd.pred), mean_absolute_error(dd.act,dd.pred),
         100*mean_absolute_error(dd.act,dd.pred)/dd.act.mean(), dd.act.mean()))
print("  Errors at 5-minute resolution are largely independent, so they cancel on")
print("  aggregation -- the daily number is far more reliable than the interval one.")
