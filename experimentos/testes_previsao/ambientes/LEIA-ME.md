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
