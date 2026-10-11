# -*- coding: utf-8 -*-
"""Etapa A do plano: Time-LLM (Jin et al., ICLR 2024), treinado nestes dados, regime A, piloto CURTO (so consumo).

Time-LLM "reprograma" um LLM congelado para series: a serie (normalizada por janela) e cortada em patches de
16 h; uma camada de atencao cruzada traduz cada patch para uma combinacao de ~1.000 "prototipos de texto"
(combinacoes lineares aprendidas do vocabulario do LLM); antes dos patches vai um PROMPT em texto com o contexto
do conjunto e estatisticas da janela (min, max, mediana, tendencia, 5 maiores defasagens). O LLM (GPT-2 aqui,
congelado) processa prompt + patches e uma cabeca linear projeta a saida nas 24 h. So a reprogramacao, o
mapeamento do vocabulario e a cabeca treinam.

Por que piloto curto (decisao de 10/10/2026): Tan et al., "Are Language Models Actually Useful for Time Series
Forecasting?" (NeurIPS 2024) mostram que tirar o LLM desses modelos nao piora o resultado. Entao o piloto mede
exatamente isso nos nossos dados, com duas variantes no mesmo protocolo:
- `Time-LLM`: GPT-2 small (124 M, congelado), o padrao do NeuralForecast;
- `Time-LLM-semLLM`: a ablacao "w/o LLM" de Tan et al.: o LLM vira identidade (prompt + patches reprogramados
  vao direto para a cabeca), o resto igual.
Portao: grupo da frente no consumo; e, para valer o custo, o LLM precisa ganhar da propria ablacao.

Codigo: NeuralForecast 3.1.9 (`M.TimeLLM`, ja no previsao_gpu), GPT-2 do HuggingFace (cache local). Protocolo e
configuracao comuns do 04_redes_treinadas.py (COMUM_T: entrada 168 h, 500 passos, parada antecipada, robust por
janela), com `windows_batch_size` 32 (era 128): em 08/10 o Time-LLM derrubou a maquina quatro vezes por memoria.
Guarda de memoria: o processo se encerra se passar de LIMITE_GB de memoria privada.

Uso: DISPOSITIVO=cuda python piloto_timellm.py [semLLM] [teste] [caso ...]   (ambiente previsao_gpu; padrao casas_cons)
Depois: python piloto_comum.py Time-LLM[-semLLM] <caso> A   (ambiente da biblioteca)
"""
import importlib
import os
import sys
import threading
import time
import types

import psutil
import torch
from neuralforecast import models as M

from comum import carrega
from piloto_comum import grava_piloto

R = importlib.import_module("04_redes_treinadas")
SEM_LLM = "semLLM" in sys.argv[1:]
TESTE = "teste" in sys.argv[1:]  # 2 passos de treino: so confere que roda
LIMITE_GB = 18
PROMPT = {"casas_cons": "Hourly electricity consumption of a house in a rural community in Ireland.",
          "casas_prod": "Hourly rooftop solar photovoltaic generation of a house in Ireland.",
          "usinas": "Hourly generation of a small solar photovoltaic plant in southern Brazil."}


def guarda():
    p = psutil.Process()
    while True:
        gb = p.memory_info().private / 2**30
        if gb > LIMITE_GB:
            print(f"ABORTADO: memoria privada {gb:.1f} GB > {LIMITE_GB} GB", flush=True)
            os._exit(3)
        time.sleep(5)


class SemLLM(torch.nn.Module):
    """Ablacao 'w/o LLM' (Tan et al. 2024): devolve a propria entrada; mantem as embeddings do GPT-2 para o prompt."""

    def __init__(self, llm):
        super().__init__()
        self.emb = llm.get_input_embeddings()

    def get_input_embeddings(self):
        return self.emb

    def forward(self, inputs_embeds):
        return types.SimpleNamespace(last_hidden_state=inputs_embeds)


def fabrica(caso):
    m = M.TimeLLM(prompt_prefix=PROMPT[caso], **{**R.COMUM_T, "windows_batch_size": 32,
                                                  "inference_windows_batch_size": 32,
                                                  **({"max_steps": 2, "val_check_steps": 1} if TESTE else {})})
    if SEM_LLM:
        m.llm = SemLLM(m.llm)
    return m


if __name__ == "__main__":
    threading.Thread(target=guarda, daemon=True).start()
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_cons"]
    nome = ("Time-LLM-semLLM" if SEM_LLM else "Time-LLM") + ("-teste" if TESTE else "")
    for caso in casos:
        t0 = time.time()
        df = R.df_nf(carrega(caso), "A")
        jan, prev, n_par = R.roda_nf(df, lambda: fabrica(caso), caso, "A")
        f = grava_piloto(nome, caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s | {n_par} parametros "
              f"| pico de memoria privada {psutil.Process().memory_info().peak_pagefile / 2**30:.1f} GB", flush=True)
