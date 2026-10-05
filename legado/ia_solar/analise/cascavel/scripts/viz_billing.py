# -*- coding: utf-8 -*-
"""Figures 18-20: the economic layer."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, matplotlib.pyplot as plt
import matplotlib.dates as mdates
import vizstyle as V; V.setup()

B = pd.read_csv(caminho("billing.csv"), index_col=0, parse_dates=True)
Y = pd.read_csv(caminho("billing_annual.csv"), index_col=0)
Y = Y[(Y.index >= 2018) & (Y.index <= 2024)]
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start", "end"])

# ---------- 18 generation against the household's actual load ----------
b = B[(B.index.year >= 2019) & (B.index.year <= 2024)]
fig, ax = plt.subplots(figsize=(11, 4.5))
ax.fill_between(b.index, 0, b.geracao, color=V.S1, alpha=.16, linewidth=0)
ax.plot(b.index, b.geracao, color=V.S1, lw=2, label="generated")
ax.plot(b.index, b.consumo, color=V.S2, lw=2, label="consumed on site")
ax.fill_between(b.index, b.consumo, b.geracao, where=(b.geracao > b.consumo),
                color=V.S1, alpha=.10, linewidth=0)
ax.set_ylabel("kWh per month")
ax.legend(loc="upper right", ncol=2)
ax.set_title("The array produces 2.6× what the house uses — every month, in every year")
ax.annotate("surplus\n(becomes credit)", xy=(b.index[26], 430), fontsize=9.5,
            color=V.S1, ha="center", fontweight="600")
fig.savefig(caminho("figs/18_generation_vs_load.png"), bbox_inches="tight"); plt.close(fig)
print("  18_generation_vs_load")

# ---------- 19 credit balance and expiry ----------
fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.3))
ax = axes[0]
yy = Y[Y.saldo_fim.notna()]
ax.bar(yy.index.astype(str), yy.saldo_fim, color=V.S1, width=.62)
for x_, v_ in zip(range(len(yy)), yy.saldo_fim):
    ax.text(x_, v_ + 200, "%.0f" % v_, ha="center", fontsize=9, color=V.INK)
ax.set_ylabel("kWh"); ax.set_title("Unused credit balance at year end")
ax.text(.03, .88, "a balance this large can never be spent:\nannual consumption is only ~2 200 kWh",
        transform=ax.transAxes, fontsize=9, color=V.INK2)

ax = axes[1]
ex = B[B.expirar.notna() & (B.expirar > 0)]
ax.bar(ex.index, ex.expirar, color=V.S8, width=22)
ax.set_ylabel("kWh expired"); ax.set_title("Credits that expired unused in 2024")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
tot = ex.expirar.sum()
ax.text(.03, .88, "%.0f kWh written off — these were\ninjected in 2019 and hit the 60-month limit" % tot,
        transform=ax.transAxes, fontsize=9, color=V.INK2)
fig.suptitle("Surplus generation is being banked past the point of usefulness",
             x=.008, ha="left", fontsize=13, fontweight="600")
fig.tight_layout(rect=[0, 0, 1, .93])
fig.savefig(caminho("figs/19_credits.png")); plt.close(fig)
print("  19_credits")

# ---------- 20 what the bill actually did ----------
fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.2))
ax = axes[0]
cols = [V.INK2] + [V.S1] * (len(Y) - 1)
ax.bar(Y.index.astype(str), Y.pago, color=cols, width=.62)
for x_, v_ in zip(range(len(Y)), Y.pago):
    ax.text(x_, v_ + 40, "%.0f" % v_, ha="center", fontsize=8.5, color=V.INK)
ax.set_ylabel("R$ paid per year")
ax.set_title("Annual electricity bill")
ax.text(.03, .84, "2018 is the only pre-PV year", transform=ax.transAxes,
        fontsize=9, color=V.INK2)

ax = axes[1]
ax.plot(Y.index, Y.tarifa, color=V.S1, lw=2.2, marker="o", ms=7, mec=V.SURF, mew=1.4)
ax.set_ylabel("R$ per kWh consumed")
ax.set_ylim(0, .95)
ax.set_xticks(Y.index)
for x_, v_ in zip(Y.index, Y.tarifa):
    ax.annotate("%.2f" % v_, (x_, v_), fontsize=8.5, color=V.INK2,
                xytext=(0, 9), textcoords="offset points", ha="center")
ax.set_title("Effective cost of each kWh consumed")
ax.text(.30, .62, "the PV halved it, then fixed charges\nand tariff inflation took some back",
        transform=ax.transAxes, fontsize=9, color=V.INK2)
fig.suptitle("The bill fell by half in 2020 and has drifted back up since",
             x=.008, ha="left", fontsize=13, fontweight="600")
fig.tight_layout(rect=[0, 0, 1, .93])
fig.savefig(caminho("figs/20_bill.png")); plt.close(fig)
print("  20_bill")

# ---------- headline economics ----------
lost = seg.E_lost.sum()
print("\n   fault shortfall %.0f kWh; 2024 credit balance %.0f kWh; expired %.0f kWh"
      % (lost, Y.loc[2024, "saldo_fim"], Y.loc[2024, "expirado"]))
