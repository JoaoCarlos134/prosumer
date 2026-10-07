"""prossumidor: previsao de geracao e consumo de prossumidores de energia.

Estado: esqueleto do passo E1 da proposta (`docs/proposta/PROPOSTA_BIBLIOTECA.md`). Por enquanto
existem `contratos`, `protocolo`, `metricas` e `dados`; os modulos `io`, `qualidade`, `fisica`,
`diagnostico`, `previsao`, `embarcado` e `economia` ainda nao foram escritos.

O protocolo e as metricas foram portados da versao congelada do benchmark v2
(`experimentos/testes_previsao/scripts/comum.py` e `05_avalia.py`), que e o que produziu os
resultados relatados. Os numeros do benchmark ficam nos CSVs daquele diretorio, nao sao recalculados
a partir dos dados de exemplo.
"""

from __future__ import annotations

from . import contratos, dados, metricas, protocolo
from .contratos import ErroDeContrato, SerieEnergia
from .protocolo import AvisoDeSuporte, DiaSeguinte, Dobra, Janela, Regime

try:  # pragma: no cover - depende do pacote estar instalado
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("prossumidor")
except PackageNotFoundError:  # pragma: no cover - arvore de desenvolvimento sem instalacao
    __version__ = "0.0.0.dev0"

__all__ = [
    "AvisoDeSuporte",
    "DiaSeguinte",
    "Dobra",
    "ErroDeContrato",
    "Janela",
    "Regime",
    "SerieEnergia",
    "__version__",
    "contratos",
    "dados",
    "metricas",
    "protocolo",
]
