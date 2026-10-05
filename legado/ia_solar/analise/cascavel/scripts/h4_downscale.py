# -*- coding: utf-8 -*-
"""Hourly irradiance helps at hourly resolution but hurt at 5-minute resolution,
because a step function flattens the intra-hour shape. The fix is not to feed the
model hourly W/m2, but to use the hourly CLEARNESS and keep the 5-minute geometry:

    POA(5 min) = clear-sky POA(exact geometry, 5 min)  x  kc(hourly)
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

f = pd.read_parquet(caminho("frame5h.parquet"))
f["ts"] = pd.to_datetime(f.timestamp); f["night"] = f.cosz <= 0
f["h_kc"]  = (f.h_ALLSKY_SFC_SW_DWN  / f.h_CLRSKY_SFC_SW_DWN.replace(0, np.nan)).clip(0, 1.3)
f["hi_kc"] = (f.hi_ALLSKY_SFC_SW_DWN / f.hi_CLRSKY_SFC_SW_DWN.replace(0, np.nan)).clip(0, 1.3)
# the downscaled products: hourly attenuation on 5-minute geometry
f["poa_dsc"]  = f.poa_cs * f.h_kc
f["poa_dsci"] = f.poa_cs * f.hi_kc
f["dni_dsc"]  = f.poa_cs * (f.h_ALLSKY_SFC_SW_DNI /
                            (f.h_ALLSKY_SFC_SW_DWN + f.h_ALLSKY_SFC_SW_DIFF).replace(0, np.nan))

GEO = ["elev","cosz","cos_inc","sol_az","solar_time","doy","poa_cs"]
DAY = ["d_Kt","d_H","d_poa","d_T2M","d_RH2M","d_WS2M","d_CLOUD_AMT","d_PRECTOTCORR","d_AOD_55"]
HRW = ["h_T2M","h_RH2M","h_WS2M","h_CLOUD_AMT","h_AOD_55"]
T = "p_ac"
def clean(df):
    d = df[~df.night].copy(); d = d[d.p_ac.notna()]; d = d[d.p_ac <= 4000]
    return d[~((d.poa_cs > 300) & (d.d_Kt >= .6) & (d.p_ac == 0))]
S = pd.Timestamp("2025-08-01")
tr, te = clean(f[f.ts < S]), clean(f[f.ts >= S])
print("train %d  test %d" % (len(tr), len(te)))

def run(lab, feats):
    a = tr.dropna(subset=feats+[T]); b = te.dropna(subset=feats+[T])
    m = HistGradientBoostingRegressor(max_iter=250, learning_rate=.08,
                                      min_samples_leaf=40, random_state=0).fit(a[feats], a[T])
    p = np.clip(m.predict(b[feats]), 0, None); y = b[T].values
    dd = b.assign(pred=p).groupby(b.ts.dt.date).agg(
        x=(T, lambda s: s.sum()*5/60/1000), z=("pred", lambda s: s.sum()*5/60/1000))
    r = dict(model=lab, n=len(b), R2=r2_score(y,p), MAE=mean_absolute_error(y,p),
             daily_R2=r2_score(dd.x,dd.z), daily_MAE=mean_absolute_error(dd.x,dd.z))
    print("  %-40s R2 %.4f  MAE %6.1f W   daily R2 %.4f  MAE %.2f kWh"
          % (lab, r["R2"], r["MAE"], r["daily_R2"], r["daily_MAE"]), flush=True)
    return r

print("\n=== 5-minute task, same held-out year ===")
rows = []
rows.append(run("daily weather (previous best)",      GEO+DAY))
rows.append(run("hourly W/m2 as a step function",     GEO+["h_ALLSKY_SFC_SW_DWN","h_ALLSKY_SFC_SW_DNI","h_kc"]+HRW))
rows.append(run("downscaled: poa_cs x hourly kc",     GEO+["poa_dsc","h_kc"]+HRW))
rows.append(run("downscaled + daily weather",         GEO+["poa_dsc","h_kc"]+HRW+DAY))
rows.append(run("downscaled (interpolated kc)",       GEO+["poa_dsci","hi_kc"]+HRW))
rows.append(run("downscaled + interpolated + daily",  GEO+["poa_dsc","poa_dsci","h_kc","hi_kc"]+HRW+DAY))

R = pd.DataFrame(rows)
base = R.iloc[0]; best = R.loc[R.R2.idxmax()]
print("\n  baseline (daily)  : R2 %.4f  MAE %.0f W  | daily R2 %.4f  MAE %.2f kWh"
      % (base.R2, base.MAE, base.daily_R2, base.daily_MAE))
print("  best with hourly  : R2 %.4f  MAE %.0f W  | daily R2 %.4f  MAE %.2f kWh"
      % (best.R2, best.MAE, best.daily_R2, best.daily_MAE))
print("  gain              : %+.1f pp R2, %.0f W less error (%.0f %%)"
      % (100*(best.R2-base.R2), base.MAE-best.MAE, 100*(1-best.MAE/base.MAE)))
print("  best model        : %s" % best.model)

# where the gain lands
print("\n=== error by sky condition ===")
def pr(feats):
    a = tr.dropna(subset=feats+[T]); b = te.dropna(subset=feats+[T])
    m = HistGradientBoostingRegressor(max_iter=250, learning_rate=.08,
                                      min_samples_leaf=40, random_state=0).fit(a[feats], a[T])
    return b.index, np.abs(np.clip(m.predict(b[feats]),0,None) - b[T].values)
i1, e1 = pr(GEO+DAY)
fb = GEO+["poa_dsc","h_kc"]+HRW+DAY
i2, e2 = pr(fb)
cmp = pd.DataFrame({"daily": pd.Series(e1, index=i1), "hourly": pd.Series(e2, index=i2)}).dropna()
cmp["Kt"] = te.loc[cmp.index, "d_Kt"]; cmp["P"] = te.loc[cmp.index, T]
b2 = cmp.groupby(pd.cut(cmp.Kt,[0,.3,.45,.6,.7,.8]), observed=True).agg(
    n=("daily","size"), meanP=("P","mean"), MAE_daily=("daily","mean"), MAE_hourly=("hourly","mean"))
b2["cut_%"] = 100*(1-b2.MAE_hourly/b2.MAE_daily)
print(b2.round(1).to_string())
R.to_csv(caminho("ml_downscale_results.csv"), index=False)
json.dump(dict(base_R2=float(base.R2), base_MAE=float(base.MAE),
               best_R2=float(best.R2), best_MAE=float(best.MAE),
               best_model=str(best.model)), open(caminho("ml_downscale.json"),"w"), indent=1)
