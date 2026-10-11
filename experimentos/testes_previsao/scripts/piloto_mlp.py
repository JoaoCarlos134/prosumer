# -*- coding: utf-8 -*-
"""F1(e) do plano: o MLP da FV das casas (casas_prod A, skill -0,271 no benchmark) e falta de ajuste ou limite?

O MLP do benchmark (02_referencias.classicos) usa os padroes do sklearn: alpha 1e-4 (regularizacao L2 quase
nula) e parada antecipada sobre 10% de linhas SORTEADAS do treino, que caem nos mesmos dias das linhas de treino
(as 24 horas de um dia sao linhas vizinhas e muito parecidas): a validacao nao ve o sobreajuste. Com 10 casas e
~9 meses de 2020, o MLP decora o treino.

Piloto, com a regra de escolha fixada ANTES de ver o teste (nada de pescar):
- alpha em {1e-4, 1e-3, 1e-2, 1e-1, 1, 10};
- em cada dobra, VALIDACAO TEMPORAL: ajusta em todo o treino menos os ultimos 14 dias, mede o RMSE nesses 14
  dias (todas as horas) e escolhe o alpha de menor RMSE; reajusta com esse alpha em todo o treino e preve a
  dobra. Parada antecipada do sklearn mantida como no benchmark (so ela; a escolha do alpha e temporal);
- mesmos atributos, pipeline (one-hot da serie, imputacao, padronizacao) e arquitetura (64, 32) do benchmark.
Saida: `MLP-ajustado` (semente 42) e `MLP-ajustado-s1`, `-s2` (estabilidade); os alphas escolhidos ficam no
resumo. Portao (plano): ganho >= 0,05 sobre o MLP do benchmark e estavel nas 3 sementes; senao o MLP fica
rotulado "sem ajuste" no texto.

Uso: python piloto_mlp.py [teste] [semente=42] [caso]   (ambiente previsao, CPU; padrao casas_prod)
     `teste`: 1 dobra, 2 alphas
Depois: python piloto_comum.py MLP-ajustado casas_prod A   (ambiente da biblioteca)
"""
import importlib
import json
import sys
import time

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor

from comum import H, carrega, dias_teste, dobras
from piloto_comum import PILOTOS, grava_piloto

R = importlib.import_module("02_referencias")
TESTE = "teste" in sys.argv[1:]
ALPHAS = [1e-4, 1e-2] if TESTE else [1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0]
VALIDACAO_DIAS = 14
COLS = ["h", "dow", "doy_sin", "doy_cos", "serie_cod", "y_d1", "y_d2", "y_d7", "y_media7", "tot_d1", "tot_media7"]


def mlp(alpha, semente):
    # o mesmo pipeline do benchmark (com_serie), so com outro alpha e outra semente
    base = R.classicos()["MLP"]()
    base.set_params(mlpregressor=MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=600, early_stopping=True,
                                              alpha=alpha, random_state=semente))
    return base


if __name__ == "__main__":
    caso = next((a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")), "casas_prod")
    semente = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("semente=")), "42"))
    nome = ("MLP-ajustado" if semente == 42 else f"MLP-ajustado-s{semente}") + ("-teste" if TESTE else "")
    t0 = time.time()
    d = carrega(caso)
    t = R.tabela_features(d, caso)
    teste = pd.DataFrame(dias_teste(d, caso), columns=["unique_id", "dia"])
    tt = teste.merge(t, on=["unique_id", "dia"], how="left").sort_values(["unique_id", "dia", "h"]).reset_index(drop=True)
    tt["prev"] = np.nan
    escolhas = {}
    for ini, fim in dobras(caso)[:1 if TESTE else None]:
        treino = t[(t.dia < ini) & t.y.notna()]
        corte = ini - pd.Timedelta(days=VALIDACAO_DIAS)
        ajuste, valid = treino[treino.dia < corte], treino[treino.dia >= corte]
        rmse = {}
        for a in ALPHAS:
            m = mlp(a, semente).fit(ajuste[COLS], ajuste.y)
            rmse[a] = float(np.sqrt(np.mean((m.predict(valid[COLS]) - valid.y.to_numpy()) ** 2)))
        melhor = min(rmse, key=rmse.get)
        escolhas[str(ini.date())] = dict(alpha=melhor, rmse_validacao={str(k): round(v, 5) for k, v in rmse.items()})
        print(f"  dobra {ini.date()}: alpha {melhor} | " + " ".join(f"{k:g}:{v:.4f}" for k, v in rmse.items()), flush=True)
        m = mlp(melhor, semente).fit(treino[COLS], treino.y)
        sel = (tt.dia >= ini) & (tt.dia <= fim)
        tt.loc[sel, "prev"] = m.predict(tt.loc[sel, COLS])
    tt = tt[tt.prev.notna()]
    dias = tt[["unique_id", "dia"]].drop_duplicates().itertuples(index=False)
    jan = [dict(unique_id=u, ds_fut=pd.date_range(dia, periods=H, freq="h")) for u, dia in dias]
    f = grava_piloto(nome, caso, "A", jan, tt.prev.to_numpy().reshape(-1, H))
    (PILOTOS / f"{nome}__{caso}__A_alphas.json").write_text(json.dumps(escolhas, indent=1))
    print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s", flush=True)
