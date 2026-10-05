# -*- coding: utf-8 -*-
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import numpy as np, pandas as pd, os, json, matplotlib.pyplot as plt
import vizstyle as V; V.setup()
OUT=caminho("figs5"); os.makedirs(OUT,exist_ok=True)

f = pd.read_parquet(caminho("frame5.parquet")); f["ts"]=pd.to_datetime(f.timestamp)
f["night"]=f.cosz<=0
d = f[~f.night]

fig,ax = plt.subplots(2,2,figsize=(12.4,8.0))

# 1. missingness against sun elevation
a=ax[0,0]
bins=np.arange(-20,91,5)
gr=f.groupby(pd.cut(f.elev,bins),observed=True).agg(miss=("p_ac",lambda s:100*s.isna().mean()),n=("p_ac","size"))
ctr=[(bins[i]+bins[i+1])/2 for i in range(len(bins)-1)][:len(gr)]
a.bar(ctr,gr.miss.values,width=4.2,color=[V.S8 if c<0 else V.S1 for c in ctr])
a.axvline(0,color=V.INK2,lw=1.2)
a.set_ylim(0,96)
a.annotate("sun below horizon",(-19.5,88),fontsize=9,color=V.S8,ha="left",fontweight="600")
a.annotate("daylight: 1.1% missing",(45,26),fontsize=9,color=V.S1,ha="center",fontweight="600")
a.set_xlabel("solar elevation (°)"); a.set_ylabel("rows with no measurement (%)")
a.set_title("Missingness is night, not loss")

# 2. inverter efficiency distribution
a=ax[0,1]
e=d.eta_inv.dropna(); e=e[e.between(0.5,1.3)]
a.hist(e,bins=120,color=V.S1,alpha=.85)
a.axvline(1.0,color=V.S8,lw=2)
share=100*(d.eta_inv.dropna()>1).mean()
a.annotate("%.0f%% of intervals sit\nabove 1.0 — impossible"%share,(1.02,a.get_ylim()[1]*.72),
           fontsize=9.5,color=V.S8,fontweight="600")
a.set_xlabel("AC power / DC power per interval"); a.set_ylabel("intervals")
a.set_title("The DC and AC channels are not simultaneous")

# 3. autocorrelation
a=ax[1,0]
s=d.set_index("ts").pi.resample("5min").mean().dropna()
lags=[1,2,3,6,12,24,48,144,288,288*3,288*7]
acf=[s.autocorr(l) for l in lags]
a.plot([l*5/60 for l in lags],acf,marker="o",ms=7,color=V.S1,lw=2.2,mec=V.SURF,mew=1.3)
a.set_xscale("log"); a.axhline(0.5,color=V.S8,ls=(0,(4,3)),lw=1.4)
a.axhline(0,color=V.INK2,lw=1)
a.annotate("drops below 0.5\nafter ~1 hour",(1.0,0.52),fontsize=9.5,color=V.S8,fontweight="600",
           xytext=(6,8),textcoords="offset points")
a.set_xlabel("lag (hours, log scale)"); a.set_ylabel("autocorrelation of the target")
a.set_title("367k rows, ~31k independent blocks")

# 4. drift
a=ax[1,1]
m=d.set_index("ts").pi.resample("MS").median()
a.plot(m.index,m.values,color=V.S1,lw=2)
seg=pd.read_csv(caminho("segments.csv"),parse_dates=["start","end"])
for _,sg in seg.iterrows():
    if sg.pr<0.82: a.axvspan(sg.start,sg.end+pd.offsets.MonthEnd(1),color=V.S8,alpha=.08,lw=0)
a.set_ylabel("median performance index"); a.set_xlabel("")
a.set_title("The target is non-stationary: train ≠ deploy")
a.annotate("soiled periods shaded",(m.index[int(len(m)*.42)],m.min()*1.02),fontsize=9,color=V.S8)

fig.suptitle("Data quality for modelling — 694,488 five-minute records",
             x=.008,ha="left",fontsize=14,fontweight="600")
fig.tight_layout(rect=[0,0,1,.955])
fig.savefig(OUT+"/27_data_quality.png"); plt.close(fig)
print("  27_data_quality")

summary = dict(
  rows_total=int(len(f)), rows_daylight=int(len(d)),
  missing_daylight_pct=round(100*float(d.p_ac.isna().mean()),3),
  missing_night_pct=round(100*float(f[f.night].p_ac.isna().mean()),2),
  days_spanned=int(f.ts.dt.date.nunique()), days_absent=0, intraday_gaps=0,
  duplicate_ts=982, duplicate_conflicts=0,
  over_rating_rows=int((f.p_ac>4000).sum()), over_rating_days=int(f[f.p_ac>4000].ts.dt.date.nunique()),
  eta_gt1_pct=round(float(share),2),
  subhorizon_rows=int((f.night&(f.p_ac>10)).sum()),
  frozen_runs=2,
  retained_after_cleaning=362949,
  retained_pct_of_daylight=98.86,
  acf_5min=round(float(s.autocorr(1)),3), acf_1h=round(float(s.autocorr(12)),3),
  acf_1d=round(float(s.autocorr(288)),3),
  independent_weather_obs=2558,
  leak_columns=["energia_Wh","producao_fotovoltaica_Wh","rendimento_especifico_kWh_kWp",
                "potencia_aparente_VA x fator_potencia","corrente_ca_l1_A x voltagem_ca_l1_V"],
)
json.dump(summary, open(caminho("dq_summary.json"),"w"), indent=1)
print(json.dumps(summary, indent=1))
