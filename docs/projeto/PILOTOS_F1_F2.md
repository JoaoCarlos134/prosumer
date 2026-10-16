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
| FlowState (Lactec, 16/10) | consumo A | 0,537 | 0,389 | +0,052 | estreita |
| FlowState (Lactec, 16/10) | FV casas A | 0,607 | 0,466 | +0,128 | estreita |
| FlowState (Lactec, 16/10) | usinas A | 0,612 | 0,456 | +0,069 | estreita |

Referência: quantis do mesmo horário nos 14 dias anteriores. FlowState rodado no Lactec em 16/10 (CPU, 4-12 min por
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

**FlowState (acrescentado em 16/10, Lactec; as 11 fontes acima saíram idênticas na nova rodada):** as seis formas
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

## E6: a conta da `economics.brazil` contra as faturas reais da Copel (16/10/2026, Lactec, CPU) — NAO PASSA

Pergunta: com a tarifa convencional da Copel (`COPEL-DIS`, ANEEL), bandeiras, custo de disponibilidade, SCEE / GD I
(usina de Cascavel, 07/2019) e ICMS + PIS/COFINS, o `brazil.Setup(...).bill` reproduz o total pago mes a mes? Script
`experimentos/testes_previsao/scripts/piloto_fatura.py`; saidas `resultados/pilotos/fatura.json` (rodada do portao) e
`fatura_sem_duplicatas.json` (diagnostico pos-hoc); livro da ANEEL em `dados/aneel_*.csv` (ODbL 1.0, atribuicao
ANEEL; base derivada redistribuida fica sob ODbL). Dados: planilha feita a mao pelo dono com o resumo das faturas
(so no Lactec, nunca copiada): por mes de referencia, kWh importado, kWh injetado, total pago e saldo; NAO tem
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
