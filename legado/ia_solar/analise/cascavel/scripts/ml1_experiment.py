# -*- coding: utf-8 -*-
"""Does cleaning actually help a production model? Controlled test.

Design: ONE fixed test set (the last 12 months, daylight, cleaned) scored by every
variant, so the numbers are comparable. Only the training data and feature set change.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, time
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, GroupKFold

f = pd.read_parquet(caminho("frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
f["night"] = f.cosz <= 0
f["day"] = f.ts.dt.normalize()

GEO = ["elev","cosz","cos_inc","sol_az","solar_time","doy","poa_cs"]
WX  = ["d_Kt","d_H","d_poa","d_T2M","d_RH2M","d_WS2M","d_CLOUD_AMT","d_PRECTOTCORR","d_AOD_55"]
LEAK= ["e_wh","va","fp","i_ac","v_ac","i_dc","v_dc","p_dc"]
TARGET = "p_ac"

def clean(df):
    d = df[~df.night].copy()
    d = d[d.p_ac.notna()]
    d = d[d.p_ac <= 4000]
    d = d[~((d.poa_cs > 300) & (d.d_Kt >= .6) & (d.p_ac == 0))]
    return d

SPLIT = pd.Timestamp("2025-08-01")
test = clean(f[f.ts >= SPLIT])
print("fixed test set: %d daylight rows, %s to %s"
      % (len(test), test.ts.min().date(), test.ts.max().date()))

def run(name, train_df, feats, note=""):
    tr = train_df.dropna(subset=[TARGET])
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=.08, max_depth=None,
                                      min_samples_leaf=40, random_state=0)
    t0 = time.time()
    m.fit(tr[feats], tr[TARGET])
    p = np.clip(m.predict(test[feats]), 0, None)
    y = test[TARGET].values
    return dict(variant=name, n_train=len(tr), n_feat=len(feats),
                MAE=mean_absolute_error(y, p), RMSE=float(np.sqrt(((y-p)**2).mean())),
                R2=r2_score(y, p), sec=round(time.time()-t0,1), note=note)

trainpool = f[f.ts < SPLIT]
rows = []

# A. everything raw: night rows, outliers, and the concurrent inverter channels
rows.append(run("A  raw rows + raw features (incl. leak)",
                trainpool[trainpool.p_ac.notna()], GEO+WX+LEAK,
                "concurrent inverter channels available"))
# B. raw rows, leak removed
rows.append(run("B  raw rows, leak features removed",
                trainpool[trainpool.p_ac.notna()], GEO+WX,
                "night + outliers still in training"))
# C. cleaned rows, leak removed
rows.append(run("C  cleaned rows, leak removed",
                clean(trainpool), GEO+WX, "night + outliers dropped"))
# D. cleaned + geometry only (no weather at all)
rows.append(run("D  cleaned, geometry only", clean(trainpool), GEO, "no weather"))
# E. cleaned + weather only
rows.append(run("E  cleaned, weather only", clean(trainpool), WX, "no geometry"))
# F. cleaned + a soiling-state feature
tr = clean(trainpool).copy(); te = test.copy()
soil = clean(f).set_index("ts").p_ac.resample("MS").median()
# use each month's own lagged soiling level: median of the previous 30 days' PI
pi = clean(f).set_index("ts").pi.resample("D").median().rolling(30, min_periods=10).median().shift(1)
tr["soil"] = tr.ts.dt.normalize().map(pi); te["soil"] = te.ts.dt.normalize().map(pi)
test_bak = test
test = te
rows.append(run("F  cleaned + 30-day soiling state", tr, GEO+WX+["soil"],
                "lagged plant-health feature"))
test = test_bak

R = pd.DataFrame(rows)
R["MAE_%cap"] = 100*R.MAE/3960.0
pd.set_option("display.width", 220)
print("\n=== all scored on the SAME held-out 12 months of daylight data ===")
print(R[["variant","n_train","n_feat","MAE","RMSE","R2","MAE_%cap","note"]].round(4).to_string(index=False))

# ---------------- the evaluation-protocol illusion ----------------
print("\n=== same model, same data, three validation schemes ===")
cl = clean(trainpool)
X, y, g = cl[GEO+WX], cl[TARGET], cl.day
def cv(splitter, groups=None, lab=""):
    sc = []
    for tr_i, te_i in splitter.split(X, y, groups):
        m = HistGradientBoostingRegressor(max_iter=200, learning_rate=.08,
                                          min_samples_leaf=40, random_state=0)
        m.fit(X.iloc[tr_i], y.iloc[tr_i])
        sc.append(r2_score(y.iloc[te_i], np.clip(m.predict(X.iloc[te_i]),0,None)))
    return np.mean(sc), np.std(sc)
a = cv(KFold(5, shuffle=True, random_state=0), None, "random")
b = cv(GroupKFold(5), g, "grouped by day")
print("  random 5-fold           R2 = %.4f  (+/- %.4f)" % a)
print("  5-fold grouped by day   R2 = %.4f  (+/- %.4f)" % b)
holdout = R.loc[R.variant.str.startswith("C"), "R2"].iloc[0]
print("  future 12-month holdout R2 = %.4f" % holdout)
print("\n  the gap between random k-fold and a future holdout is the honest cost of")
print("  autocorrelation plus drift: %.4f -> %.4f" % (a[0], holdout))

# ---------------- leakage, made explicit ----------------
print("\n=== what the 'raw' model is actually doing ===")
cl_tr = clean(trainpool)
m = HistGradientBoostingRegressor(max_iter=200, learning_rate=.08, min_samples_leaf=40, random_state=0)
m.fit(cl_tr[GEO+WX+LEAK], cl_tr[TARGET])
from sklearn.inspection import permutation_importance
sub = test.sample(min(6000, len(test)), random_state=0)
pi_ = permutation_importance(m, sub[GEO+WX+LEAK], sub[TARGET], n_repeats=3,
                             random_state=0, scoring="r2")
imp = pd.Series(pi_.importances_mean, index=GEO+WX+LEAK).sort_values(ascending=False)
print(imp.head(8).round(4).to_string())
print("\n  the top features are the inverter's own concurrent readings. A model that")
print("  needs those to predict production is not predicting anything -- the plant has")
print("  already told it the answer.")

R.to_csv(caminho("ml_results.csv"), index=False)
json.dump(dict(random_kfold_r2=a[0], grouped_kfold_r2=b[0], future_holdout_r2=float(holdout)),
          open(caminho("ml_cv.json"),"w"), indent=1)
