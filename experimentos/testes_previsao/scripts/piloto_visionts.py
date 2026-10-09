# -*- coding: utf-8 -*-
"""Etapa A do plano: VisionTS e VisionTS++, zero-shot, regime A.

VisionTS (Chen et al., ICML 2025): dobra a serie pelo periodo (24 h) numa imagem cinza de 24 linhas x
N dias, redimensiona para 224 x 224 e usa um autoencoder mascarado de IMAGENS (MAE ViT-Base, ImageNet,
sem nenhuma serie temporal no pre-treino) para "pintar" a parte da direita, que e o futuro. VisionTS++
(2025) continua o pre-treino desse MAE em series temporais e devolve 9 quantis.

Interesse: a sazonalidade diaria forte da geracao FV e o caso ideal de um modelo que enxerga o dia
como uma coluna de pixels. Portao: grupo da frente num caso (ver piloto_comum.py).

Mesmas janelas dos outros fundacionais (1024 h de historico, 24 h a frente). Pesos fora do repositorio,
em ~/.cache/visionts. Ambiente: ~/.venvs/previsao_gpu (visionts/timm/torchvision instalados com --no-deps).

Uso: python piloto_visionts.py [VisionTS|VisionTS++] [caso ...]   (padrao: os dois, usinas)
Depois: python piloto_comum.py <modelo> <caso> A   (ambiente da biblioteca)
"""
import sys
import time
from pathlib import Path

import numpy as np
import torch

from comum import CONTEXTO_FM, H, carrega, janelas
from piloto_comum import grava_piloto

CKPT = Path.home() / ".cache" / "visionts"
DISP = "cuda" if torch.cuda.is_available() else "cpu"


def preve(nome, jan):
    """VisionTS++ usa a funcao do benchmark (03_fundacionais.visiontspp), sem copia; o VisionTS original,
    que nao passou no piloto, so existe aqui."""
    if nome == "VisionTS++":
        import importlib
        return importlib.import_module("03_fundacionais").visiontspp(jan), 115059712
    from visionts import VisionTS
    m = VisionTS(arch="mae_base", finetune_type="ln", ckpt_dir=str(CKPT))
    m.update_config(context_len=CONTEXTO_FM, pred_len=H, periodicity=24)
    m = m.to(DISP).eval()
    n_par = sum(p.numel() for p in m.parameters())
    out = []
    with torch.no_grad():
        for i in range(0, len(jan), 64):
            x = torch.tensor(np.stack([w["y"] for w in jan[i:i + 64]]))[:, :, None].to(DISP)
            out += list(m(x)[:, :H, 0].float().cpu().numpy())
    return out, n_par


if __name__ == "__main__":
    args = sys.argv[1:]
    nomes = [a for a in args if a.startswith("VisionTS")] or ["VisionTS", "VisionTS++"]
    casos = [a for a in args if not a.startswith("VisionTS")] or ["usinas"]
    for caso in casos:
        jan = janelas(carrega(caso), caso, contexto=CONTEXTO_FM)
        for nome in nomes:
            t0 = time.time()
            prev, n_par = preve(nome, jan)
            dt = time.time() - t0
            f = grava_piloto(nome, caso, "A", jan, prev)
            print(f"OK {f.name} | {len(jan)} janelas | {dt:.0f} s em {DISP} | {n_par} parametros", flush=True)
