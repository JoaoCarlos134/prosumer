# -*- coding: utf-8 -*-
"""Etapa A do plano: MOMENT (Goswami et al., ICML 2024), codificador congelado + cabeca linear treinada.

MOMENT: codificador T5 pre-treinado por reconstrucao de patches mascarados no "Time-series Pile" (13 dominios).
Entrada fixa de 512 pontos em 64 patches de 8; normalizacao por janela (RevIN). Para prever, o artigo faz
"linear probing": o codificador fica congelado e so uma cabeca linear (64 x d_model -> 24) e treinada.

Como o codificador nao muda, as saidas dele sao calculadas UMA vez por dobra e guardadas na GPU em fp16; o
treino da cabeca roda sobre esse cache (eficiencia: o codificador nao e chamado a cada epoca). A cabeca e a do
proprio MOMENT (`m.head`), com os pesos iniciais dele.

Protocolo das redes proprias (redes_proprias.py), com o que o MOMENT exige: entrada de 512 h (nao 168),
origem movel (cabeca treinada do zero em cada dobra so com o passado), janelas de treino a cada 6 h, 10% para
parada antecipada (paciencia 4, ate 30 epocas), Adam 1e-3, lote 256, perda MSE (a do artigo), semente 42.

Uso: python piloto_moment.py [small|base|large] [caso ...]   (ambiente previsao_gpu; momentfm com --no-deps)
Depois: python piloto_comum.py MOMENT-<tamanho> <caso> A   (ambiente da biblioteca)
"""
import sys
import time

import numpy as np
import torch
import torch.nn as nn

from comum import H, carrega, dobras, janelas
from piloto_comum import grava_piloto

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
L = 512


def carrega_moment(tamanho):
    from momentfm import MOMENTPipeline
    m = MOMENTPipeline.from_pretrained(
        f"AutonLab/MOMENT-1-{tamanho}",
        model_kwargs={"task_name": "forecasting", "forecast_horizon": H, "head_dropout": 0.1,
                      "freeze_encoder": True, "freeze_embedder": True})
    m.init()
    return m.to(DEV).eval()


@torch.no_grad()
def codifica(m, X, lote=256):
    """X: (N, 512) ja normalizado por janela -> saida do codificador (N, 1, 64, d_model) em fp16."""
    out = []
    for i in range(0, len(X), lote):
        x = torch.as_tensor(X[i:i + lote], device=DEV)[:, None, :]
        b, c, _ = x.shape
        mascara = torch.ones((b, L), device=DEV)
        e = m.patch_embedding(m.tokenizer(x=x), mask=mascara)
        n = e.shape[2]
        e = e.reshape(b * c, n, -1)
        from momentfm.utils.masking import Masking
        att = Masking.convert_seq_to_patch_view(mascara, m.patch_len).repeat_interleave(c, dim=0)
        h = m.encoder(inputs_embeds=e, attention_mask=att).last_hidden_state
        out.append(h.reshape(b, c, n, -1).half())
    return torch.cat(out)


def treina_cabeca(m, d, caso, ini, fim, epocas=30):
    Xs, Ys = [], []
    for _, g in d.groupby("unique_id"):
        y = g.set_index("ds").y
        tr = y[y.index < ini].interpolate(limit_direction="both").to_numpy(np.float32)
        for k in range(L, len(tr) - H + 1, 6):
            Xs.append(tr[k - L:k]); Ys.append(tr[k:k + H])
    X, Y = np.stack(Xs), np.stack(Ys)
    mu, sd = X.mean(1, keepdims=True), X.std(1, keepdims=True) + 1e-3
    E = codifica(m, (X - mu) / sd)
    Y = torch.tensor((Y - mu) / sd, device=DEV)
    torch.manual_seed(42); rng = np.random.default_rng(42)
    idx = rng.permutation(len(E)); nval = len(E) // 10
    va, trn = idx[:nval], idx[nval:]
    cabeca = m.head
    for p in cabeca.parameters():  # cabeca do zero em cada dobra (pesos iniciais guardados)
        p.requires_grad_(True)
    opt = torch.optim.Adam(cabeca.parameters(), lr=1e-3); melhor, estado, paciencia = 1e9, None, 0
    for _ in range(epocas):
        cabeca.train()
        for i in range(0, len(trn), 256):
            b = trn[i:i + 256]
            opt.zero_grad()
            loss = nn.functional.mse_loss(cabeca(E[b].float())[:, 0, :], Y[b]); loss.backward(); opt.step()
        cabeca.eval()
        with torch.no_grad():
            v = nn.functional.mse_loss(cabeca(E[va].float())[:, 0, :], Y[va]).item()
        if v < melhor - 1e-4:
            melhor, estado, paciencia = v, {k: t.clone() for k, t in cabeca.state_dict().items()}, 0
        else:
            paciencia += 1
            if paciencia >= 4:
                break
        rng.shuffle(trn)
    cabeca.load_state_dict(estado); cabeca.eval()
    del E
    jan = [w for w in janelas(d, caso, contexto=L) if ini <= w["dia"] <= fim]
    Xt = np.stack([w["y"] for w in jan]); mu, sd = Xt.mean(1, keepdims=True), Xt.std(1, keepdims=True) + 1e-3
    with torch.no_grad():
        p = cabeca(codifica(m, (Xt - mu) / sd).float())[:, 0, :].cpu().numpy() * sd + mu
    return jan, list(p), sum(t.numel() for t in cabeca.parameters())


if __name__ == "__main__":
    args = sys.argv[1:]
    tamanho = next((a for a in args if a in ("small", "base", "large")), "small")
    casos = [a for a in args if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_prod"]
    for caso in casos:
        t0 = time.time()
        d = carrega(caso)
        m = carrega_moment(tamanho)
        inicial = {k: t.clone() for k, t in m.head.state_dict().items()}
        jan, prev = [], []
        for ini, fim in dobras(caso):
            m.head.load_state_dict(inicial)
            j, p, n_cab = treina_cabeca(m, d, caso, ini, fim)
            jan += j; prev += p
            torch.cuda.empty_cache()
        f = grava_piloto(f"MOMENT-{tamanho}", caso, "A", jan, prev)
        n_tot = sum(t.numel() for t in m.parameters())
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_tot} parametros "
              f"({n_cab} treinados)", flush=True)
