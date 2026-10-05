# -*- coding: utf-8 -*-
"""Concatenate the seven annual 5-minute inverter exports into one file.

NO data cleaning: every value is written exactly as it appears in the workbook,
including "n/a" strings, zeros and any duplicated timestamps at the file
boundaries. The only additions are a parsed `timestamp` column and two
provenance columns; the original date string is kept verbatim alongside.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import csv, glob, os, sys
from datetime import datetime
import openpyxl

SRC = sorted(glob.glob(caminho("minuto/*.xlsx")))
OUT = caminho("dados_5min_2019-2026.csv")

COLS = [
    ("data_hora_raw",                 "Data e horário",        "dd.MM.yyyy HH:mm"),
    ("corrente_ca_l1_A",              "Corrente CA L1",        "A"),
    ("corrente_cc_mpp1_A",            "Corrente CC MPP1",      "A"),
    ("energia_Wh",                    "Energia",               "Wh"),
    ("fator_potencia",                "Fator de potência",     "1"),
    ("potencia_aparente_VA",          "Potência aparente",     "VA"),
    ("potencia_reativa_VAr",          "Potência reativa",      "VAr"),
    ("rendimento_especifico_kWh_kWp", "Rendimento específico", "kWh/kWp"),
    ("voltagem_ca_l1_V",              "Voltagem CA L1",        "V"),
    ("voltagem_cc_mpp1_V",            "Voltagem CC MPP1",      "V"),
    ("producao_fotovoltaica_Wh",      "Produção fotovoltaica", "Wh"),
]
HEADER = ["timestamp"] + [c[0] for c in COLS] + ["arquivo", "planilha"]

def cell(v):
    """Render a cell exactly as stored, without coercing or normalising."""
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d.%m.%Y %H:%M")
    return str(v)

def parse_ts(s):
    s = s.strip()
    for f in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    return None

total = 0
unparsed = 0
per_file = []
seen = {}
dupes = 0
col12_nonempty = 0

with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(HEADER)
    for path in SRC:
        base = os.path.basename(path)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            n = 0
            tmin = tmax = None
            for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if r <= 2:                      # the two header rows
                    continue
                if row is None or all(v is None for v in row[:11]):
                    continue
                if len(row) > 11 and row[11] is not None and str(row[11]).strip() != "":
                    col12_nonempty += 1
                vals = [cell(v) for v in row[:11]]
                ts = parse_ts(vals[0])
                if ts is None:
                    unparsed += 1
                    iso = ""
                else:
                    iso = ts.strftime("%Y-%m-%d %H:%M:%S")
                    if tmin is None or ts < tmin: tmin = ts
                    if tmax is None or ts > tmax: tmax = ts
                    if iso in seen:
                        dupes += 1
                    else:
                        seen[iso] = base
                w.writerow([iso] + vals + [base, ws.title])
                n += 1
            per_file.append((base, ws.title, n, tmin, tmax))
            total += n
            print("  %-40s %-10s %7d rows  %s -> %s"
                  % (base, ws.title, n,
                     tmin.strftime("%Y-%m-%d %H:%M") if tmin else "?",
                     tmax.strftime("%Y-%m-%d %H:%M") if tmax else "?"), flush=True)
        wb.close()

with open(caminho("colunas_5min.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["coluna", "cabecalho_original", "unidade"])
    w.writerow(["timestamp", "(derivado de 'Data e horário')", "ISO 8601, hora local"])
    for short, orig, unit in COLS:
        w.writerow([short, orig + " | Primo 4.0-1 (1)" if short != "data_hora_raw" else orig, unit])
    w.writerow(["arquivo", "(proveniência: arquivo de origem)", ""])
    w.writerow(["planilha", "(proveniência: aba de origem)", ""])

print("\ntotal rows          : %d" % total)
print("unparsed timestamps : %d" % unparsed)
print("duplicate timestamps: %d  (file-boundary overlap, kept as-is)" % dupes)
print("12th column non-empty: %d" % col12_nonempty)
print("output              : %s  (%.1f MB)" % (OUT, os.path.getsize(OUT) / 1e6))

# espelho parquet, que e o que o resto do pipeline le (identico ao CSV, so tipado)
import pandas as pd
TXT = ["data_hora_raw", "arquivo", "planilha"]
d = pd.read_csv(OUT, dtype={k: str for k in TXT}, keep_default_na=False, na_values={k: [] for k in TXT})
d["timestamp"] = pd.to_datetime(d["timestamp"])
num = [k for k in d.columns if k not in TXT + ["timestamp"]]
d[num] = d[num].apply(pd.to_numeric, errors="coerce").astype(float)
d.to_parquet(caminho("dados_5min_2019-2026.parquet"), index=False, compression="zstd")
print("parquet              : %s  %s" % (caminho("dados_5min_2019-2026.parquet"), d.shape))
