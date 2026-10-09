# -*- coding: utf-8 -*-
"""Piloto F2(c) do plano: previsao em FAIXA (quantis) com o FlowState, regime A.

Pergunta: a biblioteca (e o aplicativo) pode dar uma faixa confiavel, do tipo "amanha entre 8 e 12 kWh"?
O FlowState devolve 9 quantis (10% a 90%) sem treino. Avaliacao (no ambiente da biblioteca, mesmas horas
avaliadas do benchmark):
- calibracao: quantas vezes o real cai dentro da faixa de 80% (q10-q90) e de 60% (q20-q80);
- qualidade: CRPS aproximado = 2 x media da perda quantilica nos 9 quantis;
- referencia probabilistica ingenua e causal: os quantis do MESMO horario nos 14 dias anteriores.
Portao: cobertura dentro de +-5 pontos do nominal e CRPS melhor que a referencia.

Uso:  python piloto_quantis.py gera [caso]      (ambiente previsao; so no Lactec: FlowState)
      python piloto_quantis.py avalia [caso]    (ambiente da biblioteca)
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from comum import CONTEXTO_FM, H, carrega, janelas
from piloto_comum import PILOTOS

QS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def gera(caso):
    import torch
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    from tsfm_public import FlowStateForPrediction
    m = FlowStateForPrediction.from_pretrained("ibm-granite/granite-timeseries-flowstate-r1").eval()
    assert list(m.config.quantiles) == QS, m.config.quantiles
    jan = janelas(carrega(caso), caso, contexto=CONTEXTO_FM)
    t0, partes = time.time(), []
    with torch.no_grad():
        for i in range(0, len(jan), 128):
            lote = jan[i:i + 128]
            x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]
            r = m(past_values=x, scale_factor=1.0, prediction_length=H, batch_first=True)
            # forma medida em 09/10/2026: (lote, quantis, horizonte, 1) com batch_first=True
            q = r.quantile_outputs.detach().numpy()[..., 0]
            assert q.shape == (len(lote), len(QS), H), q.shape
            for w, qq in zip(lote, q):
                for k, nivel in enumerate(QS):
                    partes.append(pd.DataFrame(dict(unique_id=w["unique_id"], ds=w["ds_fut"], q=nivel,
                                                    valor=qq[k, :H].astype(float))))
    df = pd.concat(partes, ignore_index=True)
    f = PILOTOS / f"FlowState-quantis__{caso}__A.parquet"
    df.to_parquet(f, index=False)
    print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s | forma de saida conferida", flush=True)


def perda_quantilica(y, q, nivel):
    e = y - q
    return np.maximum(nivel * e, (nivel - 1) * e)


def avalia(caso):
    import importlib
    av = importlib.import_module("05_avalia")
    base = av.real(caso)
    base = base[base.avalia][["unique_id", "ds", "y"]]
    Q = pd.read_parquet(PILOTOS / f"FlowState-quantis__{caso}__A.parquet")
    Q = Q.pivot_table(index=["unique_id", "ds"], columns="q", values="valor").clip(lower=0)
    # quantis cruzados (q20 < q10) nao sao quantis: ordena por linha, como se faz na pratica
    Q = pd.DataFrame(np.sort(Q.to_numpy(), axis=1), index=Q.index, columns=Q.columns)
    # referencia: quantis do mesmo horario nos 14 dias anteriores (so passado)
    todo = carrega(caso)[["unique_id", "ds", "y"]]
    ref = []
    for uid, g in todo.groupby("unique_id"):
        s = g.set_index("ds").y
        hora = s.groupby(s.index.hour)
        for nivel in QS:
            r = hora.transform(lambda x: x.shift(1).rolling(14, min_periods=7).quantile(nivel))
            ref.append(pd.DataFrame(dict(unique_id=uid, ds=r.index, q=nivel, valor=r.to_numpy())))
    R = pd.concat(ref).pivot_table(index=["unique_id", "ds"], columns="q", values="valor")
    j = base.set_index(["unique_id", "ds"]).join(Q, how="inner").join(R, how="inner", rsuffix="_ref").dropna()
    y = j.y.to_numpy()
    res = {}
    for nome, suf in [("FlowState", ""), ("referencia_14_dias", "_ref")]:
        cols = [f"{n}{suf}" if suf else n for n in QS]
        M = j[cols].to_numpy()
        crps = 2 * np.mean([perda_quantilica(y, M[:, k], n).mean() for k, n in enumerate(QS)])
        res[nome] = dict(cobertura_80=round(float(np.mean((y >= M[:, 0]) & (y <= M[:, 8]))), 3),
                         cobertura_60=round(float(np.mean((y >= M[:, 1]) & (y <= M[:, 7]))), 3),
                         largura_80_media=round(float(np.mean(M[:, 8] - M[:, 0])), 4),
                         CRPS=round(float(crps), 4))
    fs, rf = res["FlowState"], res["referencia_14_dias"]
    res["skill_CRPS"] = round(1 - fs["CRPS"] / rf["CRPS"], 4)
    res["portao"] = bool(abs(fs["cobertura_80"] - 0.8) <= 0.05 and abs(fs["cobertura_60"] - 0.6) <= 0.05
                         and res["skill_CRPS"] > 0)
    res["horas_avaliadas"] = int(len(j))
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo[f"FlowState-quantis|{caso}|A"] = res
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    acao, caso = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "usinas")
    {"gera": gera, "avalia": avalia}[acao](caso)
