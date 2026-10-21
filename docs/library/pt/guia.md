# Guia em português

A `prosumer` analisa a **geração** (fotovoltaica) e o **consumo** de quem produz e consome energia, a partir
dos arquivos que o portal do inversor ou o medidor exportam: qualidade dos dados, o relógio dos dados
conferido pelo sol, uma checagem honesta da previsão do dia seguinte, a previsão dos próximos dias, o telhado e
a saúde da usina, e a conta de luz com e sem a geração. O código e a documentação principal estão em inglês;
este guia resume o uso para o setor elétrico brasileiro.

## Instalar

```bash
pip install "prosumer[lightgbm,net,fronius] @ git+https://github.com/JoaoCarlos134/prosumer"
```

Python 3.11 ou mais novo. Tudo roda em CPU.

## Ler os dados do inversor ou do medidor

```python
# network
from prosumer.io import read_energy

# a exportação de 5 minutos do Fronius Solar.web ("minuto"), de qualquer outra marca, ou uma tabela do medidor
pv = read_energy("minha_usina_2025.xlsx", tz="America/Sao_Paulo", quantity="generation", site=(-25.43, -49.27))
```

O leitor nunca escolhe a coluna pela posição: reconhece a exportação do Fronius Solar.web e, em qualquer outra
tabela, escolhe a energia pelo nome e pela unidade (kWh, Wh; ou potência em kW, W), nunca corrente, tensão,
fator de potência ou temperatura. Um contador (registro do medidor, ou a "energia de hoje" do inversor, que
zera à meia-noite) é reconhecido pelos valores e diferenciado. Na dúvida, dá erro com a lista das colunas.
`site` (latitude, longitude, arredondadas para 2 casas) zera as horas sem sol.

## A análise completa numa chamada

```python
from prosumer import analyze, data

pv, _ = data.example_plant(n_series=1, days=60)  # dados sintéticos; troque pelos seus
r = analyze(pv, site=(-25.43, -49.27), test_days=14)
print(r.to_markdown()[:300])
```

O relatório traz: a qualidade (cobertura, buracos), o relógio conferido pelo sol (um arquivo em UTC lido como
hora local aparece como +3 h), o diagnóstico (orientação do telhado, desempenho nos dias claros, degraus de
limpeza ou falha), a checagem da previsão do dia seguinte (a **mediana** das previsões contra uma referência
justa, com intervalo de confiança), as fontes e licenças, e notas em linguagem simples.

## Os próximos dias

```python
from prosumer import data, forecast_ahead

pv, _ = data.example_plant(n_series=1, days=200)
o = forecast_ahead(pv, days=3, site=(-25.43, -49.27))  # sem previsão do tempo: o dia típico do mês
print(o.daily[["date", "total", "confidence"]])
```

Com a previsão do tempo ao vivo (`io.open_meteo.fetch_forecast`, até 16 dias, vários modelos), a geração de
cada hora = potência efetiva aprendida nos dias claros x irradiância no plano dos painéis. A confiança em cada
dia de antecedência foi medida nas duas usinas do Paraná; fora delas é uma suposição, e o resultado diz isso.

## As notas em português

As notas, o registro do `app.run` e as mensagens de erro saem em inglês por padrão e em português com
`lang="pt"` (números com vírgula decimal, datas em dia/mês/ano):

```python
from prosumer import i18n

print(r.to_dict(lang="pt")["notes"][:2])
print(o.to_dict(lang="pt")["notes"][0])
try:
    forecast_ahead(pv, days=99, site=(-25.43, -49.27))
except ValueError as e:
    print(i18n.message(e, "pt"))
```

Nomes e códigos (colunas, nomes das previsões, `source`, `confidence`, unidades) ficam como estão; o site os
rotula. As traduções estão num só catálogo, `prosumer/i18n/pt.py`.

## A conta de luz (`economics.brazil`)

```python
# network
from prosumer.economics import brazil

book = brazil.TariffBook.from_aneel(
    "COPEL-DIS",  # SigAgente da ANEEL: "CEMIG-D", "ELETROPAULO" (Enel SP), "LIGHT SESA", ...
    icms={"2018-01-01": 0.29, "2022-06-23": 0.18, "2024-03-18": 0.19},  # as alíquotas lidas na fatura
    pis_cofins=0.0925,
    fio_b_years=[2025, 2026],  # só para GD II
)
setup = brazil.Setup(book=book, connection="bifasico_3", connected="2023-05-10")  # GD II pela data
conta = setup.bill(consumo, geracao)
```

O que está modelado, cada regra citada à lei ou à resolução no código: tarifa cheia com ICMS e PIS/COFINS "por
dentro", bandeira do mês (só na energia faturada), custo de disponibilidade (30/50/100 kWh), postos e feriados
da tarifa branca, e o SCEE da Lei 14.300/2022: GD I com compensação integral até 2045, GD II com a rampa do Fio
B (15% em 2023 ... 90% em 2028), créditos de 60 meses, o mais antigo primeiro. **Tarifa branca com geração**
(REN 1.000 art. 655-G): a injeção compensa primeiro o próprio posto; o excedente vai para os outros postos,
convertido pela razão da TE Energia entre eles; o que sobra vira crédito do posto em que foi injetado, e o
crédito também compensa primeiro o seu posto.

Onde a lei deixa a leitura aberta, a escolha é um parâmetro, com a prática das distribuidoras como padrão:
`after_2028` (GD II depois de 2028), `gd2_minimum` (a lei e a REN 1.000 diferem sobre o mínimo da GD II),
`icms_exempt_compensated` (isenção do ICMS na energia compensada: "all", "te_only", "none"), `te_energy` e
`posto_order` (tarifa branca com geração). ICMS e PIS/COFINS são digitados pela pessoa: não há tabela por
estado.

Não modelado: COSIP (digite em `Setup(cosip=...)`), grupo A, tarifa social, geração compartilhada ou remota, a
reforma tributária (LC 214/2025). Conferido contra faturas reais da Copel: a energia sem geração fica a +-5%,
mas as contas com compensação ainda não são reproduzidas (falta separar como o imposto incide sobre a energia
compensada: precisa de faturas detalhadas).

## Licenças dos dados

As casas de Dingle (Irlanda) são CC0 (Khadem et al., 2024, *Scientific Data*); o PVDAQ (EUA) é CC BY 4.0; os
dados da ANEEL são ODbL (atribuir à ANEEL); os da Open-Meteo são CC BY 4.0, mas a API gratuita é só para uso não
comercial. Cada entrada leva sua fonte e licença até o relatório (`Report.provenance`).
