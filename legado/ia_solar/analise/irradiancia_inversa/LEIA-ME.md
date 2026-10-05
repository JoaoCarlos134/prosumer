# Irradiância estimada a partir da potência — o que ela resolve e o que não resolve

Teste da proposta: inverter `P = G·A·η` para obter irradiância a 5 min e usar
isso para "quebrar" a NASA POWER em 5 min, melhorando o modelo.

`estima_irradiancia.py` roda as duas usinas. Divisão treino/teste em 01/08/2025,
a mesma do resto do projeto. HistGradientBoosting com `random_state=42` e o resto
no padrão, como no `Projeto_solo`.

## Os quatro cenários

| | Cenário | Cascavel R² | Curitiba R² |
|---|---|---|---|
| **A** | base atual (NASA horária + diária + geometria) | 0,8199 | 0,7483 |
| **B** | + `G_inv` do mesmo instante | **0,9999** | **0,9999** |
| **C** | + POA reconstruída por ML, sem usar potência | 0,8091 | 0,7404 |
| **D** | + `G_inv` defasada de 1 hora | 0,8344 | 0,7656 |

## Leitura

**B é vazamento, não resultado.** `G_inv` sai de `potencia_ca_W` por uma
transformação quase monotônica. Pedir ao modelo que preveja a potência com ela
entre os preditores é pedir que copie a resposta. O R² 0,9999 é a prova
aritmética disso, não um ganho.

**C é o teste honesto e ele não ganha.** Treinar um modelo para prever o kc de
5 min a partir de NASA + geometria (usando `G_inv` só como alvo de treino) e
depois alimentar a POA reconstruída ao modelo de potência **piora** o resultado:
−0,011 em Cascavel e −0,008 em Curitiba. O downscaling não cria informação: ele
reorganiza a que já está nos preditores, e o gradient boosting já fazia essa
combinação sozinho.

**D ganha, mas muda a pergunta.** Usar a irradiância medida uma hora antes vale
+0,015 e +0,017 de R², e no acumulado diário vale bem mais: 0,908 → 0,943 e
0,878 → 0,930. Só que isso é *nowcast* — exige a usina rodando e medida
recente. Não serve para simular um ano a partir de clima, que é o caso do HOMER.

## O número que fecha o assunto

Decompondo a variância do kc de 5 min entre o que varia **entre horas** e o que
varia **dentro da hora**:

| | Cascavel | Curitiba |
|---|---|---|
| entre horas — recuperável de um dado horário | 83,3 % | 79,0 % |
| dentro da hora — invisível para qualquer dado horário | 16,7 % | 21,0 % |

Ou seja: o teto de um dado horário *perfeito* é alto (R² 0,795 e 0,783 contra o
kc medido). O problema não é a resolução temporal da NASA — é a qualidade dela.

| kc de 5 min previsto por | Cascavel | Curitiba |
|---|---|---|
| kc horário cru da NASA | **−0,38** | **−0,59** |
| modelo C (NASA + geometria) | 0,54 | 0,62 |
| média horária perfeita do kc medido | 0,795 | 0,783 |

O kc horário da NASA tem R² **negativo** contra o kc medido: é pior que prever a
média. O modelo C conserta boa parte disso — mas o ganho morre na hora de prever
potência, porque o modelo de potência já tinha as mesmas entradas.

## Onde `G_inv` é de fato útil

Não como preditor. Como **produto de dado**:

- série de POA a 5 min do que a usina realmente viu, para diagnóstico de
  sujeira e sombreamento (é o que separa Cascavel de Curitiba nas faixas de kc);
- aferição da NASA em resolução sub-horária, que até aqui só tinha sido feita
  por agregação;
- alvo de treino para downscaling, que foi o uso testado em C.

Fica em `irradiancia_inversa_<usina>.parquet`.

## Ressalvas do método

- **O `+38%` (Cascavel) e `+60%` (Curitiba) de diferença entre a NASA e `G_inv`
  não são erro da NASA.** `G_inv` carrega junto tudo que o K constante não
  captura: sombreamento que varia com a hora, sujeira que varia com a estação,
  descasamento de strings. O achado anterior do projeto — NASA diária lendo 3,2%
  *abaixo* do real em dias claros — continua valendo; é outra medida.
- **Curitiba está inflada.** O `poa_ceu_claro` de lá usa um plano único, e o
  telhado tem dois (pendência 2 do `ESTADO_DO_PROJETO.md`). Parte dos 60% é esse
  erro de geometria, não irradiância.
- **K é calibrado, não medido, e deu maior que 1.** Ajustado para que o
  percentil 98 de `G_inv/poa_ceu_claro` caia em 1,0: resultou **1,122** em
  Cascavel e **1,042** em Curitiba. Um "fator de perdas" acima de 1 é sinal de
  que a âncora está errada — o percentil 98 pega momentos de *cloud enhancement*,
  os picos de borda de nuvem que passam do céu claro. O efeito é uma escala de
  `G_inv` um pouco alta. Isso não muda nenhuma conclusão desta análise, porque os
  quatro cenários usam a mesma `G_inv` e o que está em jogo é conteúdo de
  informação, não escala. Mas invalida `G_inv` como medida absoluta de
  irradiância: para isso, ancorar em dias claros filtrados, não num percentil.
- **A temperatura de célula é modelada**, não medida: `T_c = T_ar + 0,03125·G`
  (NOCT 45 °C), com `T_ar` horária da NASA. Sem sensor na traseira do módulo,
  essa é a maior fonte de incerteza na inversão.
- **γ = −0,004/°C** vem da ficha técnica de Cascavel e foi reaproveitado em
  Curitiba, onde não há datasheet.

## Conclusão

Quebrar a NASA em 5 min pela potência não melhora o modelo, e a versão que
"melhora" é vazamento. O que move o ponteiro, em ordem de tamanho:

1. **Um piranômetro ou célula de referência na usina.** Medido depois, em
   `base_modelagem/referencia/sensor_irradiancia.py`: um único canal de
   irradiância fecha **99% do vão** entre o modelo embarcado e o completo,
   +0,22 de R². **Correção:** eu havia escrito aqui que o piranômetro valia
   +0,18 e +0,25, tirado da distância de A até B. Aquele número é otimista
   demais — o `G_inv` do cenário B carrega junto o estado da usina (sujeira,
   sombreamento, eficiência do inversor), que um piranômetro não mede. O piso
   medido é +0,22; o teto não é mensurável sem o sensor.
2. **Uma fonte horária melhor que a NASA POWER** (satélite geoestacionário:
   CAMS, SARAH-3, Solcast, INPE). 79–83% da variância de 5 min é recuperável de
   um dado horário bom; a NASA só não é bom.
3. **Resolver a geometria de Curitiba**, que é pré-requisito para qualquer
   medida de irradiância fazer sentido lá.
