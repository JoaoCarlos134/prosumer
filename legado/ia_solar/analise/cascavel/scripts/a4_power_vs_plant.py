# -*- coding: utf-8 -*-
"""The daily analysis showed a 6-9% winter deficit in PR it could not explain.
With a physical clear-sky reference at 5-minute resolution we can ask whether
that deficit is in the plant or in the NASA POWER irradiance."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd
from scipy import stats

f = pd.read_parquet(caminho("frame5.parquet"))
MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# daily aggregates from the 5-minute record
d = f[(f.p_ac >= 0) & (f.p_ac < 4200)].groupby("date").agg(
    e_kwh=("p_ac", lambda s: s.sum()*5/60/1000),
    poa_cs=("poa_cs", lambda s: s.sum()*5/60/1000),
    n=("p_ac", "size"),
    month=("month", "first"), year=("year", "first"),
    d_poa=("d_poa", "first"), d_H=("d_H", "first"), d_Kt=("d_Kt", "first"),
    d_T2M=("d_T2M", "first"), healthy=("healthy", "first"), regime=("regime", "first"))
d = d[(d.n > 100) & d.d_poa.notna()]
clear = d[d.d_Kt >= 0.65]
print("days: %d total, %d clear" % (len(d), len(clear)))

print("\n--- NASA POWER modelled POA vs the physical clear-sky reference, CLEAR DAYS ---")
print("    (on a clear day the two should agree; a seasonal pattern here is reanalysis bias)")
clear = clear.copy(); clear["ratio"] = clear.d_poa / clear.poa_cs
g = clear.groupby("month").ratio.agg(["median", "size"])
g["dev_%"] = 100*(g["median"]/clear.ratio.median() - 1)
g.index = [MON[i-1] for i in g.index]
print(g.round(3).to_string())
amp = g["dev_%"].max() - g["dev_%"].min()
print("\n  seasonal swing in the POWER / clear-sky ratio : %.1f pp" % amp)
win = g.loc[["Jun","Jul","Aug"], "dev_%"].mean()
sum_ = g.loc[["Dec","Jan","Feb"], "dev_%"].mean()
print("  winter JJA %+.1f %%   summer DJF %+.1f %%   -> POWER reads %s in winter"
      % (win, sum_, "HIGH" if win > sum_ else "LOW"))

print("\n--- the same months, measured plant performance against each reference ---")
c2 = clear.copy()
c2["pi_cs"]    = c2.e_kwh / (3.96 * c2.poa_cs)     # vs physical clear-sky
c2["pr_power"] = c2.e_kwh / (3.96 * c2.d_poa)      # vs NASA POWER
h = c2[c2.healthy]
t = h.groupby("month")[["pi_cs", "pr_power"]].median()
t["n"] = h.groupby("month").size()
t.index = [MON[i-1] for i in t.index]
t["dev_cs_%"]    = 100*(t.pi_cs/t.pi_cs.median()-1)
t["dev_power_%"] = 100*(t.pr_power/t.pr_power.median()-1)
print(t.round(3).to_string())
print("\n  seasonal swing vs physical clear-sky : %.1f pp" % (t["dev_cs_%"].max()-t["dev_cs_%"].min()))
print("  seasonal swing vs NASA POWER         : %.1f pp" % (t["dev_power_%"].max()-t["dev_power_%"].min()))
print("\n  If the swing collapses against the physical reference, the winter deficit")
print("  was never in the plant - it is a seasonal bias in the reanalysis irradiance.")

print("\n--- NASA POWER daily irradiance error vs the plant, all clear days ---")
print("  median POWER/clear-sky ratio : %.4f" % clear.ratio.median())
print("  IQR                          : %.4f - %.4f" % (clear.ratio.quantile(.25), clear.ratio.quantile(.75)))
r = stats.linregress(clear.poa_cs, clear.d_poa)
print("  regression POWER = %.4f * clear-sky + %.3f   (R2 %.4f)" % (r.slope, r.intercept, r.rvalue**2))

# ---------- temperature coefficient, now properly conditioned ----------
print("\n--- power temperature coefficient at matched irradiance ---")
hi = f[(f.poa_cs.between(820, 1000)) & (f.d_Kt >= 0.65) & f.healthy
       & (f.p_dc > 500) & (f.p_dc < 4300) & (f.v_dc > 250) & f.d_T2M.notna()].copy()
hi["p_norm"] = hi.p_dc / (hi.poa_cs/1000.0)
print("  matched intervals: %d  (clear-sky POA 820-1000 W/m2, healthy regimes)" % len(hi))
for xv, lab, unit in [("d_T2M", "ambient air temperature", "%/K"), ("v_dc", "string DC voltage", "%/V")]:
    s = stats.linregress(hi[xv], hi.p_norm)
    print("  vs %-24s slope %+.3f %s   (r %+.3f, n %d)"
          % (lab, 100*s.slope/hi.p_norm.median(), unit, s.rvalue, len(hi)))
# V_dc as a thermometer: dV/dT from the data, then dP/dT via the chain rule
sv = stats.linregress(hi.d_T2M, hi.v_dc)
sp = stats.linregress(hi.v_dc, hi.p_norm)
print("\n  string voltage vs air temperature : %+.3f V/K  (%.3f %%/K of Vmp)"
      % (sv.slope, 100*sv.slope/hi.v_dc.median()))
print("  power vs string voltage           : %+.3f %%/V" % (100*sp.slope/hi.p_norm.median()))
print("  implied power temp coefficient    : %+.3f %%/K" % (100*sv.slope*sp.slope/hi.p_norm.median()))
print("  (datasheet for a 330 Wp module is typically -0.35 to -0.45 %/K)")

# ---------- inverter efficiency curve ----------
print("\n--- inverter conversion efficiency vs load ---")
e = f[(f.p_dc > 40) & (f.p_dc < 4300) & (f.p_ac > 0) & (f.p_ac < 4200)
      & f.eta_inv.between(0.3, 1.02)].copy()
e["load_%"] = 100*e.p_dc/4000.0
b = e.groupby(pd.cut(e["load_%"], [0,2,5,10,20,30,50,70,90,110]), observed=True).agg(
    eta=("eta_inv","median"), n=("eta_inv","size"))
print(b.round(4).to_string())
print("\n  weighted (energy-share) efficiency : %.4f"
      % (np.average(e.eta_inv, weights=e.p_ac)))

d.to_csv(caminho("daily_from_5min.csv"))
