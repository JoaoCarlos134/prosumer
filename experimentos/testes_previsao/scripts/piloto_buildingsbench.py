# -*- coding: utf-8 -*-
"""F1(f) do plano: BuildingsBench (Emami et al., NeurIPS 2023 Datasets and Benchmarks; NREL), zero-shot, so CONSUMO.

O que e: Transformers codificador-decodificador pre-treinados em Buildings-900K, ~900 mil predios SIMULADOS dos EUA
(ResStock/ComStock, EnergyPlus), so para carga de predio. Entrada: 168 h de carga + calendario (dia do ano, da
semana, hora), tipo de predio (residencial/comercial) e latitude/longitude normalizadas pelos dados de treino; saida:
24 h, decodificadas uma a uma (autorregressivo). A carga entra transformada por Box-Cox (ajustada no Buildings-900K,
um arquivo do conjunto) e a cabeca devolve media e desvio de uma gaussiana nesse espaco. E o unico fundacional do
levantamento feito so para consumo de predios: e isso que poderia acrescentar.

Configuracao, fixada antes de ver o teste:
- casas como RESIDENCIAIS; coordenadas pela regra dos proprios autores para casas fora dos EUA: o benchmark deles poe
  Londres (LCL), Edimburgo (IDEAL) e Sceaux na posicao de Mt. Baker, WA (48,825362, -121,717270), dentro da faixa
  de treino (metadata/benchmark.toml do conjunto). A Irlanda segue a mesma regra;
- ano de 2020 = bissexto (normalizacao do dia do ano, como no benchmark.toml);
- previsao pontual = media gaussiana decodificada de forma gulosa (o `predict` do pacote), desfeita a Box-Cox;
- quantis (para o F2c): media + z x desvio no espaco Box-Cox, desfeitos pela Box-Cox (monotona, entao os quantis
  sao preservados), z dos niveis 10%-90%;
- tamanhos S (~3 M), M e L (~160 M): a DECISAO e pelo L (o principal do artigo); S e M so informam tamanho.
Protocolo: comum.janelas com contexto de 168 h (o que o modelo aceita), CPU como os fundacionais do 03.
Portao (plano): grupo da frente no consumo.

Instalacao (11/10/2026): `buildings_bench==2.0.0` e `tomli` com --no-deps no ~/.venvs/previsao_gpu (o resolvedor
puxaria torch 2.4.1 e transformers 4.34). Metadados (withheld_pumas.tsv, 4 mapas de PUMA para a normalizacao de
lat/lon, transforms/boxcox.pkl) e pesos (v1.1.0, Transformer_Gaussian_{S,M,L}.pt) em ~/.cache/buildingsbench, do
OEDI (oedi-data-lake.s3.amazonaws.com/buildings-bench/). Licenca do codigo e dos pesos: BSD-3.

Uso: python piloto_buildingsbench.py [S|M|L ...] [teste]   (ambiente previsao_gpu; padrao os tres)
Depois: python piloto_comum.py BuildingsBench-L casas_cons A   e   python piloto_quantis.py avalia BuildingsBench-L casas_cons
"""
import importlib.resources
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.stats import norm

from comum import DISPOSITIVO, H, carrega, janelas
from piloto_comum import PILOTOS, grava_piloto

BB = Path.home() / ".cache" / "buildingsbench"
os.environ.setdefault("BUILDINGS_BENCH", str(BB))
LATLON = np.array([48.825362, -121.717270])   # regra dos autores para casas fora dos EUA (Mt. Baker, WA)
CONTEXTO = 168
QS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
TESTE = "teste" in sys.argv[1:]
LOTE = 128


def modelo(tamanho):
    import tomli
    from buildings_bench.models import model_factory
    cfg = tomli.loads((importlib.resources.files("buildings_bench") / "configs" /
                       f"TransformerWithGaussian-{tamanho}.toml").read_text())
    m, _, _ = model_factory(f"TransformerWithGaussian-{tamanho}", cfg["model"])
    ck = torch.load(BB / "checkpoints" / f"Transformer_Gaussian_{tamanho}.pt", map_location="cpu", weights_only=True)
    m.load_state_dict({k.replace("module.", ""): v for k, v in ck["model"].items()})
    return m.to(DISPOSITIVO).eval(), sum(p.numel() for p in m.parameters())


def entradas(lote, box, latlon, tempo):
    from buildings_bench import BuildingTypes
    n, L = len(lote), CONTEXTO + H
    carga = np.zeros((n, L, 1), np.float32)
    carga[:, :CONTEXTO, 0] = box.transform(np.stack([np.clip(w["y"], 0, None) for w in lote])[..., None])[..., 0]
    ds = [pd.date_range(w["ds_fut"][0] - pd.Timedelta(hours=CONTEXTO), periods=L, freq="h") for w in lote]
    tf = np.stack([tempo.transform(x) for x in ds])          # (n, L, 3): dia do ano, dia da semana, hora
    t = lambda a: torch.tensor(a, dtype=torch.float32, device=DISPOSITIVO)
    return {"load": t(carga), "latitude": t(np.full((n, L, 1), latlon[0])), "longitude": t(np.full((n, L, 1), latlon[1])),
            "day_of_year": t(tf[..., 0:1]), "day_of_week": t(tf[..., 1:2]), "hour_of_day": t(tf[..., 2:3]),
            "building_type": torch.full((n, L, 1), BuildingTypes.RESIDENTIAL_INT, dtype=torch.long, device=DISPOSITIVO)}


if __name__ == "__main__":
    from buildings_bench import transforms as T
    tamanhos = [a for a in sys.argv[1:] if a in ("S", "M", "L")] or ["S", "M", "L"]
    box = T.BoxCoxTransform(); box.load(BB / "metadata" / "transforms")
    latlon = T.LatLonTransform().transform_latlon(LATLON).astype(np.float32)
    tempo = T.TimestampTransform(is_leap_year=True)
    caso = "casas_cons"
    jan = janelas(carrega(caso), caso, contexto=CONTEXTO)[:LOTE if TESTE else None]
    assert all(len(w["y"]) == CONTEXTO for w in jan)
    z = norm.ppf(QS)
    for tam in tamanhos:
        t0 = time.time()
        m, n_par = modelo(tam)
        prev, partes = [], []
        with torch.no_grad():
            for i in range(0, len(jan), LOTE):
                lote = jan[i:i + LOTE]
                # espaco Box-Cox; o 2o retorno e (n, 24, 2) = [media, desvio], com o softplus ja aplicado pelo pacote
                media, gauss = m.predict(entradas(lote, box, latlon, tempo))
                mu = media[..., 0].cpu().numpy()                                  # (n, 24)
                sd = gauss[..., 1].cpu().numpy()
                p = box.undo_transform(mu[..., None])[..., 0]
                q = np.stack([box.undo_transform((mu + zk * sd)[..., None])[..., 0] for zk in z], 1)  # (n, 9, 24)
                for w, pp, qq in zip(lote, p, q):
                    prev.append(pp)
                    partes += [pd.DataFrame(dict(unique_id=w["unique_id"], ds=w["ds_fut"], q=nv, valor=qq[k]))
                               for k, nv in enumerate(QS)]
        nome = f"BuildingsBench-{tam}" + ("-teste" if TESTE else "")
        f = grava_piloto(nome, caso, "A", jan, prev)
        pd.concat(partes, ignore_index=True).to_parquet(PILOTOS / f"{nome}-quantis__{caso}__A.parquet", index=False)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DISPOSITIVO} | {n_par} parametros | "
              f"media prevista {np.mean(prev):.3f} x real do contexto {np.mean([w['y'][-H:].mean() for w in jan]):.3f} kWh/h",
              flush=True)
