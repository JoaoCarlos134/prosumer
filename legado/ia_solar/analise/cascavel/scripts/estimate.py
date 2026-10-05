import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json
from scipy import stats

df = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
meta = json.load(open(caminho("meta.json")))
KWP = meta["kwp"]
res = {}

# quality filter: drop very low irradiance days where PR is numerically unstable
q = df[(df.poa >= 1.0) & (df.pr.between(0.05, 1.3))].copy()
clear = q[q.Kt >= 0.60].copy()          # clear-ish days
print(f"all={len(df)}  quality={len(q)}  clear={len(clear)}")
res["n_all"], res["n_quality"], res["n_clear"] = len(df), len(q), len(clear)

def ols(y, X, names):
    X = np.column_stack([np.ones(len(y))] + list(X))
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    s2 = resid @ resid / dof
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    r2 = 1 - resid.var() / y.var()
    return dict(names=["const"] + names, beta=beta, se=se, t=beta / se,
                r2=r2, dof=dof, resid=resid)

# ---------- 1. empirical temperature coefficient ----------
# PR = a + b*(Tcell-25) on clear days  ->  gamma_pv = b/a
o = ols(clear.pr.values, [clear.tcell.values - 25], ["Tcell-25"])
g_emp = o["beta"][1] / o["beta"][0]
g_se = abs(g_emp) * np.sqrt((o["se"][1]/o["beta"][1])**2 + (o["se"][0]/o["beta"][0])**2)
res["temp_coeff_pct_per_K"] = [100*g_emp, 100*g_se]
print(f"\n1) empirical power temp coefficient = {100*g_emp:+.3f} %/K  (+/- {100*g_se:.3f}), R2={o['r2']:.3f}")

# multivariate on clear days: isolate temperature from airmass/spectrum
mv = ols(clear.pr.values,
         [clear.tcell.values-25, clear.airmass.values, clear.kd.values, clear.t_years.values],
         ["Tcell-25","airmass","kd","t_years"])
print("   multivariate (clear days):")
for nm, b, s, t in zip(mv["names"], mv["beta"], mv["se"], mv["t"]):
    print(f"     {nm:10s} {b:+.5f}  se {s:.5f}  t {t:+6.1f}")
print(f"     R2={mv['r2']:.3f}")
res["mv_clear"] = {n: [float(b), float(s)] for n, b, s in zip(mv["names"], mv["beta"], mv["se"])}

# ---------- 2. degradation ----------
mon = q.resample("MS").agg(pr=("pr","mean"), pr_t=("pr_tcorr","mean"),
                           n=("pr","size"), t=("t_years","mean"))
mon = mon[mon.n >= 20]
def trend(y, t, label):
    sl, ic, r, p, se = stats.linregress(t, y)
    rate = 100 * sl / ic                  # %/year relative to fitted start
    rate_se = 100 * se / ic
    print(f"   {label:22s} {rate:+.3f} %/yr  (se {rate_se:.3f}, p={p:.2g})  n={len(y)}")
    return rate, rate_se, p
print("\n2) degradation (monthly means, OLS):")
res["degr_pr"]   = trend(mon.pr.values,   mon.t.values, "raw PR")
res["degr_prt"]  = trend(mon.pr_t.values, mon.t.values, "temp-corrected PR")

# YoY method (same-month comparison removes seasonality)
piv = q.groupby([q.index.year, q.index.month]).pr_tcorr.mean().unstack()
yoy = (piv / piv.shift(1) - 1) * 100
print("   YoY same-month median: %+.2f %%/yr" % np.nanmedian(yoy.values))
res["degr_yoy_median"] = float(np.nanmedian(yoy.values))

# ---------- 3. PVUSA-style capacity regression ----------
# E = poa*(a + b*poa + c*Tamb + d*wind)
hi = q[q.poa >= 3.0]
pv = ols((hi.e_kwh / hi.poa).values,
         [hi.poa.values, hi.T2M.values, hi.WS2M.values],
         ["poa","Tamb","wind"])
print("\n3) PVUSA-style regression (E/POA ~ POA + Tamb + wind):")
for nm, b, s, t in zip(pv["names"], pv["beta"], pv["se"], pv["t"]):
    print(f"     {nm:6s} {b:+.5f}  se {s:.5f}  t {t:+6.1f}")
# rated power at PTC-ish conditions
ptc = pv["beta"][0] + pv["beta"][1]*6.0 + pv["beta"][2]*20.0 + pv["beta"][3]*1.0
print(f"     implied PTC capacity factor vs nameplate: {ptc/KWP:.3f}")
res["pvusa_ptc_ratio"] = float(ptc / KWP)

# ---------- 4. soiling ----------
sl, ic, r, p, se = stats.linregress(clear.dry_days.values, clear.pr_tcorr.values)
print(f"\n4) soiling: PR_corr vs consecutive dry days = {100*sl/ic:+.4f} %/day (p={p:.2g}, r={r:+.3f})")
res["soiling_pct_per_dry_day"] = [float(100*sl/ic), float(100*se/ic), float(p)]
bins = pd.cut(clear.dry_days, [-1,0,2,5,10,20,1000],
              labels=["rain today","1-2 d","3-5 d","6-10 d","11-20 d",">20 d"])
print(clear.groupby(bins, observed=True).pr_tcorr.agg(["mean","count"]).round(4).to_string())

# ---------- 5. driver correlations with efficiency ----------
drivers = ["poa","H","Kt","Kc","kd","T2M","T2M_MAX","T2M_MIN","dT","tcell","RH2M","dewdep",
           "WS2M","WS10M","PRECTOTCORR","dry_days","rain_7d","rain_30d","CLOUD_AMT",
           "AOD_55","ALLSKY_SRF_ALB","airmass","cos_inc","daylength","uv_ratio","PS","TS","t_years"]
rows = []
for d in drivers:
    for tgt in ["pr","pr_tcorr"]:
        s = q[[d,tgt]].dropna()
        if len(s) < 100: continue
        pr_, pp = stats.pearsonr(s[d], s[tgt]); sr_, sp = stats.spearmanr(s[d], s[tgt])
        rows.append(dict(driver=d, target=tgt, n=len(s), pearson=pr_, p_pearson=pp, spearman=sr_))
corr = pd.DataFrame(rows)
corr.to_csv(caminho("driver_correlations.csv"), index=False)
print("\n5) strongest drivers of temp-corrected PR:")
cc = corr[corr.target=="pr_tcorr"].reindex(corr[corr.target=="pr_tcorr"].pearson.abs().sort_values(ascending=False).index)
print(cc.head(15)[["driver","n","pearson","spearman","p_pearson"]].round(4).to_string(index=False))

# ---------- 6. annual energy balance / yields ----------
yr = df.groupby("year").agg(days=("e_kwh","size"), E=("e_kwh","sum"), poa=("poa","sum"),
                            H=("H","sum"), pr=("pr","mean"), t=("T2M","mean"))
yr["yield_kwh_kwp"] = yr.E / KWP
yr["full_years"] = yr.days/365.25
print("\n6) annual summary:")
print(yr.round(3).to_string())
full = yr[yr.days >= 360]
print(f"   mean specific yield (complete years): {full.yield_kwh_kwp.mean():.0f} kWh/kWp/yr")
res["specific_yield"] = float(full.yield_kwh_kwp.mean())

# ---------- 7. losses budget ----------
poa_y = df.poa.sum()/df.shape[0]*365
e_y   = df.e_kwh.sum()/df.shape[0]*365
print(f"\n7) reference yield {poa_y:.0f} kWh/m2/yr -> ideal {poa_y*KWP:.0f} kWh, actual {e_y:.0f} kWh")
therm = np.average(meta["gamma_pv"]*(q.tcell-25), weights=q.poa)
print(f"   modelled thermal loss {100*therm:+.1f} %, residual (soiling+mismatch+inverter+wiring+spectral) {100*(np.nanmean(q.pr)-1-therm):+.1f} %")
res["thermal_loss_pct"] = float(100*therm)
res["residual_loss_pct"] = float(100*(np.nanmean(q.pr)-1-therm))

json.dump(res, open(caminho("estimates.json"),"w"), indent=1, default=float)
print("\nwrote estimates.json, driver_correlations.csv")
