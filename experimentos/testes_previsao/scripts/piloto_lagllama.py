# -*- coding: utf-8 -*-
"""Etapa A do plano: Lag-Llama (Rasul et al., 2024), zero-shot, regime A.

Lag-Llama: transformer so-decodificador (arquitetura do LLaMA: RMSNorm, RoPE, SwiGLU) cuja entrada em cada
passo nao e um patch, e o valor atual mais um conjunto fixo de DEFASAGENS (lags) tiradas das frequencias
comuns (hora anterior, mesmo horario ontem, semana passada, mes, trimestre...; ~84 lags, a maior de ~1 ano no
horario) e estatisticas de escala. A saida e uma t de Student por passo; o futuro e amostrado passo a passo
(autorregressivo). Pre-treino em 27 conjuntos (~352 milhoes de pontos). Previsao pontual aqui: mediana de 100
amostras. Contexto padrao do modelo: 32 passos (a atencao ve 32; as defasagens vao muito mais longe); o
artigo sugere testar contexto maior com RoPE escalado.

Interesse: faixa (amostras) sem treino, para o piloto F2c. Portao: grupo da frente num caso.

Codigo: so no GitHub (time-series-foundation-models/lag-llama, commit df7531a, 06/06/2025), clonado em
~/.cache/lag-llama-repo/src e posto no sys.path; pesos do HuggingFace time-series-foundation-models/Lag-Llama
(Apache-2.0). O repositorio pede gluonts<=0.14.4; roda com o 0.16.2 do previsao_gpu. O checkpoint guarda
objetos Python: o torch >= 2.6 so carrega com TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 (posto so neste processo).

Uso: python piloto_lagllama.py [ctx=32|256|1024] [caso ...]   (ambiente previsao_gpu)
Depois: python piloto_comum.py Lag-Llama-ctx<ctx> <caso> A   (ambiente da biblioteca)
"""
import os
import sys
import time
from pathlib import Path

os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
REPO = Path.home() / ".cache" / "lag-llama-repo" / "src"
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from comum import H, carrega, janelas  # noqa: E402
from piloto_comum import grava_piloto  # noqa: E402

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
HIST = 2048  # historico entregue: contexto + a maior defasagem (~1 ano nao cabe; o modelo preenche o que falta)


def preditor(ctx):
    from huggingface_hub import hf_hub_download
    from lag_llama.gluon.estimator import LagLlamaEstimator
    ckpt_path = hf_hub_download("time-series-foundation-models/Lag-Llama", "lag-llama.ckpt")
    a = torch.load(ckpt_path, map_location=DEV, weights_only=False)["hyper_parameters"]["model_kwargs"]
    rope = {"type": "linear", "factor": max(1.0, (ctx + H) / a["context_length"])} if ctx > a["context_length"] else None
    est = LagLlamaEstimator(ckpt_path=ckpt_path, prediction_length=H, context_length=ctx, input_size=a["input_size"],
                            n_layer=a["n_layer"], n_embd_per_head=a["n_embd_per_head"], n_head=a["n_head"],
                            scaling=a["scaling"], time_feat=a["time_feat"], rope_scaling=rope, batch_size=64,
                            num_parallel_samples=100, device=DEV)
    modulo = est.create_lightning_module()
    n_par = sum(p.numel() for p in modulo.parameters())
    return est.create_predictor(est.create_transformation(), modulo), n_par


def preve(ctx, jan):
    from gluonts.dataset.common import ListDataset
    pred, n_par = preditor(ctx)
    ds = ListDataset([{"start": pd.Period(w["dia"] - pd.Timedelta(hours=len(w["y"])), freq="h"),
                       "target": w["y"].astype(np.float32)} for w in jan], freq="h")
    torch.manual_seed(42)
    out = [np.median(f.samples, axis=0)[:H] for f in pred.predict(ds)]
    return out, n_par


if __name__ == "__main__":
    args = sys.argv[1:]
    ctx = int(next((a.split("=")[1] for a in args if a.startswith("ctx=")), "32"))
    casos = [a for a in args if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_prod"]
    for caso in casos:
        t0 = time.time()
        jan = janelas(carrega(caso), caso, contexto=HIST)
        prev, n_par = preve(ctx, jan)
        f = grava_piloto(f"Lag-Llama-ctx{ctx}", caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
