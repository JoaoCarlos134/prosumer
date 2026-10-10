# -*- coding: utf-8 -*-
"""Etapa A do plano: Crossformer (Zhang e Yan, ICLR 2023), treinado nestes dados, regime A, MULTIVARIADO.

Crossformer: cada serie e cortada em segmentos de 12 h (DSW, "dimension-segment-wise embedding"), virando uma
grade series x segmentos. A atencao em DOIS ESTAGIOS (TSA) alterna atencao no tempo (entre segmentos da mesma
serie) e atencao entre series (por um pequeno conjunto de "roteadores", custo linear no numero de series).
Codificador hierarquico (junta segmentos vizinhos a cada camada) e decodificador que preve por segmento em
cada escala. Foi o primeiro transformer a modelar de proposito a dependencia entre series.

Interesse: dependencia entre series (como o DUET, outro mecanismo). Portao: grupo da frente num caso.

Codigo: so o modelo da Time-Series-Library (github.com/thuml/Time-Series-Library, commit 4e938a1, MIT),
clonada em ~/.cache/tslib-repo; o `reformer_pytorch` (so usado pelo Reformer) vira um modulo vazio.
Hiperparametros do script oficial da TSLib para eletricidade (ECL): d_model 256, d_ff 512, 2 camadas, 8
cabecas, factor 3, dropout 0,1, segmento de 12, perda MSE, Adam 1e-4, lote 16, paciencia 3. O modelo nao
normaliza a entrada (a TSLib padroniza o conjunto com o treino): cada serie e padronizada com media e desvio
do treino da dobra. Protocolo nosso: entrada de 168 h, origem movel, janelas de treino a cada 6 h, 10% para
parada antecipada, ate 30 epocas, semente 42. Laco: redes_proprias.treina_multivariado (o mesmo do DUET); modelo e receita: redes_proprias.crossformer,
usados tambem pelo 04_redes_treinadas.py (entrou no benchmark em 10/10/2026).

Uso: DISPOSITIVO=cuda python piloto_crossformer.py [semente=42] [caso ...]   (ambiente previsao_gpu; padrao casas_cons)
Depois: python piloto_comum.py Crossformer <caso> A   (ambiente da biblioteca)
"""
import sys
import time

import torch

from comum import carrega, dobras
from piloto_comum import grava_piloto
from redes_proprias import DEV, RECEITA_CROSSFORMER, chama_tslib, crossformer, treina_multivariado


if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_cons"]
    semente = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("semente=")), "42"))
    nome = "Crossformer" if semente == 42 else f"Crossformer-s{semente}"
    for caso in casos:
        t0 = time.time()
        d = carrega(caso)
        jan, prev = [], []
        for ini, fim in dobras(caso):
            j, p, n_par = treina_multivariado(d, caso, crossformer, chama_tslib, ini, fim, semente=semente,
                                              **RECEITA_CROSSFORMER)
            jan += j; prev += p
            torch.cuda.empty_cache()
        f = grava_piloto(nome, caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
