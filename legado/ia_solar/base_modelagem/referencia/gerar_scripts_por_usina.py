# -*- coding: utf-8 -*-
"""Separa a base por usina e gera um script pronto para cada uma."""
import pandas as pd, io, os
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]            # base_modelagem/
AMBAS = BASE / "ambas_usinas"

b = pd.read_parquet(AMBAS / "base_modelagem_5min.parquet")
h = pd.read_parquet(AMBAS / "base_modelagem_horaria.parquet")
mestre = io.open(AMBAS / "Modelos_Regressao_Geracao.py", encoding="utf-8").read()

CFG = {
    "Cascavel": dict(arq="base_Cascavel_5min.parquet", corte="2025-08-01",
                     titulo="USINA_CASCAVEL - CASCAVEL-PR - 3,96 kWp - inversor Fronius Primo 4.0-1",
                     nota="Potencia e geometria vem da ficha tecnica (12 x 330 Wp, 13 graus, 25 graus a leste\n# do norte) e foram confirmadas pelos dados. Os numeros por kWp sao confiaveis."),
    "Curitiba": dict(arq="base_Curitiba_5min.parquet", corte="2025-08-01",
                     titulo="USINA_CURITIBA - CURITIBA-PR - ~9,6 kWp ESTIMADO - inversor Fronius Symo 12.0-3",
                     nota="ATENCAO: a potencia nominal NAO foi informada. A planilha divide por 12,000 kWp,\n# que e a potencia CA do inversor e nao a do arranjo. A estimativa usada aqui (~9,6 kWp)\n# vem do proprio dado e e um limite inferior. Todo numero por kWp desta usina e PROVISORIO."),
}

for site, c in CFG.items():
    os.chdir(BASE / site.lower())                     # cada usina na sua pasta
    sub = b[b.site == site].copy()
    sub.to_parquet(c["arq"], index=False, compression="zstd")
    hs = h[h.site == site].copy()
    hs.to_csv("base_%s_horaria.csv" % site, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    hs.to_parquet("base_%s_horaria.parquet" % site, index=False, compression="zstd")

    s = mestre
    # cabecalho
    s = s.replace(
        "# Usinas: Usina Cascavel (Cascavel-PR, 3,96 kWp) e Usina Curitiba (Curitiba-PR, ~9,6 kWp)",
        "# Usina:  " + c["titulo"] + "\n#\n# " + c["nota"].replace("\n# ", "\n# "))
    # configuracao
    s = s.replace("caminho_arquivo = r'base_modelagem_5min.parquet'",
                  "caminho_arquivo = r'%s'" % c["arq"])
    s = s.replace("# caminho_arquivo = r'base_modelagem_horaria.csv'",
                  "# caminho_arquivo = r'base_%s_horaria.csv'" % site)
    s = s.replace("USINA          = 'Cascavel'    # 'Cascavel', 'Curitiba' ou 'TODAS'",
                  "USINA          = '%s'    # esta base contem apenas esta usina" % site)
    s = s.replace("DATA_CORTE     = '2025-08-01'", "DATA_CORTE     = '%s'" % c["corte"])
    s = s.replace("PASTA_SAIDA    = 'resultados_regressao'",
                  "PASTA_SAIDA    = 'resultados_%s'" % site)
    nome = "Modelos_Regressao_%s.py" % site
    io.open(nome, "w", encoding="utf-8").write(s)
    print("%-34s  %6d registros  %5.1f MB   -> %s"
          % (nome, len(sub), os.path.getsize(c["arq"])/1e6, c["arq"]))
    print("   %-31s  %6d registros  %5.1f MB"
          % ("base_%s_horaria.csv" % site, len(hs), os.path.getsize("base_%s_horaria.csv" % site)/1e6))
