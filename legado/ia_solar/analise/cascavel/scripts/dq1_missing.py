# -*- coding: utf-8 -*-
"""Data quality, part 1: missingness, the time grid, duplicates."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd

RAW = pd.read_csv(caminho("dados_5min_2019-2026.csv"), dtype=str, keep_default_na=False)
CH = ["corrente_ca_l1_A","corrente_cc_mpp1_A","energia_Wh","fator_potencia",
      "potencia_aparente_VA","potencia_reativa_VAr","rendimento_especifico_kWh_kWp",
      "voltagem_ca_l1_V","voltagem_cc_mpp1_V","producao_fotovoltaica_Wh"]
print("raw rows: %d" % len(RAW))

# ---------- 1. what does "n/a" actually mean? ----------
f = pd.read_parquet(caminho("frame5.parquet"))
f["ts"] = pd.to_datetime(f.timestamp)
f["night"] = f.cosz <= 0
na = f.producao_fotovoltaica_Wh.isna() if "producao_fotovoltaica_Wh" in f else f.p_ac.isna()
print("\n--- is missingness just night-time? ---")
tab = pd.crosstab(f.p_ac.isna(), f.night, rownames=["p_ac missing"], colnames=["sun below horizon"])
print(tab.to_string())
day_missing = int(((f.p_ac.isna()) & (~f.night)).sum())
day_total = int((~f.night).sum())
print("\n  missing during DAYLIGHT : %d of %d  (%.2f %%)" % (day_missing, day_total, 100*day_missing/day_total))
print("  missing at NIGHT        : %d of %d  (%.2f %%)"
      % (int((f.p_ac.isna()&f.night).sum()), int(f.night.sum()), 100*(f.p_ac.isna()&f.night).mean()))
print("  -> night rows are logged but carry no measurement; that is the bulk of the 36%")

print("\n--- per-channel missingness, daylight only ---")
d = f[~f.night]
for c in ["p_ac","p_dc","i_dc","v_dc","i_ac","v_ac","fp","va"]:
    n = int(d[c].isna().sum())
    print("  %-6s %7d  %.3f %%" % (c, n, 100*n/len(d)))
print("\n  note: v_ac is missing more often than the DC channels -- the inverter reports")
print("  grid voltage only while exporting, so it drops out at the margins of the day")

# ---------- 2. the time grid ----------
print("\n--- completeness of the 5-minute grid ---")
t = f.ts.sort_values()
full = pd.date_range(t.min(), t.max(), freq="5min")
print("  first record : %s" % t.min())
print("  last record  : %s" % t.max())
print("  expected slots on a full 5-min grid : %d" % len(full))
print("  rows present                        : %d  (%.1f %%)" % (len(f), 100*len(f)/len(full)))
print("  -> the export is daylight-only, so a 'complete' grid is the wrong yardstick")

# calendar-day coverage is the meaningful test
days = pd.Series(sorted(set(f.ts.dt.date)))
alldays = pd.date_range(t.min().date(), t.max().date(), freq="D").date
missing_days = sorted(set(alldays) - set(days))
print("\n  calendar days spanned : %d" % len(alldays))
print("  days with any record  : %d" % len(days))
print("  days entirely absent  : %d" % len(missing_days))
if missing_days:
    print("    %s" % ", ".join(str(x) for x in missing_days[:12]))

# intraday gaps: consecutive records more than 5 min apart, within a day
f2 = f.sort_values("ts").copy()
f2["gap"] = f2.ts.diff().dt.total_seconds()/60
f2["same_day"] = f2.ts.dt.date == f2.ts.shift().dt.date
intraday = f2[(f2.same_day) & (f2.gap > 5.5)]
print("\n  intraday gaps larger than one interval : %d" % len(intraday))
print("  total time lost to them                : %.1f hours" % ((intraday.gap-5).sum()/60))
g = intraday.gap
print("  gap length distribution (minutes):")
print("    median %.0f | p90 %.0f | max %.0f" % (g.median(), g.quantile(.9), g.max()))
print("  worst 5 gaps:")
for _, r in intraday.nlargest(5, "gap").iterrows():
    print("    %s  %.0f min" % (r.ts, r.gap))

# records per day: partial days
rpd = f.groupby(f.ts.dt.date).size()
print("\n  records per day: median %d, p05 %d, min %d" % (rpd.median(), rpd.quantile(.05), rpd.min()))
short = rpd[rpd < rpd.median()*0.5]
print("  days with under half the median record count : %d" % len(short))
print("    %s" % ", ".join("%s(%d)" % (d, n) for d, n in short.head(8).items()))

# ---------- 3. duplicates ----------
print("\n--- duplicate timestamps at the annual file boundaries ---")
raw = RAW.copy()
dup_mask = raw.duplicated(subset=["timestamp"], keep=False) & (raw.timestamp != "")
dups = raw[dup_mask]
print("  rows involved : %d  (%d distinct timestamps)" % (len(dups), dups.timestamp.nunique()))
conflict = 0; identical = 0
for ts, grp in dups.groupby("timestamp"):
    vals = grp[CH].drop_duplicates()
    if len(vals) == 1: identical += 1
    else: conflict += 1
print("  timestamps whose duplicate rows AGREE exactly : %d" % identical)
print("  timestamps whose rows DISAGREE               : %d" % conflict)
print("  -> %s" % ("safe to drop either copy" if conflict == 0
                   else "a de-duplication rule has to pick a side"))
if conflict:
    for ts, grp in dups.groupby("timestamp"):
        if len(grp[CH].drop_duplicates()) > 1:
            print("\n  example conflict at %s:" % ts)
            print(grp[["arquivo"]+CH[:5]].to_string(index=False))
            break
