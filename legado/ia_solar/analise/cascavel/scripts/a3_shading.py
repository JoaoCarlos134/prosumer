# -*- coding: utf-8 -*-
"""Soiling or shading? A uniform deposit scales the whole day down by the same
factor; an obstruction bites at particular sun positions. Also resolves the
6-9% winter deficit the daily analysis could not explain."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd

f = pd.read_parquet(caminho("frame5.parquet"))
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])

q = f[(f.d_Kt >= 0.65) & (f.poa_cs > 80) & (f.p_ac >= 0) & (f.p_ac < 4200)
      & f.p_ac.notna() & (f.elev > 3)].copy()
q["pi"] = q.p_ac / (3.96 * q.poa_cs)          # measured / clear-sky expectation
q = q[q.pi.between(0, 1.6)]
q["st_bin"] = (q.solar_time * 2).round() / 2   # half-hour bins of solar time
print("clear-day daylight intervals:", len(q))

def prof(d, col="st_bin"):
    g = d.groupby(col).pi.agg(["median", "size"])
    return g[g["size"] >= 25]

print("\n--- performance index by solar time, healthy vs faulted ---")
h = prof(q[q.healthy]); u = prof(q[~q.healthy])
j = pd.concat([h["median"].rename("healthy"), u["median"].rename("faulted")], axis=1).dropna()
j["ratio"] = j.faulted / j.healthy
j["loss_%"] = 100 * (1 - j.ratio)
print(j.round(3).to_string())
mid = j[(j.index >= 9) & (j.index <= 15)]
edge = j[(j.index < 8.5) | (j.index > 15.5)]
print("\n  midday (09-15h solar) loss : %.1f %%" % mid["loss_%"].mean())
print("  edges (<8.5h, >15.5h) loss : %.1f %%" % edge["loss_%"].mean())
spread = j["loss_%"].max() - j["loss_%"].min()
print("  spread across the day      : %.1f pp" % spread)
if spread < 8:
    print("  -> the loss is nearly FLAT across the day: uniform soiling / module")
    print("     current loss, not a localised obstruction")
else:
    print("  -> the loss is concentrated in particular hours: shading")

print("\n--- the winter deficit: healthy regimes only, by season and solar time ---")
seas = {"summer DJF":[12,1,2], "autumn MAM":[3,4,5], "winter JJA":[6,7,8], "spring SON":[9,10,11]}
tab = {}
for lbl, mm in seas.items():
    d = q[q.healthy & q.month.isin(mm)]
    tab[lbl] = prof(d)["median"]
S = pd.DataFrame(tab).dropna(how="all")
print(S.round(3).to_string())
print("\n  whole-day mean PI by season (healthy regimes):")
for lbl, mm in seas.items():
    d = q[q.healthy & q.month.isin(mm)]
    print("    %-11s PI %.3f   n=%6d" % (lbl, d.pi.median(), len(d)))

print("\n--- shading map: PI by solar elevation and azimuth (healthy, clear) ---")
d = q[q.healthy].copy()
d["el_bin"] = pd.cut(d.elev, [3,8,13,20,30,40,50,60,90])
d["az_bin"] = pd.cut(d.sol_az, [30,60,80,100,120,240,260,280,300,330])
pv = d.pivot_table(index="el_bin", columns="az_bin", values="pi", aggfunc="median", observed=True)
cnt = d.pivot_table(index="el_bin", columns="az_bin", values="pi", aggfunc="size", observed=True)
print(pv.where(cnt >= 30).round(3).to_string())
print("\n  (low elevation + eastern azimuth = morning horizon;")
print("   low elevation + western azimuth = evening horizon)")

low_e = d[(d.elev < 13) & (d.sol_az < 110)].pi.median()
low_w = d[(d.elev < 13) & (d.sol_az > 250)].pi.median()
high  = d[d.elev > 45].pi.median()
print("\n  PI at sun <13 deg in the east : %.3f" % low_e)
print("  PI at sun <13 deg in the west : %.3f" % low_w)
print("  PI at sun >45 deg             : %.3f" % high)

S.to_csv(caminho("season_profile.csv")); j.to_csv(caminho("tod_loss.csv")); pv.to_csv(caminho("shading_map.csv"))

# clear-sky model bias check against NASA POWER, so PI<1 is not just model error
print("\n--- is the clear-sky reference itself biased? ---")
dd = q[q.healthy].groupby("date").agg(
    poa_cs_kwh=("poa_cs", lambda s: s.sum()*5/60/1000),
    e_kwh=("p_ac", lambda s: s.sum()*5/60/1000),
    d_poa=("d_poa", "first"), d_Kt=("d_Kt", "first"))
dd = dd[dd.poa_cs_kwh > 3]
print("  clear days, n=%d" % len(dd))
print("  Haurwitz clear-sky POA daily total : %.2f kWh/m2 (median)" % dd.poa_cs_kwh.median())
print("  NASA POWER modelled POA            : %.2f kWh/m2 (median)" % dd.d_poa.median())
print("  ratio POWER / clear-sky            : %.3f" % (dd.d_poa/dd.poa_cs_kwh).median())
