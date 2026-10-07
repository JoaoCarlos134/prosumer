# Biblioteca `prossumidor` e TCC

A proposta de transformar o código do projeto numa biblioteca Python e de usar esse trabalho como
TCC (e, depois, mestrado). **Estado em 06/10/2026:** o uso acadêmico para o TCC foi autorizado pela
gestão em 05/10/2026, conforme [`CLAUDE.md`](../../CLAUDE.md). Titularidade e licença seguem os termos
do projeto; a decisão de licença continua com o Lactec. O repositório é privado e **não tem arquivo
LICENSE**. Os dados de terceiros não têm autorização para publicação.

| Arquivo | O que é |
|---|---|
| `Proposta_TCC_prossumidor.pdf` | proposta para a gestão (10 páginas): objetivos, etapas E0–E8, cronograma, decisões pedidas |
| `PROPOSTA_BIBLIOTECA.md` | estudo de viabilidade técnica (30/09/2026): módulos, de onde vem cada código, riscos |
| [`gera_proposta_tcc.py`](gera_proposta_tcc.py) | gera o PDF (precisa de `reportlab`) |

O PDF preserva a proposta apresentada em 05/10/2026; os pedidos de autorização nele são históricos.
O repositório já contém documentação, experimentos e código legado. A licença MIT inicial foi removida
em 05/10/2026. A fundação do pacote (`src/prossumidor/`, contratos, dados sintéticos e CI; etapa E1)
ainda é o próximo trabalho de biblioteca, depois da conclusão dos experimentos v2.

O exportador `biblioteca_tcc/scripts/exporta_repo_prossumidor.py` fica **somente na máquina do Lactec**:
contém o mapa de nomes e não deve ser copiado para cá. A sincronização é feita naquela máquina;
registre as alterações locais antes de uma nova exportação.

Para a revisão atual e as etapas E0–E8, veja [`revisao_projeto.md`](../../graphify-out/revisao_projeto.md).
