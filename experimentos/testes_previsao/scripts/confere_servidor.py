"""Conferencias das rodadas do servidor que comparam pastas de resultados (18/11/2026). Portoes em PILOTOS_F1_F2.md.

  python confere_servidor.py v3   sementes 42/43/44 (resultados_v3_s*) x v2 (resultados/): grupos de empate e skill
  python confere_servidor.py v4   casas no ano todo (resultados_v4): ranking por estacao (dobras de 31 dias)
  python confere_servidor.py v5   regime C6 x C por modelo (resultados_v5)
  python confere_servidor.py v7   Chronos-2 ajustado x zero-shot (resultados_v7)
  python confere_servidor.py v1   teste intocado das usinas (resultados_v1) x v2
Saidas: resultados/pilotos/servidor_<rodada>.json (agregados; nada por hora). Ambiente: previsao (pandas, scipy).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados" / "pilotos"
REF = {"persist_24h", "semanal_168h", "media_7d", "persist_ceu_claro"}
ENS = {"Ensemble-mediana", "Ensemble-mediana-corrigida"}


def le(pasta, nome):
    f = RAIZ / pasta / nome
    return pd.read_csv(f, sep=";", decimal=",", encoding="utf-8-sig") if f.exists() else None


def empates(pasta):
    dm = le(pasta, "dm_vs_melhor.csv")
    if dm is None:
        return {}
    return {(r.caso, r.regime, r.modelo): str(r.empatado_com_melhor) == "True" for r in dm.itertuples()}


def v3():
    v2 = le("resultados", "metricas.csv").set_index(["caso", "regime", "modelo"]).skill
    e2 = empates("resultados")
    sem = {s: le(f"resultados_v3_s{s}", "metricas.csv") for s in (42, 43, 44)}
    sem = {s: m.set_index(["caso", "regime", "modelo"]).skill for s, m in sem.items() if m is not None}
    emp = {s: empates(f"resultados_v3_s{s}") for s in sem}
    comuns = sorted(set(v2.index).intersection(*[set(m.index) for m in sem.values()])) if sem else []
    linhas, mesmo_empate, dentro = [], 0, 0
    for k in comuns:
        sk = np.array([sem[s][k] for s in sem])
        faixa = float(sk.max() - sk.min())
        dif = float(v2[k] - sk.mean())
        ok_skill = abs(dif) <= max(faixa, 0.01)
        ok_emp = all(emp[s].get(k) == e2.get(k) for s in sem)
        mesmo_empate += ok_emp
        dentro += ok_skill
        linhas.append(dict(caso=k[0], regime=k[1], modelo=k[2], v2=float(v2[k]), media_sementes=float(sk.mean()),
                           faixa_sementes=faixa, dif=dif, skill_ok=bool(ok_skill), empate_igual=bool(ok_emp)))
    n = len(comuns)
    rel = dict(n_modelos=n, fracao_empate_igual=mesmo_empate / n if n else None,
               fracao_skill_dentro=dentro / n if n else None, linhas=linhas)
    rel["PASSA"] = bool(n and rel["fracao_empate_igual"] >= 0.9 and rel["fracao_skill_dentro"] >= 0.9)
    return rel


def v4():
    D = le("resultados_v4", "metricas_por_dobra.csv")
    D["inicio"] = pd.to_datetime(D.inicio)
    D["estacao"] = D.inicio.dt.month.map(lambda m: "abr-jun" if m <= 6 else ("jul-set" if m <= 9 else "out-dez"))
    rel, passa = {}, True
    for caso, g in D[~D.modelo.isin(REF)].groupby("caso"):
        for regime, gg in g.groupby("regime"):
            tab = gg.groupby(["estacao", "modelo"]).skill.mean().unstack(0)
            rk = tab.rank(ascending=False)
            n = len(tab)
            pos = {e: {m: int(rk.loc[m, e]) for m in ENS if m in rk.index} for e in tab.columns}
            topo = all(p <= max(1, int(np.ceil(n / 4))) for e in pos.values() for m, p in e.items()
                       if m == ("Ensemble-mediana-corrigida" if caso == "casas_cons" else "Ensemble-mediana"))
            sp = {f"{a}|{b}": float(spearmanr(tab[a], tab[b], nan_policy="omit").statistic)
                  for i, a in enumerate(tab.columns) for b in tab.columns[i + 1:]}
            rel[f"{caso}|{regime}"] = dict(n_modelos=n, posicao_ensemble=pos, spearman_entre_estacoes=sp,
                                           ensemble_no_quartil_de_cima=bool(topo),
                                           melhor_por_estacao={e: tab[e].idxmax() for e in tab.columns})
            passa = passa and topo
    rel["PASSA"] = passa
    return rel


def v5():
    M = le("resultados_v5", "metricas.csv")
    M = M[(M.caso == "usinas") & ~M.modelo.isin(REF)]
    DR = le("resultados_v5", "dm_regimes.csv")
    rel, ganham = {}, 0
    ambos = sorted(set(M[M.regime == "C6"].modelo) & set(M[M.regime == "C"].modelo))
    for m in ambos:
        s6 = float(M[(M.regime == "C6") & (M.modelo == m)].skill.iloc[0])
        s1 = float(M[(M.regime == "C") & (M.modelo == m)].skill.iloc[0])
        p = None
        if DR is not None:
            q = DR[(DR.comparacao == "C6 x C") & (DR.modelo_1 == f"{m} (C6)") & (DR.modelo_2 == f"{m} (C)")]
            p = float(q.p.iloc[0]) if len(q) else None
        g = s6 - s1 >= 0.02 and (p is None or p < 0.05)
        ganham += g
        rel[m] = dict(skill_C=s1, skill_C6=s6, ganho=s6 - s1, p_dm=p, ganha=bool(g))
    rel["PASSA"] = bool(ambos) and ganham >= len(ambos) / 2
    rel["n"] = len(ambos)
    return rel


def v7():
    M = le("resultados_v7", "metricas.csv").set_index(["caso", "regime", "modelo"]).skill
    rel, ganham = {}, 0
    for caso, regime in [("usinas", "A"), ("usinas", "C"), ("casas_prod", "A"), ("casas_cons", "A")]:
        a, b = M.get((caso, regime, "Chronos-2-ft")), M.get((caso, regime, "Chronos-2"))
        if a is None or b is None:
            continue
        g = a - b >= 0.02
        ganham += g
        rel[f"{caso}|{regime}"] = dict(zero_shot=float(b), ajustado=float(a), ganho=float(a - b), ganha=bool(g))
    rel["PASSA"] = ganham >= 2
    return rel


def v1():
    M = le("resultados_v1", "metricas.csv")
    v2 = le("resultados", "metricas.csv")
    e1 = empates("resultados_v1")
    rel = {}
    for regime in ("A", "C"):
        a = M[(M.caso == "usinas") & (M.regime == regime)].set_index("modelo").skill
        b = v2[(v2.caso == "usinas") & (v2.regime == regime)].set_index("modelo").skill
        comuns = sorted(set(a.index) & set(b.index) - REF)
        rel[regime] = dict(n=len(comuns), spearman_v1_v2=float(spearmanr(a[comuns], b[comuns]).statistic) if comuns else None,
                           melhor_v1=a.drop(list(REF & set(a.index)), errors="ignore").idxmax(),
                           ensemble_v1=float(a.get("Ensemble-mediana", np.nan)),
                           ensemble_empatado_com_melhor=bool(e1.get(("usinas", regime, "Ensemble-mediana"), False)
                                                             or a.drop(list(REF & set(a.index)), errors="ignore").idxmax() == "Ensemble-mediana"),
                           skill_v1={m: float(a[m]) for m in comuns}, skill_v2={m: float(b[m]) for m in comuns})
    lg = M[(M.caso == "usinas") & (M.modelo == "LightGBM")].set_index("regime").skill
    rel["LightGBM_C_menos_A"] = float(lg.get("C", np.nan) - lg.get("A", np.nan))
    rel["PASSA"] = bool(rel["A"]["ensemble_empatado_com_melhor"] and rel["C"]["ensemble_empatado_com_melhor"]
                        and rel["LightGBM_C_menos_A"] > 0)
    return rel


if __name__ == "__main__":
    r = sys.argv[1]
    rel = {"v1": v1, "v3": v3, "v4": v4, "v5": v5, "v7": v7}[r]()
    (SAIDA / f"servidor_{r}.json").write_text(json.dumps(rel, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in rel.items() if k != "linhas"}, indent=1, default=float)[:4000])
