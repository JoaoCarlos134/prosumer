# -*- coding: utf-8 -*-
"""Etapa A do plano: CycleNet (Lin et al., NeurIPS 2024), treinado nestes dados, regime A.

Residual Cycle Forecasting (RCF): cada serie tem um ciclo aprendivel Q de comprimento W (24 h ou 168 h),
iniciado em zero e aprendido junto com o resto. Na janela normalizada (RevIN, aqui a mesma normalizacao
por janela do SparseTSF), subtrai-se o trecho de Q alinhado com a fase da janela; um backbone Linear
(L -> H) ou MLP (L -> 512 -> H) preve o RESIDUO; soma-se de volta o trecho de Q das 24 h seguintes. Na
implementacao oficial (github.com/ACAT-SCUT/CycleNet) cada canal tem o seu ciclo; aqui cada serie (casa
ou usina) e um canal. Mesmo autor do SparseTSF, que empatou com o melhor no consumo.

Protocolo IGUAL ao do SparseTSF no 04_redes_treinadas.py (treina_proprio): 168 h de entrada, origem movel
(treino do zero em cada dobra so com dados anteriores), janelas de treino a cada 6 h, 10% para parada
antecipada (paciencia 4, ate 30 epocas), L1, Adam 1e-3, lote 256, semente 42. A unica diferenca e que o
modelo recebe a fase (hora do dia ou da semana) e o indice da serie.

Interesse: muito pequeno (W x series + L x H parametros na versao Linear): candidato ao embarcado.
Portao: grupo da frente num caso (piloto_comum.py).

Uso: python piloto_cyclenet.py <caso> [W=24|168] [linear|mlp] [mse] [semente=42]   (ambiente previsao_gpu ou etapa_a)
     L1 e a perda do protocolo (igual ao SparseTSF); `mse` e a do artigo do CycleNet.
Depois: python piloto_comum.py CycleNet-<backbone>-W<W> <caso> A   (ambiente da biblioteca)
"""
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from comum import ENTRADA_NN, H, carrega, dobras, janelas
from piloto_comum import grava_piloto

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class CycleNet(nn.Module):
    def __init__(self, n_series, W, backbone="linear", L=ENTRADA_NN, Hh=H):
        super().__init__()
        self.W, self.L, self.H = W, L, Hh
        self.Q = nn.Parameter(torch.zeros(n_series, W))  # um ciclo por serie, iniciado em zero (oficial)
        if backbone == "linear":
            self.f = nn.Linear(L, Hh)
        else:
            self.f = nn.Sequential(nn.Linear(L, 512), nn.ReLU(), nn.Linear(512, Hh))

    def ciclo(self, serie, fase, n, desloc=0):
        idx = (fase[:, None] + desloc + torch.arange(n, device=fase.device)[None, :]) % self.W
        return torch.gather(self.Q[serie], 1, idx)

    def forward(self, x, serie, fase):  # x: (B, L) normalizado; fase = fase do 1o ponto da janela
        r = x - self.ciclo(serie, fase, self.L)
        return self.f(r) + self.ciclo(serie, fase, self.H, desloc=self.L)


def fase_de(ts, W):
    ts = pd.DatetimeIndex(ts)
    return (ts.hour if W == 24 else ts.dayofweek * 24 + ts.hour).to_numpy()


def treina(d, caso, ini, fim, W, backbone, perda="l1", semente=42, epocas=30):
    fp = nn.functional.l1_loss if perda == "l1" else nn.functional.mse_loss
    ids = {u: i for i, u in enumerate(sorted(d.unique_id.unique()))}
    Xs, Ys, Ss, Fs = [], [], [], []
    for uid, g in d.groupby("unique_id"):
        y = g.set_index("ds").y
        y = y[y.index < ini]
        tr = y.interpolate(limit_direction="both").to_numpy(np.float32)
        fases = fase_de(y.index, W)
        for k in range(ENTRADA_NN, len(tr) - H + 1, 6):  # janelas a cada 6 h, como o SparseTSF
            Xs.append(tr[k - ENTRADA_NN:k]); Ys.append(tr[k:k + H])
            Ss.append(ids[uid]); Fs.append(fases[k - ENTRADA_NN])
    X, Y = np.stack(Xs), np.stack(Ys)
    mu, sd = X.mean(1, keepdims=True), X.std(1, keepdims=True) + 1e-3
    X, Y = torch.tensor((X - mu) / sd).to(DEV), torch.tensor((Y - mu) / sd).to(DEV)
    S, F = torch.tensor(Ss).to(DEV), torch.tensor(np.array(Fs)).to(DEV)
    torch.manual_seed(semente); rng = np.random.default_rng(semente)
    idx = rng.permutation(len(X)); nval = len(X) // 10
    va, trn = idx[:nval], idx[nval:]
    m = CycleNet(len(ids), W, backbone).to(DEV)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3); melhor, estado, paciencia = 1e9, None, 0
    for _ in range(epocas):
        m.train()
        for i in range(0, len(trn), 256):
            b = trn[i:i + 256]
            opt.zero_grad(); loss = fp(m(X[b], S[b], F[b]), Y[b]); loss.backward(); opt.step()
        m.eval()
        with torch.no_grad():
            v = fp(m(X[va], S[va], F[va]), Y[va]).item()
        if v < melhor - 1e-4:
            melhor, estado, paciencia = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        else:
            paciencia += 1
            if paciencia >= 4:
                break
        rng.shuffle(trn)
    m.load_state_dict(estado); m.eval()
    jan = [w for w in janelas(d, caso, contexto=ENTRADA_NN) if ini <= w["dia"] <= fim]
    Xt = np.stack([w["y"] for w in jan]); mu, sd = Xt.mean(1, keepdims=True), Xt.std(1, keepdims=True) + 1e-3
    St = torch.tensor([ids[w["unique_id"]] for w in jan]).to(DEV)
    Ft = torch.tensor(np.array([fase_de([w["dia"] - pd.Timedelta(hours=ENTRADA_NN)], W)[0] for w in jan])).to(DEV)
    with torch.no_grad():
        p = m(torch.tensor((Xt - mu) / sd).to(DEV), St, Ft).cpu().numpy() * sd + mu
    return jan, list(p), sum(t.numel() for t in m.parameters())


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
        j, p, n_par = treina(d, caso, ini, fim, W, backbone, perda, semente)
        jan += j; prev += p
    f = grava_piloto(nome, caso, "A", jan, prev)
    print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
