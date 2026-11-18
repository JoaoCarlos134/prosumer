# C10: busca de dados públicos de FV com coordenadas e dados de 2024 em diante (18/11/2026)

Pedido de 18/11 (fila do servidor, C10): FV com coordenadas (ou ao menos o município) e dados de 2024 em diante, para
cruzar com o arquivo de previsões do tempo (Open-Meteo Previous Runs começa em 06/03/2024), residencial de
preferência, Brasil e outros climas. Nada foi baixado além da lista pública de sistemas do PVDAQ (metadados). Licença
conferida antes de qualquer download; nenhum dado com nome de dono.

| Fonte | Licença | Coordenadas | Período | Passo | Tamanho / sistemas | Serve para | Situação |
|---|---|---|---|---|---|---|---|
| **NREL PVDAQ, frota residencial** (lista `systems_20250729.csv` do data lake OEDI) | CC BY 4.0 | sim (ponto por CEP americano; tilt e azimute no metadata) | 1158 sistemas fixos, QA "pass", com dados de antes de 03/2024 até 01–07/2025 | 5–15 min (varia) | mediana 7,4 kW; climas Cfa 295, Csb 241, Csa 178, Dfb 149, Dfa 131, BSk 108, BSh 22, Cfb 17, outros | **V11 num sítio NOVO e P5 (confiança por clima)**: sobrepõe o arquivo de tempo; telhado e relógio com verdade no metadata | **melhor candidato**; só EUA (nenhum no hemisfério sul) |
| BR-PVGen v2 (Zenodo, de Jesus et al. 2026) | CC BY 4.0 | não (só o estado) → C9 estima | 26/03/2024 → 09/06/2025 | 15 min | 51 usinas de 1–5 MW (30 seguidores, 21 fixas), bifaciais | P4 (POA medida); P5/V11 só se o C9 passar | já no servidor |
| Ausgrid Solar Home | CC BY 3.0 AU | não (só código postal) | 2010–2013 | 30 min | 300 casas com FV | regras do consumo | já no servidor; antes do arquivo de tempo |
| Open Climate Fix `uk_pv` (Hugging Face) | a conferir no cartão do conjunto (o MIT do OCF cobre o código, não necessariamente os dados) | ofuscadas pelos mantenedores | cartão diz 2018–2021; arquivos mensais citados até 2023 (o README está desatualizado, dizem os mantenedores) | 2–30 min | 1311 sistemas | clima oceânico (Cfb) | **não baixar** antes de conferir licença e cobertura |
| 175 sistemas residenciais (J. Renew. Sustain. Energy, 2022; Utrecht) | a conferir | tilt e azimute no metadata | 2014–2017 | 1 min | 175 | telhado (sem tempo arquivado) | fora do período |
| Arctic multi-azimuth (Mendeley Data, 2024) | a conferir no repositório | sim (um sítio) | 09/2021 → 08/2023 | — | painéis em 8 azimutes e 2 inclinações | transposição / orientação | fora do período do arquivo |
| PVOutput, Solcast | termos de uso restringem redistribuição / pago | — | — | — | — | — | não usar |
| Brasil: ANEEL (SISGD / painel de GD), ONS | dados abertos | município, sem série por unidade | — | — | — | — | não há série temporal por sistema; nenhuma base aberta de FV residencial com coordenadas e série 2024+ foi encontrada (dissertações da UFPB, UFPA e UFV citam bases medidas, sem link aberto confirmado) |

**Recomendação.** O PVDAQ residencial é o próximo passo para destravar o V11 num sítio que não escolheu os padrões e
o P5 por clima (fora do Brasil): escolher ANTES de baixar, por regra escrita no portão (por exemplo, 2 sistemas por
clima de Köppen com ≥ 10 sistemas, sorteados com semente fixa entre os de QA "pass", fixos, com ≥ 12 meses depois de
03/2024), um job por sistema no servidor. Brasil continua sem base pública com coordenadas: o C9 é o caminho para o
BR-PVGen.

Fontes: [PVDAQ no OpenEI](https://data.openei.org/submissions/4568), [lista de sistemas (S3)](https://oedi-data-lake.s3.amazonaws.com/pvdaq/csv/systems_20250729.csv),
[catálogo data.gov do PVDAQ](https://catalog.data.gov/dataset/photovoltaic-data-acquisition-pvdaq-public-datasets),
[OCF uk_pv](https://huggingface.co/datasets/openclimatefix/uk_pv), [discussão sobre os arquivos do uk_pv](https://huggingface.co/datasets/openclimatefix/uk_pv/discussions/9),
[175 sistemas residenciais (Utrecht)](https://dspace.library.uu.nl/bitstream/handle/1874/422978/5.0100939.pdf?sequence=1),
[Arctic multi-azimuth (Mendeley)](https://data.mendeley.com/datasets/pmjt7gyp3r/1),
[dissertação UFPB](https://cear.ufpb.br/ppger/contents/documentos/dissertacoes-apresentadas/DISSERTAO_ADONIAS_ATUALIZADA_25.pdf),
[dissertação UFPA](https://bdm.ufpa.br/bitstreams/438aeab5-d27a-405f-b5e0-4bb2f0a03923/download).
