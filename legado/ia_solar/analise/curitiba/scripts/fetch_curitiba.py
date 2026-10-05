import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import truststore; truststore.inject_into_ssl()
import requests, pandas as pd, sys, time, json
LAT, LON = -25.4284, -49.2733          # Curitiba-PR
DU = "https://power.larc.nasa.gov/api/temporal/daily/point"
HU = "https://power.larc.nasa.gov/api/temporal/hourly/point"
START, END = "20210717", "20260717"

GD = ["ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,ALLSKY_KT,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,TOA_SW_DWN",
      "T2M,T2M_MAX,T2M_MIN,T2MDEW,RH2M,WS2M,WS10M,PS,PRECTOTCORR",
      "CLOUD_AMT,ALLSKY_SRF_ALB,AOD_55,ALLSKY_SFC_UVA,ALLSKY_SFC_UVB,TS"]
frames, meta = [], {}
for i, p in enumerate(GD):
    r = requests.get(DU, params={"parameters":p,"community":"RE","longitude":LON,"latitude":LAT,
        "start":START,"end":END,"format":"JSON"}, timeout=240)
    print("daily group", i, r.status_code, file=sys.stderr)
    if r.status_code != 200: sys.exit(r.text[:400])
    j = r.json()
    if i == 0: meta["geometry"] = j.get("geometry")
    d = pd.DataFrame(j["properties"]["parameter"]); d.index = pd.to_datetime(d.index, format="%Y%m%d")
    frames.append(d)
D = pd.concat(frames, axis=1).sort_index().replace(-999.0, pd.NA)
D.index.name = "data"; D.to_csv(caminho("nasa_power_curitiba_daily.csv"))
json.dump(meta, open(caminho("nasa_power_curitiba_meta.json"),"w"), indent=1)
print("daily:", D.shape, meta["geometry"])

HP = ["ALLSKY_SFC_SW_DWN","CLRSKY_SFC_SW_DWN","ALLSKY_SFC_SW_DNI","ALLSKY_SFC_SW_DIFF",
      "ALLSKY_KT","TOA_SW_DWN","T2M","T2MDEW","RH2M","WS2M","WS10M","PS","PRECTOTCORR",
      "QV2M","ALLSKY_SRF_ALB","AOD_55","CLOUD_AMT"]
YEARS = [("20210717","20220716"),("20220717","20230716"),("20230717","20240716"),
         ("20240717","20250716"),("20250717","20260717")]
groups = [HP[i:i+10] for i in range(0,len(HP),10)]
hf = []
for gi, grp in enumerate(groups):
    parts = []
    for s,e in YEARS:
        for _ in range(3):
            try:
                r = requests.get(HU, params={"parameters":",".join(grp),"community":"RE",
                    "longitude":LON,"latitude":LAT,"start":s,"end":e,"format":"JSON",
                    "time-standard":"LST"}, timeout=300)
                if r.status_code == 200: break
                print("  ", s, e, r.status_code, r.text[:150], file=sys.stderr)
            except Exception as ex:
                print("  retry", ex, file=sys.stderr); time.sleep(4)
        else: sys.exit("failed %s-%s" % (s,e))
        d = pd.DataFrame(r.json()["properties"]["parameter"]); parts.append(d)
        print("  hourly g%d %s-%s %d" % (gi,s,e,len(d)), flush=True)
    hf.append(pd.concat(parts))
H = pd.concat(hf, axis=1)
H = H[~H.index.duplicated(keep="first")].sort_index()
H.index = pd.to_datetime(H.index, format="%Y%m%d%H"); H.index.name = "lst"
H = H.replace(-999.0, pd.NA)
H.to_csv(caminho("nasa_power_curitiba_hourly.csv"))
print("hourly:", H.shape, H.index.min(), "->", H.index.max())
