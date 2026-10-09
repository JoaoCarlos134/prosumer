# -*- coding: utf-8 -*-
"""Piloto F2(e) do plano: ajuste fino do TTM-r2 nos nossos dados, regime A.

Pergunta: adaptar um fundacional pequeno aos dados da casa/usina melhora o zero-shot? Interessa a
biblioteca porque o TTM (~1 M de parametros) e o candidato principal ao embarcado: se o ajuste fino
valer, a biblioteca oferece `ajusta()` para ele.

Protocolo (o mesmo das redes do benchmark, origem movel):
- um ajuste por dobra, so com dados ANTERIORES ao inicio da dobra (comum.dobras);
- janelas de treino: 1024 h de historico -> 24 h seguintes, andando um dia por vez, alvo sem buraco;
  o historico e interpolado so com o passado da janela, como em comum.janelas;
- espinha dorsal (backbone) congelada, treina so decoder e cabeca: o ajuste leve que os autores do TTM
  recomendam para pouco dado, e barato em CPU;
- parada antecipada pelos 10% de janelas de treino mais RECENTES (validacao temporal, nao sorteada);
- previsao das janelas de teste da dobra com o mesmo `comum.janelas` dos outros fundacionais.
Comparacao: o TTM-r2 zero-shot publicado no metricas.csv. Portao: skill +0,02 ou mais.

Uso: python piloto_ttm_ajuste.py [caso ...] [--variante decoder|cabeca]   (padrao: casas_cons, decoder;
     ambiente previsao, so no Lactec)
Depois: python piloto_comum.py TTM-r2-ajustado <caso> A   (ambiente da biblioteca)
"""
import sys
import time

import numpy as np
import pandas as pd
import torch

try:
    import truststore
    truststore.inject_into_ssl()  # proxy do Lactec
except ImportError:
    pass

from comum import CONTEXTO_FM, H, carrega, dobras, janelas
from piloto_comum import grava_piloto

torch.manual_seed(42)
np.random.seed(42)
MAX_EPOCAS, PACIENCIA, LOTE = 10, 2, 64
# Variantes (piloto de 09/10/2026): 'decoder' = decoder + cabeca, lr 1e-3 (1a rodada: perdeu 0,043 de skill);
# 'cabeca' = so a cabeca de saida, lr 1e-4 (o ajuste mais leve possivel).
VARIANTE = sys.argv[sys.argv.index("--variante") + 1] if "--variante" in sys.argv else "decoder"
LR = {"decoder": 1e-3, "cabeca": 1e-4}[VARIANTE]
NOME = {"decoder": "TTM-r2-ajustado", "cabeca": "TTM-r2-ajustado-cabeca"}[VARIANTE]


def janelas_treino(d, ate):
    """(contexto, alvo, inicio do alvo) de todas as series, com o alvo terminando antes de `ate`."""
    X, Y, T = [], [], []
    for _, g in d.groupby("unique_id"):
        s = g.set_index("ds")["y"]
        s = s[s.index < ate]
        hist = s.interpolate(limit_direction="both").fillna(0.0).to_numpy(np.float32)
        bruto = s.to_numpy(np.float32)
        dias = np.arange(CONTEXTO_FM, len(s) - H + 1, 24)
        for t in dias:
            alvo = bruto[t:t + H]
            if np.isnan(alvo).any():
                continue
            X.append(hist[t - CONTEXTO_FM:t])
            Y.append(alvo)
            T.append(s.index[t])
    return np.stack(X), np.stack(Y), np.array(T, dtype="datetime64[ns]")


def ajusta(X, Y, T):
    from tsfm_public.toolkit.get_model import get_model
    m = get_model("ibm-granite/granite-timeseries-ttm-r2", context_length=CONTEXTO_FM, prediction_length=H)
    for nome, p in m.named_parameters():
        p.requires_grad = nome.startswith("head") if VARIANTE == "cabeca" else "backbone" not in nome
    treinaveis = [p for p in m.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(treinaveis, lr=LR)
    # Validacao = os 10% de janelas mais RECENTES no tempo (de todas as series), nao as ultimas da pilha,
    # que seriam as ultimas casas.
    corte = np.quantile(T.astype("int64"), 0.9)
    val = T.astype("int64") >= corte
    Xt, Yt, Xv, Yv = X[~val], Y[~val], X[val], Y[val]
    xv, yv = torch.tensor(Xv)[:, :, None], torch.tensor(Yv)
    melhor, estado, sem_melhora, epocas = np.inf, None, 0, 0
    for ep in range(MAX_EPOCAS):
        m.train()
        idx = np.random.permutation(len(Xt))
        for i in range(0, len(idx), LOTE):
            b = idx[i:i + LOTE]
            x, y = torch.tensor(Xt[b])[:, :, None], torch.tensor(Yt[b])
            perda = torch.mean((m(past_values=x).prediction_outputs[:, :H, 0] - y) ** 2)
            opt.zero_grad()
            perda.backward()
            opt.step()
        m.eval()
        with torch.no_grad():
            v = float(torch.mean((m(past_values=xv).prediction_outputs[:, :H, 0] - yv) ** 2))
        epocas = ep + 1
        if v < melhor - 1e-6:
            melhor, estado, sem_melhora = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        else:
            sem_melhora += 1
            if sem_melhora >= PACIENCIA:
                break
    m.load_state_dict(estado)
    return m.eval(), epocas, sum(p.numel() for p in treinaveis)


def roda(caso):
    d = carrega(caso)
    jan = janelas(d, caso, contexto=CONTEXTO_FM)
    todas_j, todas_p, info = [], [], []
    for k, (ini, fim) in enumerate(dobras(caso), start=1):
        t0 = time.time()
        X, Y, T = janelas_treino(d, ini)
        m, epocas, n_trein = ajusta(X, Y, T)
        da_dobra = [w for w in jan if ini <= w["dia"] <= fim]
        with torch.no_grad():
            for i in range(0, len(da_dobra), 256):
                lote = da_dobra[i:i + 256]
                x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]
                todas_p += list(m(past_values=x).prediction_outputs[:, :H, 0].numpy())
        todas_j += da_dobra
        info.append(f"dobra {k}: {len(X)} janelas de treino, {epocas} epocas, {time.time() - t0:.0f} s")
        print(f"  {caso} {info[-1]} ({n_trein} parametros treinados)", flush=True)
    return todas_j, todas_p


if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if not a.startswith("--") and a not in ("decoder", "cabeca")]
    for caso in casos or ["casas_cons"]:
        t0 = time.time()
        jan, prev = roda(caso)
        f = grava_piloto(NOME, caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s", flush=True)
