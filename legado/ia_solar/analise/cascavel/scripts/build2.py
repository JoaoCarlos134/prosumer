# -*- coding: utf-8 -*-
"""Rebuild the master dataset on the DATASHEET geometry from 'Fatura de energia.xlsx'.

Known now, assumed before:
  12 x 330 Wp = 3.96 kWp DC   (was 4.00)
  inverter 4 kW AC            (DC/AC = 0.99 -> clipping essentially impossible)
  tilt 13 deg                 (was fitted to 17)
  orientation 25 deg East of North -> Duffie&Beckman gamma = 155 (was fitted to 244)
  24 49'30.4"S  53 38'43.9"W  (was city-centre Cascavel; same POWER grid cell)
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, solar

LAT, LON = -24.83, -53.65
KWP_DC  = 3.96
KW_AC   = 4.0
TILT    = 13.0
AZIM    = 155.0          # 180 = due north; 155 = 25 deg east of north
GAMMA_PV = -0.0040

gen = pd.read_excel(caminho("serie.xlsx"))
gen.columns = ["data", "e_kwh", "e_kwp_old", "e_tot"]
gen = gen.set_index("data")[["e_kwh"]]

pw = pd.read_csv(caminho("nasa_power_true.csv"), index_col=0, parse_dates=True)
df = gen.join(pw, how="left")

df["n"]  = df.index.dayofyear
df["H"]  = df["ALLSKY_SFC_SW_DWN"]
df["H0"] = solar.H0_daily(LAT, df["n"].values)
df["Kt"] = df["H"] / df["H0"]
df["Hd"] = df["ALLSKY_SFC_SW_DIFF"]
fb = df["Hd"].isna() & df["H"].notna()
df.loc[fb, "Hd"] = df.loc[fb, "H"] * solar.erbs_daily_diffuse_fraction(df.loc[fb, "Kt"])
df["kd"] = df["Hd"] / df["H"]
df["Kc"] = df["H"] / df["CLRSKY_SFC_SW_DWN"]

alb = df["ALLSKY_SRF_ALB"].fillna(df["ALLSKY_SRF_ALB"].median())
valid = df[["H", "Hd", "T2M", "e_kwh"]].notna().all(axis=1)
sub = df[valid]
n_, H_, Hd_ = sub["n"].values.astype(float), sub["H"].values, sub["Hd"].values
alb_, tamb_, wind_, E_ = alb[valid].values, sub["T2M"].values, sub["WS2M"].values, sub["e_kwh"].values
month_ = sub.index.month.values
print("usable days:", len(sub))

def evaluate(beta, gamma, kwp):
    r = solar.poa_daily(LAT, n_, H_, Hd_, beta, gamma, albedo=alb_)
    poa = r["poa"]
    dt = (r["daylength"] / r["_poa_h"].shape[1])[:, None]
    poa_wm2 = np.where(dt > 0, r["_poa_h"] / dt, 0) * 1000.0
    tcell = solar.weighted_cell_temp(poa_wm2, tamb_, wind_)
    pr = E_ / (kwp * np.where(poa > 0.05, poa, np.nan))
    pr_c = pr / (1 + GAMMA_PV * (tcell - 25.0))
    return poa, tcell, pr, pr_c, r

def seasonal_cv(prc):
    m = pd.Series(prc, index=month_).groupby(level=0).mean()
    return float(m.std() / m.mean())

print("\n%-26s %7s %7s %8s %8s" % ("geometry", "POA/yr", "meanPR", "R2(E~POA)", "seasCV"))
for lbl, (b, g, k) in {
        "TRUE 13 deg / 25 E of N": (TILT, AZIM, KWP_DC),
        "fitted (old) 17/244":     (17.0, 244.0, 4.00),
        "latitude tilt, due N":    (abs(LAT), 180.0, KWP_DC),
        "horizontal":              (0.0, 180.0, KWP_DC)}.items():
    p, tc, q, qc, _ = evaluate(b, g, k)
    print("%-26s %7.0f %7.3f %8.4f %8.4f"
          % (lbl, np.nanmean(p) * 365, np.nanmean(q),
             np.corrcoef(p, E_)[0, 1] ** 2, seasonal_cv(qc)))

poa, tcell, pr, pr_c, r = evaluate(TILT, AZIM, KWP_DC)

out = sub.copy()
out["poa"], out["poa_beam"] = poa, r["poa_beam"]
out["poa_diff"], out["poa_grnd"] = r["poa_diff"], r["poa_grnd"]
out["cos_inc"], out["airmass"] = r["cos_inc_w"], r["airmass_w"]
out["daylength"] = r["daylength"]
out["tcell"], out["pr"], out["pr_tcorr"] = tcell, pr, pr_c
out["yield_sp"] = out["e_kwh"] / KWP_DC
out["tr_gain"]  = out["poa"] / out["H"]
out["dT"]       = out["T2M_MAX"] - out["T2M_MIN"]
out["dewdep"]   = out["T2M"] - out["T2MDEW"]
out["uv_ratio"] = out["ALLSKY_SFC_UVA"] / out["H"]
out["ac_load"]  = out["e_kwh"] / (KW_AC * out["daylength"])   # mean AC loading while generating

rain = out["PRECTOTCORR"].fillna(0.0)
dry = np.zeros(len(rain)); c = 0
for i, v_ in enumerate(rain.values):
    c = 0 if v_ >= 1.0 else c + 1
    dry[i] = c
out["dry_days"] = dry
out["rain_7d"]  = rain.rolling(7, min_periods=1).sum()
out["rain_30d"] = rain.rolling(30, min_periods=1).sum()
out["year"], out["month"] = out.index.year, out.index.month
out["t_years"] = (out.index - out.index[0]).days / 365.25

meta = dict(lat=LAT, lon=LON, kwp=KWP_DC, kw_ac=KW_AC, dc_ac=KWP_DC / KW_AC,
            tilt=TILT, azimuth=AZIM, azimuth_deg_east_of_north=25.0,
            geometry_source="datasheet (Fatura de energia.xlsx, sheet Geracao)",
            modules="12 x 330 Wp", gamma_pv=GAMMA_PV,
            n_days=int(len(out)), start=str(out.index.min().date()), end=str(out.index.max().date()),
            r2_E_poa=float(np.corrcoef(poa, E_)[0, 1] ** 2), seasonal_cv=seasonal_cv(pr_c))
json.dump(meta, open(caminho("meta.json"), "w"), indent=1)
out.to_csv(caminho("master.csv"))
print("\nwrote master.csv", out.shape)
print(out[["e_kwh", "poa", "pr", "pr_tcorr", "tcell"]].describe().round(3).to_string())
