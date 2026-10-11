# -*- coding: utf-8 -*-
"""F1(f) do plano: TimesFM-3 (Google, 2026), zero-shot, regime A, piloto.

O que muda em relacao ao TimesFM-2.5 (ja no benchmark): mesma familia (decodificador so, patches de 32 h na
entrada e 64 h na saida, cabeca de 9 quantis), com destendencia linear opcional do contexto, normalizacao
RevIN refinada de forma iterativa e atencao entre variaveis (covariaveis passadas e futuras entram no proprio
modelo, sem a regressao linear externa do 2.5). Aqui so o regime A (historico), como o plano pede.

Pesos: google/timesfm-3.0-pytorch no HuggingFace (codigo Apache-2.0; os PESOS tem licenca propria, anotada
no plano como nao comercial: uso so de pesquisa, nunca na biblioteca publicada sem conferir). Pacote
`timesfm` 3.0.2, ja no ~/.venvs/previsao_gpu.

Protocolo: o do 03_fundacionais.py (comum.janelas, contexto de CONTEXTO_FM = 1024 h); previsao pontual =
mediana (quantil 0,5), como o TimesFM-2.5. Grava tambem os 9 quantis em `TimesFM-3-quantis__<caso>__A.parquet`
(mesmo formato do piloto do FlowState) para o piloto de faixas F2(c).
Portao: grupo da frente no consumo (casas_cons A); os outros dois casos saem de graca (zero-shot, minutos).

Uso: python piloto_timesfm3.py [teste] [caso ...]   (ambiente previsao_gpu; padrao: os tres)
Depois: python piloto_comum.py TimesFM-3 <caso> A   e   python piloto_quantis.py avalia <caso> TimesFM-3
"""
import sys
import time

import numpy as np
import pandas as pd
from comum import CONTEXTO_FM, DISPOSITIVO, H, carrega, janelas
from piloto_comum import PILOTOS, grava_piloto

DEV = DISPOSITIVO  # padrao cpu, como os fundacionais do 03 (64 janelas em 4 s)
TESTE = "teste" in sys.argv[1:]
LOTE = 64


if __name__ == "__main__":
    from timesfm import TimesFM3Forecaster
    if DEV == "cpu":  # o try_gc do 3.0.2 consulta a GPU mesmo com device="cpu" e quebra com CUDA_VISIBLE_DEVICES=""
        import gc
        import timesfm3.torch.timesfm3_forecaster as _tf
        _tf.try_gc = lambda *a, **k: gc.collect()
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_cons", "casas_prod", "usinas"]
    m = TimesFM3Forecaster.from_pretrained("google/timesfm-3.0-pytorch", device=DEV, per_core_batch_size=LOTE)
    qs = list(m.config.quantiles)
    assert qs == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], qs
    for caso in casos:
        t0 = time.time()
        jan = janelas(carrega(caso), caso, contexto=CONTEXTO_FM)[:LOTE if TESTE else None]
        prev, partes = [], []
        for i in range(0, len(jan), LOTE):
            lote = jan[i:i + LOTE]
            for w, r in zip(lote, m.predict_batch(contexts=[w["y"] for w in lote], horizon=H, return_quantiles=True)):
                q = np.asarray(r.quantiles, float)
                # forma do quantis: conferida no modo teste (horizonte x 9 ou 9 x horizonte, por variavel)
                q = q.reshape(-1, q.shape[-1]) if q.ndim > 2 else q
                q = q if q.shape[-1] == len(qs) else q.T
                q = q[:H]
                assert q.shape == (H, len(qs)), q.shape
                p = np.asarray(r.forecast, float).reshape(-1)[:H]
                if TESTE and i == 0 and w is lote[0]:
                    print(f"  formas: forecast {np.shape(r.forecast)}, quantis {np.shape(r.quantiles)}; "
                          f"max |mediana - q50| = {np.abs(p - q[:, 4]).max():.2e}", flush=True)
                prev.append(p)
                partes += [pd.DataFrame(dict(unique_id=w["unique_id"], ds=w["ds_fut"], q=n, valor=q[:, k]))
                           for k, n in enumerate(qs)]
        nome = "TimesFM-3-teste" if TESTE else "TimesFM-3"
        f = grava_piloto(nome, caso, "A", jan, prev)
        pd.concat(partes, ignore_index=True).to_parquet(PILOTOS / f"{nome}-quantis__{caso}__A.parquet", index=False)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV}", flush=True)
