# Revisão geral do plano (E0–E7), 11/10/2026

Visão de cima: onde está cada etapa, o que melhorou desde o plano de 09/10, o que pode melhorar. Base: o grafo do
graphify (`graphify-out/`, código reextraído hoje por AST: 1.736 nós, 3.718 ligações, 93 comunidades; os 19
documentos alterados desde 07/10 ainda estão com a extração de 07/10 — rodar `/graphify . --update` para refazê-los),
o `Plano_TCC_simples.tex`, o `CLAUDE.md`, o `ESTUDO_ETAPA_A.md` e o `PILOTOS_F1_F2.md`.

## O que o grafo mostra

1. **Biblioteca e benchmark ainda são duas ilhas.** Não há nenhuma ligação direta entre os nós de `src/prosumer`
   (104 nós, 6 módulos, 379 linhas de código) e os scripts do benchmark (294 nós); o benchmark só chama a biblioteca
   em 3 lugares, e só as métricas (`05b_resolucao`, `piloto_comum`, o teste de regressão; o `07` usa o
   `correct_bias`). O nó de código mais ligado do projeto é `comum.carrega()` (46 ligações), seguido de
   `comum.dobras()` (30): o protocolo de fato vive no `comum.py`, não no `prosumer.protocol.DayAhead`, que já tem
   dobras e janelas. Hoje são duas implementações do mesmo protocolo.
2. **A física do sol está em quatro lugares**: `legado/.../solar.py`, `comum.ghi_ceu_claro`, `prosumer.data._clear_sky`
   (privada) e `piloto_geometria.geometria_solar` (nova, com vetor do sol e POA). É exatamente o módulo `physics`
   que a E2 pede.
3. **O legado é a maior comunidade sem dono na biblioteca**: diagnóstico das usinas (`a2_fault`, `a3_shading`, …,
   55 nós), tarifas (`aplica_tarifas`), relatórios de 5 min. São as fontes da E4 (diagnóstico) e da E6 (economia),
   mas dependem dos dados brutos de 5 min, que só existem no Lactec.
4. **Os 20 pilotos repetem infraestrutura**: cada `piloto_*.py` novo de F2 (meio-dia, total do dia, multi-NWP,
   geometria) recalcula skill e DM à mão; há duas guardas de memória diferentes (psutil no Time-LLM, API do
   Windows no AutoARIMA). O `piloto_comum` só cobre o caso "uma previsão horária contra o benchmark".
5. **Os documentos derivam**: os nós de documento ainda falam em "36 modelos, 131 linhas" e
   `prossumidor.diagnostico` (nomes antigos); o `Plano_TCC_simples.tex` diz 248 resultados e 321 testes (hoje: 260
   linhas, 57 modelos, 313 testes rodáveis aqui). O `CLAUDE.md` virou um diário (~450 linhas) que mistura regras,
   estado e histórico.

## Etapa por etapa

| Etapa | Plano | Onde está (11/10) | Situação |
|---|---|---|---|
| F0 Decisões | out | idioma decidido; licença, permissão por escrito do professor e compra do Pi 5 + ESP32 em aberto | parcial |
| F1 Fechar o teste | out | a–c feitos; e, f decididos (MLP instável, TimesFM-3 e BuildingsBench não passam, FlowState entrou); **d (AutoARIMA) sem como rodar aqui** | quase |
| A Modelos pendentes | nov–dez | **12 de 13 decididos um mês e meio antes**: entraram VisionTS++, CycleNet, Crossformer, Mamba; falta só o TimeGPT (decisão do autor) | quase |
| F2 Pilotos | out–nov | passaram (a) várias NWP, (c) faixas no regime A, (d) meio-dia; não passaram (b) geometria, (e) ajuste fino do TTM, (f) total do dia; FlowState nas faixas no Lactec | quase |
| F2b Levar para a biblioteca | — | não começou | — |
| E1 Base | feito | pacote, contratos, dados sintéticos, CI, teste de regressão | feito |
| E2 Versão 0.1 | nov–jan | nomes em inglês, métricas em resoluções, correção de viés, `DayAhead`; **no mesmo dia:** protocolo completo (janelas com preenchimento causal e covariáveis, normalização só com o treino, máscara de horas) | ~35% |
| E3 Checagem 1 | fev | **no mesmo dia:** o benchmark já usa o protocolo da biblioteca, com igualdade exata contra a v2 congelada | ~30% |
| E4 Versão 0.2 | fev–abr | TFLite conferidos (legado); candidatos pequenos medidos no benchmark | 0% |
| E5 Hardware | mai | sem o hardware | 0% |
| E6 Versão 0.3 | jun–jul | tarifas só no legado; licença não escolhida | 0% |
| App (o TCC) | ago–out | — | 0% |
| E7 Escrita | contínuo | nenhum texto do TCC ainda (só proposta, plano, LEIA-ME e os registros) | 0% |

**O que melhorou desde o plano de 09/10:** o teste ficou mais forte (52 → 57 modelos, 243 → 260 linhas, com 4
modelos novos que lideram casos: o Crossformer é o 1º das usinas no regime A); 22 modelos ou variantes
estudados e decididos com evidência; a revisão dos scripts não achou vazamento (5 pontos a declarar); três
melhorias de método passaram nos pilotos e já indicam funções da biblioteca; e três resultados negativos firmes
para o texto (o LLM piora o Time-LLM; ajuste fino do TTM piora; correção de viés na geração piora).

## O que pode melhorar, por etapa

**F0.** Pedir já a permissão por escrito do professor (é o que destrava publicar dados e o artigo das usinas) e
comprar o Pi 5 + ESP32 agora: a E5 é em maio, mas a E4 (modelos para aparelho) já precisa medir neles.

**F1.** O AutoARIMA não roda mais nesta máquina: o Smart App Control passou a bloquear o `statsmodels` do
`classicos` em 11/10. Duas saídas: rodar o `piloto_autoarima_memoria.py` no Lactec, ou fechar o item como
"inviável em resolução horária" com o que já se mediu (15,2 h em usinas|A no padrão; >20 GB na configuração
reduzida com exógenas). Recomendo a segunda, citando as medições: o portão (< 2 h/caso) já falhou duas vezes.

**A.** Só falta o TimeGPT. Se for testar, só as casas (CC0) e com orçamento definido; se não, registrar como
"não testado: serviço pago que exige enviar os dados", que também é um resultado para a biblioteca (que não envia
dados por padrão).

**F2 → F2b, dentro da E2.** Os três que passaram mudam a interface, então devem entrar no desenho da E2, não
depois:
- várias NWP → `prosumer.io.open_meteo(models=[...])` com checagem de cobertura (o 08b já mostra que AIFS e UKMO
  começam tarde) e média/desvio entre modelos como atributos;
- meio-dia → `DayAhead(issue_hour=0)` com a hora de emissão como parâmetro (hoje fixa em 00:00 no protocolo);
- faixas → quantis como saída padrão (Chronos-2 Apache-2.0 ou LightGBM quantílico; TimesFM-3 não, pela licença)
  e um piloto de calibração conformal causal para o regime C (as duas fontes erram por < 1 ponto).
O total do dia não passou como melhoria, mas um LightGBM de 300 árvores empata com o Timer-XL de 84 M no total do
dia: anotar como candidato da E4 (previsão do dia no aparelho).

**E2.** O maior risco do plano é ela: é a etapa de 120 h e está em ~25%. Sugestões:
1. **Começar pelo protocolo, e fazer a E3 de forma contínua.** Trocar o miolo do `comum.py` (`carrega`, `dobras`,
   `janelas`, `normaliza_por_treino`, a máscara de horas do `05_avalia.real`) por chamadas à biblioteca, uma
   função por vez, cada uma com um teste de igualdade contra as previsões gravadas (como o multi-NWP e a
   geometria já fizeram, diferença 0,0). Ao fim, a E3 vira só "rodar tudo de novo", não um projeto de 30 h.
2. **`prosumer.physics`** juntando as quatro cópias da geometria solar (céu claro, posição e vetor do sol, POA,
   Erbs), com testes contra o legado.
3. **`ranking()` e `ties_with_best()`** sobre o DM + Holm que já existem em `metrics`.
4. **A chamada única do aplicativo** (`analyze(series) -> Report`) desenhada já agora, mesmo que vazia por dentro:
   ela define o que cada módulo precisa devolver.
5. **`piloto_comum.compara()`** genérico (previsões em qualquer resolução, par de DM declarado) antes do próximo
   piloto: os quatro de hoje recalcularam a avaliação à mão.

**E3.** Hoje o teste de regressão confere as métricas a partir das previsões gravadas; a E3 do plano é mais forte
(as previsões saem da biblioteca). Com a sugestão 1 da E2, ela anda junto.

**E4.** Diagnóstico depende dos dados de 5 min do Lactec: planejar uma ida ao Lactec para exportar uma amostra
anonimizada (ou rodar a E4 lá). Candidatos de aparelho já medidos no benchmark: SparseTSF (32 parâmetros),
CycleNet (4,3 mil), Ridge, LightGBM do total do dia, TTM, FlowState (9 M, Pi).

**E5.** Sem hardware não há etapa: ver F0.

**E6.** Licença antes da E6 (o plano já diz); as pendências de COSIP e PIS/COFINS do legado de tarifas continuam.

**App.** Escolher cedo entre Streamlit (SciKeywordMap) e FastAPI + pywebview (Loom) pesa pouco agora, mas a
escolha define como o relatório é devolvido (sugestão 4 da E2).

**E7.** Começar o capítulo de método agora, enquanto está fresco: protocolo v2, regimes, avaliação e a lista de
pontos a declarar já está escrita (três versões de torch; zeros nas redes do NeuralForecast; validação sorteada
das redes próprias; máscara da FV das casas; portão sem Holm; TiDE; normalização). É texto que o LEIA-ME v2, o
ESTUDO e o PILOTOS já têm quase pronto.

**Documentação.** Separar o `CLAUDE.md` em regras + estado curto (o que um começo de sessão precisa) e mover o
diário de 06–11/10 para `docs/projeto/HISTORICO.md`; atualizar os números do `Plano_TCC_simples.tex` e do
`LEIA-ME.md` do benchmark (57 modelos, 260 linhas).

**Ambiente.** O Smart App Control bloqueou, em 4 dias: torch 2.14 (GPU), pyarrow 26, mypy, hypothesis e agora o
statsmodels. É o gatilho do WSL2 anotado na memória ("adiar até o TTM/embarcado"): a E4 está chegando, e o
`classicos` já não roda. Recomendo instalar o WSL2 antes da E4.

## Modo teste (11/10)

`experimentos/testes_previsao/scripts/modo_teste.ps1`: sem argumentos só mostra; `-Aplicar` fecha uma lista
explícita de programas (Steam, Discord, Wallpaper Engine, Logitech/Gigabyte/HyperX, Xbox, Copilot, Ollama, OneDrive;
o Brave só com `-FecharNavegador`), troca para o plano "Alto desempenho" e, com `-Prioridade`, sobe os python para
AboveNormal; `-Restaurar` desfaz. Libera ~4,7 GB (~8 GB com o navegador). Nunca fecha VS Code, Claude Code,
terminal, Python nem processos do Windows. A fila da noite usa com `MODO_TESTE=1 bash fila_noite.sh`.
Sem overclock: muda números, aquece e o gargalo medido é memória, não clock. Subir a GPU de 200 W para 216 W é
dentro da especificação, mas pede administrador: `nvidia-smi -pl 216` (desfazer com `-pl 200`).
