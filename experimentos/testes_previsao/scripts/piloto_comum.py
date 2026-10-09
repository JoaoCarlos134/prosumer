# -*- coding: utf-8 -*-
"""Avaliacao dos PILOTOS (plano de 09/10/2026): o mesmo criterio do benchmark, sem tocar nele.

Os pilotos gravam em resultados/pilotos/, nunca em resultados/previsoes/: assim nao entram no
07_ensemble.py nem no 05_avalia.py, e nada publicado muda por causa de um teste exploratorio.

Avaliacao = a do benchmark: horas avaliadas e corte de negativos copiados do 05_avalia (via o teste de
regressao, que ja os reproduz), skill contra a mesma referencia, e Diebold-Mariano contra o melhor modelo
do teste. Portao "grupo da frente": p >= 0,05 SEM a correcao de Holm (mais exigente que o benchmark, que
corrige pela familia inteira).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from comum import RES

# A avaliacao usa a biblioteca (ambiente ~/.venvs/prossumidor); a geracao das previsoes roda no ambiente
# do modelo (previsao), que nao tem a biblioteca. Por isso os imports da avaliacao ficam dentro dela.

PILOTOS = RES / "pilotos"
PILOTOS.mkdir(exist_ok=True)


def grava_piloto(nome, caso, regime, janelas_, previsoes):
    linhas = [pd.DataFrame(dict(unique_id=w["unique_id"], ds=w["ds_fut"], yhat=np.asarray(p, float)[:24]))
              for w, p in zip(janelas_, previsoes)]
    df = pd.concat(linhas, ignore_index=True)
    f = PILOTOS / f"{nome}__{caso}__{regime}.parquet"
    df.to_parquet(f, index=False)
    return f


def avalia_piloto(nome, caso, regime="A", extra=None):
    """Skill, metricas e DM contra o melhor do teste; grava o resumo em resultados/pilotos/resumo.json."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
    import test_regressao_benchmark as T
    from prossumidor import metricas as pm

    p = pd.read_parquet(PILOTOS / f"{nome}__{caso}__{regime}.parquet")[["unique_id", "ds", "yhat"]]
    p["yhat"] = p["yhat"].clip(lower=0)
    m, ref = pm.alinha(p, T.real_avaliado(caso), T.referencia(caso))
    met = pm.metricas(m)
    M = T.PUBLICADO[(T.PUBLICADO.caso == caso) & (T.PUBLICADO.regime == regime)].sort_values("skill", ascending=False)
    melhor = M.iloc[0]
    mb, _ = T._alinhado(caso, melhor.modelo, regime)
    _, est, pval = pm.diebold_mariano(pm.erros_quadraticos(m), pm.erros_quadraticos(mb))
    sk = pm.skill(m, ref)
    lo, hi = pm.skill_ic95(m, ref)
    pos = int((M.skill > sk).sum()) + 1
    r = dict(modelo=nome, caso=caso, regime=regime, skill=round(sk, 4), ic95=[round(lo, 4), round(hi, 4)],
             R2=round(met["R2"], 4), nRMSE=round(met["nRMSE"], 4), MBE=round(met["MBE"], 4),
             posicao=f"{pos}o de {len(M) + 1}", melhor=melhor.modelo, skill_melhor=round(float(melhor.skill), 4),
             dm_p_vs_melhor=round(pval, 4), grupo_da_frente=bool(pval >= 0.05 or sk >= melhor.skill), **(extra or {}))
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo[f"{nome}|{caso}|{regime}"] = r
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
    return r


if __name__ == "__main__":
    # Uso (no ambiente da biblioteca): python piloto_comum.py <modelo> <caso> [regime] [chave=valor ...]
    nome, caso = sys.argv[1], sys.argv[2]
    regime = sys.argv[3] if len(sys.argv) > 3 and "=" not in sys.argv[3] else "A"
    extra = dict(a.split("=", 1) for a in sys.argv[3:] if "=" in a)
    print(json.dumps(avalia_piloto(nome, caso, regime, extra), ensure_ascii=False, indent=1))
