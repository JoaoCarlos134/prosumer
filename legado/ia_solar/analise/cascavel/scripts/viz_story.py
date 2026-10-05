import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from scipy import stats
import vizstyle as V; V.setup()

OUT = caminho("figs"); import os; os.makedirs(OUT, exist_ok=True)
df   = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
mon  = pd.read_csv(caminho("monthly_pr.csv"), index_col=0, parse_dates=True)
seg  = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])
cp   = json.load(open(caminho("changepoints.json")))
est  = json.load(open(caminho("estimates.json")))
meta = json.load(open(caminho("meta.json")))
KWP  = meta["kwp"]; BASE = cp["baseline_pr"]
q    = df[(df.poa >= 1.0) & (df.pr.between(0.05, 1.3))].copy()
tnum = mdates.date2num(q.index.to_pydatetime())

def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png"); plt.close(fig); print("  ", name)

# ---------- 01 the headline: PR over time with regimes ----------
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.scatter(q.index, q.pr_tcorr, s=4, color=V.S1, alpha=.16, linewidths=0, rasterized=True)
r = q.pr_tcorr.rolling(30, center=True, min_periods=15).median()
ax.plot(q.index, r, color=V.S1, lw=1.6, label="30-day median")
for _, s in seg.iterrows():
    healthy = s.pr >= 0.82
    ax.add_patch(Rectangle((mdates.date2num(s.start), 0.55),
                 mdates.date2num(s.end + pd.offsets.MonthEnd(1)) - mdates.date2num(s.start), 0.55,
                 color=(V.S3 if healthy else V.S8), alpha=.06, zorder=0, linewidth=0))
    ax.hlines(s.pr, s.start, s.end + pd.offsets.MonthEnd(1),
              color=(V.S3 if healthy else V.S8), lw=3, zorder=6, capstyle="round")
    ax.text(s.start + (s.end - s.start)/2, 1.075, f"{s.pr:.2f}", ha="center", fontsize=9,
            color=(V.S3 if healthy else V.S8), fontweight="600")
ax.axhline(BASE, color=V.INK2, ls=(0,(4,3)), lw=1.1)
ax.text(q.index[8], BASE-.045, f"healthy baseline {BASE:.2f}", fontsize=9, color=V.INK2)
for c in cp["changepoints"]:
    ax.axvline(pd.Timestamp(c), color=V.MUTED, lw=1, ls=(0,(2,3)))
ax.set_ylim(.55, 1.12); ax.set_ylabel("Temp-corrected performance ratio")
ax.set_title("Performance ratio collapsed over 2021-2023, then recovered in a single step (Nov 2023)")
ax.legend(loc="lower right")
save(fig, "01_pr_timeline")

# ---------- 02 month x year heatmap ----------
piv = q.groupby([q.index.year, q.index.month]).pr_tcorr.mean().unstack()
fig, ax = plt.subplots(figsize=(9.5, 4.2))
im = ax.imshow(piv.values, cmap=V.SEQ, aspect="auto", vmin=.66, vmax=.93)
ax.set_xticks(range(12)); ax.set_xticklabels(list("JFMAMJJASOND"))
ax.set_yticks(range(len(piv))); ax.set_yticklabels(piv.index)
ax.grid(False)
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        v = piv.values[i, j]
        if np.isfinite(v):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8,
                    color=("#ffffff" if v > .84 else V.INK))
ax.set_title("Temp-corrected PR by month — the loss is a period effect, not a seasonal one")
fig.colorbar(im, ax=ax, pad=.02, label="PR")
save(fig, "02_pr_heatmap")

# ---------- 03 cumulative shortfall ----------
d = df.copy()
d["E_base"] = d.poa * KWP * BASE
cum_a = d.e_kwh.cumsum(); cum_b = d.E_base.cumsum()
fig, ax = plt.subplots(figsize=(10, 4.4))
ax.fill_between(d.index, cum_a, cum_b, color=V.S8, alpha=.14, linewidth=0)
ax.plot(d.index, cum_b, color=V.INK2, lw=1.8, ls=(0,(5,3)))
ax.plot(d.index, cum_a, color=V.S1, lw=2.2)
ax.text(d.index[-1], cum_b.iloc[-1], f"  expected at PR {BASE:.2f}\n  {cum_b.iloc[-1]:,.0f} kWh",
        va="center", fontsize=9, color=V.INK2)
ax.text(d.index[-1], cum_a.iloc[-1], f"  actual\n  {cum_a.iloc[-1]:,.0f} kWh",
        va="center", fontsize=9, color=V.S1, fontweight="600")
gap = cum_b.iloc[-1]-cum_a.iloc[-1]
ax.annotate(f"shortfall {gap:,.0f} kWh ({100*gap/cum_b.iloc[-1]:.0f}%)",
            xy=(d.index[int(len(d)*.62)], (cum_a.iloc[int(len(d)*.62)]+cum_b.iloc[int(len(d)*.62)])/2),
            fontsize=10, color=V.S8, fontweight="600", ha="center")
ax.set_ylabel("Cumulative energy (kWh)"); ax.margins(x=.14)
ax.set_title("Cumulative generation vs. what a healthy system would have produced")
save(fig, "03_cumulative_shortfall")

# ---------- 04 annual yield + PR ----------
yr = df.groupby("year").agg(E=("e_kwh","sum"), days=("e_kwh","size"), poa=("poa","sum"))
yr = yr[yr.days >= 360]; yr["sy"] = yr.E/KWP; yr["pr"] = yr.E/(KWP*yr.poa)
fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
axes[0].bar(yr.index.astype(str), yr.sy, color=V.S1, width=.62)
for x, v in zip(range(len(yr)), yr.sy): axes[0].text(x, v+12, f"{v:,.0f}", ha="center", fontsize=9, color=V.INK)
axes[0].set_ylabel("kWh/kWp/yr"); axes[0].set_title("Specific yield (complete years)")
axes[1].bar(yr.index.astype(str), yr.pr, color=[V.S3 if v>=.78 else V.S8 for v in yr.pr], width=.62)
for x, v in zip(range(len(yr)), yr.pr): axes[1].text(x, v+.008, f"{v:.2f}", ha="center", fontsize=9, color=V.INK)
axes[1].set_ylim(0,1.0); axes[1].set_ylabel("PR"); axes[1].set_title("Annual performance ratio")
save(fig, "04_annual")

# ---------- 05 E vs POA regression by regime ----------
fig, ax = plt.subplots(figsize=(7.4, 5.2))
sc = ax.scatter(q.poa, q.e_kwh, c=tnum, cmap=V.SEQ, s=6, alpha=.45, linewidths=0, rasterized=True)
xs = np.linspace(q.poa.min(), q.poa.max(), 50)
for _, s in seg.iterrows():
    sl = q[(q.index >= s.start) & (q.index <= s.end + pd.offsets.MonthEnd(1))]
    if len(sl) < 100: continue
    k = np.polyfit(sl.poa, sl.e_kwh, 1)
    ax.plot(xs, np.polyval(k, xs), lw=1.6, color=(V.S3 if s.pr>=.82 else V.S8), alpha=.85)
ax.set_xlabel("Plane-of-array irradiation (kWh/m²/day)"); ax.set_ylabel("Daily energy (kWh)")
ax.set_title("Energy vs POA — the fan of slopes is the efficiency loss")
cb = fig.colorbar(sc, ax=ax, pad=.02); cb.set_label("date")
cb.set_ticks(mdates.date2num(pd.to_datetime([f"{y}-01-01" for y in range(2020,2027)]).to_pydatetime()))
cb.set_ticklabels([str(y) for y in range(2020,2027)])
save(fig, "05_energy_vs_poa")

# ---------- 06 loss waterfall ----------
th = est["thermal_loss_pct"]; resid = est["residual_loss_pct"]
steps = [("Reference\n(POA × kWp)", 100, V.INK2), ("Thermal", th, V.S2),
         ("Soiling / fault\n/ BOS / inverter", resid, V.S8)]
fig, ax = plt.subplots(figsize=(7.6, 4.3))
run = 100; xs_ = []
ax.bar(0, 100, color="#c9c8c2", width=.6); ax.text(0, 101, "100%", ha="center", fontsize=9)
for i, (lbl, v, c) in enumerate(steps[1:], start=1):
    ax.bar(i, v, bottom=run+v if v < 0 else run, color=c, width=.6)
    ax.text(i, run+v/2, f"{v:+.1f}%", ha="center", va="center", fontsize=9, color="white", fontweight="600")
    run += v
ax.bar(len(steps), run, color=V.S1, width=.6)
ax.text(len(steps), run+1, f"{run:.1f}%", ha="center", fontsize=9, fontweight="600")
ax.set_xticks(range(len(steps)+1))
ax.set_xticklabels([s[0] for s in steps] + ["Delivered\n(mean PR)"], fontsize=9)
ax.set_ylabel("% of reference yield"); ax.set_ylim(0, 108)
ax.set_title("Where the energy goes (whole-period average)")
save(fig, "06_loss_waterfall")
print("story figures done")
