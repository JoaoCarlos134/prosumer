import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, os, matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
import vizstyle as V; V.setup()

OUT=caminho("figs"); os.makedirs(OUT, exist_ok=True)
df = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
q  = df[(df.poa>=1.0) & (df.pr.between(0.05,1.3))].copy()
tnum = mdates.date2num(q.index.to_pydatetime())

# (column, label, unit, log?)
DRIVERS = [
 ("poa","Plane-of-array irradiation","kWh/m²/d",0),
 ("H","Global horizontal irradiation","kWh/m²/d",0),
 ("Kt","Clearness index Kt","",0),
 ("Kc","Clear-sky index (GHI/clear-sky)","",0),
 ("kd","Diffuse fraction","",0),
 ("poa_diff","Diffuse POA component","kWh/m²/d",0),
 ("tcell","Modelled cell temperature","°C",0),
 ("T2M","Air temperature","°C",0),
 ("T2M_MAX","Daily max air temperature","°C",0),
 ("T2M_MIN","Daily min air temperature","°C",0),
 ("dT","Diurnal temperature range","K",0),
 ("TS","Ground/skin temperature","°C",0),
 ("RH2M","Relative humidity","%",0),
 ("dewdep","Dew-point depression","K",0),
 ("T2MDEW","Dew point","°C",0),
 ("WS2M","Wind speed @2 m","m/s",0),
 ("WS10M","Wind speed @10 m","m/s",0),
 ("PRECTOTCORR","Precipitation","mm/d",0),
 ("dry_days","Consecutive dry days","d",0),
 ("rain_7d","Rain, trailing 7 d","mm",0),
 ("rain_30d","Rain, trailing 30 d","mm",0),
 ("CLOUD_AMT","Cloud amount","%",0),
 ("AOD_55","Aerosol optical depth 550 nm","",0),
 ("ALLSKY_SRF_ALB","Surface albedo","",0),
 ("uv_ratio","UVA / GHI (spectral proxy)","",0),
 ("airmass","Air mass (irradiance-weighted)","",0),
 ("cos_inc","cos(incidence angle), weighted","",0),
 ("daylength","Day length","h",0),
 ("PS","Surface pressure","kPa",0),
 ("tr_gain","Transposition gain POA/GHI","",0),
]

# ---------- big grid ----------
n = len(DRIVERS); ncol = 5; nrow = int(np.ceil(n/ncol))
fig, axes = plt.subplots(nrow, ncol, figsize=(4.0*ncol, 2.9*nrow))
stats_rows = []
for ax, (col, lbl, unit, lg) in zip(axes.ravel(), DRIVERS):
    if col not in q.columns or q[col].notna().sum() < 200:
        ax.axis("off"); continue
    b = V.driver_panel(ax, q[col].values, q.pr_tcorr.values, tnum, lbl, unit, nbins=12, logx=bool(lg))
    s = q[[col,"pr_tcorr"]].dropna()
    r, p = stats.pearsonr(s[col], s.pr_tcorr); rs, _ = stats.spearmanr(s[col], s.pr_tcorr)
    rng = (b.y.max()-b.y.min()) if b is not None else np.nan
    stats_rows.append(dict(driver=col, label=lbl, unit=unit, n=len(s),
                           pearson=r, spearman=rs, p=p, span=rng))
    ax.set_ylim(.45, 1.15)
    ax.text(.03,.055, f"r={r:+.2f}  ρ={rs:+.2f}", transform=ax.transAxes, fontsize=8.5,
            color=(V.S8 if p<0.001 and abs(r)>.2 else V.MUTED), fontweight="600")
    ax.set_ylabel("")
for ax in axes.ravel()[n:]: ax.axis("off")
for i in range(nrow): axes[i,0].set_ylabel("Temp-corrected PR")
fig.suptitle("Temp-corrected performance ratio vs. every available NASA POWER driver\n"
             "dots = daily values shaded light→dark by date;  orange = binned median with IQR band",
             x=.008, ha="left", fontsize=14, fontweight="600", y=.998)
fig.tight_layout(rect=[0,0,1,.975])
fig.savefig(f"{OUT}/07_driver_grid.png"); plt.close(fig)
print("  07_driver_grid")

S = pd.DataFrame(stats_rows).sort_values("pearson", key=abs, ascending=False)
S.to_csv(caminho("driver_strength.csv"), index=False)
print(S.round(3).to_string(index=False))

# ---------- ranked correlation bar ----------
fig, ax = plt.subplots(figsize=(8.2, 8.0))
T = S.sort_values("pearson")
cols = [V.S1 if v>0 else V.S8 for v in T.pearson]
ax.barh(T.label, T.pearson, color=cols, height=.66)
ax.axvline(0, color=V.INK2, lw=1)
ax.grid(axis="x"); ax.set_axisbelow(True)
for y_, v in zip(range(len(T)), T.pearson):
    ax.text(v + (.012 if v>0 else -.012), y_, f"{v:+.2f}", va="center",
            ha="left" if v>0 else "right", fontsize=8.5, color=V.INK2)
ax.set_xlim(-.45,.45); ax.set_xlabel("Pearson r with temp-corrected PR")
ax.set_title("Which drivers move measured efficiency\n(marginal correlations — confounded with each other)")
fig.savefig(f"{OUT}/08_driver_ranking.png", bbox_inches="tight"); plt.close(fig)
print("  08_driver_ranking")
