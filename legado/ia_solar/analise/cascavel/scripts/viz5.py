# -*- coding: utf-8 -*-
"""Figures for the 5-minute analysis."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, os, matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
import solar, vizstyle as V; V.setup()

OUT = caminho("figs5"); os.makedirs(OUT, exist_ok=True)
LAT = -24.83; D2R = np.pi/180
f = pd.read_parquet(caminho("frame5.parquet")); f["ts"] = pd.to_datetime(f.timestamp)
seg = pd.read_csv(caminho("segments.csv"), parse_dates=["start","end"])
def save(fig,n): fig.savefig(OUT+"/"+n+".png"); plt.close(fig); print("  ",n)

# ---------- 21 azimuth: daily degeneracy vs 5-minute identifiability ----------
q = f[(f.cosz>0.15)&(f.d_Kt>=0.62)&f.healthy&(f.p_ac>0)&(f.p_ac<4200)&f.p_ac.notna()]
decl,omega,cosz,doy = q.decl.values,q.omega.values,q.cosz.values,q.doy.values
czp=np.clip(cosz,.02,None); ghi=1098.*czp*np.exp(-.059/czp)
I0=1367.*(1+.033*np.cos(2*np.pi*doy/365.))*czp; kt=ghi/I0
kd=np.clip(np.where(kt<=.22,1-.09*kt,np.where(kt<=.8,.9511-.1604*kt+4.388*kt**2-16.638*kt**3+12.336*kt**4,.165)),0,1)
dif=ghi*kd; bea=np.clip(ghi-dif,0,None); Ai=np.clip(bea/I0,0,1); fb=np.sqrt(np.clip(bea/np.where(ghi>0,ghi,1),0,None))
P=q.p_ac.values
def r2_5(b,g):
    ci=np.clip(solar.cos_incidence(LAT,decl,omega,b,g),0,None)
    p=((bea+dif*Ai)*(ci/czp)+dif*(1-Ai)*((1+np.cos(b*D2R))/2)*(1+fb*np.sin(b*D2R/2)**3)+ghi*.16*((1-np.cos(b*D2R))/2))
    return np.corrcoef(p,P)[0,1]**2
d=pd.read_csv(caminho("master.csv"),index_col=0,parse_dates=True)
v=d.dropna(subset=["H","Hd","T2M","e_kwh"])
n_,H_,Hd_=v.n.values.astype(float),v.H.values,v.Hd.values
alb=v.ALLSKY_SRF_ALB.fillna(.16).values; E_=v.e_kwh.values
def r2_d(b,g):
    return np.corrcoef(solar.poa_daily(LAT,n_,H_,Hd_,b,g,albedo=alb)["poa"],E_)[0,1]**2
G=np.arange(110,251,5.)
rd=np.array([r2_d(13,g) for g in G]); r5=np.array([r2_5(13,g) for g in G])
fig,axes=plt.subplots(1,2,figsize=(11.6,4.4))
for ax,y,ttl,col in [(axes[0],rd,"Daily totals — azimuth is invisible",V.MUTED),
                     (axes[1],r5,"5-minute profile — azimuth is resolved",V.S1)]:
    ax.plot(G,y,color=col,lw=2.4)
    ax.axvline(180,color=V.GRID,lw=1.2,ls=(0,(2,3)))
    ax.axvline(205,color=V.S3,lw=2,ls=(0,(5,3)))
    ax.plot(G[y.argmax()],y.max(),marker="o",ms=8,color=col,mec=V.SURF,mew=1.5,zorder=5)
    ax.set_xlabel("azimuth (°), tilt fixed at 13°"); ax.set_ylabel("R² of energy vs modelled POA")
    ax.set_title(ttl)
axes[0].annotate("R²(155)=R²(205)\nexactly equal",(155,r2_d(13,155)),fontsize=9,color=V.INK2,
                 xytext=(0,-34),textcoords="offset points",ha="center")
axes[0].axvline(155,color=V.S8,lw=1.4,ls=(0,(3,3)))
axes[1].annotate("datasheet 205°\n(25° E of N)",(205,r5[np.argmin(abs(G-205))]),fontsize=9.5,
                 color=V.S3,fontweight="600",xytext=(8,-28),textcoords="offset points")
axes[1].annotate("fit peaks 202.5°",(G[r5.argmax()],r5.max()),fontsize=9,color=V.S1,
                 fontweight="600",xytext=(-8,10),textcoords="offset points",ha="right")
fig.suptitle("The degeneracy that daily data could not break",x=.008,ha="left",fontsize=13.5,fontweight="600")
fig.tight_layout(rect=[0,0,1,.94]); save(fig,"21_azimuth_resolved")

# ---------- 22 fault fingerprint: voltage vs current ----------
hi=f[(f.poa_cs>700)&(f.d_Kt>=0.62)&(f.p_ac>200)&(f.p_ac<4200)&(f.i_dc>0.3)&(f.v_dc>100)].copy()
hi["i_norm"]=hi.i_dc/(hi.poa_cs/1000.); hi["ym"]=hi.ts.dt.to_period("M").dt.to_timestamp()
g=hi.groupby("ym").agg(i=("i_norm","median"),v=("v_dc","median"),n=("i_norm","size")); g=g[g.n>=50]
base_i=g.loc[:"2021-04","i"].median(); base_v=g.loc[:"2021-04","v"].median()
fig,ax=plt.subplots(figsize=(11,4.6))
ax.plot(g.index,100*(g.i/base_i-1),color=V.S8,lw=2.2,label="DC current (irradiance-normalised)")
ax.plot(g.index,100*(g.v/base_v-1),color=V.S1,lw=2.2,label="DC string voltage")
ax.axhline(0,color=V.INK2,lw=1)
for _,s in seg.iterrows():
    if s.pr<0.82: ax.axvspan(s.start,s.end+pd.offsets.MonthEnd(1),color=V.S8,alpha=.06,lw=0)
for c in ["2023-11-01","2024-09-01"]:
    ax.axvline(pd.Timestamp(c),color=V.S3,lw=1.6,ls=(0,(4,3)))
ax.annotate("cleaning",(pd.Timestamp("2023-11-01"),-22),color=V.S3,fontsize=9.5,fontweight="600",
            xytext=(6,0),textcoords="offset points")
ax.annotate("cleaning",(pd.Timestamp("2024-09-01"),-22),color=V.S3,fontsize=9.5,fontweight="600",
            xytext=(6,0),textcoords="offset points")
ax.set_ylabel("% vs the 2019-21 healthy baseline"); ax.set_ylim(-26,10)
ax.legend(loc="lower left")
ax.set_title("Current collapses, voltage never does — the string is intact, the glass is not")
save(fig,"22_fault_fingerprint")

# ---------- 23 recovery factor vs sun elevation ----------
q2=f[(f.d_Kt>=0.60)&(f.poa_cs>150)&(f.p_ac>0)&(f.p_ac<4200)&f.i_dc.notna()&(f.elev>5)].copy()
q2["i_norm"]=q2.i_dc/(q2.poa_cs/1000.)
be=q2[(q2.ts>="2023-08-15")&(q2.ts<"2023-11-01")]; af=q2[(q2.ts>="2023-11-01")&(q2.ts<"2024-01-15")]
bins=[5,15,25,35,45,55,65,90]; ctr=[(bins[i]+bins[i+1])/2 for i in range(len(bins)-1)]
bi=be.groupby(pd.cut(be.elev,bins),observed=True).i_norm.median()
ai=af.groupby(pd.cut(af.elev,bins),observed=True).i_norm.median()
rat=(ai/bi).values
fig,axes=plt.subplots(1,2,figsize=(11.6,4.3))
ax=axes[0]
ax.plot(ctr,bi.values,marker="o",ms=7,color=V.S8,lw=2,mec=V.SURF,mew=1.3,label="before (Aug–Oct 2023)")
ax.plot(ctr,ai.values,marker="o",ms=7,color=V.S3,lw=2,mec=V.SURF,mew=1.3,label="after (Nov 2023–Jan 2024)")
ax.set_xlabel("solar elevation (°)"); ax.set_ylabel("DC current per kW/m² (A)")
ax.set_title("Same array, six weeks apart"); ax.legend(loc="lower right")
ax=axes[1]
ax.plot(ctr,100*(rat-1),marker="o",ms=8,color=V.S1,lw=2.4,mec=V.SURF,mew=1.4)
ax.axhline(100*(rat[-1]-1),color=V.MUTED,ls=(0,(4,3)),lw=1.2)
ax.annotate("+%.0f%% at high sun"%(100*(rat[-1]-1)),(ctr[-1],100*(rat[-1]-1)),fontsize=9,
            color=V.INK2,xytext=(-4,-16),textcoords="offset points",ha="right")
ax.annotate("+%.0f%% at low sun"%(100*(rat[0]-1)),(ctr[0],100*(rat[0]-1)),fontsize=9.5,
            color=V.S1,fontweight="600",xytext=(6,2),textcoords="offset points")
ax.set_xlabel("solar elevation (°)"); ax.set_ylabel("current recovered by the cleaning (%)")
ax.set_title("Recovery is largest at oblique incidence")
fig.suptitle("The optical signature of soiling, not of an obstruction",x=.008,ha="left",
             fontsize=13.5,fontweight="600")
fig.tight_layout(rect=[0,0,1,.93]); save(fig,"23_soiling_signature")

# ---------- 24 inverter efficiency curve ----------
e=f[(f.p_dc>40)&(f.p_dc<4300)&(f.p_ac>0)&(f.p_ac<4200)&f.eta_inv.between(.3,1.02)].copy()
e["load"]=100*e.p_dc/4000.
bb=[0,2,5,10,20,30,50,70,90,110]
gg=e.groupby(pd.cut(e.load,bb),observed=True).agg(eta=("eta_inv","median"),n=("eta_inv","size"),
                                                  en=("p_ac","sum"))
ctr2=[(bb[i]+bb[i+1])/2 for i in range(len(bb)-1)]
fig,ax=plt.subplots(figsize=(8.6,4.4))
ax.plot(ctr2,100*gg.eta.values,marker="o",ms=8,color=V.S1,lw=2.4,mec=V.SURF,mew=1.4)
ax2=ax.twiny(); ax2.set_xlim(ax.get_xlim()); ax2.set_xticks([]); ax2.grid(False)
share=100*gg.en.values/gg.en.sum()
for x,y,s in zip(ctr2,100*gg.eta.values,share):
    ax.annotate("%.0f%% of\nenergy"%s,(x,y),fontsize=7.5,color=V.MUTED,ha="center",
                xytext=(0,-24),textcoords="offset points")
w=np.average(e.eta_inv,weights=e.p_ac)
ax.axhline(100*w,color=V.S2,ls=(0,(4,3)),lw=1.6)
ax.annotate("energy-weighted %.2f%%"%(100*w),(95,100*w),fontsize=9.5,color=V.S2,
            fontweight="600",ha="right",xytext=(0,6),textcoords="offset points")
ax.set_xlabel("inverter loading (% of 4.0 kW AC)"); ax.set_ylabel("conversion efficiency (%)")
ax.set_ylim(70,102)
ax.set_title("Inverter conversion accounts for only 1.5% of the loss budget")
save(fig,"24_inverter_efficiency")

# ---------- 25 NASA POWER vs the physical clear-sky reference ----------
dd=f[(f.p_ac>=0)&(f.p_ac<4200)].groupby("date").agg(
    poa_cs=("poa_cs",lambda s:s.sum()*5/60/1000), n=("p_ac","size"),
    d_poa=("d_poa","first"), d_Kt=("d_Kt","first"), month=("month","first"))
dd=dd[(dd.n>100)&dd.d_poa.notna()]; cl=dd[dd.d_Kt>=0.65].copy()
cl["ratio"]=cl.d_poa/cl.poa_cs
fig,axes=plt.subplots(1,2,figsize=(11.6,4.3))
ax=axes[0]
ax.scatter(cl.poa_cs,cl.d_poa,s=9,color=V.S1,alpha=.45,linewidths=0,rasterized=True)
lim=[cl.poa_cs.min()*.95,cl.poa_cs.max()*1.03]
ax.plot(lim,lim,color=V.INK2,ls=(0,(4,3)),lw=1.3)
r=stats.linregress(cl.poa_cs,cl.d_poa); xs=np.linspace(*lim,20)
ax.plot(xs,r.intercept+r.slope*xs,color=V.S2,lw=2)
ax.set_xlabel("physical clear-sky POA (kWh/m²·d)"); ax.set_ylabel("NASA POWER POA (kWh/m²·d)")
ax.set_title("Clear days: POWER reads %.1f%% low"%(100*(1-cl.ratio.median())))
ax=axes[1]
MON=["J","F","M","A","M","J","J","A","S","O","N","D"]
gm=cl.groupby("month").ratio.median()
ax.bar([MON[i-1] for i in gm.index],100*(gm.values/cl.ratio.median()-1),
       color=[V.S8 if abs(x)>1 else V.S1 for x in 100*(gm.values/cl.ratio.median()-1)],width=.64)
ax.axhline(0,color=V.INK2,lw=1)
ax.set_ylabel("deviation of the POWER/clear-sky ratio (%)")
ax.set_title("and its error has a seasonal cycle")
fig.suptitle("Calibrating NASA POWER against the plant itself",x=.008,ha="left",
             fontsize=13.5,fontweight="600")
fig.tight_layout(rect=[0,0,1,.93]); save(fig,"25_power_bias")

# ---------- 26 average day by regime ----------
q3=f[(f.d_Kt>=0.65)&(f.poa_cs>50)&(f.p_ac>=0)&(f.p_ac<4200)&(f.elev>3)].copy()
q3["st"]=(q3.solar_time*4).round()/4
fig,ax=plt.subplots(figsize=(10,4.6))
for i,s in seg.iterrows():
    d=q3[q3.regime==i]
    if len(d)<400: continue
    p=d.groupby("st").p_ac.median()
    p=p[d.groupby("st").size()>=15]
    ax.plot(p.index,p.values,lw=2.2,color=(V.S3 if s.pr>=.82 else V.S8),alpha=.9,
            label="%s–%s  PR %.2f"%(s.start.strftime("%b %y"),s.end.strftime("%b %y"),s.pr))
cs=q3.groupby("st").poa_cs.median()*3.96
ax.plot(cs.index,cs.values,color=V.INK2,lw=1.4,ls=(0,(4,3)),label="clear-sky reference × 3.96 kWp")
ax.set_xlabel("solar time (h)"); ax.set_ylabel("AC power (W)")
ax.set_xlim(5.5,18.5)
ax.legend(fontsize=8.5,loc="upper right",ncol=2)
ax.set_title("Median clear-day power curve by regime — the whole curve sags, evenly")
save(fig,"26_day_curves")
print("done")
