"""Vitrine LOCAL do uso prolongado (18/11/2026): o piloto V11 nas duas usinas, para a apresentacao do TCC.

Le as saidas IGNORADAS do `piloto_uso_prolongado.py` (dados de usina: nunca no git) e escreve uma pagina HTML
autonoma (abre sem internet; ECharts copiado do webapp) em resultados/pilotos/vitrine_local/ (gitignored).
Nunca publicar essa pasta nem hospedar a pagina: as curvas por dia sao dados das usinas.

  python experimentos/testes_previsao/scripts/vitrine_uso_prolongado.py     (depois do `avalia` do piloto)
"""

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from piloto_comum import PILOTOS  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
SAIDA = PILOTOS / "vitrine_local"
ECHARTS = RAIZ / "webapp/web/node_modules/echarts/dist/echarts.min.js"
INICIO_EXEMPLO = pd.Timestamp("2024-09-01")      # o primeiro inicio do piloto: o ano de uso mais longo
SERIES = ["Cascavel", "Curitiba"]


def _dados(serie):
    rel = json.loads((PILOTOS / "uso_prolongado.json").read_text(encoding="utf-8"))
    v = {n: pd.read_parquet(PILOTOS / f"uso_prolongado_{n}__usinas__{serie}.parquet") for n in ("L", "LB")}
    for d in v.values():
        d["ini"] = d.alvo - pd.to_timedelta(d.uso - 1, unit="D")
    lb = v["LB"]
    ex = lb[(lb.ini == INICIO_EXEMPLO) & (lb.lead == 1)].sort_values("alvo")
    dia = dict(x=ex.alvo.dt.strftime("%Y-%m-%d").tolist(), real=ex.Y.round(2).tolist(),
               hoje=ex.F.round(2).tolist(), aprende=ex.Yhat.round(2).tolist(),
               lo=ex.lo_v.round(2).tolist(), hi=ex.hi_v.round(2).tolist())
    m = ex.assign(mes=ex.alvo.dt.to_period("M")).groupby("mes")
    cont = m.size()
    mm = m[["Y", "F", "Yhat"]].sum()[cont >= 26]
    mes = dict(x=[str(p) for p in mm.index], real=mm.Y.round(0).tolist(), hoje=mm.F.round(0).tolist(),
               aprende=mm.Yhat.round(0).tolist(),
               erro_hoje=((mm.F - mm.Y) / mm.Y * 100).round(1).tolist(),
               erro_aprende=((mm.Yhat - mm.Y) / mm.Y * 100).round(1).tolist())
    aprendeu = {}
    for k in (1, 4, 7):                                 # cada lead com as PROPRIAS datas (lead k comeca k-1 dias depois)
        q = lb[(lb.ini == INICIO_EXEMPLO) & (lb.lead == k)].sort_values("alvo")
        datas = q.alvo.dt.strftime("%Y-%m-%d").tolist()
        aprendeu[f"lead{k}"] = dict(a=[[d, round(x, 3)] for d, x in zip(datas, q.a)],
                                    b=[[d, round(x, 3)] for d, x in zip(datas, q.b)])
    curva = {}
    for n in ("L", "LB"):
        r = rel["variantes"][f"{n}|{serie}"]
        curva[n] = {f: dict(hoje=r["a_mais_b"][f"lead1_{f}"]["skill_F"], aprende=r["a_mais_b"][f"lead1_{f}"]["skill_v"])
                    for f in ("1-30", "31-90", "91-180", "181-365") if f"lead1_{f}" in r["a_mais_b"]}
    erro = rel["variantes"][f"LB|{serie}"]["erro_pct_lead1"]
    return dict(serie=serie, dia=dia, mes=mes, aprendeu=aprendeu, curva=curva, erro=erro,
                portao=rel["portao_resultado"])


PAGINA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Uso prolongado - vitrine local</title>
<script src="echarts.min.js"></script><style>
body{font-family:system-ui,sans-serif;margin:0;background:#f3f4f6;color:#111}
header{background:#0f3d5c;color:#fff;padding:20px 24px}h1{margin:0;font-size:22px}
header p{margin:6px 0 0;opacity:.85}main{max-width:1200px;margin:auto;padding:16px}
.tile{background:#fff;border-radius:12px;box-shadow:0 1px 3px #0002;padding:16px;margin:14px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.kpi{background:#fff;border-radius:12px;box-shadow:0 1px 3px #0002;padding:14px}.kpi b{font-size:26px;display:block}
.chart{height:340px}h2{font-size:16px;margin:0 0 8px}select{font-size:15px;padding:4px}
small{color:#555}</style></head><body>
<header><h1>Previsao da geracao com o uso prolongado</h1>
<p>Replay causal: o aplicativo previu toda noite o dia seguinte so com o que sabia, e aprendeu com o proprio erro.
Vitrine LOCAL com dados reais das usinas, nao publicar.</p></header><main>
<label>Usina: <select id="sel"></select></label>
<div class="kpis" id="kpis"></div>
<div class="tile"><h2>Total do dia: previsto x medido (lead 1, uso a partir de 01/09/2024)</h2>
<small>Faixa = 80% do aprendizado. "Hoje" = o aplicativo atual; "aprendendo" = ajusta confianca, vies e faixa com o proprio erro.</small>
<div class="chart" id="c_dia" style="height:380px"></div></div>
<div class="tile"><h2>Total do mes: previsto x medido, erro em %</h2><div class="chart" id="c_mes"></div></div>
<div class="tile"><h2>Curva de aprendizado: skill do total do dia (lead 1) por dias de uso</h2>
<small>Skill = 1 - erro / erro da media sazonal; media dos 8 inicios do piloto. L = so o que previu desde a instalacao;
LB = tambem o historico do arquivo.</small><div class="chart" id="c_curva"></div></div>
<div class="tile"><h2>O que o aplicativo aprendeu: confianca no tempo (a) e vies (b)</h2>
<div class="chart" id="c_aprendeu"></div></div>
</main><script>
const D = __DADOS__;
const sel = document.getElementById('sel'); D.forEach((d,i)=>sel.add(new Option('Usina '+d.serie,i)));
const charts = {}; const ch = id => charts[id] || (charts[id] = echarts.init(document.getElementById(id)));
const pct = v => (v*100).toFixed(0)+'%';
function desenha(i){
 const d = D[i], e = d.erro;
 const k = (t,v,s)=>`<div class="kpi"><small>${t}</small><b>${v}</b><small>${s||''}</small></div>`;
 const mes = e['mes_91-180']||{}, sem = e['semana_91-180']||{}, dia = e['alvo_91-180']||{};
 document.getElementById('kpis').innerHTML =
  k('Erro do total do mes', pct(mes.v||NaN), 'hoje: '+pct(mes.F||NaN)+' | uso 91-180 dias') +
  k('Erro do total da semana', pct(sem.v||NaN), 'hoje: '+pct(sem.F||NaN)) +
  k('Erro do total do dia', pct(dia.v||NaN), 'hoje: '+pct(dia.F||NaN)) +
  k('Dias com erro ate 10%', pct(dia.dias_ate_10pct_v||NaN), 'hoje: '+pct(dia.dias_ate_10pct_F||NaN));
 ch('c_dia').setOption({tooltip:{trigger:'axis'},legend:{top:0},grid:{left:50,right:20,top:30,bottom:60},
  dataZoom:[{type:'slider'},{type:'inside'}],xAxis:{type:'category',data:d.dia.x},yAxis:{name:'kWh/dia'},
  series:[{name:'faixa',type:'line',data:d.dia.lo,stack:'b',lineStyle:{opacity:0},symbol:'none'},
   {name:'faixa 80%',type:'line',data:d.dia.hi.map((h,j)=>h-d.dia.lo[j]),stack:'b',lineStyle:{opacity:0},
    areaStyle:{color:'#93c5fd55'},symbol:'none'},
   {name:'medido',type:'line',data:d.dia.real,symbol:'none',lineStyle:{color:'#111',width:1.5}},
   {name:'hoje',type:'line',data:d.dia.hoje,symbol:'none',lineStyle:{color:'#9ca3af',width:1}},
   {name:'aprendendo',type:'line',data:d.dia.aprende,symbol:'none',lineStyle:{color:'#ea580c',width:1.5}}]},true);
 ch('c_mes').setOption({tooltip:{trigger:'axis'},legend:{top:0},grid:{left:60,right:20,top:30,bottom:30},
  xAxis:{type:'category',data:d.mes.x},yAxis:{name:'kWh/mes'},
  series:[{name:'medido',type:'bar',data:d.mes.real,itemStyle:{color:'#374151'}},
   {name:'hoje',type:'bar',data:d.mes.hoje,itemStyle:{color:'#9ca3af'},label:{show:true,position:'top',fontSize:9,
    formatter:p=>d.mes.erro_hoje[p.dataIndex]+'%'}},
   {name:'aprendendo',type:'bar',data:d.mes.aprende,itemStyle:{color:'#ea580c'},label:{show:true,position:'top',
    fontSize:9,formatter:p=>d.mes.erro_aprende[p.dataIndex]+'%'}}]},true);
 const fx = ['1-30','31-90','91-180','181-365'];
 ch('c_curva').setOption({tooltip:{trigger:'axis'},legend:{top:0},grid:{left:50,right:20,top:30,bottom:30},
  xAxis:{type:'category',data:fx.map(f=>f+' dias')},yAxis:{name:'skill'},
  series:[{name:'hoje',type:'line',data:fx.map(f=>(d.curva.LB[f]||{}).hoje),lineStyle:{color:'#9ca3af'}},
   {name:'aprendendo (L)',type:'line',data:fx.map(f=>(d.curva.L[f]||{}).aprende)},
   {name:'aprendendo (LB)',type:'line',data:fx.map(f=>(d.curva.LB[f]||{}).aprende),lineStyle:{color:'#ea580c'}}]},true);
 const s = []; for (const [l,v] of Object.entries(d.aprendeu)) { s.push({name:'a '+l,type:'line',data:v.a,symbol:'none'});
  s.push({name:'b '+l,type:'line',data:v.b,symbol:'none',lineStyle:{type:'dashed'}}); }
 ch('c_aprendeu').setOption({tooltip:{trigger:'axis'},legend:{top:0},grid:{left:50,right:20,top:40,bottom:30},
  xAxis:{type:'time'},yAxis:{min:0.5},series:s},true);
}
sel.onchange = () => desenha(+sel.value); desenha(0);
window.onresize = () => Object.values(charts).forEach(c=>c.resize());
</script></body></html>"""


def main():
    SAIDA.mkdir(exist_ok=True)
    shutil.copy(ECHARTS, SAIDA / "echarts.min.js")
    dados = [_dados(s) for s in SERIES]
    html = PAGINA.replace("__DADOS__", json.dumps(dados, default=float).replace("NaN", "null"))
    (SAIDA / "uso_prolongado.html").write_text(html, encoding="utf-8")
    print(SAIDA / "uso_prolongado.html")


if __name__ == "__main__":
    main()
