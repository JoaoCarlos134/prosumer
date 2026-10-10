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


# ---------- modelos MULTIVARIADOS (todas as series do caso numa janela): pilotos do DUET e do Crossformer ----------
def largo(d):
    """Quadro largo (tempo x series), SEM preencher: o preenchimento e feito depois de cortar no tempo (causal)."""
    w = d.pivot(index="ds", columns="unique_id", values="y").sort_index()
    return w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="h"))


def _preenche(w):
    """Interpola por serie e zera as pontas, como comum.janelas; chamar so sobre um trecho ja cortado."""
    return w.interpolate(limit_direction="both").fillna(0.0)


def treina_multivariado(d, caso, fab, chama, ini, fim, L, lr, perda="l1", escala=False, lote=32, epocas=30,
                        paciencia_max=5, semente=42):
    """Treina do zero com os dados anteriores a `ini` e preve os dias de [ini, fim], uma janela por dia com
    TODAS as series. `fab(n_series)` constroi o modelo; `chama(m, x)` devolve (previsao, perda_auxiliar).
    `escala`: padroniza cada serie com media e desvio do treino da dobra (para modelos sem RevIN).
    Entradas de teste montadas como em comum.janelas: historico ate a vespera, cortado e so entao interpolado.
    Devolve (janelas, previsoes, n_parametros) so para os (serie, dia) que o protocolo avalia."""
    fp = nn.functional.l1_loss if perda == "l1" else nn.functional.mse_loss
    w = largo(d)
    cols = list(w.columns)
    if escala:
        ant = w[w.index < ini]
        mu, sd = ant.mean(), ant.std() + 1e-3
        w = (w - mu) / sd
    # Interpolacao CAUSAL (corrigido 10/10/2026): antes o quadro inteiro era interpolado de uma vez, e um buraco
    # no fim do historico podia ser preenchido com valores do dia previsto. Agora: corta, depois preenche.
    tr = _preenche(w[w.index < ini]).to_numpy(np.float32)
    X = np.stack([tr[k - L:k] for k in range(L, len(tr) - H + 1, 6)])
    Y = np.stack([tr[k:k + H] for k in range(L, len(tr) - H + 1, 6)])
    X, Y = torch.tensor(X), torch.tensor(Y)
    torch.manual_seed(semente); rng = np.random.default_rng(semente)
    idx = rng.permutation(len(X)); nval = len(X) // 10
    va, trn = idx[:nval], idx[nval:]
    m = fab(len(cols)).to(DEV)
    opt = torch.optim.Adam(m.parameters(), lr=lr); melhor, estado, paciencia = 1e9, None, 0
    for _ in range(epocas):
        m.train()
        for i in range(0, len(trn), lote):
            b = trn[i:i + lote]
            opt.zero_grad()
            out, aux = chama(m, X[b].to(DEV))
            loss = fp(out, Y[b].to(DEV)) + aux
            loss.backward(); opt.step()
        m.eval()
        with torch.no_grad():
            v = np.mean([fp(chama(m, X[va[i:i + 64]].to(DEV))[0], Y[va[i:i + 64]].to(DEV)).item()
                         for i in range(0, len(va), 64)])
        if v < melhor - 1e-4:
            melhor, estado, paciencia = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        else:
            paciencia += 1
            if paciencia >= paciencia_max:
                break
        rng.shuffle(trn)
    m.load_state_dict(estado); m.eval()
    jan = [j for j in janelas(d, caso, contexto=L) if ini <= j["dia"] <= fim]
    prev = {}
    with torch.no_grad():
        for dia in sorted({j["dia"] for j in jan}):
            x = torch.tensor(_preenche(w.loc[:dia - pd.Timedelta(hours=1)].tail(L)).to_numpy(np.float32))[None].to(DEV)
            p = chama(m, x)[0][0].cpu().numpy()  # (H, n)
            for c, uid in enumerate(cols):
                prev[(uid, dia)] = p[:, c] * sd[uid] + mu[uid] if escala else p[:, c]
    return jan, [prev[(j["unique_id"], j["dia"])] for j in jan], sum(t.numel() for t in m.parameters())


def crossformer(n):
    """Crossformer da Time-Series-Library (commit 4e938a1, MIT, em ~/.cache/tslib-repo), hiperparametros do
    script oficial de eletricidade (ECL). Etapa A, 10/10/2026: passou no portao (1o nas usinas, 2o na FV das
    casas, estavel em 3 sementes). O `reformer_pytorch` (so do Reformer) vira um modulo vazio."""
    import sys
    import types
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / ".cache" / "tslib-repo"))
    sys.modules.setdefault("reformer_pytorch", types.SimpleNamespace(LSHSelfAttention=None))
    from models.Crossformer import Model
    return Model(types.SimpleNamespace(
        task_name="long_term_forecast", enc_in=n, seq_len=ENTRADA_NN, pred_len=H, e_layers=2, d_layers=1, factor=3,
        d_model=256, d_ff=512, n_heads=8, dropout=0.1))


def mamba(n):
    """Mamba da Time-Series-Library (models/MambaSimple.py, bloco em PyTorch puro, sem mamba_ssm), hiperparametros
    do script oficial de eletricidade (ECL). Etapa A, 10/10/2026: passou no portao na FV das casas. Como na TSLib, a
    previsao sao as ultimas 24 saidas da varredura causal sobre os 168 h de entrada (limitacao declarada no ESTUDO)."""
    import sys
    import types
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / ".cache" / "tslib-repo"))
    from models.MambaSimple import Model
    return Model(types.SimpleNamespace(
        task_name="long_term_forecast", pred_len=H, enc_in=n, c_out=n, d_model=128, expand=2, d_ff=16, d_conv=4,
        e_layers=2, embed="timeF", freq="h", dropout=0.1))


# receita do Mamba (TSLib ECL: MSE, Adam 1e-4, lote 32, paciencia 3; o modelo normaliza a janela, sem escala)
RECEITA_MAMBA = dict(L=ENTRADA_NN, lr=1e-4, perda="mse", lote=32, paciencia_max=3)


# receita de treino do Crossformer (TSLib ECL: MSE, Adam 1e-4, lote 16, paciencia 3; sem RevIN -> escala do treino)
RECEITA_CROSSFORMER = dict(L=ENTRADA_NN, lr=1e-4, perda="mse", escala=True, lote=16, paciencia_max=3)


def chama_tslib(m, x):
    """Modelos da TSLib recebem (x, marcas, x_dec, marcas_dec); sem perda auxiliar."""
    return m(x, None, None, None), 0.0
