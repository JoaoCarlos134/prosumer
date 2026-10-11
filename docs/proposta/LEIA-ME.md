# Biblioteca `prosumer` (antes `prossumidor`) e TCC

A proposta de transformar o código do projeto numa biblioteca Python e de usar esse trabalho como
TCC (e, depois, mestrado). **Estado em 06/10/2026:** o uso acadêmico para o TCC foi autorizado pela
gestão em 05/10/2026, conforme [`CLAUDE.md`](../../CLAUDE.md). A licença é decisão do autor (a Lactec só entra
se o projeto for ligado formalmente a um projeto dela). O repositório é privado e **não tem arquivo
LICENSE**. Os dados das usinas só podem ser publicados com a permissão do professor responsável por eles; as 20 casas são o conjunto público CC0 de Khadem et al. (2024), que pode ser publicado com citação.

| Arquivo | O que é |
|---|---|
| `Proposta_TCC_prossumidor.pdf` | proposta para a gestão (10 páginas): objetivos, etapas E0–E8, cronograma, decisões pedidas |
| `PROPOSTA_BIBLIOTECA.md` | estudo de viabilidade técnica (30/09/2026): módulos, de onde vem cada código, riscos |
| [`gera_proposta_tcc.py`](gera_proposta_tcc.py) | gera o PDF (precisa de `reportlab`) |
| `Plano_TCC_simples.pdf` | plano em linguagem simples (07/10/2026): proposta, o que foi feito, teste ampliado, etapas com horas e cronograma |
| [`Plano_TCC_simples.tex`](Plano_TCC_simples.tex) | fonte editável do plano; compilar com `pdflatex Plano_TCC_simples.tex` |

O PDF preserva a proposta apresentada em 05/10/2026; os pedidos de autorização nele são históricos.
O repositório já contém documentação, experimentos e código legado. A licença MIT inicial foi removida
em 05/10/2026. A fundação do pacote (`src/prossumidor/`, contratos, dados sintéticos e CI; etapa E1)
foi concluída em 06/10/2026; o próximo trabalho de biblioteca é a etapa E2 (versão 0.1).

O exportador `biblioteca_tcc/scripts/exporta_repo_prossumidor.py` fica **somente na máquina do Lactec**:
contém o mapa de nomes e não deve ser copiado para cá. A sincronização é feita naquela máquina;
registre as alterações locais antes de uma nova exportação.

Para o estado atual veja [`CLAUDE.md`](../../CLAUDE.md); as etapas E0–E8 estão no PDF da proposta.
