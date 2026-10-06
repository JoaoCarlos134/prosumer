# Ambientes Python dos testes

Quatro ambientes, porque os modelos exigem versões incompatíveis de torch e transformers.
Versões exatas congeladas em 05/10/2026 (`uv pip freeze`).

| Ambiente | Python | Para quê |
|---|---|---|
| `previsao.txt` | 3.12 | quase tudo: referências, LightGBM, redes (NeuralForecast), Chronos, TimesFM, TiRex, TTM, Toto 1.0, avaliação e figuras |
| `lote2.txt` | 3.12 | Toto 2.0, TiRex-2 (e TabPFN-TS, que ficou de fora em CPU) |
| `lote2_hf.txt` | 3.12 | Sundial, Timer-XL, Time-MoE (`transformers==4.40.1`, `trust_remote_code`) |
| `moirai.txt` | 3.11 | Moirai 2.0 e Moirai-MoE (`uni2ts`, torch 2.4) |

Criar (com [uv](https://docs.astral.sh/uv/)), na pasta `~/.venvs` (ou defina `VENVS` para outra):

    uv venv ~/.venvs/previsao --python 3.12
    uv pip install --python ~/.venvs/previsao/Scripts/python.exe -r previsao.txt --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cpu

Repita para `lote2` e `lote2_hf` (Python 3.12) e `moirai` (Python 3.11). Em Linux/macOS o executável é
`bin/python`. Com GPU NVIDIA, troque o índice `whl/cpu` por `whl/cu126` (ou a versão do seu driver) e
remova o sufixo `+cpu` de `moirai.txt`.

Atrás de proxy com certificado próprio (rede do Lactec): `export UV_NATIVE_TLS=1`.

## O que foi preciso mudar para recriar os quatro ambientes (06/10/2026, Windows + RTX 4070)

Recriar do zero numa máquina com GPU exigiu três desvios da receita acima. Sem eles a instalação
falha ou — pior — passa calada e deixa o ambiente errado.

**1. `--no-deps` é obrigatório.** Os `.txt` são `uv pip freeze` de ambientes montados aos poucos, e o
conjunto congelado não é resolvível de uma vez: `gluonts==0.16.2` exige `pandas<3` e o arquivo fixa
`pandas==3.0.6`. `uv pip install -r` falha na resolução. Como o freeze já fixa todas as transitivas,
instale sem resolver:

    uv pip install --python ~/.venvs/previsao/Scripts/python.exe --no-deps -r previsao.txt --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu128

**2. Dependências de git precisam de `core.longpaths` e `--no-build-isolation`.** São duas:
`granite-tsfm` (em `previsao`, implementa o TTM) e `tirex-2` (em `lote2`). No Windows o checkout
estoura o limite de 260 caracteres e o build falha; além disso a política de Controle de Aplicativo
bloqueia o python temporário que o uv cria para compilar (`os error 4551`). Passe o `core.longpaths`
só nesse comando, sem alterar o git global, e compile com o python do próprio ambiente:

    export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.longpaths GIT_CONFIG_VALUE_0=true
    uv pip install --python ~/.venvs/lote2/Scripts/python.exe setuptools wheel
    uv pip install --python ~/.venvs/lote2/Scripts/python.exe --no-deps --no-build-isolation "tirex-2 @ git+https://github.com/NX-AI/tirex-2@e68253bd5a99fd2de92c2ebee11d93a16b2a5e68"

O `tirex-2` instala assim. O `granite-tsfm` instala mas fica incompleto (versão 0.0.0, sem o
subpacote `tsfm_public.toolkit`): o TTM-r2 já estava pronto e não entra em nenhuma fila, mas isso
precisa ser resolvido antes do fine-tuning do TTM.

**3. O índice CUDA é por ambiente — e errar passa calado.** `previsao` fixa `torch==2.11.0`, que
existe em `whl/cu128`. `lote2` fixa `torch==2.14.1`, que **não** existe em cu128, só em `whl/cu130`;
com cu128 o uv cai no PyPI, onde o wheel de Windows é CPU, e o ambiente termina com `2.14.1+cpu` sem
erro nenhum — o TabPFN-TS então roda em CPU e leva dias. Confira sempre:

    ~/.venvs/lote2/Scripts/python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
    # esperado: 2.14.1+cu130 True

`lote2_hf` (torch 2.8.0) e `moirai` (torch 2.4.1) continuam em CPU de propósito: os fundacionais
rodam em CPU e são rápidos.

### Cuidados ao rodar com GPU

- **TiRex-2 precisa rodar sem GPU visível.** Com um torch de CUDA instalado, o `xlstm` monta os
  caminhos do kernel sLSTM no import só porque `torch.cuda.is_available()` é verdadeiro, e exige
  `CUDA_HOME` (nvcc), que os wheels do pip não trazem. O `roda_lote2.py` já isola essa etapa com
  `CUDA_VISIBLE_DEVICES=-1`; string vazia não serve, o torch ignora.
- **Time-MoE-50M em lotes de 8.** Com 32 e contexto de 1024 h a RAM vai de 0,7 para 13,1 GB e a
  rodada morre por falta de memória. Já está no `03c_fundacionais_lote2.py`.
