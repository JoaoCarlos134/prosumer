# -*- coding: utf-8 -*-
"""V6 (16/11/2026): CRPS e cobertura das faixas de TODO modelo que as entrega, sem e com conformal causal.

Os 17 arquivos `resultados/pilotos/*-quantis__*.parquet` sao as unicas previsoes gravadas com quantis (as 260 de
`resultados/previsoes/` guardam so `yhat`): LightGBM, Chronos-2, TimesFM-3 e FlowState (14 combinacoes, as do piloto
F2(c') `piloto_conformal.py`) mais BuildingsBench S/M/L nas casas (3, novas). Reusa o `avalia` do piloto: mesmas
horas avaliadas, mesma referencia dos 14 dias, mesmos escores (`prosumer.metrics.band_scores`). Nao treina nada.

Saidas (agregados, nada por hora): `resultados/pilotos/faixas_v6.json` e `faixas_v6.csv`. O portao esta em
`docs/projeto/PILOTOS_F1_F2.md` (secao V6), escrito antes da rodada. Uso (ambiente da biblioteca, CPU, minutos):
    python 05c_faixas.py
"""
import json

import pandas as pd

import piloto_conformal as P
from piloto_comum import PILOTOS

NOVAS = [(f"BuildingsBench-{t}", "casas_cons", "A") for t in ("S", "M", "L")]
FORMA = "nivel_28d"   # a forma que esta na biblioteca (`postprocessing.conformal_quantiles`, 28 dias)


if __name__ == "__main__":
    tudo, linhas = {}, []
    for fonte, caso, regime in P.FONTES + NOVAS:
        chave = f"{fonte}|{caso}|{regime}"
        r = P.avalia(fonte, caso, regime)
        tudo[chave] = r
        v = r[FORMA]
        linhas.append({"fonte": fonte, "caso": caso, "regime": regime, "nova": (fonte, caso, regime) in NOVAS,
                       "cob80_bruta": v["bruta"]["cob80"], "cob60_bruta": v["bruta"]["cob60"],
                       "cob80_conformal": v["calibrada"]["cob80"], "cob60_conformal": v["calibrada"]["cob60"],
                       "crps_bruta": v["bruta"]["CRPS"], "crps_conformal": v["calibrada"]["CRPS"],
                       "crps_referencia": v["referencia"]["CRPS"], "skill_bruta": v["skill_bruta"],
                       "skill_conformal": v["skill_calibrada"], "bruta_calibrada": v["bruta_calibrada"],
                       "portao_item": v["portao"], "horas": v["horas"]})
        print(chave, {k: linhas[-1][k] for k in ("cob80_bruta", "cob80_conformal", "skill_bruta", "skill_conformal",
                                                 "portao_item")}, flush=True)
    df = pd.DataFrame(linhas)
    n = len(df)
    veredito = {
        "itens": n, "itens_passam": int(df.portao_item.sum()),
        "bruta_calibrada": int(df.bruta_calibrada.sum()),
        "conformal_calibrada": int(((df.cob80_conformal - 0.8).abs() <= 0.05).mul((df.cob60_conformal - 0.6).abs() <= 0.05).sum()),
        "novas_passam": int(df[df.nova].portao_item.sum()), "novas": int(df.nova.sum()),
        "crps_conformal_pior_1pct_onde_bruta_ok": int(((df.crps_conformal > 1.01 * df.crps_bruta) & df.bruta_calibrada).sum()),
    }
    veredito["passa"] = bool(veredito["itens_passam"] >= 0.8 * n and veredito["conformal_calibrada"] > veredito["bruta_calibrada"])
    (PILOTOS / "faixas_v6.json").write_text(json.dumps({"veredito": veredito, "itens": tudo}, indent=1, ensure_ascii=False), encoding="utf-8")
    df.to_csv(PILOTOS / "faixas_v6.csv", index=False, sep=";", decimal=",")
    print(json.dumps(veredito, indent=1))
