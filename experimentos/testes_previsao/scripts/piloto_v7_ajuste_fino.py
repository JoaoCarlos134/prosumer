"""G3 / V7 (servidor, 18/11/2026): o ajuste fino do Chronos-2 nestes dados ganha do zero-shot?

Portao em docs/projeto/PILOTOS_F1_F2.md, "V7" (commitado antes de rodar). So o Chronos-2: o `chronos-forecasting`
2.3.2 tem `Chronos2Pipeline.fit`; os pacotes do TiRex-2 (`tirex2` 0.3.1) e do Toto-2.0 (`toto2` 2.0.0) so tem
inferencia (nenhum modulo de treino), e escrever um laco de treino para eles seria um metodo novo, nao o deles.
Metodo (configuracao UNICA, escolhida antes, sem busca): origem movel do benchmark (`comum.dobras`); no inicio de
cada dobra, `fit` a partir do `amazon/chronos-2` com todos os dados ANTES da dobra (uma serie por usina/casa; buracos
como NaN), ajuste completo, context_length 1024, prediction_length 24, learning_rate 1e-5, num_steps 500,
batch_size 64; depois as janelas da dobra como no `03_fundacionais.py` (mediana). Casos: usinas A, usinas C
(covariaveis do C: passado = EXOG; futuro conhecido = EXOG), casas_prod A, casas_cons A.
Saidas: resultados_v7/previsoes/Chronos-2-ft__<caso>__<regime>.parquet (usinas: privado, fora do git); a comparacao
com o zero-shot e o 05_avalia.py rodado em resultados_v7 com as previsoes do Chronos-2 e das referencias copiadas.
Uso (ambiente previsao, GPU): BENCH_SAIDA=resultados_v7 python piloto_v7_ajuste_fino.py
"""

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parent))
from comum import EXOG, H, PREV, RAIZ, RES, carrega, dobras, grava, janelas  # noqa: E402

CASOS = [("usinas", "A"), ("usinas", "C"), ("casas_prod", "A"), ("casas_cons", "A")]
CFG = dict(context_length=1024, learning_rate=1e-5, num_steps=500, batch_size=64, finetune_mode="full")
REFS = {"usinas": "persist_ceu_claro", "casas_prod": "persist_24h", "casas_cons": "persist_24h"}


def copia_base():
    """Zero-shot do Chronos-2 e as referencias da v2 para resultados_v7/previsoes (o 05 compara os dois)."""
    orig = RAIZ / "resultados" / "previsoes"
    for caso, regime in CASOS:
        for nome in (f"Chronos-2__{caso}__{regime}.parquet", f"{REFS[caso]}__{caso}__A.parquet"):
            if (orig / nome).exists() and not (PREV / nome).exists():
                shutil.copy2(orig / nome, PREV / nome)


def treino(d, ini, exog):
    ent = []
    for _, g in d[d.ds < ini].groupby("unique_id", sort=False):
        e = {"target": g.y.to_numpy(np.float32)}
        if exog:
            e["past_covariates"] = {c: g[c].to_numpy(np.float32) for c in EXOG}
            e["future_covariates"] = {c: None for c in EXOG}
        ent.append(e)
    return ent


def roda():
    from chronos import BaseChronosPipeline
    assert RES.name == "resultados_v7", "rode com BENCH_SAIDA=resultados_v7"
    copia_base()
    log = RES / "tempos_v7.json"
    tempos = json.loads(log.read_text()) if log.exists() else {}
    for caso, regime in CASOS:
        chave = f"Chronos-2-ft|{caso}|{regime}"
        if chave in tempos:
            continue
        exog = regime != "A"
        d = carrega(caso, regime)
        jan = janelas(d, caso, exog=exog)
        prev = [None] * len(jan)
        t0 = time.time()
        for ini, fim in dobras(caso):
            ini_n, fim_n = pd.Timestamp(ini).tz_localize(None), pd.Timestamp(fim).tz_localize(None)
            base = BaseChronosPipeline.from_pretrained("amazon/chronos-2", device_map="cuda")
            with tempfile.TemporaryDirectory() as tmp:
                p = base.fit(treino(d, ini_n, exog), prediction_length=H, output_dir=tmp, **CFG)
            idx = [i for i, w in enumerate(jan) if ini_n <= w["dia"] <= fim_n]
            qs = list(p.quantiles)
            i50 = int(np.argmin(np.abs(np.array(qs) - 0.5)))
            for k in range(0, len(idx), 64):
                lote = idx[k:k + 64]
                ent = []
                for i in lote:
                    e = {"target": jan[i]["y"]}
                    if exog:
                        e["past_covariates"] = dict(jan[i]["x_pass"])
                        e["future_covariates"] = dict(jan[i]["x_fut"])
                    ent.append(e)
                for i, x in zip(lote, p.predict(ent, prediction_length=H)):
                    prev[i] = x[0, i50].cpu().numpy()
            del p, base
            torch.cuda.empty_cache()
            print(f"{caso} {regime} dobra {ini_n.date()}: {len(idx)} janelas, {time.time() - t0:.0f} s", flush=True)
        assert all(x is not None for x in prev)
        grava("Chronos-2-ft", caso, regime, jan, prev)
        tempos[chave] = dict(segundos=round(time.time() - t0), janelas=len(jan), **CFG)
        log.write_text(json.dumps(tempos, indent=1))


if __name__ == "__main__":
    roda()
