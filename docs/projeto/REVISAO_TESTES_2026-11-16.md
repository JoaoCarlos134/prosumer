# Revisão de todos os testes e plano para a VM do Lactec (16/11/2026)

Revisão de tudo o que foi testado até hoje, com todos os dados disponíveis (públicos e privados), feita a partir
dos registros do repositório: `experimentos/testes_previsao/LEIA-ME.md` (benchmark v2), `PILOTOS_F1_F2.md`,
`ESTUDO_ETAPA_A.md`, `ESTUDO_EMBARCADO.md`, `HISTORICO.md` e `resultados/metricas.csv` (260 linhas, 57 modelos).
Nenhum número abaixo foi recalculado: são os gravados. A segunda parte é o plano de rodadas para a VM do Lactec
(servidor compartilhado com Slurm: 48 threads, 2 GPU de ~96 GB, 251 GB de RAM, mas na prática ~20 GB de RAM livres
enquanto outro usuário ocupar o resto; uma GPU livre).

## 1. Os dados

| Dado | Licença / acesso | Período | Onde já entrou |
|---|---|---|---|
| Usinas Cascavel (3,96 kWp) e Curitiba (~9,6 kWp), horário | **privado** (do professor) | 26/07/2019 → 31/05/2026 | benchmark A/B/C, horizonte, E4 diagnóstico, conformal |
| Exports de 5 min do Fronius (CA, MPPT, CC) | **privado**, só no Lactec | idem (as faturas vão até 08/2026) | análise ia_solar, piloto MPPT |
| Resumo das faturas Copel (104 faturas) | **privado**, só no Lactec | 01/2018 → 08/2026 | E6 (não passa) |
| 20 casas de Dingle (Khadem et al. 2024) | CC0 | 2020 inteiro, 1 min | benchmark A/B (só out–dez como teste) |
| Clima medido de Dingle | CC0 | 2020 | regime B das casas |
| Open-Meteo Previous Runs (IFS, GFS, ICON, Météo-France, GEM, CMA, AIFS, UKMO), leads 1–7 | não comercial | 2024 → 05/2026 | regime C, F2(a), horizonte |
| NASA POWER | público | toda a série | regime B das usinas |
| ANEEL tarifas e bandeiras | ODbL | 2017 → | E6, `economics.brazil` |
| NREL PVDAQ | CC BY 4.0 | até 2023 | só o controle do piloto MPPT (8 dias claros; não valeu) |
| Growatt de Tamil Nadu (Kaggle) | CC BY 4.0 | 03/2026 → | leitor de contadores (fixture) |

## 2. O que foi testado, e o veredito

| Bloco | O que mediu | Veredito |
|---|---|---|
| Benchmark v2 (57 modelos, 3 casos, regimes A/B/C) | previsão do dia seguinte, origem móvel, DM + Holm | feito; achados centrais: o clima decide nas usinas (A +0,14 → C +0,37 → B +0,51), mediana de todos robusta, fundacionais sem treino na frente |
| Etapa A (13 modelos pendentes) | estudo + piloto de cada | entram Crossformer, CycleNet, Mamba, VisionTS++; não passam Moirai 1.1, MOMENT, Lag-Llama, DUET, xLSTM, S-Mamba, TimeGrad, Time-LLM (GPT-2), LLMTime; **TimeGPT espera decisão** |
| F1 (fechar o teste) | AutoARIMA, MLP ajustado, TimesFM-3, BuildingsBench | **AutoARIMA nunca medido até o fim**; os outros não passam |
| F2 (melhorias) | várias NWP, geometria, faixas, meio-dia, total do dia, ajuste do TTM | passam: várias NWP (+0,373 no C), faixas + conformal, meio-dia; não passam: geometria das casas, total direto, ajuste fino do TTM |
| Horizonte 1–15 dias | geração e consumo | passa nos leads 1–7 (geração) e 1–14 (consumo); 8–15 com só ~2 meses de amostra |
| E4 diagnóstico com energia horária | eventos conhecidos das usinas | 4 de 5 (fator 3 escolhido nestes sítios) |
| E6 faturas | conta da biblioteca × pago | não passa: sem geração ±5%; com GD I a biblioteca cobra ~21% a menos (imposto sobre a compensada) |
| Composição da mediana da biblioteca | adaptadores × mediana de 47 | regime A não passa (a 0,01); regime C passa |
| MPPT | parcela por canal separa falha de sujeira | não passa (1 de 3) |
| Embarcado | SparseTSF, CycleNet, LightGBM/RF em C | passa no x86/WebAssembly; **sem medida no Raspberry Pi / ESP32** |
| Biblioteca | ~700 testes + regressão contra `metricas.csv` | verde no Lactec |

## 3. Fraquezas que a revisão encontrou

Ordenadas pelo quanto limitam o que o TCC e os artigos podem afirmar.

1. **Não existe período de teste intocado.** Todas as escolhas posteriores à v2 foram feitas olhando o mesmo teste
   das usinas (01/08/2025 → 31/05/2026) e das casas (out–dez/2020): os a_k do `outlook`, o fator 3 da penalidade do
   diagnóstico, a composição da mediana, os 28 dias do conformal, os limiares do relógio, o `median_weather`. Cada
   uma foi decidida com portão escrito antes, mas o portão foi medido no mesmo teste que já tinha guiado as
   anteriores. Nenhum número da biblioteca foi conferido num período que não serviu para escolher nada.
2. **Duas usinas, um estado.** Toda constante "medida no Paraná" (`outlook.TRUST`/`SKILL`, `diagnostics.PENALTY`,
   dias claros) está declarada, mas nunca validada fora. O piloto do PVDAQ tem portão commitado (`d630450`) e o do
   telhado medido também (`08aba0b`, revisado em `06827c2`); nenhum dos dois rodou, porque faltou memória.
3. **Casas: um inverno, 92 dias.** No FV das casas 21 de 32 modelos empatam com o melhor: o caso quase não separa
   modelos. Os dados cobrem 2020 inteiro, mas só out–dez é teste.
4. **Redes treinadas com uma semente e duas versões de torch.** As 52 entradas originais usaram torch 2.11 e as do
   passo T usaram 2.14; parte rodou em GPU e parte em CPU. Só os pilotos da etapa A usaram 3 sementes. O ranking das
   redes mistura variação de semente com diferença de modelo.
5. **Avaliação só do ponto no benchmark.** CRPS e cobertura existem só nos pilotos (F2(c), conformal); o
   `05_avalia.py` não avalia faixas, embora vários modelos as entreguem.
6. **No regime C só o LightGBM viu as várias NWP.** O F2(a) passou (+0,373) e o próximo passo registrado era refazer
   o C dos outros modelos com as entradas novas. Isso nunca foi feito. O AIFS tinha ~5 meses de histórico; hoje tem
   ~21.
7. **Lacunas de cobertura.** AutoARIMA em 6 combinações, nunca medido nem com a configuração reduzida. Ajuste fino
   dos fundacionais fortes (Chronos-2, TiRex-2, Toto-2.0) nunca tentado: só o TTM, que piorou. Time-LLM só com
   GPT-2, não com a configuração do artigo (LLaMA-7B). TimeGPT espera a sua decisão.
8. **O benchmark nunca foi refeito de ponta a ponta numa máquina só.** A regressão confere as métricas a partir das
   previsões gravadas, não as previsões em si. As previsões vêm de três máquinas e de vários contornos do Smart App
   Control.
9. **Relógio de Curitiba (NASA 1 h atrasada).** Está declarado. Não foi refeito por custo; com a VM o custo cai.
10. **Fora do alcance de computação:** as faturas pedem faturas detalhadas em PDF, o embarcado pede o hardware, a
    separação sujeira × sombra × string pede a análise das tensões CC de 5 min (leve), e o TimeGPT pede a sua decisão.

## 4. O que a VM muda

- **Muda:** GPU de 96 GB livre (cabem o ajuste fino de fundacionais, o Time-LLM com LLM grande e todas as redes com
  várias sementes); 48 threads (classicos estatísticos, LightGBM, PVDAQ em paralelo); Linux (sem Smart App Control:
  um ambiente único e congelado para tudo); Slurm (fila com limite de tempo de verdade, sem o problema de processos
  filhos soltos de `subprocess.run(timeout=)`, ver HISTORICO 09/10).
- **Não muda enquanto a RAM estiver ocupada:** ~20 GB por job. O AutoARIMA com clima e o PVDAQ completo podem
  precisar de mais. Pedir `--mem` explícito e deixar esses jobs na fila (`gpu_sim`/`gpu_unlimited`) para quando a
  memória liberar.
- **Dados privados num servidor compartilhado:** a cópia das usinas vai para um diretório próprio com `chmod 700`,
  nunca para pasta compartilhada nem para o repositório, e é apagada ao fim. Confirmar com o professor que isso
  está dentro da permissão dele (os dados já moravam no Lactec, mas o servidor tem outros usuários).

## 5. Plano de rodadas, em ordem de valor

Cada item segue a regra do projeto: portão escrito e commitado antes de rodar, saídas em `resultados/pilotos/` (ou
num `resultados_v3/` novo), registro honesto em `PILOTOS_F1_F2.md` também quando falha.

| # | Rodada | Pergunta | Recurso | Dados |
|---|---|---|---|---|
| V0 | **Montagem** | os ambientes de `ambientes/*.txt` montam no Linux; suíte da biblioteca, `test_auditoria.py` e a paridade completa (todas as combinações do `test_forecast_parity`, não só as duas padrão) passam | CPU, horas | repo + usinas (privado) |
| V1 | **Teste intocado das usinas** (a mais valiosa) | as escolhas congeladas (mediana, `median_weather`, a_k, fator 3, conformal) seguem valendo num período que não serviu para escolher nada: 01/06 → ~15/11/2026 | CPU; GPU para as redes | exports até 15/11/2026 **recebidos em 16/11** (seção 6) + `01_prepara_dados.py` no Lactec + Open-Meteo do período |
| V2 | **Generalidade no PVDAQ + telhado medido** | os portões `d630450` e `08aba0b`/`06827c2` (já escritos): orientação × metadata, relógio, cadeia física fora do Paraná | CPU, ≤20 GB por sistema, um job por sistema | PVDAQ (público) |
| V3 | **Reprodução v3 numa máquina só** | o ranking e os empates da v2 sobrevivem a um ambiente só, um torch só e **3 sementes** em toda rede treinada? Portão: mesmos grupos de empate (DM + Holm) e diferença de skill por modelo dentro da variação entre sementes | GPU livre, dias | tudo |
| V4 | **Casas no ano inteiro** | origem móvel de abril a dezembro de 2020 (quatro estações) em vez de um inverno: o ranking e a mediana mudam com a estação? | CPU + GPU | Dingle (CC0) |
| V5 | **Regime C com as 6 NWP (+ AIFS, ~21 meses)** em todos os modelos que aceitam clima | o que o F2(a) mostrou no LightGBM vale para os outros e para a mediana? | GPU + CPU | Open-Meteo (baixar de novo até nov/2026) |
| V6 | **CRPS e cobertura no benchmark** | avaliar as faixas de todo modelo que as entrega, com e sem conformal, no `05_avalia.py` | CPU, leve | previsões gravadas |
| V7 | **Ajuste fino de Chronos-2, TiRex-2 e Toto-2.0** | o ajuste por usina/casa, com origem móvel, ganha +0,02 sobre o zero-shot em ≥ 2 casos? A biblioteca continua zero-shot salvo ganho grande (regra de velocidade de 16/10) | GPU 96 GB | tudo |
| V8 | **AutoARIMA** | medir o pico de memória e o tempo numa série (o `piloto_autoarima_memoria.py` está pronto) e, se couber, as 6 combinações; senão declarar inviável com a medida | CPU, RAM > 20 GB: na fila | tudo |
| V9 | **Time-LLM na configuração do artigo** | com LLaMA-7B o LLM ainda piora (como com GPT-2 e em Tan et al. 2024)? Baixa prioridade: fecha a evidência, não muda a biblioteca | GPU 96 GB | casas |
| V10 | **Curitiba reagregada com o deslocamento de fração de hora** (opcional) | a decisão de 11–12/10 foi não refazer por custo; com a VM custa uma noite. Decisão sua | CPU + GPU | 5 min do Lactec |

Fora da VM (não é computação): faturas detalhadas (E6), Raspberry Pi 5 / ESP32 (E5), tensões CC por MPPT
(leve, no Lactec), TimeGPT (decisão), segundo conjunto público de consumo para validar as constantes do consumo
(candidato: o Solar Home da Ausgrid, 300 casas com FV; **conferir a licença antes**).

## 6. Decisões

Resolvidas em 16/11/2026:

1. **Novo export das usinas: RECEBIDO.** Exports de 5 min do Solar.web das duas usinas, 01/01 → 15/11/2026
   (Cascavel: Primo 4.0, CA + 1 MPPT; Curitiba: Symo 12.0, CA trifásica + 2 MPPT, com energia por MPPT), guardados
   junto dos exports antigos na pasta privada de dados brutos do Lactec (`Projeto_IA/ia_solar/dados_brutos/<usina>/
   exportacoes/`; os nomes dos arquivos trazem o nome do dono e NUNCA entram no repositório). Com eles o V1 tem
   01/06 → 15/11/2026 de teste intocado (~5,5 meses, inverno e primavera) e o `01_prepara_dados.py` pode estender
   `usinas_horario.parquet` (privado, fora do repositório desde 04/11).
2. **Dados na VM: PERMITIDO pelos donos** (todos os dados podem ir para a VM). Boa prática mantida: diretório
   próprio com `chmod 700`, nada em pasta compartilhada, porque o servidor tem outros usuários.

Ainda abertas:

3. **V3 vira o benchmark publicado (v3) ou fica como conferência da v2?** Recomendação: v3 publicado, v2 como registro.
   Os números mudam no último dígito (Linux, outro torch) e as sementes dão a faixa de variação que faltava.
4. **V10 (Curitiba):** refazer ou manter a decisão de 11–12/10?
5. **TimeGPT:** segue esperando (API paga, envia dados; só casas, nunca usinas).
6. **Banco local e aprendizado com o uso (seção 7):** o desenho abaixo é proposta; o que entra na biblioteca depende do
   piloto V11.

## 7. Banco de dados local e aprendizado com o uso (pedido de 16/11/2026)

Ideia: quem usa o aplicativo por meses deve receber previsões melhores que quem acabou de chegar, porque o
aplicativo guarda o que previu, vê o que aconteceu e ajusta o que é PRÓPRIO daquele sítio. Hoje cada `app.run` começa
do zero: lê o arquivo inteiro, ajusta o telhado e esquece tudo.

**Primeiro passo já feito (16/11):** `outlook.look_back` / `Result.past` mostra os últimos 7 dias como o método os
teria previsto na véspera, ao lado do medido (gráfico na página "Próximos dias"). É uma RECONSTRUÇÃO (hindcast):
com o banco, passa a ser a previsão que o aplicativo de fato emitiu.

**O banco (local, no computador da pessoa; SQLite num arquivo ao lado do aplicativo):**

| Tabela | O que guarda | Para quê |
|---|---|---|
| `medicoes` | cada hora medida de cada arquivo enviado, sem duplicar (chave: série, hora); de onde veio | histórico que cresce a cada envio; o arquivo novo só precisa trazer os dias novos |
| `previsoes` | cada previsão emitida: hora de emissão, versão da biblioteca e do método, lead, `y_hat`, `low`, `high`, fonte, modelos de tempo | erro REAL por lead, não reconstruído |
| `parametros_sitio` | telhado, kW efetivo, a_k e skill por lead aprendidos no sítio, com n e data | o que o sítio ensinou, com a origem declarada |
| `eventos` | o que a pessoa marca: limpeza, sombra nova, inversor trocado, viagem, aparelho novo, feriado | explicar erros grandes e tirar esses dias do ajuste |
| `planos` | as janelas de carga sugeridas, a que a pessoa escolheu e o que ela de fato usou | medir se o conselho serviu (economia realizada) |

**O que aprende com o uso (cada item é uma hipótese até o V11 medir):**

1. **Confiança por lead do próprio sítio:** o `TRUST` e o `SKILL` medidos no Paraná viram o ponto de partida; com o
   erro real guardado, cada sítio ganha os seus, puxados para o padrão enquanto há poucos dias (encolhimento:
   a_sítio = (n·a_medido + n0·a_padrão)/(n + n0), n0 escolhido em sítios que NÃO entram na avaliação). Os rótulos de
   confiança passam a dizer a verdade daquele telhado.
2. **Faixas calibradas no próprio erro:** `postprocessing.conformal_quantiles` (já na biblioteca, piloto F2(c'))
   sobre os erros guardados: a faixa de 80% cobre 80% naquele sítio.
3. **Correção de viés do consumo:** `correct_bias` (14 dias) só onde o piloto mostrou ganho (viés grande); o banco
   permite medir por casa quando ligar.
4. **Telhado e kW efetivo acompanhados no tempo:** mais dias claros = telhado mais firme; queda do kW efetivo vira
   aviso de sujeira/falha (o diagnóstico existente, agora contínuo).
5. **Eventos marcados pela pessoa** saem do ajuste (um feriado não ensina o perfil da semana).

Regras do projeto que valem aqui: nada sob medida para os nossos dados (o encolhimento e o n0 são parâmetros
declarados); a biblioteca segue só-CPU e rápida; a privacidade fica (o banco nunca sai do computador; nada vai para
servidor).

## 8. V11 — simulação do uso prolongado (piloto, portão antes de rodar)

Pergunta: uma pessoa que usa o aplicativo por N dias recebe previsões melhores do que o aplicativo "congelado" de
hoje? Quanto, depois de quantos dias, e nunca pior no começo?

Simulação (replay causal, nenhum dado do futuro):

- Cada sítio vira um "usuário" que começa no dia S com H dias de histórico (H ∈ {30, 90, 365}) e envia dados novos a
  cada k dias (k ∈ {1, 7, 30}). Toda noite o aplicativo simulado emite a previsão dos leads 1–7 com a previsão do
  tempo que existia naquela noite (Previous Runs, leads 1–7, desde 2024), grava no banco, e na manhã seguinte
  atualiza os parâmetros do sítio só com o que já aconteceu.
- Duas variantes no mesmo replay: **congelada** (o método de hoje, padrões do Paraná) e **aprendendo** (itens 1–3 da
  seção 7). Mesmo sítio, mesmos dias, mesmas horas avaliadas.
- Saída: curva de aprendizado = skill do total do dia (lead 1 e lead 7), cobertura das faixas de 80/60% e CRPS em
  função dos dias de uso.

Portão (rascunho; commitar antes de rodar): (G1) após 90 dias de uso, a variante aprendendo ganha ≥ +0,02 de skill no
total do dia (lead 1) em ≥ 2/3 dos sítios de AVALIAÇÃO, com DM p < 0,05 no conjunto; (G2) nos primeiros 30 dias
nunca perde mais que 0,01 (o encolhimento tem de proteger quem acabou de chegar); (G3) cobertura de 80% dentro de ±5
pontos depois de 60 dias. n0 e qualquer limiar são escolhidos num grupo de sítios de AJUSTE separado antes, e os
números do relatório saem só dos sítios de avaliação.

Sítios: usinas de Cascavel e Curitiba (2024-03 → 2026-11 com os exports novos: ~2,7 anos de replay com tempo
arquivado), BR-PVGen (51 usinas brasileiras, se o período cruzar o arquivo da Open-Meteo), Dingle e Ausgrid para o
consumo (sem tempo: só o perfil e o viés). Divisão ajuste/avaliação fixada por sorteio com semente, antes de olhar.

Custo: CPU, independente por sítio × início × variante: o caso ideal da VM (48 threads, pouca RAM por job). Uma
estimativa grosseira: ~2 s por noite simulada (o `forecast_ahead` + `look_back` medidos hoje) × ~1.000 noites × ~60
sítios × 9 combinações (H, k) × 2 variantes ≈ 600 h de CPU, ~13 h na VM com 48 threads; o piloto começa com 3 sítios
e uma combinação.

## 9. Dados públicos que ajudam o projeto (busca de 16/11/2026)

Licenças conferidas só pelo que as páginas mostram: confirmar cada uma na fonte antes de usar e antes de publicar
qualquer coisa derivada.

| Dado | O que tem | Para quê aqui | Licença / acesso |
|---|---|---|---|
| **BR-PVGen** (Zenodo, IEEE Access 2026) | 51 usinas FV distribuídas no Brasil, vários climas; inversor (CA, CC, reativa) + estação solarimétrica (POA, GHI); coordenadas só por estado | o achado mais útil: validar no BRASIL, fora do Paraná, as constantes (`TRUST`, `SKILL`, dias claros, penalidade), o ajuste do telhado contra POA medida, falhas por inversor; sítios do V11 | "Open" no Zenodo; licença exata a conferir |
| **Ausgrid Solar Home** | 300 casas de NSW (Austrália), FV + consumo + carga controlada, meia hora, 3 anos (2010–2013); dados mensais de 2.657 casas | validar as regras do consumo e do viés fora de Dingle (o "segundo conjunto" da fraqueza 3); net metering; V11 | CC BY (portal NSW) |
| **GoiEner** (Espanha, Sci. Data 2024) | 25.559 séries horárias de clientes, ~3 anos (2014–2022) | consumo em escala: as regras do perfil e do viés em milhares de casas | Zenodo; conferir licença |
| **EDS-lab/pv-generation** (Hugging Face) | coleção harmonizada de vários conjuntos de FV abertos, metadados com inclinação, azimute, potência e local | validar o ajuste do telhado contra a orientação declarada em muitos sistemas | por conjunto de origem |
| **175 sistemas residenciais** (Visser et al., Holanda) | FV de 175 telhados, 2014–2017, orientação conhecida | idem, num clima nublado | aberto (conferir) |
| **Open Climate Fix uk_pv** | 1.311 sistemas FV do Reino Unido (2018–2021), 2 e 5 min, local ofuscado | escala e clima do norte; regime A/B | acesso por cadastro no Hugging Face; licença a conferir |
| **Telhados de Hong Kong** (Sci. Data 2025) | 60 estações, inversor a cada 5 min, 3 anos | clima subtropical úmido parecido com parte do Brasil | aberto (Dryad) |
| **PVOD** (China) | 10 usinas com medição + NWP | o regime C fora do Paraná com NWP própria | aberto (conferir) |
| **PVDAQ** (NREL) | já no `io.pvdaq` | V2 | CC BY 4.0 |
| **Open-Meteo Historical Forecast API** | previsão "como emitida" desde 2021/2022 conforme o modelo | regime C para dados anteriores a 2024 (Previous Runs começa em 2024) | não comercial (o plano pago resolve o uso comercial) |
| **Open-Meteo Historical Weather (ERA5 / ERA5-Land)** | reanálise horária desde 1940 | regime B (clima do dia) em QUALQUER sítio, inclusive as casas de Ausgrid e GoiEner | não comercial |
| **INMET (estações automáticas)** e **rede SONDA (INPE)** | GHI medida em solo, horária; SONDA com controle de qualidade BSRN | clima medido perto das usinas (há estações em Cascavel e Curitiba a conferir) em vez da NASA; conferir o relógio de Curitiba | dados públicos; acesso a conferir |
| **ANEEL – relação de MMGD** | cadastro de toda a geração distribuída (potência, município, data) | valores típicos (kWp por município) para o caso sem `kwp`; contexto do mercado | dados abertos |
| **Kaggle**: Growatt (CC BY) e casa com bateria (MIT) | já anotados em 17/10 | leitor de contadores; bateria para o "e se" | CC BY / MIT |

Lacuna que a busca NÃO resolveu: não há conjunto aberto de consumo de CASAS brasileiras hora a hora (só a carga
agregada do ONS/EPE). Fonte possível: Lactec/Copel, com anonimização, ou os próprios usuários do aplicativo com
consentimento.

Fontes da busca: [BR-PVGen v2](https://zenodo.org/records/23739670), [BR-PVGen v1](https://zenodo.org/records/21511487),
[Ausgrid Solar home](https://ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data),
[portal NSW](https://data.nsw.gov.au/data/dataset/solar-home-electricty-data),
[GoiEner](https://www.nature.com/articles/s41597-023-02846-0),
[EDS-lab/pv-generation](https://huggingface.co/datasets/EDS-lab/pv-generation),
[175 sistemas](https://www.researchgate.net/publication/362441024_Open-source_quality_control_routine_and_multi-year_power_generation_data_of_175_PV_systems),
[uk_pv](https://huggingface.co:443/datasets/openclimatefix/uk_pv),
[Hong Kong](https://www.nature.com/articles/s41597-025-04397-y),
[PVOD](https://www.sciencedirect.com/science/article/abs/pii/S0038092X21008070),
[Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api),
[Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api),
[BDMEP/INMET](https://portal.inmet.gov.br/servicos/bdmep-dados-hist%C3%B3ricos),
[SONDA](https://labren.ccst.inpe.br/producao/eventos/XIISBSR_2005_Goiania_3563_SONDA_FRMartins_etal.pdf),
[ANEEL dados abertos](https://dadosabertos.aneel.gov.br/dataset/?res_format=CSV&tags=radia%C3%A7%C3%A3o+solar),
[correção de viés com aprendizado contínuo (vento)](https://arxiv.org/pdf/2402.13916),
[correção residual online](https://arxiv.org/pdf/2603.25495).
