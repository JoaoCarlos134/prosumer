# Revisão de literatura e levantamento de modelos

| Arquivo | O que é |
|---|---|
| `smart_buildings.docx` | o texto da revisão Edge AI em smart buildings (rascunho) |
| `1Referencias_projetoIA.xlsx` | planilha-mestre das 71 referências da revisão |
| `Visao_geral_modelos_previsao.xlsx` | **visão geral, sem resultados:** 127 entradas bibliográficas, 28 representadas nos testes; 36 modelos, variantes e referências nas métricas v2/lote 2, cobertura por caso/regime, bibliotecas e benchmarks |
| `Modelos_previsao_geracao_consumo.xlsx` | o levantamento original (28/09/2026), preservado como registro histórico; a coluna de resultados e os indicadores de execução estão desatualizados |
| `Referencias_previsao_consumo_embarcado.xlsx` | 15 artigos de previsão de consumo com IA embarcada |
| `rede_keywords_vosviewer.json` | rede de palavras-chave (VOSviewer) |
| `referencias_pdf/`, `prev_consumo_embarcado_refs/` | os PDF dos artigos (fora do git) |
| `scripts/gera_visao_geral_modelos.py` | gera a visão geral usando o levantamento, `metricas.csv` e `tempos_redes*.json` atuais |

Os resultados dos testes estão em [`../../experimentos/testes_previsao/`](../../experimentos/testes_previsao/).
Visão geral regenerada em 06/10/2026. A cobertura vem das linhas presentes em
`resultados/metricas.csv`, incluindo B-curto e C-gfs quando disponíveis; nenhum regime é marcado
apenas por estar planejado. Presença nas métricas não substitui a auditoria das previsões.

Os totais não são equivalentes: as 28 entradas do levantamento correspondem a 29 variantes
avaliadas (Toto 2.0 possui dois tamanhos), mais 7 referências/combinações = 36 linhas na aba Testados.
N-BEATS foi representado por N-BEATSx. O rótulo `Timer-XL-84m` dos resultados carrega
`thuml/timer-base-84m`; portanto, a execução comprova Timer base, sem confirmar Timer-XL.

Para regenerar, a partir da raiz do repositório, use um Python com `pandas` e `openpyxl`:

```powershell
python docs/literatura/scripts/gera_visao_geral_modelos.py
```

O gerador não altera a planilha original e não consulta a internet. Citações, licenças, versões
de bibliotecas e motivos de exclusão preservam o levantamento; não foram revalidados nesta revisão.
O documento `smart_buildings.docx` permanece um rascunho com referências, tabelas e análise dos
autores ainda pendentes. Os PDFs indicados pelas planilhas não acompanham este repositório.
