# -*- coding: utf-8 -*-
"""Etapa A do plano: LLMTime (Gruver, Finzi, Qiu e Wilson, NeurIPS 2023), zero-shot, regime A, piloto CURTO.

LLMTime nao treina nada: escreve a serie como TEXTO e pede a um LLM pre-treinado que continue o texto. Cada valor
e escalado e escrito com precisao fixa, sem ponto decimal (0,734 -> "734"), separado por virgula; o LLM gera a
continuacao digito a digito (so digitos e virgula sao permitidos), e o texto gerado volta a ser numero. Repetindo
a geracao com amostragem (temperatura 1) sai uma distribuicao; a previsao pontual e a mediana das amostras. A
ideia do artigo: LLMs preferem continuacoes simples e repetitivas, um bom vies para series.

Por que piloto curto (decisao de 10/10/2026): o artigo usou GPT-3 e LLaMA-2 70B; nao ha LLM desse porte nesta
maquina, e Tan et al. (NeurIPS 2024) indicam que o LLM nao ajuda em previsao. Um piloto barato no consumo diz se
vale olhar mais.

Configuracao (a do LLaMA no codigo oficial, github.com/ngruver/llm-time-series, 'llama_hypers'): escala basic=False
com alpha 0,99 e beta 0,3 (desloca pelo minimo da janela menos 0,3 x amplitude e divide pelo quantil 0,99), 3
digitos de precisao, sem espaco entre digitos (o tokenizador ja separa cada digito), temperatura 1,0, top-p 0,9,
correcao de meio-bin (ruido uniforme dentro do ultimo digito). LLM: Qwen2.5-1.5B BASE (Apache-2.0; o artigo
mostra que modelos ajustados para conversa pioram), tokeniza cada digito separado, como o LLaMA. Separador ","
(o oficial usa ", "; uma ficha a menos por valor). Contexto: 336 h (duas semanas, ~1.400 fichas); 10 amostras por
janela (o oficial usa 20). Custo medido na RTX 4070: ~7 s por janela (2 janelas x 10 amostras por chamada; a
memoria cresce rapido com o lote), ~3,5 h no consumo: roda na fila da noite. Saidas com menos de 24 valores sao completadas com o
ultimo valor valido (contadas e impressas).

Uso: DISPOSITIVO=cuda python piloto_llmtime.py [teste] [lote=2] [caso ...]   (ambiente previsao_gpu; padrao casas_cons)
Depois: python piloto_comum.py LLMTime <caso> A   (ambiente da biblioteca)
"""
import sys
import time

import numpy as np
import torch
from transformers import (AutoModelForCausalLM, AutoTokenizer, LogitsProcessor, LogitsProcessorList,
                          StoppingCriteria, StoppingCriteriaList)

from comum import H, carrega, janelas
from piloto_comum import grava_piloto

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
LLM = "Qwen/Qwen2.5-1.5B"
TESTE = "teste" in sys.argv[1:]
CONTEXTO, AMOSTRAS = 336, 10
LOTE = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("lote=")), "2"))  # janelas por chamada (x AMOSTRAS)
ALPHA, BETA, PREC = 0.99, 0.3, 3


class SoPermitidos(LogitsProcessor):
    def __init__(self, ids, vocab):
        self.mascara = torch.full((vocab,), float("-inf"))
        self.mascara[ids] = 0.0

    def __call__(self, input_ids, scores):
        return scores + self.mascara[: scores.shape[-1]].to(scores.device)


class Ate24(StoppingCriteria):
    """Para quando todas as sequencias ja escreveram 24 valores (24 virgulas depois do prompt)."""

    def __init__(self, virgula, n_prompt):
        self.virgula, self.n_prompt = virgula, n_prompt

    def __call__(self, input_ids, scores, **kw):
        return bool(((input_ids[:, self.n_prompt:] == self.virgula).sum(1) >= H).all())


def escala(y):
    mn = y.min() - BETA * (y.max() - y.min())
    q = np.quantile(y - mn, ALPHA)
    return mn, (q if q > 0 else 1.0)


def para_texto(y, mn, q):
    return ",".join(str(int(round(v * 10**PREC))) for v in np.clip((y - mn) / q, 0, None)) + ","


def de_texto(s, mn, q, rng):
    vals = [int(t) for t in s.split(",")[:H] if t.isdigit()]
    falta = H - len(vals)
    if not vals:
        return None, H
    vals += [vals[-1]] * falta
    v = (np.array(vals, float) + rng.uniform(0, 1, H)) / 10**PREC  # correcao de meio-bin
    return v * q + mn, falta


if __name__ == "__main__":
    casos = [a for a in sys.argv[1:] if a in ("usinas", "casas_prod", "casas_cons")] or ["casas_cons"]
    tok = AutoTokenizer.from_pretrained(LLM)
    tok.padding_side = "left"
    llm = AutoModelForCausalLM.from_pretrained(LLM, dtype=torch.bfloat16).to(DEV).eval()
    ok_ids = sorted({tok.convert_tokens_to_ids(c) for c in "0123456789,"})
    virgula = tok.convert_tokens_to_ids(",")
    proc = LogitsProcessorList([SoPermitidos(ok_ids, llm.config.vocab_size)])
    rng = np.random.default_rng(42); torch.manual_seed(42)
    for caso in casos:
        t0 = time.time()
        jan = janelas(carrega(caso), caso, contexto=CONTEXTO)[:LOTE * 2 if TESTE else None]
        prev, completados, vazios = [], 0, 0
        for i in range(0, len(jan), LOTE):
            lote = jan[i:i + LOTE]
            esc = [escala(w["y"]) for w in lote]
            textos = [para_texto(w["y"], *e) for w, e in zip(lote, esc)]
            enc = tok(textos, return_tensors="pt", padding=True).to(DEV)
            with torch.no_grad():
                out = llm.generate(**enc, do_sample=True, temperature=1.0, top_p=0.9, max_new_tokens=H * 5,
                                   num_return_sequences=AMOSTRAS, logits_processor=proc,
                                   stopping_criteria=StoppingCriteriaList([Ate24(virgula, enc["input_ids"].shape[1])]),
                                   pad_token_id=tok.pad_token_id)
            gen = tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
            for k, (w, e) in enumerate(zip(lote, esc)):
                amostras = []
                for s in gen[k * AMOSTRAS:(k + 1) * AMOSTRAS]:
                    v, falta = de_texto(s, *e, rng)
                    completados += falta > 0
                    if v is not None:
                        amostras.append(v)
                vazios += not amostras
                prev.append(np.median(amostras, axis=0) if amostras else np.full(H, float(np.median(w["y"][-H:]))))
            if TESTE or i % (LOTE * 25) == 0:
                print(f"  {caso}: {i + len(lote)}/{len(jan)} janelas, {time.time() - t0:.0f} s", flush=True)
        f = grava_piloto("LLMTime-teste" if TESTE else "LLMTime", caso, "A", jan, prev)
        print(f"OK {f.name} | {len(jan)} janelas | {time.time() - t0:.0f} s em {DEV.type} | amostras completadas "
              f"{completados}/{len(jan) * AMOSTRAS} | janelas sem amostra valida {vazios}", flush=True)
