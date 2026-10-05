# Estado do projeto — retomada

Última sessão: 28/09/2026. Este arquivo existe para retomar o trabalho sem
refazer descobertas. O `LEIA-ME.md` explica a estrutura; este aqui explica
**onde paramos**.

**28/09/2026 — pipeline reprodutível de verdade.** Até aqui os scripts de
`analise/` só rodavam na pasta plana onde foram escritos (e `frame5.parquet`
nem existia na pasta). Agora cada um roda de qualquer lugar, via
`analise/comum/scripts/caminhos.py`. Teste: pipeline inteiro (42 etapas, ~7 min,
fora os downloads da NASA) refeito numa cópia a partir das exportações brutas —
80 saídas idênticas byte a byte às guardadas, inclusive as bases de modelagem.
Só diferiram a fatura (entrou 2025, ver pendência 1) e tempos de execução.

---

## O que está pronto

| Entrega | Onde |
|---|---|
| Série de 5 min unificada, Cascavel | `analise/cascavel/dados/dados_5min_2019-2026.parquet` (694.488 linhas) |
| Série de 5 min unificada, Curitiba | `analise/curitiba/dados/curitiba_5min.parquet` (490.013 linhas) |
| NASA POWER diária + horária, os dois sites | `analise/*/dados/nasa_power_*.csv` |
| Base de modelagem limpa | `base_modelagem/` (620.278 linhas, 28 colunas) |
| Scripts de regressão por usina | `base_modelagem/cascavel/` e `/curitiba/` |
| Documentação com equações | `base_modelagem/Documentacao_Base_Modelagem.xlsx` |
| Relatórios HTML | `analise/cascavel/relatorios/`, `analise/comparativo/` |
| Base tarifária Copel-DIS (ANEEL) | `analise/tarifas/` — histórico 2010→2027, bandeiras mês a mês, componentes |
| Séries de 5 min em XLSX com tarifa por linha | `analise/*/dados/*_5min_*.xlsx` (abas Tarifas, Bandeiras, HOMER) |
| Teste do downscaling por inversão da potência | `analise/irradiancia_inversa/` — não melhora o modelo, ver LEIA-ME |
| Modelos para embarcamento, com TensorFlow Lite | `base_modelagem/embarcado/` — 32 arquivos .tflite e o comparativo. **Verificados em 05/10/2026** a partir do arquivo (`referencia/verifica_tflite.py`): os 32 reproduzem o R² original; o pré-processamento que faltava para usá-los fora do Python está em `preprocessamento_*.json` |
| Documentação dividida em duas | `base_modelagem/Documentacao_Dados.xlsx` e `_Resultados.xlsx` |

### Artefatos publicados (claude.ai)

- Auditoria Cascavel — https://claude.ai/code/artifact/c1913307-d4a3-4e63-8acb-abbfe4b7eb12
- Achados dos 5 min — https://claude.ai/code/artifact/a253b6e0-9110-4439-a6d3-d18b0b26e63c
- Explorador interativo — https://claude.ai/code/artifact/e50e6b4e-870d-4a95-8b2f-ecf3b077bbe1
- Dois sites — https://claude.ai/code/artifact/356d1cd3-0176-4496-ab72-0a9f28328728

---

## Plano de publicação

Revisão de 23/09/2026 para artigo de periódico em **`PLANO_ARTIGO.md`**:
dois artigos, falhas de protocolo a corrigir antes de escrever e próximos
experimentos. Próximo passo: `paper/protocolo_canonico.py`.

---

## Pendências

**5. COSIP e PIS/COFINS efetivo continuam em aberto.**
A parte variável da tarifa fecha contra a fatura de 2018 de Cascavel (modelo
0,8062 R$/kWh contra 0,8457 medido). O resíduo, ~R$ 10,62/mês, é COSIP — mas é
um número de 2018 e de Cascavel. Curitiba não tem nenhuma fatura, então não tem
COSIP nem confirmação do PIS/COFINS efetivo (uso o nominal 9,25%).
**O que destrava:** uma fatura recente de cada UC.

**1. ~~`relatorio.html` desatualizado~~ — arquivo regenerado em 28/09/2026.**
Agora usa 3,96 kWp, PR 0,758 e déficit de 6.365 kWh. A fatura de 2025 (que
entrou na `Fatura de energia.xlsx` em 14/09, depois da primeira análise) também
entrou: em 2025 **expiraram 2.750 kWh de créditos** (1.548 em 2024) e a geração
cobriu 3,0× o consumo. O texto do relatório, escrito à mão em `make_report.py`,
ainda fala só até 2024; as figuras 18–20 e o explorador já mostram 2025.
O artefato publicado (Auditoria Cascavel, link acima) continua na versão antiga.

**2. Curitiba: potência e geometria não resolvidas.**
O ajuste de orientação falha (R² 0,52/0,59 contra 0,89 em Cascavel) porque o
telhado não é um plano único por string. A potência nominal é estimativa própria
(~9,6 kWp); a planilha divide por 12,000 kWp, que é a potência CA do inversor.
**O que destrava:** uma foto do telhado e o mapa de strings do instalador.

**3. Curitiba não tem dados de fatura.**
A análise econômica que reenquadrou Cascavel (2,6× sobredimensionada, créditos
expirando) não pôde ser repetida.

**4. Cascavel está sujando de novo.**
A corrente CC cai desde a limpeza de set/2024; em ago/2026 estava ~8% abaixo da
linha de base. Padrão de dente de serra: ~12 meses para perder 10%.

---

## Fatos que custaram horas e não estão em documentação nenhuma

- **NASA POWER horária, carimbo "LST"**: alinha em **−55 minutos** contra o
  relógio do inversor. A correção de longitude sozinha daria −35. Verificado por
  agregação, r = 0,947 em 38.010 horas.
- **A série horária da NASA POWER termina em 31/05/2026**, a diária vai até
  julho. Isso deixa ~15% do período de teste sem irradiância horária, e o modelo
  despenca ali (R² −0,86 nessas linhas). Os scripts já detectam e descartam.
- **Azimute não é recuperável de totais diários**: a função objetivo é
  exatamente simétrica em torno do norte — R²(155°) = R²(205°) com diferença
  0,00e+00. Só com dados sub-diários.
- **Convenção Duffie & Beckman**: γ = 0 é sul, positivo para **oeste**. Logo
  "25° a leste do norte" é **γ = 205**, não 155. Errei isso na primeira vez;
  não mudou nada em resolução diária (POA idêntica a 3,6e−15) mas quebra tudo
  em 5 min.
- **Duas coordenadas a 19 km caem na mesma célula da NASA POWER** e retornam
  dados byte a byte idênticos. Não vale refinar localização.
- **NASA POWER diária lê 3,2% abaixo** da irradiância real em dias claros, com
  ciclo sazonal de 4,1 pontos. É o piso de erro.
- **Eficiência do inversor > 1 em 25% dos intervalos**: o lado CA vem de contador
  integrado, o CC de amostra instantânea — não são simultâneos. Por isso o
  número de 98,5% que eu citei tem precisão de ±1, não de duas casas.

---

- **Os PDF de resolução da ANEEL estão atrás de Cloudflare** e devolvem 403 para
  curl e para qualquer fetch, com ou sem User-Agent de navegador. A API de dados
  abertos (`dadosabertos.aneel.gov.br`, CKAN) serve a mesma informação em JSON e
  responde normalmente. É por ali que a base tarifária entra.
- **ICMS do Paraná sobre energia mudou duas vezes no período dos dados**: 29%
  até 22/06/2022, 18% até 17/03/2024, 19% desde então. Quem usar uma alíquota
  única erra 10 pontos no começo da série do Curitiba.
- **As duas usinas têm direito adquirido da Lei 14.300** (conexão em 2019 e
  2021, antes do corte de 07/01/2023): compensação integral, sem Fio B sobre a
  injetada, até 31/12/2045. No HOMER isso é sellback igual à tarifa cheia.

- **Inverter a potência para obter irradiância a 5 min NÃO melhora o modelo.**
  Testado nas duas usinas: o cenário que "ganha" (R² 0,9999) é vazamento puro —
  `G_inv` é o alvo reescrito. O downscaling honesto, com `G_inv` só como alvo de
  treino, PIORA o R² em 0,011 e 0,008. Downscaling reorganiza informação, não
  cria. Só 17% (Cascavel) e 21% (Curitiba) da variância do kc de 5 min mora
  dentro da hora: o gargalo é a qualidade da NASA, não a resolução dela. O kc
  horário da NASA tem R² **negativo** contra o kc medido (−0,38 e −0,59).

- **Uma única coluna entrega quase todo o R².** `poa_estimada` (= `poa_ceu_claro`
  × `kc_horario`) sozinha, num modelo linear, dá R² 0,8196 em Cascavel contra
  0,8228 das 20 colunas — **99,6%**. Em Curitiba, 95,0%. A escolha de algoritmo
  vale 0,03; ter ou não ter essa coluna vale 0,24. A física é P = η·A·POA, linear
  na irradiância: depois de construir a POA direito, sobra pouco para o modelo.
  Isso explica de uma vez o linear empatar com árvore em Cascavel, o embarcado
  desabar para 0,58 e o downscaling não ajudar.
  Tabela em `base_modelagem/embarcado/ablacao_preditores.csv`.
- **Curitiba ganha com árvore por um motivo ruim.** Lá o HistGB bate o linear
  (0,7483 × 0,7132) porque o `poa_ceu_claro` está errado — telhado de dois planos
  modelado como um. A árvore corrige não-linearmente o erro da física. É a
  pendência 2 disfarçada de vantagem de algoritmo.
- **TFLite cabe em 3,4 KB** (MLP 16-8, int8 total, R² 0,8117 em Cascavel) contra
  389 KB do HistGB em pickle e 2,6 GB do Random Forest. float32, float16 e int8
  dinâmico dão R² idêntico ao Keras; só o int8 total perde algo. A latência do
  int8 medida aqui é maior que a do float32 — artefato de x86, inverte num
  Cortex-M com CMSIS-NN.

- **Um sensor de irradiância substitui toda a NASA POWER.** O vão entre o modelo
  embarcado (sem NASA) e o completo é 0,225 em Cascavel e 0,232 em Curitiba. Um
  único canal de irradiância fecha **99,3% e 98,7%** dele; as outras oito
  variáveis da reanálise valem ~1%. POA + temperatura, **dois preditores**, dá
  0,8201 em Cascavel. **O `+0,18` que eu citei antes para o piranômetro está
  errado** — vinha do cenário B da irradiância inversa, cujo `G_inv` carrega o
  estado da usina junto. Piso medido: +0,22. Teto: não mensurável sem o sensor.
  Script: `base_modelagem/referencia/sensor_irradiancia.py`.

## Diagnósticos fechados

**Cascavel** — sujeira progressiva, não degradação. Corrente CC caiu 16% com
tensão estável em 1% (exclui módulo aberto, diodo de bypass e inversor). A
limpeza de nov/2023 devolveu +28% em sol alto e +54% em sol baixo: assinatura
angular de camada de sujeira. Causa raiz: **13° de inclinação** — sem declive a
chuva não lava. Duas limpezas detectadas: nov/2023 e set/2024.

**Curitiba** — falha específica da string 1 entre dez/2022 e jul/2023 (corrente
−50% contra −18% da string 2, recuperação num único mês). E uma **reconfiguração
em jun/2025**: as tensões trocaram de patamar (−19% e +21%, soma constante),
módulos remanejados entre as entradas, potência CC subiu 15%.

---

## Ambiente

Instalados nesta máquina durante o trabalho: `truststore` (obrigatório — o proxy
da Lactec quebra a verificação TLS; usar `truststore.inject_into_ssl()` antes de
qualquer `requests`), `pyarrow`, `xgboost 3.4.1`.

Comandos que precisam de rede rodam com o sandbox desligado.

---

## Modelo escolhido

**HistGradientBoosting**, após comparar 13 algoritmos (mesma família do
Projeto_solo, versão regressão), todos com parâmetros padrão e só
`random_state=42`. R² médio 0,7609. Cascavel 0,8047 / Curitiba 0,7170.
Gradient Boosting clássico fica 0,0015 à frente em Cascavel mas leva 57,4 s
contra 3,3 s. XGBoost ficou em 6º.

Tabela completa em `base_modelagem/*/comparacao_modelos_completa.csv`.
