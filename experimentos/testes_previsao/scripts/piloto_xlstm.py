# -*- coding: utf-8 -*-
"""Etapa A do plano: xLSTM (Beck et al., NeurIPS 2024), via NeuralForecast, treinado nestes dados.

xLSTM: LSTM "estendido". Duas celulas novas: sLSTM (memoria escalar com porta exponencial e normalizacao,
recorrente) e mLSTM (memoria em MATRIZ, regra de atualizacao covariancia, sem recorrencia entre ocultos:
treina em paralelo como atencao linear). Blocos residuais empilhados. No NeuralForecast o xLSTM e um
codificador (pilha de blocos) com decodificador MLP, igual ao LSTM/GRU do benchmark.

Interesse: e o LSTM moderno; LSTM/GRU do benchmark so com historico perdem da persistencia de ceu claro nas
usinas. Portao: grupo da frente num caso.

Protocolo IDENTICO ao das redes do 04 (mesmo COMUM_T, mesmo roda_nf: entrada 168 h, origem movel, 30 dias de
validacao, semente 42). Backbone mLSTM (padrao do NeuralForecast; o sLSTM pede nvcc para compilar o kernel).
O pacote `xlstm` monta caminhos de CUDA no import so porque a GPU existe e exige CUDA_HOME: aponta-se para a
pasta do torch (nada e compilado com o mLSTM).

Instalacao: uv pip install --no-deps xlstm==2.0.6 no previsao_gpu (dacite/omegaconf/einops ja estao).
Uso: python piloto_xlstm.py [caso ...]   (ambiente previsao_gpu, DISPOSITIVO=cuda)
Depois: python piloto_comum.py xLSTM <caso> A   (ambiente da biblioteca)
"""
import importlib
import os
import sys
import time
from pathlib import Path

import torch

os.environ.setdefault("CUDA_HOME", str(Path(torch.__file__).parent))
from neuralforecast import models as M  # noqa: E402

from comum import carrega  # noqa: E402
from piloto_comum import grava_piloto  # noqa: E402

R = importlib.import_module("04_redes_treinadas")

if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_prod"]
    for caso in casos:
        t0 = time.time()
        df = R.df_nf(carrega(caso), "A")
        jan, prev, n_par = R.roda_nf(df, lambda: M.xLSTM(**R.COMUM_T), caso, "A")
        f = grava_piloto("xLSTM", caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s | {n_par} parametros", flush=True)
