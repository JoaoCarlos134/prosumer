# -*- coding: utf-8 -*-
"""Oct 2023 vs Nov-Dec 2023, either side of the repair. Six weeks apart, so sun
geometry barely moves: whatever changed shows up cleanly.

A cleaning restores every sun position by the same factor.
Removing an obstruction restores only the sun positions it was blocking."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd

f = pd.read_parquet(caminho("frame5.parquet"))
f["ts"] = pd.to_datetime(f.timestamp)
q = f[(f.d_Kt >= 0.60) & (f.poa_cs > 150) & (f.p_ac > 0) & (f.p_ac < 4200)
      & f.i_dc.notna() & (f.elev > 5)].copy()
q["pi"] = q.p_ac/(3.96*q.poa_cs)
q["i_norm"] = q.i_dc/(q.poa_cs/1000.0)

before = q[(q.ts >= "2023-08-15") & (q.ts < "2023-11-01")]
after  = q[(q.ts >= "2023-11-01") & (q.ts < "2024-01-15")]
print("before (15 Aug - 31 Oct 2023): %d intervals" % len(before))
print("after  (01 Nov 2023 - 14 Jan 2024): %d intervals" % len(after))

print("\n--- recovery factor by solar time ---")
print("    (a uniform cleaning gives the same ratio in every row)")
def by(d, key, bins=None):
    g = d.groupby(key, observed=True).agg(pi=("pi","median"), i=("i_norm","median"), n=("pi","size"))
    return g[g.n >= 20]
before["st"] = (before.solar_time*2).round()/2
after["st"]  = (after.solar_time*2).round()/2
b, a = by(before,"st"), by(after,"st")
j = pd.concat([b.pi.rename("before"), a.pi.rename("after"),
               b.i.rename("I_before"), a.i.rename("I_after")], axis=1).dropna()
j["PI_ratio"] = j.after/j.before
j["I_ratio"]  = j.I_after/j.I_before
print(j.round(3).to_string())
core = j[(j.index >= 8) & (j.index <= 16)]
print("\n  recovery factor 08-16h solar : mean %.3f, sd %.3f, range %.3f-%.3f"
      % (core.I_ratio.mean(), core.I_ratio.std(), core.I_ratio.min(), core.I_ratio.max()))
if core.I_ratio.std() < 0.05:
    print("  -> uniform across the whole day: a CLEANING or a module-level")
    print("     current restoration, not the removal of an obstruction")
else:
    print("  -> varies with time of day: an obstruction was removed")

print("\n--- recovery factor by solar elevation ---")
for d, nm in [(before,"before"),(after,"after")]:
    d["eb"] = pd.cut(d.elev, [5,15,25,35,45,55,65,90])
b2, a2 = by(before,"eb"), by(after,"eb")
k = pd.concat([b2.i.rename("I_before"), a2.i.rename("I_after")], axis=1).dropna()
k["ratio"] = k.I_after/k.I_before
print(k.round(3).to_string())
print("  spread of the recovery factor across elevation: %.3f" % (k.ratio.max()-k.ratio.min()))

print("\n--- string voltage either side of the step ---")
for d, nm in [(before,"before"),(after,"after")]:
    hi = d[d.poa_cs > 700]
    print("  %-7s Vmp median %.1f V   Impp/kWm2 %.2f A   PI %.3f   n=%d"
          % (nm, hi.v_dc.median(), hi.i_norm.median(), hi.pi.median(), len(hi)))

print("\n--- was the same thing true at the 2021 onset? (gradual or sudden) ---")
m = q.copy(); m["ym"] = m.ts.dt.to_period("M")
g = m[m.poa_cs > 700].groupby("ym").agg(i=("i_norm","median"), v=("v_dc","median"), n=("i_norm","size"))
g = g[g.n >= 50]
w = g.loc["2021-01":"2022-06"]
w = w.assign(i_rel=100*(w.i/g.loc["2020-01":"2021-04"].i.median()-1))
print(w.round(2).to_string())
