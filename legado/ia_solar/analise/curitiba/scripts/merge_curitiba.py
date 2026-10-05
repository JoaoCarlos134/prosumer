# -*- coding: utf-8 -*-
"""Merge the five Usina Curitiba annual exports into one file. Same contract as the
Cascavel merge: no cleaning, values written exactly as stored, provenance added."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import csv, glob, os, sys
from datetime import datetime
import openpyxl

SRC = sorted(glob.glob(caminho("curitiba/*.xlsx")))
OUT = caminho("curitiba_5min_2021-2026.csv")

COLS = [
 ("data_hora_raw",                 "Data e horário",        "dd.MM.yyyy HH:mm"),
 ("corrente_ca_l1_A",              "Corrente CA L1",        "A"),
 ("corrente_ca_l2_A",              "Corrente CA L2",        "A"),
 ("corrente_ca_l3_A",              "Corrente CA L3",        "A"),
 ("corrente_cc_mpp1_A",            "Corrente CC MPP1",      "A"),
 ("corrente_cc_mpp2_A",            "Corrente CC MPP2",      "A"),
 ("energia_Wh",                    "Energia",               "Wh"),
 ("energia_mpp1_Wh",               "Energia MPP1",          "Wh"),
 ("energia_mpp2_Wh",               "Energia MPP2",          "Wh"),
 ("fator_potencia",                "Fator de potência",     "1"),
 ("potencia_aparente_VA",          "Potência aparente",     "VA"),
 ("potencia_reativa_VAr",          "Potência reativa",      "VAr"),
 ("rendimento_especifico_kWh_kWp", "Rendimento específico", "kWh/kWp"),
 ("voltagem_ca_l1_V",              "Voltagem CA L1",        "V"),
 ("voltagem_ca_l2_V",              "Voltagem CA L2",        "V"),
 ("voltagem_ca_l3_V",              "Voltagem CA L3",        "V"),
 ("voltagem_cc_mpp1_V",            "Voltagem CC MPP1",      "V"),
 ("voltagem_cc_mpp2_V",            "Voltagem CC MPP2",      "V"),
 ("producao_fotovoltaica_Wh",      "Produção fotovoltaica", "Wh"),
]
NC = len(COLS)
HEADER = ["timestamp"] + [c[0] for c in COLS] + ["arquivo", "planilha"]

def cell(v):
    if v is None: return ""
    if isinstance(v, datetime): return v.strftime("%d.%m.%Y %H:%M")
    return str(v)

def parse_ts(s):
    s = s.strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(s, fmt)
        except ValueError: pass
    return None

total = unparsed = dupes = extra_nonempty = 0
seen = set()
with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(HEADER)
    for path in SRC:
        base = os.path.basename(path)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            n = 0; tmin = tmax = None
            for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if r <= 2: continue
                if row is None or all(v is None for v in row[:NC]): continue
                if len(row) > NC and any(v is not None and str(v).strip() != "" for v in row[NC:]):
                    extra_nonempty += 1
                vals = [cell(v) for v in row[:NC]]
                ts = parse_ts(vals[0])
                if ts is None: unparsed += 1; iso = ""
                else:
                    iso = ts.strftime("%Y-%m-%d %H:%M:%S")
                    tmin = ts if tmin is None or ts < tmin else tmin
                    tmax = ts if tmax is None or ts > tmax else tmax
                    if iso in seen: dupes += 1
                    else: seen.add(iso)
                w.writerow([iso] + vals + [base, ws.title]); n += 1
            total += n
            print("  %-42s %-10s %7d rows  %s -> %s"
                  % (base, ws.title, n,
                     tmin.strftime("%Y-%m-%d %H:%M") if tmin else "?",
                     tmax.strftime("%Y-%m-%d %H:%M") if tmax else "?"), flush=True)
        wb.close()

with open(caminho("colunas_curitiba.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["coluna","cabecalho_original","unidade"])
    w.writerow(["timestamp","(derivado de 'Data e horário')","ISO 8601, hora local"])
    for s_, o, u in COLS:
        w.writerow([s_, o + (" | Symo 12.0-3 208-240 (1)" if s_ != "data_hora_raw" else ""), u])
    w.writerow(["arquivo","(proveniência)",""]); w.writerow(["planilha","(proveniência)",""])

print("\ntotal rows           : %d" % total)
print("unparsed timestamps  : %d" % unparsed)
print("duplicate timestamps : %d" % dupes)
print("cells beyond col %-2d  : %d" % (NC, extra_nonempty))
print("output               : %s  (%.1f MB)" % (OUT, os.path.getsize(OUT)/1e6))

# espelho parquet, que e o que o resto do pipeline le (identico ao CSV, so tipado)
import pandas as pd
TXT = ["data_hora_raw", "arquivo", "planilha"]
d = pd.read_csv(OUT, dtype={k: str for k in TXT}, keep_default_na=False, na_values={k: [] for k in TXT})
d["timestamp"] = pd.to_datetime(d["timestamp"])
num = [k for k in d.columns if k not in TXT + ["timestamp"]]
d[num] = d[num].apply(pd.to_numeric, errors="coerce").astype(float)
d.to_parquet(caminho("curitiba_5min.parquet"), index=False, compression="zstd")
print("parquet              : %s  %s" % (caminho("curitiba_5min.parquet"), d.shape))
