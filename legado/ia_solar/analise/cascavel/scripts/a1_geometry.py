# -*- coding: utf-8 -*-
"""Fit array tilt and azimuth from the 5-minute profile. Daily totals could not
separate east from west; the intraday shape can."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, solar

LAT = -24.83
D2R = np.pi/180
f = pd.read_parquet(caminho("frame5.parquet"))

# clear intervals, healthy regimes, sun well up, sane inverter records
q = f[(f.cosz > 0.15) & (f.d_Kt >= 0.62) & f.healthy &
      (f.p_ac > 0) & (f.p_ac < 4200) & f.p_ac.notna()].copy()
print("clear-sky intervals in healthy regimes:", len(q))

decl, omega, cosz, doy = q.decl.values, q.omega.values, q.cosz.values, q.doy.values
czp = np.clip(cosz, .02, None)
ghi = 1098.0*czp*np.exp(-.059/czp)
E0 = 1 + .033*np.cos(2*np.pi*doy/365.)
I0 = 1367.*E0*czp
kt = ghi/I0
kd = np.clip(np.where(kt<=.22, 1-.09*kt,
      np.where(kt<=.8, .9511-.1604*kt+4.388*kt**2-16.638*kt**3+12.336*kt**4, .165)),0,1)
dif = ghi*kd; bea = np.clip(ghi-dif,0,None)
Ai = np.clip(bea/I0,0,1); fb = np.sqrt(np.clip(bea/np.where(ghi>0,ghi,1),0,None))
P = q.p_ac.values

def poa(beta, gamma):
    ci = np.clip(solar.cos_incidence(LAT, decl, omega, beta, gamma), 0, None)
    Rb = ci/czp
    b2 = np.sin(beta*D2R/2)**3
    return ((bea+dif*Ai)*Rb + dif*(1-Ai)*((1+np.cos(beta*D2R))/2)*(1+fb*b2)
            + ghi*.16*((1-np.cos(beta*D2R))/2))

def r2(beta, gamma):
    p = poa(beta, gamma)
    return np.corrcoef(p, P)[0,1]**2

print("\n--- R2 vs azimuth, tilt fixed at the datasheet 13 deg ---")
print("   (180 = due north; 155 = datasheet; 205 = its mirror)")
best = None
for g in range(100, 266, 5):
    v = r2(13.0, g)
    star = ""
    if best is None or v > best[0]: best = (v, 13.0, g)
    if g in (155, 180, 205): star = "   <-- " + {155:"datasheet",180:"due north",205:"mirror of datasheet"}[g]
    print("   az %3d   R2 %.5f%s" % (g, v, star))

print("\n--- symmetry test: is the daily-total degeneracy broken? ---")
print("   R2(155) = %.6f" % r2(13,155))
print("   R2(205) = %.6f" % r2(13,205))
print("   difference = %.3e  (daily totals gave exactly 0)" % abs(r2(13,155)-r2(13,205)))

print("\n--- joint grid search ---")
bb = None
for beta in np.arange(0, 31, 1.0):
    for gamma in np.arange(110, 251, 2.5):
        v = r2(beta, gamma)
        if bb is None or v > bb[0]: bb = (v, beta, gamma)
print("   best fit: tilt %.0f deg, azimuth %.1f deg  (R2 %.5f)" % (bb[1], bb[2], bb[0]))
print("   datasheet: tilt 13 deg, azimuth 155.0 deg  (R2 %.5f)" % r2(13,155))
print("   azimuth %.1f deg = %.1f deg %s of north"
      % (bb[2], abs(180-bb[2]), "east" if bb[2] < 180 else "west"))

# production-weighted solar azimuth: a model-free read of which way the array looks
w = P/P.sum()
print("\n--- model-free check ---")
print("   production-weighted mean solar azimuth : %.1f deg (compass)" % (q.sol_az.values*w).sum())
print("   production-weighted mean solar time    : %.2f h" % (q.solar_time.values*w).sum())
print("   (a due-north array would give 0.0 / 12.00 by symmetry)")

# per-season, to show it is not a seasonal artefact
print("\n   by season:")
for lbl, mm in [("summer DJF",[12,1,2]),("autumn MAM",[3,4,5]),("winter JJA",[6,7,8]),("spring SON",[9,10,11])]:
    s = q[q.month.isin(mm)]
    if len(s) < 500: continue
    ws = s.p_ac.values/s.p_ac.values.sum()
    print("     %-11s weighted solar time %.2f h   n=%d" % (lbl, (s.solar_time.values*ws).sum(), len(s)))
