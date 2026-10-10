# -*- coding: utf-8 -*-
"""Etapa A do plano: DUET (Qiu et al., KDD 2025), treinado nestes dados, regime A, MULTIVARIADO.

DUET = "dual clustering". (1) Agrupamento temporal: uma mistura de especialistas lineares (4 especialistas,
2 ativos por janela, roteador por distribuicao) escolhe o extrator conforme o "jeito" da janela (dia de sol x
dia nublado, semana normal x feriado). (2) Agrupamento de canais: uma mascara aprendida (distancia de
Mahalanobis no dominio da frequencia, amostrada com Gumbel) decide quais series podem olhar para quais, e
um transformer sobre os canais junta as series relacionadas. RevIN por janela. Cada janela entra com TODAS as
series do caso alinhadas no tempo: e o que permite usar a correlacao entre as 20 casas da mesma comunidade.

Interesse: dependencia entre series, que nenhum modelo do benchmark usa de proposito (iTransformer trata
series como variaveis, mas sem agrupamento). Portao: grupo da frente num caso.

Codigo: so o modelo do repositorio oficial (github.com/decisionintelligence/DUET, commit dcc6e67, MIT),
clonado em ~/.cache/duet-repo/src; o arcabouco de benchmark dele (darts, merlion, ray...) NAO e importado:
pacotes vazios no sys.modules e so `models/duet_model.py` e as camadas. Hiperparametros do script oficial
do conjunto Solar (horario): entrada 512 h, d_model 512, d_ff 512, 2 camadas, 4 especialistas com k=2,
fc_dropout 0, dropout 0,1, MAE, Adam 5e-4, lote 32, paciencia 5. Protocolo nosso: origem movel (treino do
zero em cada dobra so com o passado), janelas de treino a cada 6 h, 10% para parada antecipada, ate 30 epocas,
semente 42. A perda de balanceamento dos especialistas e somada a MAE, como no oficial.

Uso: python piloto_duet.py [dm=512|64] [caso ...]   (ambiente previsao_gpu; padrao casas_cons)
Depois: python piloto_comum.py DUET <caso> A   (ambiente da biblioteca)
"""
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from comum import H, carrega, dobras, janelas
from piloto_comum import grava_piloto

REPO = Path.home() / ".cache" / "duet-repo" / "src"
sys.path.insert(0, str(REPO))
for nome in ("ts_benchmark", "ts_benchmark.baselines", "ts_benchmark.baselines.duet"):
    mod = types.ModuleType(nome)
    mod.__path__ = [str(REPO / Path(*nome.split(".")))]
    sys.modules[nome] = mod
from ts_benchmark.baselines.duet.models.duet_model import DUETModel  # noqa: E402

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
L = 512


def config(n, dm=512):
    return types.SimpleNamespace(
        enc_in=n, seq_len=L, pred_len=H, CI=True, d_model=dm, d_ff=dm, e_layers=2, n_heads=1, factor=3,
        dropout=0.1, fc_dropout=0.0, activation="gelu", output_attention=0, num_experts=4, k=2,
        noisy_gating=True, hidden_size=dm // 2, moving_avg=25)


def largo(d):
    """Quadro largo (tempo x series), interpolado por serie; buracos nas pontas viram 0."""
    w = d.pivot(index="ds", columns="unique_id", values="y").sort_index()
    w = w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="h"))
    return w.interpolate(limit_direction="both").fillna(0.0)


def treina(d, caso, ini, fim, dm=512, epocas=30):
    w = largo(d)
    cols = list(w.columns)
    tr = w[w.index < ini].to_numpy(np.float32)
    X = np.stack([tr[k - L:k] for k in range(L, len(tr) - H + 1, 6)])
    Y = np.stack([tr[k:k + H] for k in range(L, len(tr) - H + 1, 6)])
    X, Y = torch.tensor(X), torch.tensor(Y)
    torch.manual_seed(42); rng = np.random.default_rng(42)
    idx = rng.permutation(len(X)); nval = len(X) // 10
    va, trn = idx[:nval], idx[nval:]
    m = DUETModel(config(len(cols), dm)).to(DEV)
    opt = torch.optim.Adam(m.parameters(), lr=5e-4); melhor, estado, paciencia = 1e9, None, 0
    for _ in range(epocas):
        m.train()
        for i in range(0, len(trn), 32):
            b = trn[i:i + 32]
            opt.zero_grad()
            out, aux = m(X[b].to(DEV))
            loss = nn.functional.l1_loss(out, Y[b].to(DEV)) + aux
            loss.backward(); opt.step()
        m.eval()
        with torch.no_grad():
            v = np.mean([nn.functional.l1_loss(m(X[va[i:i + 64]].to(DEV))[0], Y[va[i:i + 64]].to(DEV)).item()
                         for i in range(0, len(va), 64)])
        if v < melhor - 1e-4:
            melhor, estado, paciencia = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        else:
            paciencia += 1
            if paciencia >= 5:
                break
        rng.shuffle(trn)
    m.load_state_dict(estado); m.eval()
    # um dia de teste = uma janela com TODAS as series; guarda so os (serie, dia) que o protocolo avalia
    jan = [j for j in janelas(d, caso, contexto=L) if ini <= j["dia"] <= fim]
    dias = sorted({j["dia"] for j in jan})
    prev = {}
    with torch.no_grad():
        for dia in dias:
            x = torch.tensor(w.loc[:dia - pd.Timedelta(hours=1)].tail(L).to_numpy(np.float32))[None].to(DEV)
            p = m(x)[0][0].cpu().numpy()  # (H, n)
            for c, uid in enumerate(cols):
                prev[(uid, dia)] = p[:, c]
    return jan, [prev[(j["unique_id"], j["dia"])] for j in jan], sum(t.numel() for t in m.parameters())


if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_cons"]
    dm = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("dm=")), "512"))
    nome = "DUET" if dm == 512 else f"DUET-dm{dm}"
    for caso in casos:
        t0 = time.time()
        d = carrega(caso)
        jan, prev = [], []
        for ini, fim in dobras(caso):
            j, p, n_par = treina(d, caso, ini, fim, dm)
            jan += j; prev += p
            torch.cuda.empty_cache()
        f = grava_piloto(nome, caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
