# -*- coding: utf-8 -*-
"""Redes treinadas nestes dados (NeuralForecast + SparseTSF, ResNet-1D e CycleNet proprias).

Mesmo protocolo para todas: entrada de 168 h, saida de 24 h, ultimos 30 dias antes de cada dobra
como validacao para parada antecipada, um modelo global por caso, semente 42, os MESMOS lotes em
todas (COMUM). Origem movel (v2): o modelo e treinado do zero no inicio de cada dobra (comum.dobras)
so com dados anteriores a ela; dentro da dobra a janela anda um dia por vez com o historico real.
Uso: python 04_redes_treinadas.py [caso ...]   (tempos em resultados/tempos_redes_<casos>.json)
"""
import gc, sys, time, json, logging, warnings
import numpy as np, pandas as pd, torch, torch.nn as nn
warnings.filterwarnings("ignore"); logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)
logging.getLogger("lightning.pytorch").setLevel(logging.ERROR)
from neuralforecast import NeuralForecast
from neuralforecast import models as M
from comum import carrega, grava, janelas, dobras, normaliza_por_treino, CASOS, EXOG, H, ENTRADA_NN, RES, PREV, REGIMES, DISPOSITIVO
from redes_proprias import (DEV, RECEITA_CROSSFORMER, RECEITA_MAMBA, CycleNet, ResNet1D, SparseTSF, chama_tslib,
                            crossformer, mamba, treina_multivariado, treina_proprio)

torch.set_num_threads(5)          # dois processos em paralelo (usinas | casas), ~5 GB livres
ARGS = sys.argv[1:]
CASOS_ARG = [a for a in ARGS if a in CASOS] or list(CASOS)
SO_MODELOS = ARGS[ARGS.index("--modelos") + 1].split(",") if "--modelos" in ARGS else None   # lote 2: so os novos
SO_REGIMES = ARGS[ARGS.index("--regimes") + 1].split(",") if "--regimes" in ARGS else None
VERSAO_ESCALA = "treino_sem_validacao_2026-10-06"
LOG = RES / ("tempos_redes_%s.json" % "_".join(CASOS_ARG))
# O que ja foi feito vem de TODOS os tempos_redes_*.json: o nome do arquivo depende dos casos passados na
# linha de comando, e olhar so o proprio fazia "04 casas_cons" retreinar tudo que esta em
# tempos_redes_casas_prod_casas_cons.json (corrigido em 09/10/2026).
def _le_tempos():
    t = {}
    for f in sorted(RES.glob("tempos_redes_*.json")):
        t.update(json.loads(f.read_text()))
    return t


tempos = _le_tempos()
COMUM = dict(h=H, input_size=ENTRADA_NN, max_steps=500, val_check_steps=50, early_stop_patience_steps=4,
             batch_size=16, windows_batch_size=128, inference_windows_batch_size=128,
             scaler_type="robust", random_seed=42, accelerator="gpu" if DISPOSITIVO == "cuda" else "cpu",
             enable_progress_bar=False,
             logger=False, enable_model_summary=False)


# Passo T (07/10/2026). As cinco redes abaixo exigem `devices=1` explicito: sem ele o Lightning
# levanta "devices selected with CPUAccelerator should be an int > 0". Nao entra no COMUM de proposito,
# para nao mexer na configuracao das 52 entradas que ja rodaram.
COMUM_T = {**COMUM, "devices": 1}


def modelos_nf(regime, n_series, caso):
    # Regime B: a normalizacao por janela (scaler_type) explode quando o clima futuro sai da faixa da janela
    # de entrada (semana nublada seguida de dia limpo -> previsoes de 99 kWh/h numa usina de 4 kW).
    # Solucao: normalizar cada serie usando so o treino anterior a validacao, sem
    # normalizacao por janela. local_scaler_type no cross_validation incluiria o teste.
    ex = dict(futr_exog_list=EXOG, scaler_type="identity") if regime != "A" else {}
    C = {**COMUM, **ex}
    base = {
        "LSTM": lambda: M.LSTM(**C), "GRU": lambda: M.GRU(**C),
        "NHITS": lambda: M.NHITS(**C),
        # layernorm=False: o MLPResidual do TiDE termina num LayerNorm sobre temporal_width (4 = o numero
        # de exogenas), aplicado em CADA hora. Isso tira a media e a escala das 4 variaveis de clima hora a
        # hora, ou seja, apaga a amplitude - exatamente o sinal de "quanto sol faz". Com o default o TiDE
        # ficava em nRMSE 0,59 no regime B contra 0,29 do NHITS; sem o layernorm vai a 0,28. Medido na
        # dobra 1 das usinas; temporal_width maior nao resolve, so o layernorm.
        "TiDE": lambda: M.TiDE(**C, layernorm=False), "KAN": lambda: M.KAN(**C),
        "NBEATSx": lambda: M.NBEATSx(**C),     # lote 2 (05/10/2026); o TimeXer do NeuralForecast nao aceita clima futuro
        # Passo T: estas quatro aceitam E usam o clima futuro (verificado embaralhando as exogenas e
        # vendo a previsao mudar), entao valem em A, B e C.
        "DeepAR": lambda: M.DeepAR(**{**COMUM_T, **ex}),
        "FEDformer": lambda: M.FEDformer(**{**COMUM_T, **ex}),
        "Autoformer": lambda: M.Autoformer(**{**COMUM_T, **ex}),
        "Informer": lambda: M.Informer(**{**COMUM_T, **ex}),
    }
    if regime == "A":
        base.update({"TCN": lambda: M.TCN(**COMUM), "DLinear": lambda: M.DLinear(**COMUM),
                     "iTransformer": lambda: M.iTransformer(n_series=n_series, **COMUM),
                     # era o mais lento e na v1/v2 em CPU rodou so nas usinas; em GPU deixou de ser caro
                     "PatchTST": lambda: M.PatchTST(**COMUM),
                     # Passo T, so no regime A. As tres primeiras levantam
                     # "does not support future exogenous variables" no NeuralForecast 3.1.9.
                     "TimeMixer": lambda: M.TimeMixer(n_series=n_series, **COMUM_T),
                     "TimeXer": lambda: M.TimeXer(n_series=n_series, **COMUM_T),
                     # TimeLLM FORA (08/10/2026). Tres motivos que se somam: (1) derrubou a maquina
                     # quatro vezes por falta de memoria - carrega um LLM e estoura o commit charge,
                     # que aqui tem so ~13 GB de folga (limite 40,8 GB = 31,8 de RAM + 9 de paginacao);
                     # (2) recusa covariavel futura, entao renderia so o regime A; (3) a familia LLM
                     # ja estava excluida por principio no levantamento, citando Tan et al. (NeurIPS
                     # 2024): tirar o LLM desses modelos nao piora o resultado. Para voltar, precisa de
                     # mais arquivo de paginacao ou de uma maquina com mais RAM.
                     # TimesNet aceita futr_exog_list mas IGNORA o conteudo: embaralhar o clima futuro
                     # nao muda a previsao (mesmo defeito do TiDE antes do layernorm=False). Fica so em A
                     # porque um resultado em B ou C seria "rede com clima" sem usar o clima.
                     "TimesNet": lambda: M.TimesNet(**COMUM_T)})
    else:
        base.update({"TFT": lambda: M.TFT(**C),
                     "TSMixerx": lambda: M.TSMixerx(n_series=n_series, **C)})
    return base


def df_nf(d, regime):
    x = d.copy()
    x["available_mask"] = x.y.notna().astype(float)
    x["y"] = x.y.fillna(0.0)
    cols = ["unique_id", "ds", "y", "available_mask"] + (EXOG if regime != "A" else [])
    return x[cols]


def para_janelas(cv, nome, ini=None, fim=None):
    cv = cv.copy(); cv["dia"] = cv.ds.dt.normalize()
    if ini is not None:
        # So os dias desta dobra. O cross_validation conta as n_windows a partir do fim de CADA serie,
        # entao uma serie que acaba antes das outras (H14 em casas_cons acaba em 11/12) recua e reemite
        # dias de uma dobra anterior - com um modelo treinado depois deles (vazamento) e duplicando linhas.
        cv = cv[(cv.dia >= ini) & (cv.dia <= fim.normalize())]
    jan, prev = [], []
    for (uid, dia), g in cv.groupby(["unique_id", "dia"]):
        if len(g) == H:
            jan.append(dict(unique_id=uid, ds_fut=pd.DatetimeIndex(g.ds))); prev.append(g[nome].to_numpy())
    return jan, prev


# ---------- SparseTSF, ResNet-1D e CycleNet proprias (univariadas, regime A): em redes_proprias.py ----------
# CycleNet: ciclo de 24 h na geracao e de 168 h no consumo (o periodo dominante de cada caso; o piloto
# testou os dois no consumo e deu empate), backbone Linear, perda L1 como os outros.
PROPRIAS = {"SparseTSF": lambda n, caso: SparseTSF(), "ResNet-1D": lambda n, caso: ResNet1D(),
            "CycleNet": lambda n, caso: CycleNet(n, 168 if caso == "casas_cons" else 24)}
# Multivariadas (todas as series do caso numa janela), regime A. Crossformer: etapa A, 10/10/2026 (TSLib, receita
# do script oficial de eletricidade; laco proprio porque o NeuralForecast nao tem o modelo). Deterministico na GPU
# (mesma semente, previsoes identicas), entao roda na GPU, diferente do CycleNet. Mamba: etapa A, 10/10/2026 (TSLib,
# bloco em PyTorch puro; lento: varredura sequencial).
MULTIVARIADAS = {"Crossformer": (crossformer, chama_tslib, RECEITA_CROSSFORMER),
                 "Mamba": (mamba, chama_tslib, RECEITA_MAMBA)}


def roda_nf(df, fab, caso, regime):
    """Treina do zero em cada dobra e preve os dias dela; devolve janelas, previsoes e parametros."""
    jan, prev, n_par = [], [], 0
    for ini, fim in dobras(caso):
        n = (fim.normalize() - ini).days + 1
        entrada = df[df.ds <= fim].copy()
        escalas = None
        if regime != "A":
            entrada, escalas = normaliza_por_treino(entrada, ini - pd.Timedelta(hours=720), ["y"] + EXOG)
        nf = NeuralForecast(models=[fab()], freq="h")
        cv = nf.cross_validation(df=entrada, n_windows=n, step_size=H, val_size=720, refit=False)
        col = [c for c in cv.columns if c not in ("unique_id", "ds", "cutoff", "y", "available_mask")][0]
        if escalas is not None:
            for uid, (media, desvio) in ((u, e["y"]) for u, e in escalas.items()):
                sel = cv.unique_id == uid
                cv.loc[sel, col] = cv.loc[sel, col] * desvio + media
        j, p = para_janelas(cv, col, ini, fim)
        jan += j; prev += p
        n_par = sum(x.numel() for x in nf.models[0].parameters())
        del nf, cv; gc.collect()
    return jan, prev, n_par


def anota(chave, t0, n_par, nome, caso, regime, disp=DISPOSITIVO):
    tempos[chave] = dict(segundos=round(time.time() - t0, 1), parametros=int(n_par), dobras=len(dobras(caso)),
                         dispositivo=disp, torch=torch.__version__)
    if regime != "A":
        tempos[chave]["normalizacao"] = VERSAO_ESCALA
    # rele o proprio arquivo antes de gravar: outro processo pode ter escrito nele (armadilha de 08/10)
    proprio = json.loads(LOG.read_text()) if LOG.exists() else {}
    proprio[chave] = tempos[chave]
    LOG.write_text(json.dumps(proprio, indent=1))
    print("OK    %-12s %-10s %s  %8d parametros  %6.0f s" % (nome, caso, regime, n_par, time.time() - t0), flush=True)


if __name__ == "__main__":
    falhas = 0
    for caso in CASOS_ARG:
        for regime in REGIMES[caso]:
            if SO_REGIMES and regime not in SO_REGIMES:
                continue
            d = carrega(caso, regime)
            df = df_nf(d, regime)
            for nome, fab in modelos_nf(regime, d.unique_id.nunique(), caso).items():
                chave = f"{nome}|{caso}|{regime}"
                feito = chave in tempos and (PREV / f"{nome}__{caso}__{regime}.parquet").exists()
                if regime != "A":
                    feito = feito and tempos[chave].get("normalizacao") == VERSAO_ESCALA
                if feito or (SO_MODELOS and nome not in SO_MODELOS):
                    continue
                t0 = time.time()
                try:
                    jan, prev, n_par = roda_nf(df, fab, caso, regime)
                    grava(nome, caso, regime, jan, prev)
                    anota(chave, t0, n_par, nome, caso, regime)
                except Exception as e:
                    falhas += 1
                    print("FALHA %-12s %-10s %s  %s: %s" % (nome, caso, regime, type(e).__name__, str(e)[:300]), flush=True)
                gc.collect()
        if SO_REGIMES and "A" not in SO_REGIMES:
            continue
        d = carrega(caso)
        for nome, fab in PROPRIAS.items():
            chave = f"{nome}|{caso}|A"
            if (chave in tempos and (PREV / f"{nome}__{caso}__A.parquet").exists()) or (SO_MODELOS and nome not in SO_MODELOS):
                continue
            t0 = time.time()
            try:
                jan, prev = [], []
                for ini, fim in dobras(caso):
                    j, p, n_par = treina_proprio(d, caso, lambda n: fab(n, caso), ini, fim)
                    jan += j; prev += p
                grava(nome, caso, "A", jan, prev)
                anota(chave, t0, n_par, nome, caso, "A", DEV.type)
            except Exception as e:
                falhas += 1
                print("FALHA %-12s %-10s A  %s: %s" % (nome, caso, type(e).__name__, str(e)[:300]), flush=True)
        for nome, (fab, chama, receita) in MULTIVARIADAS.items():
            chave = f"{nome}|{caso}|A"
            if (chave in tempos and (PREV / f"{nome}__{caso}__A.parquet").exists()) or (SO_MODELOS and nome not in SO_MODELOS):
                continue
            t0 = time.time()
            try:
                jan, prev = [], []
                for ini, fim in dobras(caso):
                    j, p, n_par = treina_multivariado(d, caso, fab, chama, ini, fim, **receita)
                    jan += j; prev += p
                    torch.cuda.empty_cache()
                grava(nome, caso, "A", jan, prev)
                anota(chave, t0, n_par, nome, caso, "A", DEV.type)
            except Exception as e:
                falhas += 1
                print("FALHA %-12s %-10s A  %s: %s" % (nome, caso, type(e).__name__, str(e)[:300]), flush=True)
    sys.exit(1 if falhas else 0)
