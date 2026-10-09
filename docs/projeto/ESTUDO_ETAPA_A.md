# Etapa A: estudo e piloto dos modelos pendentes

Regra do plano (09/10/2026): nenhum modelo sai sem **estudo + evidência**. Para cada um: como funciona, o
que pode acrescentar à biblioteca, como fazer rodar, e um piloto. **Portão** para o teste completo: empatar
com o melhor num caso (Diebold–Mariano contra o melhor do teste, p ≥ 0,05 **sem** Holm, mais exigente que
o benchmark) ou trazer algo que nenhum outro traz (clima sem treino, tamanho de embarcado, faixa,
dependência entre séries).

Avaliação: `scripts/piloto_comum.py` (mesmas horas avaliadas, mesmo corte de negativos e mesma referência do
`05_avalia.py`). Saídas em `resultados/pilotos/` (fora de `previsoes/`: não entram na mediana nem no
`metricas.csv`); números em `resultados/pilotos/resumo.json`.

Ambiente da etapa A na máquina de casa: `~/.venvs/etapa_a` = `previsao_gpu` (torch 2.9.1+cu128) + o pacote
de cada modelo instalado com `--no-deps` (resolver puxaria o torch 2.14.1, bloqueado pelo Smart App Control).
Modelos do `uni2ts` usam o `~/.venvs/moirai` já existente.

| Modelo | Situação | Resultado em uma linha |
|---|---|---|
| VisionTS | **não passa** (estudado e testado, 3 casos) | 9º–23º; nunca empata (FV das casas p = 0,022) |
| VisionTS++ | **PASSA** (FV das casas) | 9º de 48 na FV das casas, empata com o Toto-2.0-313m (p = 0,14); devolve 9 quantis |
| Moirai 1.1 | **não passa** (2 tamanhos, 2 patches válidos, A e B) | usa mal o clima: em B fica em último (24º de 24) |
| CycleNet, MOMENT, Lag-Llama, DUET, Crossformer, Mamba/S-Mamba, xLSTM, TimeGrad, Time-LLM, LLMTime, TimeGPT | a fazer | — |

---

## VisionTS e VisionTS++ (09/10/2026)

**Como funciona.** Chen et al., *VisionTS: Visual Masked Autoencoders Are Free-Lunch Zero-Shot Time Series
Forecasters* (ICML 2025). A série é cortada pelo período (24 h) e empilhada numa imagem cinza: cada coluna é
um dia, cada linha uma hora. A imagem é redimensionada para 224 × 224, a metade da direita (o futuro) fica
mascarada, e um autoencoder mascarado de **imagens** (MAE ViT-Base, 112 M parâmetros, pré-treinado só no
ImageNet, sem nenhuma série temporal) reconstrói os pixels que faltam. A previsão é a coluna reconstruída
desfeita de volta em série, com a normalização da janela invertida. Não há treino nos nossos dados (no
artigo, o ajuste fino é só das camadas de normalização, `finetune_type="ln"`; aqui zero-shot).
VisionTS++ (2025) continua o pré-treino desse MAE em séries temporais, aceita várias variáveis como canais de
cor e tem 9 cabeças de quantil.

**O que pode acrescentar.** A sazonalidade diária forte da geração FV é o caso ideal: o dia vira uma coluna
de pixels e "dia parecido com ontem" vira "coluna parecida com a vizinha". O VisionTS++ ainda dá faixa
(quantis) sem treino, o que interessa ao piloto F2c. E o modo multivariado do VisionTS++ (clima como outra
cor da imagem) seria um segundo caminho de clima-sem-treino — **não testado** ainda.

**Como rodar.** `pip install visionts` (1.0.1) com `--no-deps` + `timm 1.0.30` + `torchvision 0.24.1+cu128`.
Pesos baixados na primeira chamada para `~/.cache/visionts` (MAE do Facebook, 427 MB; VisionTS++ do
HuggingFace `Lefei/VisionTSpp`). Contexto de 1024 h como os outros fundacionais, `periodicity=24`.
Script: `scripts/piloto_visionts.py [VisionTS|VisionTS++] [caso ...]`.
Tempo na RTX 4070: usinas 47 s (VisionTS) e 341 s (VisionTS++, 598 janelas); casas 3–6 s.

**Licença.** Código do VisionTS: MIT. Pesos do VisionTS++ no HuggingFace: MIT. **Atenção:** o VisionTS
baixa o MAE oficial do Facebook, cujo repositório é CC-BY-NC 4.0 (uso não comercial); o VisionTS++ é
derivado desse MAE. Conferir a cadeia de licença antes de pôr na biblioteca.

**Piloto (regime A, os três casos).**

| Caso | VisionTS | VisionTS++ | Melhor do teste |
|---|---|---|---|
| usinas | +0,042 (22º/50), MBE −0,1% | +0,060 (18º/50), MBE **+14%** | TiRex-2 +0,141 |
| FV das casas | +0,130 (9º/48), p = 0,022 | **+0,127 (9º/48), p = 0,144: empata** | Toto-2.0-313m +0,178 |
| consumo | +0,165 (23º/49), MBE −10% | +0,176 (21º/49), MBE −21% | mediana corrigida +0,207 |

**Decisão.** VisionTS++ **passa no portão** (empata na FV das casas) e traz quantis → entra no teste completo
(regime A nos três casos, gravando com `comum.grava`; e testar o modo multivariado com o clima em B). O IC
dele é largo (+0,094 a +0,161 na FV das casas): o empate pode ser fraqueza do teste, não força do modelo.
VisionTS original **não passa**: nunca empata e o VisionTS++ o domina. Fica descartado com evidência.
O viés do VisionTS++ (+14% nas usinas, −21% no consumo) é o mesmo padrão dos outros fundacionais no consumo;
a correção de viés da biblioteca (`correct_bias`) vale para o consumo, não para a geração.

---

## Moirai 1.1 (09/10/2026)

**Como funciona.** Woo et al., *Unified Training of Universal Time Series Forecasting Transformers* (ICML
2024). Transformer só-codificador treinado por máscara no LOTSA (27 bilhões de observações, 9 domínios).
Duas ideias: (1) **patches de tamanho que depende da frequência** (para dado horário o modelo aprendeu
patches de 32 e 64 pontos); (2) **any-variate attention**: alvo e covariáveis são achatados numa sequência
só de patches, cada variável com o seu identificador (RoPE no tempo + viés de atenção por variável), então o
número de variáveis é livre. A saída é uma mistura de distribuições (t de Student, binomial negativa,
log-normal, normal quase degenerada); a previsão pontual aqui é a mediana de 100 amostras.

**O que podia acrescentar.** O Moirai 2 e o Moirai-MoE do benchmark rodaram só no regime A. O Moirai 1 aceita
covariáveis futuras (`feat_dynamic_real`) sem treino: seria um terceiro modelo de clima-sem-treino, ao lado
do Chronos-2 e do TimesFM com regressão.

**Como rodar.** Ambiente `~/.venvs/moirai` (uni2ts 2.0, torch 2.4.1 CPU), sem instalar nada.
`MoiraiForecast(module=MoiraiModule.from_pretrained("Salesforce/moirai-1.1-R-<tamanho>"), patch_size=64, ...)`;
no regime B as quatro exógenas do benchmark (`poa_ceu_claro`, `ghi_horario`, `poa_estimada`,
`temp_ar_horaria`) entram como `feat_dynamic_real` de forma (lote, 1024 + 24, 4).
Script: `scripts/piloto_moirai1.py [small|base] [caso] [A B C] [patch=32|64]`.
Tempo em CPU nas usinas: 18–63 s (A), 79–154 s (B). **Licença dos pesos: CC-BY-NC 4.0** (não comercial).

**Armadilhas encontradas.** Com `patch_size=16` (o do Moirai-MoE, que só tem esse tamanho) o Moirai 1 prevê
~zero (skill −1,20, MBE −95%): 16 não existe para dado horário no Moirai 1. Com `patch_size="auto"` o
uni2ts 2.0 quebra (`128 x 131` no `prediction_mask`). Os números válidos são com 32 e 64.

**Piloto (usinas, A e B).**

| Configuração | A | B (com clima) |
|---|---|---|
| small, patch 32 | −0,057 (37º/50), MBE −24% | −0,154 (24º/24), MBE −31% |
| small, patch 64 | +0,035 (22º/50), MBE −9% | +0,054 (24º/24), MBE −6% |
| base, patch 64 | +0,055 (21º/50), MBE −7% | +0,027 (24º/24), MBE −14% |
| melhor do teste | TiRex-2 +0,141 | TiRex-2 +0,509 |

**Decisão. Não passa, descartado com evidência.** No regime A fica no meio da tabela, abaixo do Moirai-MoE
(+0,079) e do Moirai 2 (+0,060) do próprio benchmark. A razão de testá-lo era o clima, e o clima quase não
muda nada: o vão A → B é de +0,02 (small) e **negativo** (base), contra ~+0,40 nos outros modelos. Ou seja, a
any-variate attention zero-shot não aprende a relação "mais sol, mais geração" a partir das covariáveis. O
large (311 M) não foi testado: o base já piora com o clima em relação ao small, então não há sinal de que
tamanho resolva.
