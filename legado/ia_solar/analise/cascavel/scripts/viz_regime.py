import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, os, matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
import vizstyle as V; V.setup()
from viz_drivers import DRIVERS   # reuse the driver list

OUT=caminho("figs"); os.makedirs(OUT, exist_ok=True)
df  = pd.read_csv(caminho("master.csv"), index_col=0, parse_dates=True)
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])
q   = df[(df.poa>=1.0) & (df.pr.between(0.05,1.3))].copy()

# label each day with its regime and whether that regime is healthy
q["regime"] = np.nan; q["healthy"] = False
for i, s in seg.iterrows():
    m = (q.index >= s.start) & (q.index <= s.end + pd.offsets.MonthEnd(1))
    q.loc[m, "regime"] = i
    q.loc[m, "healthy"] = s.pr >= 0.82
q = q.dropna(subset=["regime"])
h = q[q.healthy].copy()
tnum_h = mdates.date2num(h.index.to_pydatetime())
print(f"healthy-regime days: {len(h)} of {len(q)}")

# ---------- 09 driver grid, healthy regime only ----------
n=len(DRIVERS); ncol=5; nrow=int(np.ceil(n/ncol))
fig, axes = plt.subplots(nrow, ncol, figsize=(4.0*ncol, 2.9*nrow))
rows=[]
for ax,(col,lbl,unit,lg) in zip(axes.ravel(), DRIVERS):
    if col not in h.columns or h[col].notna().sum()<200: ax.axis("off"); continue
    V.driver_panel(ax, h[col].values, h.pr_tcorr.values, tnum_h, lbl, unit, nbins=10)
    s_=h[[col,"pr_tcorr"]].dropna()
    r,p=stats.pearsonr(s_[col],s_.pr_tcorr); rs,_=stats.spearmanr(s_[col],s_.pr_tcorr)
    # same statistic on the full record, for contrast
    sa=q[[col,"pr_tcorr"]].dropna(); ra,_=stats.pearsonr(sa[col],sa.pr_tcorr)
    rows.append(dict(driver=col,label=lbl,r_healthy=r,r_all=ra,p=p,n=len(s_)))
    ax.set_ylim(.55,1.15); ax.set_ylabel("")
    ax.text(.03,.90,f"r={r:+.2f} (all {ra:+.2f})",transform=ax.transAxes,fontsize=8.5,
            color=(V.S8 if p<1e-3 and abs(r)>.2 else V.MUTED),fontweight="600")
for ax in axes.ravel()[n:]: ax.axis("off")
for i in range(nrow): axes[i,0].set_ylabel("Temp-corrected PR")
fig.suptitle("Same drivers, healthy regimes only — removing the 2021-23 fault strips most apparent effects\n"
             "\"all\" = correlation over the whole record, for contrast",
             x=.008, ha="left", fontsize=14, fontweight="600", y=.998)
fig.tight_layout(rect=[0,0,1,.975]); fig.savefig(f"{OUT}/09_driver_grid_healthy.png"); plt.close(fig)
print("  09_driver_grid_healthy")
C=pd.DataFrame(rows); C["shrink"]=C.r_all.abs()-C.r_healthy.abs()
C.sort_values("shrink",ascending=False).to_csv(caminho("confounding.csv"),index=False)
print(C.sort_values("shrink",ascending=False).round(3).head(12).to_string(index=False))

# ---------- 10 confounding: all-record vs within-regime r ----------
fig, ax = plt.subplots(figsize=(7.6,6.4))
ax.axhline(0,color=V.GRID,lw=1); ax.axvline(0,color=V.GRID,lw=1)
ax.plot([-.4,.4],[-.4,.4],color=V.MUTED,ls=(0,(4,3)),lw=1)
ax.scatter(C.r_all, C.r_healthy, s=44, color=V.S1, alpha=.85, zorder=3, edgecolors=V.SURF, linewidths=1.5)
for _,r_ in C.iterrows():
    if abs(r_.r_all)>.12 or abs(r_.r_healthy)>.12:
        ax.annotate(r_.label, (r_.r_all, r_.r_healthy), fontsize=8, color=V.INK2,
                    xytext=(5,4), textcoords="offset points")
ax.set_xlabel("r over the whole record"); ax.set_ylabel("r within healthy regimes only")
ax.set_xlim(-.42,.42); ax.set_ylim(-.42,.42); ax.grid(True, axis="both")
ax.set_title("How much of each apparent effect is really the fault episode\n"
             "points below the diagonal = correlation inflated by the 2021-23 regime")
fig.savefig(f"{OUT}/10_confounding.png", bbox_inches="tight"); plt.close(fig)
print("  10_confounding")

# ---------- 11 multivariate model, standardised, with regime fixed effects ----------
feats=["poa","Kt","kd","tcell","dT","RH2M","WS2M","dry_days","rain_7d","AOD_55","airmass","uv_ratio"]
M=q[feats+["pr_tcorr","regime"]].dropna()
X=(M[feats]-M[feats].mean())/M[feats].std()
D=pd.get_dummies(M.regime.astype(int),prefix="reg",drop_first=True).astype(float)
def ols(y,X):
    X=np.column_stack([np.ones(len(y)),X]); b,*_=np.linalg.lstsq(X,y,rcond=None)
    e=y-X@b; s2=e@e/(len(y)-X.shape[1]); se=np.sqrt(np.diag(s2*np.linalg.inv(X.T@X)))
    return b,se,1-e.var()/y.var()
y=M.pr_tcorr.values
b1,se1,r2_1=ols(y,X.values)                                  # no regime control
b2,se2,r2_2=ols(y,np.column_stack([X.values,D.values]))      # with regime fixed effects
res=pd.DataFrame(dict(feat=feats,b_naive=b1[1:],se_naive=se1[1:],
                      b_fe=b2[1:1+len(feats)],se_fe=se2[1:1+len(feats)]))
res["t_fe"]=res.b_fe/res.se_fe
res=res.reindex(res.b_fe.abs().sort_values().index)
print(f"\nR2 naive={r2_1:.3f}  with regime fixed effects={r2_2:.3f}")
print(res.round(4).to_string(index=False))
res.to_csv(caminho("multivariate.csv"),index=False)

fig,ax=plt.subplots(figsize=(8.4,6.2))
yy=np.arange(len(res))
ax.barh(yy-.19,res.b_naive,height=.36,color="#c9c8c2",label="no regime control")
ax.barh(yy+.19,res.b_fe,height=.36,color=V.S1,label="with regime fixed effects")
ax.errorbar(res.b_fe,yy+.19,xerr=1.96*res.se_fe,fmt="none",ecolor=V.INK2,elinewidth=1,capsize=2)
ax.set_yticks(yy); ax.set_yticklabels(res.feat)
ax.axvline(0,color=V.INK2,lw=1); ax.grid(axis="x"); ax.set_axisbelow(True)
ax.set_xlabel("change in temp-corrected PR per 1 SD of driver")
ax.set_title(f"Standardised driver effects  (R² {r2_1:.2f} → {r2_2:.2f} once regime is controlled)\n"
             "bars with 95% CI; grey shows how much each effect shrinks")
ax.legend(loc="lower right")
fig.savefig(f"{OUT}/11_multivariate.png",bbox_inches="tight"); plt.close(fig)
print("  11_multivariate")
