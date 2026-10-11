# -*- coding: utf-8 -*-
"""Piloto: calibracao CONFORMAL CAUSAL das faixas (quantis) gravadas pelo piloto F2(c).

Problema: as faixas do LightGBM quantilico saem estreitas na FV das casas (cobertura 80% = 0,647) e no regime C
das usinas (0,741); as do Chronos-2 largas no C (0,838 / 0,656). Pergunta: um ajuste conformal que so usa o
passado conserta a cobertura sem perder CRPS?

Metodo (Romano et al. 2019, CQR, com calibracao movel): para cada par simetrico (q_a, q_1-a) e cada dia d, os
escores das previsoes dos N dias anteriores a d (todas as series; o real de d-1 ja e conhecido as 00:00 de d):
- aditivo:     E = max(q_a - y, y - q_1-a)              -> faixa [q_a - c, q_1-a + c]
- normalizado: E = max(q_a - y, y - q_1-a) / largura      -> faixa [q_a - c L, q_1-a + c L]   (L = q_1-a - q_a)
- por nivel:   cada quantil (mediana inclusive) q_a += quantil a de (y - q_a) / largura de 80%, x a largura
  (a forma que PASSOU e foi para a biblioteca: `prosumer.postprocessing.conformal_quantiles`, 28 dias).
c = quantil conformal de E no nivel (1 - 2a) (com a correcao (n+1)/n). Horas com largura ~0 (noite na FV)
nao entram na calibracao nem sao mexidas. c pode ser negativo (estreita a faixa larga). Os 4 pares sao
ajustados um a um, a mediana fica; quantis cruzados sao ordenados (como na avaliacao). Antes de ter
`MIN_DIAS` dias de calibracao a faixa sai sem ajuste.

Avaliacao: as horas avaliadas do benchmark, SO nos dias em que a calibracao ja esta ativa, as tres faixas
(bruta, calibrada, referencia dos 14 dias) nas mesmas horas. Portao: cobertura de 80% e 60% dentro de
+-5 pontos e CRPS melhor que a referencia; e, onde a bruta ja passava, nao piorar o CRPS mais que 1%.

Uso (ambiente da biblioteca): python piloto_conformal.py   -> resultados/pilotos/conformal.json
"""
import importlib
import json

import numpy as np
import pandas as pd

from piloto_comum import PILOTOS
from piloto_quantis import QS, referencia
from prosumer.metrics import band_scores

FONTES = [("LightGBM", c, r) for c, r in [("casas_cons", "A"), ("casas_prod", "A"), ("usinas", "A"), ("usinas", "C")]]
FONTES += [("Chronos-2", c, r) for c, r in [("casas_cons", "A"), ("casas_prod", "A"), ("usinas", "A"), ("usinas", "C")]]
FONTES += [("TimesFM-3", c, "A") for c in ("casas_cons", "casas_prod", "usinas")]
VARIANTES = [("aditivo", 14), ("aditivo", 28), ("normalizado", 14), ("normalizado", 28), ("nivel", 14), ("nivel", 28)]
MIN_DIAS = 7
EPS = 1e-6


def calibra(Q, y, dia, tipo, n_dias, producao):
    """Q (linhas, 9) ordenado, y (linhas,), dia (linhas,) datetime64, producao (linhas,) bool: horas que entram
    na calibracao e sao ajustadas. Devolve Q ajustado e a mascara de linhas em que a calibracao estava ativa."""
    out = Q.copy()
    dias = np.unique(dia)
    ativo = np.zeros(len(y), bool)
    if tipo == "nivel":  # cada quantil (mediana inclusive) desloca pelo quantil a de (y - q_a) / largura de 80%
        L = Q[:, 8] - Q[:, 0]
        ok = (L > EPS) & producao & np.isfinite(y)
        for d in dias:
            cal = ok & (dia < d) & (dia >= d - np.timedelta64(n_dias, "D"))
            if len(np.unique(dia[cal])) < MIN_DIAS:
                continue
            alvo = (dia == d) & (L > EPS) & producao
            ativo |= dia == d
            for k, a in enumerate(QS):
                c = np.quantile((y[cal] - Q[cal, k]) / L[cal], a)
                out[alvo, k] = Q[alvo, k] + c * L[alvo]
        return np.sort(np.clip(out, 0, None), axis=1), ativo
    for k in range(4):  # pares (0,8) (1,7) (2,6) (3,5): 80, 60, 40, 20%
        lo, hi = Q[:, k], Q[:, 8 - k]
        L = hi - lo
        nivel = QS[8 - k] - QS[k]
        E = np.maximum(lo - y, y - hi)
        if tipo == "normalizado":
            E = E / np.where(L > EPS, L, np.nan)
        ok = np.isfinite(E) & (L > EPS) & producao
        for d in dias:
            cal = ok & (dia < d) & (dia >= d - np.timedelta64(n_dias, "D"))
            if len(np.unique(dia[cal])) < MIN_DIAS:
                continue
            e = np.sort(E[cal])
            n = len(e)
            c = e[min(n - 1, int(np.ceil((n + 1) * nivel)) - 1)]
            alvo = (dia == d) & (L > EPS) & producao
            ativo |= dia == d
            m = c * L[alvo] if tipo == "normalizado" else c
            out[alvo, k] = lo[alvo] - m
            out[alvo, 8 - k] = hi[alvo] + m
    return np.sort(np.clip(out, 0, None), axis=1), ativo


def horas_de_producao(caso, j):
    """Horas que entram na calibracao, CAUSAL: consumo todas; usinas sol acima do horizonte (ceu claro > 0, a
    mascara do benchmark, astronomica); FV das casas o perfil horario medio ANTES do teste (o benchmark usa o do
    proprio teste so para avaliar). As horas de noite tem faixa ~0 e encheriam a calibracao de escores ~0."""
    from comum import CASOS, carrega
    from prosumer.metrics import evaluated_mask
    if caso == "casas_cons":
        return np.ones(len(j), bool)
    if caso == "usinas":
        return j.avalia.to_numpy()
    todo = carrega(caso)
    antes = todo[todo.ds < CASOS[caso]["ini"]]
    f = j.reset_index()[["unique_id", "ds"]]
    return evaluated_mask(f.assign(y=0.0), "profile", profile=antes).to_numpy()


def avalia(fonte, caso, regime):
    av = importlib.import_module("05_avalia")
    base = av.real(caso).set_index(["unique_id", "ds"])
    Q = pd.read_parquet(PILOTOS / f"{fonte}-quantis__{caso}__{regime}.parquet")
    Q = Q.pivot_table(index=["unique_id", "ds"], columns="q", values="valor").clip(lower=0)
    Q = pd.DataFrame(np.sort(Q.to_numpy(), axis=1), index=Q.index, columns=[f"q{n}" for n in QS])
    R = referencia(caso)
    j = base.join(Q, how="inner").join(R, how="left")
    j = j[j.y.notna()]
    producao = horas_de_producao(caso, j)
    dia = j.index.get_level_values("ds").normalize().to_numpy()
    y = j.y.to_numpy()
    qcols, rcols = [f"q{n}" for n in QS], [f"q{n}_ref" for n in QS]
    res = {}
    for tipo, n_dias in VARIANTES:
        Qc, ativo = calibra(j[qcols].to_numpy(), y, dia, tipo, n_dias, producao)
        sel = ativo & j.avalia.to_numpy() & np.isfinite(j[rcols].to_numpy()).all(axis=1)
        b = {nome: band_scores(y[sel], M[sel], QS) for nome, M in
             [("bruta", j[qcols].to_numpy()), ("calibrada", Qc), ("referencia", j[rcols].to_numpy())]}
        r = {nome: dict(cob80=round(v["coverage_80"], 3), cob60=round(v["coverage_60"], 3),
                        larg80=round(v["width_80"], 4), CRPS=round(v["CRPS"], 4)) for nome, v in b.items()}
        cal_ok = lambda v: abs(v["coverage_80"] - 0.8) <= 0.05 and abs(v["coverage_60"] - 0.6) <= 0.05
        r["skill_bruta"] = round(1 - b["bruta"]["CRPS"] / b["referencia"]["CRPS"], 4)
        r["skill_calibrada"] = round(1 - b["calibrada"]["CRPS"] / b["referencia"]["CRPS"], 4)
        r["bruta_calibrada"] = bool(cal_ok(b["bruta"]))
        r["portao"] = bool(cal_ok(b["calibrada"]) and r["skill_calibrada"] > 0
                           and (not r["bruta_calibrada"] or b["calibrada"]["CRPS"] <= 1.01 * b["bruta"]["CRPS"]))
        r["horas"] = int(sel.sum())
        res[f"{tipo}_{n_dias}d"] = r
    return res


if __name__ == "__main__":
    f = PILOTOS / "conformal.json"
    tudo = {}
    for fonte, caso, regime in FONTES:
        chave = f"{fonte}|{caso}|{regime}"
        tudo[chave] = avalia(fonte, caso, regime)
        for v, r in tudo[chave].items():
            print(f"{chave:28s} {v:15s} bruta {r['bruta']['cob80']:.3f}/{r['bruta']['cob60']:.3f} "
                  f"sk {r['skill_bruta']:+.3f} | calib {r['calibrada']['cob80']:.3f}/{r['calibrada']['cob60']:.3f} "
                  f"sk {r['skill_calibrada']:+.3f} | portao {r['portao']}", flush=True)
        f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
