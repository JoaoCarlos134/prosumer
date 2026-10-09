# Proposta: biblioteca `prossumidor`

> **Estado em 06/10/2026.** Este estudo de viabilidade descreve uma arquitetura proposta;
> o pacote instalável existe (etapa E1, 06/10/2026), com `contratos`, `protocolo`, `metricas` e `dados`; os outros módulos ainda não foram escritos. O uso acadêmico para o TCC
> foi liberado em 05/10/2026; a licença é decisão do autor (a Lactec só entra se o projeto for ligado
> formalmente a ela) e os dados das usinas dependem da permissão do professor. Público decidido em
> 09/10/2026: núcleo internacional (inglês) com camada brasileira; ver `CLAUDE.md`. O benchmark v2 deve ser concluído e validado antes de atualizar as decisões
> baseadas nos testes v1 abaixo. Consulte [`CLAUDE.md`](../../CLAUDE.md) e a
> [estado atual](../../CLAUDE.md).

Uma biblioteca Python para prever **geração e consumo** de quem produz e consome
energia — usina FV, casa com FV e bateria, edificação — do dado bruto do medidor
ao modelo embarcado. Estudo de viabilidade feito em 30/09/2026 a partir da análise
de rede do projeto ([`REDE_PROJETO.md`](../projeto/REDE_PROJETO.md)) e dos testes de modelos
([`LEIA-ME.md`](../../experimentos/testes_previsao/LEIA-ME.md)). A disponibilidade do nome no PyPI
foi conferida durante o estudo; não representa reserva do nome.

**Recomendação em uma frase:** sim, vale fazer — mas como uma **camada de domínio
fina sobre bibliotecas que já existem**, não como uma biblioteca que "resolve tudo"
do zero. O que é único deste projeto (diagnóstico só com o inversor, protocolo de
previsão congelado com modelos fundacionais, contexto tarifário brasileiro,
exportação para embarcado) cabe em ~6 módulos; o resto é adaptador.

---

## 1. Por que agora: o que a análise de rede mostrou

| Sintoma no projeto | Número | Consequência |
|---|---:|---|
| Data de corte `2025-08-01` escrita à mão | 16 scripts | mudar o teste = editar 16 arquivos |
| Métricas (R², MAE…) reimplementadas | 19 scripts | definições divergem entre relatórios |
| Agregação horária reescrita | 7 scripts | cada uma com sua regra de buraco/noite |
| Semente fixada separadamente | 12 scripts | reprodutibilidade depende de disciplina |
| Correção do proxy (`truststore`) repetida | 5 scripts | — |
| Nó mais conectado do projeto | `frame5.parquet`, que **não existe no disco** | 19 scripts dependem de um intermediário não guardado |
| Cadeia mais longa da linhagem | 14 passos, da NASA ao relatório de 5 min | uma mudança no início (kWp 4,00 → 3,96) propaga para ~110 arquivos à mão |
| Saídas que nenhum script lê | ~30 arquivos | números chegam aos relatórios por transcrição manual |

O `relatorio.html` desatualizado e a fatura de 2025 que não entrou na análise
(ambos corrigidos em 28/09) foram exatamente esse tipo de falha. Uma biblioteca
com protocolo único e um pipeline declarado resolve a classe inteira de problemas,
não um caso.

Os próprios testes deram a segunda evidência: em um dia, três quebras de
ambiente — `uni2ts` rebaixando o torch, o `huggingface_hub` novo quebrando o
Toto, o `granite-tsfm` do GitHub trocando o `transformers`. Modelos fundacionais
mudam de API a cada trimestre; o código de projeto não deve falar com eles direto.

## 2. O que NÃO fazer de novo (o ecossistema já resolve)

| Necessidade | Já existe | Como a `prossumidor` usa |
|---|---|---|
| Geometria solar, céu claro, transposição, temperatura de célula | **pvlib** | dependência direta |
| Clima: NASA POWER, **CAMS (satélite)**, ERA5, PVGIS, Solcast | **pvlib.iotools** | adaptador + o alinhamento de −55 min da NASA como função testada |
| Redes treinadas (LSTM, GRU, NHITS, TiDE, PatchTST, TFT…) | **NeuralForecast** / Darts | adaptador opcional |
| Modelos fundacionais | chronos-forecasting, timesfm, tirex, granite-tsfm, uni2ts, toto | um adaptador por modelo, cada um como *extra* isolado |
| Estatísticos e árvores | StatsForecast, LightGBM | adaptador |
| Pipeline de carga em produção | **OpenSTEF 4.0** | não competir: exportar para ele |
| Degradação e sujeira (SRR) | **RdTools** | comparar com o diagnóstico próprio, não substituir |
| Execução em microcontrolador | LiteRT (TFLite), emlearn | etapa de exportação |

## 3. O que é único (a lacuna que justifica a biblioteca)

Nenhuma biblioteca acima faz:

1. **Diagnóstico só com o inversor**, sem sensor de irradiância: separação
   corrente × tensão CC para sujeira, duas entradas MPPT como controle uma da outra
   para falha de string, detecção de limpezas por ponto de mudança
   (`a2_fault.py`, `a3_shading.py`, `changepoint.py`, `curitiba_analysis2.py`).
2. **Um protocolo de previsão congelado** que compara referências, árvores, redes e
   modelos fundacionais na mesma tarefa, com regimes explícitos (só histórico ×
   clima conhecido), IC por bootstrap de dias e *skill* contra a persistência de
   céu claro (`testes_modelos/scripts/comum.py`, `05_avalia.py`).
3. **Leitura dos formatos reais** que o projeto recebe: exportação anual do
   Fronius Solar.web, medidor de 1 min das casas (com detecção de casa sem FV,
   minuto corrompido e mudança de horário de verão), fatura Copel.
4. **Contexto tarifário brasileiro**: TUSD/TE da ANEEL, bandeiras, ICMS do PR por
   período, Lei 14.300 e créditos que expiram (`tarifas/`, `billing.py`).
5. **Caminho até o embarcado** medido por igual para todas as famílias
   (tamanho, R², latência — hoje só TFLite em `compara_modelos_embarcado.py`).
6. **Regras de qualidade que custaram horas** e não estão em documentação nenhuma:
   colunas que reescrevem o alvo, hora de ponta com inversor dormindo, eficiência
   do inversor > 1 por falta de simultaneidade, NASA diária 3,2% abaixo.

## 4. Módulos e de onde vem o código

| Módulo | Faz | Código que já existe no projeto |
|---|---|---|
| `prossumidor.io` | lê Fronius, medidores, faturas, ANEEL; clima via pvlib com alinhamento | `merge_5min.py`, `merge_curitiba.py`, `build_merge.py`, `billing.py`, `baixa_tarifas_aneel.py`, `h1_align.py` |
| `prossumidor.qualidade` | buracos, noite, pontas do dia, vazamento, casas sem FV, horário de verão, relatório de qualidade | `01_prepara_dados.py`, `dq1..dq3`, `dq_curitiba.py`, `data_quality_summary.csv` |
| `prossumidor.fisica` | POA de céu claro, ajuste de geometria, kWp estimado, irradiância inversa | `solar.py`, `a1_geometry.py`, `build_curitiba2.py`, `estima_irradiancia.py` |
| `prossumidor.diagnostico` | sujeira, falha de string, limpezas, PR corrigido | `a2_fault.py`, `a3_shading.py`, `changepoint.py`, `curitiba_analysis2.py` |
| `prossumidor.previsao` | interface única `ajusta/preve` + adaptadores | `02_referencias.py`, `03_fundacionais.py`, `04_redes_treinadas.py` |
| `prossumidor.protocolo` | janelas do dia seguinte, regimes, métricas, bootstrap, Diebold–Mariano, relatório | `comum.py`, `05_avalia.py` |
| `prossumidor.embarcado` | exporta (TFLite int8, ONNX, emlearn) e mede | `compara_modelos_embarcado.py` |
| `prossumidor.economia` | tarifa cheia, créditos, Lei 14.300, exportação HOMER | `aplica_tarifas.py`, `monta_planilha_tarifas.py` |

## 5. Como seria usar

```python
import prossumidor as ps

usina = ps.io.fronius("dados_brutos/cascavel/serie_5min/", kwp=3.96, lat=-24.83, lon=-53.65,
                      inclinacao=13, azimute=155)
clima = ps.io.clima(usina, fonte="cams")              # ou "nasa" (já alinhada em -55 min), "era5"
serie = ps.qualidade.limpa(usina, clima)              # noite, pontas do dia, vazamento — com relatório
print(serie.relatorio_qualidade())

tarefa = ps.protocolo.DiaSeguinte(serie, teste_de="2025-08-01", regimes=["historico", "clima"])
resultado = tarefa.compara([
    ps.previsao.PersistenciaCeuClaro(),
    ps.previsao.LinearFisico(),
    ps.previsao.LightGBM(),
    ps.previsao.fundacional("chronos-2"),             # extra: pip install prossumidor[chronos]
    ps.previsao.fundacional("ttm"),                   # 3M parâmetros, o mais consistente nos testes
])                                                    # + mediana de todos, sempre incluída
resultado.tabela()                                    # skill com IC95%, nMAE, viés, R², energia diária
ps.embarcado.exporta(resultado.melhor(max_kb=64), formato="tflite-int8")

diag = ps.diagnostico.sujeira(serie)                  # eventos de limpeza, perda acumulada
ps.economia.fatura(serie, consumo, distribuidora="copel", conexao="2019-07")
```

## 5b. O que os testes decidiram para a biblioteca

Os testes v1 de [`experimentos/testes_previsao/`](../../experimentos/testes_previsao/)
(33 modelos, 3 casos) viram escolhas concretas:

| Decisão | Por quê (resultado do teste) |
|---|---|
| **Conjunto padrão de `compara()`:** persistência de céu claro, linear físico, LightGBM, TTM, Chronos-2 | cobre o teto (LightGBM/TFT ≈ +0,48–0,50 com clima), o melhor zero-shot consistente (TTM, ranking médio 3,3) e o híbrido físico (+0,42 com uma variável) — em segundos, sem GPU |
| **Saída padrão = mediana dos modelos**, não "o melhor" | no v1, 1º nas usinas, 2º na geração FV das casas e **5º no consumo**, a 0,012 do primeiro; escolher o vencedor pelo teste é vazamento. O viés no consumo precisa ser reportado e tratado |
| **Normalização global obrigatória com covariáveis** | a normalização por janela do NeuralForecast fez GRU/LSTM/NHITS/KAN preverem até 2.400 kWh/h numa usina de 4 kW; a biblioteca deve impedir essa combinação, não documentá-la |
| **Relatório de viés junto do erro** | os fundacionais subestimam o consumo em ~20% (preveem a mediana); um bom RMSE escondia isso |
| **Detecção de série sem sinal** em `qualidade` | 10 das 20 casas não têm FV; sem a checagem, o erro normalizado dobrou |
| **`embarcado` começa por TTM (3 M) e SparseTSF (32 parâmetros)** | SparseTSF empata com os melhores no consumo; TTM é o mais estável sem treino |
| **Regime explícito (histórico × clima conhecido)** | o vão entre regimes (~0,40) é dez vezes a diferença entre algoritmos; misturar os dois numa tabela engana |
| **Cada fundacional num ambiente isolado** | `uni2ts` exige torch 2.4; `granite-tsfm` do GitHub trouxe torch 2.11 e transformers 5; o Toto quebrou com o `huggingface_hub` novo |

## 5c. O que a v2 e a revisão de 07/10/2026 mudaram

A v2 (origem móvel, 36 modelos, lote 2) e a revisão do repositório em 07/10/2026 confirmam a maior
parte da 5b e mudam o resto. Cada linha diz o que fazer na biblioteca e de onde veio.

| Decisão | Por quê |
|---|---|
| **Prioridade: `io.clima` antes de mais adaptadores de modelo** | o clima pesa ~10× mais que o modelo: nas usinas, o ganho mediano com o clima (A→B) é +0,489 de skill, e o 1º e o 5º modelo em A diferem 0,046 (`Comparacao_modelos_regimes_A_B.xlsx`). Fontes a cobrir: NASA (já usada), **estação local medida** (as casas de Dingle têm uma, a cada minuto), previsão ECMWF IFS (regime C) e ECMWF AIFS (IA). `io.clima` deve dizer se o arquivo de previsões cobre as datas pedidas: o da Open-Meteo só começa em 06/03/2024 |
| **Conjunto padrão de `compara()` atualizado**: persistência de céu claro, linear físico, LightGBM, **Toto-2.0-313m**, **TiRex-2**, TTM, + mediana | na v2 o Toto-2.0-313m tem o melhor ranking médio no regime A (3,0) e o TiRex-2 é o melhor modelo individual nas usinas nos três regimes; o TTM continua o candidato do embarcado (3 M parâmetros, segundos em CPU). Chronos-2 sai do padrão |
| **Saída padrão = mediana** (reforçado) | empata com o melhor nos **6 de 6** testes A e B (Diebold–Mariano com Holm), com 51 modelos (09/10/2026); é 1ª nas usinas em C e 2ª em B, a 0,001 do TiRex-2 |
| **Fuso: dizer em que fuso o arquivo está e o que fazer com o horário de verão** (feito em 07/10: `fuso_origem` e `troca_de_horario` em `SerieEnergia.de_dataframe`; hora repetida resolvida pela ordem, série a série; o resto vira `ErroDeContrato` com as duas sugestões) | as casas de Dingle estão em **hora local de Dublin numa grade sem buraco** (o horário da geração FV salta ~1 h em 29/03 nas 10 casas), com as linhas de 29/03 01:00 e 25/10 01:00 preenchidas; declarar o fuso real quebrava o contrato com um `ValueError` cru do pandas. No Brasil não aparece (sem horário de verão desde 2019); na Europa e nos EUA, sempre. Lição: **nunca supor o fuso de um arquivo — medir** (contra o sol, como aqui) |
| **Proveniência no contrato**: fonte, licença e local em toda série | as casas foram tratadas como "origem desconhecida, não publicar" até 07/10; são o conjunto **CC0** de Khadem et al. (2024), *Scientific Data*, doi:10.1038/s41597-024-03454-2. O que pode ser publicado depende disso |
| **Dados reais de exemplo**: `dados.casas_dingle()` baixa do figshare, com a citação | CC0 permite. Não embutir no pacote (dezenas de MB); baixar e guardar em cache. Os sintéticos continuam para os testes |
| **Cada adaptador declara o que exige e o que pode fazer**: `requer_gpu` (não / recomendada / sim), licença dos pesos, se envia dados para fora | GPU: TabPFN-TS, Time-LLM, Mamba e LLMTime são inviáveis sem GPU; o TiRex-2 precisa da GPU **escondida** (`CUDA_VISIBLE_DEVICES=-1`). Licença: TimesFM-3 só para pesquisa. Dados: o TimeGPT roda nos servidores da Nixtla — a biblioteca deve **recusar** série privada nesses adaptadores sem permissão explícita (as usinas nunca podem ir) |
| **`ranking()` e `empata_com_melhor()` no `protocolo`** | posição de 0 (1º) a 1 (último) em cada caso e regime, média nos testes em que o modelo rodou, sempre informando quantos foram; empate = Diebold–Mariano com Holm, p ≥ 0,05. Posições próximas quase nunca são diferenças reais (na FV das casas, 21 de 32 empatam com o melhor) |
| **Gerador aleatório por chamada no IC** | o `05_avalia.py` usa um gerador único para todos os modelos: o IC de cada um depende da ordem dos arquivos (diferença de ~0,005). A biblioteca já semeia cada chamada |
| **Teste de regressão contra o benchmark** (feito em 07/10) | `tests/test_regressao_benchmark.py` recalcula as 131 linhas de `metricas.csv` com a biblioteca e exige igualdade; quebrar a referência ou o corte de negativos derruba 99 delas. A máscara de horas avaliadas ainda é uma cópia no teste, até ser portada |
| **Não escolher modelo; a saída é a mediana de todos** (piloto de 09/10/2026) | escolher o melhor da rodada anterior piora nos 7 testes (até −0,23 na FV das casas); ficar só com os 5 ou 10 melhores ajuda o consumo e piora as usinas ou a FV. Não há regra de escolha que valha em todos os casos; a mediana empata com o melhor nos 6 testes A e B |
| **Correção de viés só para consumo** (piloto de 09/10/2026) | fator = real ÷ previsto dos últimos 14 dias, por série, só com o passado. No consumo leva o viés dos modelos de IA de ~−20% a <1% e a mediana de +0,191 a +0,207; na geração solar **piora** até −0,10 (o clima muda de um dia para o outro e o fator vira ruído). Desligada para geração |
| **Métricas em várias resoluções** (09/10/2026) | o consumo de uma casa hora a hora tem R² 0,37; no pico 17–20 h, 0,35; nos blocos noite/dia, 0,69; no total do dia, 0,58; somando as 20 casas, 0,64. No total do dia os modelos quase não passam da média de 7 dias (+0,10 o LightGBM, +0,01 a mediana). `protocolo` mede nas quatro resoluções e o usuário escolhe a da sua decisão (fatura, bateria, tarifa branca) |
| **Verificar o relógio pelo sol** em `qualidade` | o fuso das casas estava errado e só apareceu comparando o horário da geração FV com o meio-dia solar (salto de ~1 h em 29/03 nas 10 casas). A biblioteca faz essa checagem sozinha em toda série de geração |
| **A biblioteca e o aplicativo rodam só em CPU** (09/10/2026) | o melhor modelo de cada um dos 7 testes roda em CPU (TiRex-2, Toto-2.0-313m, Chronos-2, LightGBM), e a mediana só dos modelos de CPU fica igual ou melhor em 4 testes e no máximo 0,016 abaixo nos outros. GPU só para o benchmark. Para um usuário com 1–2 séries, a previsão do dia leva segundos |
| **TTM sem ajuste fino** (piloto de 09/10/2026) | ajustar a cabeça do TTM com os dados anteriores a cada dobra piora nos 3 casos (−0,010 a −0,019; ajustando também o decoder, −0,043). O TTM entra como está |
| **FlowState como segundo modelo pequeno** (piloto de 09/10/2026) | 9,1 M parâmetros, zero-shot: empata com o melhor no consumo e passa o TTM na geração solar (+0,134 × +0,119 na FV das casas; +0,114 × +0,092 nas usinas). Cabe num Raspberry Pi, não num ESP32; devolve quantis |
| **Interface pensada para o aplicativo** (09/10/2026) | o TCC é um aplicativo fácil de usar sobre a biblioteca (página web local como o SciKeywordMap ou programa como o Loom). A API pública precisa de uma chamada que faça a análise completa a partir dos arquivos do usuário e devolva um relatório |
| **O repositório é a cópia principal** | o exportador do Lactec copia arquivos antigos por cima dos novos (planilhas, `comum.py`, resultados da GPU). Trabalho da biblioteca não depende dele |

## 6. Princípios de projeto

- **Adaptadores finos, dependências opcionais.** `pip install prossumidor` traz só
  pandas, numpy, pvlib e LightGBM. Cada modelo fundacional é um *extra*
  (`prossumidor[chronos]`, `[timesfm]`, `[ttm]`…) com versão travada e teste de
  contrato — quando a API do fornecedor mudar, quebra um adaptador, não o projeto.
- **Um protocolo, um lugar.** Datas de corte, sementes e métricas vivem na tarefa,
  nunca no script.
- **Pipeline declarado.** O grafo de linhagem já calculado (`linhagem.json`) é a
  especificação do pipeline: cada etapa declara o que lê e escreve, e só o que
  mudou é refeito. Recomendo **não** escrever um executor próprio: usar Snakemake
  ou DVC por cima.
- **Contratos de dados.** Toda série carrega unidade, fuso, taxa e máscara de
  validade; nenhuma função aceita um DataFrame "cru".
- **Anonimização por padrão.** Nomes de proprietários nunca entram em nomes de
  arquivo ou colunas (pendência do `PLANO_ARTIGO.md`).

## 7. Esforço e ordem

| Versão | Conteúdo | Esforço (1 pessoa) |
|---|---|---|
| 0.1 | `io` (Fronius, medidor, clima), `qualidade`, `fisica`, `protocolo`, adaptadores de referências + LightGBM + Chronos-2 + TTM | ~4 semanas — o código existe, falta empacotar e testar |
| 0.2 | `diagnostico`, adaptadores NeuralForecast e demais fundacionais, `embarcado` | ~4 semanas |
| 0.3 | `economia` (ANEEL, Lei 14.300, HOMER), documentação, CI, publicação no PyPI | ~3 semanas |

## 8. Riscos e quando não fazer

- **Manutenção dos adaptadores** é o custo recorrente real. Mitigação: poucos
  modelos por padrão, os demais como contribuição.
- **Sobreposição com OpenSTEF** no lado do consumo: se o foco virar só carga de
  distribuidora, contribuir com o OpenSTEF é melhor que competir.
- **Dados de terceiros:** os dados das usinas e das casas não podem ir junto
  sem consentimento; a biblioteca precisa de dados de exemplo sintéticos.
- **Não vale a pena** se o objetivo for só publicar os artigos A e B: para isso
  basta congelar o protocolo (`comum.py` + `05_avalia.py`) e um Snakefile.
