# -*- coding: utf-8 -*-
"""POWER hourly is stamped 'LST'. Establish what that means against the plant's
own clock before joining, then merge onto the 5-minute frame."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd

H = pd.read_csv(caminho("nasa_power_hourly.csv"), index_col=0, parse_dates=True)
f = pd.read_parquet(caminho("frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
f["night"] = f.cosz <= 0
print("hourly rows %d, 5-min rows %d" % (len(H), len(f)))

d = f[f.p_ac.notna() & (f.p_ac <= 4000)].copy()

print("\n--- what offset aligns POWER's LST with the inverter's clock? ---")
best = None
for off_min in range(-120, 121, 5):
    key = (d.ts + pd.Timedelta(minutes=off_min)).dt.floor("h")
    g = H.ALLSKY_SFC_SW_DWN.reindex(key).values
    m = np.isfinite(g) & np.isfinite(d.p_ac.values)
    if m.sum() < 1000: continue
    r = np.corrcoef(g[m], d.p_ac.values[m])[0, 1]
    if best is None or r > best[0]: best = (r, off_min)
    if off_min % 20 == 0:
        print("   offset %+4d min   r = %.4f" % (off_min, r))
print("\n  best alignment: %+d minutes, r = %.4f" % (best[1], best[0]))
print("  longitude correction alone would be %+.0f min (4 x (%.3f - (-45)))"
      % (4*(-53.65+45), -53.65))
print("  -> POWER's LST is mean solar time from longitude; it does NOT include the")
print("     equation of time, and the stamp is the hour the value applies to.")
OFF = best[1]

# ---- join hourly onto the 5-minute grid ----
key = (f.ts + pd.Timedelta(minutes=OFF)).dt.floor("h")
cols = ["ALLSKY_SFC_SW_DWN","CLRSKY_SFC_SW_DWN","ALLSKY_SFC_SW_DNI","ALLSKY_SFC_SW_DIFF",
        "ALLSKY_KT","TOA_SW_DWN","T2M","RH2M","WS2M","WS10M","PS","PRECTOTCORR",
        "CLOUD_AMT","AOD_55","QV2M"]
Hc = H[cols].add_prefix("h_")
f = f.join(Hc.reindex(key).set_index(f.index))

# smooth interpolation: hourly values are step functions on a 5-min grid, so also
# provide a centred linear interpolation, which is closer to the physical truth
Hi = H[cols].copy()
Hi.index = Hi.index + pd.Timedelta(minutes=30)          # value applies to hour centre
Hi = Hi.reindex(Hi.index.union((f.ts + pd.Timedelta(minutes=OFF)).sort_values().unique())).sort_index()
Hi = Hi.interpolate(method="time", limit=12)
lin = Hi.reindex(f.ts + pd.Timedelta(minutes=OFF)).add_prefix("hi_")
f = f.join(lin.set_index(f.index))

# clear-sky index at hourly resolution: the variable the daily product cannot give
f["h_kc"] = f.h_ALLSKY_SFC_SW_DWN / f.h_CLRSKY_SFC_SW_DWN.replace(0, np.nan)
f["hi_kc"] = f.hi_ALLSKY_SFC_SW_DWN / f.hi_CLRSKY_SFC_SW_DWN.replace(0, np.nan)

day = f[~f.night]
print("\n--- coverage of the hourly join on daylight rows ---")
for c in ["h_ALLSKY_SFC_SW_DWN","h_ALLSKY_SFC_SW_DNI","h_ALLSKY_KT","h_CLOUD_AMT","hi_ALLSKY_SFC_SW_DWN"]:
    print("   %-24s missing %.2f %%" % (c, 100*day[c].isna().mean()))

print("\n--- how much more informative is hourly than daily? ---")
sub = day[day.p_ac.notna() & (day.p_ac <= 4000)]
for c, lab in [("d_H","daily GHI (broadcast)"), ("h_ALLSKY_SFC_SW_DWN","hourly GHI"),
               ("hi_ALLSKY_SFC_SW_DWN","hourly GHI, interpolated"),
               ("poa_cs","modelled clear-sky POA")]:
    s = sub[[c,"p_ac"]].dropna()
    print("   r(%-28s, AC power) = %.4f" % (lab, np.corrcoef(s[c], s.p_ac)[0,1]))
print("\n   distinct weather values available:")
print("     daily  : %d" % sub.d_H.nunique())
print("     hourly : %d" % sub.h_ALLSKY_SFC_SW_DWN.nunique())

f.drop(columns=["ts"]).to_parquet(caminho("frame5h.parquet"), index=False, compression="zstd")
print("\nwrote frame5h.parquet %s" % (f.shape,))
