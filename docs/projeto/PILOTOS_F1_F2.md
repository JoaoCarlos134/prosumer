# Pilotos F1 e F2 do plano (11/10/2026, máquina com GPU)

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
| F1(d) AutoARIMA, memória | `piloto_autoarima_memoria.py` | não roda aqui: desde 11/10 o Smart App Control bloqueia o `statsmodels` (`_smoothers_lowess`) do ambiente `classicos`, e o `statsforecast.models` importa ele | **rodar na máquina de CPU** (script pronto: uma série, uma dobra, pico de memória, vigia de 16 GB) |
| F1(e) MLP ajustado (FV das casas A) | `piloto_mlp.py` | sementes 42/1/2: −0,219 / +0,133 / −0,072 (benchmark −0,271); viés até +51% | **não passa** (instável); o MLP fica "sem ajuste" no texto |
| F1(f) TimesFM-3 | `piloto_timesfm3.py` | consumo +0,184 (16º/53, p < 0,001); FV casas +0,092 (28º); usinas +0,059 (22º) | **não passa** (+0,000 a +0,013 sobre o TimesFM-2.5 já no benchmark) |
| F1(f) BuildingsBench (consumo A) | `piloto_buildingsbench.py` | L (161 M, decide): +0,127 (40º/53, p < 0,001), viés −17%; M (16 M) +0,138, S (2,6 M) +0,121, ambos sem viés; faixas: cobertura de 80% entre 0,49 e 0,62, CRPS muito pior que a referência | **não passa** |
| F2(a) várias previsões do tempo (usinas C) | `08b_previsao_tempo_extra.py`, `piloto_multi_nwp.py` | LightGBM: IFS +0,330 → IFS+GFS+ICON +0,365 → 6 NWP **+0,373** (1º de 24 no C, à frente da mediana +0,367); IFS+AIFS +0,346 contra +0,299 do IFS com o mesmo treino curto. Todos p < 0,001 contra o par | **PASSA** |
| F2(b) geometria do telhado (FV casas B) | `piloto_geometria.py` | LightGBM com POA −0,029 (p 0,019); linear físico +0,020 (p 0,28) (números refeitos em 11/10 com `prosumer.physics`: o script original amostrava o sol 30 s cedo, `astype('timedelta64[m]')` truncava 2,5 min; a decisão não muda); inclinação estimada no limite da grade (60°) em 8 de 10 casas | **não passa** |
| F2(c) faixas (quantis) | `piloto_quantis.py` | ver a tabela abaixo: há uma fonte calibrada em cada caso do regime A | **PASSA** no regime A; no C falta calibrar |
| F2(d) atualização ao meio-dia (pico 17–20 h, consumo) | `piloto_meio_dia.py` | emitida às 12:00 **+0,265** contra +0,237 do melhor das 00:00 (Timer-XL-84m), p 0,023; +0,07 sobre o mesmo LightGBM das 00:00 | **PASSA** |
| F2(f) modelo direto do total do dia (consumo) | `piloto_total_dia.py` | direto +0,147 contra +0,146 da soma do Timer-XL-84m (p 0,98) e +0,095 da soma do LightGBM | **não passa** (empata com o melhor; registro: um LightGBM de 300 árvores empata com um fundacional de 84 M no total do dia) |
| Horizonte longo, geração e consumo (12/10) | `piloto_horizonte.py` | geração: `encolhido` bate a climatologia no total do dia nos leads 1-7 nas duas usinas (+0,48/+0,49 no lead 1 a +0,18/+0,22 no 7, p ≤ 0,0002); leads 8-15 não testáveis (amostra curta, ~2 meses); consumo: `perfil_dia_util` bate `persist` nos leads 1-14 | **PASSA** (ver a seção no fim) |

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
| FlowState (CPU, 16/10) | consumo A | 0,537 | 0,389 | +0,052 | estreita |
| FlowState (CPU, 16/10) | FV casas A | 0,607 | 0,466 | +0,128 | estreita |
| FlowState (CPU, 16/10) | usinas A | 0,612 | 0,456 | +0,069 | estreita |

Referência: quantis do mesmo horário nos 14 dias anteriores. FlowState rodado em CPU em 16/10 (CPU, 4-12 min por
caso): CRPS melhor que a referência nos três, faixas estreitas demais; com a calibração conformal (F2(c') abaixo)
passa nos três. Os pesos do
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

**FlowState (acrescentado em 16/10; as 11 fontes acima saíram idênticas na nova rodada):** as seis formas
passam nos três casos. Por nível, 28 dias: consumo 0,541/0,393 → 0,806/0,608 (skill de CRPS +0,051 → +0,071); FV das
casas 0,609/0,468 → 0,818/0,627 (+0,115 → +0,125); usinas 0,611/0,454 → 0,806/0,617 (+0,066 → +0,091). (Os números
brutos diferem um pouco da tabela F2(c): aqui só os dias com calibração ativa.)

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

## E4: diagnostico da usina so com a energia horaria (12/10/2026) — PASSA EM PARTE (4 de 5)

Pergunta: sem corrente/tensao CC e sem geometria (o caso comum de um prossumidor), a energia horaria CA e o local
reencontram os achados da analise de 5 min (`docs/projeto/ia_solar/ESTADO_DO_PROJETO.md`, "Diagnosticos
fechados")? Script `experimentos/testes_previsao/scripts/piloto_diagnostico.py` (sem `--biblioteca`: a 1a
versao; com: `prosumer.diagnostics.diagnose`, mais a varredura do fator da penalidade e a conferencia nas casas);
saidas `resultados/pilotos/diagnostico.json` e `diagnostico_biblioteca.json` (todos os numeros abaixo saem
dela). Segundos de CPU (a varredura, ~30 s).

Cadeia: dias claros pela propria serie (energia do dia / GHI de ceu claro >= 0,9 x percentil 90 da janela de
31 dias); orientacao ajustada nesses dias (bussola inteira); indice diario = energia / (kWp x POA de ceu claro);
retas por trecho (DP exato + BIC); degraus >= 5% entre trechos = eventos.

PORTAO (escrito antes, no `ESPERADO` do script): achar a +-1 mes Cascavel limpezas nov/2023 e set/2024 (para
cima); Curitiba falha da string 1 dez/2022 (para baixo), volta jul/2023 (para cima) e reconfiguracao jun/2025
(para cima). **Resultado com o fator escolhido (3): 4 de 5.**

| Evento | Fator 3 (biblioteca) | Fator 2 |
|---|---|---|
| Cascavel limpeza nov/2023 | 2023-11-04, +24% | 2023-11-04, +24% |
| Cascavel limpeza set/2024 | 2024-08-12, +10% | 2024-08-12, +10% |
| Curitiba falha dez/2022 | 2022-12-07, -17% | 2022-12-07, -21% |
| Curitiba volta jul/2023 | 2023-08-02, +101% | 2023-08-02, +103% |
| Curitiba reconfiguracao jun/2025 | nao achado | 2025-07-29, +15% |
| Degraus a mais nas usinas | Curitiba +27% fev/2024, +19% dez/2024 | Cascavel -5% ago/2021; Curitiba -19% mar/2022, +23% dez/2024 |
| Degraus nas 10 casas de Dingle (sem evento conhecido) | 1 | 8 |

Os tamanhos de Curitiba (+101%) sao medidos do fim de uma reta muito inclinada ao inicio da seguinte, num telhado
mal descrito por um plano: valem como "houve um evento", nao como tamanho (na analise de 5 min a string 1 caiu
-50% e a 2, -18%). As notas da biblioteca chamam esses degraus de incertos.

**Correcao (revisao independente de 12/10):** a 1a versao deste texto dizia PASSA, tirava a reconfiguracao do
portao ("vista so nas tensoes CC, sem degrau no indice CA") e dizia que o fator 3 era "o unico que da as duas
limpezas e nada mais em Cascavel". As tres coisas estavam erradas: o portao foi REDUZIDO depois da rodada; com o
fator 2 a reconfiguracao aparece (+15% em 2025-07-29), entao ela e visivel na energia CA; e o fator 4 da as mesmas
duas limpezas em Cascavel (mas perde a falha de Curitiba). O numero citado para o indice mensal (0,632 -> 0,663)
nao tinha script nem saida gravada e saiu.

**Escolha do fator (declarar: feita NESTAS usinas e casas):** fatores 1, 2, 3, 4, 6 na cadeia inteira. So o 2
passa o portao completo, mas da 8 degraus nas casas, varios em 26-29/03/2020 (mudanca de horario na Irlanda; a
fonte tem 20 linhas em hora impossivel nessa data). O 3 perde a reconfiguracao e da 1 degrau nas casas. Fica o 3:
o aplicativo e para leigo e um alarme falso custa mais que um evento de +15% perdido. Limite da conferencia nas
casas: ~65-70 dias claros por casa e ajuste do telhado nao confiavel em 8 de 10 (inclinacao no limite da grade),
entao ela mede alarme falso so onde o modulo ja avisa que nao confia; nao vale como prova para telhados bem
ajustados.

O que o piloto mudou no caminho:

1. **Defeito na biblioteca:** `physics.fit_orientation` buscava azimutes 90-270 (leste-sul-oeste) por padrao;
   no hemisferio sul o painel olha para o norte. Cascavel saia 5 graus para leste e o indice ficava com um vai e
   vem sazonal que escondia as limpezas. Padrao agora: bussola inteira (Cascavel 15 graus / 30; a geometria
   conhecida e 13 / 25). Nenhum numero publicado usou o padrao (os dois chamadores passam a grade).
2. **Indice diario, nao horario semanal:** a 1a versao (mediana semanal do indice por hora) era ruidosa demais em
   Curitiba (relogio deslocado de fracao de hora, telhado de varios planos).
3. **Penalidade do BIC x3:** com o BIC comum (fator 1) as usinas tem 9 e 11 degraus, quase todos sazonais (o
   residuo diario nao e ruido independente).
4. **Orientacao em varias passadas:** um degrau de nivel puxa o ajuste conjunto (falha sintetica 0,8 -> 0,55:
   20 graus, R2 0,84, 5 degraus; com as passadas, 15 graus e 1 degrau - guardado em
   `tests/test_diagnostics.py`). Uma variante descartada (escala por dia, que tira tambem a amplitude sazonal)
   deu em Cascavel 10 graus / 50 e um degrau falso todo abril; o codigo dela nao foi guardado.

Defeitos achados pela revisao e consertados antes de seguir: serie toda zero derrubava `diagnose` e `analyze`
(divisao por zero); inversor que morre no meio dava orientacao sem sentido (R2 -1: os dias mortos contavam como
claros, 0 >= 0,9 x 0); `kwp` por serie incompleto dava nota falsa (agora e erro). Testes novos para cada um, mais
hemisferio norte com horario de verao e buracos.

Limites: telhado de varios planos diferentes (Curitiba R2 0,81) deixa resto sazonal que vira degraus extras; com
R2 < 0,85 ou inclinacao no limite da grade as notas chamam todo degrau de incerto e nao relatam tendencia nem
perda. Um telhado leste+oeste simetrico vira um plano equivalente mais deitado (R2 > 0,99 no teste) e funciona.
Sujeira x sombra x falha de string pedem dados de 5 min ou CC (proximo).
Decisao: entra na biblioteca (`prosumer.diagnostics`, secao `diagnostics` do `analyze` com `site`, `kwp=`), com
fator 3 e a perda da reconfiguracao declarada.

## Horizonte longo: a proxima semana, por hora e no total do dia (12/10/2026) — PASSA nos leads 1-7 (geracao) e 1-14 (consumo)

Pergunta: para marcar cargas pesadas na semana, ate que antecedencia k (dias) a previsao do tempo ainda ajuda a
geracao FV contra a climatologia, com que metodo, e quanto confiar nela (fator a_k)? No consumo (sem clima), que
regra de historico serve de 1 a 14 dias? Script `experimentos/testes_previsao/scripts/piloto_horizonte.py`;
saidas `resultados/pilotos/horizonte.json` (os numeros abaixo saem dele, exceto os da contagem de pedidos e das
razoes Meteo-France/IFS dos leads 1-2, ver abaixo) e `horizonte_usina_*.parquet`;
tempo baixado em `dados/previsao_tempo_horizonte.parquet` (Previous Runs, `previous_day1..7`, seis modelos,
GHI, 4,7 MB, 84 pedidos, ~11 min, nenhum 429; o json guarda so a segunda usina, 42 pedidos e 338 s, porque o
`grava` substituiu o dicionario: os 84 pedidos vem dos horarios do cache, 17:02-17:13) e `dados/previsao_tempo_rodadas.parquet` (Single Runs, 0,2 MB,
256 pedidos, ~9 min). Antecedencia k = previsao do dia D emitida as 00:00 de D-k+1, com o observado ate 23:00 de
D-k (k = 1 e o benchmark). Contas: ~4 s por usina, 1 s no consumo (CPU).

**Ordem dos commits (para a revisao):** `f5509d7` = script com o portao G1-G4 e o filtro de qualidade, ANTES de
qualquer download ou conta (so a disponibilidade da Single Runs foi sondada antes, sem numero de previsao: o
arquivo comeca em 02/04/2026). `7e8e003` = comparacao EXTRA pedida pela sessao principal (linhas do regime C do
benchmark no lead 1, referencias do consumo, Meteo-France no lead 3), acrescentada DEPOIS do commit do portao e
antes de rodar o `avalia` e o `compara`; NAO faz parte do portao. O consumo (`casas`) e o calculo da usina
Cascavel rodaram entre os dois commits; nada no portao mudou.

Metodos da geracao (orientacao do telhado por `diagnostics.roof_orientation` antes do teste: Cascavel 15 graus /
30, R2 0,919; Curitiba 20 / 320, R2 0,819; kW_eff = mediana do `performance_index` dos dias claros CAUSAIS dos
60 dias anteriores): `fisico` = kW_eff x POA da media do GHI previsto; `ajustado` = b x POA prevista, b de
minimos quadrados nos 90 dias anteriores com o arquivo do proprio lead; `climatologia` = kW_eff x POA de ceu
claro x claridade mediana do mesmo mes em anos anteriores; `persist_cs` = indice de ceu claro do ultimo dia
completo; `encolhido` = climatologia + a_k (fisico - climatologia), a_k ajustado antes do teste (duas usinas
juntas, normalizadas). Teste: 297 dias em Cascavel, 301 em Curitiba (dias com todas as horas de sol validas);
4.014 e 4.025 horas de sol.

PORTAO (no docstring, commit `f5509d7`): G1 metodo de tempo escolhido = maior skill medio contra a climatologia
no total do dia, leads 1-7, duas usinas; G2 usa o tempo no lead k so se o escolhido bate a climatologia no total
do dia com skill > 0 e DM p < 0,05 nas DUAS usinas; G3 leads 8-15 so relato ("indicativo" se o fisico bate a
climatologia com p < 0,05 nas duas, nunca adotado); G4 consumo: maior skill medio por hora contra `persist` nos
leads 1-14, desde que bata `persist` em todos (skill > 0 e p < 0,05).

**Filtro de qualidade do tempo (declarado antes de rodar, aviso da sessao principal):** um modelo sai da media no
dia se alguma hora tem GHI > 1,2 x ceu claro + 50 W/m2. Descartes (modelo-dias, todo o periodo baixado,
Cascavel / Curitiba): IFS 0/0 nos leads 1-5, **54/99 no lead 6 e 177/178 no lead 7**; GEM 0-10; CMA 0-7; GFS,
ICON e Meteo-France 0. O IFS dos leads 6-7 nao e um defeito isolado: o arquivo vem de passos de 3 ou 6 h
interpolados, que espalham energia para as horas de manha cedo e fim da tarde (media do lead 7 em Cascavel: 1,59
x ceu claro as 18 h e 4,0 x as 19 h; no lead 1, 0,84 e 1,96). O filtro pega essas horas de borda. Os dias
descartados do IFS no lead 7 em Cascavel caem quase todos antes do teste (172 de 177 entre mar/2024 e abr/2025), isto e, no periodo que ajusta o
a_k e o `ajustado`. Na Single Runs (rodadas das 12 UTC) o filtro nao descartou nada. Os descartes do IFS terminam
por volta de 19-20/04/2025: o arquivo dos leads longos do IFS parece um produto diferente no comeco da calibracao e
no teste (revisao). Efeito pequeno: sem o filtro, a_6 = 0,868 e a_7 = 0,820 (contra 0,855/0,785), e o skill de teste
dos leads 6-7 muda no maximo 0,005.

**Composicao dos modelos por lead (do arquivo, nao escolhida):** Meteo-France so tem `previous_day1..3`; ICON nao
tem `previous_day7`; o CMA dos leads 5-7 para em 07/08/2025 (esta na calibracao, quase nao esta no teste). A
media dos leads 1-3 tem seis modelos; a do lead 7, IFS (filtrado), GFS e GEM. Media e espalhamento mudam de
composicao entre calibracao e teste nos leads 5-7.

Conferencia: o lead 1 baixado agora reproduz os arquivos do regime C do benchmark (`previsao_tempo.parquet` +
`previsao_tempo_extra.parquet`) com **diferenca maxima 0,0** nos seis modelos e nas duas usinas (18.095-19.727
horas comuns por modelo; 1 hora a mais no novo, a ultima, que o deslocamento do rotulo deixa vazia no benchmark).

### Geracao: skill do total do dia contra a climatologia

| lead | fisico Casc. / Curit. | ajustado Casc. / Curit. | encolhido Casc. / Curit. | p encolhido | a_k | G2 |
|---|---|---|---|---|---|---|
| 1 | +0,490 / +0,502 | +0,507 / +0,516 | +0,481 / +0,495 | < 0,0001 | 1,083 | passa |
| 2 | +0,450 / +0,428 | +0,460 / +0,447 | +0,445 / +0,421 | < 0,0001 | 1,069 | passa |
| 3 | +0,418 / +0,397 | +0,428 / +0,412 | +0,416 / +0,395 | < 0,0001 | 1,051 | passa |
| 4 | +0,387 / +0,385 | +0,403 / +0,383 | +0,394 / +0,390 | < 0,0001 | 0,916 | passa |
| 5 | +0,345 / +0,321 | +0,357 / +0,320 | +0,356 / +0,331 | < 0,0001 | 0,906 | passa |
| 6 | +0,207 / +0,301 | +0,218 / +0,296 | +0,239 / +0,308 | < 0,0001 | 0,855 | passa |
| 7 | +0,128 / +0,200 | +0,130 / +0,191 | +0,177 / +0,220 | 0,0002 / < 0,0001 | 0,785 | passa |

Por hora (horas de sol), contra a climatologia, o encolhido da +0,335/+0,295 no lead 1, +0,264/+0,227 no 4 e
+0,111/+0,116 no 7 (Cascavel/Curitiba), todos p < 0,001. A `persist_cs` perde da climatologia em todos os leads
(dia: -0,10/-0,05 no lead 1, -0,34/-0,39 no 7): a climatologia ja ganha da persistencia no lead 1. a_k por usina:
Cascavel 1,029 -> 0,806, Curitiba 1,133 -> 0,767 (lead 1 -> 7); o a_k > 1 dos leads 1-3 diz que, antes do teste,
o fisico reagia de menos as nuvens previstas. **Correcao da revisao independente (12/10): isso NAO se confirma no
teste.** Ajustado nos proprios dias de teste (oraculo, so para conferir), o a_k fica abaixo de 1 em todos os leads
nas duas usinas (lead 1: 0,943/0,984; lead 3: 0,951/0,984; lead 7: 0,595/0,715), e nos leads 1-3 o encolhido e o
pior dos tres metodos de tempo (lead 1: +0,481/+0,495 contra fisico +0,490/+0,502 e ajustado +0,507/+0,516; DM
encolhido x ajustado em Cascavel no lead 1, p 0,016): o a_k > 1 custa ~0,007-0,009 de skill nos leads 1-3.

**G1:** skill medio no dia, leads 1-7, duas usinas: fisico +0,354, ajustado +0,3619, **encolhido +0,3620**. O
encolhido e o escolhido pela regra, mas a diferenca para o ajustado e de 0,0001: e um EMPATE, nao um "melhor".
Nos leads 1-3 o ajustado tem o maior skill pontual e o encolhido o menor dos tres; o encolhido so se separa nos
leads 6-7 (onde o a_k < 1 puxa para a climatologia). **G2: passa nos sete leads.** Padrao da biblioteca:
encolhido com a_k = 1,083 / 1,069 / 1,051 / 0,916 / 0,906 / 0,855 / 0,785 (leads 1-7).

Espalhamento x erro (Spearman entre o desvio relativo do GHI entre os modelos e o erro absoluto relativo do total
do dia do encolhido): Cascavel +0,29 a +0,43, p < 0,001 em todos os leads; Curitiba +0,07 a +0,21, p < 0,05 so
nos leads 2, 3, 4 e 7 (p 0,09-0,20 nos 1, 5, 6). O espalhamento diz algo sobre o erro, de forma fraca, e mais
em Cascavel.

### Leads 8-15 (Single Runs, so relato — G3)

O arquivo de rodadas unicas comeca na rodada de 02/04/2026 12 UTC (IFS e GFS; as de 28/03-01/04 nao existem).
Avaliavel so em ~42-58 dias de abr-mai/2026 (outono), sem periodo anterior ao teste: nem `ajustado` nem a_k.
Media de IFS e GFS; o IFS vai ate o lead 14, o lead 15 e so GFS. Skill do fisico no total do dia contra a
climatologia (p do DM):

| lead | Cascavel | Curitiba | lead | Cascavel | Curitiba |
|---|---|---|---|---|---|
| 1 | +0,464 (0,005) | +0,522 (< 0,001) | 9 | +0,025 (0,86) | +0,072 (0,41) |
| 4 | +0,348 (0,030) | +0,442 (< 0,001) | 10 | +0,045 (0,75) | +0,079 (0,37) |
| 5 | +0,227 (0,094) | +0,391 (< 0,001) | 12 | -0,089 (0,54) | +0,006 (0,94) |
| 6 | +0,067 (0,65) | +0,232 (0,003) | 13 | -0,170 (0,21) | -0,043 (0,66) |
| 7 | +0,114 (0,46) | +0,146 (0,086) | 14 | -0,092 (0,43) | +0,056 (0,56) |
| 8 | -0,029 (0,82) | +0,217 (0,030) | 15 | **-0,403 (0,015)** | -0,056 (0,58) |

Nenhum lead de 8 a 15 fica "indicativo" (G3). Nesta amostra curta o fisico ja nao se separa da climatologia em
Cascavel a partir do lead 5 (no arquivo longo de Previous Runs separa ate o 7: a amostra de 2 meses tem pouco
poder); Curitiba separa ate o 6 e no 8. No lead 15 (so GFS) o fisico e significativamente PIOR que a
climatologia em Cascavel. Leitura: alem de 7 dias este piloto nao da base para usar o tempo; a amostra (2 meses,
uma estacao) tambem nao prova que nao ha nada.

### Consumo (20 casas, teste out-dez/2020): skill por hora contra `persist` (p do DM)

| lead | semana | media_4sem | media_7d | perfil_dia_util |
|---|---|---|---|---|
| 1 | -0,126 (< 0,001) | +0,101 | +0,158 | +0,160 |
| 2 | -0,069 (0,006) | +0,146 | +0,175 | +0,196 |
| 4 | -0,014 (0,44) | +0,190 | +0,190 | +0,236 |
| 7 | 0,000 (= persist) | +0,202 | +0,185 | +0,245 |
| 10 | +0,004 (0,89) | +0,203 | +0,190 | +0,249 |
| 14 | 0,000 (= persist) | +0,200 | +0,189 | +0,244 |

(as tres medias: p < 0,001 em todos os leads; tabela completa, leads 1-14, no json.) No total do dia o
`perfil_dia_util` da +0,011 (p 0,87) no lead 1, empata com `persist`; +0,127 (p 0,009) no 2 e +0,21 a +0,23
(p <= 0,003) do 4 ao 14. **G4: perfil_dia_util (skill medio por hora +0,234; media_4sem +0,187; media_7d +0,186)
bate `persist` nos 14 leads: passa.** Nos leads 7 e 14 a `semana` e o proprio `persist` (o mesmo dia da semana e
o ultimo observado). O skill cresce com o lead porque a referencia piora (o dia observado fica mais longe), nao
porque a regra melhora.

### Comparacao extra (fora do portao, commit `7e8e003`)

(a) Lead 1 nas usinas, nas 8.940 horas avaliadas do benchmark, skill contra `persist_ceu_claro|A` (p do DM contra
o LightGBM|C): Ensemble-mediana|C +0,367 (p < 0,001), LightGBM|C +0,330, **fisico +0,325 (p 0,88)**,
**encolhido +0,321 (p 0,73)**, linear_fisico|C +0,312 (p 0,15), climatologia +0,031, persist_cs +0,004. Os
skills recalculados das linhas do benchmark sao iguais aos do `metricas.csv` (0,3118 / 0,3303 / 0,3673): as
horas sao as mesmas. O fisico e o encolhido EMPATAM com o LightGBM do regime C (com seis modelos de tempo em vez
de so o IFS, e sem treino alem de kW_eff, orientacao e a_k) e perdem da mediana de todos os modelos.
(b) Consumo, lead 1: as referencias do benchmark `persist_24h` 0, `semanal_168h` -0,1258 e `media_7d` +0,1575 sao
reproduzidas exatamente pelas regras `persist`, `semana` e `media_7d`; `perfil_dia_util` +0,1595.
(c) Meteo-France no arquivo: so ha `previous_day1..3` (4-7 vazios). No lead 3 o GHI fica alto mas nao
impossivel (maximo 1.089 W/m2 em Cascavel, 1.083 em Curitiba; IFS 1.110/1.138), mas a razao Meteo-France/IFS da
soma das 9-15 h cresce com o lead (Cascavel ~1,01 / 1,08 / 1,13, Curitiba ~1,07 / 1,14 / 1,19 nos leads 1/2/3,
recontados pela revisao nas horas em que todos os modelos tem valor; os da 1a versao, 1,02/1,09/1,15 e
1,08/1,16/1,20, nao saem do script, que so calcula o lead 3) e chega a 1,4-2,1 as 17-18 h. Nao e o 2-2,8x da
Forecast API ao vivo, mas e ~10-20% acima dos OUTROS MODELOS (nao do medido) e entra na media dos leads 2-3. O filtro descartou 0 dias do Meteo-France.

**Decisao:** padrao da biblioteca na geracao: `encolhido` com os a_k acima nos leads 1-7 (empatado com o
`ajustado`; o encolhido nao precisa do arquivo de previsoes de cada lead depois de ajustado o a_k), **com o a_k
limitado a 1 (decisao DEPOIS da revisao, portanto post hoc: nos leads 1-3 o a_k > 1 nao se confirmou no teste; com
a_k = 1 o metodo e o fisico nesses leads)**;
climatologia a partir do lead 8. Consumo: `perfil_dia_util` nos leads 1-14. Limites: duas usinas no mesmo estado;
o lead 7 do IFS depende do filtro (interpolacao de passo de 6 h); a composicao dos modelos muda entre calibracao
e teste nos leads 5-7; o Meteo-France puxa a media para cima nos leads 2-3; os leads 8-15 tem so ~2 meses; as
casas sao um outono irlandes.

## E6: a conta da `economics.brazil` contra as faturas reais da Copel (16/10/2026, CPU) — NAO PASSA

Pergunta: com a tarifa convencional da Copel (`COPEL-DIS`, ANEEL), bandeiras, custo de disponibilidade, SCEE / GD I
(usina de Cascavel, 07/2019) e ICMS + PIS/COFINS, o `brazil.Setup(...).bill` reproduz o total pago mes a mes? Script
`experimentos/testes_previsao/scripts/piloto_fatura.py`; saidas `resultados/pilotos/fatura.json` (rodada do portao) e
`fatura_sem_duplicatas.json` (diagnostico pos-hoc); livro da ANEEL em `dados/aneel_*.csv` (ODbL 1.0, atribuicao
ANEEL; base derivada redistribuida fica sob ODbL). Dados: planilha feita a mao pelo dono com o resumo das faturas
(so na máquina de CPU, nunca copiada): por mes de referencia, kWh importado, kWh injetado, total pago e saldo; NAO tem
COSIP, aliquotas, bandeira nem a energia separada. 104 faturas (01/2018-08/2026): P0 sem geracao 19 (01/2018-07/2019),
P1 com geracao 85; nenhuma excluida (em todas as P1 a injecao do mes cobre o importado acima de 50 kWh, entao o
saldo nao entra). Gravados so erros relativos por fatura e agregados.

**Ordem dos commits:** `0e971b4` = script com a pergunta, o metodo e o PORTAO, antes de qualquer conta contra as
faturas (vistos antes: a estrutura e os numeros brutos da planilha, a razao injecao/geracao por janela e o minimo de
50 kWh pela conta do saldo de 2019; declarado no docstring). `daa47d0` = so velocidade (memoizacao; a 1a rodada foi
parada antes de terminar qualquer configuracao). `e6274db` = resultados da rodada do portao. `793fa25` = modo
`sem-duplicatas` (pos-hoc), `b3e2c60` = seus resultados.

Metodo: serie horaria cujo total bate com a fatura (importado I nas horas 0-5 e 18-23, injetado X nas 10-13, sem
sobreposicao): na convencional o preco so depende do dia e o SCEE compensa em kWh no mes, entao a conta depende so de
I, X e dos dias. Periodo: a fatura M cobre ~9/(M-1)..8/M (conferido: injecao/geracao do inversor por fatura tem
desvio-padrao 0,068 no ciclo do dia 9, contra 0,158 no mes M-1 e 0,150 no mes M). Primaria `ciclo` = o ciclo em dois
pedacos de mes-calendario, cada um faturado pela biblioteca com sua fracao de dias dos kWh e do minimo (pro-rata da
Copel); `calendario` = a fatura inteira no mes M-1 (o jeito do aplicativo). SUPOSICOES (a planilha nao tem as
aliquotas): ICMS do PR 29% / 18% de 23/06/2022 / 19% de 18/03/2024 (tabela do legado; o `from_aneel` so aceita uma
aliquota para todas as datas, entao a tabela do livro foi trocada), PIS/COFINS 9,25% nominal; minimo 50 kWh; GD I.
COSIP (desconhecida): em P0 mediana de (pago - conta) nas OUTRAS 18 faturas; em P1 a mediana das 19 de P0.
Leituras da lei: `icms_exempt_compensated` "all" (padrao), `bandeira_on_minimum=True` (padrao), bandeira por mes
(pro-rata no `ciclo`), `pis_cofins_exempt_compensated=True`; `gd2_minimum` e `after_2028` nao se aplicam (GD I ate
2045), ficaram no padrao. Grade de 16 configuracoes ({ciclo, calendario} x ICMS {all, te_only, none, PR48} x
`bandeira_on_minimum`) = BUSCA nas mesmas faturas, relatada. Sem teste estatistico (contagem de faturas na faixa).

PORTAO (commit `0e971b4`, primaria): G1 energia P0 dentro de +-2% em >= 80% e COSIP estimada em [0, 30] R$; G2 total
P0 +-3% em >= 80%; G3 total P1 +-3% em >= 80%; G4 = G1-G3 na montagem `calendario`.

### Rodada do portao (`fatura.json`): NAO PASSA, por um defeito da biblioteca

| Montagem (padroes) | G1 energia P0 | COSIP | G2 total P0 | G3 total P1 |
|---|---|---|---|---|
| ciclo (primaria) | 4/19 | -160,82 R$ (fora) | 3/19 | 0/85 |
| calendario (G4) | 6/19 | -164,04 R$ (fora) | 5/19 | 0/85 |

G1, G2, G3 e G4 **nao passam** (as 16 configuracoes tambem nao). Causa achada depois: a base de tarifas da ANEEL
gerada em 16/10/2026 traz **cada registro duas vezes** (8.844 registros, 4.422 unicos; mesmo conteudo, `_id`
diferente), o `io.aneel.fetch_tariffs` mantem os dois e o `TariffBook` SOMA linhas de mesma chave (feito para as
linhas so-TUSD e so-TE): TUSD e TE dobram (B1 convencional 2017/18: 382,48 + 498,64 contra 191,24 + 249,32 do legado).
Hoje, qualquer `TariffBook.from_aneel` da contas ~2x. Defeito relatado, com reproducao, para o `library-builder`.

### Diagnostico pos-hoc sem as duplicatas (`fatura_sem_duplicatas.json`): continua NAO PASSANDO

Registros iguais fora o `_id` retirados no download; o livro fica IGUAL aos CSV do legado (21 vigencias B1
convencional, diferenca 0,0). Mesmo portao, mesmo metodo (nao muda o veredito acima: e diagnostico).

| Montagem (padroes) | G1 energia P0 | COSIP | G2 total P0 | G3 total P1 | P1 mediana do erro | D3: P1 com COSIP por ano |
|---|---|---|---|---|---|---|
| ciclo (primaria) | 5/19 | 9,38 R$ | 9/19 | 0/85 | -21% | 18/85 |
| calendario | 7/19 | 10,24 R$ | 15/19 | 0/85 | -21% | 19/85 |

- **P0 (sem geracao): perto, mas fora do +-2%.** Erro da energia: mediana -0,5% (ciclo) / -0,2% (calendario), todas
  as 19 dentro de +-10%, 17/19 (ciclo) e 19/19 (calendario) dentro de +-5%. Padrao sazonal: a biblioteca fica 2-5%
  abaixo nos meses de consumo alto e 2-5% acima nos de consumo baixo; reta pago = a x conta + b: a = 1,144 e b =
  -16,6 R$ (ciclo). Algo cresce com o consumo alem do modelo (COSIP por faixa de consumo? aliquota efetiva?); a
  planilha nao separa. O PIS/COFINS "implicito" de 17% nao e plausivel: nao e so a aliquota. O `calendario` sai
  melhor que o `ciclo` em P0, sem explicacao testada.
- **P1 (com geracao): a biblioteca fica ~21% abaixo do pago** (mediana; 3/85 dentro de +-5%). Na leitura padrao a
  conta e o minimo (50 kWh) + COSIP, constante; o pago cresce com o kWh compensavel (importado - 50). Conta POS-HOC
  feita a parte (nao esta no script): o residuo (pago - conta - COSIP) contra (importado - 50) tem inclinacao
  **0,21 R$/kWh** (08/2019-05/2022, r 0,99), **0,39** (08/2022-02/2024, r 0,90) e **0,27** (04/2024-08/2026, r 0,83).
  Uma cobranca POR kWh compensado, por cima do minimo, que nenhuma leitura da biblioteca produz: com o minimo
  limitando, "all" e "te_only" dao a mesma conta (o `te_only` compensa MAIS kWh, 284 contra 250 num mes de 300
  importados, e o imposto some em creditos) e o "none" so muda os meses em que a compensacao nao chega ao minimo.
  Isto e o segundo achado para a biblioteca: o imposto sobre a energia compensada entra no custo por kWh
  compensado `c`, que fica DENTRO do limite do custo de disponibilidade; numa fatura real o imposto e cobrado por cima.
  Hipotese, nao testada: ICMS (e talvez PIS/COFINS) sobre a TUSD (2019-2022) e sobre TUSD + TE (07/2022-12/2023, fim
  do teto de 48 meses do Convenio 16/2015 no PR) da energia compensada.
- D3 (COSIP por ano civil, deixa um fora) leva a mediana a ~0% mas so 18-19/85 ficam em +-3%: o erro e a variacao
  com o consumo, nao so o nivel. Fora da faixa (99 casos na primaria): 33 com bandeira mudando no ciclo, 25 de
  consumo alto, 10 com vigencia nova, 2 com ICMS mudando. 12/2022 sai +67% (a biblioteca acima do pago): o pago
  desse mes e o menor da serie (devolucao de credito na fatura? nao conferido).

**Decisao:** a biblioteca NAO reproduz as faturas da Copel. Dois defeitos para o `library-builder`: (1) duplicatas da
ANEEL dobram a tarifa (urgente: afeta todo `from_aneel` hoje); (2) imposto sobre energia compensada preso ao limite
do minimo. Sem eles, a energia sem geracao fica a ~+-5% (COSIP e aliquota efetiva desconhecidas impedem o +-2%).
Proximo piloto: com FATURAS DETALHADAS (PDF: linhas de energia, bandeira, ICMS, PIS/COFINS, COSIP, energia
compensada, datas de leitura) de alguns meses de cada periodo de ICMS, para separar COSIP, aliquotas e a regra do
imposto na compensada antes de mexer na biblioteca. Nao testado: tarifa branca, GD II, outras distribuidoras.
Tempos: rodada do portao 696 s, diagnostico 220 s (CPU; o download da ANEEL ~1 min cada).

### Rodada depois do conserto da biblioteca (16/10/2026, `fatura_pos_conserto.json`): mesmo veredito

Depois de `94559b7` (`io.aneel.search` guarda uma vez os registros repetidos com `_id` novo) e `814a6be`
(`from_aneel` aceita ICMS e PIS/COFINS por data), a rodada foi refeita com o caminho NORMAL da biblioteca
(`python piloto_fatura.py baixa pos-conserto` e `python piloto_fatura.py pos-conserto`: getter padrao, ICMS do PR
por data no proprio `from_aneel`; mesmo portao e metodo). O livro baixado bate com o legado (21 vigencias B1
convencional, dif 0,0) e as 16 configuracoes e os erros por fatura sao IGUAIS aos do diagnostico pos-hoc sem
duplicatas (conferido por igualdade dos JSON). Logo o defeito (1) esta consertado na biblioteca e o veredito nao
muda: **NAO PASSA** (G1 5/19, G2 9/19, G3 0/85 na primaria). O que falta e o defeito (2), o imposto sobre a energia
compensada preso ao limite do minimo, que so se separa com faturas detalhadas (PDF). Tempo 209 s.

## Composicao da mediana: os adaptadores da biblioteca chegam a mediana do benchmark? (16/10/2026, CPU) — G-A NAO PASSA, G-C PASSA

Pergunta (do usuario, 16/10): o `Ensemble-mediana` do benchmark e a mediana de TODOS os modelos de cada teste (47-48
no regime A, 21-22 em B e C); a biblioteca usa a mesma regra, mas por padrao so com as tres ingenuas, e o usuario
acrescenta os adaptadores que existem (LightGBM, Chronos-2, TiRex-2, Toto-2.0-313m, FlowState). Quanto vale a
mediana desses membros? Script `experimentos/testes_previsao/scripts/piloto_composicao_biblioteca.py` (portao no
commit `7c18680`, antes de qualquer conta); saida `resultados/pilotos/composicao_biblioteca.json`. Nada roda
modelo: medianas hora a hora das previsoes gravadas, avaliadas como o benchmark (teste de regressao). DM contra o
melhor de cada teste, sem Holm (pilotos). ~5 s.

Portao: G-A (K1 e K2 em separado): nos 3 testes A, skill >= Ensemble-mediana - 0,010 E DM vs o melhor p >= 0,05.
G-C (usinas C): a mediana das linhas de regime C que a biblioteca faz, idem.

| Composicao (regime A) | usinas | FV casas | consumo (corrigida) |
|---|---|---|---|
| K0 ingenuas (padrao de hoje) | +0,013 (29o) p 0,000 | +0,055 (36o) p 0,005 | +0,145 (33o) p 0,000 (+0,113) |
| K1 ingenuas + LightGBM | +0,076 (17o) p 0,000 | +0,114 (19o) p 0,045 | +0,192 (10o) p 0,000 (+0,175) |
| **K2 ingenuas + LightGBM + 4 fundacionais** | +0,124 (4o) **p 0,046** | +0,160 (4o) p 0,288 | +0,201 (5o) **p 0,025** (+0,199) |
| K3 LightGBM + 4 fundacionais | +0,131 (3o) p 0,135 | +0,170 (2o) p 0,529 | +0,199 (6o) p 0,004 (+0,201) |
| K4 4 fundacionais | +0,136 (3o) p 0,263 | +0,166 (3o) p 0,312 | +0,193 (10o) p 0,000 (+0,195) |
| Ensemble-mediana (47-48 modelos) | +0,128 | +0,164 | +0,194 |
| melhor do teste | Crossformer +0,150 | Toto-2.0-313m +0,178 | Ensemble-mediana-corrigida +0,209 |

Regime C (usinas): KC = mediana de {LightGBM, Chronos-2, TiRex-2, linear_fisico} = **+0,372, 1o de 24**, p 0,25 contra
o Ensemble-mediana C (+0,367, o melhor), a frente dele. **G-C PASSA.**

**Decisao.** G-A NAO PASSA para K1 nem para K2: com todos os adaptadores a mediana fica a 0,01 do Ensemble-mediana
nos tres testes A (K2 -0,004, -0,004, +0,007), mas nao empata com o melhor em dois (usinas p 0,046; consumo p 0,025
contra a mediana CORRIGIDA de 47 modelos). Conforme o portao: o `analyze` diz, numa nota, quando a saida e a mediana
so das ingenuas e o que o benchmark mediu ao acrescentar os cinco modelos. G-C PASSA: o `analyze` ganhou a linha
`median_weather` (mediana das linhas de regime C quando ha duas ou mais), com a nota de que e a linha a ler quando
ha previsao do tempo (teste em `tests/test_analysis.py`).

Observacao POS-HOC (hipotese, nao muda nada): nas duas series de geracao, tirar as ingenuas da mediana melhora (K3
passa nas usinas e na FV das casas; as ingenuas da geracao sao fracas, +0,013 e +0,055); no consumo nao (K3 p
0,004). Testar "mediana sem as ingenuas quando ha modelos" pede dado que nao serviu para escolhe-la (nao ha outro
caso no benchmark): fica registrada para quando houver um sitio novo.

## Parcela de cada canal (MPPT) para separar falha de string de sujeira (17/10/2026, CPU) — NAO PASSA

Script `experimentos/testes_previsao/scripts/piloto_mppt.py` (portao no commit `81b06bb`, antes de rodar); saida
`resultados/pilotos/mppt.json`. Dias claros pela energia CA total, parcela de cada MPPT na energia dos dias claros,
`diagnostics.changepoints` com os padroes. 1010 s.

- Curitiba (2 MPPT, 213 dias claros): achou 1 dos 3 eventos a +-45 dias: a volta de jul/2023 (2023-08-02, +19%).
  A falha da string 1 de dez/2022 NAO aparece no prazo (ha um degrau de -27,8% em 2023-03-02, tres meses depois) e a
  reconfiguracao de jun/2025 tambem nao. Outros degraus: 2022-04-15 +14,5%, 2024-05-29 +11%, 2025-03-21 +8,1%.
- Controle negativo (PVDAQ 1199, 7 inversores): so 8 dias claros na soma dos inversores (o controle NAO vale: G2
  "passa" sem informacao). Defeito menor do script: a lista "fora dos eventos" repete o degrau achado.

**Decisao:** G1 nao passa (1 de 3): a parcela por canal nao entra na biblioteca. Sujeira x sombra x falha de string
continua em aberto; o proximo passo seria olhar as tensoes CC por MPPT (a analise de 5 min viu a reconfiguracao
nelas), e um controle com mais dias claros.

## V11-piloto: o aplicativo aprende com o proprio erro? Replay causal nas duas usinas (portao 18/11/2026, ANTES de rodar)

Pergunta (secao 8 de `REVISAO_TESTES_2026-11-16.md`, versao piloto: 2 usinas, uma combinacao H/k): uma pessoa que
usa o aplicativo por N dias recebe previsoes melhores se o aplicativo guardar o que previu e ajustar os parametros
do SITIO com o erro observado, contra o aplicativo "congelado" de hoje (padroes do Parana)? Script
`experimentos/testes_previsao/scripts/piloto_uso_prolongado.py` (commit seguinte a este portao); saidas em
`resultados/pilotos/uso_prolongado*.{parquet,json}` (o parquet de previsoes por hora e de usina: fica fora do git,
como os outros `*__usinas__*`; o json so com metricas agregadas).

**Replay (nenhum dado do futuro).** Noite t (emissao no dia t-1, depois das 23:00): `outlook.forecast_ahead` da
biblioteca, `days=7`, sobre a serie ate 23:00 de t-1, com o tempo que existia: o dia D = t+k-1 usa o
`previous_day{k}` (lead k) de `dados/previsao_tempo_horizonte.parquet` (seis modelos, a convencao do piloto do
horizonte). Telhado: `diagnostics.roof_orientation` sobre os dados ANTES do primeiro dia de cada mes, passado como
`tilt/azimuth` (o app real reajusta a cada envio; mensal = o mesmo efeito, 30x mais barato). Tres chamadas por
noite, mesmas entradas: `trust=TRUST` (a saida CONGELADA, exatamente a do app), `trust=(1,)*7` (y_w = so o tempo)
e `trust=(0,)*7` (s = expectativa sazonal); como a previsao e s + a(y_w - s), as tres bastam para qualquer a.
Noites: alvos de 2024-03-07 a 2026-05-31 (o arquivo do tempo), ~810 por usina. Medido antes: ~0,9 s por chamada.

**Inicios e dias de uso.** Inicios S = 1o dia de cada dois meses de 2024-09-01 a 2025-11-01 (8 inicios); de cada S,
ate 365 dias de uso (cortados em 2026-05-31). Faixas de dias de uso: [1-30], [31-90], [91-180], [181-365].

**Variantes** (por usina, por inicio; o aprendizado da manha do dia t so usa pares (previsao, real) com alvo <= t-1):
- **F (congelada):** a saida de `trust=TRUST`, faixa da biblioteca (`low`/`high` do total do dia).
- **L (aprende so com o que ela mesma previu desde S)** e **LB (L + historico: no dia S o app reconstroi as previsoes
  dos 365 dias anteriores, como o `look_back`, e aprende com elas tambem).** Tres pecas, nesta ordem:
  1. a_k: por lead, minimos quadrados sem intercepto nas horas de sol dos ultimos 365 dias de pares,
     a_sitio = soma((y-s)(y_w-s)) / soma((y_w-s)^2); encolhido a = (n a_sitio + n0 TRUST_k)/(n + n0), n = dias
     com pares, cortado em [0, 1] (o teto 1 da biblioteca, decisao de 12/10).
  2. vies b_k: razao soma(y)/soma(y_hat com o a_k acima) dos totais diarios dos ultimos 90 dias do lead k,
     encolhida para 1 com o mesmo n0, cortada em [0,7; 1,3]. Previsao = b_k (s + a_k (y_w - s)).
  3. faixa de 80% do total do dia: a regra do `postprocessing.conformal_quantiles` aplicada ao total do dia de cada
     lead: escores r = (Y - Y_hat)/W dos ultimos 60 dias, W = largura da faixa F daquele dia; faixa =
     Y_hat + quantil_{0,1 e 0,9}(r) W. Com menos de 30 dias de pares: a faixa F transladada para o novo Y_hat.
  Ablacao relatada: so a_k; a_k + b_k.
- **n0** em {7, 15, 30, 60, 120, 240}, escolhido deixando a usina de fora: o n0 de Cascavel e o que maximiza o ganho
  medio de skill (leads 1-7, todas as faixas e inicios) em Curitiba, e vice-versa. Todos os n0 relatados.

**Metricas.** Skill do total do dia = 1 - RMSE/RMSE da expectativa sazonal s (a referencia do `SKILL`), por usina,
lead e faixa de dias de uso, juntando os inicios. DM (perda quadratica, HAC lag 7) sobre os dias de calendario:
diferenca de perda de cada dia = media entre os inicios que o cobrem naquela faixa. Cobertura da faixa de 80% do
total do dia. Relato: a_k e b_k aprendidos ao longo do tempo; skill por lead medido vs o `SKILL` padrao; por hora.

**Portao** (decidido separadamente para L e para LB, com o n0 da outra usina, previsao com a_k + b_k):
- **G1:** faixa [91-180], lead 1: skill(variante) - skill(F) >= +0,02 NAS DUAS usinas, DM p < 0,05 em cada uma.
- **G2:** faixa [1-30], todo lead 1-7: a variante nunca perde mais de 0,01 de skill para F em nenhuma usina.
- **G3:** faixas [31-90], [91-180] e [181-365]: cobertura de 80% da variante entre 0,75 e 0,85 nas duas usinas.
- Passa = G1 e G2 e G3. LB e o que o app faria de fato (ele ja tem o historico); L mede o aprender com o uso puro.

**Vies a declarar (contra o aprendizado):** o `TRUST` foi ajustado em 2024-03-07 -> 2025-07-31 DESTAS duas usinas e
o `SKILL` medido em 2025-08 -> 2026-05 delas: a congelada F esta dentro da amostra em todo o replay. O ganho medido
aqui SUBESTIMA o de um sitio novo; um PASSA e conservador, um NAO PASSA nao e conclusivo. Quem decide e o V11
completo (BR-PVGen, 51 usinas, e o periodo intocado 06-11/2026), no servidor.

**Consequencia.** Passa: o V11 completo vai para a fila do servidor e o banco local (secao 7) ganha as pecas que
passaram. Nao passa: registro aqui, padroes ficam, e a secao 7 e revista. Consumo (casas de Dingle: vies + faixa)
fica para um portao proprio, depois deste.

Emenda ANTES de rodar (18/11, commit do script): (1) a redacao do G3 acima foi corrigida (era "faixas >= [31-90]...
ate [181-365]"; o sentido e o mesmo). (2) Relato extra, FORA do portao, pedido pelo usuario para a demo: erro
percentual da energia (soma|real - previsto| / soma real) no total do dia, da semana e do mes, e a fracao de
dias/semanas/meses com erro <= 10%, F e variante, leads 1 e 7. A meta de 10% do usuario e lida nesses numeros;
nao decide nada aqui.

### Resultado (18/11/2026, CPU, ~16 min Cascavel + ~10 min Curitiba de replay; avaliacao ~1 min) — NAO PASSA

`resultados/pilotos/uso_prolongado.json`. 816 noites por usina, 3 chamadas do `forecast_ahead` por noite (~1,1 s
por noite em Cascavel, ~0,7 s em Curitiba, isto e ~0,2-0,4 s por chamada; o "0,9 s por chamada" do portao foi a
primeira chamada, fria). A congelada F e exatamente s + TRUST(y_w - s) da biblioteca (conferido pela revisao em
todas as 137.088 horas) e e COERENTE com o `SKILL` (lead 1: 0,44-0,51 por faixa; lead 7: 0,12-0,23 contra 0,199),
mas por construcao em parte: o `SKILL` foi medido em 2025-08 -> 2026-05 destas usinas, dentro do replay.

| Variante, usina (n0 da outra usina) | G1 lead 1, uso 91-180: ganho (p DM) | G2 | G3: celulas fora de [0,75; 0,85] (pior) |
|---|---|---|---|
| L, Cascavel (60) | -0,001 (0,95) | sim | 2 de 21 (lead 7 uso 31-90: 0,701) |
| L, Curitiba (240) | +0,003 (0,78) | sim | 8 de 21 (lead 5 uso 31-90: 0,731), quase todas leads 5-6 |
| LB, Cascavel (120) | +0,001 (0,26) | sim | 2 de 21 (lead 3 uso 181-365: 0,734) |
| LB, Curitiba (120) | +0,004 (0,91) | sim | 8 de 21 (lead 6 uso 31-90: 0,729) |

Leitura (corrigida depois da revisao do mesmo dia; a primeira versao exagerava 1 e 2):
1. **Nao ha o que aprender aqui no a_k e no vies:** o a_k aprendido fica no padrao (lead 1 0,98-1,00; lead 4
   0,88-0,95; lead 7 0,69-0,81, contra 1,00 / 0,92 / 0,79) e o b_k em 0,99-1,02. Esperado: o `TRUST` foi ajustado
   NESTAS usinas (o vies declarado no portao). O piloto nao diz se um sitio novo ganha.
2. **Aprender nao e "sempre inofensivo":** com o n0 escolhido na outra usina (60-240) os primeiros 30 dias nunca
   perdem mais de 0,01 (G2). Mas n0 pequeno perde (ganho medio dos leads 1-7: L Cascavel -0,009 com n0 = 7, -0,005
   com 15), e mais tarde no uso o lead 7 perde ate 0,012 (LB Curitiba, uso 91-180) e 0,008 (L Cascavel, 31-90).
   Ganho medio por n0, todas as variantes: -0,009 a +0,005.
3. **A faixa: a ideia ajuda nos leads longos, a conta do piloto nao calibra.** A faixa F e estreita no lead 7
   (cobertura 0,59-0,67 em Cascavel, 0,67-0,73 em Curitiba) e a conformal a alarga, mas a variante NUNCA passa de
   0,781 em nenhuma celula do G3 (abaixo de 80% em toda parte), e PIORA os leads 2-3, onde F ja cobria 0,77-0,83
   (Cascavel lead 3 uso 181-365: 0,819 -> 0,734/0,740). Causa achada pela revisao: `np.quantile` linear SEM a
   correcao de amostra finita (n+1) sobre so 30-60 escores diarios (a biblioteca usa ~700 escores por hora, onde o
   vies some). Sonda POS HOC da revisao (quantis conservadores de split conformal, niveis floor/ceil de a(n+1)/n):
   LB cobriria 0,79-0,84 (Cascavel) e 0,77-0,82 (Curitiba) em toda celula do G3. Nao muda este veredito (o G1 cai
   de qualquer forma); a correcao entra no portao do V11-b ANTES de rodar. Nota: a regra do piloto centra no
   ponto (Y_hat + q(r) W, r = (Y - Y_hat)/W); a `conformal_quantiles` desloca cada borda pelo proprio escore: nao
   e "a mesma regra", como o portao dizia.
4. **Erro percentual (pedido da demo; LB, lead 1, uso 91-365; F entre parenteses):** total do dia 13-16% (13-16%),
   ~50% dos dias dentro de 10% em Cascavel, ~43% em Curitiba; semana 5,6-8,8% (6-9%), 70-82% das semanas dentro de
   10%; mes 3,4-5,9% (3,8-6,2%), 86-97% dos meses dentro de 10%. Lead 7: dia 21-26%, mes 5-7%. A meta de 10% vale
   para a semana e o mes, nao para o dia. Cuidado com o mes: os inicios se sobrepoem, entao os ~60 pares
   (inicio, mes completo) de cada usina sao so 17-18 meses de calendario distintos.

Consequencia (a do portao): os padroes ficam; o V11 completo (BR-PVGen + periodo intocado) continua sendo quem
decide para sitios novos, agora com a pergunta afiada: (a) a_k/vies num sitio que NAO escolheu o `TRUST`;
(b) a faixa conformal por sitio, com a correcao de amostra finita escrita no portao antes de rodar. A vitrine LOCAL (`scripts/vitrine_uso_prolongado.py`, pasta ignorada
`vitrine_local/`) mostra estes resultados com as curvas das usinas, so para a apresentacao.

## V6: CRPS e cobertura das faixas de todo modelo que as entrega, sem e com conformal (16/11/2026, CPU) — PORTÃO (resultado: PASSA, ver "Resultados da fila do servidor de 18/11/2026")

**Pergunta.** O benchmark (`05_avalia.py`) avalia só o ponto. As faixas existem em 17 arquivos
`resultados/pilotos/*-quantis__*.parquet` (as 260 previsões de `resultados/previsoes/` guardam só `yhat`): LightGBM,
Chronos-2, TimesFM-3 e FlowState (14 combinações, as do piloto F2(c') `piloto_conformal.py`) e BuildingsBench S/M/L nas
casas (3 combinações, novas). A calibração conformal causal de 28 dias da biblioteca
(`postprocessing.conformal_quantiles`, forma "nivel_28d" do piloto) conserta a cobertura em todas?

**Método (`scripts/05c_faixas.py`, sem treino).** Reusa o `avalia` do `piloto_conformal.py`: mesmas horas avaliadas,
mesma referência dos 14 dias, mesmos escores (`prosumer.metrics.band_scores`: cobertura de 80% e 60%, largura, CRPS), só
nos dias em que a calibração já está ativa. Faixa bruta × calibrada, por combinação.

**Portão (fixado antes de rodar).**
- G1: a calibrada tem cobertura de 80% e de 60% dentro de ±5 pontos do nominal e skill de CRPS > 0 contra a
  referência (e, onde a bruta já era calibrada, CRPS não pior que 1%) em **>= 80% das 17 combinações** (13 de 17).
- G2: o número de combinações calibradas sobe (calibradas depois > calibradas antes).
- Relatado sem portão: as 3 combinações novas separadas (BuildingsBench), cobertura e CRPS por modelo.
- PASSA = G1 e G2.

**Cuidado declarado.** As 14 combinações já passaram pelo piloto F2(c') no MESMO período de teste; para elas esta
rodada reconfere e não é evidência independente. Só as 3 do BuildingsBench são combinações que não escolheram a forma.
O teste intocado das usinas é o V1 (01/06 a 15/11/2026), fora desta rodada.

**Saídas.** `resultados/pilotos/faixas_v6.json` e `faixas_v6.csv` (agregados; nada por hora de usina).

## C1: usinas e previsão do tempo estendidas até 15/11/2026 (servidor, 18/11/2026) — PORTÃO (antes de rodar)

**Pergunta.** Os exports novos de 5 min (01/01 → 15/11/2026) estendem `usinas_horario.parquet` sem mudar nada do que
já existe? Pré-requisito do V1, do V11-b, do P2 e do G1 no período novo.

**Método.** `scripts/01b_estende_usinas.py` (ambiente da biblioteca): energia horária com as regras do
`01_prepara_dados.py`; convenção do carimbo de 5 min (0, −5 ou +5 min) escolhida pela concordância com a série
existente em jan–mai/2026; geometria (`poa_ceu_claro`) de jun–nov copiada da mesma hora um ano antes; NASA POWER
baixada de novo (atraso de 0 ou 1 h por usina, o que reproduz a coluna existente); `poa_estimada` nova pela conversão do
regime C (céu claro × kc). Previous Runs baixada de novo até 15/11 em arquivos `_v1` (IFS/GFS lead 1, os 6 extras lead 1,
6 modelos leads 1–7). Nada publicado é sobrescrito.

**Portão.** (1) Na sobreposição jan–mai/2026, ≥ 99,5 % das horas de sol válidas nas duas séries batem ao Wh (|dif| <
0,5 Wh); senão o script para SEM gravar. (2) Relatados, sem portão: erro relativo da geometria copiada (esperado < 1 %),
correlação NASA nova × antiga (esperada > 0,99), cobertura da NASA nas horas novas, correlação do proxy da
`poa_estimada`, diferença máxima dos arquivos de tempo na sobreposição. Se a NASA cobrir < 95 % das horas de sol
novas, o regime B fica fora do V1 (é só o teto). Saída agregada: `resultados/pilotos/estende_usinas.json`.

## Fila do servidor de 18/11/2026: portões escritos ANTES de qualquer rodada

Todas rodam sem supervisão no servidor (cadeia Slurm em `experimentos/testes_previsao/vm/slurm/fila_18nov.sh`); o
clone do servidor não é ligado ao GitHub: o registro abaixo é completado lá, commitado no ramo local `vm/2026-11`, e o
usuário leva o ramo e os agregados à máquina de CPU. Saídas por hora das usinas ficam em caminhos ignorados.
Escolhas congeladas comuns: nada é reajustado no período intocado 01/06 → 15/11/2026; as configurações abaixo são as
únicas rodadas (sem busca de hiperparâmetros no teste).

### V11-b: faixa conformal por sítio no período intocado (C2)

**Pergunta.** A faixa de 80 % do total do dia, recalibrada por sítio com os resíduos que o banco já tinha, cobre
~80 % num período que não serviu para escolher nada? (No V11-piloto a faixa de hoje cobriu 0,59–0,73 no lead 7 e a
conformal sem correção de amostra finita ficou abaixo.) **Método.** `scripts/piloto_v11b.py`: replay causal do app de
hoje (padrões, nada reajustado) de 25/03 a 15/11/2026 com os dados do C1; regra da faixa no cabeçalho do script:
resíduos escalados r = (Y − F)/(hi − lo) dos 60 dias anteriores à emissão (só pares com alvo ≤ noite da emissão),
n ≥ 30, níveis conservadores de amostra finita (ordem ⌊0,1(n+1)⌋ e ⌈0,9(n+1)⌉), **cada borda anda a partir da
previsão pontual** (não centrada). **Portão.** Nas duas usinas: cobertura de todos os leads juntos em [0,77; 0,83] E
cada lead 1–7 em [0,70; 0,90] (≈ 168 dias por lead: ±0,03 de erro de amostragem). Relatados: cobertura da faixa de
hoje, largura relativa, skill do app contra a expectativa sazonal por lead, erro percentual dia/semana/mês e fração
dentro de 10 % (leads 1 e 7). **Se passar:** a faixa conformal por sítio entra no `outlook` (biblioteca, com testes)
como faixa padrão quando o banco tiver ≥ 30 pares; senão fica a de hoje e o achado é registrado.

### G1 / P1-gpu: fundacionais com as 6 NWP como covariáveis, leads 1–7

**Pergunta.** Chronos-2 ou TabPFN-TS, recebendo a POA de cada uma das 6 NWP (+ média, espalhamento e céu claro),
batem a cadeia física do app no total do dia? **Método.** `scripts/piloto_p1_gpu.py` (cabeçalho): uma previsão de
168 h por noite; o dia e+k usa o `previous_day{k}`; passado com o lead 1; referência física = replay do app de hoje
nas mesmas noites; comparação também com o `LightGBM-C-multi6` do F2(a) no lead 1. Período de DECISÃO: o teste do
benchmark (01/08/2025 → 31/05/2026). **Portão.** Lead 1, nas duas usinas: skill diário (contra a expectativa sazonal
do app) do modelo − skill do físico ≥ +0,02 E DM p < 0,05 (perda quadrática diária, HAC lag 7). Relatados: leads 2–7,
skill horário, tempo de inferência por sítio na CPU (regra de velocidade: só entra na biblioteca como opção). O
período intocado (01/06 → 15/11/2026) é lido SÓ como confirmação do modelo que passar; não muda a decisão.

### V1: teste intocado das usinas (C3 + G4)

**Pergunta.** O ranking e as escolhas da v2 valem num período que não serviu para escolher nada? **Método.** O
benchmark inteiro com `BENCH_TESTE=v1 BENCH_SAIDA=resultados_v1` (`comum.py`): teste 01/06 → 15/11/2026, dobras de 61
dias, dados do C1, regimes A, C e C-gfs (o B fica fora: a NASA cobre só 55 % das horas de sol novas; portão do C1).
Modelos: os do pipeline (`02_referencias`, `02b_classicos` sem AutoARIMA, `03_fundacionais`, `03b_moirai`,
`03c_fundacionais_lote2`, `04_redes_treinadas` na GPU), `07_ensemble`, `05_avalia`. Os modelos que entraram na v2 por
pilotos (TimesFM-3, Crossformer, DUET etc.) não são refeitos aqui (declarado). **Portão** (`confere_servidor.py v1`):
o `Ensemble-mediana` é o melhor ou empata com ele (DM + Holm) nos regimes A e C; o LightGBM C ganha do A. Relatados:
Spearman do skill v1 × v2 por regime, skill de cada modelo nos dois períodos. **Se falhar:** a mediana como padrão da
biblioteca é revista com os dois períodos lado a lado (decisão do usuário).

### V5 / G2: regime C6 (a média das 6 NWP) em todo modelo que aceita clima

**Pergunta.** O ganho do F2(a) (várias NWP no LightGBM) vale para os outros modelos? **Método.** `BENCH_C6=1
BENCH_SAIDA=resultados_v5`: regime novo C6 = as 4 colunas de clima do C com o GHI e a temperatura = média hora a hora
das 6 NWP do `LightGBM-C-multi6` (IFS, GFS, ICON, Météo-France, GEM, CMA; o AIFS fica de fora porque só existe desde
18/02/2025 e mudaria os membros no meio do treino). Mesmo teste do benchmark. Modelos com clima: LightGBM, linear
físico (`02`), Chronos-2, TimesFM-2.5 (`03`), TiRex-2, TabPFN-TS (`03c`), redes com clima (`04`, GPU). As previsões
de C e A da v2 são copiadas para a pasta para o `05_avalia` comparar C6 × C (DM entre regimes). **Portão**
(`confere_servidor.py v5`): C6 − C ≥ +0,02 de skill horário com DM p < 0,05 em ≥ metade dos modelos. **Se passar:** o
regime C publicado ganha a média das NWP (a biblioteca já usa a mediana das NWP no `outlook`); senão fica registrado
que o ganho do F2(a) é do LightGBM com as NWP separadas.

### V7 / G3: ajuste fino do Chronos-2

**Pergunta.** Ajustar o Chronos-2 por caso, com origem móvel, ganha do zero-shot? **Método.**
`scripts/piloto_v7_ajuste_fino.py`: configuração única (ajuste completo, lr 1e-5, 500 passos, lote 64, contexto 1024),
refeito no início de cada dobra com os dados anteriores; casos usinas A, usinas C, casas_prod A, casas_cons A. TiRex-2 e
Toto-2.0 ficam de fora: os pacotes instalados (`tirex2` 0.3.1, `toto2` 2.0.0) não têm código de treino. **Portão**
(`confere_servidor.py v7`): +0,02 de skill sobre o zero-shot em ≥ 2 dos 4 casos. **Se passar:** a biblioteca
continua zero-shot por padrão (regra de velocidade), com o ajuste como opção documentada.

### V4 / G5: casas no ano todo

**Pergunta.** O ranking e a mediana mudam com a estação? **Método.** `BENCH_TESTE=v4 BENCH_SAIDA=resultados_v4`: teste
01/04 → 31/12/2020, dobras de 31 dias, regimes A e B, todos os modelos do pipeline (como no V1). **Portão**
(`confere_servidor.py v4`): por estação (abr–jun, jul–set, out–dez; média do skill das dobras), o ensemble padrão
(`Ensemble-mediana` na produção, `Ensemble-mediana-corrigida` no consumo) fica no quartil de cima dos modelos em
todas as estações. Relatados: Spearman entre estações, melhor modelo por estação. **Se falhar:** o padrão da biblioteca
para casas ganha uma nota sazonal e a escolha é revista.

### V3 / G6: benchmark inteiro com 3 sementes num ambiente só

**Pergunta.** O ranking e os empates da v2 sobrevivem a um ambiente só e à variação de semente? **Método.** Uma
pasta por semente (`BENCH_SAIDA=resultados_v3_s{42,43,44}`, `SEMENTE`): as redes treinadas (`04`, GPU) por semente;
LightGBM/referências/clássicos/fundacionais zero-shot (determinísticos) uma vez em `resultados_v3_base` e copiados;
`07` + `05` por semente. **Portão** (`confere_servidor.py v3`): em ≥ 90 % dos modelos comuns, o status "empatado com o
melhor" é o mesmo da v2 nas três sementes E |skill v2 − média das sementes| ≤ max(faixa das sementes, 0,01). Nada
decidido sobre publicar a v3 (decisão aberta do usuário, seção 6 da revisão).

### V9 / G7: Time-LLM com LLaMA-7B (configuração do artigo)

**Pergunta.** Com o LLM do artigo o Time-LLM ainda perde para a própria ablação sem LLM (como com GPT-2 e em Tan et
al. 2024)? **Método.** `scripts/piloto_timellm.py llama7b` e `llama7b semLLM` (mesmo protocolo do piloto de 10/10,
casas_cons A; `huggyllama/llama-7b` congelado, token de leitura do HuggingFace fora do repositório). **Portão** (o do
piloto de 10/10): grupo da frente no consumo E o LLM ganha da própria ablação. Baixa prioridade: fecha a evidência,
não muda a biblioteca.

### P2 / C4: leads 8–15 com abr–nov/2026 de rodadas únicas

**Pergunta.** Com ~7,5 meses (eram 2) os leads 8–10 têm habilidade? **Método.** `scripts/piloto_p2.py`: rodada das
12 UTC de cada dia (IFS e GFS, Single Runs) de 28/03 a 14/11/2026; `outlook.forecast_ahead(days=15)` com confiança 1
(W) e 0 (S, a expectativa sazonal); telhado causal por mês. **Portão.** Um lead k ∈ {8, 9, 10} ganha peso no `TRUST`
só se, nas duas usinas, n ≥ 150 dias, skill de W contra S > 0 e DM p < 0,05; senão a linha plana depois do dia 7 fica,
agora com evidência. O a_k ótimo é só relato (não vira padrão sem um sítio que não o escolheu).

### C9: posição das usinas do BR-PVGen pelos próprios dados

**Pergunta.** Dá para estimar latitude e longitude de uma usina só pela forma da curva medida em dias claros?
**Método.** `scripts/piloto_c9_posicao.py` (cabeçalho): ajuste da forma da curva de céu claro (posição do sol + plano)
nos dias claros; validação em sistemas de posição conhecida, nunca usados para ajustar nada: os 6 do PVDAQ (potência
AC, plano ajustado junto) e as duas usinas (só relato, passo de 1 h). Conferido antes só em curvas SINTÉTICAS (erro
< 0,05°), não nos dados de validação. **Portão.** Nos sistemas do PVDAQ com passo ≤ 5 min (50, 1200, 1201): |erro|
≤ 0,5° na latitude E na longitude em ≥ 2 dos 3. **Se passar:** as posições do BR-PVGen (GHI medido da estação, plano
horizontal) são gravadas com a incerteza = o maior erro da validação e destravam o tempo no sítio (P5 e V11 no BR-PVGen,
em portões próprios depois); senão P5/V11 no BR-PVGen continuam bloqueados.

### P4 / C6: conversão tempo → kWh nas 21 usinas fixas do BR-PVGen

**Pergunta.** Onde está o erro de conversão que deixa o teto do regime B em ~+0,51? **Método.**
`scripts/piloto_p4_conversao.py` (ambiente `p4` = biblioteca + pvlib): metade dos dias para ajustar, metade para
avaliar; (a) GHI medido → POA: isotrópica da biblioteca × Hay-Davies × Perez (plano ajustado por modelo na metade de
ajuste); (b) POA medida → potência: linear × derating de temperatura (Ross, com a temperatura do ar, o que o app teria
da previsão; painel medido só diagnóstico). Posição: a do C9 se passou, senão o centro do estado (declarado).
**Portão.** (a) Perez com RMSE da POA ≥ 5 % menor que a isotrópica em ≥ 2/3 das usinas → a biblioteca ganha Perez
(com testes); (b) derating de Ross com RMSE da potência ≥ 2 % menor em ≥ 2/3 → a biblioteca ganha o derating. Usinas
bifaciais de 1–5 MW no chão, não telhados: o resultado vale para a física, não para a escala (declarado).

## Resultados da fila do servidor de 18/11/2026 (rodadas 18-20/11, registro de 23/11/2026)

Cada veredito abaixo e o do portao escrito antes (secoes acima e V6). Agregados em `resultados/pilotos/*.json|csv` e
`resultados_v{1,3_s42,3_s43,3_s44,4,5,7}/` (metricas e DM; as previsoes ficam fora do git). Log das rodadas:
`~/Projeto_IA/STATUS.md` do servidor. Numeros conferidos contra os JSONs em 23/11.

| Rodada | Veredito | Numeros que decidem |
|---|---|---|
| C1 estende usinas | PASSA | 100 % das horas batem ao Wh na sobreposicao; 4032 horas novas por usina; NASA cobre 55 % das horas de sol novas (B fora do V1) |
| V0 suite da biblioteca (17/11) | ok | 712 passam, 2 falham = `test_clear_sky_is_bit_identical` por 1 ulp (ambiente, ja conhecido) |
| V0 paridade completa (job 996) | ok | terminou com status 0 em 19/11; o resumo `logs/v0b_paridade.txt` ficou no servidor (nao conferido aqui) |
| V11-b faixa conformal por sitio | **PASSA** | cobertura todos os leads 0,819 (Cascavel) e 0,793 (Curitiba), hoje 0,691 e 0,637; por lead 0,771-0,841 (hoje no lead 7: 0,512 e 0,500); largura relativa a de hoje ~1,0 nos leads 1-3, 1,45-1,76 nos leads 5-7 |
| G1 / P1-gpu fundacionais + 6 NWP | NAO PASSA | lead 1, ganho sobre o fisico: Chronos-2 -0,107 / -0,126, TabPFN-TS -0,113 / -0,065 (Cascavel / Curitiba; DM p <= 0,03); pior em quase todo lead 1-7. LightGBM-6NWP +0,021 (p 0,25) / +0,004 (p 0,88) |
| V1 teste intocado | PASSA | Ensemble-mediana empatado com o melhor em A (melhor MLP) e C (melhor KAN); Spearman v1 x v2 0,94 (A) e 0,87 (C); LightGBM C - A = +0,25 |
| V5 regime C6 | PASSA (pelo portao; fraco, ver item 3 abaixo) | 18 de 23 modelos ganham >= +0,02 com p < 0,05 **sem correcao** (como o portao escreveu); com Holm sobre os 23 testes C6 x C so 5 de 23 (em `dm_regimes.csv`, p_holm < 0,05 so em Chronos-2, DeepAR, FEDformer, Ridge, TabPFN-TS); todos os 23 ganhos sao positivos (+0,013 a +0,048); nao ganham KAN, NBEATSx, NHITS, RandomForest, TiDE |
| V7 ajuste fino Chronos-2 | PASSA (3 de 4) | usinas A +0,066, usinas C +0,090, casas_cons A +0,029; casas_prod A **-0,062** |
| V4 casas no ano todo | NAO PASSA | so `casas_prod|B` falha: mediana em 2o, 1o e **7o de 23** (out-dez); Spearman entre estacoes 0,36-0,48 nesse caso (0,61-0,97 nos outros) |
| V3 3 sementes | PASSA | 250 linhas modelo x caso; status de empate igual ao da v2 em 92,4 %; skill dentro da tolerancia em 95,6 % |
| V6 faixas + conformal | **PASSA** (decisao do usuario, 23/11) | 13 de 17 combinacoes passam o item; calibradas 7 -> 16 (G2). Ver nota abaixo |
| V2 PVDAQ | NAO PASSA | G1 telhado: tilt certo em 1 de 6; G2 relogio: 2 de 6; G3 cadeia fisica: mediana 0,465 contra 0,718 em Cascavel |
| V2 telhado medido | NAO PASSA | H1: medido nao pior em 3 de 5 (precisava de todos); H2 passa (0,547 contra 0,558) |
| P4 conversao (21 usinas BR-PVGen) | NAO PASSA | Perez ganha em 7 de 21, Hay-Davies 7, Ross 4 (precisava de 14). Posicao pelo centro do estado (o C9 nao validou): fraco, nao conclusivo |
| V8 AutoARIMA memoria | ok | pico 41,8 GB (limite 56), ajuste ~1060 s, 61 janelas |
| C9 posicao BR-PVGen | NAO VALIDADO | a validacao quebrou (`IndexError` no `np.add.reduceat` com lista de dias vazia, `piloto_c9_posicao.py:120`); as posicoes gravadas erram nos dois sentidos, muitas absurdas (BA +31,9; MG ate +70,0; SP de -64,2 a +39,0; PR -9,5) e so 18 de 51 caem no estado: `c9_posicao_brpvgen.csv` NAO e valido, nao usar |
| P2 leads 8-15 | NAO RODOU | Open-Meteo Single Runs: `HTTP 400 No data is available for this location`; os 3 jobs seguintes falharam sem o arquivo |
| V9 Time-LLM LLaMA-7B | NAO RODOU | `mat1 and mat2 must have the same dtype (Half x Float)` em `piloto_timellm.py` |

Redes (G4, G5, G6) marcadas FALHOU no STATUS so porque Crossformer e Mamba quebram (`No module named 'models'`, caminho
do codigo dos autores); as outras redes rodaram (32 a 108 por job) e estao no V1, V3, V4 e V5. Crossformer e Mamba ja
estavam fora do V1 pelo portao (entraram na v2 por pilotos).

**Nota V6 (portao ambiguo, decidido 23/11).** O portao dizia ">= 80 % das 17 combinacoes (13 de 17)"; 13/17 = 76 %.
O `05c_faixas.py` aplicou 0,8 x 17 = 13,6 e deu NAO PASSA; o usuario decidiu pela contagem escrita (13 de 17), que foi o
numero fixado antes de rodar. Rejeitado: ler o 80 % literal (o parentese era a regra operacional). As 4 que falham:
as 3 novas (BuildingsBench S/M/L, as unicas independentes): a conformal conserta a cobertura (0,49-0,62 -> 0,80-0,81)
mas o CRPS fica muito pior que a referencia (skill -1,9 a -21,8: o modelo, nao a faixa); e TimesFM-3 casas_prod A
(cobertura de 60 % 0,653, CRPS 1,5 % pior). Leitura: a calibracao conformal conserta a cobertura onde a faixa bruta
estava descalibrada; nao salva um modelo ruim. Duas ressalvas (revisao de 23/11): no TimesFM-3 casas_prod A a faixa
bruta ja estava calibrada (cob80 0,789, cob60 0,576) e a conformal a tirou da tolerancia (cob60 0,653) e piorou o CRPS
(0,1371 -> 0,1392); e as 13 que passam sao todas combinacoes ja escolhidas no mesmo periodo (F2(c')), enquanto as 3
independentes falham: o V6 nao traz evidencia independente de que a conformal melhora o CRPS.

**Achados que mudam a biblioteca (para a maquina de CPU):**
1. V11-b: a faixa conformal por sitio (regra do `piloto_v11b.py`: residuos escalados dos 60 dias, n >= 30, quantis de
   amostra finita, cada borda a partir do ponto) entra no `outlook` como faixa padrao quando o banco tiver >= 30
   pares, com testes. E o unico resultado desta fila que muda o que o app entrega.
2. V2/PVDAQ, contra a regra "nada sob medida": (a) `diagnostics.roof_orientation` superestima o tilt em 5 de 6
   sistemas dos EUA (ajustado 25-60 graus, verdade 10-45); (b) o relogio acertou com confianca em so 2 de 6. O padrao
   NAO e "falha onde ha horario de verao": o sistema 1433 (America/Denver, com horario de verao) passa (desvio 0,
   concordancia 0,537) e o controle Cascavel (sem horario de verao) falha (desvio -1 h, concordancia 0,19); o sistema
   1239 da desvios mensais de -11 h, sinal de erro de fuso no proprio piloto. PRIMEIRO passo: conferir a conversao de
   fuso do `piloto_pvdaq.py` (e por que Cascavel falha aqui e nao nos testes da biblioteca); so depois, se sobrar
   erro, testar o `quality.clock_offset` em dados com horario de verao (o Parana nao tem desde 2019).
3. V5: o regime C publicado ganharia a media das 6 NWP (consequencia do portao), MAS com cautela: os p do portao nao
   tem correcao (com Holm so 5 de 23 passam; corrigido de "6" na revisao de 25/11) e o periodo de teste e o mesmo que escolheu as varias NWP (F2(a)). Antes
   de republicar o regime C, conferir o C6 no periodo intocado do V1 (o V1 nao rodou C6).
4. V4: o padrao da biblioteca para producao das casas ganha nota sazonal; a escolha da mediana para `casas_prod` no
   regime B e revista.
5. V7: zero-shot continua padrao; ajuste fino vira opcao documentada, com o aviso de que perdeu em `casas_prod`.
6. V1 e V3: a mediana como padrao e o ranking da v2 confirmados fora da amostra e entre sementes (nada muda; publicar
   a v3 continua decisao do usuario).

**Negativos que fecham caminhos:** P1-gpu (fundacionais com NWP como covariaveis nao chegam perto da cadeia fisica:
a Prioridade 1 continua na cadeia fisica e no LightGBM com NWP separadas). O periodo intocado do P1-gpu foi calculado
pelo script e da o mesmo sinal (-0,06 a -0,16), mas pelo portao nao decide nada.

**A refazer (bugs de script, nao resultados):** C9 (dias vazios na validacao, e as latitudes absurdas), P2 (fonte das
rodadas unicas: conferir se a Single Runs guarda abr-nov/2026 ou trocar de fonte), V9 (dtype), Crossformer/Mamba
(caminho do `models`). P4 so tem sentido de novo com posicoes do C9 validadas.

## Rodadas de 25/11/2026 na maquina de CPU (versao 0.6.3 do README): C9 e P2 depois dos consertos

Os consertos estao no commit `d5ef1ad` (e descritos nos proprios scripts). Portoes: os de 18/11, sem mudanca.

### C9 (posicao pelos proprios dados): NAO PASSA

A validacao quebrava por um defeito do script (indices desalinhados: toda a serie virava NaN). Consertado, e com uma
mudanca de metodo declarada ANTES de qualquer posicao de VALIDACAO calculada (as do BR-PVGen de 18/11 ja existiam e seguem invalidas; lisura do dia claro medida em medias de 15 min nos
passos mais finos; em 1 min o ruido sozinho reprovava todo dia), rodou nos 6 sistemas do PVDAQ (passo nativo) e nas
duas usinas (`resultados/pilotos/c9_posicao.json`).
Evidencia da mudanca (sonda de 25/11 com o criterio antigo no passo nativo, so contagem de dias, nenhuma posicao):
razao soma|variacoes| / (2 x maximo) mediana 6,46 no PVDAQ 50 (1 min; 0 de 365 dias lisos), 3,92 no 1200 e 3,87 no
1201 (5 min; 31 e 25 dias lisos). A mudanca vale tambem para os dois de 5 min, que com o criterio antigo teriam ~30
dias claros antes do filtro de maximo; o portao nao passaria de qualquer modo (erros de 6 a 15 graus).

| Sistema | passo | dias claros | erro lat | erro lon | plano ajustado |
|---|---|---|---|---|---|
| PVDAQ 50 | 1 min | 80 | +1,9 | +4,0 | 46 / 174 |
| PVDAQ 1200 | 5 min | 44 | +12,2 | +6,3 | 60 / 203 |
| PVDAQ 1201 | 5 min | 41 | +8,8 | +14,7 | 24 / 254 |
| PVDAQ 1239 | 15 min | 4 | +12,1 | -15,4 | 13 / 47 |
| PVDAQ 34 | 15 min | 65 | -7,8 | -0,4 | 11 / 350 |
| PVDAQ 1433 | 15 min | 22 | +3,3 | -3,8 | 3 / 0 |
| Cascavel | 1 h | 80 | -0,0 | -13,0 | 24 / 73 |
| Curitiba | 1 h | 80 | -28,6 | -4,1 | 60 / 360 |

Portao (|erro| <= 0,5 grau em lat E lon em >= 2 dos 3 sistemas de passo <= 5 min): **0 de 3. NAO PASSA.** Leitura:
com a curva normalizada pelo maximo do dia, o plano e a posicao se confundem (um telhado virado para leste adianta a
curva como uma longitude mais a leste: Cascavel saiu virada a 73 graus e 13 graus a oeste; a inclinacao troca com a
latitude). O metodo so foi conferido em curvas sinteticas (onde o plano era conhecido). Consequencia, como escrito
no portao: as posicoes do BR-PVGen NAO sao calculadas; P5 e V11 no BR-PVGen continuam bloqueados (o PVDAQ residencial
do C10, com coordenadas, e o caminho). `c9_posicao_brpvgen.csv` (de 18/11) continua invalido.

Achado lateral (para a versao 0.7.1, relogio fora do Parana): os carimbos brutos do PVDAQ 1200, 1201 e 34 seguem o
horario de verao (o centro da producao pula +1 h de marco a outubro); 1239 e 1433 tem relogio irregular (1433 deriva
+-2 h no meio do ano).

### P2 (leads 8-15 com rodadas unicas): PASSA no lead 8, NAO nos leads 9 e 10

Consertado (a Single Runs ja nao guarda as rodadas antes de ~30/05/2026 e responde 400 "No data is available"; as
rodadas 02/04-30/05 do piloto do horizonte entraram como estavam), rodou na maquina de CPU em 25/11: 227 noites de
02/04 a 14/11/2026 por usina (o portao pedia desde 28/03: 5 dias perdidos, e 1 rodada de 10/06 faltando em Cascavel;
`p2_download.json`), `forecast_ahead(days=15)` com confianca 1 (W) e 0 (S). Saidas: `p2.json` (agregados),
`dados/previsao_tempo_rodadas_v1.parquet` (publico), `p2__usinas__*.parquet` (privado, fora do git).

| lead | Cascavel n / skill W / p DM / a otimo | Curitiba n / skill W / p DM / a otimo |
|---|---|---|
| 7 | 213 / +0,248 / 0,0001 / 0,78 | 218 / +0,141 / 0,008 / 0,68 |
| **8** | 212 / **+0,188** / **0,0008** / 0,72 | 217 / **+0,136** / **0,021** / 0,68 |
| 9 | 211 / +0,113 / 0,064 / 0,65 | 216 / +0,073 / 0,20 / 0,60 |
| 10 | 210 / +0,061 / 0,31 / 0,58 | 215 / +0,011 / 0,87 / 0,51 |
| 13 | 208 / -0,037 / 0,49 / 0,44 | 213 / -0,144 / 0,011 / 0,30 |
| 15 | 206 / -0,161 / 0,020 / 0,33 | 211 / -0,298 / <0,001 / 0,25 |

**Portao: o lead 8 passa nas duas usinas (n >= 150, skill > 0, p < 0,05); 9 e 10 nao.** Com 2 meses (12/10) nenhum
lead passava: a linha plana a partir do dia 8 nao tem mais evidencia, so a partir do dia 9. O portao nao diz QUAL peso
o lead 8 ganha (o a otimo, 0,72 e 0,68, e so relato: nao vira padrao sem um sitio que nao o escolheu) -> decisao do
usuario, versao 0.8.0 do README; o `TRUST` da biblioteca segue com 7 valores ate la. Leitura lateral: os a otimos dos
leads 4-7 neste periodo (0,92/0,89, 0,86/0,84, 0,81/0,78, 0,78/0,68) ficam perto do `TRUST` atual (0,92, 0,91, 0,86,
0,79), medido em outro periodo: o `TRUST` se sustenta, salvo Curitiba no lead 7. No dia 15 (e no 13 em Curitiba) o tempo
piora a previsao com p < 0,05.
