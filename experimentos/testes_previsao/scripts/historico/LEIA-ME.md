# Scripts de uma vez só (histórico)

Filas e testes rápidos que já cumpriram o papel e não devem rodar de novo; ficam aqui como registro de
como cada rodada foi feita (09/10/2026). Não rodam desta pasta (importam `comum` da pasta de cima).

| Script | O que fez |
|---|---|
| `roda_v2.py` | fila das redes da v2 (usinas e casas em dois processos), 05–06/10 |
| `roda_lote2.py` | esperava as linhas `FIM` da v2 e rodava o lote 2 + ensemble + métricas + figuras. **Armadilha:** um runner que espera `FIM` de outro pode esperar para sempre se o outro morrer (13 h paradas em 08/10) |
| `roda_B.py` | retreino das 7 redes do regime B das usinas com a normalização corrigida |
| `roda_restante.py` | o que faltava da v2, como processo independente |
| `teste_correcao_B.py` | teste rápido da correção do regime B (GRU, 150 passos) |

Para refazer o que deriva das previsões, use `../atualiza.py`. Para treinar, chame os scripts numerados
diretamente, um processo por lote (a memória é o gargalo da máquina de casa).
