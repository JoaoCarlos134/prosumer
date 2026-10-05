# -*- coding: utf-8 -*-
"""Compact column-oriented JSON payload for the interactive explorer."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json

df  = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start", "end"])
meta = json.load(open(caminho("meta.json")))
bill = pd.read_csv(caminho("billing.csv"), index_col=0, parse_dates=True)
bann = pd.read_csv(caminho("billing_annual.csv"), index_col=0)

# regime id per day
df["regime"] = -1
for i, s in seg.iterrows():
    m = (df.index >= s.start) & (df.index <= s.end + pd.offsets.MonthEnd(1))
    df.loc[m, "regime"] = i
df = df[df.regime >= 0]

DRIVERS = [
 # key, label, unit, group, decimals
 ("poa",            "Plane-of-array irradiation", "kWh/m²·d", "Irradiance", 3),
 ("H",              "Global horizontal irradiation", "kWh/m²·d", "Irradiance", 3),
 ("Kt",             "Clearness index", "", "Irradiance", 4),
 ("Kc",             "Clear-sky index", "", "Irradiance", 4),
 ("kd",             "Diffuse fraction", "", "Irradiance", 4),
 ("poa_diff",       "Diffuse POA component", "kWh/m²·d", "Irradiance", 3),
 ("tr_gain",        "Transposition gain POA/GHI", "", "Irradiance", 4),
 ("tcell",          "Modelled cell temperature", "°C", "Thermal", 2),
 ("T2M",            "Air temperature", "°C", "Thermal", 2),
 ("T2M_MAX",        "Daily max air temperature", "°C", "Thermal", 2),
 ("T2M_MIN",        "Daily min air temperature", "°C", "Thermal", 2),
 ("dT",             "Diurnal temperature range", "K", "Thermal", 2),
 ("TS",             "Ground / skin temperature", "°C", "Thermal", 2),
 ("RH2M",           "Relative humidity", "%", "Humidity", 2),
 ("dewdep",         "Dew-point depression", "K", "Humidity", 2),
 ("T2MDEW",         "Dew point", "°C", "Humidity", 2),
 ("WS2M",           "Wind speed @2 m", "m/s", "Wind", 2),
 ("WS10M",          "Wind speed @10 m", "m/s", "Wind", 2),
 ("PRECTOTCORR",    "Precipitation", "mm/d", "Rain & soiling", 2),
 ("dry_days",       "Consecutive dry days", "d", "Rain & soiling", 0),
 ("rain_7d",        "Rain, trailing 7 d", "mm", "Rain & soiling", 1),
 ("rain_30d",       "Rain, trailing 30 d", "mm", "Rain & soiling", 1),
 ("CLOUD_AMT",      "Cloud amount", "%", "Sky", 2),
 ("AOD_55",         "Aerosol optical depth 550 nm", "", "Sky", 3),
 ("ALLSKY_SRF_ALB", "Surface albedo", "", "Sky", 3),
 ("uv_ratio",       "UVA / GHI (spectral proxy)", "", "Sky", 5),
 ("airmass",        "Air mass (irradiance-weighted)", "", "Geometry", 3),
 ("cos_inc",        "cos(incidence angle)", "", "Geometry", 4),
 ("daylength",      "Day length", "h", "Geometry", 3),
 ("PS",             "Surface pressure", "kPa", "Sky", 2),
]
TARGETS = [
 ("pr_tcorr", "Temp-corrected PR", "", 4),
 ("pr",       "Performance ratio", "", 4),
 ("yield_sp", "Specific yield", "kWh/kWp·d", 3),
 ("e_kwh",    "Daily energy", "kWh", 2),
]

start = df.index.min()
cols = {"d": [int(x) for x in (df.index - start).days]}

def pack(key, dec):
    v = pd.to_numeric(df[key], errors="coerce").values.astype(float)
    out = []
    for x in v:
        out.append(None if not np.isfinite(x) else (int(round(x)) if dec == 0 else round(float(x), dec)))
    return out

for k, _, _, _, dec in DRIVERS: cols[k] = pack(k, dec)
for k, _, _, dec in TARGETS:    cols[k] = pack(k, dec)
cols["regime"] = [int(x) for x in df.regime.values]

segments = [dict(i=int(i), start=str(s.start.date()), end=str((s.end + pd.offsets.MonthEnd(1)).date()),
                 label="%s–%s" % (s.start.strftime("%b %y"), s.end.strftime("%b %y")),
                 pr=round(float(s.pr), 3), months=int(s.months),
                 healthy=bool(s.pr >= 0.82), lost=round(float(s.E_lost)), lost_pct=round(float(s.lost_pct), 1))
            for i, s in seg.iterrows()]

b = bill[bill.consumo.notna() & (bill.index.year <= 2024)]
monthly = dict(
    d=[str(x.date()) for x in b.index],
    geracao=[None if not np.isfinite(x) else round(float(x), 1) for x in b.geracao],
    consumo=[None if not np.isfinite(x) else round(float(x), 1) for x in b.consumo],
    injetado=[None if not np.isfinite(x) else round(float(x), 1) for x in b.injetado],
    pago=[None if not np.isfinite(x) else round(float(x), 2) for x in b.pago],
)
annual = dict(
    year=[int(x) for x in bann.index if x <= 2024],
    pago=[round(float(bann.loc[y, "pago"]), 2) for y in bann.index if y <= 2024],
    consumo=[round(float(bann.loc[y, "consumo"]), 1) for y in bann.index if y <= 2024],
    geracao=[round(float(bann.loc[y, "geracao"]), 1) for y in bann.index if y <= 2024],
    saldo=[None if not np.isfinite(bann.loc[y, "saldo_fim"]) else round(float(bann.loc[y, "saldo_fim"]))
           for y in bann.index if y <= 2024],
    tarifa=[round(float(bann.loc[y, "tarifa"]), 3) for y in bann.index if y <= 2024],
)

payload = dict(
    start=str(start.date()), n=len(df),
    meta={k: meta[k] for k in ("kwp", "kw_ac", "tilt", "azimuth", "lat", "lon")},
    drivers=[dict(k=k, label=l, unit=u, group=g) for k, l, u, g, _ in DRIVERS],
    targets=[dict(k=k, label=l, unit=u) for k, l, u, _ in TARGETS],
    segments=segments, cols=cols, monthly=monthly, annual=annual,
)
js = json.dumps(payload, separators=(",", ":"))
open(caminho("payload.json"), "w").write(js)
print("payload %.0f KB  rows=%d  drivers=%d" % (len(js) / 1024, len(df), len(DRIVERS)))

# explorador interativo: o payload entra no lugar do marcador do template
tpl = open(pathlib.Path(__file__).with_name("explorer_tpl.html"), encoding="utf-8").read()
html = tpl.replace("/*__PAYLOAD__*/", js)
open(str(pathlib.Path(caminho("report.html")).with_name("explorador.html")), "w", encoding="utf-8").write(html)
