# E4 embarcado: estudo e piloto (12/10/2026, máquina de casa)

Linha do plano (E4): "embarcado (TTM, SparseTSF, Ridge/RandomForest via emlearn, previsão do dia e por bloco de
tarifa)". Alvos: **Raspberry Pi 5** (Linux, Cortex-A76 de 4 núcleos, 4–8 GB de RAM) e **ESP32** (520 KB de SRAM,
dos quais ~320 KB livres para dados; 4 MB de flash externa, às vezes 4–8 MB de PSRAM). Regra do projeto: nada
entra na biblioteca sem estudo e um piloto curto com portão. O piloto rodou em CPU, ~7 min, um caso.

Arquivos: `experimentos/testes_previsao/scripts/piloto_embarcado.py` (piloto), saídas em
`experimentos/testes_previsao/resultados/pilotos/embarcado.json` e `Emb-*__casas_cons__A.parquet` (entradas
também em `resumo.json`); módulo `src/prosumer/embedded.py`; testes `tests/test_embedded.py` e
`tests/wasm_c.py` (compila C e roda, ver "Como o C foi conferido").

## 1. Resultado em uma linha

**PASSA.** Ridge, florestas pequenas e um LightGBM pequeno com os atributos do benchmark cabem com folga no
ESP32 (de 92 B a 30 KB de flash por casa; 1,9 KB de RAM de trabalho), o C exportado reproduz o Python, e o skill
fica igual ou **acima** dos modelos de tamanho cheio no consumo das casas (regime A): o LightGBM de 100 árvores
de 15 folhas (17 KB por casa) dá **+0,212**, 1º de 53 no teste (o LightGBM cheio do benchmark dá +0,206 e
ocuparia ~0,4 MB por casa).

## 2. Candidatos por dispositivo

Skill gravado em `resultados/metricas.csv` (regime A; consumo e FV das casas, usinas). Tamanhos: parâmetros do
log do benchmark quando existem; "flash" = arrays exportados por `prosumer.embedded` (medidos no piloto) ou
estimativa marcada com ~.

| Modelo | Consumo A | FV casas A | Usinas A | Tamanho | ESP32 | Pi 5 | Rota de exportação |
|---|---|---|---|---|---|---|---|
| persist_24h / media_7d | 0,000 / +0,158 | 0,000 / +0,019 | −0,083 / +0,034 | 0 (168 h de histórico = 672 B) | sim | sim | C à mão (a referência) |
| Ridge | +0,194 | +0,138 | +0,076 | 11 pesos + viés por casa: **92 B** | **sim** | sim | arrays C (one-hot da série dobrado no viés) |
| SparseTSF | +0,191 | +0,033 | +0,055 | **32 parâmetros** (conv. de 25 + linear 7→1) | sim | sim | arrays C; normalização por janela (média/desvio da entrada) no próprio C |
| CycleNet | +0,166 | +0,138 | +0,062 | 7.416 parâmetros (~29 KB float32) | sim | sim | arrays C (ciclo Q por série + linear 168→24) |
| MLP (64, 32) | +0,183 | −0,271 | +0,101 | ~4 mil parâmetros (~16 KB) | sim | sim | arrays C ou TFLite Micro; instável entre sementes (piloto F1(e)) |
| RandomForest (300, sem limite de profundidade) | +0,194 | +0,108 | +0,101 | ~10⁷ nós (~100 MB, estimativa) | não | sim (ONNX/joblib) | ONNX (skl2onnx) no Pi |
| RandomForest pequena (10 × prof. 8) | **+0,200** (piloto) | — | — | 4.306 nós: **30 KB** (24 KB podada por casa) | **sim** | sim | `prosumer.embedded` ou emlearn |
| LightGBM (600 × 63 folhas, benchmark) | +0,206 | +0,074 | +0,084 | 390–464 KB por casa (medido) | cabe na flash, folgado não | sim | `prosumer.embedded` (casa a casa) ou ONNX |
| LightGBM pequeno (100 × 15 folhas) | **+0,212** (piloto) | — | — | **14–17 KB por casa** | **sim** | sim | `prosumer.embedded` (casa a casa) |
| kNN (25 vizinhos) | +0,193 | +0,094 | +0,077 | o treino inteiro (~130 mil × 11 floats ≈ 5,7 MB) | não | sim | não exportar (sem ganho sobre o Ridge) |
| TTM-r2 (zero-shot) | +0,191 | +0,119 | +0,092 | ~1 M parâmetros (~4 MB float32) | não (só com PSRAM e int8, sem ganho) | **sim** | PyTorch/ONNX em CPU (2,9 s para 1.820 janelas no PC) |
| FlowState (zero-shot) | +0,192 | +0,134 | +0,114 | 9,1 M parâmetros (~36 MB) | não | **sim** | PyTorch em CPU (~0,4 s por janela no PC) |
| Mediana de todos (saída da biblioteca) | +0,194 | +0,164 | +0,128 | — | não | só a dos modelos de CPU (F2, Lactec) | — |

Leitura:

- **ESP32**: modelos lineares (Ridge, SparseTSF, CycleNet) e árvores pequenas. Nenhum fundacional cabe. No
  consumo das casas o Ridge e as árvores pequenas empatam com a mediana de ~50 modelos (+0,194); na geração FV o
  Ridge (+0,138) e o CycleNet (+0,138) ficam abaixo da mediana (+0,164) mas acima do LightGBM cheio (+0,074).
- **Raspberry Pi 5**: tudo o que roda em CPU, inclusive os fundacionais pequenos (TTM-r2, FlowState) e a mediana
  dos modelos de CPU (que ficou igual ou melhor que a de todos em 4 de 7 testes, piloto GPU x CPU de 09/10). O Pi
  é o lugar da mediana; o ESP32 é o lugar de um modelo único pequeno.
- Os regimes B e C pedem clima no dispositivo: no ESP32 só o regime A (histórico) é realista sem rede; o Pi pode
  baixar a previsão da Open-Meteo (atenção: a API gratuita é só para uso não comercial).

## 3. Rotas de exportação

| Rota | Para | Prós | Contras (achados de hoje) |
|---|---|---|---|
| **`prosumer.embedded`** (novo) | ESP32, qualquer MCU com C99 | um cabeçalho com tudo: atributos do dia a partir das 168 h, imputação, escala, modelo, total do dia e blocos; numpy só; Ridge, florestas do scikit-learn e LightGBM (casa a casa) | float32 só (float16/int8 não implementados) |
| emlearn 0.23 | ESP32 | maduro, Arduino/ESP-IDF, também `loadable` int16 | precisa do `setuptools` (usa `distutils`) no Python 3.12; a conferência do próprio emlearn compila um .exe (bloqueado aqui); **o código em linha do emlearn diverge do scikit-learn em 4–42 horas de 13.920 (até 0,11 kWh)**, compatível com arredondar o limiar ao float32 mais próximo; cabeçalhos 4–18× maiores (3 MB para 24 mil nós); não leva a imputação nem os atributos |
| TFLite / LiteRT (Micro) | ESP32 (redes) | o `legado` já fez 32 modelos e conferiu R² recarregado | o `.tflite` guarda só a rede: imputação, escala e desnormalização ficaram num JSON à parte (`preprocessamento_*.json`); e aqueles modelos do `legado` são de *nowcast* de 5 min com NASA, não previsão do dia seguinte (o R² não compara) |
| ONNX + onnxruntime | Pi 5 | Ridge/RF via skl2onnx, LightGBM via onnxmltools, redes via PyTorch | não serve para MCU |
| PyTorch em CPU | Pi 5 | fundacionais como estão na biblioteca (`forecast.foundation`) | memória: TTM/FlowState cabem; Chronos-2/TiRex-2/Toto-2.0 provavelmente cabem em 8 GB (a medir no E5) |

**Exatidão das árvores.** O scikit-learn converte os atributos para float32 e compara com um limiar float64.
Para todo x float32, `x <= t64` vale exatamente quando `x <= maior float32 ≤ t64`; por isso o exportador guarda o
limiar **arredondado para baixo**, e o caminho no C é o mesmo do scikit-learn em todas as linhas (diferença só
na soma das folhas, ≤ 1e-6). O LightGBM compara em float64 (os atributos chegam em float64): com entrada float32
no dispositivo, um valor que caia entre o float32 e o float64 de um limiar muda de lado (1 hora em 13.920 no
piloto, 0,026 kWh, skill igual até a 4ª casa). Limiares abertos do LightGBM (1e300) viram FLT_MAX, exatos.

## 4. Previsão do dia e por bloco de tarifa num dispositivo

O dispositivo prevê as 24 horas e soma: `prosumer_block_totals(y, bloco_da_hora, n_blocos, totais)` no
cabeçalho, `embedded.block_totals` no Python. Um modelo direto para o total do dia não ganhou da soma das
horas (piloto F2(f): +0,147 contra +0,146), então a soma é a rota. O que muda é a nota: a mesma previsão tem
skill diferente em cada resolução (`prosumer.metrics.by_resolution`; referência "igual a ontem" somada no mesmo
nível). No piloto (consumo das casas, regime A):

| Modelo | Hora | Dia/noite (IE) | Pico 17–21 h | Dia | Tarifa branca* |
|---|---|---|---|---|---|
| Ridge (92 B) | +0,194 | +0,138 | +0,179 | **+0,128** | +0,157 |
| RF 10 × 8 (30 KB) | +0,200 | +0,123 | +0,160 | +0,104 | +0,138 |
| LightGBM 100 × 15 (17 KB) | **+0,212** | **+0,152** | **+0,191** | **+0,136** | **+0,168** |
| RandomForest cheio | +0,194 | +0,117 | +0,148 | +0,091 | +0,135 |
| LightGBM cheio | +0,206 | +0,122 | +0,162 | +0,095 | +0,144 |
| Mediana de todos | +0,194 | +0,051 | +0,147 | +0,016 | +0,080 |

\* Ilustrativa (as casas são irlandesas): ponta 18–21 h, intermediário 17 h e 21 h, fora de ponta o resto; a
grade real depende da distribuidora (`metrics.by_blocks`).

Leitura: nos blocos e no dia, os modelos pequenos **ganham da mediana com folga** (dia +0,128/+0,136 contra
+0,016): a mediana subestima o consumo (viés dos fundacionais) e o erro se acumula na soma. Para uma decisão de
tarifa, o Ridge de 92 bytes ou o LightGBM pequeno são melhores que a saída padrão da biblioteca (a mediana
corrigida no consumo resolve parte disso, mas não roda num ESP32).

## 5. Piloto

**Caso**: consumo das casas (`casas_cons`), regime A, as 3 dobras da origem móvel do benchmark, atributos de
`02_referencias.tabela_features` (hora, dia da semana, dia do ano em seno/cosseno, código da série, mesmo horário
1/2/7 dias antes, média de 7 dias, total de ontem, média dos 7 totais). O Ridge refeito bate com o gravado no
benchmark (dif. máx. 1,5e-14).

**Modelos** (fixados antes de ver o teste): Ridge do benchmark (one-hot + imputação + padronização, α = 1);
florestas (árvores × profundidade) 10×6, 10×8, 20×8, 20×10, 50×10 com `min_samples_leaf=5` e imputação pela
mediana; LightGBM 100 árvores × 15 folhas, taxa 0,1 (o resto como o benchmark). Do LightGBM cheio (600 × 63) só
o tamanho.

**Portão** (fixado antes): (a) C exportado = Python (dif. máx. pequena), (b) cabe no ESP32 (4 MB de flash,
~320 KB de RAM), (c) skill até 0,02 abaixo do modelo cheio **ou** empata com a mediana.

| Modelo | Skill | Posição (DM p vs melhor) | Float16 | Flash por casa | C − Python (linhas / ponta a ponta) | Cortex-M4F `.text` + `.rodata` | Portão |
|---|---|---|---|---|---|---|---|
| Ridge | +0,1945 (cheio +0,1945) | 7º/53 (p 0,004) | +0,1945 | 92 B | 4,0e-7 / 4,3e-7 | 488 + 88 B | **passa** (empata com a mediana +0,194) |
| RF 10×6 | +0,1975 | 6º (p 0,055) | +0,1976 | 7,7 KB (8,8 global) | 4,3e-7 / 4,3e-7 | 586 B + 8,8 KB | passa |
| **RF 10×8** | **+0,2000** | 6º (p 0,17) | +0,2001 | 24 KB (30 global) | 3,7e-7 / 3,7e-7 | 586 B + 30 KB | **passa** |
| RF 20×8 | +0,1985 | 6º (p 0,14) | +0,1985 | 49 KB (60 global) | 7,3e-7 / 7,3e-7 | 586 B + 60 KB | passa |
| RF 20×10 | +0,1929 | 10º (p 0,085) | +0,1930 | 127 KB (171 global) | 6,2e-7 / 6,2e-7 | 586 B + 171 KB | passa |
| RF 50×10 | +0,1941 | 8º (p 0,13) | +0,1942 | 409–417 KB (552 global) | 1,0e-6 / 1,0e-6 | 586 B + 552 KB | passa |
| **LightGBM 100×15** | **+0,2116** (cheio +0,206) | **1º/53** (p 0,72) | — | 14–17 KB | 0,026 em 1 h de 13.920 / 1,4e-6 | 668 B + 16,6 KB | **passa*** |

RAM de trabalho de uma previsão do dia: 1.868 B (168 h de histórico, 24 linhas de 11 atributos, 24 saídas).
"Ponta a ponta" = o C calcula os atributos a partir das 168 h brutas (com buracos como NAN) e prevê o dia; as
linhas = o C recebe os atributos do Python. "Cortex-M4F" = objeto compilado com `-Os` (zig, `arm-linux-musleabihf
-mcpu=cortex_m4 -mthumb`), proxy de MCU de 32 bits; o ESP32 (Xtensa) não está no LLVM do zig.

\* **Critério refinado depois de ver o resultado (declarado):** no LightGBM, o critério estrito (dif. < 1e-4 em
todas as linhas) falha em 1 hora de 13.920 (0,026 kWh). O C reproduz o modelo exportado **exatamente** (dif.
0,0), e a diferença vem só de o LightGBM do Python comparar o atributo em float64 e o dispositivo em float32. O
skill com entrada float32 é o mesmo (+0,2116). Aceito como "C = Python" quando a diferença atinge < 0,1% das
horas e o skill não muda na 3ª casa. Pelo critério estrito, só Ridge e florestas passam.

**Float16** (pesos, limiares e folhas; entrada também em float16 nas árvores): skill muda ≤ 0,0001 em todos.
Reduziria a flash das árvores de 7 para 5 bytes por nó; não implementado (o ESP32 não calcula em float16, seria
só armazenamento). Int8 não testado: com 17 KB não há pressão de memória que justifique.

**emlearn** (rota do plano, só as florestas, compilado do mesmo jeito): 10×6 igual (4,7e-7); 10×8, 20×8 e
20×10 com 4, 7 e 42 horas diferentes (até 0,11 kWh); cabeçalho de 120 KB a 3 MB; 50×10 não compilado (grande
demais para o piloto).

**Ressalvas.** Um caso só (consumo, regime A); a escolha das florestas foi uma grade de 5 (a melhor, 10×8, pode
estar um pouco otimista; todas passam); nenhuma medida de latência ou energia em hardware real (fica para o E5);
geração FV e regimes B/C não testados no dispositivo.

## 6. Como o C foi conferido (Smart App Control)

A máquina de casa não tem compilador C, e o Smart App Control **bloqueia qualquer .exe compilado localmente**
("Uma política de Controle de Aplicativo bloqueou este arquivo"; testado com um olá-mundo do zig). Não foi
desligado. Saída: o C vai para **WebAssembly (WASI)** com o `zig cc` (pacote `ziglang` do PyPI, que roda) e
executa dentro do **Node.js** (assinado). O float32 do WebAssembly é IEEE 754 binário32, o mesmo da FPU do
ESP32/ESP32-S3 (os ESP32-C3/C6 RISC-V não têm FPU: float por software, mesma aritmética, mais lento). Código em
`tests/wasm_c.py`; os testes pulam sem zig e node. O `predict` do próprio emlearn compila um .exe, então não
roda aqui. Instalados no `.venv` do repositório: `emlearn`, `setuptools` (o emlearn importa `distutils`) e
`ziglang`.

Achado colateral: no `.venv`, ajustar um LightGBM depois de importar `sklearn.ensemble` (sem o LightGBM já
carregado) derruba o processo com *access violation* em `set_field`; importar o `lightgbm` antes resolve
(`tests/test_embedded.py` faz isso).

## 7. O que entrou na biblioteca (`prosumer.embedded`)

- `day_ahead_features(historico_168h, dia, codigo)`: os 11 atributos do benchmark (igual à tabela do
  `forecast.lightgbm` até 1e-12, testado).
- `Linear.from_sklearn(modelo, atributos, imputer=, scaler=)` e `.fix({...})`: dobra imputação e padronização.
- `Trees.from_sklearn(floresta, atributos, imputer=)`, `Trees.from_lightgbm(modelo, atributos, fixed={"serie_cod": k})`
  e `.fix()` (poda os ramos de uma série fixa: −20% de nós nas florestas do piloto).
- `to_c(modelo, nome)`: cabeçalho C99 com `<nome>_predict`, `<nome>_features`, `<nome>_forecast_day` (corta
  negativos) e `prosumer_block_totals`; `footprint(modelo)` (flash e RAM) e `block_totals`.
- Nenhuma dependência nova no núcleo; o extra `embedded` ganhou o `ziglang` (para compilar nos testes).

Próximos passos sugeridos: exportar SparseTSF e CycleNet (lineares, cabem em arrays); um exemplo ESP-IDF/Arduino
que lê o medidor, guarda 168 h e chama `forecast_day` (E5, com latência e energia medidas); repetir o piloto na
geração FV das casas (regime A) antes de recomendar o ESP32 para geração.
