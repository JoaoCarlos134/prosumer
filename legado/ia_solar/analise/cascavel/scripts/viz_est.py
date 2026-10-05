import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, os, matplotlib.pyplot as plt
from scipy import stats
import solar, vizstyle as V; V.setup()

OUT = caminho("figs"); os.makedirs(OUT, exist_ok=True)
df = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start", "end"])
meta = json.load(open(caminho("meta.json"))); KWP = meta["kwp"]; LAT = meta["lat"]
q = df[(df.poa >= 1.0) & (df.pr.between(0.05, 1.3))].copy()
q["regime"] = np.nan; q["healthy"] = False
for i, s in seg.iterrows():
    m = (q.index >= s.start) & (q.index <= s.end + pd.offsets.MonthEnd(1))
    q.loc[m, "regime"] = i; q.loc[m, "healthy"] = s.pr >= 0.82
h = q[q.healthy]
clear = h[h.Kt >= 0.60]
out = {}

# ---------- 12 temperature coefficient ----------
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
ax = axes[0]
ax.scatter(clear.tcell, clear.pr, s=7, color=V.S1, alpha=.30, linewidths=0, rasterized=True)
sl, ic, r, p, se = stats.linregress(clear.tcell, clear.pr)
xs = np.linspace(clear.tcell.min(), clear.tcell.max(), 50)
ax.plot(xs, ic + sl * xs, color=V.S2, lw=2.2)
g = 100 * sl / (ic + sl * 25)
b = V.binned_median(clear.tcell.values, clear.pr.values, 12)
ax.plot(b.x, b.y, color=V.S8, lw=1.6, ls=(0, (4, 2)))
ax.set_xlabel("Modelled cell temperature (deg C)"); ax.set_ylabel("Raw PR")
ax.set_title("Clear days, healthy regimes:  %+.3f %%/K" % g)
ax.text(.03, .06, "solid = OLS   dashed = binned median", transform=ax.transAxes,
        fontsize=8.5, color=V.MUTED)
out["temp_coeff_clear_healthy"] = float(g)

ax = axes[1]
Xc = np.column_stack([np.ones(len(clear)), clear.Kt, clear.airmass, clear.kd])
def resid(y):
    b_, *_ = np.linalg.lstsq(Xc, y, rcond=None); return y - Xc @ b_
ry = resid(clear.pr.values); rx = resid(clear.tcell.values)
ax.scatter(rx, ry, s=7, color=V.S1, alpha=.30, linewidths=0, rasterized=True)
sl2, ic2, r2_, p2, se2 = stats.linregress(rx, ry)
xs2 = np.linspace(rx.min(), rx.max(), 30); ax.plot(xs2, ic2 + sl2 * xs2, color=V.S2, lw=2.2)
g2 = 100 * sl2 / clear.pr.mean(); g2se = 100 * se2 / clear.pr.mean()
ax.set_xlabel("cell temperature, residual after Kt / air mass / diffuse fraction")
ax.set_ylabel("PR, same residual")
ax.set_title("Partial effect:  %+.3f %%/K  (+/- %.3f, p=%.1g)" % (g2, 1.96 * g2se, p2))
out["temp_coeff_partial"] = [float(g2), float(g2se)]
fig.suptitle("Estimating the module power temperature coefficient", x=.008, ha="left",
             fontsize=13, fontweight="600")
fig.tight_layout(rect=[0, 0, 1, .95]); fig.savefig(OUT + "/12_temp_coefficient.png"); plt.close(fig)
print("  12_temp_coefficient")

# ---------- 13 soiling ----------
fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
ax = axes[0]
bins = [-1, 0, 1, 2, 4, 7, 12, 20, 999]
labs = ["rain\ntoday", "1 d", "2 d", "3-4 d", "5-7 d", "8-12 d", "13-20 d", ">20 d"]
cb = pd.cut(clear.dry_days, bins, labels=labs)
gg = clear.groupby(cb, observed=True).pr_tcorr.agg(["mean", "sem", "count"])
ax.bar(gg.index.astype(str), gg["mean"], yerr=1.96 * gg["sem"], color=V.S1, width=.62,
       error_kw=dict(ecolor=V.INK2, elinewidth=1, capsize=3))
for x_, (v, c_) in enumerate(zip(gg["mean"], gg["count"])):
    ax.text(x_, v + .012, "n=%d" % c_, ha="center", fontsize=7.5, color=V.MUTED)
ax.set_ylim(.75, .95); ax.set_ylabel("Temp-corrected PR")
ax.set_xlabel("consecutive days without >1 mm rain")
ax.set_title("No soiling signal in dry spells")

ax = axes[1]
sl, ic, r, p, se = stats.linregress(clear.dry_days, clear.pr_tcorr)
V.driver_panel(ax, clear.dry_days.values, clear.pr_tcorr.values,
               np.arange(len(clear)), "consecutive dry days", "d", nbins=10)
xd = np.linspace(0, clear.dry_days.max(), 20)
ax.plot(xd, ic + sl * xd, color=V.S8, lw=2)
ax.set_ylabel("Temp-corrected PR")
ax.set_title("slope %+.3f %%/dry-day (p=%.2g) - wrong sign for soiling" % (100 * sl / ic, p))
out["soiling_healthy"] = [float(100 * sl / ic), float(p)]
fig.tight_layout(); fig.savefig(OUT + "/13_soiling.png"); plt.close(fig)
print("  13_soiling")

# ---------- 14 tilt/azimuth objective surface ----------
v = df.dropna(subset=["H", "Hd", "T2M", "e_kwh"])
n_, H_, Hd_ = v.n.values.astype(float), v.H.values, v.Hd.values
alb_ = v.ALLSKY_SRF_ALB.fillna(.16).values
tamb_, wind_, E_ = v.T2M.values, v.WS2M.values, v.e_kwh.values
mo_ = v.index.month.values
def obj(beta, gamma):
    r = solar.poa_daily(LAT, n_, H_, Hd_, beta, gamma, albedo=alb_); poa = r["poa"]
    dt = (r["daylength"] / r["_poa_h"].shape[1])[:, None]
    tc = solar.weighted_cell_temp(np.where(dt > 0, r["_poa_h"] / dt, 0) * 1000., tamb_, wind_)
    pr = E_ / (KWP * np.where(poa > .05, poa, np.nan)); prc = pr / (1 - .004 * (tc - 25))
    m_ = pd.Series(prc, index=mo_).groupby(level=0).mean()
    return float(m_.std() / m_.mean())
B = np.arange(0, 41, 2.5); G = np.arange(90, 276, 7.5)
Z = np.array([[obj(b, g) for g in G] for b in B])
fig, ax = plt.subplots(figsize=(8.2, 5.2))
cf = ax.contourf(G, B, Z, levels=18, cmap=V.SEQ.reversed()); ax.grid(False)
ax.contour(G, B, Z, levels=[Z.min() * 1.05, Z.min() * 1.15, Z.min() * 1.3],
           colors=[V.SURF], linewidths=.9)
ax.plot(meta["azimuth"], meta["tilt"], marker="*", ms=20, color=V.S2, mec=V.SURF, mew=1.5, zorder=5)
ax.annotate("best fit %.0f/%.0f" % (meta["tilt"], meta["azimuth"]),
            (meta["azimuth"], meta["tilt"]), color=V.S2, fontsize=9.5, fontweight="600",
            ha="right", xytext=(-12, -3), textcoords="offset points")
ax.plot(180, abs(LAT), marker="o", ms=9, color=V.INK, mec=V.SURF, mew=1.5, zorder=5)
ax.annotate("  latitude tilt, due north", (180, abs(LAT)), color=V.INK, fontsize=9,
            xytext=(8, 4), textcoords="offset points")
ax.set_xlabel("surface azimuth (180 deg = due north)"); ax.set_ylabel("tilt (deg)")
ax.set_title("Fitting array orientation - tilt is identifiable, azimuth is not")
ax.text(.5, .04, "the dark valley runs flat across azimuth - daily totals barely constrain it",
        transform=ax.transAxes, ha="center", fontsize=8.5, color=V.SURF)
fig.colorbar(cf, ax=ax, pad=.02, label="seasonal CV of temp-corrected PR  (lower = better)")
fig.savefig(OUT + "/14_orientation_fit.png", bbox_inches="tight"); plt.close(fig)
good = Z <= Z.min() * 1.15
out["tilt_range"] = [float(B[good.any(1)].min()), float(B[good.any(1)].max())]
out["azim_range"] = [float(G[good.any(0)].min()), float(G[good.any(0)].max())]
print("  14_orientation_fit   tilt band", out["tilt_range"], " azimuth band", out["azim_range"])

# ---------- 15 degradation in the current regime ----------
cur = seg.iloc[-1]
cq = q[q.index >= cur.start]
m = cq.resample("MS").agg(pr=("pr_tcorr", "mean"), n=("pr", "size")); m = m[m.n >= 20]
t = (m.index - m.index[0]).days / 365.25
sl, ic, r, p, se = stats.linregress(t, m.pr)
fig, ax = plt.subplots(figsize=(9, 4.3))
ax.scatter(m.index, m.pr, s=42, color=V.S1, zorder=3, edgecolors=V.SURF, linewidths=1.2)
ax.plot(m.index, ic + sl * t, color=V.S2, lw=2.2)
band = 1.96 * m.pr.std() / np.sqrt(len(m))
ax.fill_between(m.index, ic + sl * t - band, ic + sl * t + band, color=V.S2, alpha=.12, linewidth=0)
rate = 100 * sl / ic; rse = 100 * se / ic
ax.set_ylabel("Monthly temp-corrected PR")
ax.set_title("Degradation in the current healthy regime (%s onward): %+.2f %%/yr  "
             "(95%% CI %+.2f to %+.2f, p=%.2f)"
             % (cur.start.date(), rate, rate - 1.96 * rse, rate + 1.96 * rse, p))
ax.text(.02, .06, "no statistically detectable degradation over this window",
        transform=ax.transAxes, fontsize=9.5, color=V.INK2)
fig.savefig(OUT + "/15_degradation.png", bbox_inches="tight"); plt.close(fig)
out["degr_current"] = [float(rate), float(rse), float(p)]
print("  15_degradation  %+.3f +/- %.3f %%/yr" % (rate, 1.96 * rse))

# ---------- 16 model validation ----------
fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0))
ax = axes[0]
pred = h.poa * KWP * h.pr_tcorr.mean() * (1 - .004 * (h.tcell - 25))
ax.scatter(pred, h.e_kwh, s=6, color=V.S1, alpha=.35, linewidths=0, rasterized=True)
lim = [0, max(pred.max(), h.e_kwh.max()) * 1.03]
ax.plot(lim, lim, color=V.INK2, ls=(0, (4, 3)), lw=1.2); ax.set_xlim(lim); ax.set_ylim(lim)
mbe = 100 * (h.e_kwh - pred).mean() / h.e_kwh.mean()
rmse = 100 * np.sqrt(((h.e_kwh - pred) ** 2).mean()) / h.e_kwh.mean()
ax.set_xlabel("modelled daily energy (kWh)"); ax.set_ylabel("measured (kWh)")
ax.set_title("Model vs measured\nMBE %+.1f%%  rRMSE %.1f%%" % (mbe, rmse))

ax = axes[1]
res = (h.e_kwh - pred) / h.e_kwh.mean() * 100
mb = res.groupby(h.index.month).agg(["mean", "sem"])
ax.bar(mb.index, mb["mean"], yerr=1.96 * mb["sem"],
       color=[V.S8 if abs(x) > 4 else V.S1 for x in mb["mean"]], width=.66,
       error_kw=dict(ecolor=V.INK2, elinewidth=1, capsize=2))
ax.axhline(0, color=V.INK2, lw=1); ax.set_xticks(range(1, 13))
ax.set_xticklabels(list("JFMAMJJASOND"))
ax.set_ylabel("residual (% of mean)"); ax.set_title("Seasonal bias left in the model")

ax = axes[2]
rb = res.groupby(pd.cut(h.Kt, [0, .3, .4, .5, .6, .65, .7, .8]), observed=True).agg(["mean", "sem", "size"])
ax.bar(range(len(rb)), rb["mean"], yerr=1.96 * rb["sem"], color=V.S1, width=.66,
       error_kw=dict(ecolor=V.INK2, elinewidth=1, capsize=2))
ax.set_xticks(range(len(rb)))
ax.set_xticklabels([str(i) for i in rb.index], rotation=35, ha="right", fontsize=8)
ax.axhline(0, color=V.INK2, lw=1); ax.set_xlabel("clearness index bin")
ax.set_title("Bias vs sky condition")
fig.suptitle("Where the NASA POWER + transposition model is wrong (healthy regimes only)",
             x=.008, ha="left", fontsize=13, fontweight="600")
fig.tight_layout(rect=[0, 0, 1, .93]); fig.savefig(OUT + "/16_model_validation.png"); plt.close(fig)
out["model_mbe_pct"] = float(mbe); out["model_rrmse_pct"] = float(rmse)
print("  16_model_validation  MBE %+.2f%%  rRMSE %.2f%%" % (mbe, rmse))

# ---------- 17 PR distributions by regime ----------
fig, ax = plt.subplots(figsize=(9, 4.2))
for i, s in seg.iterrows():
    d = q[q.regime == i].pr_tcorr.dropna()
    if len(d) < 60: continue
    col = V.S3 if s.pr >= .82 else V.S8
    kde = stats.gaussian_kde(d); xs = np.linspace(.5, 1.1, 200)
    ax.plot(xs, kde(xs), color=col, lw=2, alpha=.9)
    ax.fill_between(xs, kde(xs), color=col, alpha=.07, linewidth=0)
    ax.annotate("%s-%s  PR %.2f" % (s.start.strftime("%b %Y"), s.end.strftime("%b %Y"), s.pr),
                (s.pr, kde(s.pr)[0]), color=col, fontsize=8.5, fontweight="600",
                xytext=(4, 4), textcoords="offset points")
ax.set_xlabel("Temp-corrected PR"); ax.set_ylabel("density"); ax.set_yticks([])
ax.set_title("The regimes are cleanly separated distributions, not gradual drift")
fig.savefig(OUT + "/17_pr_distributions.png", bbox_inches="tight"); plt.close(fig)
print("  17_pr_distributions")

json.dump(out, open(caminho("estimates2.json"), "w"), indent=1, default=float)
print("wrote estimates2.json")
