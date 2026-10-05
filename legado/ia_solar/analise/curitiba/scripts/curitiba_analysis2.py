# -*- coding: utf-8 -*-
"""Curitiba / Curitiba. The single-orientation fit is poor (R2 ~0.6 against 0.89 at
Cascavel) while the day curve peaks at solar noon, so the array is near due north
and something else breaks the model. Find it, then do the performance analysis."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json
from scipy import stats

f = pd.read_parquet(caminho("curitiba_frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
M = json.load(open(caminho("curitiba_meta.json")))
C1, C2 = M["cap_mpp1_kwp"]*1000, M["cap_mpp2_kwp"]*1000
clear = f[(f.cosz > .15) & (f.d_Kt >= .62) & f.p_ac.notna() & (f.i1 > .2)].copy()
print("clear-day intervals: %d" % len(clear))

# ---------- 1. morning / afternoon asymmetry ----------
print("\n--- morning vs afternoon at matched sun elevation (clear days) ---")
clear["side"] = np.where(clear.solar_time < 12.25, "AM", "PM")
clear["eb"] = pd.cut(clear.elev, [10,20,30,40,50,60,75])
for k in (1,2):
    p = clear.pivot_table(index="eb", columns="side", values="in%d"%k, aggfunc="median", observed=True)
    p["PM/AM"] = p.PM/p.AM
    print("  MPP%d (current per kW/m2)" % k)
    print(p.round(3).to_string().replace("\n","\n    "))
print("\n  a symmetric, unshaded array gives PM/AM ~ 1.00 at every elevation")

print("\n--- asymmetry by season (a fixed obstruction moves with the sun's path) ---")
seas = {"summer DJF":[12,1,2], "autumn MAM":[3,4,5], "winter JJA":[6,7,8], "spring SON":[9,10,11]}
for lab, mm in seas.items():
    s = clear[clear.month.isin(mm) & clear.elev.between(15,40)]
    if len(s) < 300: continue
    a1 = s[s.side=="PM"].in1.median()/s[s.side=="AM"].in1.median()
    a2 = s[s.side=="PM"].in2.median()/s[s.side=="AM"].in2.median()
    print("   %-11s  MPP1 PM/AM %.3f   MPP2 PM/AM %.3f   n=%d" % (lab, a1, a2, len(s)))

# ---------- 2. performance on genuinely clear, high-sun intervals ----------
hi = clear[(clear.poa_cs > 700)]
print("\n--- performance index, clear days, POA>700 W/m2 (n=%d) ---" % len(hi))
print("  combined %.3f | MPP1 %.3f | MPP2 %.3f" % (hi.pi.median(), hi.pi1.median(), hi.pi2.median()))
print("  (Cascavel on the same definition was 0.79)")

# ---------- 3. monthly series and regimes ----------
q = hi.copy(); q["ym"] = q.ts.dt.to_period("M").dt.to_timestamp()
g = q.groupby("ym").agg(n=("pi","size"), pi=("pi","median"), pi1=("pi1","median"), pi2=("pi2","median"),
                        in1=("in1","median"), in2=("in2","median"),
                        v1=("v1","median"), v2=("v2","median"))
g = g[g.n >= 60]
print("\n--- monthly (clear, high sun) ---")
print(g.round(3).to_string())

y = g.pi.values; T = len(y)
C = np.full((T+1,T+1), np.inf)
for a in range(T):
    for b in range(a+1,T+1):
        s = y[a:b]; C[a,b] = float(((s-s.mean())**2).sum())
MIN=4
def dp(k):
    F=np.full((k+1,T+1),np.inf); bk=np.zeros((k+1,T+1),int); F[0,0]=0
    for j in range(1,k+1):
        for t in range(j*MIN,T+1):
            for s0 in range((j-1)*MIN,t-MIN+1):
                v=F[j-1,s0]+C[s0,t]
                if v<F[j,t]: F[j,t]=v; bk[j,t]=s0
    cps=[];t=T
    for j in range(k,0,-1): s0=bk[j,t]; cps.append(s0); t=s0
    return F[k,T], sorted(c for c in cps if c>0)
best=None
print("\n--- changepoints ---")
for k in range(1,6):
    sse,cps=dp(k); bic=T*np.log(sse/T)+(2*k-1)*np.log(T)
    print("  k=%d BIC %8.2f  %s" % (k,bic,[str(g.index[c].date()) for c in cps]))
    if best is None or bic<best[0]: best=(bic,k,cps)
_,K,CPS=best
edges=[0]+CPS+[T]; segs=[]
for i in range(len(edges)-1):
    a,b=edges[i],edges[i+1]; sl=g.iloc[a:b]
    segs.append(dict(start=str(sl.index[0].date()), end=str(sl.index[-1].date()), months=b-a,
                     pi=sl.pi.mean(), pi1=sl.pi1.mean(), pi2=sl.pi2.mean(),
                     in1=sl.in1.mean(), in2=sl.in2.mean(), v1=sl.v1.mean(), v2=sl.v2.mean()))
S=pd.DataFrame(segs); base=S.iloc[0]
for c in ["pi","pi1","pi2","in1","in2","v1","v2"]: S[c+"_r"]=100*(S[c]/base[c]-1)
pd.set_option("display.width",250)
print("\n--- segments (relative to the first) ---")
print(S[["start","end","months","pi","pi1_r","pi2_r","in1_r","in2_r","v1_r","v2_r"]].round(2).to_string(index=False))
print("\n--- string-specific or site-wide? ---")
for _,r in S.iterrows():
    d1,d2=r.in1_r,r.in2_r
    if abs(d1)<3 and abs(d2)<3: v="both at baseline"
    elif abs(d1-d2)<4: v="both strings move together -> site-wide"
    elif d1<d2: v="MPP1 specific"
    else: v="MPP2 specific"
    print("  %s..%s  MPP1 current %+6.1f %%  MPP2 %+6.1f %%   %s" % (r.start,r.end,d1,d2,v))

# ---------- 4. long-run trend ----------
t_yr = (g.index - g.index[0]).days/365.25
for c in ["pi","in1","in2"]:
    sl,ic,rr,p,se = stats.linregress(t_yr, g[c])
    print("  trend %-4s %+6.2f %%/yr (p=%.3g)" % (c, 100*sl/ic, p))

S.to_csv(caminho("curitiba_segments.csv"), index=False); g.to_csv(caminho("curitiba_monthly.csv"))

# ---------- 5. annual energy ----------
day = f[f.p_ac.notna()]
yr = day.groupby(day.ts.dt.year).agg(E=("p_ac", lambda s: s.sum()*5/60/1000), n=("p_ac","size"))
yr = yr[yr.n > 60000]
yr["kWh_kWp_est"] = yr.E/M["cap_total_kwp"]
yr["kWh_kWp_workbook"] = yr.E/12.0
print("\n--- annual energy ---")
print(yr.round(1).to_string())
