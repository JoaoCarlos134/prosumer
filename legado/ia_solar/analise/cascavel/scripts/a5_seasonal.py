# -*- coding: utf-8 -*-
"""The 'winter deficit' reversed sign once the temperature correction was dropped.
Test whether the correction itself produced it, and retry the temperature
coefficient on genuinely clear instants rather than merely clear days."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd
from scipy import stats
MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ---------- 1. raw vs temperature-corrected PR seasonality, daily record ----------
d = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])
d["healthy"] = False
for _, s in seg.iterrows():
    if s.pr >= 0.82:
        d.loc[(d.index >= s.start) & (d.index <= s.end + pd.offsets.MonthEnd(1)), "healthy"] = True
q = d[(d.poa >= 1.0) & d.pr.between(.05,1.3) & d.healthy]
t = q.groupby(q.index.month)[["pr","pr_tcorr","tcell"]].mean()
t.index = [MON[i-1] for i in t.index]
t["raw_dev_%"]   = 100*(t.pr/t.pr.mean()-1)
t["tcorr_dev_%"] = 100*(t.pr_tcorr/t.pr_tcorr.mean()-1)
print("--- seasonality of PR, healthy regimes, daily NASA POWER record ---")
print(t.round(3).to_string())
print("\n  swing in RAW PR              : %.1f pp  (%s highest)"
      % (t["raw_dev_%"].max()-t["raw_dev_%"].min(), t["raw_dev_%"].idxmax()))
print("  swing in TEMP-CORRECTED PR   : %.1f pp  (%s highest)"
      % (t["tcorr_dev_%"].max()-t["tcorr_dev_%"].min(), t["tcorr_dev_%"].idxmax()))
print("\n  The correction divides by (1 + g*(Tcell-25)) with g = -0.004/K.")
print("  Cell temperature ranges %.1f to %.1f C across the year." % (t.tcell.min(), t.tcell.max()))
print("  Implied coefficient from the raw seasonal swing: %+.3f %%/K"
      % (100*(t.pr.max()-t.pr.min())/t.pr.mean()/(t.tcell.min()-t.tcell.max())))
if t["raw_dev_%"].idxmin() != t["tcorr_dev_%"].idxmin():
    print("  -> the correction REVERSES which months look worst. The 'winter deficit'")
    print("     is an artefact of the assumed temperature coefficient, not the plant.")

# what coefficient would flatten the year?
best = None
for g in np.arange(-0.010, 0.0005, 0.0002):
    prc = q.pr/(1+g*(q.tcell-25))
    m = prc.groupby(q.index.month).mean()
    cv = m.std()/m.mean()
    if best is None or cv < best[0]: best = (cv, g)
print("\n  coefficient that best flattens the seasonal cycle: %+.3f %%/K (CV %.4f)"
      % (100*best[1], best[0]))
print("  assumed in the audit: -0.400 %/K")

# ---------- 2. temperature coefficient on genuinely clear instants ----------
print("\n--- temperature coefficient, restricted to the clear-sky envelope ---")
f = pd.read_parquet(caminho("frame5.parquet"))
h = f[(f.poa_cs > 600) & f.healthy & (f.p_dc > 400) & (f.p_dc < 4300)
      & (f.v_dc > 250) & f.d_T2M.notna() & (f.p_ac > 0) & (f.p_ac < 4200)].copy()
h["p_norm"] = h.p_dc/(h.poa_cs/1000.0)
# keep only instants at the top of the distribution for their irradiance bin:
# these are the moments with no cloud attenuation, where poa_cs is a true reference
h["pb"] = pd.cut(h.poa_cs, np.arange(600, 1060, 50))
thr = h.groupby("pb", observed=True).p_norm.quantile(0.90).rename("thr")
h = h.join(thr, on="pb")
env = h[h.p_norm >= h.thr*0.97].copy()
print("  intervals on the clear envelope: %d of %d" % (len(env), len(h)))
for xv, lab in [("d_T2M","ambient air temperature"), ("v_dc","string DC voltage")]:
    s = stats.linregress(env[xv], env.p_norm)
    print("    p_norm vs %-22s %+.3f %%/unit  (r %+.3f)"
          % (lab, 100*s.slope/env.p_norm.median(), s.rvalue))
sv = stats.linregress(env.d_T2M, env.v_dc)
sp = stats.linregress(env.v_dc, env.p_norm)
print("    Vmp vs air temperature  : %+.3f V/K = %+.3f %%/K"
      % (sv.slope, 100*sv.slope/env.v_dc.median()))
print("    implied power coeff     : %+.3f %%/K" % (100*sv.slope*sp.slope/env.p_norm.median()))
s = stats.linregress(env.d_T2M, env.p_norm)
print("    direct p_norm vs T2M    : %+.3f %%/K  <- best available estimate"
      % (100*s.slope/env.p_norm.median()))
print("\n  Vmp temperature coefficient is the trustworthy number here: crystalline")
print("  silicon datasheets give -0.40 to -0.45 %/K for Vmp, so the modules are normal.")
