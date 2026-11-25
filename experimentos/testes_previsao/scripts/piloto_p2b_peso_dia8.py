"""P2-b (25/11/2026): o peso do lead 8 vale numa usina que nao o escolheu, e num periodo que nao o escolheu?

Portao em docs/projeto/PILOTOS_F1_F2.md, "P2-b" (commitado antes de rodar). So le os `p2__usinas__*.parquet` do P2 e
os totais diarios reais (mesma montagem do `piloto_p2.avalia`). Previsao do lead 8 = S + a (W - S).
  (1) cruzado: a otimo de cada usina (grade 0-1 a cada 0,01) aplicado na outra;
  (2) no tempo: a ajustado nas duas usinas juntas ate 2026-08-07 (alvo), avaliado depois, em cada usina.
Se passar: TRUST[8] = a das duas usinas juntas no periodo inteiro (minimos quadrados, limitado a 1); SKILL[8] = media
das duas usinas do skill com esse a.

Uso (ambiente da biblioteca): python piloto_p2b_peso_dia8.py   -> resultados/pilotos/p2b_peso_dia8.json
"""

import json

import numpy as np
import pandas as pd

import piloto_p2 as P2
import piloto_uso_prolongado as V
from comum import SITIOS
from piloto_comum import PILOTOS

LEAD = 8
CORTE = pd.Timestamp("2026-08-07")


def pares(serie):
    x = V._serie(serie)
    y = x.set_index(x.ds.dt.tz_localize(None)).y
    diario = y.groupby(y.index.normalize()).sum(min_count=24)
    cheio = y.notna().groupby(y.index.normalize()).sum() == 24
    d = pd.read_parquet(P2.arq(serie))
    d["Y"] = diario.reindex(d.alvo).where(cheio.reindex(d.alvo).fillna(False).to_numpy()).to_numpy()
    return d[d.lead == LEAD].dropna(subset=["Y"]).sort_values("alvo").reset_index(drop=True)


def a_ls(q):
    """Minimos quadrados de Y - S = a (W - S), limitado a [0, 1]."""
    x, y = (q.W - q.S).to_numpy(), (q.Y - q.S).to_numpy()
    return float(np.clip((x @ y) / (x @ x), 0, 1))


def a_grade(q):
    grade = np.linspace(0, 1, 101)
    erro = [np.sqrt(((q.Y - (q.S + a * (q.W - q.S))) ** 2).mean()) for a in grade]
    return float(grade[int(np.argmin(erro))])


def avalia(q, a):
    f = q.S + a * (q.W - q.S)
    rmS = float(np.sqrt(((q.Y - q.S) ** 2).mean()))
    rmF = float(np.sqrt(((q.Y - f) ** 2).mean()))
    dl = ((q.Y - f) ** 2 - (q.Y - q.S) ** 2).groupby(q.alvo).mean().sort_index()
    return dict(n=len(q), a=a, skill=1 - rmF / rmS, p_dm=float(V._dm(dl.to_numpy())))


def main():
    Q = {s: pares(s) for s in SITIOS}
    proprio = {s: a_grade(q) for s, q in Q.items()}
    outra = {s: [o for o in SITIOS if o != s][0] for s in SITIOS}
    rel = {"portao": "docs/projeto/PILOTOS_F1_F2.md, P2-b", "lead": LEAD, "a_proprio": proprio}
    cruz, tempo = {}, {}
    junto_1 = pd.concat([q[q.alvo <= CORTE] for q in Q.values()])
    a_1 = a_ls(junto_1)
    for s, q in Q.items():
        c = avalia(q, proprio[outra[s]])
        c["skill_a_proprio"] = avalia(q, proprio[s])["skill"]
        c["ok"] = bool(c["skill"] > 0 and c["p_dm"] < 0.05 and c["skill"] >= c["skill_a_proprio"] - 0.02)
        cruz[s] = c
        t = avalia(q[q.alvo > CORTE].reset_index(drop=True), a_1)
        t["ok"] = bool(t["skill"] > 0)
        tempo[s] = t
    rel["cruzado"] = cruz
    rel["tempo"] = dict(a_primeira_metade=a_1, corte=str(CORTE.date()), **tempo)
    passa = all(c["ok"] for c in cruz.values()) and all(tempo[s]["ok"] for s in SITIOS)
    a_tudo = a_ls(pd.concat(Q.values()))
    rel["PORTAO"] = dict(PASSA=passa)
    if passa:
        rel["PORTAO"].update(TRUST_8=round(a_tudo, 4),
                             SKILL_8=round(float(np.mean([avalia(q, a_tudo)["skill"] for q in Q.values()])), 3),
                             skill_por_usina={s: avalia(q, a_tudo)["skill"] for s, q in Q.items()})
    (PILOTOS / "p2b_peso_dia8.json").write_text(json.dumps(rel, indent=1, default=float), encoding="utf-8")
    print(json.dumps(rel, indent=1, default=float))


if __name__ == "__main__":
    main()
