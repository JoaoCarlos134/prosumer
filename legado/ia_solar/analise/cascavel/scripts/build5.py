# -*- coding: utf-8 -*-
"""Build the 5-minute analysis frame: instantaneous solar geometry, clear-sky
reference, AC/DC power, inverter efficiency, merged with the daily NASA POWER record.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, solar

LAT, LON = -24.83, -53.65
TZ_MERIDIAN = -45.0          # UTC-3, no DST in Brazil since 2019
KWP, KW_AC = 3.96, 4.0
TILT, AZIM = 13.0, 205.0     # datasheet 25 deg EAST of north (D&B gamma; 180 = due north)
D2R = np.pi / 180

df = pd.read_parquet(caminho("dados_5min_2019-2026.parquet"))
df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
df = df[df.timestamp.notna()]
print("unique 5-min records:", len(df))

t = df.timestamp
doy = t.dt.dayofyear.values.astype(float)
hour = (t.dt.hour + t.dt.minute / 60.0).values

# ---- solar geometry (Spencer declination + equation of time) ----
B = 2 * np.pi * (doy - 1) / 365.0
decl = (0.006918 - 0.399912*np.cos(B) + 0.070257*np.sin(B)
        - 0.006758*np.cos(2*B) + 0.000907*np.sin(2*B)
        - 0.002697*np.cos(3*B) + 0.00148*np.sin(3*B)) / D2R
eot = 229.18 * (0.000075 + 0.001868*np.cos(B) - 0.032077*np.sin(B)
                - 0.014615*np.cos(2*B) - 0.040849*np.sin(2*B))
solar_time = hour + (4 * (LON - TZ_MERIDIAN) + eot) / 60.0
omega = 15.0 * (solar_time - 12.0)

cosz = (np.sin(decl*D2R)*np.sin(LAT*D2R) + np.cos(decl*D2R)*np.cos(LAT*D2R)*np.cos(omega*D2R))
cosz = np.clip(cosz, -1, 1)
elev = np.degrees(np.arcsin(cosz))
# solar azimuth, 0 = north, clockwise (compass)
sin_az = -np.cos(decl*D2R)*np.sin(omega*D2R)/np.maximum(np.cos(np.arcsin(cosz)), 1e-6)
cos_az = ((np.sin(decl*D2R) - np.sin(LAT*D2R)*cosz) /
          np.maximum(np.cos(LAT*D2R)*np.cos(np.arcsin(cosz)), 1e-6))
sol_az = (np.degrees(np.arctan2(np.clip(sin_az,-1,1), np.clip(cos_az,-1,1)))) % 360

cos_inc = solar.cos_incidence(LAT, decl, omega, TILT, AZIM)
cos_inc = np.clip(cos_inc, 0, None)

# ---- Haurwitz clear-sky GHI, Erbs split, HDKR transposition (instantaneous) ----
czp = np.clip(cosz, 0.01, None)
ghi_cs = np.where(cosz > 0, 1098.0 * czp * np.exp(-0.059 / czp), 0.0)
E0 = 1 + 0.033*np.cos(2*np.pi*doy/365.0)
I0 = 1367.0 * E0 * czp
kt = np.where(I0 > 0, ghi_cs / I0, 0)
kd = np.clip(np.where(kt <= .22, 1 - .09*kt,
             np.where(kt <= .8, .9511 - .1604*kt + 4.388*kt**2 - 16.638*kt**3 + 12.336*kt**4, .165)), 0, 1)
dif_cs = ghi_cs * kd
bea_cs = np.clip(ghi_cs - dif_cs, 0, None)
Rb = cos_inc / czp
Ai = np.clip(np.where(I0 > 0, bea_cs / I0, 0), 0, 1)
f = np.sqrt(np.where(ghi_cs > 0, bea_cs / ghi_cs, 0))
b2 = np.sin(TILT*D2R/2)**3
poa_cs = ((bea_cs + dif_cs*Ai)*Rb
          + dif_cs*(1-Ai)*((1+np.cos(TILT*D2R))/2)*(1 + f*b2)
          + ghi_cs*0.16*((1-np.cos(TILT*D2R))/2))
poa_cs = np.where(cosz > 0, np.clip(poa_cs, 0, None), 0.0)

# ---- electrical ----
e_wh = df.producao_fotovoltaica_Wh.values          # Wh per 5-min interval
p_ac = e_wh * 12.0                                  # W, interval mean
i_dc = df.corrente_cc_mpp1_A.values
v_dc = df.voltagem_cc_mpp1_V.values
p_dc = i_dc * v_dc
eta_inv = np.where(p_dc > 25, p_ac / np.where(p_dc > 0, p_dc, np.nan), np.nan)

out = pd.DataFrame(dict(
    timestamp=t.values, date=t.dt.date.values, year=t.dt.year.values, month=t.dt.month.values,
    doy=doy, hour=hour, solar_time=solar_time, omega=omega,
    decl=decl, elev=elev, sol_az=sol_az, cosz=cosz, cos_inc=cos_inc,
    poa_cs=poa_cs, p_ac=p_ac, p_dc=p_dc, i_dc=i_dc, v_dc=v_dc,
    e_wh=e_wh, fp=df.fator_potencia.values, va=df.potencia_aparente_VA.values,
    v_ac=df.voltagem_ca_l1_V.values, i_ac=df.corrente_ca_l1_A.values,
    eta_inv=eta_inv,
))
# performance index against the clear-sky reference
out["pi"] = np.where(out.poa_cs > 50, out.p_ac / (KWP * 1000 * out.poa_cs / 1000.0), np.nan)

# ---- merge the daily NASA POWER record ----
daily = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
daily.index = daily.index.date
keep = ["H","Kt","Kc","kd","poa","T2M","T2M_MAX","RH2M","WS2M","PRECTOTCORR",
        "CLOUD_AMT","AOD_55","tcell","pr","pr_tcorr","dry_days"]
out = out.merge(daily[keep].rename(columns={c: "d_"+c for c in keep}),
                left_on="date", right_index=True, how="left")

# regime labels
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])
out["regime"] = -1
ts = pd.to_datetime(out.timestamp)
for i, s in seg.iterrows():
    m = (ts >= s.start) & (ts <= s.end + pd.offsets.MonthEnd(1))
    out.loc[m, "regime"] = i
out["healthy"] = out.regime.map({i: bool(s.pr >= 0.82) for i, s in seg.iterrows()}).fillna(False)

out.to_parquet(caminho("frame5.parquet"), index=False, compression="zstd")
print("frame5.parquet written:", out.shape)
day = out[out.cosz > 0.05]
print("daylight records:", len(day))
print(day[["p_ac","p_dc","v_dc","i_dc","eta_inv","poa_cs","pi","elev"]].describe().round(3).to_string())
