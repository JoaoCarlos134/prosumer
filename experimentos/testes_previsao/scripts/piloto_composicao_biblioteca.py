# -*- coding: utf-8 -*-
"""Piloto (16/10/2026): a mediana dos modelos que a BIBLIOTECA tem chega perto da mediana do benchmark?

PERGUNTA. O `Ensemble-mediana` do benchmark (07_ensemble.py) e a mediana, hora a hora, de TODOS os modelos que
rodaram em cada caso e regime (47-48 no regime A, 21-22 em B e C). Ele e 1o nas usinas em C, 2o-3o nos outros
testes, e a versao corrigida e 1a no consumo. A biblioteca usa a mesma REGRA (mediana, nunca escolhe modelo), mas
NAO os mesmos membros: o `analyze` roda por padrao so as tres ingenuas (persist_24h, semanal_168h, media_7d) e
o usuario acrescenta `models=[...]` entre os adaptadores que existem hoje: LightGBM e quatro fundacionais
zero-shot (Chronos-2, TiRex-2, Toto-2.0-313m, FlowState). Nenhuma mediana desses membros foi medida. A resposta
decide o conjunto que o `analyze` deve recomendar (ou rodar) por padrao.

METODO. Nada roda modelo: medianas, hora a hora, das previsoes GRAVADAS em `resultados/previsoes/` (as mesmas que
a biblioteca refaz: conferencia E3 de 11/10 e 16/10), avaliadas como o benchmark (horas avaliadas e referencia do
teste de regressao, corte de negativos). A mediana usa os membros que tem previsao na hora (`median` do pandas,
como o `analyze` e o 07_ensemble). Composicoes no regime A (os tres casos):

- K0 `ingenuas` = o padrao de hoje do `analyze`;
- K1 `ingenuas+LightGBM` = o que roda so com o extra `lightgbm` (sem torch);
- K2 `ingenuas+LightGBM+4 fundacionais` = todos os adaptadores da biblioteca;
- K3 `LightGBM+4 fundacionais` (sem as ingenuas);
- K4 `4 fundacionais`.

Regime C (so usinas, unico caso com previsao do tempo real): as linhas de regime C que a biblioteca faz hoje sao
o LightGBM com covariaveis, o Chronos-2 e o TiRex-2 com covariaveis e o `weather_linear` (~ `linear_fisico` do
benchmark, que usa a POA em vez do GHI medio). KC = mediana de {LightGBM, Chronos-2, TiRex-2, linear_fisico} em C.
(Hoje o `analyze` NAO faz mediana das linhas de regime C; isto mede se deveria.)

Consumo: tambem a versao corrigida de cada composicao (`correct_bias`, 14 dias), como linha (no `analyze` a
correcao e linha, nao saida: piloto de 12/10).

PORTAO (fixado antes de rodar; sem Holm, como todo piloto, declarado):
- G-A, para K1 e para K2 separadamente: nos TRES testes A, skill >= skill do Ensemble-mediana - 0,010 E
  Diebold-Mariano contra o melhor do teste (o 1o do `metricas.csv`, qualquer linha que nao seja referencia) com
  p >= 0,05. Passa K1 => o conjunto enxuto (sem torch) basta; so K2 passa => o conjunto recomendado precisa dos
  extras das fundacionais; nenhum passa => a biblioteca diz que o padrao fica abaixo do benchmark.
- G-C (usinas): KC com skill >= Ensemble-mediana C - 0,010 e DM contra o melhor de C com p >= 0,05 => o `analyze`
  passa a dar a mediana das linhas de regime C (alem da de A).
K0, K3, K4 e as corrigidas sao relatadas, sem portao.

SAIDA: `resultados/pilotos/composicao_biblioteca.json` (agregados por composicao e teste). Fora de `previsoes/`.

Uso (ambiente da biblioteca, CPU, ~1 min): python piloto_composicao_biblioteca.py
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

import comum
from prosumer import metrics as pm
from prosumer.postprocessing import correct_bias

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
import test_benchmark_regression as T  # noqa: E402

INGENUAS = ["persist_24h", "semanal_168h", "media_7d"]
FUND = ["Chronos-2", "TiRex-2", "Toto-2.0-313m", "FlowState"]
COMPOSICOES_A = {
    "K0 ingenuas": INGENUAS,
    "K1 ingenuas+LightGBM": INGENUAS + ["LightGBM"],
    "K2 ingenuas+LightGBM+4 fundacionais": INGENUAS + ["LightGBM"] + FUND,
    "K3 LightGBM+4 fundacionais": ["LightGBM"] + FUND,
    "K4 4 fundacionais": FUND,
}
COMPOSICAO_C = {"KC LightGBM+Chronos-2+TiRex-2+linear_fisico": ["LightGBM", "Chronos-2", "TiRex-2", "linear_fisico"]}
CASOS = ["usinas", "casas_prod", "casas_cons"]
TOL = 0.010
SAIDA = comum.RES / "pilotos" / "composicao_biblioteca.json"


def previsao(nome, caso, regime):
    p = pd.read_parquet(comum.PREV / f"{nome}__{caso}__{regime}.parquet")[["unique_id", "ds", "yhat"]]
    return p.set_index(["unique_id", "ds"])["yhat"].clip(lower=0).rename(nome)


def mediana(membros, caso, regime):
    j = pd.concat([previsao(m, caso, regime) for m in membros], axis=1, join="outer")
    return j.median(axis=1).rename("yhat").reset_index()


def avalia(prev, caso, regime, melhor_err):
    m, ref = pm.align(prev, T.evaluated_actual(caso), T.reference(caso))
    sk = pm.skill(m, ref)
    _, _, p = pm.diebold_mariano(pm.squared_errors(m), melhor_err)
    met = pm.metrics(m)
    return {"skill": round(sk, 4), "dm_p_vs_melhor": round(p, 4), "MBE": round(met["MBE"], 4),
            "R2": round(met["R2"], 4), "horas": len(m)}


def teste(caso, regime, composicoes):
    M = T.PUBLISHED[(T.PUBLISHED.caso == caso) & (T.PUBLISHED.regime == regime)].sort_values("skill", ascending=False)
    melhor = M.iloc[0]
    mb, _ = T._aligned(caso, melhor.modelo, regime)
    melhor_err = pm.squared_errors(mb)
    ens = float(M.loc[M.modelo == "Ensemble-mediana", "skill"].iloc[0])
    out = {"melhor": melhor.modelo, "skill_melhor": round(float(melhor.skill), 4), "skill_ensemble": round(ens, 4),
           "n_linhas": len(M), "composicoes": {}}
    for nome, membros in composicoes.items():
        med = mediana(membros, caso, regime)
        r = avalia(med, caso, regime, melhor_err)
        r["posicao"] = f"{int((M.skill > r['skill']).sum()) + 1}o de {len(M) + 1}"
        r["perto_do_ensemble"] = bool(r["skill"] >= ens - TOL)
        r["empata_com_melhor"] = bool(r["dm_p_vs_melhor"] >= 0.05 or r["skill"] >= float(melhor.skill))
        r["passa"] = r["perto_do_ensemble"] and r["empata_com_melhor"]
        if caso == "casas_cons":
            real = comum.carrega(caso)[["unique_id", "ds", "y"]]
            cor = correct_bias(med, real, quantity="consumption")[["unique_id", "ds", "yhat"]]
            r["corrigida"] = avalia(cor, caso, regime, melhor_err)
        out["composicoes"][nome] = r
    return out


if __name__ == "__main__":
    t0 = time.time()
    res = {f"{c}|A": teste(c, "A", COMPOSICOES_A) for c in CASOS}
    res["usinas|C"] = teste("usinas", "C", COMPOSICAO_C)
    veredito = {}
    for k in ("K1 ingenuas+LightGBM", "K2 ingenuas+LightGBM+4 fundacionais"):
        veredito[f"G-A {k}"] = all(res[f"{c}|A"]["composicoes"][k]["passa"] for c in CASOS)
    veredito["G-C"] = res["usinas|C"]["composicoes"][next(iter(COMPOSICAO_C))]["passa"]
    saida = {"pergunta": "mediana dos adaptadores da biblioteca x Ensemble-mediana do benchmark",
             "portao": {"G-A": f"nos 3 testes A: skill >= ensemble - {TOL} e DM vs melhor p >= 0,05 (sem Holm)",
                        "G-C": f"usinas C: idem para KC"},
             "veredito": veredito, "testes": res, "tempo_s": round(time.time() - t0, 1)}
    SAIDA.write_text(json.dumps(saida, indent=1, ensure_ascii=False))
    for t, r in res.items():
        print(f"\n{t}: melhor {r['melhor']} {r['skill_melhor']:+.3f}, Ensemble-mediana {r['skill_ensemble']:+.3f}")
        for nome, x in r["composicoes"].items():
            cor = f" | corrigida {x['corrigida']['skill']:+.3f} p {x['corrigida']['dm_p_vs_melhor']:.3f}" if "corrigida" in x else ""
            print(f"  {nome:42s} {x['skill']:+.3f} ({x['posicao']}) p {x['dm_p_vs_melhor']:.3f} MBE {x['MBE']:+.3f}"
                  f" {'PASSA' if x['passa'] else ''}{cor}")
    print("\nveredito:", veredito, f"({time.time() - t0:.0f} s)")
