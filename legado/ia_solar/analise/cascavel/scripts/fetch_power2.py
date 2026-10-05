import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import truststore; truststore.inject_into_ssl()
import requests, pandas as pd, json, sys

LAT, LON = -24.83, -53.65
START, END = "20190726", "20260911"
URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

GROUPS = [
    # irradiance / solar geometry
    "ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,ALLSKY_KT,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,TOA_SW_DWN",
    # meteorology
    "T2M,T2M_MAX,T2M_MIN,T2MDEW,RH2M,WS2M,WS10M,PS,PRECTOTCORR",
    # sky / surface
    "CLOUD_AMT,ALLSKY_SRF_ALB,AOD_55,ALLSKY_SFC_UVA,ALLSKY_SFC_UVB,TS",
]

frames = []
meta = {}
for i, params in enumerate(GROUPS):
    r = requests.get(URL, params={
        "parameters": params, "community": "RE",
        "longitude": LON, "latitude": LAT,
        "start": START, "end": END, "format": "JSON"}, timeout=180)
    print("group", i, r.status_code, file=sys.stderr)
    if r.status_code != 200:
        print(r.text[:500], file=sys.stderr); sys.exit(1)
    j = r.json()
    meta[f"group{i}"] = j.get("header", {})
    if i == 0:
        meta["geometry"] = j.get("geometry")
        meta["parameter_info"] = j.get("parameters", {})
    else:
        meta.setdefault("parameter_info", {}).update(j.get("parameters", {}))
    d = pd.DataFrame(j["properties"]["parameter"])
    d.index = pd.to_datetime(d.index, format="%Y%m%d")
    frames.append(d)

power = pd.concat(frames, axis=1).sort_index()
power.index.name = "data"
power = power.replace(-999.0, pd.NA)
power.to_csv(caminho("nasa_power_true.csv"))
json.dump(meta, open(caminho("nasa_power_true_meta.json"),"w"), indent=1)

print(power.shape)
print(power.isna().mean().round(4).to_string())
print(power.describe().T.to_string())
