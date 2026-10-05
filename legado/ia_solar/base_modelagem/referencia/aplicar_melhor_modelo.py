# -*- coding: utf-8 -*-
"""Troca o bloco de modelos dos scripts compartilhados pelo vencedor da comparacao."""
import io, json, re, pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]            # base_modelagem/
AMBAS = BASE / "ambas_usinas"

best = json.load(open(AMBAS / "melhor_modelo.json"))
R = pd.read_csv(AMBAS / "comparacao_modelos_completa.csv", sep=";", decimal=",", encoding="utf-8-sig")
MELHOR = best["melhor"]

# como instanciar cada modelo no script final (padrao da biblioteca, so random_state)
RECEITA = {
 'HistGradientBoosting' : ("from sklearn.ensemble import HistGradientBoostingRegressor",
                           "HistGradientBoostingRegressor(random_state=SEED)"),
 'XGBoost'              : ("from xgboost import XGBRegressor",
                           "XGBRegressor(random_state=SEED, n_jobs=-1)"),
 'Random Forest'        : ("from sklearn.ensemble import RandomForestRegressor",
                           "make_pipeline(SimpleImputer(strategy='median'),\n                             RandomForestRegressor(random_state=SEED, n_jobs=-1))"),
 'Extra Trees'          : ("from sklearn.ensemble import ExtraTreesRegressor",
                           "make_pipeline(SimpleImputer(strategy='median'),\n                             ExtraTreesRegressor(random_state=SEED, n_jobs=-1))"),
 'Gradient Boosting'    : ("from sklearn.ensemble import GradientBoostingRegressor",
                           "make_pipeline(SimpleImputer(strategy='median'),\n                             GradientBoostingRegressor(random_state=SEED))"),
 'Bagging'              : ("from sklearn.ensemble import BaggingRegressor",
                           "make_pipeline(SimpleImputer(strategy='median'),\n                             BaggingRegressor(random_state=SEED, n_jobs=-1))"),
 'Arvore de Decisao'    : ("from sklearn.tree import DecisionTreeRegressor",
                           "make_pipeline(SimpleImputer(strategy='median'),\n                             DecisionTreeRegressor(random_state=SEED))"),
 'Regressao Linear'     : ("from sklearn.linear_model import LinearRegression",
                           "make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),\n                             LinearRegression())"),
}
imp_extra, instancia = RECEITA[MELHOR]

def tabela(usina):
    s = R[R.usina == usina].sort_values("R2", ascending=False)
    out = []
    for _, r in s.iterrows():
        marca = "  <== ESCOLHIDO" if r.modelo == MELHOR else ""
        if pd.isna(r.R2):
            out.append("#   %-22s        falhou%s" % (r.modelo, marca))
        else:
            out.append("#   %-22s R2 %6.4f   MAE %7.1f W   %6.1f s%s"
                       % (r.modelo, r.R2, r.MAE_W, r.tempo_s, marca))
    return "\n".join(out)

BLOCO_TPL = """modelos = {{
    # Unico modelo mantido apos a comparacao das 13 alternativas testadas no
    # Projeto_solo (ver o cabecalho). Parametros padrao da biblioteca; a unica
    # coisa fixada e random_state, para o resultado ser reproduzivel.
    'Media (referencia)'   : DummyRegressor(strategy='mean'),
    '{melhor}' : {inst},
}}
"""

for arquivo, usina in [(BASE / "cascavel" / "Modelos_Regressao_Cascavel.py", "Cascavel"),
                       (BASE / "curitiba" / "Modelos_Regressao_Curitiba.py", "Curitiba"),
                       (AMBAS / "Modelos_Regressao_Geracao.py",  None)]:
    s = io.open(arquivo, encoding="utf-8").read()

    # 1. cabecalho com a tabela da comparacao
    cab = ["#", "# MODELO ESCOLHIDO: %s" % MELHOR, "#",
           "# Comparados 13 algoritmos (a mesma familia testada no Projeto_solo, na versao",
           "# de regressao), todos com parametros padrao e apenas random_state fixado."]
    if usina:
        cab += ["# Resultado no periodo de teste desta usina:", tabela(usina)]
    else:
        cab += ["# Resultado em Cascavel:", tabela("Cascavel"),
                "#", "# Resultado em Curitiba:", tabela("Curitiba")]
    cab += ["#", "# A comparacao completa esta em comparacao_modelos_completa.csv.",
            "# Para repetir: referencia/comparar_modelos.py"]
    s = s.replace("# Requisitos: pandas, numpy, matplotlib, seaborn, scikit-learn, pyarrow",
                  "\n".join(cab) + "\n#\n# Requisitos: pandas, numpy, matplotlib, seaborn, scikit-learn, pyarrow")

    # 2. imports enxutos
    s = s.replace("""from sklearn.linear_model import LinearRegression, Ridge
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import (RandomForestRegressor, ExtraTreesRegressor,
                              GradientBoostingRegressor, HistGradientBoostingRegressor)
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.dummy import DummyRegressor""",
"""%s
from sklearn.dummy import DummyRegressor""" % imp_extra)

    # 3. bloco de modelos
    i0 = s.index("modelos = {")
    i1 = s.index("###############################################################################\n"
                 "###############################################################################\n"
                 "###############################################################################\n"
                 "###############################################################################\n"
                 "# 6. TREINAR E AVALIAR")
    s = s[:i0] + BLOCO_TPL.format(melhor=MELHOR, inst=instancia) + "\n\n" + s[i1:]

    # 4. SEED e fim do RODAR_LENTOS
    s = s.replace("PASTA_SAIDA    = 'resultados", "SEED           = 42            # semente unica, nada de ajuste de hiperparametros\nPASTA_SAIDA    = 'resultados", 1)
    s = re.sub(r"RODAR_LENTOS   = False.*?\n(\s+# \(bem mais lento.*?\n)?", "", s, flags=re.S, count=1)

    io.open(arquivo, "w", encoding="utf-8").write(s)
    import ast; ast.parse(s)
    print("%-32s atualizado (%d linhas) - modelo: %s" % (arquivo.name, len(s.splitlines()), MELHOR))
