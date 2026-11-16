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
| V1 | **Teste intocado das usinas** (a mais valiosa) | as escolhas congeladas (mediana, `median_weather`, a_k, fator 3, conformal) seguem valendo num período que não serviu para escolher nada: 01/06 → ~15/11/2026 | CPU; GPU para as redes | **novo export do Solar.web** até nov/2026 + `01_prepara_dados.py` no Lactec + Open-Meteo do período |
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

## 6. Decisões que dependem de você

1. **Novo export das usinas até nov/2026** (Solar.web, via professor/donos): é o que permite o V1, o único teste
   que responde à fraqueza 1.
2. **Dados das usinas na VM compartilhada:** ok do professor para copiá-los para lá (com `chmod 700` e apagados ao fim)?
3. **V3 vira o benchmark publicado (v3) ou fica como conferência da v2?** Recomendação: v3 publicado, v2 como registro.
   Os números mudam no último dígito (Linux, outro torch) e as sementes dão a faixa de variação que faltava.
4. **V10 (Curitiba):** refazer ou manter a decisão de 11–12/10?
5. **TimeGPT:** segue esperando (API paga, envia dados; só casas, nunca usinas).
