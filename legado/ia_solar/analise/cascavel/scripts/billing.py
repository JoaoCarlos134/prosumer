# -*- coding: utf-8 -*-
"""Economic layer: consumption, injection, credits and payments from 'Fatura de energia.xlsx'."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json

x = pd.ExcelFile(caminho("fatura.xlsx"))
f = x.parse("Fatura", header=None)

MONTHS = list(range(1, 13))
rows = {}
cur = None
for i in range(4, 38):
    yr, lbl = f.iloc[i, 0], f.iloc[i, 1]
    if pd.notna(yr): cur = int(yr)
    if pd.isna(lbl) or cur is None: continue
    key = str(lbl).split("[")[0].strip()
    vals = pd.to_numeric(f.iloc[i, 2:14], errors="coerce").values
    rows.setdefault(cur, {})[key] = vals
    if key == "Crédito":
        rows[cur]["saldo_fim_ano"] = pd.to_numeric(f.iloc[i, 14], errors="coerce")

recs = []
for yr, d in rows.items():
    for j, mo in enumerate(MONTHS):
        recs.append(dict(year=yr, month=mo, date=pd.Timestamp(yr, mo, 1),
                         consumo=d.get("Consumo", [np.nan]*12)[j],
                         injetado=d.get("Injetado", [np.nan]*12)[j],
                         pago=d.get("Pagamento", [np.nan]*12)[j],
                         credito=d.get("Crédito", [np.nan]*12)[j],
                         expirar=d.get("Expirar", [np.nan]*12)[j]))
B = pd.DataFrame(recs).set_index("date").sort_index()

# generation from the daily series
g = pd.read_excel(caminho("serie.xlsx")); g.columns = ["data", "e", "ek", "et"]
B["geracao"] = g.set_index("data").e.resample("MS").sum().reindex(B.index)

B["autoconsumo"] = B.geracao - B.injetado            # generated and used on site
B["import_rede"] = B.consumo - B.autoconsumo         # drawn from the grid
B["tarifa_efetiva"] = B.pago / B.consumo
B.to_csv(caminho("billing.csv"))

Y = B.groupby("year").agg(consumo=("consumo", "sum"), injetado=("injetado", "sum"),
                          pago=("pago", "sum"), geracao=("geracao", "sum"),
                          expirado=("expirar", "sum"), meses=("consumo", "count"))
Y["saldo_fim"] = [rows[y].get("saldo_fim_ano", np.nan) for y in Y.index]
Y["autoconsumo"] = Y.geracao - Y.injetado
Y["frac_auto"] = Y.autoconsumo / Y.geracao
Y["cobertura"] = Y.geracao / Y.consumo
Y["tarifa"] = Y.pago / Y.consumo
print(Y.round(3).to_string())

full = Y[(Y.index >= 2020) & (Y.index <= 2024)]
print("\n--- structural findings ---")
print("mean annual generation  %.0f kWh" % full.geracao.mean())
print("mean annual consumption %.0f kWh" % full.consumo.mean())
print("coverage ratio          %.2fx  (generation / consumption)" % full.cobertura.mean())
print("self-consumed on site   %.0f%% of generation" % (100 * full.frac_auto.mean()))
print("credit balance end 2024 %.0f kWh" % Y.loc[2024, "saldo_fim"])
print("credits expired in 2024 %.0f kWh" % Y.loc[2024, "expirado"])

# pre-PV baseline: 2018 is the only full year without generation
t18 = Y.loc[2018, "tarifa"]
print("\n2018 (pre-PV): %.0f kWh consumed, R$ %.2f paid, effective R$ %.3f/kWh"
      % (Y.loc[2018, "consumo"], Y.loc[2018, "pago"], t18))
for y in range(2020, 2025):
    print("  %d: R$ %7.2f paid on %.0f kWh -> R$ %.3f/kWh   (saving vs a no-PV bill at that year's tariff)"
          % (y, Y.loc[y, "pago"], Y.loc[y, "consumo"], Y.loc[y, "tarifa"]))

# value of the fault, given the credit surplus
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start", "end"])
lost = seg.E_lost.sum()
print("\n--- what the fault actually cost ---")
print("energy shortfall vs healthy baseline: %.0f kWh" % lost)
print("but the credit balance GREW to %.0f kWh and %.0f kWh expired unused in 2024,"
      % (Y.loc[2024, "saldo_fim"], Y.loc[2024, "expirado"]))
print("so the marginal kWh had no offset value: surplus generation was already being")
print("banked past the 60-month credit expiry window.")

json.dump(dict(
    gen_mean=float(full.geracao.mean()), cons_mean=float(full.consumo.mean()),
    coverage=float(full.cobertura.mean()), self_cons=float(full.frac_auto.mean()),
    saldo_2024=float(Y.loc[2024, "saldo_fim"]), expirado_2024=float(Y.loc[2024, "expirado"]),
    tarifa_2018=float(t18), tarifa_2024=float(Y.loc[2024, "tarifa"]),
    pago_2018=float(Y.loc[2018, "pago"]), pago_2024=float(Y.loc[2024, "pago"]),
), open(caminho("billing_summary.json"), "w"), indent=1)
Y.to_csv(caminho("billing_annual.csv"))
print("\nwrote billing.csv, billing_annual.csv, billing_summary.json")
