# Plano de publicação — revisão do projeto para artigo

Revisão feita em 23/09/2026 sobre todo o conteúdo da pasta. Complementa o
`ESTADO_DO_PROJETO.md`: aquele diz onde paramos, este diz o que falta para
virar artigo de periódico.

---

## 1. A história: dois artigos, não um

**Artigo A (principal) — "A qualidade da entrada, não o algoritmo, limita a
estimativa de potência FV a partir de reanálise."** A evidência já existe:

- Uma única variável física (`poa_estimada`) num modelo **linear** entrega
  99,6% do R² do modelo completo em Cascavel e 95% em Curitiba. Trocar de
  algoritmo vale ~0,03 de R²; ter essa variável vale 0,24.
- Um canal de irradiância fecha 99% do vão entre o modelo sem clima e o modelo
  completo com NASA. As outras oito variáveis da NASA valem ~1%.
- Downscaling da NASA horária para 5 min por inversão da potência não ajuda
  (−0,011 e −0,008 de R²). A versão que "ajuda" (R² 0,9999) é vazamento.
  Resultado negativo, raro e útil.
- O kc horário da NASA tem R² **negativo** contra o kc medido, mas 79–83% da
  variância de 5 min seria recuperável de uma boa fonte horária. O problema é
  a qualidade da NASA, não a resolução.
- O embarcado em TFLite (3,4 KB, R² 0,81) entra como consequência prática.

**Artigo B — diagnóstico de falhas só com dados do inversor, sem sensor de
irradiância.** Artigo de estudo de caso:

- Cascavel: sujeira e não degradação (separação corrente × tensão CC,
  recuperação dependente do ângulo após limpeza), 13° de inclinação como causa
  raiz, dente de serra recorrente.
- Curitiba: falha restrita à string 1 e reconfiguração posterior, detectadas
  usando as duas entradas MPPT como controle uma da outra.
- Periódicos: *Progress in Photovoltaics*, *Solar Energy*, *IEEE Journal of
  Photovoltaics*.

Juntar os dois num manuscrito enfraquece ambos.

---

## 2. O que um revisor vai apontar (corrigir antes de escrever)

1. **Os números principais vêm de protocolos diferentes.** O comparativo de 13
   algoritmos (HistGB 0,8047, `referencia/comparar_modelos.py`) usa geometria +
   clima diário + sujeira, **sem NASA horária**, em 51.538 linhas de teste. A
   ablação, o sensor e o embarcado (HistGB 0,8199) usam a horária, em 43.889
   linhas. Precisa de **um protocolo congelado** e tudo reexecutado nele. Hoje
   "HistGB escolhido como melhor" e "linear basta" são medidos em conjuntos de
   variáveis diferentes.
2. **Um único corte treino/teste, sem incerteza.** Teste ≈ ago/2025 a mai/2026
   (com horária), um período por usina. Falta:
   - avaliação com origem móvel (treino até o ano N, teste no ano N+1);
   - intervalos de confiança por bootstrap em blocos diários;
   - teste de Diebold–Mariano entre modelos.

   Sem isso, 0,8199 contra 0,8228 não é interpretável.
3. **Métricas fora da convenção FV.** Revisores de solar esperam nRMSE, nMAE,
   MBE e *skill score* contra um modelo de referência (Yang et al., 2020,
   verificação de previsões solares determinísticas). A referência que falta é
   um **modelo físico de base**: pvlib ou PVWatts com as mesmas entradas da
   NASA. Se o linear com `poa_estimada` empatar com ele, isso **reforça** a
   tese. O `pvlib` não está instalado.
4. **Enquadramento.** Não é previsão: NASA POWER é reanálise e chega com
   atraso. Chamar de estimativa, modelo de potência esperada ou sensor virtual.
   Só o cenário D (persistência de 1 h) é *nowcast* de verdade.
5. **`estado_sujeira` sai do alvo.** A defasagem de 1 dia evita vazamento, mas
   no teste ele usa a produção observada — é realimentação do estado da usina.
   Declarar e rodar com e sem ele.
6. **Metadados de Curitiba.** kWp estimado (9,6) e telhado de dois planos
   modelado como um. Ou conseguir o mapa de strings do instalador, ou
   transformar em contribuição: caso de "metadados desconhecidos", em que o
   HistGB bater o linear mostra o modelo corrigindo a física errada.
7. **Latência do embarcado medida só em x86.** Medir num MCU real (ESP32 ou
   Cortex-M) ou reportar só tamanho e acurácia.
8. **Consentimento e anonimato.** Os nomes dos proprietários aparecem nos
   arquivos. Renomear para Usina A e B e obter consentimento por escrito antes
   de publicar os dados.

---

## 3. Experimentos que sobem o nível do artigo

- **Irradiância medida em solo.** O INMET tem estações automáticas nas duas
  cidades com piranômetro e radiação global horária (códigos a confirmar). Com
  isso:
  - a NASA é validada contra medição, não só por agregação;
  - o experimento do piranômetro passa de estimado a medido.

  É o maior ganho isolado.
- **Fonte de satélite no lugar da NASA** — CAMS ou NSRDB (confirmar cobertura
  das duas usinas), ou ERA5 como segunda reanálise. Se o R² subir com o mesmo
  modelo, a tese central fica demonstrada em vez de inferida.
- **RdTools em Cascavel**: taxa de degradação ano a ano e algoritmo SRR de
  sujeira, comparados com o método de pontos de mudança. Revisores de FV
  conhecem essas ferramentas.
- **Confirmar datas de limpeza com o proprietário** (nov/2023 e set/2024) para
  validar a detecção. Cruzar chuva × autolimpeza com `chuva_diaria` para
  sustentar o argumento dos 13°.
- **Figura do deslocamento de −55 min da NASA** (correlação cruzada × defasagem).
  Achado não documentado que outros vão citar.

---

## 4. Arrumação antes da submissão

- ~~`git init`~~ feito em 28/09 na raiz `Projeto_IA/` (dados pesados fora, ver
  `.gitignore`); falta o primeiro commit. Arquivar versão com DOI no Zenodo com
  a base anonimizada.
- ~~Duplicatas e `catboost_info/`~~ — lista de remoção entregue em 28/09; o
  CatBoost não grava mais `catboost_info/`.
- ~~`relatorio.html` desatualizado~~ — regenerado em 28/09.
- ~~Pipeline só rodava na pasta plana original~~ — corrigido em 28/09 e
  verificado do bruto às bases de modelagem.
- Concentrar o pipeline do artigo numa pasta `paper/` que reconstrói todas as
  tabelas e figuras a partir de `base_modelagem/`.

---

## Ordem sugerida

1. Congelar um protocolo e reexecutar com origem móvel, IC e base pvlib — o
   resto depende disso. Primeiro entregável: `paper/protocolo_canonico.py`
   (convenções do projeto) gerando a tabela-mestre com IC.
2. Obter os dados do INMET e uma fonte de satélite.
3. Resolver os metadados de Curitiba, ou reenquadrar como caso de metadados
   desconhecidos.
4. Esboçar o Artigo A com a skill `paper-writing`.
