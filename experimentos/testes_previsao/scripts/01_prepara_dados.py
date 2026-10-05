# -*- coding: utf-8 -*-
"""Extrai so a parte necessaria dos dados, em base horaria.

Usinas (Cascavel, Curitiba): energia horaria do inversor (soma dos 5 min) +
  poa_ceu_claro (geometria, sempre conhecida) + clima NASA POWER horario
  (ghi_horario, poa_estimada, temp_ar_horaria), ja alinhado em -55 min.
Casas (H1..H20): Production(Wh) e Consumption(Wh) somados por hora. Nada de
  bateria, rede ou estado de carga.

Saida: testes_modelos/dados/usinas_horario.parquet e casas_horario.parquet
"""
from pathlib import Path
import numpy as np, pandas as pd

RAIZ = Path(__file__).resolve().parents[2]              # Projeto_IA/
SAIDA = RAIZ / "testes_modelos" / "dados"
SAIDA.mkdir(parents=True, exist_ok=True)
IA = RAIZ / "ia_solar"

USINAS = {
    "Cascavel": dict(bruto=IA / "analise/cascavel/dados/dados_5min_2019-2026.parquet",
                     base=IA / "base_modelagem/cascavel/base_Cascavel_horaria.parquet", kwp=3.96),
    "Curitiba": dict(bruto=IA / "analise/curitiba/dados/curitiba_5min.parquet",
                     base=IA / "base_modelagem/curitiba/base_Curitiba_horaria.parquet", kwp=9.60),
}
FIM_NASA = pd.Timestamp("2026-06-01")                    # a NASA horaria termina em 31/05/2026


def preenche_por_hora(s):
    """Preenche buracos com o valor da mesma hora nos dias vizinhos (geometria muda devagar)."""
    t = s.to_frame("v"); t["d"] = t.index.normalize(); t["h"] = t.index.hour
    p = t.pivot_table(index="d", columns="h", values="v", dropna=False)
    p = p.interpolate(limit_direction="both")
    return t.join(p.stack(future_stack=True).rename("f"), on=["d", "h"])["v"].fillna(t.join(p.stack(future_stack=True).rename("f"), on=["d", "h"])["f"])


tabs = []
for usina, c in USINAS.items():
    r = pd.read_parquet(c["bruto"], columns=["timestamp", "energia_Wh"])
    r = r.drop_duplicates("timestamp")
    g = r.set_index("timestamp").energia_Wh.resample("h")
    y = g.sum(min_count=1).where(g.count() >= 11)         # hora valida: >= 11 dos 12 registros
    b = pd.read_parquet(c["base"]).set_index("data_hora")
    idx = pd.date_range(y.index.min(), min(y.index.max(), FIM_NASA - pd.Timedelta("1h")), freq="h")
    d = pd.DataFrame(index=idx)
    d["y_Wh"] = y.reindex(idx)
    for col in ["poa_ceu_claro", "poa_estimada", "ghi_horario", "temp_ar_horaria"]:
        d[col] = b[col].reindex(idx)
    noite = d.index.hour.isin(range(0, 5)) | d.index.hour.isin(range(20, 24))
    for col in ["poa_ceu_claro", "poa_estimada", "ghi_horario"]:
        d.loc[noite & d[col].isna(), col] = 0.0
    d["poa_ceu_claro"] = preenche_por_hora(d["poa_ceu_claro"]).fillna(0.0)
    # fora da base (horas sem sol ou buracos) o ceu claro e zero quando nao ha nenhum registro diurno naquele horario
    d["temp_ar_horaria"] = d["temp_ar_horaria"].interpolate(limit_direction="both")
    for col in ["poa_estimada", "ghi_horario"]:
        d[col] = d[col].where(d.poa_ceu_claro > 0, 0.0)
        d[col] = preenche_por_hora(d[col]).fillna(0.0)
    # sem sol nao ha geracao: o registro noturno do inversor e falho, mas o valor e zero
    d.loc[d.poa_ceu_claro <= 0, "y_Wh"] = 0.0
    # nas pontas do dia o inversor ainda dorme e nao registra: se o dia teve registro normal
    # entre 9 h e 15 h (>= 60 de 72), as horas de pouco sol sem registro completo valem o que foi somado
    cont = g.count().reindex(idx).fillna(0)
    meio = cont.where((cont.index.hour >= 9) & (cont.index.hour < 15)).groupby(cont.index.normalize()).sum()
    dia_ok = pd.Series(cont.index.normalize(), index=cont.index).map(meio) >= 60
    ponta = dia_ok & (d.poa_ceu_claro < 150) & d.y_Wh.isna()
    d.loc[ponta, "y_Wh"] = g.sum().reindex(idx)[ponta].fillna(0.0)
    d["y_valido"] = d.y_Wh.notna()
    d["kwp"] = c["kwp"]; d["serie"] = usina
    tabs.append(d.rename_axis("ds").reset_index())
    print("%-9s %s -> %s  %6d horas  %.1f%% com alvo valido  energia anual media %.0f kWh"
          % (usina, idx.min().date(), idx.max().date(), len(d), 100 * d.y_valido.mean(),
             d.y_Wh.sum() / 1000 / (len(d) / 8760)))
U = pd.concat(tabs, ignore_index=True)
U.to_parquet(SAIDA / "usinas_horario.parquet", index=False)

# --- casas: so producao e consumo ---
casas = []
for i in range(1, 21):
    f = RAIZ / "dados_casas" / ("H%d_Wh.csv" % i)
    x = pd.read_csv(f, usecols=["date", " Production(Wh)", " Consumption(Wh)"], parse_dates=["date"])
    x.columns = ["date", "prod", "cons"]
    x["hora"] = (x.date - pd.Timedelta("1min")).dt.floor("h")     # 01:01..02:00 -> 01:00
    g = x.groupby("hora")
    n = g.size()
    h = g[["prod", "cons"]].sum(min_count=1).where(n >= 55)        # hora valida: >= 55 minutos
    h = h.reindex(pd.date_range(h.index.min(), h.index.max(), freq="h"))
    h["casa"] = "H%d" % i
    casas.append(h.rename_axis("ds").reset_index())
C = pd.concat(casas, ignore_index=True)
C["prod_kWh"] = C.pop("prod") / 1000; C["cons_kWh"] = C.pop("cons") / 1000
C.to_parquet(SAIDA / "casas_horario.parquet", index=False)
m = C.assign(mes=C.ds.dt.month).groupby("mes")[["prod_kWh", "cons_kWh"]].sum() / 20
print("casas: %d linhas, %s -> %s; faltantes prod %.2f%% cons %.2f%%" % (len(C), C.ds.min(), C.ds.max(),
      100 * C.prod_kWh.isna().mean(), 100 * C.cons_kWh.isna().mean()))
print("kWh por casa por mes (media das 20):"); print(m.round(0).T.to_string())
