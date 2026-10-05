# -*- coding: utf-8 -*-
"""NASA POWER hourly point data, local solar time, for the whole plant record."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import truststore; truststore.inject_into_ssl()
import requests, pandas as pd, sys, time, json

LAT, LON = -24.83, -53.65
URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

CANDIDATES = ["ALLSKY_SFC_SW_DWN","CLRSKY_SFC_SW_DWN","ALLSKY_SFC_SW_DNI","ALLSKY_SFC_SW_DIFF",
              "ALLSKY_KT","TOA_SW_DWN","ALLSKY_SFC_PAR_TOT","CLRSKY_SFC_PAR_TOT",
              "T2M","T2MDEW","RH2M","WS2M","WS10M","PS","PRECTOTCORR","QV2M","T2MWET",
              "ALLSKY_SRF_ALB","AOD_55","CLOUD_AMT"]

def probe(p):
    r = requests.get(URL, params={"parameters":p,"community":"RE","longitude":LON,"latitude":LAT,
        "start":"20250801","end":"20250802","format":"JSON","time-standard":"LST"}, timeout=90)
    return r.status_code == 200

print("probing hourly parameter availability ...")
good = []
for c in CANDIDATES:
    ok = probe(c)
    print("   %-22s %s" % (c, "ok" if ok else "NOT AVAILABLE HOURLY"))
    if ok: good.append(c)
print("\nusable: %d parameters" % len(good))

# POWER caps the parameter count per request, so fetch in groups
GROUPS = [good[i:i+10] for i in range(0, len(good), 10)]
YEARS = [("20190726","20200725"),("20200726","20210725"),("20210726","20220725"),
         ("20220726","20230725"),("20230726","20240725"),("20240726","20250725"),
         ("20250726","20260726")]

frames = []
for gi, grp in enumerate(GROUPS):
    parts = []
    for s, e in YEARS:
        for attempt in range(3):
            try:
                r = requests.get(URL, params={"parameters":",".join(grp),"community":"RE",
                    "longitude":LON,"latitude":LAT,"start":s,"end":e,
                    "format":"JSON","time-standard":"LST"}, timeout=300)
                if r.status_code == 200: break
                print("   %s-%s status %d: %s" % (s, e, r.status_code, r.text[:200]), file=sys.stderr)
            except Exception as ex:
                print("   retry %s-%s: %s" % (s, e, ex), file=sys.stderr); time.sleep(4)
        else:
            sys.exit("failed on %s-%s" % (s, e))
        d = pd.DataFrame(r.json()["properties"]["parameter"])
        parts.append(d)
        print("  group %d  %s-%s  %d rows" % (gi, s, e, len(d)), flush=True)
    frames.append(pd.concat(parts))

H = pd.concat(frames, axis=1)
H = H[~H.index.duplicated(keep="first")].sort_index()
H.index = pd.to_datetime(H.index, format="%Y%m%d%H")
H.index.name = "lst"
H = H.replace(-999.0, pd.NA)
H.to_csv(caminho("nasa_power_hourly.csv"))
print("\nhourly frame:", H.shape, H.index.min(), "->", H.index.max())
print(H.isna().mean().round(4).to_string())
print(H.describe().T.round(2).to_string())
