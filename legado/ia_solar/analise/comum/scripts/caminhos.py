# -*- coding: utf-8 -*-
"""Onde cada arquivo da analise mora.

Os scripts de analise foram escritos para rodar numa pasta plana e usam nomes
curtos ("frame5.parquet", "figs5/22_fault_fingerprint.png"). Depois os arquivos
foram separados em dados/, figuras/ e relatorios/ por usina. caminho() traduz o nome
curto para o caminho real, de modo que qualquer script roda de qualquer pasta:

    import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
    from caminhos import caminho
    f = pd.read_parquet(caminho("frame5.parquet"))
"""
from pathlib import Path

ANALISE = Path(__file__).resolve().parents[2]
IA_SOLAR = ANALISE.parent
BRUTOS = IA_SOLAR / "dados_brutos"
CASCAVEL = ANALISE / "cascavel"
CURITIBA = ANALISE / "curitiba"
COMPARATIVO = ANALISE / "comparativo"
TEMP = ANALISE / "_temp"          # figuras reduzidas para embutir nos HTML; pode apagar

# Nomes curtos antigos que nao batem com o nome do arquivo em disco
_ARQUIVOS = {
    "serie.xlsx":         BRUTOS / "cascavel" / "USINA_CASCAVEL_serie_temporal_2019-2026.xlsx",
    "fatura.xlsx":        BRUTOS / "cascavel" / "Fatura de energia.xlsx",
    "report.html":        CASCAVEL / "relatorios" / "relatorio.html",
    "report5.html":       CASCAVEL / "relatorios" / "relatorio_5min.html",
    "report2sites.html":  COMPARATIVO / "relatorio_dois_sites.html",
    "site_comparison.csv": COMPARATIVO / "site_comparison.csv",
    "R4_sites.png":       COMPARATIVO / "R4_sites.png",
}

# Pastas da pasta plana original
_PASTAS = {
    "minuto":     BRUTOS / "cascavel" / "serie_5min",
    "curitiba":      BRUTOS / "curitiba" / "serie_5min",
    "figs":       CASCAVEL / "figuras",
    "figs5":      CASCAVEL / "figuras",
    "figs_curitiba": CURITIBA / "figuras",
    "figs_opt":   TEMP / "figs_opt",
    "figs5_opt":  TEMP / "figs5_opt",
    "figs2_opt":  TEMP / "figs2_opt",
}


def _dados(nome):
    """Arquivo de dados solto: Curitiba tem prefixo proprio, o resto e Cascavel."""
    if nome.startswith(("curitiba", "nasa_power_curitiba", "colunas_curitiba")):
        return CURITIBA / "dados" / nome
    return CASCAVEL / "dados" / nome


def caminho(nome):
    """Caminho real (str) para um nome curto da pasta plana original."""
    partes = nome.replace("\\", "/").split("/")
    if len(partes) == 1:
        alvo = _ARQUIVOS.get(nome) or _PASTAS.get(nome) or _dados(nome)
    else:
        pasta = _PASTAS[partes[0]]
        alvo = _ARQUIVOS.get(partes[-1], pasta.joinpath(*partes[1:]))
    return str(alvo)
