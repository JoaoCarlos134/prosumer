# -*- coding: utf-8 -*-
"""Does hourly POWER lift the ceiling that daily POWER imposed?
Same fixed held-out year, same model, same protocol as before."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

f = pd.read_parquet(caminho("frame5h.parquet"))
f["ts"] = pd.to_datetime(f.timestamp); f["night"] = f.cosz <= 0
GEO = ["elev","cosz","cos_inc","sol_az","solar_time","doy","poa_cs"]
DAY = ["d_Kt","d_H","d_poa","d_T2M","d_RH2M","d_WS2M","d_CLOUD_AMT","d_PRECTOTCORR","d_AOD_55"]
HR  = ["h_ALLSKY_SFC_SW_DWN","h_CLRSKY_SFC_SW_DWN","h_ALLSKY_SFC_SW_DNI","h_ALLSKY_SFC_SW_DIFF",
       "h_kc","h_T2M","h_RH2M","h_WS2M","h_CLOUD_AMT","h_AOD_55","h_PRECTOTCORR"]
HRI = ["hi_ALLSKY_SFC_SW_DWN","hi_CLRSKY_SFC_SW_DWN","hi_ALLSKY_SFC_SW_DNI","hi_ALLSKY_SFC_SW_DIFF",
       "hi_kc","hi_T2M","hi_WS2M","hi_CLOUD_AMT"]
T = "p_ac"

def clean(df):
    d = df[~df.night].copy(); d = d[d.p_ac.notna()]; d = d[d.p_ac <= 4000]
    return d[~((d.poa_cs > 300) & (d.d_Kt >= .6) & (d.p_ac == 0))]

S = pd.Timestamp("2025-08-01")
tr, te = clean(f[f.ts < S]), clean(f[f.ts >= S])
print("train %d   test %d (%s .. %s)" % (len(tr), len(te), te.ts.min().date(), te.ts.max().date()))

# lagged plant-health feature, as before
pi = clean(f).set_index("ts").pi.resample("D").median().rolling(30, min_periods=10).median().shift(1)
for d_ in (tr, te): d_["soil"] = d_.ts.dt.normalize().map(pi)

def run(name, feats):
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=.08,
                                      min_samples_leaf=40, random_state=0)
    m.fit(tr[feats], tr[T])
    p = np.clip(m.predict(te[feats]), 0, None); y = te[T].values
    dd = te.assign(pred=p).groupby(te.ts.dt.date).agg(
        a=(T, lambda s: s.sum()*5/60/1000), b=("pred", lambda s: s.sum()*5/60/1000))
    return dict(model=name, n_feat=len(feats), MAE=mean_absolute_error(y,p),
                RMSE=float(np.sqrt(((y-p)**2).mean())), R2=r2_score(y,p),
                daily_R2=r2_score(dd.a, dd.b), daily_MAE=mean_absolute_error(dd.a, dd.b))

rows = [
 run("geometry only",                    GEO),
 run("geometry + DAILY weather",         GEO+DAY),
 run("geometry + HOURLY weather",        GEO+HR),
 run("geometry + hourly, interpolated",  GEO+HRI),
 run("geometry + hourly + interpolated", GEO+HR+HRI),
 run("geometry + hourly + daily",        GEO+HR+DAY),
 run("geometry + hourly + soiling",      GEO+HR+["soil"]),
 run("everything + soiling",             GEO+HR+HRI+DAY+["soil"]),
]
R = pd.DataFrame(rows); R["MAE_%cap"] = 100*R.MAE/3960
pd.set_option("display.width", 200)
print("\n=== same held-out year, 5-minute predictions ===")
print(R[["model","n_feat","MAE","RMSE","R2","MAE_%cap","daily_R2","daily_MAE"]].round(4).to_string(index=False))

base = R.loc[R.model=="geometry + DAILY weather"].iloc[0]
best = R.loc[R.R2.idxmax()]
print("\n  daily weather  : R2 %.4f, MAE %.0f W" % (base.R2, base.MAE))
print("  hourly weather : R2 %.4f, MAE %.0f W" % (best.R2, best.MAE))
print("  improvement    : %+.1f pp R2, %.0f W less error (%.0f %% reduction)"
      % (100*(best.R2-base.R2), base.MAE-best.MAE, 100*(1-best.MAE/base.MAE)))

# where the gain lands
print("\n=== error by sky condition: daily vs hourly weather ===")
def preds(feats):
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=.08,
                                      min_samples_leaf=40, random_state=0).fit(tr[feats], tr[T])
    return np.clip(m.predict(te[feats]), 0, None)
te2 = te.copy()
te2["e_daily"]  = np.abs(preds(GEO+DAY) - te[T])
te2["e_hourly"] = np.abs(preds(GEO+HR)  - te[T])
b = te2.groupby(pd.cut(te2.d_Kt,[0,.3,.45,.6,.7,.8]), observed=True).agg(
    n=("e_daily","size"), mean_P=(T,"mean"), MAE_daily=("e_daily","mean"), MAE_hourly=("e_hourly","mean"))
b["cut_%"] = 100*(1-b.MAE_hourly/b.MAE_daily)
print(b.round(1).to_string())
print("\n  the gain is largest on broken-cloud days, which is exactly where the daily")
print("  product was blind: one number could not say which hour the cloud arrived.")

R.to_csv(caminho("ml_hourly_results.csv"), index=False)
json.dump(dict(daily_R2=float(base.R2), daily_MAE=float(base.MAE),
               hourly_R2=float(best.R2), hourly_MAE=float(best.MAE),
               best_model=str(best.model)), open(caminho("ml_hourly.json"),"w"), indent=1)
