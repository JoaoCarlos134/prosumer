# -*- coding: utf-8 -*-
"""Curitiba / Curitiba, corrected build.

Fixes over the first attempt:
  * merge NASA POWER BEFORE fitting, so the fit can be restricted to clear days
  * fit geometry on DC CURRENT, which tracks irradiance without a temperature term
  * subsample for the grid search (speed), refine on the full clear set
  * estimate capacity from the fitted POA, not from a raw percentile
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, solar

LAT, LON, TZM = -25.4284, -49.2733, -45.0
D2R = np.pi/180
rng = np.random.default_rng(0)

df = pd.read_parquet(caminho("curitiba_5min.parquet"))
df = df.dropna(subset=["timestamp"]).drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
t = df.timestamp
doy = t.dt.dayofyear.values.astype(float); hour = (t.dt.hour + t.dt.minute/60).values
B = 2*np.pi*(doy-1)/365.
decl = (0.006918 - .399912*np.cos(B) + .070257*np.sin(B) - .006758*np.cos(2*B)
        + .000907*np.sin(2*B) - .002697*np.cos(3*B) + .00148*np.sin(3*B))/D2R
eot = 229.18*(.000075 + .001868*np.cos(B) - .032077*np.sin(B)
              - .014615*np.cos(2*B) - .040849*np.sin(2*B))
solar_time = hour + (4*(LON-TZM)+eot)/60.
omega = 15*(solar_time-12)
cosz = np.clip(np.sin(decl*D2R)*np.sin(LAT*D2R)+np.cos(decl*D2R)*np.cos(LAT*D2R)*np.cos(omega*D2R), -1, 1)
elev = np.degrees(np.arcsin(cosz)); czp = np.clip(cosz,.01,None)
ghi_cs = np.where(cosz>0, 1098.*czp*np.exp(-.059/czp), 0.)
I0 = 1367.*(1+.033*np.cos(2*np.pi*doy/365.))*czp
kt = np.where(I0>0, ghi_cs/I0, 0)
kd = np.clip(np.where(kt<=.22,1-.09*kt,
      np.where(kt<=.8,.9511-.1604*kt+4.388*kt**2-16.638*kt**3+12.336*kt**4,.165)),0,1)
dif = ghi_cs*kd; bea = np.clip(ghi_cs-dif,0,None)
Ai = np.clip(np.where(I0>0,bea/I0,0),0,1)
fb = np.sqrt(np.where(ghi_cs>0, bea/np.where(ghi_cs>0,ghi_cs,1), 0))

# ---- daily POWER first, so the fit can use clearness ----
D = pd.read_csv(caminho("nasa_power_curitiba_daily.csv"), index_col=0, parse_dates=True); D.index = D.index.date
dates = t.dt.date.values
Kt_d = pd.Series(dates).map(D["ALLSKY_KT"]).values.astype(float)
GHI_d = pd.Series(dates).map(D["ALLSKY_SFC_SW_DWN"]).values.astype(float)

def poa_full(beta, gamma, idx=None):
    sl = slice(None) if idx is None else idx
    ci = np.clip(solar.cos_incidence(LAT, decl[sl], omega[sl], beta, gamma), 0, None)
    b2 = np.sin(beta*D2R/2)**3
    return np.where(cosz[sl]>0, np.clip(
        (bea[sl]+dif[sl]*Ai[sl])*(ci/czp[sl])
        + dif[sl]*(1-Ai[sl])*((1+np.cos(beta*D2R))/2)*(1+fb[sl]*b2)
        + ghi_cs[sl]*.16*((1-np.cos(beta*D2R))/2), 0, None), 0.)

print("--- fitting geometry on CLEAR days, per string, using DC current ---")
geom = {}
for k in (1,2):
    I = (df["corrente_cc_mpp%d_A"%k].values).astype(float)
    clear = (cosz > .20) & np.isfinite(I) & (I > .5) & np.isfinite(Kt_d) & (Kt_d >= .60)
    idx_all = np.flatnonzero(clear)
    idx = rng.choice(idx_all, size=min(40000, idx_all.size), replace=False)
    idx.sort()
    print("  MPP%d  clear intervals %d (fit on %d)" % (k, idx_all.size, idx.size))
    best = None
    for beta in np.arange(0, 41, 2.5):
        for gamma in np.arange(100, 261, 5.):
            r = np.corrcoef(poa_full(beta, gamma, idx), I[idx])[0,1]**2
            if best is None or r > best[0]: best = (r, beta, gamma)
    r0, b0, g0 = best
    for beta in np.arange(max(0,b0-3), b0+3.1, .5):
        for gamma in np.arange(g0-6, g0+6.1, 1.):
            r = np.corrcoef(poa_full(beta, gamma, idx_all), I[idx_all])[0,1]**2
            if r > best[0]: best = (r, beta, gamma)
    geom[k] = best
    az = best[2]
    print("     tilt %.1f deg, azimuth %.1f = %.0f deg %s of north, R2 %.4f"
          % (best[1], az, abs(az-180), "east" if az > 180 else "west", best[0]))

# ---- capacity from the fitted geometry ----
print("\n--- DC capacity, from clear high-irradiance intervals ---")
cap = {}
POA = {}
for k in (1,2):
    POA[k] = poa_full(geom[k][1], geom[k][2])
    P = (df["corrente_cc_mpp%d_A"%k].values*df["voltagem_cc_mpp%d_V"%k].values).astype(float)
    m = (POA[k] > 850) & np.isfinite(P) & (Kt_d >= .60) & (P > 100)
    stc = P[m]/(POA[k][m]/1000.)            # DC power normalised to 1000 W/m2
    cap[k] = np.nanpercentile(stc, 98)
    print("  MPP%d  n=%6d   P@1000W/m2: p50 %5.0f  p90 %5.0f  p98 %5.0f  p99.9 %5.0f W"
          % (k, m.sum(), np.nanpercentile(stc,50), np.nanpercentile(stc,90),
             np.nanpercentile(stc,98), np.nanpercentile(stc,99.9)))
tot = (cap[1]+cap[2])/1000
print("  estimate: MPP1 %.2f kWp, MPP2 %.2f kWp, total %.2f kWp" % (cap[1]/1000, cap[2]/1000, tot))
print("  workbook divisor 12.000 kWp -> %s by %.0f %%"
      % ("understates yield" if tot < 12 else "overstates yield", abs(100*(12.0/tot-1))))
print("  (the p98 of temperature-depressed field power understates nameplate by roughly")
print("   the thermal loss, so treat this as a lower bound on the installed DC capacity)")

out = pd.DataFrame(dict(timestamp=t.values, date=dates, year=t.dt.year.values, month=t.dt.month.values,
    doy=doy, hour=hour, solar_time=solar_time, omega=omega, decl=decl, elev=elev, cosz=cosz,
    p_ac=df.producao_fotovoltaica_Wh.values*12., fp=df.fator_potencia.values,
    va=df.potencia_aparente_VA.values, d_Kt=Kt_d, d_H=GHI_d))
for k in (1,2):
    out["i%d"%k] = df["corrente_cc_mpp%d_A"%k].values
    out["v%d"%k] = df["voltagem_cc_mpp%d_V"%k].values
    out["pdc%d"%k] = out["i%d"%k]*out["v%d"%k]
    out["p%d"%k] = df["energia_mpp%d_Wh"%k].values*12.
    out["poa%d"%k] = POA[k]
    out["pi%d"%k] = np.where(POA[k] > 50, out["pdc%d"%k]/(cap[k]*POA[k]/1000.), np.nan)
    out["in%d"%k] = np.where(POA[k] > 50, out["i%d"%k]/(POA[k]/1000.), np.nan)
out["poa_cs"] = (out.poa1*cap[1] + out.poa2*cap[2])/(cap[1]+cap[2])
out["pi"] = np.where(out.poa_cs > 50, out.p_ac/((cap[1]+cap[2])*out.poa_cs/1000.), np.nan)

keep = ["ALLSKY_SFC_SW_DWN","ALLSKY_KT","T2M","T2M_MAX","RH2M","WS2M","PRECTOTCORR",
        "CLOUD_AMT","AOD_55","ALLSKY_SFC_SW_DIFF"]
out = out.merge(D[keep].rename(columns={c:"d_"+c for c in keep}), left_on="date", right_index=True, how="left")
H = pd.read_csv(caminho("nasa_power_curitiba_hourly.csv"), index_col=0, parse_dates=True)
key = (pd.to_datetime(out.timestamp) + pd.Timedelta(minutes=-55)).dt.floor("h")
hc = ["ALLSKY_SFC_SW_DWN","CLRSKY_SFC_SW_DWN","ALLSKY_SFC_SW_DNI","T2M","WS2M","CLOUD_AMT"]
out = out.join(H[hc].add_prefix("h_").reindex(key).set_index(out.index))
out["h_kc"] = (out.h_ALLSKY_SFC_SW_DWN/out.h_CLRSKY_SFC_SW_DWN.replace(0,np.nan)).clip(0,1.3)

out.to_parquet(caminho("curitiba_frame5.parquet"), index=False, compression="zstd")
json.dump(dict(lat=LAT, lon=LON, kw_ac=12.0, workbook_divisor=12.0,
    cap_mpp1_kwp=cap[1]/1000, cap_mpp2_kwp=cap[2]/1000, cap_total_kwp=tot,
    geom_mpp1=dict(tilt=geom[1][1], azimuth=geom[1][2], r2=geom[1][0]),
    geom_mpp2=dict(tilt=geom[2][1], azimuth=geom[2][2], r2=geom[2][0]),
    n_rows=int(len(out))), open(caminho("curitiba_meta.json"),"w"), indent=1)
print("\nwrote curitiba_frame5.parquet", out.shape)
q = out[(out.poa_cs > 300) & (out.cosz > .15) & out.p_ac.notna()]
print("high-irradiance PI: median %.3f  (MPP1 %.3f, MPP2 %.3f)  n=%d"
      % (q.pi.median(), q.pi1.median(), q.pi2.median(), len(q)))
