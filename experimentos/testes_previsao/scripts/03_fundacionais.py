# -*- coding: utf-8 -*-
"""Modelos fundacionais, zero-shot (sem nenhum treino nestes dados).

Regime A (todos os casos): so o historico.  Regimes B e C (usinas): Chronos-2 e TimesFM-2.5 com
ceu claro + clima do dia como covariaveis (B: NASA, o teto; C: previsao real da vespera).
Nao treinam, entao a origem movel nao muda nada aqui.
Previsao pontual: a que cada modelo entrega por padrao (mediana no Chronos, media no TiRex,
TimesFM, TTM e Toto). Uso: python 03_fundacionais.py [modelo ...] [--casos c1,c2] [--regimes A,B,C]
"""
import gc, sys, time, json
import numpy as np, torch
import truststore; truststore.inject_into_ssl()
from comum import carrega, janelas, grava, CASOS, H, RES, REGIMES

torch.set_num_threads(10)
LOG = RES / "tempos_fundacionais.json"
tempos = json.loads(LOG.read_text()) if LOG.exists() else {}


def em_lotes(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def chronos2(jan, exog=False):
    from chronos import BaseChronosPipeline
    p = BaseChronosPipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
    qs = list(p.quantiles); i50 = int(np.argmin(np.abs(np.array(qs) - 0.5)))
    ent = []
    for w in jan:
        e = {"target": w["y"]}
        if exog:
            e["past_covariates"] = dict(w["x_pass"]); e["future_covariates"] = dict(w["x_fut"])
        ent.append(e)
    out = []
    for lote in em_lotes(ent, 64):
        r = p.predict(lote, prediction_length=H)
        out += [x[0, i50].numpy() for x in r]
    return out


def chronos_bolt(jan, exog=False):
    from chronos import BaseChronosPipeline
    p = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-small", device_map="cpu")
    out = []
    for lote in em_lotes(jan, 128):
        x = torch.tensor(np.stack([w["y"] for w in lote]))
        _, m = p.predict_quantiles(x, prediction_length=H, quantile_levels=[0.5])
        out += list(m.numpy())
    return out


def timesfm25(jan, exog=False):
    import timesfm
    m = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    m.compile(timesfm.ForecastConfig(max_context=1024, max_horizon=256, normalize_inputs=True, per_core_batch_size=64,
                                     use_continuous_quantile_head=True, return_backcast=exog))
    if not exog:
        p, _ = m.forecast(horizon=H, inputs=[w["y"] for w in jan])
        return list(p[:, -H:])
    # covariaveis: regressao linear sobre as exogenas + TimesFM no residuo ("xreg + timesfm")
    cov = {c: [np.r_[w["x_pass"][c], w["x_fut"][c]] for w in jan] for c in jan[0]["x_pass"]}
    p, _ = m.forecast_with_covariates(inputs=[w["y"] for w in jan], dynamic_numerical_covariates=cov,
                                      xreg_mode="xreg + timesfm", force_on_cpu=True)
    return [np.asarray(x)[-H:] for x in p]


def tirex(jan, exog=False):
    from tirex import load_model
    m = load_model("NX-AI/TiRex", device="cpu", backend="torch")
    out = []
    for lote in em_lotes(jan, 128):
        x = torch.tensor(np.stack([w["y"] for w in lote]))
        _, mean = m.forecast(context=x, prediction_length=H)
        out += list(mean.numpy())
    return out


def ttm(jan, exog=False):
    from tsfm_public.toolkit.get_model import get_model
    m = get_model("ibm-granite/granite-timeseries-ttm-r2", context_length=1024, prediction_length=H).eval()
    out = []
    with torch.no_grad():
        for lote in em_lotes(jan, 256):
            x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]
            out += list(m(past_values=x).prediction_outputs[:, :H, 0].numpy())
    return out


def toto(jan, exog=False):
    from toto.model.toto import Toto
    from toto.inference.forecaster import TotoForecaster
    from toto.data.util.dataset import MaskedTimeseries
    # o huggingface_hub novo deixou de repassar proxies/resume_download, que o Toto ainda exige:
    # baixa os pesos e chama o carregador interno com todos os argumentos
    from huggingface_hub import snapshot_download
    pasta = snapshot_download("Datadog/Toto-Open-Base-1.0")
    cfg = json.loads(open(f"{pasta}/config.json").read())
    t = Toto._from_pretrained(model_id=pasta, revision=None, cache_dir=None, force_download=False, proxies=None,
                              resume_download=None, local_files_only=True, token=None, **cfg).eval()
    f = TotoForecaster(t.model)
    out = []
    for lote in em_lotes(jan, 32):
        x = torch.tensor(np.stack([w["y"] for w in lote]))[:, None, :]
        B, _, L = x.shape
        ts = torch.tensor(np.stack([(w["ds_fut"][0].value // 10**9) - 3600 * np.arange(L, 0, -1) for w in lote]))[:, None, :]
        inp = MaskedTimeseries(series=x, padding_mask=torch.ones_like(x, dtype=torch.bool), id_mask=torch.zeros_like(x, dtype=torch.int),
                               timestamp_seconds=ts, time_interval_seconds=torch.full((B, 1), 3600))
        with torch.no_grad():
            r = f.forecast(inp, prediction_length=H, num_samples=None)
        out += list(r.mean[:, 0, :].numpy())
    return out


def flowstate(jan, exog=False):
    """FlowState (IBM, ~9,1 M param.): codificador S5 + decodificador de base funcional. Entrou em 09/10/2026
    depois de passar no piloto (piloto_flowstate.py, mesmo codigo). scale_factor 1,0 = serie horaria
    (tsfm_public.models.flowstate.utils.get_fixed_factor("H")). Precisa do granite-tsfm completo (Lactec)."""
    from tsfm_public import FlowStateForPrediction
    m = FlowStateForPrediction.from_pretrained("ibm-granite/granite-timeseries-flowstate-r1").eval()
    out = []
    with torch.no_grad():
        for lote in em_lotes(jan, 128):
            x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]
            r = m(past_values=x, scale_factor=1.0, prediction_length=H, batch_first=True)
            out += list(r.prediction_outputs[:, :H, 0].numpy())
    return out


MODELOS = {"Chronos-2": chronos2, "Chronos-Bolt-small": chronos_bolt, "TimesFM-2.5": timesfm25,
           "TiRex": tirex, "TTM-r2": ttm, "Toto": toto, "FlowState": flowstate}
COM_EXOG = {"Chronos-2", "TimesFM-2.5"}

if __name__ == "__main__":
    args = sys.argv[1:]
    so_casos = args[args.index("--casos") + 1].split(",") if "--casos" in args else list(CASOS)
    so_regimes = args[args.index("--regimes") + 1].split(",") if "--regimes" in args else None
    escolhidos = [a for a in args if a in MODELOS] or list(MODELOS)
    for nome in escolhidos:
        for caso in so_casos:
            for regime in (REGIMES[caso] if nome in COM_EXOG else ["A"]):
                if (so_regimes and regime not in so_regimes) or f"{nome}|{caso}|{regime}" in tempos:
                    continue                          # ja feito (nao treina: refazer daria o mesmo)
                t0 = time.time()
                try:
                    jan = janelas(carrega(caso, regime), caso, exog=(regime != "A"))
                    prev = MODELOS[nome](jan, exog=(regime != "A"))
                    grava(nome, caso, regime, jan, prev)
                    dt = time.time() - t0
                    tempos[f"{nome}|{caso}|{regime}"] = dict(segundos=round(dt, 1), janelas=len(jan))
                    print("OK    %-20s %-10s %s  %5d janelas  %6.0f s" % (nome, caso, regime, len(jan), dt), flush=True)
                except Exception as e:
                    print("FALHA %-20s %-10s %s  %s: %s" % (nome, caso, regime, type(e).__name__, str(e)[:300]), flush=True)
                LOG.write_text(json.dumps(tempos, indent=1))
                gc.collect()
