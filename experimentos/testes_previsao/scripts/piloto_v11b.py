"""C2 / V11-b (servidor, 18/11/2026): a faixa conformal POR SITIO, com a correcao de amostra finita, no periodo
INTOCADO 01/06 -> 15/11/2026. Nada reajustado: o app de hoje (TRUST, SKILL, a faixa sazonal) e so a faixa nova.

Portao em docs/projeto/PILOTOS_F1_F2.md, "V11-b" (commitado antes de rodar). Regra da faixa (escrita antes):
  Para o lead k e o dia-alvo i, emitido na noite e = i - k: residuos escalados r_j = (Y_j - F_j) / (hi_j - lo_j) dos
  pares (lead k) com alvo j em (e - 60, e] (so o que o banco ja tinha na noite da emissao), F = o total do dia que o
  app emitiu, [lo, hi] = a faixa de 80% de hoje. Com n >= 30 residuos: r_lo = estatistica de ordem floor(0,1 (n+1))
  (minimo 1), r_hi = estatistica de ordem ceil(0,9 (n+1)) (maximo n) - os niveis conservadores de amostra finita.
  Faixa nova = [F + r_lo (hi - lo), F + r_hi (hi - lo)], cortada em 0: CADA BORDA anda a partir da previsao pontual
  (nao e centrada; a mesma ideia do `postprocessing.conformal_quantiles` com o residuo escalado pela largura de hoje).
  Com n < 30: a faixa de hoje.

Uso (ambiente da biblioteca):
  python piloto_v11b.py replay Cascavel | Curitiba     (retoma; ~10 min cada)
  python piloto_v11b.py avalia
Saidas: resultados/pilotos/uso_prolongado_v11b__usinas__<serie>.parquet (por hora, privado, fora do git) e
resultados/pilotos/v11b.json (agregados).
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import piloto_uso_prolongado as V  # noqa: E402
from piloto_comum import PILOTOS  # noqa: E402

V.ARQ_USINAS, V.ARQ_HORIZONTE = "usinas_horario_v1.parquet", "previsao_tempo_horizonte_v1.parquet"
V.PRIMEIRO_ALVO, V.ULTIMO_ALVO = pd.Timestamp("2026-03-25"), pd.Timestamp("2026-11-15")  # 60+7 dias de banco antes
V.arq = lambda s: PILOTOS / f"uso_prolongado_v11b__usinas__{s}.parquet"
INI_TESTE = pd.Timestamp("2026-06-01")
JAN, MIN_N, A_LO, A_HI = 60, 30, 0.1, 0.9


def faixa_conformal(t, k):
    q = t[t.lead == k].set_index("alvo").sort_index()
    larg = (q.hi - q.lo).to_numpy(float)
    r = np.where(larg > 0, (q.Y - q.F).to_numpy(float) / np.where(larg > 0, larg, 1), np.nan)
    alvos = q.index
    lo_v, hi_v, n_usado = q.lo.to_numpy(float).copy(), q.hi.to_numpy(float).copy(), np.zeros(len(q), int)
    for i, a in enumerate(alvos):
        e = a - pd.Timedelta(days=k)
        m = (alvos > e - pd.Timedelta(days=JAN)) & (alvos <= e) & np.isfinite(r)
        rr = np.sort(r[m])
        n = len(rr)
        n_usado[i] = n
        if n >= MIN_N and larg[i] > 0:
            i_lo = max(math.floor(A_LO * (n + 1)), 1)
            i_hi = min(math.ceil(A_HI * (n + 1)), n)
            lo_v[i] = q.F.iloc[i] + rr[i_lo - 1] * larg[i]
            hi_v[i] = q.F.iloc[i] + rr[i_hi - 1] * larg[i]
    out = q.assign(lo_v=np.maximum(lo_v, 0), hi_v=np.maximum(hi_v, 0), n_conf=n_usado).reset_index()
    return out[out.alvo >= INI_TESTE]


def avalia():
    rel = {"portao": "docs/projeto/PILOTOS_F1_F2.md, V11-b", "periodo": [str(INI_TESTE.date()), "2026-11-15"]}
    passa = True
    for s in V.SERIES:
        t = V._pares(s)
        R = {}
        todas = []
        for k in range(1, V.LEADS + 1):
            v = faixa_conformal(t, k)
            todas.append(v)
            rm = lambda c: float(np.sqrt(((v.Y - v[c]) ** 2).mean()))  # noqa: E731
            R[f"lead{k}"] = dict(n=len(v), skill_F_vs_S=1 - rm("F") / rm("S"),
                                 cob_hoje=float(((v.Y >= v.lo) & (v.Y <= v.hi)).mean()),
                                 cob_conformal=float(((v.Y >= v.lo_v) & (v.Y <= v.hi_v)).mean()),
                                 largura_rel_conformal=float((v.hi_v - v.lo_v).mean() / (v.hi - v.lo).mean()),
                                 n_conf_min=int(v.n_conf.min()))
        T = pd.concat(todas)
        cob = float(((T.Y >= T.lo_v) & (T.Y <= T.hi_v)).mean())
        g_pool = 0.77 <= cob <= 0.83
        g_cel = all(0.70 <= R[f"lead{k}"]["cob_conformal"] <= 0.90 for k in range(1, V.LEADS + 1))
        # erro percentual (relato, pedido de 18/11): dia, semana, mes, lead 1 e 7, so o app de hoje
        err = {}
        for k in (1, 7):
            q = T[T.lead == k].assign(semana=lambda d: d.alvo.dt.to_period("W"), mes=lambda d: d.alvo.dt.to_period("M"))
            for nivel, minimo in (("alvo", 1), ("semana", 6), ("mes", 26)):
                g = q.groupby(nivel)[["Y", "F"]].sum()
                g = g[q.groupby(nivel).size() >= minimo]
                err[f"lead{k}_{nivel}"] = dict(erro=float((g.Y - g.F).abs().sum() / g.Y.sum()),
                                               ate_10pct=float(((g.Y - g.F).abs() / g.Y <= 0.10).mean()), n=len(g))
        rel[s] = dict(por_lead=R, cobertura_conformal_todos_leads=cob,
                      cobertura_hoje_todos_leads=float(((T.Y >= T.lo) & (T.Y <= T.hi)).mean()),
                      G_pool=g_pool, G_celulas=g_cel, erro_pct=err)
        passa = passa and g_pool and g_cel
        print(s, json.dumps(rel[s]["por_lead"], indent=0, default=float)[:2000])
    rel["PASSA"] = passa
    (PILOTOS / "v11b.json").write_text(json.dumps(rel, indent=1, default=float), encoding="utf-8")
    print("PASSA", passa)


if __name__ == "__main__":
    if sys.argv[1] == "replay":
        V.replay(sys.argv[2])
    elif sys.argv[1] == "avalia":
        avalia()
