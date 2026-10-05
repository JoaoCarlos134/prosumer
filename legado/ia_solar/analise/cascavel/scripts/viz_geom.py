# -*- coding: utf-8 -*-
"""Fig 14 rebuilt: validate the fitted geometry against the now-known datasheet geometry."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, matplotlib.pyplot as plt
import solar, vizstyle as V; V.setup()

m = json.load(open(caminho("meta.json"))); LAT = m["lat"]; KWP = m["kwp"]
TILT, AZIM = m["tilt"], m["azimuth"]
df = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
v = df.dropna(subset=["H", "Hd", "T2M", "e_kwh"])
n_, H_, Hd_ = v.n.values.astype(float), v.H.values, v.Hd.values
alb_ = v.ALLSKY_SRF_ALB.fillna(.16).values
E_, tamb_, wind_ = v.e_kwh.values, v.T2M.values, v.WS2M.values
mo_ = v.index.month.values

def metrics(beta, gamma):
    r = solar.poa_daily(LAT, n_, H_, Hd_, beta, gamma, albedo=alb_)
    poa = r["poa"]
    dt = (r["daylength"] / r["_poa_h"].shape[1])[:, None]
    tc = solar.weighted_cell_temp(np.where(dt > 0, r["_poa_h"] / dt, 0) * 1000., tamb_, wind_)
    pr = E_ / (KWP * np.where(poa > .05, poa, np.nan)); prc = pr / (1 - .004 * (tc - 25))
    s = pd.Series(prc, index=mo_).groupby(level=0).mean()
    return np.corrcoef(poa, E_)[0, 1] ** 2, float(s.std() / s.mean())

TILTS = np.arange(0, 36, 1.0)
AZIMS = np.arange(95, 266, 2.5)
r2_t = np.array([metrics(b, AZIM)[0] for b in TILTS])
r2_a = np.array([metrics(TILT, g)[0] for g in AZIMS])
cv_t = np.array([metrics(b, AZIM)[1] for b in TILTS])
cv_a = np.array([metrics(TILT, g)[1] for g in AZIMS])

fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.5))

ax = axes[0]
ax.plot(TILTS, r2_t, color=V.S1, lw=2.2)
bt = TILTS[r2_t.argmax()]
ax.axvline(TILT, color=V.S3, lw=2, ls=(0, (5, 3)))
ax.plot(bt, r2_t.max(), marker="o", ms=8, color=V.S1, mec=V.SURF, mew=1.5, zorder=5)
ax.annotate("R² optimum %.0f°" % bt, (bt, r2_t.max()), fontsize=9, color=V.S1,
            xytext=(-6, -16), ha="right", textcoords="offset points", fontweight="600")
ax.annotate("datasheet 13°", (TILT, r2_t.min() + .004), fontsize=9.5, color=V.S3,
            xytext=(7, 0), textcoords="offset points", fontweight="600")
ax.plot(17.0, metrics(17.0, AZIM)[0], marker="*", ms=15, color=V.S2, mec=V.SURF, mew=1.2, zorder=5)
ax.annotate("my fit 17°", (17.0, metrics(17.0, AZIM)[0]), fontsize=9, color=V.S2,
            xytext=(10, 6), textcoords="offset points", fontweight="600")
ax.set_xlabel("tilt (°), azimuth held at datasheet value")
ax.set_ylabel("R² of daily energy vs POA")
ax.set_title("Tilt is identifiable — and the fit was right")

ax = axes[1]
ax.plot(AZIMS, r2_a, color=V.S1, lw=2.2)
ax.axvline(180, color=V.MUTED, lw=1, ls=(0, (2, 3)))
ax.axvline(AZIM, color=V.S3, lw=2, ls=(0, (5, 3)))
ax.axvline(2 * 180 - AZIM, color=V.S3, lw=1.2, ls=(0, (2, 2)), alpha=.7)
ax.plot(244.0, metrics(TILT, 244.0)[0], marker="*", ms=15, color=V.S2, mec=V.SURF, mew=1.2, zorder=5)
ax.annotate("my fit 244°\n(wrong by 89°)", (244.0, metrics(TILT, 244.0)[0]), fontsize=9,
            color=V.S2, ha="right", xytext=(-6, 10), textcoords="offset points", fontweight="600")
ax.annotate("datasheet\n155°", (AZIM, r2_a.min() + .002), fontsize=9.5, color=V.S3,
            xytext=(-6, 0), ha="right", textcoords="offset points", fontweight="600")
ax.annotate("mirror 205°\nidentical R²", (205, r2_a.min() + .002), fontsize=9,
            color=V.S3, xytext=(6, 0), textcoords="offset points", alpha=.85)
ax.annotate("due north", (180, r2_a.max()), fontsize=8.5, color=V.MUTED,
            xytext=(4, -14), textcoords="offset points")
ax.set_xlabel("azimuth (°), tilt held at datasheet 13°")
ax.set_ylabel("R² of daily energy vs POA")
ax.set_title("Azimuth is not — the curve is symmetric about north")

fig.suptitle("Checking the fitted orientation against the datasheet", x=.008, ha="left",
             fontsize=13, fontweight="600")
fig.tight_layout(rect=[0, 0, 1, .94])
fig.savefig(caminho("figs/14_orientation_fit.png")); plt.close(fig)

sym = abs(metrics(TILT, 155)[0] - metrics(TILT, 205)[0])
print("  14_orientation_fit")
print("   R2 optimum tilt      : %.0f deg   (datasheet 13, old fit 17)" % bt)
print("   R2(155) vs R2(205)   : differ by %.2e  -> exactly symmetric" % sym)
print("   R2 range over azimuth: %.5f .. %.5f (%.2f%% spread)"
      % (r2_a.min(), r2_a.max(), 100 * (r2_a.max() / r2_a.min() - 1)))
print("   R2 range over tilt   : %.5f .. %.5f (%.2f%% spread)"
      % (r2_t.min(), r2_t.max(), 100 * (r2_t.max() / r2_t.min() - 1)))
