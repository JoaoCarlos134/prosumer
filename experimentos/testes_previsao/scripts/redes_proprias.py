# -*- coding: utf-8 -*-
"""Redes proprias (PyTorch puro) e o laco de treino delas: um lugar so para o benchmark e os pilotos.

Antes viviam dentro do 04_redes_treinadas.py e os pilotos copiavam o codigo; agora o 04 e o
piloto_cyclenet.py importam daqui (09/10/2026). O laco `treina_proprio` e o mesmo que produziu as
entradas de SparseTSF e ResNet-1D: mesma ordem de operacoes e de sementes, entao refazer da o mesmo.

Protocolo: 168 h de entrada, 24 h de saida, origem movel (treino do zero em cada dobra so com o
passado), janelas de treino a cada 6 h, 10% aleatorios para parada antecipada (paciencia 4, ate 30
epocas), Adam 1e-3, lote 256, normalizacao por janela (media e desvio da entrada).
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from comum import DISPOSITIVO, ENTRADA_NN, H, janelas

DEV = torch.device("cuda" if DISPOSITIVO == "cuda" and torch.cuda.is_available() else "cpu")


class SparseTSF(nn.Module):
    """Lin et al. (2024): subamostra a serie por periodo (24 h) e aplica uma linear compartilhada."""
    def __init__(self, L=ENTRADA_NN, Hh=H, p=24):
        super().__init__(); self.p = p
        self.conv = nn.Conv1d(1, 1, kernel_size=1 + 2 * (p // 2), padding=p // 2, bias=False)
        self.lin = nn.Linear(L // p, Hh // p, bias=False)
    def forward(self, x):                       # x: (B, L) normalizado
        B, L = x.shape
        x = self.conv(x[:, None, :])[:, 0, :] + x
        x = x.reshape(B, L // self.p, self.p).permute(0, 2, 1)       # (B, p, L/p)
        return self.lin(x).permute(0, 2, 1).reshape(B, -1)


class Bloco(nn.Module):
    def __init__(self, ci, co):
        super().__init__()
        self.c = nn.Sequential(nn.Conv1d(ci, co, 7, padding=3), nn.BatchNorm1d(co), nn.ReLU(),
                               nn.Conv1d(co, co, 5, padding=2), nn.BatchNorm1d(co), nn.ReLU(),
                               nn.Conv1d(co, co, 3, padding=1), nn.BatchNorm1d(co))
        self.s = nn.Sequential(nn.Conv1d(ci, co, 1), nn.BatchNorm1d(co)) if ci != co else nn.Identity()
    def forward(self, x):
        return torch.relu(self.c(x) + self.s(x))


class ResNet1D(nn.Module):
    """ResNet para series (Wang et al., 2017), com cabeca de regressao de 24 saidas."""
    def __init__(self, Hh=H):
        super().__init__()
        self.b = nn.Sequential(Bloco(1, 32), Bloco(32, 64), Bloco(64, 64))
        self.head = nn.Linear(64, Hh)
    def forward(self, x):
        return self.head(self.b(x[:, None, :]).mean(-1))


class CycleNet(nn.Module):
    """Lin et al. (NeurIPS 2024), Residual Cycle Forecasting. Um ciclo aprendivel Q (W pontos, iniciado em
    zero) por serie; o backbone preve o residuo da janela sem o ciclo e o trecho seguinte do ciclo e somado
    de volta. Precisa saber a serie e a fase (hora do dia ou da semana do 1o ponto da janela).
    Entrou no benchmark em 09/10/2026 (etapa A; ver docs/projeto/ESTUDO_ETAPA_A.md)."""
    usa_fase = True

    def __init__(self, n_series, W, backbone="linear", L=ENTRADA_NN, Hh=H):
        super().__init__()
        self.W, self.L, self.H = W, L, Hh
        self.Q = nn.Parameter(torch.zeros(n_series, W))
        if backbone == "linear":
            self.f = nn.Linear(L, Hh)
        else:
            self.f = nn.Sequential(nn.Linear(L, 512), nn.ReLU(), nn.Linear(512, Hh))

    def ciclo(self, serie, fase, n, desloc=0):
        idx = (fase[:, None] + desloc + torch.arange(n, device=fase.device)[None, :]) % self.W
        return torch.gather(self.Q[serie], 1, idx)

    def forward(self, x, serie, fase):
        return self.f(x - self.ciclo(serie, fase, self.L)) + self.ciclo(serie, fase, self.H, desloc=self.L)


def fase_de(ts, W):
    ts = pd.DatetimeIndex(ts)
    return (ts.hour if W == 24 else ts.dayofweek * 24 + ts.hour).to_numpy()


def treina_proprio(d, caso, fab, ini, fim, epocas=30, perda="l1", semente=42):
    """Treina do zero com os dados anteriores a `ini` e preve os dias de [ini, fim].

    `fab(n_series)` constroi o modelo. Modelos com `usa_fase` recebem (x, serie, fase); os outros so x.
    Devolve (janelas, previsoes, n_parametros).
    """
    fp = nn.functional.l1_loss if perda == "l1" else nn.functional.mse_loss
    ids = {u: i for i, u in enumerate(sorted(d.unique_id.unique()))}
    m = None
    Xs, Ys, Ss, Fs = [], [], [], []
    W = None
    for uid, g in d.groupby("unique_id"):
        y = g.set_index("ds").y
        y = y[y.index < ini]
        tr = y.interpolate(limit_direction="both").to_numpy(np.float32)
        for k in range(ENTRADA_NN, len(tr) - H + 1, 6):                  # janelas a cada 6 h
            Xs.append(tr[k - ENTRADA_NN:k]); Ys.append(tr[k:k + H]); Ss.append(ids[uid]); Fs.append(y.index[k - ENTRADA_NN])
    X, Y = np.stack(Xs), np.stack(Ys)
    mu, sd = X.mean(1, keepdims=True), X.std(1, keepdims=True) + 1e-3
    X, Y = torch.tensor((X - mu) / sd).to(DEV), torch.tensor((Y - mu) / sd).to(DEV)
    torch.manual_seed(semente); rng = np.random.default_rng(semente)
    idx = rng.permutation(len(X)); nval = len(X) // 10
    va, trn = idx[:nval], idx[nval:]
    m = fab(len(ids)).to(DEV)
    fase = getattr(m, "usa_fase", False)
    if fase:
        W = m.W
        S, F = torch.tensor(Ss).to(DEV), torch.tensor(fase_de(Fs, W)).to(DEV)
        chama = lambda i: m(X[i], S[i], F[i])                             # noqa: E731
    else:
        chama = lambda i: m(X[i])                                         # noqa: E731
    opt = torch.optim.Adam(m.parameters(), lr=1e-3); melhor, estado, paciencia = 1e9, None, 0
    for ep in range(epocas):
        m.train()
        for i in range(0, len(trn), 256):
            b = trn[i:i + 256]
            opt.zero_grad(); loss = fp(chama(b), Y[b]); loss.backward(); opt.step()
        m.eval()
        with torch.no_grad():
            v = fp(chama(va), Y[va]).item()
        if v < melhor - 1e-4:
            melhor, estado, paciencia = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        else:
            paciencia += 1
            if paciencia >= 4:
                break
        rng.shuffle(trn)
    m.load_state_dict(estado); m.eval()
    # previsao: janela de 168 h antes de cada dia de teste da dobra
    jan = [w for w in janelas(d, caso, contexto=ENTRADA_NN) if ini <= w["dia"] <= fim]
    Xt = np.stack([w["y"] for w in jan]); mu, sd = Xt.mean(1, keepdims=True), Xt.std(1, keepdims=True) + 1e-3
    xt = torch.tensor((Xt - mu) / sd).to(DEV)
    with torch.no_grad():
        if fase:
            St = torch.tensor([ids[w["unique_id"]] for w in jan]).to(DEV)
            Ft = torch.tensor(fase_de([w["dia"] - pd.Timedelta(hours=ENTRADA_NN) for w in jan], W)).to(DEV)
            p = m(xt, St, Ft).cpu().numpy() * sd + mu
        else:
            p = m(xt).cpu().numpy() * sd + mu
    return jan, list(p), sum(t.numel() for t in m.parameters())
