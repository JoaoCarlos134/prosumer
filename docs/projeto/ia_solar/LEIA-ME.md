# Projeto IA Solar — Cascavel e Curitiba

Duas usinas fotovoltaicas, dados de 5 minutos do inversor Fronius cruzados com
NASA POWER. Tudo aqui é reproduzível do arquivo bruto ao relatório.

---

## Estrutura

    ia_solar/
      LEIA-ME.md                  este arquivo
      dados_brutos/               NADA AQUI FOI ALTERADO
        cascavel/
          USINA_CASCAVEL_serie_temporal_2019-2026.xlsx   série diária
          Fatura de energia.xlsx                       consumo, injeção, créditos, ficha técnica
          serie_5min/                                  7 exportações anuais do inversor
          exportacoes/                                 exportações avulsas
        curitiba/
          serie_5min/                                  5 exportações anuais do inversor
      base_modelagem/             <<< O QUE SEUS COLEGAS PRECISAM
        cascavel/                 uma pasta, um script, roda sozinha
          Modelos_Regressao_Cascavel.py
          base_Cascavel_5min.parquet      362.996 registros (14 MB)
          base_Cascavel_horaria.csv       32.656 registros, abre no Excel
          base_Cascavel_horaria.parquet
          dicionario_colunas.csv
          resultados_exemplo/             saidas das minhas execucoes, para conferencia
        curitiba/                 idem, 257.282 registros
          Modelos_Regressao_Curitiba.py
          base_Curitiba_5min.parquet      (10 MB)
          base_Curitiba_horaria.csv       23.087 registros
          ...
        ambas_usinas/             as duas juntas, com a coluna 'site'
          Modelos_Regressao_Geracao.py    tem o seletor USINA = 'Cascavel'|'Curitiba'|'TODAS'
          base_modelagem_5min.parquet     620.278 registros (24 MB)
          base_modelagem_horaria.csv
        referencia/               scripts que montaram as bases
      analise/                    a análise completa
        cascavel/    relatorios/ dados/ figuras/ scripts/
        curitiba/    dados/ figuras/ scripts/
        comum/scripts/    solar.py (geometria e transposição), vizstyle.py
        comparativo/ relatório dos dois sites

---

## Para rodar os modelos (o caso comum)

1. Copie **uma** pasta: `base_modelagem/cascavel/` ou `base_modelagem/curitiba/`.
   Cada uma e autossuficiente — o script precisa somente do `.parquet` que esta
   ao lado dele. **Nenhum CSV e obrigatorio.**
2. `pip install pandas numpy matplotlib seaborn scikit-learn pyarrow`
3. Rode o script. Nao precisa editar nada para a execucao padrao.

### Os quatro arquivos de dados de cada usina

O script le **apenas o `.parquet`**. Os CSV existem para voces olharem os dados.

| Arquivo | Linhas | Tamanho | O que e |
|---|---:|---:|---|
| `base_<Usina>_5min.parquet` | 362.996 / 257.282 | 14 / 10 MB | **o que o modelo usa**. O script le este. |
| `base_<Usina>_5min.csv` | as mesmas | 105 / 75 MB | **espelho exato** do parquet, mesmas linhas e colunas. **Não fica guardado**: gere com `referencia/gerar_csv_espelho.py` |
| `base_<Usina>_horaria.csv` | 32.656 / 23.087 | 12 / 8 MB | **agregado por hora** (media de ~12 intervalos). NAO sao as mesmas linhas |
| `amostra_<Usina>_5min.csv` | ~1.000 | 0,3 MB | **8 dias inteiros** espalhados pelos anos, do nublado ao limpo |

**Para so conferir o que entra no modelo, abra a `amostra_`.** Sao dias
completos de 5 em 5 minutos, abre instantaneo e ja mostra a forma do dia.

**Para conferir linha a linha contra o parquet, gere o `base_<Usina>_5min.csv`**
com `python base_modelagem/referencia/gerar_csv_espelho.py`. Ele e gravado a
partir do proprio parquet e verificado na volta: mesmas 362.996 linhas, mesmas
28 colunas, diferenca maxima de 4,6e-13 (so arredondamento do texto). Sao 105 MB,
por isso nao ficam na pasta.

**Cuidado com o `_horaria.csv`.** Ele tem as mesmas colunas, mas cada linha e a
media de uma hora: 11 vezes menos linhas. Serve para olhar tendencia no Excel,
nao para conferir o que o modelo recebeu. Se for usar para treinar, troque a
linha no bloco `1. CONFIGURACAO`:

    caminho_arquivo = r'base_Cascavel_horaria.csv'   # em vez do .parquet

O `dicionario_colunas.csv` explica cada uma das 28 colunas, com unidade, faixa
e percentual de faltantes.

### O que o script gera

Cria a pasta `resultados_<usina>/` com **4 figuras PNG** e **3 arquivos CSV**:

| Arquivo | Conteudo |
|---|---|
| `comparacao_modelos_*.png` | R2 e MAE de cada modelo, lado a lado |
| `previsto_x_real_*.png` | dispersao de 5 min, agregado diario e histograma de residuos |
| `erro_por_condicao_*.png` | erro por faixa de nebulosidade e por hora do dia |
| `importancia_*.png` | importancia das variaveis por permutacao |
| `metricas_*.csv` | a tabela de R2 / MAE / RMSE / tempo |
| `previsao_diaria_*.csv` | energia real x prevista, dia a dia |
| `importancia_*.csv` | a importancia em numeros |

Os graficos abrem na tela (`plt.show()`) **e** sao salvos em disco.

### Resultados de referencia (ja medidos nesta base)

| Usina | melhor modelo | R2 (5 min) | MAE | R2 diario | MAE diario |
|---|---|---:|---:|---:|---:|
| Cascavel | HistGradientBoosting | 0,804 | 316 W (8,0 %) | 0,911 | 1,40 kWh (8,7 %) |
| Curitiba | HistGradientBoosting | 0,715 | 804 W (8,4 %) | 0,799 | 3,99 kWh (13,9 %) |

Tempo: cerca de 15 s por usina com `RODAR_LENTOS = False`, num notebook comum.
Se os seus numeros baterem com estes, a instalacao esta correta.

---

## Quatro avisos que economizam tempo

**1. Vazamento de dados.** No arquivo bruto do inversor, `energia_Wh`,
`producao_fotovoltaica_Wh`, `rendimento_especifico` e (em Curitiba)
`MPP1 + MPP2` são o mesmo número que o alvo, com no máximo 0,01 Wh de diferença.
`potencia_aparente × fator_potencia` reconstrói o alvo com r = 0,9996. Um modelo
com essas colunas chega a R² = 0,9999 e não prevê nada — está lendo a resposta.
**Já foram removidas da base de modelagem.** Não as traga de volta.

**2. Nunca use `train_test_split` aleatório.** Registros de 5 minutos têm
autocorrelação de 0,90 no passo seguinte e 0,48 uma hora depois. Medido nesta
base: R² 0,839 no k-fold aleatório contra 0,799 num período futuro real. O
script já separa por data e traz um `GroupKFold` agrupado por dia para comparar.

**3. O alvo não é estacionário.** A usina de Cascavel foi ficando suja e foi
limpa duas vezes; a de Curitiba teve uma falha numa string e uma reconfiguração.
O índice de desempenho anual vai de 0,66 a 0,50 e volta a 0,66. Treinar em
período sujo e testar em período limpo dá resultado ruim sem que o modelo
esteja errado. Use `estado_sujeira` como variável, ou treine só no regime atual.

**4. Curitiba: potência e geometria são ESTIMADAS.** A planilha divide por
12,000 kWp, que é a potência CA do inversor e não a do arranjo. Estimativa
própria: ~9,6 kWp. O ajuste de orientação falha nesse site (R² 0,52/0,59 contra
0,89 em Cascavel) porque o telhado não é um plano único por string. Todo número
por kWp de Curitiba é provisório.

---

## Fatos úteis que não estão na documentação de ninguém

- **NASA POWER horária**: o carimbo "LST" alinha em **−55 minutos** contra o
  relógio do inversor (a correção de longitude sozinha daria −35). Verificado
  por agregação, r = 0,947 em 38.010 horas.
- **NASA POWER diária** lê **3,2 % abaixo** da irradiância real em dias claros,
  com ciclo sazonal de 4,1 pontos. É o piso de erro de qualquer modelo que a use.
- **Azimute não é recuperável de totais diários** — a função objetivo é
  exatamente simétrica em torno do norte. Só com dados sub-diários.
- Duas coordenadas a 19 km de distância caem na mesma célula da NASA POWER e
  retornam dados idênticos. Não vale a pena refinar a localização.

---

## Ordem do pipeline (se for refazer)

Cada script roda de qualquer pasta (`python analise/cascavel/scripts/build5.py`).
Os nomes curtos dentro deles ("frame5.parquet", "figs5/...") passam por
`caminho()`, em `analise/comum/scripts/caminhos.py`, que aponta para `dados/`,
`figuras/`, `relatorios/` ou `dados_brutos/`.

**Cascavel** (`analise/cascavel/scripts/`)

    merge_5min.py                 7 exportações anuais -> dados_5min_2019-2026.csv + .parquet
    fetch_power2.py, fetch_hourly.py   NASA POWER diária e horária (rede + truststore)
    build2.py -> changepoint.py -> estimate.py -> billing.py      série diária, regimes, fatura
    build5.py -> h1_align.py      frame5.parquet e frame5h.parquet (5 min + NASA horária)
    a1..a6, dq1..dq4, ml1..ml3, h2..h4    diagnóstico, qualidade, modelos
    viz_*.py, viz5.py             figuras 01-28
    export_data.py                payload.json + relatorios/explorador.html
    make_report.py, make_report5.py      relatorios/relatorio.html e relatorio_5min.html

**Curitiba** (`analise/curitiba/scripts/`)

    merge_curitiba.py -> fetch_curitiba.py -> build_curitiba2.py -> dq_curitiba.py
    -> curitiba_analysis2.py -> viz_curitiba.py

**Comparativo** (`analise/comparativo/`): `compare_sites.py`, `make_report2sites.py`

**Base de modelagem** (`base_modelagem/referencia/`, depois das duas usinas)

    build_base_modelagem.py       frame5h + curitiba_frame5 -> ambas_usinas/base_modelagem_*
    gerar_scripts_por_usina.py    separa por usina e gera Modelos_Regressao_<Usina>.py
    comparar_modelos.py -> aplicar_melhor_modelo.py      13 algoritmos, grava o vencedor
    gerar_csv_espelho.py          base_<Usina>_5min.csv (espelho do parquet) e amostra_
    ablacao_preditores.py, sensor_irradiancia.py, compara_modelos_embarcado.py
    amplia_documentacao.py -> divide_documentacao.py     Documentacao_*.xlsx

`frame5.parquet` e `frame5h.parquet` (Cascavel) não ficam guardados: são
intermediários de ~30 MB que `build5.py` e `h1_align.py` refazem em segundos.
As figuras reduzidas para embutir nos HTML vão para `analise/_temp/`, que pode
ser apagada.

---

## Principais achados

**Cascavel (Usina Cascavel, 3,96 kWp, 2019–2026)** — a queda de desempenho de
0,89 para 0,71 entre 2021 e 2023 foi **sujeira progressiva**, não degradação:
a corrente CC caiu 16 % enquanto a tensão da string ficou estável em 1 %, e a
limpeza de novembro de 2023 devolveu +28 % em sol alto e +54 % em sol baixo — a
assinatura angular de uma camada de sujeira. A inclinação de 13° é a causa: sem
declive, a chuva não lava. Perda acumulada de 6.365 kWh, mas sem impacto
financeiro relevante, porque a usina gera 2,6× o consumo e os créditos expiram.

**Curitiba (Usina Curitiba, ~9,6 kWp, 2021–2026)** — de dezembro de 2022 a julho
de 2023 a string 1 perdeu 50 % da corrente enquanto a string 2 perdeu 18 %:
falha específica de uma string, e não da usina. Em junho de 2025 as tensões das
duas entradas trocaram de patamar (−19 % e +21 %, soma constante): módulos foram
remanejados entre as entradas, e a potência CC subiu 15 % logo depois.

O detalhe que separa os dois casos é o número de rastreadores MPPT: com dois,
uma string serve de controle para a outra.
