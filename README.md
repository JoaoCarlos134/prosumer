# prossumidor

Base do TCC (e, depois, do mestrado) de João Carlos Jachenski Junior: uma biblioteca Python para prever geração
e consumo de prossumidores de energia, usina FV, casa com FV e bateria, do dado do medidor ao modelo
embarcado. Nasce do projeto de PD&I Edge AI (Lactec), com uso acadêmico
autorizado pela gestão em 05/10/2026.

**Repositório privado.** As séries das usinas são de terceiros e não têm consentimento para publicação.
Os nomes dos proprietários foram trocados pelo nome da cidade da usina e as coordenadas arredondadas
para ~1 km (mesmo ponto de grade nas bases de clima). Não reintroduza nada disso.

| Pasta | O que é |
|---|---|
| `docs/proposta/` | proposta do TCC (PDF e gerador), estudo de viabilidade da biblioteca |
| `docs/projeto/` | estado das análises, plano dos artigos A e B, análise de rede, resumos |
| `docs/literatura/` | revisão Edge AI, referências, levantamento e visão geral de 127 modelos |
| `experimentos/testes_previsao/` | testes de previsão do dia seguinte: scripts, dados horários, ambientes, resultados |
| `legado/` | o código do projeto que vai virar os módulos da biblioteca (não roda daqui: os dados brutos ficaram no Lactec) |

Para retomar com o Claude Code, comece por `CLAUDE.md`.
