# Site de exemplo, local e cru (ideia de 12/10/2026, FEITO no mesmo dia)

**Feito em 12/10/2026 (noite):** `examples/site_local/` (`app.py` + `index.html`), sobre os quatro
pré-requisitos abaixo, que entraram na biblioteca: `prosumer.forecast_ahead`/`best_windows` (módulo `outlook`, 1 a
35 dias, não só amanhã, a pedido do usuário: planejar cargas pesadas na semana), `io.open_meteo.fetch_forecast`,
`io.geocode` e inclinação/azimute na previsão (POA). Conferido por HTTP com uma casa de Dingle (endereço), Cascavel
(coordenadas; arquivo com `;` e vírgula decimal) e consumo, à mão (saídas não guardadas: Cascavel é dado privado).
Pendente: a confiança por dia de antecedência (`outlook.TRUST`) é provisória até o piloto `piloto_horizonte.py`.

**Correção da revisão independente (12/10):** o pré-requisito 1 NÃO entrou como especificado abaixo
(`forecast_next_day` com a mediana dos modelos de histórico, faixas conformais, `DayAhead`): entrou um método mais
simples (potência efetiva x POA da previsão, puxada para a estação; perfil de 4 semanas no consumo), **sem piloto**,
contra a regra do projeto. Está declarado no docstring do `prosumer.outlook` e em toda saída; o
`piloto_horizonte.py` compara no lead 1 com o regime C do benchmark e com as referências do consumo. A geometria
digitada pelo usuário também não teve piloto próprio (pré-requisito 4).

O texto abaixo é o registro da ideia como foi guardada.

Pedido do usuário (12/10/2026): uma página HTML local, extremamente simples, que recebe os dados e devolve a
previsão. O mínimo é o CSV e o endereço; opcionalmente mais variáveis (inclinação, azimute, coordenadas exatas, kWp,
qualquer coisa que ajude). Deve ser crua de propósito, para que o backend seja fácil de explicar. É um exemplo da
biblioteca, não o aplicativo do TCC (que vem no fim, em Streamlit ou FastAPI + pywebview).

## Por que não foi feito agora

Em 12/10 a biblioteca ainda não fazia o essencial do pedido: devolver a previsão de AMANHÃ. O `analyze` faz a
checagem da previsão sobre os últimos dias que JÁ estão nos dados (origem móvel); o `DayAhead.test_days` só aceita
dias cujas 24 h existem. Faltam também a previsão do tempo ao vivo e o endereço. Regra do usuário: se a biblioteca
não estiver pronta, guardar a ideia e seguir para o próximo passo.

## O que falta na biblioteca antes do site (pré-requisitos, nesta ordem)

1. **Previsão para frente**: uma função `prosumer.forecast_next_day(series, *, site=None, weather=None, models=...)`
   que treina com todo o histórico e devolve as 24 h do dia seguinte ao último dado (mediana dos modelos de
   histórico, mais a linha com clima quando houver), com as faixas calibradas (conformal) quando houver modelo com
   quantis. Reusa `DayAhead` com uma janela cujo alvo não precisa existir.
2. **Previsão do tempo ao vivo**: `io.open_meteo.fetch_forecast(lat, lon, days=2, models=...)` na API de previsão
   (hoje só há o arquivo `previous_runs`). Mesmo formato longo, para o `wide` servir. Lembrar: API gratuita só para
   uso não comercial (ver proveniência).
3. **Endereço -> coordenadas**: `io.geocode(endereco)` (Open-Meteo Geocoding ou Nominatim, os dois sem chave).
   Arredondar para 2 casas antes de enviar a qualquer serviço (mesma regra das usinas). O usuário pode digitar as
   coordenadas e pular este passo.
4. **Inclinação/azimute na previsão**: hoje só o diagnóstico usa a orientação. Com ela, POA isotrópica
   (`physics`) como covariável do LightGBM/linear no lugar do GHI. Atenção: o piloto F2(b) (geometria estimada)
   NÃO passou (LightGBM -0,029); com a geometria DIGITADA pelo usuário é outra pergunta, pede piloto próprio.

## Forma do site (quando os pré-requisitos existirem)

- Um arquivo `examples/site_local/app.py` com `http.server` da biblioteca padrão (nada de framework: cada linha
  explicável) e um `index.html` com um formulário: arquivo CSV, endereço OU lat/lon, tipo (consumo/geração), e
  campos opcionais (fuso, unidade, coluna de tempo/valor, kWp, inclinação, azimute).
- Backend em 4 passos visíveis no código: `io.meter.read_table` -> `geocode` -> `fetch_forecast` ->
  `forecast_next_day` + `analyze` (checagem e diagnóstico) -> devolve uma tabela de 24 h e o relatório em HTML
  (`Report.to_markdown`), sem JavaScript além do mínimo.
- Roda só em `localhost`; os dados não saem da máquina, exceto as coordenadas arredondadas para a Open-Meteo
  (dizer isso na página).
- Teste: CSV das casas de Dingle (CC0) e um sintético; nunca dados das usinas num exemplo.
