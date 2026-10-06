# -*- coding: utf-8 -*-
"""Redes treinadas nestes dados (NeuralForecast + SparseTSF e ResNet-1D proprias).

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

torch.set_num_threads(5)          # dois processos em paralelo (usinas | casas), ~5 GB livres
DEV = torch.device("cuda" if DISPOSITIVO == "cuda" and torch.cuda.is_available() else "cpu")
ARGS = sys.argv[1:]
CASOS_ARG = [a for a in ARGS if a in CASOS] or list(CASOS)
SO_MODELOS = ARGS[ARGS.index("--modelos") + 1].split(",") if "--modelos" in ARGS else None   # lote 2: so os novos
SO_REGIMES = ARGS[ARGS.index("--regimes") + 1].split(",") if "--regimes" in ARGS else None
VERSAO_ESCALA = "treino_sem_validacao_2026-10-06"
LOG = RES / ("tempos_redes_%s.json" % "_".join(CASOS_ARG))
tempos = json.loads(LOG.read_text()) if LOG.exists() else {}
COMUM = dict(h=H, input_size=ENTRADA_NN, max_steps=500, val_check_steps=50, early_stop_patience_steps=4,
             batch_size=16, windows_batch_size=128, inference_windows_batch_size=128,
             scaler_type="robust", random_seed=42, accelerator="gpu" if DISPOSITIVO == "cuda" else "cpu",
             enable_progress_bar=False,
             logger=False, enable_model_summary=False)


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
    }
    if regime == "A":
        base.update({"TCN": lambda: M.TCN(**COMUM), "DLinear": lambda: M.DLinear(**COMUM),
                     "iTransformer": lambda: M.iTransformer(n_series=n_series, **COMUM),
                     # era o mais lento e na v1/v2 em CPU rodou so nas usinas; em GPU deixou de ser caro
                     "PatchTST": lambda: M.PatchTST(**COMUM)})
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


# ---------- SparseTSF e ResNet-1D proprias (univariadas, regime A) ----------
class SparseTSF(nn.Module):
    """Lin et al. (2024): subamostra a serie por periodo (24 h) e aplica uma linear compartilhada."""
    def __init__(self, L=ENTRADA_NN, Hh=H, p=24):
        super().__init__(); self.p = p
        self.conv = nn.Conv1d(1, 1, kernel_size=1 + 2 * (p // 2), padding=p // 2, bias=False)
        self.lin = nn.Linear(L // p, Hh // p, bias=False)
    def forward(self, x):                       # x: (B, L) normalizado
        B, L = x.shape
        x = self.conv(x[:, None, :])[:, 0, :] + x
        x = x.reshape(B, L // self.p, self.p).permute(0, 2, 1)       # (B, p, L/p)
        return self.lin(x).permute(0, 2, 1).reshape(B, -1)


class Bloco(nn.Module):
    def __init__(self, ci, co):
        super().__init__()
        self.c = nn.Sequential(nn.Conv1d(ci, co, 7, padding=3), nn.BatchNorm1d(co), nn.ReLU(),
                               nn.Conv1d(co, co, 5, padding=2), nn.BatchNorm1d(co), nn.ReLU(),
                               nn.Conv1d(co, co, 3, padding=1), nn.BatchNorm1d(co))
        self.s = nn.Sequential(nn.Conv1d(ci, co, 1), nn.BatchNorm1d(co)) if ci != co else nn.Identity()
    def forward(self, x):
        return torch.relu(self.c(x) + self.s(x))


class ResNet1D(nn.Module):
    """ResNet para series (Wang et al., 2017), com cabeca de regressao de 24 saidas."""
    def __init__(self, Hh=H):
        super().__init__()
        self.b = nn.Sequential(Bloco(1, 32), Bloco(32, 64), Bloco(64, 64))
        self.head = nn.Linear(64, Hh)
    def forward(self, x):
        return self.head(self.b(x[:, None, :]).mean(-1))


def treina_proprio(d, caso, cls, ini, fim, epocas=30):
    Xs, Ys = [], []
    for uid, g in d.groupby("unique_id"):
        y = g.set_index("ds").y
        tr = y[y.index < ini].interpolate(limit_direction="both").to_numpy(np.float32)
        for k in range(ENTRADA_NN, len(tr) - H + 1, 6):                  # janelas a cada 6 h
            Xs.append(tr[k - ENTRADA_NN:k]); Ys.append(tr[k:k + H])
    X, Y = np.stack(Xs), np.stack(Ys)
    mu, sd = X.mean(1, keepdims=True), X.std(1, keepdims=True) + 1e-3
    X, Y = torch.tensor((X - mu) / sd).to(DEV), torch.tensor((Y - mu) / sd).to(DEV)
    torch.manual_seed(42); rng = np.random.default_rng(42)
    idx = rng.permutation(len(X)); nval = len(X) // 10
    va, trn = idx[:nval], idx[nval:]
    m = cls().to(DEV); opt = torch.optim.Adam(m.parameters(), lr=1e-3); melhor, estado, paciencia = 1e9, None, 0
    for ep in range(epocas):
        m.train()
        for i in range(0, len(trn), 256):
            b = trn[i:i + 256]
            opt.zero_grad(); loss = nn.functional.l1_loss(m(X[b]), Y[b]); loss.backward(); opt.step()
        m.eval()
        with torch.no_grad():
            v = nn.functional.l1_loss(m(X[va]), Y[va]).item()
        if v < melhor - 1e-4:
            melhor, estado, paciencia = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        else:
            paciencia += 1
            if paciencia >= 4:
                break
        rng.shuffle(trn)
    m.load_state_dict(estado); m.eval()
    # previsao: janela de 168 h antes de cada dia de teste da dobra
    jan = [w for w in janelas(d, caso, contexto=ENTRADA_NN) if ini <= w["dia"] <= fim]
    Xt = np.stack([w["y"] for w in jan]); mu, sd = Xt.mean(1, keepdims=True), Xt.std(1, keepdims=True) + 1e-3
    with torch.no_grad():
        p = m(torch.tensor((Xt - mu) / sd).to(DEV)).cpu().numpy() * sd + mu
    return jan, list(p), sum(t.numel() for t in m.parameters())


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
                         dispositivo=disp)
    if regime != "A":
        tempos[chave]["normalizacao"] = VERSAO_ESCALA
    LOG.write_text(json.dumps(tempos, indent=1))
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
        for nome, cls in [("SparseTSF", SparseTSF), ("ResNet-1D", ResNet1D)]:
            chave = f"{nome}|{caso}|A"
            if (chave in tempos and (PREV / f"{nome}__{caso}__A.parquet").exists()) or (SO_MODELOS and nome not in SO_MODELOS):
                continue
            t0 = time.time()
            try:
                jan, prev = [], []
                for ini, fim in dobras(caso):
                    j, p, n_par = treina_proprio(d, caso, cls, ini, fim)
                    jan += j; prev += p
                grava(nome, caso, "A", jan, prev)
                anota(chave, t0, n_par, nome, caso, "A", DEV.type)
            except Exception as e:
                falhas += 1
                print("FALHA %-12s %-10s A  %s: %s" % (nome, caso, type(e).__name__, str(e)[:300]), flush=True)
    sys.exit(1 if falhas else 0)
