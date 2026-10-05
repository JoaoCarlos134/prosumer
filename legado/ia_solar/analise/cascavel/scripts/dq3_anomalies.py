# -*- coding: utf-8 -*-
"""Data quality, part 3: characterise the specific anomalies, then price a cleaning rule."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd

f = pd.read_parquet(caminho("frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
f["night"] = f.cosz <= 0
d = f[~f.night]

# ---------- 1. the >4 kW excursions ----------
print("--- AC power above the inverter rating ---")
bad = f[f.p_ac > 4000]
print("  %d intervals on %d distinct days" % (len(bad), bad.ts.dt.date.nunique()))
print(bad.groupby(bad.ts.dt.date).agg(n=("p_ac","size"), peak=("p_ac","max"),
                                      dc_peak=("p_dc","max")).round(0).to_string())
print("\n  DC power on those same intervals (max %.0f W) stays inside the array rating," % bad.p_dc.max())
print("  so the DC channels are fine and only the energy counter misbehaved.")
one = f[(f.ts.dt.date == pd.Timestamp("2019-11-19").date()) & (~f.night)]
print("\n  2019-11-19, 10:30-12:30:")
w = one[(one.hour >= 10.5) & (one.hour <= 12.5)]
print("   " + " ".join("%.0f" % x for x in w.p_ac))
print("   DC: " + " ".join("%.0f" % x for x in w.p_dc))
print("  -> AC energy runs to 6.6 kW while DC sits near 3 kW: the energy register,")
print("     not the plant. Affects %.4f%% of daylight rows." % (100*len(bad)/len(d)))

# ---------- 2. inverter efficiency above 1 ----------
print("\n--- inverter efficiency above unity ---")
e = d[d.eta_inv.notna()]
print("  share of daylight rows with eta > 1.00 : %.2f %%" % (100*(e.eta_inv > 1).mean()))
print("  share with eta > 1.02                  : %.2f %%" % (100*(e.eta_inv > 1.02).mean()))
q = e.groupby(pd.cut(e.p_dc, [0,100,300,1000,2000,3000,4300]), observed=True).agg(
    frac_gt1=("eta_inv", lambda s: 100*(s > 1).mean()), med=("eta_inv","median"), n=("eta_inv","size"))
print(q.round(3).to_string())
print("\n  the excess concentrates at low DC power, which is the signature of a timing")
print("  mismatch: AC comes from an energy counter integrated over the interval, DC from")
print("  an instantaneous current and voltage sample. They are not simultaneous.")
print("  -> eta_inv is not a trustworthy row-level feature; it is only meaningful")
print("     aggregated over many intervals, and even then it carries this bias.")

# ---------- 3. production below the horizon ----------
print("\n--- production recorded while the sun is below the horizon ---")
n = f[f.night & (f.p_ac > 10)]
print("  intervals: %d   median power %.0f W   p95 %.0f W   max %.0f W"
      % (len(n), n.p_ac.median(), n.p_ac.quantile(.95), n.p_ac.max()))
print("  solar elevation on those rows: median %.2f deg, min %.2f, max %.2f"
      % (n.elev.median(), n.elev.min(), n.elev.max()))
print("  -> all within a degree or so of the horizon: atmospheric refraction and the")
print("     interval being labelled by its end, not a clock error. Harmless.")
far = n[n.elev < -2]
print("  intervals with the sun more than 2 deg below horizon : %d" % len(far))
if len(far):
    print(far[["ts","elev","p_ac"]].head(5).to_string(index=False))

# ---------- 4. short days ----------
print("\n--- days with fewer than 288 records ---")
rpd = f.groupby(f.ts.dt.date).size()
short = rpd[rpd < 280]
print("  %d of %d days" % (len(short), len(rpd)))
sd = set(short.index)
sub = f[f.ts.dt.date.isin(sd)]
print("  on those days, share of rows that are night : %.1f %%" % (100*sub.night.mean()))
full = f[~f.ts.dt.date.isin(sd)]
print("  on full days, share of rows that are night  : %.1f %%" % (100*full.night.mean()))
print("  daylight rows per short day: median %.0f | per full day: median %.0f"
      % (sub[~sub.night].groupby(sub[~sub.night].ts.dt.date).size().median(),
         full[~full.night].groupby(full[~full.night].ts.dt.date).size().median()))
print("  -> short days are missing NIGHT rows only; daylight coverage is intact.")
print("     Row counts per day are therefore not a usable completeness signal.")

# ---------- 5. a cleaning rule, priced ----------
print("\n--- a defensible cleaning rule for a modelling table ---")
step = []
cur = f.copy(); n0 = len(cur)
def drop(mask, label):
    global cur
    k = int(mask.sum()); cur = cur[~mask]
    step.append((label, k, len(cur)))
for lab, m in [
    ("drop night rows (no signal)",            cur.cosz <= 0),
]:
    drop(m, lab)
drop(cur.p_ac.isna(), "drop daylight rows with no measurement")
drop(cur.p_ac > 4000, "drop AC power above inverter rating")
drop((cur.poa_cs > 300) & (cur.d_Kt >= .6) & (cur.p_ac == 0), "drop clear-sky zero-production rows")
drop(cur.d_Kt.isna(), "drop rows with no NASA POWER match")
print("  start: %d rows" % n0)
for lab, k, left in step:
    print("   -%6d   %-46s -> %d" % (k, lab, left))
print("  retained: %d  (%.2f %% of all rows, %.2f %% of daylight rows)"
      % (len(cur), 100*len(cur)/n0, 100*len(cur)/len(d)))

# ---------- 6. NASA POWER join quality ----------
print("\n--- NASA POWER join coverage at 5-minute resolution ---")
for c in ["d_Kt","d_poa","d_T2M","d_CLOUD_AMT","d_AOD_55"]:
    print("  %-13s missing on %6d daylight rows (%.2f %%)"
          % (c, int(d[c].isna().sum()), 100*d[c].isna().mean()))
print("\n  POWER is daily, the plant is 5-minutely: one weather value is broadcast across")
print("  ~200 rows. That is 2,558 genuinely independent weather observations, not 367k.")
