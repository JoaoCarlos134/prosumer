# Análise de rede do projeto

O projeto inteiro como um grafo: código, dados, documentos, literatura e
conhecimento (achados, entregas, pendências, resultados). Feita em 30/09–02/10/2026
no mesmo espírito do [Graphify](https://github.com/Graphify-Labs/graphify) — que foi
usado para a camada de código —, com as camadas que um grafo só de código não
enxerga. **Abra `grafo_projeto/graphify-out/graph.html` no navegador** para navegar.

**1.342 nós · 2.570 arestas · 97 comunidades.** 93% das arestas são EXTRAÍDAS dos
arquivos; 7% (176) são INFERIDAS por mim a partir dos documentos e marcadas como tal.

---

## Em sete linhas

1. **O nó mais conectado do projeto é um arquivo que não existe no disco**
   (`frame5.parquet`): 19 scripts dependem de um intermediário que ninguém guarda.
2. **Uma cadeia de 14 passos** vai do download da NASA ao relatório de 5 min; mudar o
   início (o kWp 4,00 → 3,96) afeta **~110 arquivos** à jusante, refeitos à mão.
3. **~40 saídas de análise nunca são lidas por código** — os números chegam aos
   relatórios por transcrição. E **nenhum dos 32 modelos TFLite foi carregado de volta**
   por script algum: o embarcado nunca foi executado a partir do artefato.
4. **O artigo de OCR e a revisão Edge AI são uma linha só** (21 artigos em comum);
   **os artigos A e B de FV não têm nenhuma referência ainda**, e o levantamento de
   modelos não toca nenhuma das outras coleções.
5. **A pendência mais estratégica é a geometria de Curitiba**: bloqueia os dois
   artigos de FV e é a pendência de maior intermediação (0,12), porque liga o projeto
   aos modelos de "usina nova" do levantamento (PARA-PV, histórico sintético físico).
6. **O artigo A tem 5 bloqueios; o B, 2; o de OCR, 1** — e o do OCR é estrutural:
   o código e os dados da validação não estão no projeto (7 scripts e o simulador
   citados nos documentos não existem aqui).
7. **A mesma lógica está espalhada:** data de corte em 16 scripts, métricas em 19,
   agregação horária em 7. É o argumento da `PROPOSTA_BIBLIOTECA.md`.

---

## 1. Como o grafo foi montado

| Camada | Fonte | Nós · arestas | Tipo |
|---|---|---|---|
| Código | Graphify (`--code-only`, AST local): arquivos, funções, chamadas, imports, docstrings | 442 nós | EXTRAÍDA |
| Linhagem de dados | `scripts/01_linhagem.py`: AST de cada leitura/escrita, inclusive `caminho()`, f-strings, `%` e variáveis | 611 arestas | EXTRAÍDA |
| Documentos | `scripts/02_documentos.py`: cada nome de arquivo citado em .md/.tex/.docx/PDF próprio | 20 documentos | EXTRAÍDA |
| Literatura | `scripts/03_literatura.py`: 3 listas de referências + `refs.bib` + levantamento, unificados por DOI/título | 260 artigos | EXTRAÍDA |
| Conceitos | `scripts/04_conceitos.py`: 8 entregas, 8 fontes de dados, 23 achados, 7 pendências, resultados dos testes | 176 arestas | INFERIDA |

`scripts/05_monta_grafo.py` junta tudo no formato do Graphify; `scripts/06_analisa.py`
roda Leiden (o mesmo algoritmo do Graphify), centralidade, pontos de articulação,
linhagem e lacunas. Saídas: `grafo_projeto/graph.json`, `analise.json`,
`grafo_projeto/graphify-out/graph.html` e o relatório genérico do Graphify
(`GRAPH_REPORT.md`). Nenhuma chamada a LLM externo.

## 2. O mapa: as comunidades

| # | Nós | O que é | Nós centrais |
|---|---:|---|---|
| 1 | 213 | **Levantamento de modelos + testes** | planilha de 127 modelos, "Fundacional", os 3 casos de teste |
| 2 | 144 | **Literatura de OCR + revisão Edge AI** (uma comunidade só) | `main.tex`, `smart_buildings.docx`, relatório de campo |
| 3 | 141 | **Testes de previsão** | `comum.py`, `03_fundacionais.py`, `04_redes_treinadas.py` |
| 4 | 104 | **Pipeline de Cascavel** | `make_report.py`, **`frame5.parquet` (não existe)**, `segments.csv` |
| 5 | 85 | **Curitiba + comparativo dos dois sites** | `viz_curitiba.py`, `merge_curitiba.py`, `build_curitiba2.py` |
| 6 | 63 | **Planejamento** | `ESTADO_DO_PROJETO.md`, `PLANO_ARTIGO.md`, Artigo A |
| 7 | 48 | **Dados das 20 casas** | `build_merge.py`, `01_prepara_dados.py`, `data_quality_summary.csv` |
| 8 | 43 | **Estudo do embarcado (TFLite)** | `compara_modelos_embarcado.py` |
| 9 | 40 | **Geradores de documentação + irradiância inversa** | `amplia_documentacao.py`, `divide_documentacao.py` |
| 10 | 33 | **Tarifas ANEEL/Copel** | `aplica_tarifas.py`, `baixa_tarifas_aneel.py` |
| 11 | 24 | **Scripts de regressão para os colegas** | `Modelos_Regressao_*.py` |
| 12 | 21 | **Literatura de Mamba** (do levantamento) | — |

A comunidade 2 é o achado mais claro da estrutura: **o artigo de OCR e a revisão
Edge AI dividem a mesma base bibliográfica** (TinyML, quantização, leitura de
medidores) — 21 dos 73 artigos do OCR estão na revisão. As duas frentes deveriam
ser planejadas juntas. Já a frente solar (comunidades 4, 5, 8, 11) não toca a
literatura em lugar nenhum.

## 3. Nós centrais e pontes

**Mais conectados** (sem contar imports de biblioteca): a planilha do levantamento
(124), **`testes_modelos/scripts/comum.py` (95)**, `main.tex` (81),
`smart_buildings.docx` (73), `ia_solar/LEIA-ME.md` (61), `06_figuras.py` (49),
`build_merge.py` (45), `compara_modelos_embarcado.py` (44). O `comum.py` virou o
segundo nó do projeto em dois dias: ele grava e define todas as previsões dos testes
— é o embrião do protocolo único.

**Pontes** (intermediação — os nós por onde o projeto passa de uma parte a outra):

| Nó | Intermediação | Por quê importa |
|---|---:|---|
| `ia_solar/LEIA-ME.md` | 0,27 | o único documento que liga análise, base de modelagem e entregas |
| `PROPOSTA_BIBLIOTECA.md` | 0,26 | já funciona como o mapa de módulos do projeto |
| Planilha do levantamento | 0,21 | liga literatura, modelos e testes |
| **Pendência: geometria de Curitiba** | **0,12** | a única pendência entre as pontes (ver §6) |
| `testes_modelos/scripts/comum.py` | 0,12 | é, na prática, o protocolo canônico que o PLANO pedia |

**Pontos de articulação** (se sumirem, o grafo se parte): além dos documentos acima,
`frame5.parquet (não existe)`, `make_report.py`, `amplia_documentacao.py`,
`aplica_tarifas.py`. Um intermediário não guardado como ponto de articulação é o
risco de reprodutibilidade número um.

## 4. Linhagem de dados

**A cadeia mais longa** (14 passos):

    fetch_power2.py → nasa_power_true.csv → build2.py → master.csv → changepoint.py →
    segments.csv → build5.py → frame5.parquet (NÃO EXISTE) → ml1_experiment.py →
    ml_results.csv → ml3_viz.py → 28_ml_comparison.png → make_report5.py → relatório

**Maior impacto à jusante** (quantos arquivos dependem do nó): `fetch_power2.py` 111,
série diária de Cascavel 109, `nasa_power_true.csv` 109, `build2.py` 108,
`master.csv` 106, `changepoint.py` 97, `segments.csv` 94. Ou seja: **quase toda a
análise de Cascavel depende da série diária e da NASA diária**, e nenhum mecanismo
avisa quando elas mudam.

**Saídas que nenhum script lê** (no `ia_solar`, sem figuras):
- **27 resultados de análise** (`confounding.csv`, `driver_strength.csv`,
  `ml_cv.json`, `fault_regimes.csv`, `curitiba_segments.csv`…) — os números vão para
  `make_report*.py` digitados no texto. Foi assim que o `relatorio.html` ficou com
  4,00 kWp por meses.
- **Os 32 modelos `.tflite`.** O R² e a latência foram medidos em memória, na criação;
  nenhum script carrega o arquivo salvo. O caminho até o embarcado nunca foi testado
  a partir do artefato que iria para a placa. *Resolvido em 05/10/2026:
  `ia_solar/base_modelagem/referencia/verifica_tflite.py` recarrega os 32 e reproduz o R²
  de todos; o pré-processamento, que não estava salvo, foi para `embarcado/preprocessamento_*.json`.*

**Entradas sem origem em script** (feitas à mão ou externas, todas legítimas):
`parametros_fiscais.csv`, `parametros_usinas.csv`, `explorer_tpl.html`.

**Editados no lugar** (o script lê e reescreve o mesmo arquivo):
`Documentacao_Base_Modelagem.xlsx` ↔ `amplia_documentacao.py`, `merge_5min.py` e
`merge_curitiba.py` (gravam o CSV e releem para o parquet), `gerar_csv_espelho.py`
(grava e confere). Todos legítimos e seguros de repetir (o `amplia_documentacao.py`
apaga cada aba antes de recriá-la).

**Sem uso nenhum:** as 13 exportações avulsas de `dados_brutos/cascavel/exportacoes/`
(nenhum script lê), `catboost_info/` e `curitiba/resultados_Curitiba/` (cópias, já
na lista de limpeza), `dados/merged/all_houses*.{csv,parquet}` (1,7 GB que nenhum
script do projeto lê — os testes usam os `H*_Wh.csv`).

## 5. Documentação

**Citações a arquivos que não existem:**

| Documento | Cita | Situação |
|---|---|---|
| `ESTADO_DO_PROJETO.md`, `PLANO_ARTIGO.md` | `protocolo_canonico.py` | nunca criado; `testes_modelos/scripts/comum.py` cumpre o papel |
| `Relatorio_Validacao_Campo.docx` | `leitor_camera.py`, `leitor_npu.py`, `leitor_npu_digitos.py`, `bench_npu.py`, `bancada2_medir.py`, `npu_viewer.py`, `hidrometro_simulado.html` | código do OCR fora do projeto |
| `main.tex` | `ICIT2027_OCR_EdgeIA.zip`, `hidrometro_simulado.html` | idem |
| `reference_screening.md` | `main_before_solo_style.tex` | versão antiga apagada |

**30 scripts não são citados pelo nome** em documento algum — a maioria porque o
`ia_solar/LEIA-ME.md` descreve por família (`a1..a6`, `dq1..dq4`, `viz_*`). O
`figuras/dq4_viz.py` é uma cópia desatualizada do `scripts/dq4_viz.py` (lê o nome
antigo da pasta plana) e é o único script com nome duplicado.

**Achados sem código no projeto:** os dois do OCR ("93% do PP-OCR não é medição
própria"; "pipeline C validado só no domínio do simulador") — a evidência está nos
documentos, mas o código que a produziria está fora.

## 6. Pendências e entregas

| Entrega | Bloqueada por |
|---|---|
| **Artigo A** (entrada, não algoritmo) | geometria de Curitiba · protocolo congelado · irradiância medida (INMET/satélite) · anonimização · latência medida só em x86 |
| **Artigo B** (diagnóstico com o inversor) | geometria de Curitiba · anonimização |
| **Artigo OCR (ICIT 2027)** | código e dados do OCR fora do projeto |

**A geometria de Curitiba** é a pendência que mais desbloqueia: está nos dois artigos
de FV e o grafo a liga a dois modelos do levantamento feitos para usinas sem
metadados (PARA-PV e "TSFM com histórico sintético físico"). Se a foto do telhado não
vier, transformar o caso em "metadados desconhecidos" usando esses modelos vira
contribuição em vez de pendência.

**Os testes desbloquearam parte do Artigo A:** o protocolo congelado existe agora
(`comum.py` + `05_avalia.py`) e o achado "o clima do dia domina" (+0,50 contra +0,11)
reforça a tese central do artigo com previsão, não só com estimativa.

## 7. Cobertura dos modelos

| Abordagem | No levantamento | Testados |
|---|---:|---:|
| Fundacional (zero-shot) | 33 | 7 |
| MLP / linear | 11 | 5 |
| Recorrente / convolucional | 6 | 4 |
| Transformer | 14 | 3 |
| Kolmogorov-Arnold | 8 | 1 |
| LLM | 11 | 0 |
| Espaço de estados (Mamba) | 10 | 0 |
| Imagem de céu / satélite | 7 | 0 |
| Generativo (difusão) | 5 | 0 |
| Informado por física | 5 | 0 (mas o linear físico e o TimesFM com covariáveis são híbridos físicos) |
| xLSTM | 4 | 0 (representado pelo TiRex) |

Os motivos de cada lacuna estão em `../testes_modelos/LEIA-ME.md` §1.

## 8. O que fazer, em ordem

1. **Guardar `frame5.parquet` e `frame5h.parquet`** (ou declarar o pipeline num
   Snakefile/DVC que os refaça sozinho). Tira o maior ponto de articulação do grafo.
2. **Trazer o código do OCR para o projeto** (`ocr_paper/codigo/`): sem isso o artigo
   não é reprodutível e 9 citações continuam apontando para o nada.
3. **Ler os resultados no relatório, em vez de digitá-los**: `make_report*.py` deveria
   abrir os CSV/JSON de `dados/`. Fecha as ~27 saídas órfãs.
4. **Executar um `.tflite` salvo** num Raspberry Pi ou ESP32: fecha a pendência de
   latência em x86 e testa o artefato de verdade (junto com TTM e SparseTSF, os
   candidatos dos testes).
5. **Resolver ou reenquadrar a geometria de Curitiba** (§6).
6. **Montar a bibliografia dos artigos A e B** a partir do levantamento
   (`Modelos_previsao_geracao_consumo.xlsx`, coluna "Testado"): hoje é zero.
7. **Fundir o planejamento de OCR e da revisão Edge AI**: mesma literatura.
8. **Limpeza já listada:** `figuras/dq4_viz.py`, `catboost_info/`,
   `resultados_Curitiba/`, exportações duplicadas, e decidir o destino de
   `dados/merged/` (1,7 GB sem uso). *Feita em 05/10/2026: as cópias e sobras foram
   para `_arquivo/`; `dados/` virou `dados_casas/`; de `merged/` ficou só um parquet de 144 MB (as outras três eram
   cópias da mesma tabela).*

Melhorias nos modelos: `../testes_modelos/LEIA-ME.md` §5. Biblioteca:
`PROPOSTA_BIBLIOTECA.md`.

## 9. Limites desta análise

- **Linhagem estática:** nomes montados a partir de dicionários (como os
  `base_<Usina>_5min.parquet` do `gerar_scripts_por_usina.py`) e leituras por curinga
  puro (`*.parquet`) não viram aresta. Os casos conhecidos estão citados acima.
- **A camada de conceitos é curada** (176 arestas INFERIDAS); o resto é extraído.
- **Documentos citam por nome exato**; descrição por família não conta como citação.
- **PDFs de terceiros não foram lidos** (só as listas de referências): nenhum conteúdo
  foi enviado a serviço externo.

Para refazer: `scripts/01` a `06` em ordem (01 e 06 no ambiente `.venvs/previsao`),
depois `graphify cluster-only grafo_projeto --graph grafo_projeto/graph.json --no-label`.
