# -*- coding: utf-8 -*-
"""Two plants, two climates, one method. What generalises and what does not."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json

A = pd.read_parquet(caminho("frame5.parquet")); A["ts"] = pd.to_datetime(A.timestamp)
R = pd.read_parquet(caminho("curitiba_frame5.parquet")); R["ts"] = pd.to_datetime(R.timestamp)
MA = json.load(open(caminho("meta.json"))); MR = json.load(open(caminho("curitiba_meta.json")))
capA = MA["kwp"]*1000; capR = MR["cap_total_kwp"]*1000

rows = []
for nm, d, cap, lat, lon, inv, geom in [
    ("Usina Cascavel / Cascavel", A, capA, MA["lat"], MA["lon"], "Fronius Primo 4.0-1 (1 MPPT)",
     "%.0f deg / %.0f deg E of N" % (MA["tilt"], abs(MA["azimuth"]-180))),
    ("Usina Curitiba / Curitiba", R, capR, MR["lat"], MR["lon"], "Fronius Symo 12.0-3 (2 MPPT)",
     "MPP1 %.0f/%.0f, MPP2 %.0f/%.0f" % (MR["geom_mpp1"]["tilt"], abs(MR["geom_mpp1"]["azimuth"]-180),
                                          MR["geom_mpp2"]["tilt"], abs(MR["geom_mpp2"]["azimuth"]-180)))]:
    day = d[d.p_ac.notna() & (d.cosz > 0)]
    full = day.groupby(day.ts.dt.year).agg(E=("p_ac", lambda s: s.sum()*5/60/1000), n=("p_ac","size"))
    full = full[full.n > 60000]
    q = d[(d.poa_cs > 300) & (d.cosz > .15) & d.p_ac.notna() & (d.p_ac > 100)]
    rows.append(dict(site=nm, kWp=cap/1000, inverter=inv, geometry=geom,
                     lat=lat, lon=lon,
                     years=len(full), kWh_yr=full.E.mean(), yield_kWh_kWp=full.E.mean()/(cap/1000),
                     PI_median=q.pi.median(), n_5min=len(d)))
T = pd.DataFrame(rows)
pd.set_option("display.width", 240)
print("=== the two plants side by side ===")
print(T[["site","kWp","inverter","geometry","years","kWh_yr","yield_kWh_kWp","PI_median","n_5min"]].round(3).to_string(index=False))

print("\n=== resource: Curitiba vs Cascavel (NASA POWER daily GHI) ===")
da = pd.read_csv(caminho("nasa_power_true.csv"), index_col=0, parse_dates=True)
dc = pd.read_csv(caminho("nasa_power_curitiba_daily.csv"), index_col=0, parse_dates=True)
ov = da.index.intersection(dc.index)
a, c = da.loc[ov, "ALLSKY_SFC_SW_DWN"], dc.loc[ov, "ALLSKY_SFC_SW_DWN"]
print("  overlapping days: %d" % len(ov))
print("  Cascavel  mean GHI %.3f kWh/m2/d  -> %.0f kWh/m2/yr" % (a.mean(), a.mean()*365))
print("  Curitiba  mean GHI %.3f kWh/m2/d  -> %.0f kWh/m2/yr" % (c.mean(), c.mean()*365))
print("  Curitiba receives %.1f %% %s irradiance" % (abs(100*(c.mean()/a.mean()-1)),
                                                     "less" if c.mean() < a.mean() else "more"))
print("  day-to-day correlation between the two sites: r = %.3f" % a.corr(c))
print("  (they are %.0f km apart; the correlation says how far a single-site model travels)"
      % (111*np.hypot(MA["lat"]-MR["lat"], (MA["lon"]-MR["lon"])*np.cos(np.radians(MA["lat"])))))

mon = pd.DataFrame({"Cascavel": a.groupby(a.index.month).mean(),
                    "Curitiba": c.groupby(c.index.month).mean()})
mon["ratio"] = mon.Curitiba/mon.Cascavel
MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
mon.index=[MON[i-1] for i in mon.index]
print("\n  monthly mean GHI (kWh/m2/d):")
print(mon.round(3).to_string())

print("\n=== what the Cascavel method found, applied to Curitiba ===")
print("  see curitiba_segments.csv for the regime table")
T.to_csv(caminho("site_comparison.csv"), index=False)
