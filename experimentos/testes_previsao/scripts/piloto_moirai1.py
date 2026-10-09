# -*- coding: utf-8 -*-
"""Etapa A do plano: Moirai 1.1 (Salesforce), zero-shot, com o clima como covariavel.

Moirai 1 (Woo et al., ICML 2024): transformer so-codificador treinado por mascara no LOTSA (27 bi de
observacoes). "Any-variate attention": alvo e covariaveis viram uma sequencia so de patches, cada
variavel com o seu identificador, e a atencao mistura tempo e variavel sem que o numero de variaveis
seja fixo. Saida: mistura de distribuicoes (t de Student, binomial negativa, log-normal, normal quase
degenerada); a previsao pontual aqui e a mediana de 100 amostras, como no Moirai-MoE.

Por que testar: o Moirai 2 e o Moirai-MoE do benchmark rodaram SO no regime A. O Moirai 1 aceita
covariaveis futuras (`feat_dynamic_real`) sem nenhum treino; se ele usar o clima, e o unico modelo
de clima-sem-treino alem do Chronos-2 e do TimesFM com regressao. Portao: grupo da frente num caso.

Ambiente: ~/.venvs/moirai (uni2ts 2.0, torch 2.4.1 CPU).
Uso: python piloto_moirai1.py [small|base|large] [caso] [regime ...] [patch=16|32|64|auto]
     (padrao: small usinas A B patch=64). O Moirai 1 so aprendeu patch 32 e 64 para dado horario:
     com 16 (o patch do Moirai-MoE no benchmark) a previsao cai a ~zero; com 'auto' o uni2ts quebra
     (128 x 131 no prediction_mask). 64 foi o melhor nos pilotos de 09/10/2026.
Depois: python piloto_comum.py Moirai-1.1-<tamanho>-p<patch> <caso> <regime>   (ambiente da biblioteca)
"""
import sys
import time

import numpy as np
import torch

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from comum import CONTEXTO_FM, EXOG, H, carrega, janelas
from piloto_comum import grava_piloto

torch.manual_seed(42)


def preve(tamanho, jan, exog, patch=64):
    from uni2ts.model.moirai import MoiraiForecast, MoiraiModule
    m = MoiraiForecast(module=MoiraiModule.from_pretrained(f"Salesforce/moirai-1.1-R-{tamanho}"),
                       prediction_length=H, context_length=CONTEXTO_FM, patch_size=patch, num_samples=100,
                       target_dim=1, feat_dynamic_real_dim=len(EXOG) if exog else 0,
                       past_feat_dynamic_real_dim=0).eval()
    n_par = sum(p.numel() for p in m.parameters())
    out = []
    for i in range(0, len(jan), 32):
        lote = jan[i:i + 32]
        x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]  # (B, T, 1)
        kw = dict(past_target=x, past_observed_target=torch.ones_like(x, dtype=torch.bool),
                  past_is_pad=torch.zeros(x.shape[:2], dtype=torch.bool))
        if exog:
            # covariaveis conhecidas no passado E no dia previsto: (B, T + H, n_exog)
            f = np.stack([np.stack([np.concatenate([w["x_pass"][c], w["x_fut"][c]]) for c in EXOG], -1)
                          for w in lote])
            f = torch.tensor(np.nan_to_num(f, nan=0.0))
            kw.update(feat_dynamic_real=f, observed_feat_dynamic_real=torch.ones_like(f))
        with torch.no_grad():
            s = m(**kw)  # (B, amostras, H)
        out += list(np.median(s.numpy(), axis=1).reshape(len(lote), -1)[:, :H])
    return out, n_par


if __name__ == "__main__":
    args = sys.argv[1:]
    tamanho = next((a for a in args if a in ("small", "base", "large")), "small")
    caso = next((a for a in args if a in ("usinas", "casas_prod", "casas_cons")), "usinas")
    regimes = [a for a in args if a in ("A", "B", "C")] or ["A", "B"]
    pa = next((a.split("=")[1] for a in args if a.startswith("patch=")), "64")
    patch = pa if pa == "auto" else int(pa)
    nome = f"Moirai-1.1-{tamanho}-p{pa}"
    for regime in regimes:
        t0 = time.time()
        jan = janelas(carrega(caso, regime), caso, exog=(regime != "A"))
        prev, n_par = preve(tamanho, jan, exog=(regime != "A"), patch=patch)
        f = grava_piloto(nome, caso, regime, jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em cpu | {n_par} parametros", flush=True)
