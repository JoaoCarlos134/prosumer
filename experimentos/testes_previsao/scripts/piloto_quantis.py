# -*- coding: utf-8 -*-
"""Piloto F2(c) do plano: previsao em FAIXA (quantis), 9 quantis de 10% a 90%.

Pergunta: a biblioteca (e o aplicativo) pode dar uma faixa confiavel, do tipo "amanha entre 8 e 12 kWh"?
Fontes (cada uma grava `<fonte>-quantis__<caso>__<regime>.parquet` em resultados/pilotos/):
- FlowState: 9 quantis sem treino, regime A (so no Lactec: granite-tsfm);
- TimesFM-3: 9 quantis sem treino, regime A (gerados pelo piloto_timesfm3.py);
- Chronos-2: quantis sem treino (os 9 de 10% a 90% estao entre os seus 21), regime A e, nas usinas, C (clima
  previsto como covariavel, como no 03_fundacionais);
- LightGBM: um LightGBM com perda quantilica por nivel, mesmos atributos e hiperparametros do LightGBM do
  benchmark, origem movel; regime A e, nas usinas, C.
Avaliacao (mesmas horas avaliadas do benchmark):
- calibracao: quantas vezes o real cai dentro da faixa de 80% (q10-q90) e de 60% (q20-q80);
- qualidade: CRPS aproximado = 2 x media da perda quantilica nos 9 quantis;
- referencia probabilistica ingenua e causal: os quantis do MESMO horario nos 14 dias anteriores.
Quantis cruzados (q20 < q10) sao ordenados por linha antes de avaliar, como se faz na pratica.
Portao: cobertura dentro de +-5 pontos do nominal e CRPS melhor que a referencia.

Uso:  python piloto_quantis.py gera <FlowState|Chronos-2|LightGBM> [caso] [regime] [teste]   (previsao_gpu: o torch do previsao
      esta bloqueado nesta maquina; FlowState so no Lactec, ambiente previsao)
      python piloto_quantis.py avalia <fonte> [caso] [regime]     (qualquer ambiente do benchmark)
      padrao: usinas, regime A; `teste`: 1 dobra (LightGBM) ou 64 janelas (fundacionais), arquivo `-teste`
"""
import importlib
import json
import sys
import time

import numpy as np
import pandas as pd

from comum import CONTEXTO_FM, EXOG, H, carrega, dias_teste, dobras, janelas
from piloto_comum import PILOTOS

QS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
TESTE = "teste" in sys.argv[1:]


def _grava(fonte, caso, regime, jan, quantis):
    """quantis: um array (9, >=24) por janela, na ordem de QS."""
    partes = [pd.DataFrame(dict(unique_id=w["unique_id"], ds=w["ds_fut"], q=n, valor=np.asarray(q[k, :H], float)))
              for w, q in zip(jan, quantis) for k, n in enumerate(QS)]
    f = PILOTOS / f"{fonte}{'-teste' if TESTE else ''}-quantis__{caso}__{regime}.parquet"
    pd.concat(partes, ignore_index=True).to_parquet(f, index=False)
    return f


def gera_flowstate(caso, regime):
    assert regime == "A", "FlowState: so o historico"
    import torch
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    from tsfm_public import FlowStateForPrediction
    m = FlowStateForPrediction.from_pretrained("ibm-granite/granite-timeseries-flowstate-r1").eval()
    assert list(m.config.quantiles) == QS, m.config.quantiles
    jan = janelas(carrega(caso), caso, contexto=CONTEXTO_FM)[:64 if TESTE else None]
    t0, out = time.time(), []
    with torch.no_grad():
        for i in range(0, len(jan), 128):
            lote = jan[i:i + 128]
            x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]
            r = m(past_values=x, scale_factor=1.0, prediction_length=H, batch_first=True)
            # forma medida em 09/10/2026: (lote, quantis, horizonte, 1) com batch_first=True
            q = r.quantile_outputs.detach().numpy()[..., 0]
            assert q.shape == (len(lote), len(QS), H), q.shape
            out += list(q)
    f = _grava("FlowState", caso, regime, jan, out)
    print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s | forma de saida conferida", flush=True)


def gera_chronos2(caso, regime):
    from chronos import BaseChronosPipeline
    p = BaseChronosPipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
    qs = [round(float(x), 4) for x in p.quantiles]
    ik = [qs.index(n) for n in QS]  # falha aqui se algum dos 9 niveis nao estiver entre os do modelo
    jan = janelas(carrega(caso, regime), caso, contexto=CONTEXTO_FM, exog=regime != "A")[:64 if TESTE else None]
    t0, out = time.time(), []
    for i in range(0, len(jan), 64):
        ent = []
        for w in jan[i:i + 64]:
            e = {"target": w["y"]}
            if regime != "A":
                e["past_covariates"] = dict(w["x_pass"]); e["future_covariates"] = dict(w["x_fut"])
            ent.append(e)
        out += [x[0, ik].numpy() for x in p.predict(ent, prediction_length=H)]   # (quantis, H) -> (9, H)
    f = _grava("Chronos-2", caso, regime, jan, out)
    print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s", flush=True)


def gera_lgbm(caso, regime):
    import lightgbm as lgb
    R = importlib.import_module("02_referencias")
    d = carrega(caso, regime)
    t = R.tabela_features(d, caso)
    teste = pd.DataFrame(dias_teste(d, caso), columns=["unique_id", "dia"])
    tt = teste.merge(t, on=["unique_id", "dia"], how="left").sort_values(["unique_id", "dia", "h"]).reset_index(drop=True)
    cols = ["h", "dow", "doy_sin", "doy_cos", "serie_cod", "y_d1", "y_d2", "y_d7", "y_media7", "tot_d1", "tot_media7"]
    cols += ["persist_ceu_claro"] + EXOG if regime != "A" else []
    t0 = time.time()
    Q = np.full((len(tt), len(QS)), np.nan)
    for ini, fim in dobras(caso)[:1 if TESTE else None]:
        treino = t[(t.dia < ini) & t.y.notna()]
        m = ((tt.dia >= ini) & (tt.dia <= fim)).to_numpy()
        for k, n in enumerate(QS):
            mod = lgb.LGBMRegressor(objective="quantile", alpha=n, n_estimators=600, learning_rate=0.03, num_leaves=63,
                                    min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                    random_state=42, verbose=-1)
            mod.fit(treino[cols], treino.y, categorical_feature=["serie_cod"])
            Q[m, k] = mod.predict(tt.loc[m, cols])
    ok = ~np.isnan(Q).any(axis=1)
    tt, Q = tt[ok], Q[ok]
    dias = tt[["unique_id", "dia"]].drop_duplicates().itertuples(index=False)
    jan = [dict(unique_id=u, ds_fut=pd.date_range(dia, periods=H, freq="h")) for u, dia in dias]
    f = _grava("LightGBM", caso, regime, jan, list(Q.reshape(-1, H, len(QS)).transpose(0, 2, 1)))
    print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s", flush=True)


def perda_quantilica(y, q, nivel):
    e = y - q
    return np.maximum(nivel * e, (nivel - 1) * e)


def avalia(fonte, caso, regime):
    av = importlib.import_module("05_avalia")
    base = av.real(caso)
    base = base[base.avalia][["unique_id", "ds", "y"]]
    Q = pd.read_parquet(PILOTOS / f"{fonte}-quantis__{caso}__{regime}.parquet")
    Q = Q.pivot_table(index=["unique_id", "ds"], columns="q", values="valor").clip(lower=0)
    Q = pd.DataFrame(np.sort(Q.to_numpy(), axis=1), index=Q.index, columns=[f"q{n}" for n in QS])
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
    R.columns = [f"q{n}_ref" for n in QS]
    j = base.set_index(["unique_id", "ds"]).join(Q, how="inner").join(R, how="inner").dropna()
    y = j.y.to_numpy()
    res = {}
    for nome, suf in [(fonte, ""), ("referencia_14_dias", "_ref")]:
        cols = [f"q{n}{suf}" for n in QS]
        M = j[cols].to_numpy()
        crps = 2 * np.mean([perda_quantilica(y, M[:, k], n).mean() for k, n in enumerate(QS)])
        res[nome] = dict(cobertura_80=round(float(np.mean((y >= M[:, 0]) & (y <= M[:, 8]))), 3),
                         cobertura_60=round(float(np.mean((y >= M[:, 1]) & (y <= M[:, 7]))), 3),
                         largura_80_media=round(float(np.mean(M[:, 8] - M[:, 0])), 4),
                         CRPS=round(float(crps), 4))
    fs, rf = res[fonte], res["referencia_14_dias"]
    res["skill_CRPS"] = round(1 - fs["CRPS"] / rf["CRPS"], 4)
    res["portao"] = bool(abs(fs["cobertura_80"] - 0.8) <= 0.05 and abs(fs["cobertura_60"] - 0.6) <= 0.05
                         and res["skill_CRPS"] > 0)
    res["horas_avaliadas"] = int(len(j))
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo[f"{fonte}-quantis|{caso}|{regime}"] = res
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "teste"]
    acao, fonte = args[0], args[1]
    caso = next((a for a in args[2:] if a in ("usinas", "casas_prod", "casas_cons")), "usinas")
    regime = next((a for a in args[2:] if a in ("A", "B", "C")), "A")
    if acao == "gera":
        {"FlowState": gera_flowstate, "Chronos-2": gera_chronos2, "LightGBM": gera_lgbm}[fonte](caso, regime)
    else:
        avalia(fonte, caso, regime)
