import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json
from scipy import stats

df = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
KWP = 4.0
q = df[(df.poa >= 1.0) & (df.pr.between(0.05, 1.3))]
m = q.resample("MS").agg(pr=("pr_tcorr","mean"), n=("pr","size"),
                         E=("e_kwh","sum"), poa=("poa","sum"))
m = m[m.n >= 20]
y = m.pr.values; T = len(y)

# ---- exact DP changepoint detection, piecewise-constant mean ----
def seg_cost(a, b):                     # SSE of y[a:b]
    s = y[a:b]
    return float(((s - s.mean())**2).sum()) if b > a else 0.0
C = np.full((T+1, T+1), np.inf)
for a in range(T):
    for b in range(a+1, T+1):
        C[a, b] = seg_cost(a, b)

MINSEG = 4
def dp(k):
    F = np.full((k+1, T+1), np.inf); bk = np.zeros((k+1, T+1), int)
    F[0, 0] = 0.0
    for j in range(1, k+1):
        for t in range(j*MINSEG, T+1):
            for s in range((j-1)*MINSEG, t-MINSEG+1):
                v = F[j-1, s] + C[s, t]
                if v < F[j, t]: F[j, t] = v; bk[j, t] = s
    cps, t = [], T
    for j in range(k, 0, -1):
        s = bk[j, t]; cps.append(s); t = s
    return F[k, T], sorted([c for c in cps if c > 0])

print("k   SSE      BIC        changepoints")
best = None
for k in range(1, 7):
    sse, cps = dp(k)
    npar = k + (k-1)            # k means + (k-1) breakpoints
    bic = T*np.log(sse/T) + npar*np.log(T)
    print(f"{k}  {sse:.5f}  {bic:8.2f}   {[str(m.index[c].date()) for c in cps]}")
    if best is None or bic < best[0]: best = (bic, k, cps)
_, K, CPS = best
print(f"\nselected k={K}: breaks at {[str(m.index[c].date()) for c in CPS]}")

# ---- segment table ----
edges = [0] + CPS + [T]
segs = []
for i in range(len(edges)-1):
    a, b = edges[i], edges[i+1]
    sl = m.iloc[a:b]
    t = (sl.index - sl.index[0]).days/365.25
    tr = stats.linregress(t, sl.pr.values) if b-a >= 6 else None
    segs.append(dict(start=str(sl.index[0].date()), end=str(sl.index[-1].date()),
                     months=b-a, pr=sl.pr.mean(), pr_sd=sl.pr.std(),
                     trend_pct_yr=(100*tr.slope/sl.pr.mean() if tr else np.nan),
                     trend_p=(tr.pvalue if tr else np.nan),
                     E=sl.E.sum(), poa=sl.poa.sum()))
S = pd.DataFrame(segs)
print("\nsegments:")
print(S.round(4).to_string(index=False))

# ---- lost energy vs the healthy baseline ----
base = max(S.pr[:2].max(), S.pr.iloc[-1])       # best of early plateau / current state
print(f"\nhealthy baseline PR = {base:.3f}")
S["pr_gap"]   = base - S.pr
S["E_ideal"]  = S.poa * KWP * base / S.pr * 0 + S.poa * KWP * base   # PR*poa*kwp
S["E_lost"]   = S.E_ideal - S.E
S["lost_pct"] = 100 * S.E_lost / S.E_ideal
print(S[["start","end","months","pr","pr_gap","E","E_ideal","E_lost","lost_pct"]].round(2).to_string(index=False))
print(f"\nTOTAL energy shortfall vs baseline: {S.E_lost.sum():.0f} kWh "
      f"({100*S.E_lost.sum()/S.E_ideal.sum():.1f} % of achievable)")

# ---- degradation inside stable segments only ----
print("\ndegradation within stable segments (>=12 months):")
for _, r in S[S.months >= 12].iterrows():
    print(f"   {r.start} -> {r.end}: {r.trend_pct_yr:+.2f} %/yr (p={r.trend_p:.3g})")

# ---- step sizes ----
print("\nstep changes at breakpoints:")
for i, c in enumerate(CPS):
    before, after = S.pr.iloc[i], S.pr.iloc[i+1]
    print(f"   {m.index[c].date()}: {before:.3f} -> {after:.3f}  ({100*(after/before-1):+.1f} %)")

S.to_csv(caminho("segments.csv"), index=False)
m.to_csv(caminho("monthly_pr.csv"))
json.dump(dict(changepoints=[str(m.index[c].date()) for c in CPS],
               baseline_pr=float(base),
               total_lost_kwh=float(S.E_lost.sum()),
               total_lost_pct=float(100*S.E_lost.sum()/S.E_ideal.sum())),
          open(caminho("changepoints.json"),"w"), indent=1)
print("\nwrote segments.csv, monthly_pr.csv, changepoints.json")
