# -*- coding: utf-8 -*-
"""Data quality, part 2: logging regime changes, outliers, leakage, redundancy."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd

f = pd.read_parquet(caminho("frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
f["night"] = f.cosz <= 0
d = f[~f.night].copy()
N = len(f)

# ---------- logging window changed between files ----------
print("--- records per day, by source year (the logger's window changed) ---")
rpd = f.groupby(f.ts.dt.date).size().rename("n").to_frame()
rpd["yr"] = pd.to_datetime(rpd.index).year
g = rpd.groupby("yr").n.agg(["median","min","max","size"])
print(g.to_string())
print("\n  288 = a full 24 h of 5-minute slots; ~200 = daylight only.")
print("  The export switched from daylight-only to round-the-clock logging, so the")
print("  night rows exist for some years and not others. Any model must key off the")
print("  sun position, never off the row count or the time index.")

# ---------- physical-bound outliers ----------
print("\n--- outliers against physical bounds ---")
rules = [
 ("AC power above the 4.0 kW inverter rating", (f.p_ac > 4000)),
 ("AC power above 110% of rating",             (f.p_ac > 4400)),
 ("DC power above 4.3 kW",                     (f.p_dc > 4300)),
 ("inverter efficiency above 1.0",             (f.eta_inv > 1.0)),
 ("inverter efficiency above 1.02",            (f.eta_inv > 1.02)),
 ("production while the sun is below horizon", (f.night & (f.p_ac > 10))),
 ("DC current > 0 but DC voltage = 0",         ((f.i_dc > 0.1) & (f.v_dc <= 0))),
 ("negative values in any channel",            ((f.p_ac < 0) | (f.i_dc < 0) | (f.v_dc < 0))),
 ("power factor outside [0,1]",                ((f.fp < 0) | (f.fp > 1))),
 ("daylight, clear sky, zero production",      ((~f.night) & (f.poa_cs > 300) & (f.d_Kt >= .6) & (f.p_ac == 0))),
]
for lab, m in rules:
    n = int(m.fillna(False).sum())
    print("  %-44s %6d   %.4f %%" % (lab, n, 100*n/N))

print("\n  the >4 kW records are logging-gap artefacts: energy accumulated across a")
print("  stall is dumped into one interval. Check the neighbouring interval:")
bad = f[(f.p_ac > 4400)].head(3)
for _, r in bad.iterrows():
    w = f[(f.ts >= r.ts - pd.Timedelta(minutes=15)) & (f.ts <= r.ts + pd.Timedelta(minutes=10))]
    print("    %s : %s" % (r.ts, " ".join("%.0f" % x if np.isfinite(x) else "na" for x in w.p_ac)))

# ---------- stuck sensors ----------
print("\n--- frozen readings (identical consecutive values in daylight) ---")
for c in ["v_dc","i_dc","p_ac","v_ac"]:
    s = d[c]
    same = (s.diff() == 0) & s.notna() & (s != 0)
    grp = (same != same.shift()).cumsum()
    runs = same.groupby(grp).sum()
    runs = runs[runs >= 6]                 # 30 minutes or more
    print("  %-5s runs of >=30 min identical: %4d   longest %s intervals"
          % (c, len(runs), int(runs.max()) if len(runs) else 0))

# ---------- leakage: exact algebraic relations among the channels ----------
print("\n--- redundant channels (leakage risk if the target is energy) ---")
x = d.dropna(subset=["p_ac","va","fp","i_ac","v_ac","e_wh"]).copy()
checks = [
 ("rendimento_especifico x 4000 == energia_Wh", None),
 ("potencia_aparente x fator_potencia vs AC power", x.va*x.fp*12, x.p_ac),
 ("i_ac x v_ac vs potencia_aparente",              x.i_ac*x.v_ac, x.va),
 ("i_dc x v_dc vs DC power",                       x.i_dc*x.v_dc, x.p_dc),
]
raw = pd.read_csv(caminho("dados_5min_2019-2026.csv"), usecols=["energia_Wh","rendimento_especifico_kWh_kWp",
                                                        "producao_fotovoltaica_Wh"])
r1 = raw.dropna()
rel = (r1.rendimento_especifico_kWh_kWp*4000 - r1.energia_Wh).abs()
print("  rendimento_especifico x 4000 vs energia_Wh : max |diff| %.4f Wh, r = %.8f"
      % (rel.max(), np.corrcoef(r1.rendimento_especifico_kWh_kWp, r1.energia_Wh)[0,1]))
rel2 = (r1.energia_Wh - r1.producao_fotovoltaica_Wh).abs()
print("  energia_Wh vs producao_fotovoltaica_Wh     : max |diff| %.4f Wh, r = %.8f"
      % (rel2.max(), np.corrcoef(r1.energia_Wh, r1.producao_fotovoltaica_Wh)[0,1]))
for lab, a, b in checks[1:]:
    ok = np.isfinite(a) & np.isfinite(b) & (b != 0)
    print("  %-42s r = %.6f, median ratio %.4f"
          % (lab, np.corrcoef(a[ok], b[ok])[0,1], np.median(a[ok]/b[ok])))
print("\n  -> 3 of the 11 channels are exact restatements of the target. Feeding them")
print("     to a model that predicts energy is guaranteed leakage.")

# ---------- multicollinearity among usable predictors ----------
print("\n--- correlation among candidate predictors (daylight) ---")
cols = ["poa_cs","cos_inc","elev","d_Kt","d_H","d_poa","d_T2M","d_RH2M","d_WS2M","v_dc","d_CLOUD_AMT"]
cm = d[cols].corr().abs()
hi = [(a,b,cm.loc[a,b]) for i,a in enumerate(cols) for b in cols[i+1:] if cm.loc[a,b] > .8]
for a,b,v in sorted(hi, key=lambda t:-t[2]):
    print("  |r| = %.3f   %s  <->  %s" % (v,a,b))
if not hi: print("  none above 0.8")

# ---------- autocorrelation: effective sample size ----------
print("\n--- autocorrelation of the modelling target ---")
s = d.set_index("ts").pi.resample("5min").mean().dropna()
for lag, lab in [(1,"5 min"),(12,"1 h"),(288,"1 day"),(288*7,"1 week")]:
    if lag < len(s): print("  ACF at %-7s : %+.3f" % (lab, s.autocorr(lag)))
half = next((l for l in range(1, 2000) if s.autocorr(l) < 0.5), None)
print("  autocorrelation falls below 0.5 after %s intervals (%.1f hours)"
      % (half, half*5/60 if half else float("nan")))
print("  -> %d daylight rows, but only ~%d independent blocks. Random k-fold will"
      % (len(d), len(d)//max(half,1)))
print("     report a wildly optimistic score; split by day or by month.")

# ---------- class balance / drift ----------
print("\n--- regime balance and drift ---")
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])
b = d.groupby("regime").agg(n=("pi","size"), pi=("pi","median"))
b["share_%"] = 100*b.n/b.n.sum()
b["label"] = [("%s-%s" % (seg.loc[i,"start"].strftime("%b%y"), seg.loc[i,"end"].strftime("%b%y")))
              if i in seg.index else "?" for i in b.index]
print(b.round(3).to_string())
print("\n  median target by year (non-stationary):")
print(d.groupby(d.ts.dt.year).pi.median().round(3).to_string())
