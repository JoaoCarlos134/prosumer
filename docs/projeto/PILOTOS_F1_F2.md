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
| F2(b) geometria do telhado (FV casas B) | `piloto_geometria.py` | LightGBM com POA −0,031 (p 0,017); linear físico +0,020 (p 0,28); inclinação estimada no limite da grade (60°) em 8 de 10 casas | **não passa** |
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
dobras anteriores), a pilotar.

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
