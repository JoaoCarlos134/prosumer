# Tarifas — base de referência

Insumo tarifário das duas usinas, ambas atendidas pela **Copel-DIS** (Paraná).
Montado para alimentar o HOMER e para custear as séries de 5 min.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `copel_tarifas_historico.csv` | TUSD e TE homologadas, B1 e B3, convencional e branca, por vigência (2010→2027). **Sem impostos.** |
| `copel_componentes_b1.csv` | Abertura da TUSD e da TE do B1 residencial na vigência atual — inclui o **TUSD Fio B**, base da cobrança da Lei 14.300. |
| `bandeiras_mensal.csv` | Bandeira acionada mês a mês (jan/2015 → set/2026) e o adicional em R$/MWh. |
| `bandeiras_adicional.csv` | Valores homologados de cada bandeira por vigência. |
| `parametros_fiscais.csv` | ICMS do Paraná por período e PIS/COFINS. |
| `parametros_usinas.csv` | Enquadramento de cada UC: subgrupo, ligação, custo de disponibilidade, data de conexão. |
| `_cache/` | JSON cru da API da ANEEL, para não rebaixar em toda execução. |

## Origem

Tudo vem da API de dados abertos da ANEEL (`dadosabertos.aneel.gov.br`),
não de sites de terceiros. O script `scripts/baixa_tarifas_aneel.py` reproduz a
coleta. O PDF da resolução homologatória no `www2.aneel.gov.br` está atrás de
Cloudflare e **não** é baixável por script — a API é a via que funciona.

## Como a tarifa cheia é montada

    tarifa_sem_impostos = (TUSD + TE) / 1000              # R$/kWh
    adicional_bandeira  = adicional_do_mes / 1000         # R$/kWh
    fator_impostos      = 1 / (1 - ICMS - PIS_COFINS)     # ambos "por dentro"
    tarifa_cheia        = (tarifa_sem_impostos + adicional_bandeira) * fator_impostos

Fora disso, e **não** embutido no R$/kWh:

- **Custo de disponibilidade**: 50 kWh/mês (bifásico, Cascavel) e 100 kWh/mês
  (trifásico, Curitiba). É o piso da fatura, cobrado mesmo com a geração zerando
  o consumo. No HOMER entra como encargo fixo mensal.
- **COSIP/CIP**: contribuição municipal de iluminação pública, definida por lei
  de cada município e não publicada pela ANEEL. Não está aqui; precisa vir de
  uma fatura de Cascavel e de Curitiba.

## Lei 14.300 — as duas usinas têm direito adquirido

As duas conectaram antes de 07/01/2023 (Cascavel 07/2019, Curitiba 07/2021),
então mantêm a compensação integral, **sem pagar o Fio B sobre a energia
injetada**, até 31/12/2045. O `TUSD_FioB` no `copel_componentes_b1.csv` está ali
como referência caso se queira simular uma usina nova, que pagaria a rampa da lei.

## Aferição contra fatura real

O único período de Cascavel sem geração — **2018 inteiro** — serve de prova do
método, porque ali `pago / consumo` é a tarifa de varejo de verdade.

| | R$/kWh |
|---|---|
| Modelo (TUSD+TE + bandeira do mês, ICMS 29%, PIS/COFINS 9,25%) | 0,8062 |
| Fatura (média de 12 meses) | 0,8457 |
| Resíduo | 0,0395 |

O resíduo de 0,0395 R$/kWh sobre um consumo de ~250 kWh/mês equivale a
**R$ 10,62/mês** de encargo fixo — que é exatamente a ordem de grandeza da
COSIP. Ou seja: a parte variável fecha, e o que sobra é a contribuição de
iluminação pública. Use R$ 10,62/mês como ponto de partida para Cascavel,
corrigido para hoje, até que apareça uma fatura recente.

Depois de 2019 essa conferência não vale mais: com a compensação, `pago/consumo`
mede o piso da fatura, não a tarifa.

## Limites conhecidos

- **PIS/COFINS 9,25% é o nominal.** A Copel apura a alíquota efetiva mês a mês e
  ela costuma ser menor. É o único parâmetro realmente frouxo aqui — o teste de
  2018 não consegue separá-lo da COSIP.
- **A tarifa é diária, não horária.** As usinas estão na modalidade
  convencional, que não tem posto tarifário. As colunas de 5 min repetem o mesmo
  valor dentro do dia. Só na tarifa branca isso mudaria.
- **A bandeira é atribuída pelo mês-calendário**, enquanto a fatura segue o ciclo
  de leitura (dia 9 em Cascavel). Nas viradas de bandeira há defasagem de até
  um mês em relação ao que foi cobrado.
- Os PDF das resoluções homologatórias no `www2.aneel.gov.br` estão atrás de
  Cloudflare e devolvem 403 para qualquer script. A API de dados abertos é a
  única via automatizável, e é a mesma fonte.
