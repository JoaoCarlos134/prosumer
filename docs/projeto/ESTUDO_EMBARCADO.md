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
**empata** com os modelos de tamanho cheio no consumo das casas (regime A): o LightGBM de 100 árvores de 15
folhas (17 KB por casa) dá +0,212, primeiro na estimativa pontual mas **empatado** com o melhor publicado (mediana
corrigida +0,2095, DM p 0,72) e com o LightGBM cheio (+0,206, p 0,15; o cheio ocuparia ~0,4 MB por casa). As
florestas 20×10 (+0,1929) e 50×10 (+0,1941) ficam um pouco abaixo da floresta cheia (+0,1942), também empatadas.
(Correção da revisão independente de 12/10: a 1ª versão dizia "igual ou acima" e "1º de 53" sem dizer que é
empate estatístico.)

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

Leitura: nos blocos e no dia, os modelos pequenos ficam bem acima da mediana na estimativa pontual (dia
+0,128/+0,136 contra +0,016; sem teste DM nem IC nessa resolução): a mediana subestima o consumo (viés dos fundacionais) e o erro se acumula na soma. Para uma decisão de
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
~320 KB de RAM), (c) skill até 0,02 abaixo do modelo cheio **ou** empata com a mediana. Leitura honesta de (c), da revisão: para
o Ridge ela é automática (o Ridge do piloto É o do benchmark, dif. 1,5e-14), e a marca `empata_com_mediana` do
script quer dizer "skill pontual >= mediana OU empata com o melhor" - o Ridge passa só pela estimativa pontual
(+0,1945 x +0,1938, sem teste; DM p 0,004 contra o melhor). O portão está no docstring do script, mas o
histórico do git (um commit só) não mostra que ele e a lista de modelos vieram antes dos resultados; o LightGBM
pequeno tem uma configuração só gravada (nenhuma busca no teste), a grade de 5 florestas foi avaliada no teste.

| Modelo | Skill | Posição (DM p vs melhor) | Float16 | Flash por casa | C − Python (linhas / ponta a ponta) | Cortex-M4F `.text` + `.rodata` | Portão |
|---|---|---|---|---|---|---|---|
| Ridge | +0,1945 (cheio +0,1945) | 7º/53 (p 0,004) | +0,1945 | 92 B | 4,0e-7 / 4,3e-7 | 488 + 88 B | **passa** (pontual >= mediana +0,194; não empata com o melhor) |
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
geração FV das casas (regime A) antes de recomendar o ESP32 para geração. (O 1º e o 3º foram feitos: seção 8.)

## 8. SparseTSF, CycleNet e a geração FV (12/10/2026, tarde)

Os dois passos sugeridos na seção 7: exportar as redes lineares do benchmark e repetir o piloto na geração.
Arquivos: `piloto_embarcado_redes.py` (redes; etapa `gera` no `~/.venvs/previsao_gpu` com torch, etapa `avalia`
no `.venv` com zig e node) e `piloto_embarcado.py casas_prod|usinas` (árvores e Ridge). Saídas em
`resultados/pilotos/`: `Emb-redes__<caso>.npz` (pesos de todas as dobras, históricos brutos, previsões do torch),
`Emb-{SparseTSF,CycleNet}[-torch]__<caso>__A.parquet`, `embarcado_redes.json`, `embarcado_casas_prod.json`,
`embarcado_usinas.json` e entradas no `resumo.json`. Nada em `previsoes/` nem no `metricas.csv`. CPU: ~2 min para
as redes nos três casos e ~2,5 min por caso para as árvores.

**Portão** (no docstring dos dois scripts, commit `7f2cc63`, ANTES de qualquer rodada destes casos; mais estrito
que o da seção 5): (a) C = Python em todas as horas, |C − Py| ≤ 1e-5 · max(|Py|, maior valor válido das 168 h da
janela) + 1e-7 kWh, com o C partindo das 168 h brutas (buracos como NAN); redes: todas as janelas de todas as
dobras, Py = torch retreinado; árvores: linhas de atributos e ponta a ponta da última dobra, Py = scikit-learn /
LightGBM em float64; (b) cabe no ESP32 (flash ≤ 4 MB, RAM ≤ 320 KB); (c) skill ≥ o do modelo cheio
correspondente no `metricas.csv` − 0,02 (c1), **ou** empata com o melhor do teste (DM p ≥ 0,05, sem Holm) (c2).
Sem critério refinado depois. Depois do commit do portão mudou uma coisa no script das redes, fora do portão:
`torch.set_num_threads(5)`, como o `04_redes_treinadas.py` (ver "Retreino").

### O que entrou na biblioteca

- `embedded.SparseTSF(conv, linear)`: na janela normalizada x, z = conv(x) + x (núcleo 25, preenchimento com
  zeros, sem viés), e cada uma das 24 fases é prevista pela mesma linear 7 → 1 dos valores daquela fase. 32
  parâmetros. `embedded.CycleNet(cycle, weight, bias)`: ciclo Q por série (24 h na geração, 168 h no consumo,
  como no benchmark) tirado da janela normalizada e somado de volta à saída da linear 168 → 24; fase = hora (W =
  24) ou dia da semana × 24 + hora (W = 168) do primeiro ponto, que numa previsão emitida à meia-noite é 0 ou
  dia_da_semana(dia) × 24 (`day_phase`). `CycleNet.fix(serie)` guarda o ciclo de uma série (índice na ordem do
  treino: ids ordenados), como `Trees.fix`; o `to_c` exige uma série por cabeçalho.
- Normalização exatamente a do `treina_proprio`: média e desvio **populacional** (numpy, ddof 0) das 168 h,
  desvio + 1e-3. `from_torch(modulo)` só lê o `state_dict()` (`.detach().cpu().numpy()`), sem importar torch;
  rejeita o backbone MLP do CycleNet e viés no SparseTSF.
- `causal_fill`: o preenchimento das janelas do benchmark (`DayAhead`: pandas `interpolate(limit_direction="both")`,
  0 sem nenhum valor válido), igual ao pandas bit a bit (teste). O cabeçalho faz o mesmo em float32
  (`prosumer_causal_fill`, `prosumer_normalize`), então o dispositivo recebe as 168 h brutas com NAN, como nos
  outros cabeçalhos. **Contrato diferente das árvores, declarado**: lá cada atributo com buraco recebe o valor de
  imputação; aqui o histórico é interpolado antes, como nas janelas das redes do benchmark.
- `predict(..., dtype=np.float32)` reproduz a ordem das contas do C (somas sequenciais); `forecast_day` corta
  negativos como o C; `<nome>_forecast_day(hist, dow, doy, series_code, out)` tem a mesma assinatura dos outros
  cabeçalhos (as redes ignoram `doy` e `series_code`; o SparseTSF também `dow`). `footprint`: flash = 4 bytes por
  parâmetro; RAM = histórico + janela (+ saída da convolução no SparseTSF) + 24 saídas.
- Testes (`tests/test_embedded.py`): referência numpy escrita direto do `forward` do torch (correlação, reshape,
  gather) com pesos montados à mão (roda na CI, sem torch); igualdade com módulos torch copiados do
  `redes_proprias` (pula sem torch; passa no `previsao_gpu`); C = Python via WebAssembly nos dois períodos e em
  todos os dias da semana; histórico constante (desvio 0, sobra o 1e-3) e sem nenhum valor válido.

### Retreino x previsões gravadas

| Rede | Caso | Retreinada × gravada (máx. / média, kWh) | numpy × torch (máx.) | Leitura |
|---|---|---|---|---|
| SparseTSF | consumo | 3,9e-4 / 3,6e-5 | 4,0e-7 | gravada em GPU, refeita em CPU |
| SparseTSF | FV casas | 6,2e-5 / 8,7e-6 | 2,4e-7 | idem |
| SparseTSF | usinas | 4,1e-4 / 8,3e-5 | 1,7e-6 | idem |
| CycleNet | consumo | **0,035 / 0,0036** | 6,7e-7 | CPU não determinístico (abaixo) |
| CycleNet | FV casas | **0,0** | 4,7e-7 | idêntica (com 5 threads) |
| CycleNet | usinas | **0,0** | 1,8e-6 | idêntica (com 5 threads) |

Achado: o treino do CycleNet em CPU depende do número de threads. A 1ª rodada (número de threads padrão do torch) deu até 0,038
kWh de diferença na FV das casas; com 5, como o `04`, deu 0,0 na FV das casas e nas usinas. No consumo (ciclo de
168 h, 20 séries), a dobra 1 com 1, 4, 8 e 20 threads diferiu até 0,024–0,037 kWh da gravada, com 2 e 5 bateu
(≤ 1,4e-6), e **com 5 threads também não é determinístico entre rodadas**: três rodadas no mesmo processo deram
0,024, 0,024 e 1,2e-6 kWh; na FV das casas, 0,0 nas três (medição avulsa, script fora do repositório). O skill do
CycleNet refeito no consumo é o do benchmark até a 4ª casa (+0,1659). O "determinístico em CPU" do `04` vale para a
FV das casas e as usinas, não para o consumo.

### Redes: resultado do portão

O skill é o das previsões **do C** (o que o dispositivo calcula), com a máscara de horas avaliadas do benchmark.

| Rede | Caso | Skill do C (benchmark) | Posição (DM p vs melhor) | Flash / RAM | C − torch máx. (razão à tolerância) | Portão |
|---|---|---|---|---|---|---|
| SparseTSF | consumo | +0,1907 (+0,1907) | 14º/53 (p 0,0001) | 128 B / 2,1 KB | 4,8e-7 (0,016) | **passa** por (c1); não empata |
| CycleNet W=168 | consumo | +0,1659 (+0,1659) | 26º/53 (p < 0,0001) | 16,9 KB / 1,4 KB por casa | 2,5e-6 (0,070) | **passa** por (c1); não empata |
| SparseTSF | FV casas | +0,0325 (+0,0325) | 39º/52 (p 0,002) | 128 B / 2,1 KB | 3,0e-7 (0,019) | **passa** por (c1); não empata |
| CycleNet W=24 | FV casas | +0,1376 (+0,1376) | 8º/52 (**p 0,124, empata**) | 16,3 KB / 1,4 KB por casa | 4,8e-7 (0,028) | **passa** |
| SparseTSF | usinas | +0,0547 (+0,0547) | 24º/54 (p < 0,0001) | 128 B / 2,1 KB | 1,4e-6 (0,025) | **passa** por (c1); não empata |
| CycleNet W=24 | usinas | +0,0623 (+0,0623) | 19º/54 (p < 0,0001) | 16,3 KB / 1,4 KB por usina | 2,4e-6 (0,037) | **passa** por (c1); não empata |

Melhor de cada teste: consumo `Ensemble-mediana-corrigida` +0,2095; FV casas `Toto-2.0-313m` +0,1779; usinas
`Crossformer` +0,1497. C − numpy em float32: **0,0** nas 6 (mesma aritmética). As 49 janelas das usinas com buraco
no histórico passaram pelo preenchimento do C (as casas não têm janela de teste com buraco). Objeto Cortex-M4F
(`-Os`): 562 B de código + 128 B de dados (SparseTSF); 560–626 B + 16,3–16,9 KB (CycleNet).

**Leitura honesta.** (c) é quase automático: a rede exportada é a do benchmark, então (c1) só falharia se o C ou o
retreino mudassem a previsão; o piloto testou de fato (a) e (b), e ambos passam com folga (o pior caso usa 7% da
tolerância). Caber e reproduzir não quer dizer ser boa escolha: só o CycleNet na FV das casas empata com o melhor
(e com o Ridge, +0,1376 × +0,1378); nos outros cinco casos a rede fica abaixo do Ridge de 92 B (seção 5 e abaixo).

### Árvores e Ridge na geração: resultado do portão

Mesmos modelos e configurações da seção 5, nada ajustado nestes casos. Ridge refeito × gravado: 1,8e-14
(FV casas) e 4,8e-13 (usinas).

| Modelo | FV casas: skill (cheio) | Posição (p) | Flash | Usinas: skill (cheio) | Posição (p) | Flash | Portão FV / usinas |
|---|---|---|---|---|---|---|---|
| Ridge | +0,1378 (+0,1378) | 7º/52 (**p 0,078, empata**) | 92 B | +0,0758 (+0,0758) | 16º/54 (p < 0,0001) | 92 B | passa / passa |
| RF 10×6 | +0,1148 (RF cheia +0,1076) | 18º (p 0,030) | 8,6 KB | +0,0955 (RF cheia +0,1012) | 10º (p < 0,0001) | 8,9 KB | passa / passa |
| RF 10×8 | +0,1005 | 23º (p 0,015) | 28,6 KB | +0,1012 | 8º (p < 0,0001) | 29,9 KB | passa / passa |
| RF 20×8 | +0,1119 | 19º (p 0,036) | 57 KB | +0,1012 | 8º (p < 0,0001) | 60 KB | passa / passa |
| RF 20×10 | +0,1121 | 19º (p 0,032) | 152 KB | +0,0957 | 10º (p < 0,0001) | 153 KB | passa / passa |
| RF 50×10 | +0,1149 | 18º (p 0,032) | 488 KB | +0,0997 | 10º (p < 0,0001) | 491 KB | **falha (a)** / passa |
| LightGBM 100×15 | +0,1161 (+0,0744) | 18º (p 0,046) | 21–22 KB por casa | +0,1135 (+0,0838) | 8º (p 0,0015) | 21–23 KB por usina | passa / passa |

Posições entre 52 (FV casas) e 54 (usinas) modelos. Mediana de todos: +0,1641 (FV casas), +0,1279 (usinas). Flash
das florestas = a floresta inteira (podada por série: −1 a −6%). RAM de trabalho 1.868 B em todos. Float16: skill
muda ≤ 0,0002.

- **RF 50×10 na FV das casas falha (a)**: as linhas de atributos batem (razão 0,019), mas na ponta a ponta uma hora
  difere 6,6e-4 kWh (40× a tolerância). Hipótese, **não conferida**: o C calcula um atributo (média de 7 dias ou
  total de ontem) em float32 a partir das 168 h, ele cai do outro lado de um limiar e a folha muda; é o mecanismo
  da 1 hora do LightGBM na seção 5. Fica registrado como falha, sem critério refinado.
- O LightGBM pequeno fica acima do cheio nos dois casos na estimativa pontual (+0,1161 × +0,0744; +0,1135 ×
  +0,0838), mas não empata com o melhor (p 0,046 e 0,0015). Só o Ridge empata, e só na FV das casas.
- (c) passa por (c1) em todos: os modelos pequenos ficam no nível dos cheios, mas a distância para o melhor
  (fundacionais, Crossformer) é real nestes casos.
- emlearn (só informação): diverge do scikit-learn em 2–45 horas na FV das casas e 0–2 nas usinas (até 0,07 kWh),
  como na seção 5.

### Veredito

Todos os modelos exportados **cabem** no ESP32 (o maior, a RF 50×10, usa 0,5 MB de 4 MB) e o C **reproduz** o
Python dentro do portão em 19 de 20 combinações modelo × caso desta seção (a exceção é a RF 50×10 na FV das
casas). Para escolher **o que** pôr no dispositivo decide o skill: no consumo, o LightGBM pequeno ou o Ridge (seção
5); na FV das casas, o Ridge (92 B) ou o CycleNet (16 KB), os dois empatados com o melhor; nas usinas nenhum
modelo de ESP32 empata com o melhor (o LightGBM pequeno, +0,1135, é o mais perto). O SparseTSF cabe em 128 B, mas
não empata em nenhum caso. Ressalvas: um regime só (A); nenhuma medida em hardware real (E5); o portão (c) é
fraco para as redes, como dito acima.
