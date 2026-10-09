# -*- coding: utf-8 -*-
"""Piloto F1(f) do plano: FlowState (IBM), zero-shot, regime A.

FlowState: codificador de espaco de estados S5 + decodificador de base funcional, ~9 M de parametros;
o `scale_factor` ajusta o passo de discretizacao ao periodo da serie (horario = 24/24 = 1,0, ver
tsfm_public.models.flowstate.utils.get_fixed_factor). Mesmas janelas dos outros fundacionais
(1024 h de historico, 24 h a frente).

Interesse para a biblioteca: e pequeno como o TTM (candidato ao embarcado) e devolve quantis.
Portao: grupo da frente num caso (ver piloto_comum.py). So roda na maquina do Lactec: e o granite-tsfm
completo que tem o FlowState.

Uso: python piloto_flowstate.py [caso ...]   (padrao: casas_cons; ambiente previsao)
Depois: python piloto_comum.py FlowState <caso> A   (ambiente da biblioteca)
"""
import sys
import time

import numpy as np
import torch

try:
    import truststore
    truststore.inject_into_ssl()  # proxy do Lactec
except ImportError:
    pass

from comum import CONTEXTO_FM, H, carrega, janelas
from piloto_comum import grava_piloto

MODELO = "ibm-granite/granite-timeseries-flowstate-r1"


def flowstate(jan):
    from tsfm_public import FlowStateForPrediction
    m = FlowStateForPrediction.from_pretrained(MODELO).eval()
    n_par = sum(p.numel() for p in m.parameters())
    out = []
    with torch.no_grad():
        for i in range(0, len(jan), 128):
            lote = jan[i:i + 128]
            x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]
            r = m(past_values=x, scale_factor=1.0, prediction_length=H, batch_first=True)
            out += list(r.prediction_outputs[:, :H, 0].numpy())
    return out, n_par


if __name__ == "__main__":
    for caso in sys.argv[1:] or ["casas_cons"]:
        t0 = time.time()
        jan = janelas(carrega(caso), caso, contexto=CONTEXTO_FM)
        prev, n_par = flowstate(jan)
        dt = time.time() - t0
        f = grava_piloto("FlowState", caso, "A", jan, prev)
        # avaliar no ambiente da biblioteca: python piloto_comum.py FlowState <caso> A segundos=... parametros=...
        print(f"OK {f.name} | {len(jan)} janelas | {dt:.0f} s | {n_par} parametros", flush=True)
