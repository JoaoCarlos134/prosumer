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

Laco de treino compartilhado com o Crossformer: redes_proprias.treina_multivariado.

Uso: DISPOSITIVO=cuda python piloto_duet.py [dm=512|64] [caso ...]   (ambiente previsao_gpu; padrao casas_cons)
Depois: python piloto_comum.py DUET <caso> A   (ambiente da biblioteca)
"""
import sys
import time
import types
from pathlib import Path

import torch

from comum import H, carrega, dobras
from piloto_comum import grava_piloto
from redes_proprias import DEV, treina_multivariado

REPO = Path.home() / ".cache" / "duet-repo" / "src"
sys.path.insert(0, str(REPO))
for nome in ("ts_benchmark", "ts_benchmark.baselines", "ts_benchmark.baselines.duet"):
    mod = types.ModuleType(nome)
    mod.__path__ = [str(REPO / Path(*nome.split(".")))]
    sys.modules[nome] = mod
from ts_benchmark.baselines.duet.models.duet_model import DUETModel  # noqa: E402

L = 512


def config(n, dm=512):
    return types.SimpleNamespace(
        enc_in=n, seq_len=L, pred_len=H, CI=True, d_model=dm, d_ff=dm, e_layers=2, n_heads=1, factor=3,
        dropout=0.1, fc_dropout=0.0, activation="gelu", output_attention=0, num_experts=4, k=2,
        noisy_gating=True, hidden_size=dm // 2, moving_avg=25)


if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_cons"]
    dm = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("dm=")), "512"))
    nome = "DUET" if dm == 512 else f"DUET-dm{dm}"
    for caso in casos:
        t0 = time.time()
        d = carrega(caso)
        jan, prev = [], []
        for ini, fim in dobras(caso):
            # DUETModel devolve (previsao, perda de balanceamento dos especialistas), somada a MAE como no oficial
            j, p, n_par = treina_multivariado(d, caso, lambda n: DUETModel(config(n, dm)), lambda m, x: m(x),
                                              ini, fim, L=L, lr=5e-4)
            jan += j; prev += p
            torch.cuda.empty_cache()
        f = grava_piloto(nome, caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | {n_par} parametros", flush=True)
