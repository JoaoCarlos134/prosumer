# -*- coding: utf-8 -*-
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, matplotlib.pyplot as plt, os
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import vizstyle as V; V.setup()
OUT=caminho("figs5"); os.makedirs(OUT,exist_ok=True)

R = pd.read_csv(caminho("ml_results.csv"))
f = pd.read_parquet(caminho("frame5.parquet")); f["ts"]=pd.to_datetime(f.timestamp); f["night"]=f.cosz<=0
GEO=["elev","cosz","cos_inc","sol_az","solar_time","doy","poa_cs"]
WX=["d_Kt","d_H","d_poa","d_T2M","d_RH2M","d_WS2M","d_CLOUD_AMT","d_PRECTOTCORR","d_AOD_55"]
F=GEO+WX; T="p_ac"
def clean(df):
    d=df[~df.night].copy(); d=d[d.p_ac.notna()]; d=d[d.p_ac<=4000]
    return d[~((d.poa_cs>300)&(d.d_Kt>=.6)&(d.p_ac==0))]
S=pd.Timestamp("2025-08-01")
tr=clean(f[f.ts<S]); te=clean(f[f.ts>=S])
m=HistGradientBoostingRegressor(max_iter=300,learning_rate=.08,min_samples_leaf=40,random_state=0).fit(tr[F],tr[T])
te=te.copy(); te["pred"]=np.clip(m.predict(te[F]),0,None); y=te[T].values

fig,ax=plt.subplots(1,3,figsize=(14.2,4.5))

# 1. variant comparison
a=ax[0]
lab=["A raw\n+leak","B raw\nno leak","C cleaned\nno leak","F cleaned\n+soiling"]
sel=R[R.variant.str.startswith(("A","B","C","F"))].reset_index(drop=True)
cols=[V.S8,V.MUTED,V.S1,V.S3]
a.bar(range(4),sel.MAE.values,color=cols,width=.62)
for i,(v,r2) in enumerate(zip(sel.MAE.values,sel.R2.values)):
    a.text(i,v+9,"%.0f W"%v,ha="center",fontsize=9,color=V.INK,fontweight="600")
    a.text(i,v/2,"R² %.3f"%r2,ha="center",fontsize=8.5,color="white",fontweight="600")
a.set_xticks(range(4)); a.set_xticklabels(lab,fontsize=8.5)
a.set_ylabel("MAE on the same held-out year (W)")
a.set_title("Cleaning does not lower error;\nleakage removal raises it — correctly")
a.annotate("reads the answer\noff the inverter",(0,sel.MAE[0]+95),fontsize=8.5,color=V.S8,
           ha="center",fontweight="600")

# 2. metric inflation from keeping night
a=ax[1]
allr=f[(f.ts>=S)&f.p_ac.notna()&(f.p_ac<=4000)]
pa=np.clip(m.predict(allr[F]),0,None)
vals=[[r2_score(y,te.pred),r2_score(allr[T],pa)],
      [mean_absolute_error(y,te.pred),mean_absolute_error(allr[T],pa)]]
x=np.arange(2); w=.34
a.bar(x-w/2,[vals[0][0],vals[0][1]],w,color=V.S1,label="R²")
a2=a.twinx(); a2.grid(False)
a2.bar(x+w/2,[vals[1][0],vals[1][1]],w,color=V.S2,label="MAE")
a.set_xticks(x); a.set_xticklabels(["daylight only\n(honest)","night rows kept\n(flattering)"],fontsize=9)
a.set_ylabel("R²",color=V.S1); a2.set_ylabel("MAE (W)",color=V.S2)
a.set_ylim(0,1); a2.set_ylim(0,520)
for i,v in enumerate([vals[0][0],vals[0][1]]):
    a.text(i-w/2,v+.02,"%.3f"%v,ha="center",fontsize=9,color=V.S1,fontweight="600")
for i,v in enumerate([vals[1][0],vals[1][1]]):
    a2.text(i+w/2,v+10,"%.0f"%v,ha="center",fontsize=9,color=V.S2,fontweight="600")
a.set_title("The same model, scored two ways\nNight rows flatter it by 5.5 R² points")

# 3. daily aggregation
a=ax[2]
dd=te.groupby(te.ts.dt.date).agg(act=(T,lambda s:s.sum()*5/60/1000),
                                 pred=("pred",lambda s:s.sum()*5/60/1000))
a.scatter(dd.pred,dd.act,s=13,color=V.S1,alpha=.5,linewidths=0)
lim=[0,max(dd.act.max(),dd.pred.max())*1.04]
a.plot(lim,lim,color=V.INK2,ls=(0,(4,3)),lw=1.3); a.set_xlim(lim); a.set_ylim(lim)
a.set_xlabel("predicted daily energy (kWh)"); a.set_ylabel("actual (kWh)")
a.set_title("Daily totals: R² %.3f, MAE %.2f kWh\nInterval errors cancel on aggregation"
            %(r2_score(dd.act,dd.pred),mean_absolute_error(dd.act,dd.pred)))

fig.suptitle("Does cleaning make a better production model?",x=.008,ha="left",
             fontsize=14,fontweight="600")
fig.tight_layout(rect=[0,0,1,.945])
fig.savefig(OUT+"/28_ml_comparison.png"); plt.close(fig)
print("  28_ml_comparison")
