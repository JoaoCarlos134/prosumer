# -*- coding: utf-8 -*-
"""Data quality for the Curitiba / Curitiba export, same checks as Cascavel."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json

raw = pd.read_csv(caminho("curitiba_5min_2021-2026.csv"), dtype=str, keep_default_na=False)
CH = [c for c in raw.columns if c not in ("timestamp","data_hora_raw","arquivo","planilha")]
df = pd.read_parquet(caminho("curitiba_5min.parquet"))
df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
u = df.drop_duplicates(subset=["timestamp"])
print("raw rows %d | unique timestamps %d" % (len(raw), len(u)))

# --- duplicates ---
dm = raw.duplicated(subset=["timestamp"], keep=False) & (raw.timestamp != "")
dd = raw[dm]
conf = sum(1 for _, g in dd.groupby("timestamp") if len(g[CH].drop_duplicates()) > 1)
print("\nduplicate timestamps: %d rows / %d distinct;  conflicting: %d"
      % (len(dd), dd.timestamp.nunique(), conf))

# --- calendar coverage ---
t = u.timestamp
days = pd.Series(sorted(set(t.dt.date)))
alld = pd.date_range(t.min().date(), t.max().date(), freq="D").date
miss = sorted(set(alld)-set(days))
print("\ncalendar days spanned %d | present %d | absent %d" % (len(alld), len(days), len(miss)))
if miss:
    print("  absent days: %s%s" % (", ".join(str(x) for x in miss[:15]), " ..." if len(miss)>15 else ""))

rpd = u.groupby(t.dt.date).size()
print("records/day: median %d  min %d" % (rpd.median(), rpd.min()))
print("days with <240 records: %d" % (rpd < 240).sum())
by_year = rpd.groupby(pd.to_datetime(rpd.index).year).agg(["median","min","size"])
print(by_year.to_string())

# intraday gaps
s = u.sort_values("timestamp").copy()
s["gap"] = s.timestamp.diff().dt.total_seconds()/60
s["same"] = s.timestamp.dt.date == s.timestamp.shift().dt.date
ig = s[s.same & (s.gap > 5.5)]
print("\nintraday gaps > 1 interval: %d   time lost %.1f h" % (len(ig), (ig.gap-5).sum()/60))
if len(ig):
    print(ig.nlargest(6,"gap")[["timestamp","gap"]].to_string(index=False))

# --- missingness by channel, daylight proxy ---
print("\nmissingness (share of rows where the channel is blank):")
for c in ["energia_Wh","producao_fotovoltaica_Wh","corrente_cc_mpp1_A","corrente_cc_mpp2_A",
          "voltagem_cc_mpp1_V","voltagem_cc_mpp2_V","voltagem_ca_l1_V","fator_potencia"]:
    print("  %-26s %6.2f %%" % (c, 100*u[c].isna().mean()))

# --- physical bounds ---
p_ac = u.producao_fotovoltaica_Wh*12
pdc1 = u.corrente_cc_mpp1_A*u.voltagem_cc_mpp1_V
pdc2 = u.corrente_cc_mpp2_A*u.voltagem_cc_mpp2_V
print("\noutliers against physical bounds:")
rules = [("AC power above the 12 kW inverter rating", p_ac > 12000),
         ("AC power above 110% of rating",            p_ac > 13200),
         ("negative values anywhere",                 (p_ac < 0)|(pdc1 < 0)|(pdc2 < 0)),
         ("power factor outside [0,1]",               (u.fator_potencia < 0)|(u.fator_potencia > 1)),
         ("MPP1 current>0 with voltage=0",            (u.corrente_cc_mpp1_A > .1)&(u.voltagem_cc_mpp1_V <= 0)),
         ("MPP2 current>0 with voltage=0",            (u.corrente_cc_mpp2_A > .1)&(u.voltagem_cc_mpp2_V <= 0)),
         ("one string dead while the other produces", ((pdc1 < 20)&(pdc2 > 800))|((pdc2 < 20)&(pdc1 > 800)))]
for lab, m in rules:
    n = int(m.fillna(False).sum())
    print("  %-44s %6d  %.4f %%" % (lab, n, 100*n/len(u)))

# --- leakage / redundancy ---
print("\nredundant channels (leakage if the target is energy):")
r1 = u.dropna(subset=["energia_Wh","rendimento_especifico_kWh_kWp","producao_fotovoltaica_Wh",
                      "energia_mpp1_Wh","energia_mpp2_Wh"])
print("  rendimento x 12000 vs energia_Wh   : max|d| %.4f Wh" %
      (r1.rendimento_especifico_kWh_kWp*12000 - r1.energia_Wh).abs().max())
print("  energia vs producao_fotovoltaica   : max|d| %.4f Wh" %
      (r1.energia_Wh - r1.producao_fotovoltaica_Wh).abs().max())
print("  MPP1+MPP2 energy vs total energia  : max|d| %.4f Wh, r=%.8f" %
      ((r1.energia_mpp1_Wh + r1.energia_mpp2_Wh - r1.energia_Wh).abs().max(),
       np.corrcoef(r1.energia_mpp1_Wh+r1.energia_mpp2_Wh, r1.energia_Wh)[0,1]))
x = u.dropna(subset=["potencia_aparente_VA","fator_potencia","producao_fotovoltaica_Wh"])
ok = x.potencia_aparente_VA > 0
print("  aparente x fp vs AC power          : r=%.6f" %
      np.corrcoef((x.potencia_aparente_VA*x.fator_potencia)[ok], (x.producao_fotovoltaica_Wh*12)[ok])[0,1])

json.dump(dict(rows_raw=len(raw), rows_unique=int(len(u)), dup_rows=int(len(dd)),
               dup_conflicts=int(conf), days_absent=len(miss),
               intraday_gaps=int(len(ig)), gap_hours=float((ig.gap-5).sum()/60)),
          open(caminho("curitiba_dq.json"),"w"), indent=1)
