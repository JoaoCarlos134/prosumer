# -*- coding: utf-8 -*-
"""Diagnose the fault. 12 modules on a single MPPT string, so a voltage-side
failure (module / bypass diode / open circuit) and a current-side loss
(soiling, shading, mismatch) leave different fingerprints."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd

f = pd.read_parquet(caminho("frame5.parquet"))
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])
KWP = 3.96

# high-irradiance clear intervals only, so the comparison is like-for-like
q = f[(f.poa_cs > 700) & (f.d_Kt >= 0.62) & (f.p_ac > 200) & (f.p_ac < 4200)
      & f.v_dc.notna() & f.i_dc.notna() & (f.i_dc > 0.3) & (f.v_dc > 100)].copy()
print("matched high-irradiance clear intervals:", len(q))
print("(POA_clear-sky > 700 W/m2, daily Kt >= 0.62, inverter running)\n")

print("--- string electrical state by regime ---")
rows = []
for i, s in seg.iterrows():
    d = q[q.regime == i]
    if len(d) < 200: continue
    # normalise to the same modelled irradiance so regimes are comparable
    g = d.poa_cs.values / 1000.0
    rows.append(dict(
        regime="%s-%s" % (s.start.strftime("%b%y"), s.end.strftime("%b%y")),
        state="healthy" if s.pr >= 0.82 else "FAULT",
        n=len(d),
        V_dc=d.v_dc.median(),
        I_dc_per_kWm2=np.median(d.i_dc.values/g),
        P_dc_per_kWm2=np.median(d.p_dc.values/g),
        P_ac_per_kWm2=np.median(d.p_ac.values/g),
        eta_inv=d.eta_inv.median(),
    ))
R = pd.DataFrame(rows)
base = R.iloc[0]
for c in ["V_dc","I_dc_per_kWm2","P_dc_per_kWm2"]:
    R[c+"_rel"] = 100*(R[c]/base[c]-1)
pd.set_option("display.width", 200)
print(R.round(3).to_string(index=False))

print("\n--- interpretation ---")
worst = R.loc[R.P_dc_per_kWm2.idxmin()]
print("worst regime: %s" % worst.regime)
print("  DC voltage  %+.1f %% vs the healthy baseline" % worst.V_dc_rel)
print("  DC current  %+.1f %% vs the healthy baseline" % worst.I_dc_per_kWm2_rel)
print("  DC power    %+.1f %%" % worst.P_dc_per_kWm2_rel)
if abs(worst.V_dc_rel) > 3*abs(worst.I_dc_per_kWm2_rel):
    print("  -> voltage-side fault: modules or bypass diodes, not soiling")
elif abs(worst.I_dc_per_kWm2_rel) > 3*abs(worst.V_dc_rel):
    print("  -> current-side loss: soiling, shading or module current mismatch;")
    print("     the string voltage is intact, so no module is open-circuit")
else:
    print("  -> both voltage and current down: whole-array or inverter-side derate")

# the recovery step, at 5-minute resolution
print("\n--- the November 2023 step, month by month ---")
m = q.copy(); m["ym"] = pd.to_datetime(m.timestamp).dt.to_period("M")
g = m.groupby("ym").apply(lambda d: pd.Series({
    "n": len(d),
    "V_dc": d.v_dc.median(),
    "I_dc_norm": np.median(d.i_dc.values/(d.poa_cs.values/1000)),
    "P_ac_norm": np.median(d.p_ac.values/(d.poa_cs.values/1000)),
    "eta_inv": d.eta_inv.median()}), include_groups=False)
g = g[g.n >= 60]
win = g.loc["2023-06":"2024-04"]
print(win.round(2).to_string())
if "2023-10" in [str(x) for x in win.index] and "2023-11" in [str(x) for x in win.index]:
    a, b = win.loc["2023-10"], win.loc["2023-11"]
    print("\n  Oct 2023 -> Nov 2023")
    print("    DC voltage  %.1f -> %.1f V   (%+.1f %%)" % (a.V_dc, b.V_dc, 100*(b.V_dc/a.V_dc-1)))
    print("    DC current  %.2f -> %.2f A/kW/m2 (%+.1f %%)" % (a.I_dc_norm, b.I_dc_norm, 100*(b.I_dc_norm/a.I_dc_norm-1)))
    print("    AC power    %.0f -> %.0f W/kW/m2 (%+.1f %%)" % (a.P_ac_norm, b.P_ac_norm, 100*(b.P_ac_norm/a.P_ac_norm-1)))
    print("    inverter eff %.3f -> %.3f" % (a.eta_inv, b.eta_inv))

g.to_csv(caminho("fault_monthly.csv"))
R.to_csv(caminho("fault_regimes.csv"), index=False)

# clipping and inverter behaviour
print("\n--- clipping check (DC/AC = %.2f) ---" % (KWP/4.0))
d = f[(f.p_ac > 0) & (f.p_ac < 4600)]
print("  intervals above 3800 W AC : %d  (%.3f %% of daylight)"
      % ((d.p_ac > 3800).sum(), 100*(d.p_ac > 3800).mean()))
print("  intervals above 3950 W AC : %d" % (d.p_ac > 3950).sum())
print("  99.9th percentile of AC power: %.0f W" % d.p_ac.quantile(0.999))
print("  maximum plausible AC power  : %.0f W" % d.p_ac.max())
print("  maximum DC power            : %.0f W" % f[f.p_dc < 4500].p_dc.max())
