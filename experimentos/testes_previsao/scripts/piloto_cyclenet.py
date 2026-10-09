# -*- coding: utf-8 -*-
"""Etapa A do plano: piloto do CycleNet (Lin et al., NeurIPS 2024), treinado nestes dados, regime A.

O modelo e o laco de treino estao em redes_proprias.py (os mesmos do benchmark: o CycleNet entrou no
04_redes_treinadas.py em 09/10/2026). Este script so varia o que o piloto testou: tamanho do ciclo W,
backbone (linear ou mlp), perda (L1 do protocolo ou MSE do artigo) e semente. Estudo e resultados em
docs/projeto/ESTUDO_ETAPA_A.md.

Uso: python piloto_cyclenet.py <caso> [W=24|168] [linear|mlp] [mse] [semente=42]   (ambiente previsao_gpu)
Depois: python piloto_comum.py CycleNet-<backbone>-W<W>[-mse][-s<semente>] <caso> A   (ambiente da biblioteca)
"""
import sys
import time

from comum import carrega, dobras
from piloto_comum import grava_piloto
from redes_proprias import DEV, CycleNet, treina_proprio

if __name__ == "__main__":
    args = sys.argv[1:]
    caso = next((a for a in args if a in ("usinas", "casas_prod", "casas_cons")), "casas_cons")
    W = int(next((a.split("=")[1] for a in args if a.startswith("W=")), "168" if caso == "casas_cons" else "24"))
    backbone = "mlp" if "mlp" in args else "linear"
    perda = "mse" if "mse" in args else "l1"
    semente = int(next((a.split("=")[1] for a in args if a.startswith("semente=")), "42"))
    nome = f"CycleNet-{backbone}-W{W}" + ("-mse" if perda == "mse" else "") + ("" if semente == 42 else f"-s{semente}")
    t0 = time.time()
    d = carrega(caso)
    jan, prev = [], []
    for ini, fim in dobras(caso):
        j, p, n_par = treina_proprio(d, caso, lambda n: CycleNet(n, W, backbone), ini, fim, perda=perda, semente=semente)
        jan += j; prev += p
    f = grava_piloto(nome, caso, "A", jan, prev)
    print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
