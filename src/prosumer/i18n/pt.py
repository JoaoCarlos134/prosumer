"""The Portuguese (Brazil) catalog of `prosumer.i18n`: each English template of a `Note` and its translation.

Data only: the same placeholders as the English template (a test checks it, and that every template in the
code is here), grouped by the module that writes them. Numbers and dates are formatted the Brazilian way when
rendered; numbers written inside the text itself are written here as they are read in Portuguese.
"""

from __future__ import annotations

PT: dict[str, str] = {
    # ---- analysis
    "not declared": "não declarada",
    (
        "Not modelled: COSIP read from a bill (type it as `brazil.Setup(cosip=...)`), grupo A (demand "
        "charges), the tax reform of LC 214/2025."
    ): (
        "Não modelado: a COSIP lida de uma conta (informe-a em `brazil.Setup(cosip=...)`), o grupo A "
        "(cobrança de demanda), a reforma tributária da LC 214/2025."
    ),
    "pass `weather=io.open_meteo.wide(...)` (Open-Meteo, several models)": (
        "passe `weather=io.open_meteo.wide(...)` (Open-Meteo, vários modelos)"
    ),
    "weather (regimes B and C)": "previsão do tempo (regimes B e C)",
    "bands (quantiles)": "faixas (quantis)",
    "pass a model with quantiles, e.g. `models=[forecast.LightGBMQuantile()]`": (
        "passe um modelo com quantis, p. ex. `models=[forecast.LightGBMQuantile()]`"
    ),
    "diagnostics": "diagnóstico",
    "pass `site=(lat, lon)` with a generation series: clear-day performance and its changes": (
        "passe `site=(lat, lon)` com uma série de geração: o desempenho em dias de céu limpo e suas mudanças"
    ),
    "economics": "conta de energia",
    (
        "pass `economics=` (an `economics.Tariff`, `economics.Plan` or `economics.brazil.Setup`) with the "
        "consumption (the series, or `consumption=` next to a generation series): the monthly bill, and the "
        "savings with `generation=`. {left}"
    ): (
        "passe `economics=` (um `economics.Tariff`, `economics.Plan` ou `economics.brazil.Setup`) com o "
        "consumo (a série, ou `consumption=` ao lado de uma série de geração): a conta mensal e, com "
        "`generation=`, a economia. {left}"
    ),
    "soiling vs shading and string faults need DC or 5-minute data (not yet)": (
        "sujeira x sombreamento e falhas de string precisam de dados CC ou de 5 minutos (ainda não)"
    ),
    "Forecast check skipped: {reason}": "Conferência da previsão não feita: {reason}",
    "every value is zero (a dead meter or inverter, or the wrong column).": (
        "todos os valores são zero (medidor ou inversor parado, ou a coluna errada)."
    ),
    (
        "every test hour it would score is zero (did the meter or inverter stop in the last {days} days?), "
        "so the normalised errors are undefined."
    ): (
        "toda hora de teste que ela avaliaria é zero (o medidor ou o inversor parou nos últimos {days} "
        "dias?), então os erros normalizados não estão definidos."
    ),
    "it needs {days} days of history before the {test_days} test days.": (
        "ela precisa de {days} dias de histórico antes dos {test_days} dias de teste."
    ),
    "no test day has all its target hours measured.": "nenhum dia de teste tem todas as horas-alvo medidas.",
    "{name} needs a weather forecast (`weather=`): left out.": (
        "{name} precisa de uma previsão do tempo (`weather=`): ficou de fora."
    ),
    (
        "The output (`{output}`) is the median of the {n} naive forecasts only. In the benchmark that median "
        "ranked 29th to 36th of ~53; with the library's five models added (`models=[LightGBM(), Chronos2(), "
        "TiRex2(), Toto2(), FlowState()]`) it came within 0.01 of the median of all 47 benchmark models in "
        "the three history-only tests, still short of the best model in two of them (pilot of 2026-10-16)."
    ): (
        "A saída (`{output}`) é a mediana só das {n} previsões ingênuas. No benchmark essa mediana ficou "
        "entre a 29ª e a 36ª posição de ~53; com os cinco modelos da biblioteca (`models=[LightGBM(), "
        "Chronos2(), TiRex2(), Toto2(), FlowState()]`) ela chegou a 0,01 da mediana de todos os 47 modelos "
        "do benchmark nos três testes só com histórico, ainda abaixo do melhor modelo em dois deles (piloto "
        "de 16/10/2026)."
    ),
    (
        "`{output}` is the median of the {n} forecasts that use the weather ({rows}). Measured on one test "
        "only, the benchmark's two plants (24 rows): the medians of two to four of the library's weather "
        "rows ranked 1st to 11th and beat each of their members in 10 of 11 compositions; the four together "
        "ranked 1st (+0.372), LightGBM with the linear model 9th (+0.346; +0.330 and +0.312 alone) "
        "(2026-10-16 and 2026-10-19). Measured on the benchmark's saved forecasts, whose linear model fits "
        "the irradiance on the plane of the modules; this one (`weather_linear`) fits the mean GHI."
    ): (
        "`{output}` é a mediana das {n} previsões que usam o tempo ({rows}). Medido em um único teste, as "
        "duas usinas do benchmark (24 linhas): as medianas de duas a quatro das linhas com tempo da "
        "biblioteca ficaram entre a 1ª e a 11ª posição e superaram cada um de seus membros em 10 de 11 "
        "composições; as quatro juntas ficaram em 1º (+0,372), o LightGBM com o modelo linear em 9º (+0,346; "
        "+0,330 e +0,312 sozinhos) (16/10/2026 e 19/10/2026). Medido nas previsões salvas do benchmark, cujo "
        "modelo linear usa a irradiância no plano dos módulos; este (`weather_linear`) usa o GHI médio."
    ),
    "{n} test hours without a forecast from every model left out of every row.": (
        "{n} horas de teste sem a previsão de todos os modelos ficaram fora de todas as linhas."
    ),
    (
        "the series repeats exactly: the reference ({reference}) is perfect on every test hour, so the skill "
        "is undefined. A stuck meter, a fixed estimate or synthetic data?"
    ): (
        "a série se repete exatamente: a referência ({reference}) acerta todas as horas de teste, então o "
        "skill fica indefinido. Um medidor travado, uma estimativa fixa ou dados sintéticos?"
    ),
    "{name}+conformal: {n} test days without 7 days of past errors were left as the model gave them.": (
        "{name}+conformal: {n} dias de teste sem 7 dias de erros anteriores ficaram como o modelo os deu."
    ),
    (
        "Generation without a site: the reference is 'same as yesterday', weaker than the clear-sky "
        "persistence of the benchmark. Pass site=(lat, lon) for the benchmark's reference."
    ): (
        "Geração sem local: a referência é 'igual a ontem', mais fraca que a persistência de céu limpo do "
        "benchmark. Passe site=(lat, lon) para ter a referência do benchmark."
    ),
    (
        "The output is biased by {bias:+.0%} of the mean (MBE). `{corrected}` removes it, but in the "
        "benchmark that raised the skill only for a median of ~40 models; with few models it lowered it."
    ): (
        "A saída tem um viés de {bias:+.0%} da média (MBE). `{corrected}` o remove, mas no benchmark isso só "
        "aumentou o skill da mediana de ~40 modelos; com poucos modelos, o diminuiu."
    ),
    "The output is biased by {bias:+.0%} of the mean (MBE).": (
        "A saída tem um viés de {bias:+.0%} da média (MBE)."
    ),
    "series": "série",
    "consumption": "consumo",
    "generation": "geração",
    (
        "The {what} came in steps of {freq}: summed into hours (an hour counts when at least 11/12 of it was "
        "measured); everything here is hourly."
    ): (
        "Os dados ({what}) vieram em passos de {freq}: somados em horas (uma hora conta quando ao menos "
        "11/12 dela foram medidos); tudo aqui é horário."
    ),
    (
        "Diagnostics: the change-point penalty ({penalty:g} x the BIC's) was chosen on two plants in Parana "
        "(Brazil) and ten PV houses in Ireland, and the clear-day rule was set by hand on the same plants; "
        "elsewhere they are assumptions (`analyze(diagnostics_options=...)` changes them)."
    ): (
        "Diagnóstico: a penalidade dos pontos de mudança ({penalty:g} x a do BIC) foi escolhida em duas "
        "usinas no Paraná (Brasil) e dez casas com FV na Irlanda, e a regra de dia de céu limpo foi ajustada "
        "à mão nas mesmas usinas; em outros lugares, são suposições (`analyze(diagnostics_options=...)` as "
        "altera)."
    ),
    (
        "Diagnostics: the change-point penalty ({penalty:g} x the BIC's) was chosen on two plants in Parana "
        "(Brazil) and ten PV houses in Ireland; elsewhere it is an assumption "
        "(`analyze(diagnostics_options=...)` changes it)."
    ): (
        "Diagnóstico: a penalidade dos pontos de mudança ({penalty:g} x a do BIC) foi escolhida em duas "
        "usinas no Paraná (Brasil) e dez casas com FV na Irlanda; em outros lugares, é uma suposição "
        "(`analyze(diagnostics_options=...)` a altera)."
    ),
    (
        "Diagnostics: the clear-day rule was set by hand on two plants in Parana (Brazil); elsewhere it is "
        "an assumption (`analyze(diagnostics_options=...)` changes it)."
    ): (
        "Diagnóstico: a regra de dia de céu limpo foi ajustada à mão em duas usinas no Paraná (Brasil); em "
        "outros lugares, é uma suposição (`analyze(diagnostics_options=...)` a altera)."
    ),
    (
        "Licence unknown for: {inputs}. Find it out before sharing or publishing these results "
        "(`EnergySeries.from_dataframe(provenance=...)`; `prosumer.provenance.attach` for a weather frame)."
    ): (
        "Licença desconhecida para: {inputs}. Descubra-a antes de compartilhar ou publicar estes resultados "
        "(`EnergySeries.from_dataframe(provenance=...)`; `prosumer.provenance.attach` para uma tabela de "
        "tempo)."
    ),
    "The {role} {name!r} is for non-commercial use only ({license}; {conditions}).": (
        "Uso apenas não comercial: {role} {name!r} ({license}; {conditions})."
    ),
    "These models send the series outside this machine: {names} (model card).": (
        "Estes modelos enviam a série para fora desta máquina: {names} (ficha do modelo)."
    ),
    "weather": "previsão do tempo",
    "model": "modelo",
    "tariff": "tarifa",
    "`consumption=` and `generation=` are used only with `economics=`: ignored.": (
        "`consumption=` e `generation=` só são usados com `economics=`: ignorados."
    ),
    (
        "Economics left out: the bill needs the household's consumption (`consumption=`); the generation "
        "alone says what the PV made, not what the household paid."
    ): (
        "Conta deixada de fora: a conta precisa do consumo da casa (`consumption=`); a geração sozinha diz o "
        "que o FV produziu, não o que a casa pagou."
    ),
    "Economics left out: {error}": "Conta deixada de fora: {error}",
    (
        "No month with every hour measured for some site: its expected monthly bill (`mean_month`) is not "
        "given."
    ): (
        "Nenhum mês com todas as horas medidas em algum local: a conta mensal esperada dele (`mean_month`) "
        "não é dada."
    ),
    "Bands left out: no evaluated hour where every band exists.": (
        "Faixas deixadas de fora: nenhuma hora avaliada em que todas as faixas existam."
    ),
    (
        "The band of {name} is not calibrated (80% band: {c80:.0%} of the hours, 60%: {c60:.0%}): use "
        "{name}+conformal, which is."
    ): (
        "A faixa de {name} não está calibrada (faixa de 80%: {c80:.0%} das horas; de 60%: {c60:.0%}): use "
        "{name}+conformal, que está."
    ),
    (
        "The band of {name} is not calibrated (80% band: {c80:.0%} of the hours, 60%: {c60:.0%}): do not "
        "read it as a probability."
    ): (
        "A faixa de {name} não está calibrada (faixa de 80%: {c80:.0%} das horas; de 60%: {c60:.0%}): não a "
        "leia como uma probabilidade."
    ),
    "Weather forecast without GHI (`ghi_mean` or `ghi`): no regime C forecast.": (
        "Previsão do tempo sem GHI (`ghi_mean` ou `ghi`): sem previsão de regime C."
    ),
    "Too few sun hours with a weather forecast before the test (48 per series): no regime C.": (
        "Poucas horas de sol com previsão do tempo antes do teste (48 por série): sem regime C."
    ),
    "Coverage below 95% in {n} series: {names}.": "Cobertura abaixo de 95% em {n} série(s): {names}.",
    (
        "The series do not end together: any validation must cut by fold, or later folds re-emit earlier "
        "days (see `DayAhead.check_support`)."
    ): (
        "As séries não terminam juntas: toda validação deve cortar por dobra (fold), ou as dobras seguintes "
        "repetem dias anteriores (veja `DayAhead.check_support`)."
    ),
    # ---- app
    "Unknown request fields {unknown}; the fields are {names}": (
        "Campos desconhecidos no pedido {unknown}; os campos são {names}"
    ),
    "{field} must be a whole number, not {value!r}": "{field} deve ser um número inteiro, não {value!r}",
    "price must be an object, e.g. {{'kind': 'flat', 'price': 0.8}}": (
        "price deve ser um objeto, p. ex. {{'kind': 'flat', 'price': 0.8}}"
    ),
    "Give both the latitude and the longitude, or an address": (
        "Informe a latitude e a longitude, ou um endereço"
    ),
    "Give an address or the latitude and longitude": "Informe um endereço ou a latitude e a longitude",
    "file_times must be 'local' or 'UTC'": "file_times deve ser 'local' ou 'UTC'",
    "days must be in 1-{max}": "days deve estar entre 1 e {max}",
    "load_hours must be in 1-24": "load_hours deve estar entre 1 e 24",
    "load_kw must be positive": "load_kw deve ser positivo",
    "test_days must be >= 2": "test_days deve ser >= 2",
    "models must be one of {sets}": "models deve ser um de {sets}",
    "price.kind must be one of {kinds}": "price.kind deve ser um de {kinds}",
    "Files are keyed by {keys}, not {unknown}": "Os arquivos são identificados por {keys}, não por {unknown}",
    "No file was received: send the generation or the consumption file (or both).": (
        "Nenhum arquivo recebido: envie o arquivo de geração ou o de consumo (ou os dois)."
    ),
    "Site typed: {lat}, {lon}.": "Local digitado: {lat}; {lon}.",
    "Could not look the address up ({error}). Check the connection, or type the coordinates.": (
        "Não foi possível buscar o endereço ({error}). Verifique a conexão ou digite as coordenadas."
    ),
    "Address not found: {address!r}. Type the coordinates instead.": (
        "Endereço não encontrado: {address!r}. Digite as coordenadas."
    ),
    "Address found: {name}.": "Endereço encontrado: {name}.",
    (
        "Could not find the site's time zone ({error}). Check the connection, or give the time zone (e.g. "
        "America/Sao_Paulo)."
    ): (
        "Não foi possível descobrir o fuso horário do local ({error}). Verifique a conexão ou informe o fuso "
        "(p. ex. America/Sao_Paulo)."
    ),
    "Site used (rounded): {lat}, {lon}; time zone {tz}.": (
        "Local usado (arredondado): {lat}; {lon}; fuso horário {tz}."
    ),
    "{file}: read {how}; {hours} hours, {share:.0%} measured.": (
        "{file}: lido assim: {how}; {hours} horas, {share:.0%} medidas."
    ),
    (
        "{file}: the file's clock has every hour of the daylight-saving changes (no gap in "
        "spring, one row for autumn's repeated hour), as a filled-in export writes it: read "
        "without those hours. If the file is in UTC, say so (file_times UTC)."
    ): (
        "{file}: o relógio do arquivo tem todas as horas das mudanças de horário de verão (sem buraco na "
        "primavera, uma linha só para a hora repetida do outono), como uma exportação preenchida escreve: "
        "lido sem essas horas. Se o arquivo estiver em UTC, diga isso (file_times UTC)."
    ),
    (
        "Could not download the weather forecast from Open-Meteo ({error}). Check the connection and try "
        "again."
    ): (
        "Não foi possível baixar a previsão do tempo do Open-Meteo ({error}). Verifique a conexão e tente de "
        "novo."
    ),
    "Weather forecast downloaded: {n} models.": "Previsão do tempo baixada: {n} modelos.",
    "Forecast check with the naive rules and {names}.": (
        "Conferência da previsão com as regras ingênuas e {names}."
    ),
    "Consumption": "Consumo",
    "Generation": "Geração",
    "LightGBM is not installed (`pip install prosumer[lightgbm]`): left out of the forecast check.": (
        "O LightGBM não está instalado (`pip install prosumer[lightgbm]`): ficou fora da conferência da "
        "previsão."
    ),
    "{name} is not installed (its extra, see the install notes): left out.": (
        "{name} não está instalado (é um extra, veja as notas de instalação): ficou de fora."
    ),
    "Give {what}.": "Informe {what}.",
    "the ICMS rate of your bill (a fraction, e.g. 0.19)": (
        "a alíquota de ICMS da sua conta (uma fração, p. ex. 0,19)"
    ),
    "the PIS/COFINS rate of your bill (a fraction, e.g. 0.0925)": (
        "a alíquota de PIS/COFINS da sua conta (uma fração, p. ex. 0,0925)"
    ),
    "ICMS and PIS/COFINS are fractions (0.19 for 19%)": "ICMS e PIS/COFINS são frações (0,19 para 19%)",
    "ICMS + PIS/COFINS must be below 1, not {total:.4g}": (
        "ICMS + PIS/COFINS deve ser menor que 1, não {total:.4g}"
    ),
    "kind must be one of {kinds}, not {value!r}": "kind deve ser um de {kinds}, não {value!r}",
    "Unknown time zone {tz!r}: give an IANA name, e.g. America/Sao_Paulo": (
        "Fuso horário desconhecido {tz!r}: informe um nome IANA, p. ex. America/Sao_Paulo"
    ),
    "price.scheme must be one of {schemes}, not {value!r}": (
        "price.scheme deve ser um de {schemes}, não {value!r}"
    ),
    (
        "With a generation file, give price.gd: 'GD I' (generation connected or its access requested by "
        "{day}) or 'GD II' (later)"
    ): (
        "Com um arquivo de geração, informe price.gd: 'GD I' (geração conectada ou com acesso solicitado até "
        "{day}) ou 'GD II' (depois)"
    ),
    "the COSIP": "a COSIP",
    (
        "Could not download {agent}'s tariffs from ANEEL's open data ({error}). Check the connection, or "
        "give a flat or time-of-use price instead."
    ): (
        "Não foi possível baixar as tarifas da {agent} dos dados abertos da ANEEL ({error}). Verifique a "
        "conexão ou informe um preço único ou por horário."
    ),
    "the export price": "o preço da energia injetada",
    "the fixed charge": "a taxa fixa",
    "the price per kWh": "o preço por kWh",
    "the peak price": "o preço na ponta",
    "the off-peak price": "o preço fora da ponta",
    "time-of-use (peak {start:02d}:00-{end:02d}:00 on weekdays)": (
        "por horário (ponta das {start:02d}:00 às {end:02d}:00 nos dias úteis)"
    ),
    "Peak hours {text!r}: give whole hours as start-end on a 24 h clock, e.g. 17-21": (
        "Horário de ponta {text!r}: informe horas inteiras como início-fim num relógio de 24 h, p. ex. 17-21"
    ),
    "{what}: {value!r} is not a number": "{what}: {value!r} não é um número",
    "Unknown {what} fields {fields}": "Campos desconhecidos em {what}: {fields}",
    "connection must be one of {names} or the minimum in kWh, not {value!r}": (
        "connection deve ser um de {names} ou o mínimo em kWh, não {value!r}"
    ),
    # ---- contracts
    "Empty series: nothing to infer or validate": "Série vazia: nada a inferir ou validar",
    (
        "Series {uid!r}: timestamps impossible in time zone {zone!r} because of daylight saving time "
        "({error}). If the file is in UTC, pass source_tz='UTC'. If it is in local time with the grid filled "
        "in (no gap at the missing hour, a single row at the repeated hour), pass dst='drop'."
    ): (
        "Série {uid!r}: horários impossíveis no fuso {zone!r} por causa do horário de verão ({error}). Se o "
        "arquivo está em UTC, passe source_tz='UTC'. Se está na hora local com a grade preenchida (sem "
        "lacuna na hora que não existe, uma só linha na hora repetida), passe dst='drop'."
    ),
    # ---- diagnostics
    "Series {uid}: too few clear days to fit the roof; no diagnostics.": (
        "Série {uid}: poucos dias de céu limpo para ajustar o telhado; sem diagnóstico."
    ),
    (
        "Series {uid}: panels fitted at {tilt:.0f} degrees tilt facing {azimuth:.0f} degrees (compass; R2 "
        "{r2:.2f} on clear days). The tilt is on the edge of the grid: it is not identified."
    ): (
        "Série {uid}: painéis ajustados com {tilt:.0f} graus de inclinação, voltados para {azimuth:.0f} "
        "graus (bússola; R2 {r2:.2f} nos dias de céu limpo). A inclinação está na borda da grade: não é "
        "identificada."
    ),
    (
        "Series {uid}: panels fitted at {tilt:.0f} degrees tilt facing {azimuth:.0f} degrees (compass; R2 "
        "{r2:.2f} on clear days)."
    ): (
        "Série {uid}: painéis ajustados com {tilt:.0f} graus de inclinação, voltados para {azimuth:.0f} "
        "graus (bússola; R2 {r2:.2f} nos dias de céu limpo)."
    ),
    (
        "Series {uid}: a single plane does not describe this roof well (several planes, or not enough clear "
        "days to tell). The index keeps a seasonal swing: steps are uncertain, and no trend or loss is "
        "reported. Pass the known orientation to diagnose it."
    ): (
        "Série {uid}: um único plano não descreve bem este telhado (vários planos, ou dias de céu limpo "
        "insuficientes para saber). O índice mantém uma oscilação sazonal: os degraus são incertos, e "
        "nenhuma tendência ou perda é relatada. Informe a orientação conhecida para diagnosticá-lo."
    ),
    "Series {uid}: {n} clear days, too few to look for changes over time.": (
        "Série {uid}: {n} dias de céu limpo, poucos para procurar mudanças ao longo do tempo."
    ),
    "Series {uid}: clear-day production stepped {pct:+.0f}% around {when}: {what}.": (
        "Série {uid}: a produção em dias de céu limpo deu um degrau de {pct:+.0f}% por volta de {when}: "
        "{what}."
    ),
    "A step of the same sign comes back at this time of year: it may be seasonal.": (
        "Um degrau do mesmo sinal volta nesta época do ano: pode ser sazonal."
    ),
    "Uncertain (roof fit, see above).": "Incerto (ajuste do telhado, veja acima).",
    (
        "Series {uid}: since {since} the clear-day production falls {pct:.0f}% a year; soiling builds up "
        "like this (a cleaning shows as a step up)."
    ): (
        "Série {uid}: desde {since}, a produção em dias de céu limpo cai {pct:.0f}% ao ano; a sujeira se "
        "acumula assim (uma limpeza aparece como um degrau para cima)."
    ),
    "Series {uid}: the latest period is {pct:.0f}% below the best level seen on clear days.": (
        "Série {uid}: o período mais recente está {pct:.0f}% abaixo do melhor nível visto em dias de céu "
        "limpo."
    ),
    (
        "Series {uid}: clear-day production is {pr:.2f} x the stated peak power: the kWp is too low, or the "
        "clock or the site is wrong."
    ): (
        "Série {uid}: a produção em dias de céu limpo é {pr:.2f} x a potência de pico informada: o kWp está "
        "baixo demais, ou o relógio ou o local estão errados."
    ),
    "a cleaning, a repair or a change to the array": "uma limpeza, um conserto ou uma mudança no arranjo",
    "a fault, new shading or a change to the array": (
        "uma falha, um novo sombreamento ou uma mudança no arranjo"
    ),
    # ---- economics.brazil
    "tariff book {name}: not declared": "tabela tarifária {name}: não declarada",
    "ICMS and PIS/COFINS rates typed by the user": "alíquotas de ICMS e PIS/COFINS digitadas pelo usuário",
    "{kwh:g} kWh": "{kwh:g} kWh",
    "peak_start must leave room for the intermediario hours (01:00-20:00)": (
        "peak_start deve deixar espaço para as horas do intermediário (01:00-20:00)"
    ),
    "peak_start {value!r}: give it as HH:MM, e.g. 18:00": (
        "peak_start {value!r}: informe como HH:MM, p. ex. 18:00"
    ),
    "The minimum in kWh must be >= 0, not {value!r}": "O mínimo em kWh deve ser >= 0, não {value!r}",
    "Give the connection date or the access request date": (
        "Informe a data de conexão ou a da solicitação de acesso"
    ),
    "gd must be 'GD I' or 'GD II'": "gd deve ser 'GD I' ou 'GD II'",
    "ANEEL has no tariff components file for {year} yet: Fio B from earlier years.": (
        "A ANEEL ainda não tem o arquivo de componentes tarifárias de {year}: Fio B dos anos anteriores."
    ),
    "ICMS {icms}, PIS/COFINS {pis_cofins}; not checked against a bill": (
        "ICMS {icms}, PIS/COFINS {pis_cofins}; não conferidos com uma conta"
    ),
    "No {subgroup} {modality} {posto} tariff in force on {day}": (
        "Nenhuma tarifa {subgroup} {modality} {posto} vigente em {day}"
    ),
    (
        "No {subgroup} {modality} {posto} tariff in force on {day}: the last vigencia ended on {end} "
        "(download newer data, or set extend_last=True to keep using it)"
    ): (
        "Nenhuma tarifa {subgroup} {modality} {posto} vigente em {day}: a última vigência terminou em {end} "
        "(baixe dados mais novos, ou use extend_last=True para continuar a usá-la)"
    ),
    "Tariffs after {end} reuse the last vigencia (extend_last=True).": (
        "As tarifas depois de {end} repetem a última vigência (extend_last=True)."
    ),
    "No tax rate in force on {day}": "Nenhuma alíquota de imposto vigente em {day}",
    "This TariffBook has no Fio B values: needed for GD II (see io.aneel.fetch_components)": (
        "Este TariffBook não tem valores de Fio B: necessários para a GD II (veja io.aneel.fetch_components)"
    ),
    (
        "No Fio B value on {day} (the first starts on {first}): fetch that year's components, or set "
        "fio_b_backfill=True to use the earliest value"
    ): (
        "Nenhum valor de Fio B em {day} (o primeiro começa em {first}): baixe as componentes daquele ano, ou "
        "use fio_b_backfill=True para usar o valor mais antigo"
    ),
    "Fio B before {first} uses the value of {first} (fio_b_backfill=True).": (
        "O Fio B antes de {first} usa o valor de {first} (fio_b_backfill=True)."
    ),
    "{rate:.2%} on every date": "{rate:.2%} em todas as datas",
    "{rate:.2%} from {day}": "{rate:.2%} a partir de {day}",
    "No bandeira for {month}; pass assume_bandeira (R$/MWh)": (
        "Sem bandeira para {month}; passe assume_bandeira (R$/MWh)"
    ),
    "modality must be 'Convencional' or 'Branca'": "modality deve ser 'Convencional' ou 'Branca'",
    "Tarifa branca needs the distributor's peak start (peak_start='HH:MM')": (
        "A tarifa branca precisa do início da ponta da distribuidora (peak_start='HH:MM')"
    ),
    "No hours to bill": "Nenhuma hora a faturar",
    "Import and export are netted hour by hour; a real meter nets instant by instant.": (
        "A energia consumida da rede e a injetada são compensadas hora a hora; um medidor real compensa "
        "instante a instante."
    ),
    "Months are calendar months; the bill follows the meter's reading cycle.": (
        "Os meses são meses do calendário; a conta real segue o ciclo de leitura do medidor."
    ),
    "Some months have missing hours: their energy and bill cover only the valid hours.": (
        "Alguns meses têm horas faltando: a energia e a conta deles cobrem só as horas válidas."
    ),
    "{kwh:.1f} kWh of credits expired unused (60 months).": (
        "{kwh:.1f} kWh de créditos expiraram sem uso (60 meses)."
    ),
    (
        "{n} hour(s) have consumption but no generation row (e.g. the PV series starts later): left out as "
        "unknown. If the PV was not installed yet, pass zeros for that period."
    ): (
        "{n} hora(s) têm consumo mas nenhuma linha de geração (p. ex. a série do FV começa depois): ficaram "
        "de fora como desconhecidas. Se o FV ainda não estava instalado, passe zeros para esse período."
    ),
    "COSIP/CIP (municipal street-lighting fee) not included: read it from a bill.": (
        "COSIP/CIP (contribuição de iluminação pública) não incluída: leia-a numa conta."
    ),
    (
        "From 2029 the GD II charge is a reading of Lei 14.300 art. 17 ({after_2028!r}): ANEEL's valuation "
        "of DG benefits is not modelled."
    ): (
        "A partir de 2029, a cobrança da GD II é uma leitura da Lei 14.300, art. 17 ({after_2028!r}): a "
        "valoração dos benefícios da GD pela ANEEL não é modelada."
    ),
    (
        "Tarifa branca with generation: per-posto netting (REN 1.000 art. 655-G), the TE ratio between "
        "postos from {te}, the other postos served in the order {order} (a reading)."
    ): (
        "Tarifa branca com geração: compensação por posto (REN 1.000, art. 655-G), a razão de TE entre os "
        "postos tirada {te}, os outros postos atendidos na ordem {order} (uma leitura)."
    ),
    "the given TE Energia": "da TE Energia informada",
    "the homologated TE (a reading)": "da TE homologada (uma leitura)",
    "No bandeira published for {months} yet: assumed the last one ({flag}, {add:.2f} R$/MWh, {last}).": (
        "Ainda sem bandeira publicada para {months}: assumida a última ({flag}, {add:.2f} R$/MWh, {last})."
    ),
    "GD by date": "GD pela data",
    "no GD class": "sem classe de GD",
    "{distributor} {subgroup} {modality}, {minimum}, {gd}, BRL": (
        "{distributor} {subgroup} {modality}, {minimum}, {gd}, BRL"
    ),
    "distributor": "distribuidora",
    # ---- economics.core
    "{name}: prices typed by the user": "{name}: preços digitados pelo usuário",
    (
        "Import and export are netted hour by hour; a real meter nets instant by instant, so within an hour "
        "with both PV and load the real flows are larger than these."
    ): (
        "A energia importada e a exportada são compensadas hora a hora; um medidor real compensa instante a "
        "instante, então, numa hora com FV e carga ao mesmo tempo, os fluxos reais são maiores que estes."
    ),
    (
        "{n} site-month(s) have missing hours (coverage < 1): their sums cover only the valid hours, so the "
        "bill of those months is too low."
    ): (
        "{n} mês(es) de algum local têm horas faltando (cobertura < 1): as somas cobrem só as horas válidas, "
        "então a conta desses meses fica baixa demais."
    ),
    "{kwh:.1f} kWh of credits expired unused.": "{kwh:.1f} kWh de créditos expiraram sem uso.",
    "Some months have a negative total: the exports are worth more than the imports.": (
        "Alguns meses têm total negativo: a energia exportada vale mais que a importada."
    ),
    "flat": "preço único",
    "{n} time-of-use blocks": "{n} blocos por horário",
    # ---- io
    "No components resource for {year} ({file}) in ANEEL's open data": (
        "Não há recurso de componentes tarifárias de {year} ({file}) nos dados abertos da ANEEL"
    ),
    "END": "FIM",
    "START": "INÍCIO",
    "Cannot infer the time step (fewer than two distinct timestamps); pass step=": (
        "Não é possível inferir o passo de tempo (menos de dois horários distintos); passe step="
    ),
    "freq={freq!r} is shorter than the data's step ({native}): cannot split energy": (
        "freq={freq!r} é mais curta que o passo dos dados ({native}): não dá para dividir a energia"
    ),
    "No tariff records for {distributor!r} (check SigAgente, e.g. 'COPEL-DIS')": (
        "Nenhum registro de tarifa para {distributor!r} (confira a SigAgente, p. ex. 'COPEL-DIS')"
    ),
    "No column of dates and times found among {cols}; give the time column's name": (
        "Nenhuma coluna de datas e horas encontrada entre {cols}; informe o nome da coluna de tempo"
    ),
    "Column {column!r} not in the file; it has {cols}": (
        "A coluna {column!r} não está no arquivo; ele tem {cols}"
    ),
    "column {column!r} as given": "coluna {column!r}, como informada",
    "an energy unit": "uma unidade de energia",
    "a power unit": "uma unidade de potência",
    "a name of energy": "um nome de energia",
    "column {column!r}: the only one with {rule}": "coluna {column!r}: a única com {rule}",
    "Several columns could be the energy ({names}, all with {rule}); give the energy column's name": (
        "Várias colunas podem ser a energia ({names}, todas com {rule}); informe o nome da coluna de energia"
    ),
    "column {column!r}: the only value column": "coluna {column!r}: a única coluna de valores",
    (
        "No energy column recognised among {others} (looked for an energy or power unit, or a name such as "
        "energy, production, consumption); give the energy column's name"
    ): (
        "Nenhuma coluna de energia reconhecida entre {others} (procurou-se uma unidade de energia ou de "
        "potência, ou um nome como energia, produção, consumo); informe o nome da coluna de energia"
    ),
    "recognised as a Fronius Solar.web export (two header rows, units in brackets)": (
        "reconhecido como uma exportação do Fronius Solar.web (duas linhas de cabeçalho, unidades entre "
        "colchetes)"
    ),
    "day": "dia",
    (
        "{file} has one value per {every}, coarser than the {freq!r} steps asked for: export the detailed "
        "data (5- or 15-minute or hourly; in Fronius Solar.web, the 5-minute 'minuto' export) instead of the "
        "daily totals."
    ): (
        "{file} tem um valor por {every}, mais grosso que os passos {freq!r} pedidos: exporte os dados "
        "detalhados (de 5 ou 15 minutos, ou horários; no Fronius Solar.web, a exportação 'minuto', de 5 "
        "minutos) em vez dos totais diários."
    ),
    "A Fronius Solar.web export holds the inverter's production: quantity='generation'": (
        "Uma exportação do Fronius Solar.web traz a produção do inversor: quantity='generation'"
    ),
    "format: {why}": "formato: {why}",
    "Unit {unit!r} is not read yet (kWh, Wh, kW or W); convert the column or give unit=": (
        "A unidade {unit!r} ainda não é lida (kWh, Wh, kW ou W); converta a coluna ou informe unit="
    ),
    "its values only grow within each day and restart at midnight: read as a daily counter": (
        "seus valores só crescem dentro de cada dia e recomeçam à meia-noite: lido como um contador diário"
    ),
    "its values only grow: read as a register (counter)": (
        "seus valores só crescem: lido como um registrador (contador)"
    ),
    "a units row under the header was dropped": "uma linha de unidades sob o cabeçalho foi descartada",
    "unit not stated in the file: kWh assumed": "unidade não informada no arquivo: kWh assumido",
    "file {file}: {why}, unit {unit}, kind {kind}": "arquivo {file}: {why}, unidade {unit}, tipo {kind}",
    (
        "The energy column only rises in this file: a counter (each step = the difference of two readings) "
        "or the energy of each interval (one rising morning of PV) look alike in a single day. Give "
        "kind='cumulative' or kind='interval'."
    ): (
        "A coluna de energia só sobe neste arquivo: um contador (cada passo = a diferença de duas leituras) "
        "e a energia de cada intervalo (uma manhã de FV subindo) parecem iguais num único dia. Informe "
        "kind='cumulative' ou kind='interval'."
    ),
    (
        "{file} {sheet}: no date/time column in the first row ({header}); is this a Solar.web export with "
        "its two header rows?"
    ): (
        "{file} {sheet}: nenhuma coluna de data/hora na primeira linha ({header}); é uma exportação do "
        "Solar.web com suas duas linhas de cabeçalho?"
    ),
    "No data rows found in the files given": "Nenhuma linha de dados encontrada nos arquivos informados",
    "No energy column recognised (looked for {names} in Wh/kWh); pass energy_column=, one of {headers}": (
        "Nenhuma coluna de energia reconhecida (procurou-se {names} em Wh/kWh); passe energy_column=, uma de "
        "{headers}"
    ),
    "Column {column!r} has unit {unit!r}, not an energy (Wh, kWh, MWh)": (
        "A coluna {column!r} tem a unidade {unit!r}, que não é de energia (Wh, kWh, MWh)"
    ),
    "The energy column has no value in any row": "A coluna de energia não tem valor em nenhuma linha",
    "the owner's own data": "dados do próprio dono",
    (
        "timestamps read as the {label} of each {step} interval (convention not confirmed: check with "
        "prosumer.quality.clock_offset)"
    ): (
        "horários lidos como o {label} de cada intervalo de {step} (convenção não confirmada: confira com "
        "prosumer.quality.clock_offset)"
    ),
    "{n} duplicate timestamp(s) dropped, first kept ({conflicts} with a different energy)": (
        "{n} horário(s) repetido(s) descartado(s), mantido o primeiro ({conflicts} com energia diferente)"
    ),
    "a step is valid with >= {share:.3g} of its records": (
        "um passo é válido com >= {share:.3g} dos seus registros"
    ),
    "{n} row(s) with an unreadable time left out": "{n} linha(s) com horário ilegível deixada(s) de fora",
    "{n} step(s) without sun set to zero": "{n} passo(s) sem sol zerado(s)",
    "Not a site: latitude {lat}, longitude {lon}": "Não é um local: latitude {lat}; longitude {lon}",
    "kind={kind!r} needs an energy unit (kWh, Wh), not {unit!r} (use kind='power' for W/kW)": (
        "kind={kind!r} precisa de uma unidade de energia (kWh, Wh), não {unit!r} (use kind='power' para W/kW)"
    ),
    "kind={kind!r} needs an energy unit (kWh, Wh), not {unit!r}": (
        "kind={kind!r} precisa de uma unidade de energia (kWh, Wh), não {unit!r}"
    ),
    "kind='power' needs a power unit (kW, W), not {unit!r}": (
        "kind='power' precisa de uma unidade de potência (kW, W), não {unit!r}"
    ),
    "Columns {missing} not in the table; it has {cols}": (
        "As colunas {missing} não estão na tabela; ela tem {cols}"
    ),
    "kind={kind}, unit={unit}": "tipo={kind}, unidade={unit}",
    "kind={kind}, unit={unit}, timestamps read as the {label} of each interval": (
        "tipo={kind}, unidade={unit}, horários lidos como o {label} de cada intervalo"
    ),
    "native step {step}": "passo original {step}",
    "{n} duplicate timestamp(s) dropped, first kept": (
        "{n} horário(s) repetido(s) descartado(s), mantido o primeiro"
    ),
    "{resets} counter reset(s) {done}; {spikes} outlier reading(s) dropped; {dips} small decrease(s) kept": (
        "{resets} reinício(s) do contador {done}; {spikes} leitura(s) atípica(s) descartada(s); {dips} "
        "pequena(s) queda(s) mantida(s)"
    ),
    "made invalid": "tornado(s) inválido(s)",
    "taken as a restart from zero": "tomado(s) como recomeço do zero",
    "a step is valid with >= {share:.3g} of its native steps": (
        "um passo é válido com >= {share:.3g} dos seus passos originais"
    ),
    # ---- outlook
    "The series has no valid value": "A série não tem nenhum valor válido",
    "The series came in steps of {freq}: summed into hours (11/12 of an hour needed).": (
        "A série veio em passos de {freq}: somada em horas (11/12 de uma hora necessários)."
    ),
    (
        "The outlook starts on {first}, before the data end ({last}): those days are already in the data, so "
        "they are not forecasts and say nothing about skill."
    ): (
        "A previsão começa em {first}, antes do fim dos dados ({last}): esses dias já estão nos dados, então "
        "não são previsões e nada dizem sobre o skill."
    ),
    (
        "The data end on {last}; the forecast starts on {first}, the first local day the weather forecast "
        "covers in full. The days in between are not forecast."
    ): (
        "Os dados terminam em {last}; a previsão começa em {first}, o primeiro dia local que a previsão do "
        "tempo cobre por inteiro. Os dias entre eles não são previstos."
    ),
    "The weather forecast is not used for consumption (the profile of recent weeks is).": (
        "A previsão do tempo não é usada para o consumo (usa-se o perfil das últimas semanas)."
    ),
    (
        "The consumption profile (weekdays and weekends apart, last 4 weeks) beat 'same as the last day' at "
        "every lead 1-14 on 20 Dingle houses (autumn 2020); a holiday, a trip or a new appliance is not in "
        "it."
    ): (
        "O perfil de consumo (dias úteis e fins de semana separados, últimas 4 semanas) superou 'igual ao "
        "último dia' em todos os horizontes de 1 a 14 dias em 20 casas de Dingle (outono de 2020); um "
        "feriado, uma viagem ou um aparelho novo não estão nele."
    ),
    (
        "How much the weather forecast is trusted at each lead day, and the confidence labels, were measured "
        "on two plants in Parana (Brazil), Aug/2025 to May/2026; elsewhere they are an assumption (`trust=` "
        "and `skill=` change them)."
    ): (
        "O quanto se confia na previsão do tempo em cada dia à frente, e os rótulos de confiança, foram "
        "medidos em duas usinas no Paraná (Brasil), de ago/2025 a mai/2026; em outros lugares são uma "
        "suposição (`trust=` e `skill=` os alteram)."
    ),
    "The weather forecast covers none of these hours: every day is the seasonal expectation.": (
        "A previsão do tempo não cobre nenhuma destas horas: todos os dias são a expectativa sazonal."
    ),
    (
        "Days beyond day {n} are the seasonal expectation (an average day of the month), not a forecast of "
        "their weather: beyond a week the weather forecasts showed no skill in the pilot."
    ): (
        "Os dias depois do dia {n} são a expectativa sazonal (um dia médio do mês), não uma previsão do seu "
        "tempo: além de uma semana, as previsões do tempo não mostraram skill no piloto."
    ),
    (
        "{n} hours have no forecast (never seen in the recent data) and are left out of the daily totals and "
        "of the load windows."
    ): (
        "{n} horas não têm previsão (nunca vistas nos dados recentes) e ficam fora dos totais diários e das "
        "janelas de carga."
    ),
    (
        "Weather models left out from the first day their GHI exceeds what the sun can give (> {factor:g} x "
        "clear sky + {offset:.0f} W/m2 in some hour): {models}."
    ): (
        "Modelos de tempo deixados de fora a partir do primeiro dia em que seu GHI passa do que o sol pode "
        "dar (> {factor:g} x céu limpo + {offset:.0f} W/m2 em alguma hora): {models}."
    ),
    (
        "{uid}: the roof fitted from the data is unreliable (tilt {tilt:.0f}, R2 {r2:.2f}; a tilt on the "
        "edge of the search or R2 < {good} means the data do not identify it). Give the tilt and azimuth if "
        "you know them."
    ): (
        "{uid}: o telhado ajustado aos dados não é confiável (inclinação {tilt:.0f}, R2 {r2:.2f}; uma "
        "inclinação na borda da busca ou R2 < {good} significa que os dados não o identificam). Informe a "
        "inclinação e o azimute se os souber."
    ),
    (
        "{uid}: the orientation could not be fitted from the data; assumed tilt {tilt:.0f} facing "
        "{azimuth:.0f}. Give tilt and azimuth for a better forecast."
    ): (
        "{uid}: não foi possível ajustar a orientação aos dados; assumida inclinação de {tilt:.0f} voltada "
        "para {azimuth:.0f}. Informe a inclinação e o azimute para uma previsão melhor."
    ),
    "{uid}: no clear day in the {days} days before the data end to learn the plant's power; give kwp": (
        "{uid}: nenhum dia de céu limpo nos {days} dias antes do fim dos dados para aprender a potência da "
        "usina; informe o kwp"
    ),
    "{share:g} x kwp (no recent clear day)": "{share:g} x kwp (nenhum dia de céu limpo recente)",
    "{uid}: no recent clear day to learn the plant; used {share:.0%} of the given kWp.": (
        "{uid}: nenhum dia de céu limpo recente para aprender a usina; usado {share:.0%} do kWp informado."
    ),
    "No weather forecast given: every day is the seasonal expectation.": (
        "Nenhuma previsão do tempo dada: todos os dias são a expectativa sazonal."
    ),
    "median of the clear days of the {days} days before the data end": (
        "mediana dos dias de céu limpo dos {days} dias antes do fim dos dados"
    ),
    "none": "nenhum",
    "no complete day to learn the season": "nenhum dia completo para aprender a estação",
    "{n} days of the same month in earlier years": "{n} dias do mesmo mês em anos anteriores",
    "the {n} days before the data end": "os {n} dias antes do fim dos dados",
    "too little history to learn the season: some days have no seasonal expectation": (
        "histórico curto demais para aprender a estação: alguns dias não têm expectativa sazonal"
    ),
    "{model} from {day}": "{model} a partir de {day}",
    "{uid}: fewer than {weeks} weeks of valid data behind some hours of the profile.": (
        "{uid}: menos de {weeks} semanas de dados válidos por trás de algumas horas do perfil."
    ),
    "mean of the same hour over the last {weeks} weeks, weekdays and weekends apart": (
        "média da mesma hora nas últimas {weeks} semanas, dias úteis e fins de semana separados"
    ),
    # ---- quality
    "{h:+g} h in {months}": "{h:+g} h em {months}",
    (
        "Series {uid}: the clock offset against the sun changes over the year ({per}). A logger that ignores "
        "daylight saving time (or a file in standard time read in a zone with it) does this: check the time "
        "zone of the export."
    ): (
        "Série {uid}: o desvio do relógio em relação ao sol muda ao longo do ano ({per}). Um registrador que "
        "ignora o horário de verão (ou um arquivo em horário padrão lido num fuso que o tem) faz isso: "
        "confira o fuso horário da exportação."
    ),
    (
        "Series {uid}: production happens {hours:g} h {side} than the sun at the site ({agree:.0%} of the "
        "days agree). Usually a file in UTC read as local time, a wrong time zone or, for +1 h, values "
        "labelled by the END of the interval: shift the timestamps by {shift:+g} h after checking the source."
    ): (
        "Série {uid}: a produção acontece {hours:g} h {side} que o sol no local ({agree:.0%} dos dias "
        "concordam). Em geral é um arquivo em UTC lido como hora local, um fuso horário errado ou, para +1 "
        "h, valores marcados pelo FIM do intervalo: desloque os horários em {shift:+g} h depois de conferir "
        "a fonte."
    ),
    "earlier": "mais cedo",
    "later": "mais tarde",
    (
        "Series {uid}: the production follows the clouds {hours:.1f} h {side} than the weather data (90% "
        "interval {low:+.1f} to {high:+.1f} h). A fraction of an hour usually means intervals labelled by "
        "their end or a logger clock that drifted; check the source before using the weather as an input."
    ): (
        "Série {uid}: a produção segue as nuvens {hours:.1f} h {side} que os dados de tempo (intervalo de "
        "90% de {low:+.1f} a {high:+.1f} h). Uma fração de hora em geral significa intervalos marcados pelo "
        "fim ou um relógio de registrador que derivou; confira a fonte antes de usar o tempo como entrada."
    ),
}
