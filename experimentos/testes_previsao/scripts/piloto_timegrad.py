# -*- coding: utf-8 -*-
"""Etapa A do plano: TimeGrad (Rasul et al., ICML 2021), treinado nestes dados, regime A, MULTIVARIADO e PROBABILISTICO.

TimeGrad: uma RNN (GRU) le o passado de TODAS as series juntas (valores defasados em 1, 24 e 168 h, um embedding
do indice de cada serie e atributos de calendario em seno/cosseno) e resume tudo num estado h_t. Em cada passo
futuro, a distribuicao do vetor de valores x_t (todas as series) e um modelo de DIFUSAO (DDPM) condicionado em
h_t: no treino, soma-se ruido gaussiano a x_t em um de 100 niveis e uma rede convolucional dilatada (epsilon_theta)
aprende a prever o ruido; na previsao, parte-se de ruido puro e removem-se os 100 niveis, uma hora de cada vez
(autorregressivo: a amostra de uma hora entra como defasagem da seguinte). Saida: amostras -> faixa e
dependencia entre series sem supor forma (nem gaussiana nem copula). Previsao pontual aqui: mediana de 100
amostras (grava tambem a media, `-media`).

Interesse: faixa (amostras) com dependencia entre series, aprendida nestes dados (o Lag-Llama era zero-shot).
Portao: grupo da frente num caso.

Codigo: oficial, pytorch-ts (github.com/zalandoresearch/pytorch-ts, commit 7860c96, MIT), clonado em
~/.cache/pytorch-ts-repo e posto no sys.path; nada instalado. Roda no ~/.venvs/lagllama (gluonts 0.14.4); o
pytorch-ts importa `gluonts.torch.distributions.output`, que no 0.14 se chama `distribution_output`: um apelido
de modulo resolve (mesmas classes). Hiperparametros do exemplo oficial de eletricidade (Time-Grad-Electricity):
GRU 2 camadas x 40, contexto 24 h (+ defasagem maxima 168 h), 100 passos de difusao, beta ate 0,1 linear, perda
L2, escala pela media, Adam 1e-3, 20 epocas de 100 lotes de 64. Protocolo nosso: origem movel (treino do zero
em cada dobra, so com dados anteriores a ela), quadro largo interpolado de forma causal (corta, depois preenche),
como redes_proprias.treina_multivariado. Sem parada antecipada (o exemplo oficial nao usa).

Uso: python piloto_timegrad.py [teste] [caso ...]   (ambiente lagllama; padrao casas_prod)
     `teste`: 1 epoca de 5 lotes, 5 dias, 10 amostras, so para conferir que roda
Depois: python piloto_comum.py TimeGrad <caso> A   (ambiente da biblioteca)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".cache" / "pytorch-ts-repo"))
import gluonts.torch.distributions.distribution_output as _do  # noqa: E402
sys.modules.setdefault("gluonts.torch.distributions.output", _do)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from comum import H, carrega, dobras, janelas  # noqa: E402
from piloto_comum import grava_piloto  # noqa: E402
from redes_proprias import _preenche, largo  # noqa: E402

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
TESTE = "teste" in sys.argv[1:]
HIST = 24 * 14  # historico entregue na previsao (o modelo usa 24 + 168)


def estimador(n):
    from pts import Trainer
    from pts.model.time_grad import TimeGradEstimator
    import pts.model.time_grad.time_grad_estimator as tge
    if not getattr(tge, "_sem_freq", False):  # o PyTorchPredictor do gluonts 0.14 nao aceita mais `freq`
        orig = tge.PyTorchPredictor
        tge.PyTorchPredictor = lambda freq=None, **k: orig(**k)
        tge._sem_freq = True
    return TimeGradEstimator(
        target_dim=n, prediction_length=H, context_length=H, cell_type="GRU", input_size=n * 4 + 4, freq="H",
        loss_type="l2", scaling=True, diff_steps=100, beta_end=0.1, beta_schedule="linear",
        num_parallel_samples=10 if TESTE else 100,
        trainer=Trainer(device=DEV, epochs=1 if TESTE else 20, learning_rate=1e-3,
                        num_batches_per_epoch=5 if TESTE else 100, batch_size=64))


def dobra(d, caso, ini, fim, w, cols):
    from gluonts.dataset.common import ListDataset
    tr = _preenche(w[w.index < ini])
    ds_tr = ListDataset([{"start": pd.Period(tr.index[0], freq="H"), "target": tr.to_numpy(np.float32).T}],
                        freq="H", one_dim_target=False)
    torch.manual_seed(42); np.random.seed(42)
    est = estimador(len(cols))
    # o amostrador padrao tira em media 1 janela por passada sobre a serie; com UMA serie multivariada longa quase
    # toda passada sai vazia e o gluonts desiste. 100 janelas por passada: as janelas continuam sorteadas
    from gluonts.transform import ExpectedNumInstanceSampler
    est.train_sampler = ExpectedNumInstanceSampler(num_instances=100, min_past=est.history_length, min_future=H)
    pred = est.train(ds_tr, num_workers=0, prefetch_factor=None)  # torch novo recusa prefetch sem workers
    n_par = sum(p.numel() for p in pred.prediction_net.parameters())
    jan = [j for j in janelas(d, caso, contexto=HIST) if ini <= j["dia"] <= fim]
    dias = sorted({j["dia"] for j in jan})[:5 if TESTE else None]
    jan = [j for j in jan if j["dia"] in dias]
    entradas = []
    for dia in dias:
        x = _preenche(w.loc[:dia - pd.Timedelta(hours=1)].tail(HIST))
        entradas.append({"start": pd.Period(x.index[0], freq="H"), "target": x.to_numpy(np.float32).T})
    med, media = {}, {}
    for dia, f in zip(dias, pred.predict(ListDataset(entradas, freq="H", one_dim_target=False))):
        s = f.samples  # (amostras, H, n)
        for c, uid in enumerate(cols):
            med[(uid, dia)] = np.median(s[:, :H, c], axis=0); media[(uid, dia)] = s[:, :H, c].mean(axis=0)
    chave = [(j["unique_id"], j["dia"]) for j in jan]
    return jan, [med[k] for k in chave], [media[k] for k in chave], n_par


if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_prod"]
    for caso in casos:
        t0 = time.time()
        d = carrega(caso)
        w = largo(d); cols = list(w.columns)
        jan, prev, media = [], [], []
        for ini, fim in dobras(caso)[:1 if TESTE else None]:
            j, p, m, n_par = dobra(d, caso, ini, fim, w, cols)
            jan += j; prev += p; media += m
            torch.cuda.empty_cache()
        nome = "TimeGrad-teste" if TESTE else "TimeGrad"
        f = grava_piloto(nome, caso, "A", jan, prev)
        grava_piloto(nome + "-media", caso, "A", jan, media)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
