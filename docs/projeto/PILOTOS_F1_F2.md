# Pilotos F1 e F2 do plano (11/10/2026, máquina de casa)

Regra do plano: cada melhoria começa por um piloto curto num caso, com a regra de escolha fixada **antes** de
ver o teste, e só vira trabalho completo se passar no portão. Portões: F1(e) ganho ≥ 0,05 e estável; F1(f)
grupo da frente no consumo; F2 skill +0,02 ou mais num caso (ou faixa calibrada: cobertura de 80% e 60% dentro de
±5 pontos e CRPS melhor que os quantis dos 14 dias anteriores).

Saídas em `experimentos/testes_previsao/resultados/pilotos/` (fora de `previsoes/`: nada publicado muda);
números em `resultados/pilotos/resumo.json`. Todos os pilotos que refazem um modelo do benchmark **conferem que
a versão de base reproduz a previsão gravada** (diferença máxima 0,0) antes de comparar, para que a diferença
venha só do que foi acrescentado.

| Item | Script | Resultado | Decisão |
|---|---|---|---|
| F1(d) AutoARIMA, memória | `piloto_autoarima_memoria.py` | não roda aqui: desde 11/10 o Smart App Control bloqueia o `statsmodels` (`_smoothers_lowess`) do ambiente `classicos`, e o `statsforecast.models` importa ele | **rodar no Lactec** (script pronto: uma série, uma dobra, pico de memória, vigia de 16 GB) |
| F1(e) MLP ajustado (FV das casas A) | `piloto_mlp.py` | sementes 42/1/2: −0,219 / +0,133 / −0,072 (benchmark −0,271); viés até +51% | **não passa** (instável); o MLP fica "sem ajuste" no texto |
| F1(f) TimesFM-3 | `piloto_timesfm3.py` | consumo +0,184 (16º/53, p < 0,001); FV casas +0,092 (28º); usinas +0,059 (22º) | **não passa** (+0,000 a +0,013 sobre o TimesFM-2.5 já no benchmark) |
| F1(f) BuildingsBench (consumo A) | `piloto_buildingsbench.py` | L (161 M, decide): +0,127 (40º/53, p < 0,001), viés −17%; M (16 M) +0,138, S (2,6 M) +0,121, ambos sem viés; faixas: cobertura de 80% entre 0,49 e 0,62, CRPS muito pior que a referência | **não passa** |
| F2(a) várias previsões do tempo (usinas C) | `08b_previsao_tempo_extra.py`, `piloto_multi_nwp.py` | LightGBM: IFS +0,330 → IFS+GFS+ICON +0,365 → 6 NWP **+0,373** (1º de 24 no C, à frente da mediana +0,367); IFS+AIFS +0,346 contra +0,299 do IFS com o mesmo treino curto. Todos p < 0,001 contra o par | **PASSA** |
| F2(b) geometria do telhado (FV casas B) | `piloto_geometria.py` | LightGBM com POA −0,029 (p 0,019); linear físico +0,020 (p 0,28) (números refeitos em 11/10 com `prosumer.physics`: o script original amostrava o sol 30 s cedo, `astype('timedelta64[m]')` truncava 2,5 min; a decisão não muda); inclinação estimada no limite da grade (60°) em 8 de 10 casas | **não passa** |
| F2(c) faixas (quantis) | `piloto_quantis.py` | ver a tabela abaixo: há uma fonte calibrada em cada caso do regime A | **PASSA** no regime A; no C falta calibrar |
| F2(d) atualização ao meio-dia (pico 17–20 h, consumo) | `piloto_meio_dia.py` | emitida às 12:00 **+0,265** contra +0,237 do melhor das 00:00 (Timer-XL-84m), p 0,023; +0,07 sobre o mesmo LightGBM das 00:00 | **PASSA** |
| F2(f) modelo direto do total do dia (consumo) | `piloto_total_dia.py` | direto +0,147 contra +0,146 da soma do Timer-XL-84m (p 0,98) e +0,095 da soma do LightGBM | **não passa** (empata com o melhor; registro: um LightGBM de 300 árvores empata com um fundacional de 84 M no total do dia) |

## F2(a) — várias previsões do tempo

Arquivo extra da Open-Meteo Previous Runs (`dados/previsao_tempo_extra.parquet`, mesmos pontos, variáveis e
horário do regime C). Cobertura: ICON, Météo-France, GEM e CMA desde 19/01/2024; ECMWF AIFS desde 17/02/2025;
UKMO desde 03/01/2025; JMA sem `previous_day1`. Variantes (fixadas antes): IFS (o C do benchmark, reproduzido
exatamente); IFS+GFS+ICON; os seis com arquivo completo; IFS+AIFS com treino desde 18/02/2025 e o par IFS com o
mesmo treino curto. Cada NWP entra como GHI e POA previstos, mais a média e o desvio da POA entre eles.

Leitura: a lacuna do regime C é qualidade da previsão do tempo, e combinar modelos fecha parte dela: o LightGBM
sozinho passa a mediana de todos os modelos. O AIFS (IA) acrescenta +0,047 sobre o IFS com o mesmo treino, mas
só tem ~5 meses de histórico antes do teste. Próximo passo: levar a combinação para a biblioteca (`io` da
Open-Meteo com vários modelos) e, se for o caso, refazer o regime C dos outros modelos com as entradas novas.

## F2(c) — faixas

| Fonte | Caso | Cobertura 80% | Cobertura 60% | CRPS (skill) | Portão |
|---|---|---|---|---|---|
| TimesFM-3 | consumo A | 0,795 | 0,574 | +0,080 | passa |
| LightGBM quantílico | consumo A | 0,771 | 0,581 | +0,085 | passa |
| Chronos-2 | consumo A | 0,743 | 0,542 | +0,097 | estreita |
| TimesFM-3 | FV casas A | 0,778 | 0,565 | +0,102 | passa |
| LightGBM quantílico | FV casas A | 0,647 | 0,449 | +0,103 | estreita |
| Chronos-2 | FV casas A | 0,787 | 0,555 | +0,163 | passa |
| TimesFM-3 | usinas A | 0,811 | 0,570 | +0,034 | passa |
| LightGBM quantílico | usinas A | 0,770 | 0,597 | +0,095 | passa |
| Chronos-2 | usinas A | 0,844 | 0,567 | +0,086 | passa |
| LightGBM quantílico | usinas C | 0,741 | 0,560 | **+0,340** | estreita por 0,009 |
| Chronos-2 | usinas C | 0,838 | 0,656 | +0,294 | larga por 0,006 |

Referência: quantis do mesmo horário nos 14 dias anteriores. FlowState (Lactec) ainda não rodado. Os pesos do
TimesFM-3 têm licença própria (anotada no plano como não comercial): a biblioteca deve preferir Chronos-2
(Apache-2.0) ou o LightGBM quantílico. No regime C as duas fontes erram a calibração por menos de 1 ponto além da
tolerância, com CRPS muito melhor que a referência: o passo natural é uma calibração causal (conformal sobre as
dobras anteriores): feito, ver F2(c') abaixo.

## F2(c') — calibração conformal causal das faixas (11/10/2026, noite) — PASSA

`scripts/piloto_conformal.py` (ambiente da biblioteca, ~20 s; saída `resultados/pilotos/conformal.json`), sobre os
quantis gravados de 11 combinações (LightGBM quantílico e Chronos-2 em consumo A, FV das casas A, usinas A e C;
TimesFM-3 nos três A). Para cada dia D só os erros dos N dias anteriores (todas as séries juntas; o real de D−1 é
conhecido às 00:00 de D). Calibração só nas **horas de produção**, definidas sem olhar o teste: sol acima do
horizonte nas usinas, perfil horário de ANTES do teste na FV das casas, todas no consumo. Sem isso as horas de
noite (faixa ~0, erro ~0) dominam a calibração: na primeira rodada o Chronos-2 no C não se mexeu. Avaliação nas
horas do benchmark, só nos dias com calibração ativa, as três faixas (bruta, calibrada, referência de 14 dias) nas
mesmas horas.

Três formas: CQR por par (Romano et al. 2019), aditivo ou normalizado pela largura; e um deslocamento por nível
(quantil a de (y − q_a)/largura de 80%, mediana inclusive). Passam o portão (±5 pontos nas duas coberturas, CRPS
melhor que a referência e, se a bruta já passava, CRPS no máximo 1% pior):

| forma | 14 dias | 28 dias |
|---|---|---|
| bruta (sem ajuste) | 7 de 11 | |
| CQR aditivo | 9 | 9 |
| CQR normalizado | 9 | 9 |
| **por nível** | 9 | **10** (CRPS +0,0024 em média; pior −0,013) |

Por nível, 28 dias: LightGBM FV das casas 0,651/0,457 → 0,814/0,622 (skill de CRPS +0,096 → +0,114); LightGBM C
0,741/0,560 → 0,810/0,634 (+0,337 → +0,345); Chronos-2 C, larga demais, 0,837/0,654 → 0,804/0,605 (+0,289 →
+0,296; o CQR não consegue estreitá-la: os erros se amontoam em 0 nas horas de borda do dia); Chronos-2 consumo
0,748/0,546 → 0,808/0,608. A única falha: TimesFM-3 FV das casas, que já passava e foi 3 pontos além (0,832/0,653).

**Na biblioteca:** `prosumer.postprocessing.conformal_quantiles` (por nível, 28 dias, mínimo 7, `hours=` para as
horas de produção); dá exatamente o resultado do piloto (diferença 0,0 nas 11). O `analyze` roda cada modelo com
quantis também nos 28 dias anteriores ao teste (uma dobra a mais, ajustada antes deles) e acrescenta a linha
`<modelo>+conformal`. Casas, 92 dias, LightGBM quantílico: FV 0,618/0,423 → **0,783/0,593** (calibrada, skill de
CRPS +0,081 → +0,085); consumo 0,771/0,573 → 0,795/0,594 (CRPS igual).

## F1(f) — BuildingsBench

NREL, BSD-3. Transformers codificador-decodificador pré-treinados em ~900 mil prédios **simulados** dos EUA
(Buildings-900K): 168 h de carga + calendário, tipo de prédio e latitude/longitude normalizadas; saída de 24 h
decodificada hora a hora; carga em Box-Cox ajustada no conjunto deles, cabeça gaussiana nesse espaço.

Instalação (11/10): `buildings_bench==2.0.0` e `tomli` com `--no-deps` no `previsao_gpu`; metadados (normalização
de lat/lon, `boxcox.pkl`) e pesos v1.1.0 S/M/L em `~/.cache/buildingsbench`, do OEDI. Configuração fixada antes:
casas residenciais, posição pela regra dos autores para casas fora dos EUA (Londres, Edimburgo e Sceaux vão para
Mt. Baker, WA), 2020 bissexto; decisão pelo L.

Resultado no consumo A: L +0,127 (40º de 53), viés −17%; M +0,138 (36º), S +0,121 (42º), os dois sem viés (os
outros fundacionais ficam em ~−20%). Nenhum perto do grupo da frente (+0,210). Faixas: a Box-Cox deles tem
λ = −0,067 (quase log), e a gaussiana nesse espaço vira uma cauda superior enorme nestas casas (q90 médio de
dezenas de kWh/h contra carga média de 0,6), com a faixa de 80% cobrindo só 49%–62% das horas: CRPS 2,6 a 14 vezes
o da referência. Leitura: prédios simulados dos EUA não transferem para casas irlandesas reais melhor que os
fundacionais gerais; o tamanho não ajuda (L pior que M). **Não passa.**

## Correção de viés do consumo x composição da mediana (12/10/2026) — NÃO vira saída do `analyze`

O piloto de 09/10 ("correção de viés só no consumo") usou a mediana de TODOS os ~40 modelos. Ao levar a regra
para o `analyze`, a mediana dele é pequena (ingênuas, + os modelos pedidos), e a correção piorou nas casas reais.
`scripts/piloto_vies_composicao.py` (previsões gravadas de casas_cons A, horas avaliadas do benchmark, mesma
`correct_bias` de 14 dias por casa):

| Mediana de | skill antes → depois | MBE antes → depois |
|---|---|---|
| ingênuas | +0,145 → +0,113 | -7,5% → +0,9% |
| ingênuas + LightGBM | +0,192 → +0,175 | -5,4% → +0,8% |
| ingênuas + TiRex-2, Toto-2.0, Chronos-2 | +0,193 → +0,186 | -18,2% → -0,6% |
| ingênuas + LightGBM + os 3 fundacionais | +0,200 → +0,195 | -16,5% → -0,5% |
| só os 3 fundacionais | +0,190 → +0,188 | -20,6% → -0,9% |
| todos (~40, o piloto de 09/10) | +0,194 → +0,209 | -18,9% → -0,6% |

A correção tira o viés de todas, mas só melhora o skill da mediana grande: o fator de 14 dias por casa é ruidoso
e só compensa quando há muito viés a tirar e a mediana já é estável. **Decisão:** no `analyze` a saída continua a
mediana; `median_corrected` (com os 14 dias antes do teste, então já corrige o primeiro dia) é uma linha a mais no
consumo, com nota quando a saída tem viés > 5%. O `Ensemble-mediana-corrigida` do benchmark não muda.

## E4: diagnostico da usina so com a energia horaria (12/10/2026) — PASSA

Pergunta: sem corrente/tensao CC e sem geometria (o caso comum de um prossumidor), a energia horaria CA e o local
reencontram os achados da analise de 5 min (`docs/projeto/ia_solar/ESTADO_DO_PROJETO.md`, "Diagnosticos
fechados")? Script `experimentos/testes_previsao/scripts/piloto_diagnostico.py` (sem `--biblioteca`: a 1a
versao; com: `prosumer.diagnostics.diagnose`); saidas `resultados/pilotos/diagnostico*.json`. Segundos de CPU.

Cadeia: dias claros pela propria serie (energia do dia / GHI de ceu claro >= 0,9 x percentil 90 da janela de
31 dias); orientacao ajustada nesses dias (bussola inteira); indice diario = energia / (kWp x POA de ceu claro);
retas por trecho (DP exato + BIC); degraus entre trechos = eventos.

PORTAO (fixado antes): achar a +-1 mes Cascavel limpezas nov/2023 e set/2024 (para cima); Curitiba falha da
string 1 dez/2022 (para baixo) e volta jul/2023 (para cima), reconfiguracao jun/2025 (para cima).

| Evento | Biblioteca (final) |
|---|---|
| Cascavel limpeza nov/2023 | 2023-11-04, +24% |
| Cascavel limpeza set/2024 | 2024-08-12, +10% |
| Curitiba falha dez/2022 | 2022-12-07, -17% |
| Curitiba volta jul/2023 | 2023-08-02, +101% |
| Curitiba reconfiguracao jun/2025 | nao achado |

A reconfiguracao foi vista nas TENSOES CC das strings; no indice CA mensal nao ha degrau (0,632 -> 0,663), entao
nao e detectavel so com energia CA: fica fora do portao, DECLARADO (o portao foi escrito antes de olhar isso).

O que o piloto mudou no caminho (declarar):

1. **Defeito na biblioteca:** `physics.fit_orientation` buscava azimutes 90-270 (leste-sul-oeste) por padrao;
   no hemisferio sul o painel olha para o norte. Cascavel saia 5 graus para leste e o indice tinha um vai e vem
   sazonal de +-30% que escondia as limpezas. Padrao agora: bussola inteira (Cascavel 15 graus / 30, a geometria
   conhecida e 13 / 25). Nenhum numero publicado usou o padrao (o piloto da geometria das casas passa a grade).
2. **Indice diario, nao horario semanal:** a 1a versao (mediana semanal do indice por hora) era ruidosa demais
   em Curitiba (relogio deslocado de fracao de hora, telhado de varios planos).
3. **Penalidade do BIC x3:** com o BIC comum as usinas tinham 9-11 degraus, quase todos sazonais (o residuo
   diario nao e ruido independente: autocorrelacao 0,15-0,17 e resto sazonal). O fator 3 foi ESCOLHIDO NESTAS
   DUAS USINAS (fatores 1, 2, 3, 4, 6 testados; 3 e o unico que da as duas limpezas e nada mais em Cascavel).
   Conferencia fora delas: nas 10 casas com FV de Dingle (1 ano, nenhum evento conhecido) da 1 degrau no total.
4. **Orientacao em varias passadas:** um degrau de nivel puxa o ajuste conjunto (falha sintetica 0,8 -> 0,55:
   20 graus em vez de 15). Escala por dia tira o degrau mas tambem a amplitude sazonal (Cascavel 10 graus / 50 e
   um degrau falso todo abril). Ficou: ajuste conjunto, depois de novo com o nivel de cada trecho entre degraus
   >= 5% dividido, ate a orientacao parar.

Limites: telhado de varios planos diferentes (Curitiba R2 0,81) deixa resto sazonal que vira degraus extras
(Curitiba +27% fev/2024, +19% dez/2024); com R2 < 0,85 ou inclinacao no limite da grade as notas chamam todo
degrau de incerto e nao relatam tendencia nem perda. Um telhado leste+oeste simetrico vira um plano equivalente
mais deitado (R2 0,996) e funciona. Sujeira x sombra x falha de string pedem dados de 5 min ou CC (proximo).
Decisao: entra na biblioteca (`prosumer.diagnostics`, secao `diagnostics` do `analyze` com `site`, `kwp=`).
