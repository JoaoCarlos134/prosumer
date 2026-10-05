# -*- coding: utf-8 -*-
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, json, os, matplotlib.pyplot as plt
import vizstyle as V; V.setup()
OUT=caminho("figs_curitiba"); os.makedirs(OUT,exist_ok=True)
f=pd.read_parquet(caminho("curitiba_frame5.parquet")); f["ts"]=pd.to_datetime(f.timestamp)
M=json.load(open(caminho("curitiba_meta.json")))
def save(fig,n): fig.savefig(caminho("figs_curitiba/"+n+".png")); plt.close(fig); print("  ",n)

hi=f[(f.cosz>.2)&(f.d_Kt>=.6)&(f.i1>1)&(f.i2>1)].copy()
hi["ym"]=hi.ts.dt.to_period("M").dt.to_timestamp()
m=hi.groupby("ym").agg(in1=("in1","median"),in2=("in2","median"),
                       v1=("v1","median"),v2=("v2","median"),n=("v1","size"))
m=m[m.n>=40]
b1,b2=m.loc[:"2021-11","in1"].median(),m.loc[:"2021-11","in2"].median()

# ---- R1: the string-specific fault ----
fig,ax=plt.subplots(figsize=(11,4.6))
ax.plot(m.index,100*(m.in1/b1-1),color=V.S8,lw=2.2,label="MPP1 current (irradiance-normalised)")
ax.plot(m.index,100*(m.in2/b2-1),color=V.S1,lw=2.2,label="MPP2 current")
ax.axhline(0,color=V.INK2,lw=1)
ax.axvspan(pd.Timestamp("2022-12-01"),pd.Timestamp("2023-08-01"),color=V.S8,alpha=.09,lw=0)
ax.axvline(pd.Timestamp("2023-08-01"),color=V.S3,lw=1.6,ls=(0,(4,3)))
ax.annotate("MPP1 fault\nMPP1 −50%, MPP2 −18%",(pd.Timestamp("2023-02-01"),-47),
            fontsize=9.5,color=V.S8,ha="center",fontweight="600")
ax.annotate("repaired",(pd.Timestamp("2023-08-05"),18),fontsize=9.5,color=V.S3,fontweight="600")
ax.axvline(pd.Timestamp("2025-06-01"),color=V.S2,lw=1.6,ls=(0,(4,3)))
ax.annotate("strings\nrewired",(pd.Timestamp("2025-06-10"),-40),fontsize=9.5,color=V.S2,fontweight="600")
ax.set_ylabel("% vs the 2021 baseline"); ax.legend(loc="lower right")
ax.set_title("Two MPPT inputs turn a guess into a diagnosis: one string failed, not the plant")
save(fig,"R1_string_fault")

# ---- R2: the June 2025 rewiring ----
fig,ax=plt.subplots(figsize=(10,4.3))
ax.plot(m.index,m.v1,color=V.S8,lw=2.2,label="MPP1 string voltage")
ax.plot(m.index,m.v2,color=V.S1,lw=2.2,label="MPP2 string voltage")
ax.plot(m.index,(m.v1+m.v2)/2,color=V.MUTED,lw=1.4,ls=(0,(4,3)),label="mean of the two")
ax.axvline(pd.Timestamp("2025-06-01"),color=V.S2,lw=1.8,ls=(0,(4,3)))
ax.annotate("Jun 2025: modules moved\nbetween the two inputs\n(sum unchanged, DC power +15%)",
            (pd.Timestamp("2025-06-10"),505),fontsize=9.5,color=V.S2,fontweight="600",va="top")
ax.set_ylabel("V$_{mp}$ (V)"); ax.legend(loc="lower left",ncol=3,fontsize=8.5)
ax.set_title("A rewiring visible only in the voltage channels")
save(fig,"R2_rewiring")

# ---- R3: morning/afternoon asymmetry ----
cl=f[(f.cosz>.15)&(f.d_Kt>=.62)&(f.i1>.2)].copy()
cl["side"]=np.where(cl.solar_time<12.25,"AM","PM")
bins=[10,20,30,40,50,60,75]; ctr=[(bins[i]+bins[i+1])/2 for i in range(len(bins)-1)]
cl["eb"]=pd.cut(cl.elev,bins)
fig,axes=plt.subplots(1,2,figsize=(11.6,4.3))
a=axes[0]
for k,c,lab in ((1,V.S8,"MPP1"),(2,V.S1,"MPP2")):
    p=cl.pivot_table(index="eb",columns="side",values="in%d"%k,aggfunc="median",observed=True)
    a.plot(ctr,(p.PM/p.AM).values,marker="o",ms=7,color=c,lw=2.2,mec=V.SURF,mew=1.3,label=lab)
a.axhline(1,color=V.INK2,lw=1.2,ls=(0,(4,3)))
a.set_xlabel("solar elevation (°)"); a.set_ylabel("afternoon / morning current")
a.set_title("The two strings are mirror images at low sun"); a.legend()
a.annotate("unshaded, symmetric",(62,1.02),fontsize=8.5,color=V.INK2)
a=axes[1]
seas={"summer\nDJF":[12,1,2],"autumn\nMAM":[3,4,5],"winter\nJJA":[6,7,8],"spring\nSON":[9,10,11]}
L=list(seas); r1=[];r2=[]
for lab,mm in seas.items():
    s=cl[cl.month.isin(mm)&cl.elev.between(15,40)]
    r1.append(s[s.side=="PM"].in1.median()/s[s.side=="AM"].in1.median())
    r2.append(s[s.side=="PM"].in2.median()/s[s.side=="AM"].in2.median())
x=np.arange(4); w=.36
a.bar(x-w/2,r1,w,color=V.S8,label="MPP1"); a.bar(x+w/2,r2,w,color=V.S1,label="MPP2")
a.axhline(1,color=V.INK2,lw=1.2,ls=(0,(4,3)))
a.set_xticks(x); a.set_xticklabels(L,fontsize=9); a.set_ylabel("afternoon / morning current")
a.set_title("and the deficit is strongly seasonal"); a.legend()
fig.suptitle("Curitiba: mornings are obstructed, and not equally for both strings",
             x=.008,ha="left",fontsize=13.5,fontweight="600")
fig.tight_layout(rect=[0,0,1,.93]); save(fig,"R3_asymmetry")

# ---- R4: the two sites ----
A=pd.read_parquet(caminho("frame5.parquet")); A["ts"]=pd.to_datetime(A.timestamp)
MA=json.load(open(caminho("meta.json")))
fig,axes=plt.subplots(1,3,figsize=(13.6,4.2))
a=axes[0]
da=pd.read_csv(caminho("nasa_power_true.csv"),index_col=0,parse_dates=True)
dc=pd.read_csv(caminho("nasa_power_curitiba_daily.csv"),index_col=0,parse_dates=True)
ov=da.index.intersection(dc.index)
MON=["J","F","M","A","M","J","J","A","S","O","N","D"]
ga=da.loc[ov,"ALLSKY_SFC_SW_DWN"].groupby(ov.month).mean()
gc=dc.loc[ov,"ALLSKY_SFC_SW_DWN"].groupby(ov.month).mean()
a.plot(range(1,13),ga.values,marker="o",ms=6,color=V.S2,lw=2.2,label="Cascavel")
a.plot(range(1,13),gc.values,marker="o",ms=6,color=V.S1,lw=2.2,label="Curitiba")
a.set_xticks(range(1,13)); a.set_xticklabels(MON); a.set_ylabel("GHI (kWh/m²·d)")
a.set_title("Curitiba gets %.0f%% less sun"%(100*(1-gc.mean()/ga.mean()))); a.legend()
a=axes[1]
qa=A[(A.poa_cs>700)&(A.d_Kt>=.62)&A.p_ac.notna()]
qr=f[(f.poa_cs>700)&(f.d_Kt>=.62)&f.p_ac.notna()]
a.bar([0,1],[qa.pi.median(),qr.pi.median()],color=[V.S2,V.S1],width=.55)
for i,v in enumerate([qa.pi.median(),qr.pi.median()]):
    a.text(i,v+.012,"%.2f"%v,ha="center",fontsize=11,fontweight="600",color=V.INK)
a.set_xticks([0,1]); a.set_xticklabels(["Cascavel\n3.96 kWp","Curitiba\n~9.6 kWp"],fontsize=9)
a.set_ylabel("performance index, clear days"); a.set_ylim(0,0.95)
a.set_title("Curitiba converts it less well too")
a=axes[2]
ya=[1603,1516,1345,1254,1402,1451]; yrs=[2020,2021,2022,2023,2024,2025]
yr_r=f[f.p_ac.notna()].groupby(f[f.p_ac.notna()].ts.dt.year).agg(
    E=("p_ac",lambda s:s.sum()*5/60/1000),d=("date","nunique"))
yr_r=yr_r[yr_r.d>350]
a.plot(yrs,ya,marker="o",ms=6,color=V.S2,lw=2.2,label="Cascavel (3.96 kWp)")
a.plot(yr_r.index,(yr_r.E/M["cap_total_kwp"]).values,marker="o",ms=6,color=V.S1,lw=2.2,
       label="Curitiba (~9.6 kWp est.)")
a.set_ylabel("specific yield (kWh/kWp·yr)"); a.legend(fontsize=8.5)
a.set_title("Specific yield")
fig.suptitle("Two plants, 380 km apart",x=.008,ha="left",fontsize=13.5,fontweight="600")
fig.tight_layout(rect=[0,0,1,.93]); save(fig,"R4_sites")
print("done")
