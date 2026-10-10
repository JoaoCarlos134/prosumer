# -*- coding: utf-8 -*-
"""Etapa A do plano: Mamba (Gu e Dao, 2023) e S-Mamba (Wang et al., 2024), treinados nestes dados, regime A.

Mamba: modelo de espaco de estados SELETIVO. Cada passo atualiza um estado oculto h_t = A_t h_{t-1} + B_t x_t,
com A, B, C e o passo de discretizacao dependentes da entrada (por isso "seletivo": o modelo decide o que
guardar e o que esquecer). Custo linear no comprimento, como uma RNN, mas treinavel em paralelo.

Duas formas de usar em series temporais:
- `Mamba` (Time-Series-Library, models/MambaSimple.py): token = HORA; mistura as series no embedding e varre o
  tempo. Como na TSLib, a previsao sao as ultimas 24 saidas da varredura causal sobre a entrada (a TSLib usa
  seq_len = pred_len; aqui a entrada e de 168 h, entao a 1a hora prevista so viu a entrada ate 23 h antes do
  corte: limitacao do desenho da TSLib, mantida e declarada).
- `S-Mamba` (Wang et al., "Is Mamba Effective for Time Series Forecasting?"; codigo oficial S-D-Mamba): token =
  SERIE (como o iTransformer): cada serie inteira vira um vetor e o Mamba varre as series nos dois sentidos
  (bidirecional), depois FFN e projecao para 24 h; normalizacao por janela.

Interesse: S-Mamba e outra forma de dependencia entre series (como DUET e Crossformer); Mamba e a familia
de espaco de estados, que nenhum modelo do benchmark representa.

Codigo: os dois oficiais usam `mamba_ssm`, extensao CUDA sem wheel para Windows (compila com nvcc). Aqui o
`mamba_ssm.Mamba` e trocado pelo bloco Mamba em PyTorch puro da TSLib (MambaSimple.MambaBlock, baseado no
mamba-minimal: mesma arquitetura, in_proj -> conv -> SiLU -> varredura seletiva -> porta -> out_proj; varredura
sequencial em vez do kernel fundido, entao mais lenta, numericamente o mesmo algoritmo). TSLib commit 4e938a1
em ~/.cache/tslib-repo; S-D-Mamba commit e7e8bf0 em ~/.cache/smamba-repo (ambos MIT). Os dois repositorios tem
pacotes `layers`: cada variante roda num processo.

Hiperparametros dos scripts oficiais de eletricidade (ECL), MSE, paciencia 3:
- Mamba (TSLib): d_model 128, 2 camadas, expand 2, d_state 16, d_conv 4, Adam 1e-4, lote 32.
- S-Mamba: d_model 512, d_ff 512, 3 camadas, d_state 16, Adam 1e-3, lote 16.
Protocolo nosso: entrada de 168 h, origem movel, janelas de treino a cada 6 h, 10% para parada antecipada, ate
30 epocas, semente 42; laco redes_proprias.treina_multivariado (o do DUET e do Crossformer).

Uso: DISPOSITIVO=cuda python piloto_mamba.py <Mamba|S-Mamba> [semente=42] [caso ...]   (ambiente previsao_gpu)
Depois: python piloto_comum.py <Mamba|S-Mamba> <caso> A   (ambiente da biblioteca)
"""
import importlib.util
import math
import sys
import time
import types
from pathlib import Path

import torch

from comum import ENTRADA_NN, H, carrega, dobras
from piloto_comum import grava_piloto
from redes_proprias import DEV, mamba, treina_multivariado

TSLIB = Path.home() / ".cache" / "tslib-repo"
SMAMBA = Path.home() / ".cache" / "smamba-repo"
VARIANTE = next((a for a in sys.argv[1:] if a in ("Mamba", "S-Mamba")), "S-Mamba")

sys.path.insert(0, str(SMAMBA if VARIANTE == "S-Mamba" else TSLIB))
sys.modules.setdefault("reformer_pytorch", types.SimpleNamespace(LSHSelfAttention=None))

# o MambaSimple.py da TSLib, carregado pelo caminho (seu `from layers.Embed import DataEmbedding` existe nos dois)
sys.modules["mamba_ssm"] = types.SimpleNamespace(Mamba=None)   # Embed.py do S-Mamba importa, sem usar
_spec = importlib.util.spec_from_file_location("tslib_mamba_simple", TSLIB / "models" / "MambaSimple.py")
MS = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(MS)


def Mamba(d_model, d_state=16, d_conv=4, expand=2):
    """Substituto do mamba_ssm.Mamba (mesma assinatura) com o bloco em PyTorch puro."""
    cfg = types.SimpleNamespace(d_model=d_model, d_ff=d_state, d_conv=d_conv)
    return MS.MambaBlock(cfg, d_model * expand, math.ceil(d_model / 16))


sys.modules["mamba_ssm"] = types.SimpleNamespace(Mamba=Mamba)


def fabrica(n):
    if VARIANTE == "S-Mamba":
        from model.S_Mamba import Model
        return Model(types.SimpleNamespace(
            seq_len=ENTRADA_NN, pred_len=H, output_attention=False, use_norm=True, d_model=512, d_ff=512,
            d_state=16, e_layers=3, embed="timeF", freq="h", dropout=0.1, activation="gelu",
            class_strategy="projection"))
    return mamba(n)   # o mesmo do 04_redes_treinadas.py


RECEITA = {"S-Mamba": dict(lr=1e-3, lote=16), "Mamba": dict(lr=1e-4, lote=32)}[VARIANTE]

if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_cons"]
    semente = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("semente=")), "42"))
    nome = VARIANTE if semente == 42 else f"{VARIANTE}-s{semente}"
    for caso in casos:
        t0 = time.time()
        d = carrega(caso)
        jan, prev = [], []
        for ini, fim in dobras(caso):
            j, p, n_par = treina_multivariado(d, caso, fabrica, lambda m, x: (m(x, None, None, None), 0.0), ini, fim,
                                              L=ENTRADA_NN, perda="mse", paciencia_max=3, semente=semente, **RECEITA)
            jan += j; prev += p
            torch.cuda.empty_cache()
        f = grava_piloto(nome, caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
