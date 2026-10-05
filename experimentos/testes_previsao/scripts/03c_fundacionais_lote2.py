# -*- coding: utf-8 -*-
"""Segundo lote de modelos fundacionais (zero-shot), escolhido na visao geral do levantamento
(revisao_edge_ai/Visao_geral_modelos_previsao.xlsx): os que tem codigo aberto e rodam em CPU.

Cada modelo roda no ambiente que as dependencias dele exigem:
  .venvs/lote2      Toto-2.0-22m, Toto-2.0-313m, TiRex-2, TabPFN-TS   (torch novo)
  .venvs/lote2_hf   Sundial-128m, Timer-XL-84m, Time-MoE-50M          (transformers 4.40.1, trust_remote_code)
  .venvs/moirai     Moirai-MoE-small                                  (uni2ts, torch antigo)
Mesmo protocolo dos outros fundacionais: 1024 h de historico, previsao das 24 h do dia seguinte as 00:00,
nenhum treino. Com clima (usinas B e C): TiRex-2 e TabPFN-TS, que aceitam covariaveis futuras.
Previsao pontual: a mediana (Toto 2.0, TiRex-2, TabPFN-TS, Moirai-MoE) ou a media das amostras (Sundial);
Timer-XL e Time-MoE sao deterministicos. Os tres do lote2_hf recebem a janela padronizada (media e desvio
da propria janela), como nos exemplos dos autores, e a previsao volta para a escala original.
Uso: python 03c_fundacionais_lote2.py MODELO [MODELO ...] [--smoke]   (--smoke: 3 janelas, nao grava)
Tempos em resultados/tempos_fundacionais_lote2.json.
"""
import gc, sys, time, json
import numpy as np, pandas as pd, torch
import truststore; truststore.inject_into_ssl()
from comum import carrega, janelas, grava, CASOS, EXOG, H, RES, REGIMES

torch.set_num_threads(10)
LOG = RES / "tempos_fundacionais_lote2.json"
COM_EXOG = {"TiRex-2", "TabPFN-TS"}


def em_lotes(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


# ---------------------------------------------------------------- .venvs/lote2
def toto2(hf):
    def f(jan, exog=False):
        from toto2 import Toto2Model
        m = Toto2Model.from_pretrained(hf).eval()
        out = []
        for lote in em_lotes(jan, 32):
            x = torch.tensor(np.stack([w["y"] for w in lote]))[:, None, :]          # (B, 1, T)
            with torch.no_grad():
                q = m.forecast({"target": x, "target_mask": torch.ones_like(x, dtype=torch.bool),
                                "series_ids": torch.zeros(x.shape[0], 1, dtype=torch.long)},
                               horizon=H, decode_block_size=768, has_missing_values=False)
            out += list(np.asarray(q[4, :, 0, :H], dtype=float))                     # quantil 0,5
        return out
    return f


def tirex2(jan, exog=False):
    from tirex2 import TimeseriesType, load_model
    # sem compilacao: a FlexAttention e o torch.compile exigem um compilador C++ que a maquina nao tem
    import torch._dynamo
    torch._dynamo.config.disable = True
    m = load_model("NX-AI/TiRex-2", device="cpu", use_flex_attention=False, compile=False)
    ts = []
    for w in jan:
        fut = None
        if exog:   # clima e ceu claro sao conhecidos no horizonte inteiro: covariaveis futuras [V, T+H]
            fut = torch.tensor(np.stack([np.r_[w["x_pass"][c], w["x_fut"][c]] for c in EXOG]), dtype=torch.float32)
        ts.append(TimeseriesType(target=torch.tensor(w["y"])[None], past_covariates=None, future_covariates=fut))
    out = []
    for lote in em_lotes(ts, 64):
        r = m.forecast(lote, prediction_length=H, output_type="numpy", batch_size=64)
        out += [np.asarray(x)[0, 4, :H] for x in r]                                   # (V, 9 quantis, H)
    return out


def tabpfn_ts(jan, exog=False):
    from tabpfn_time_series import TabPFNTSPipeline, TabPFNMode
    from tabpfn import TabPFNRegressor
    from tabpfn.constants import ModelVersion
    # pesos v2 (abertos). O padrao (v3.5) e os v2.5/v2.6 exigem conta e aceite de licenca na Prior Labs.
    v2 = TabPFNRegressor.create_default_for_version(ModelVersion.V2).model_path
    p = TabPFNTSPipeline(max_context_length=1024, tabpfn_mode=TabPFNMode.LOCAL,    # LOCAL: nada sai da maquina
                         tabpfn_model_config={"model_path": v2, "ignore_pretraining_limits": True})   # 1024 h > 1000 linhas
    out = []
    for lote in em_lotes(jan, 25):
        ctx, fut = [], []
        for k, w in enumerate(lote):
            ds_h = pd.date_range(end=w["ds_fut"][0] - pd.Timedelta("1h"), periods=len(w["y"]), freq="h")
            c = pd.DataFrame(dict(item_id=k, timestamp=ds_h, target=w["y"]))
            f = pd.DataFrame(dict(item_id=k, timestamp=w["ds_fut"]))
            if exog:
                for col in EXOG:
                    c[col] = w["x_pass"][col]; f[col] = w["x_fut"][col]
            ctx.append(c); fut.append(f)
        r = p.predict_df(pd.concat(ctx, ignore_index=True), future_df=pd.concat(fut, ignore_index=True), quantiles=[0.5])
        r = r.reset_index() if "item_id" not in r.columns else r
        for k in range(len(lote)):
            out.append(r[r.item_id == k].sort_values("timestamp").target.to_numpy(float)[:H])
    return out


# ---------------------------------------------------------------- .venvs/lote2_hf
def hf_causal(hf, amostras=None):
    def f(jan, exog=False):
        from transformers import AutoModelForCausalLM
        m = AutoModelForCausalLM.from_pretrained(hf, trust_remote_code=True).eval()
        out = []
        for lote in em_lotes(jan, 32):
            x = np.stack([w["y"] for w in lote]).astype(np.float32)
            mu, sd = x.mean(1, keepdims=True), x.std(1, keepdims=True) + 1e-6
            xn = torch.tensor((x - mu) / sd)
            with torch.no_grad():
                if amostras:                                     # Sundial: (B, amostras, H)
                    y = m.generate(xn, max_new_tokens=H, num_samples=amostras).numpy().mean(1)
                else:                                            # Timer-XL e Time-MoE: (B, [T+]H)
                    y = m.generate(xn, max_new_tokens=H).numpy()[:, -H:]
            out += list(y * sd + mu)
        return out
    return f


# ---------------------------------------------------------------- .venvs/moirai
def moirai_moe(jan, exog=False):
    from uni2ts.model.moirai_moe import MoiraiMoEForecast, MoiraiMoEModule
    m = MoiraiMoEForecast(module=MoiraiMoEModule.from_pretrained("Salesforce/moirai-moe-1.0-R-small"),
                          prediction_length=H, context_length=1024, patch_size=16, num_samples=100,
                          target_dim=1, feat_dynamic_real_dim=0, past_feat_dynamic_real_dim=0).eval()
    out = []
    for lote in em_lotes(jan, 64):
        x = torch.tensor(np.stack([w["y"] for w in lote]))[:, :, None]                # (B, T, 1)
        with torch.no_grad():
            s = m(past_target=x, past_observed_target=torch.ones_like(x, dtype=torch.bool),
                  past_is_pad=torch.zeros(x.shape[:2], dtype=torch.bool))
        out += list(np.median(s.numpy(), axis=1).reshape(len(lote), -1)[:, :H])
    return out


MODELOS = {"Toto-2.0-22m": toto2("Datadog/Toto-2.0-22m"), "Toto-2.0-313m": toto2("Datadog/Toto-2.0-313m"),
           "TiRex-2": tirex2, "TabPFN-TS": tabpfn_ts,
           "Sundial-128m": hf_causal("thuml/sundial-base-128m", amostras=20),
           "Timer-XL-84m": hf_causal("thuml/timer-base-84m"), "Time-MoE-50M": hf_causal("Maple728/TimeMoE-50M"),
           "Moirai-MoE-small": moirai_moe}

if __name__ == "__main__":
    args = sys.argv[1:]
    smoke = "--smoke" in args
    escolhidos = [a for a in args if a in MODELOS]
    tempos = json.loads(LOG.read_text()) if LOG.exists() else {}
    for nome in escolhidos:
        for caso in (["usinas"] if smoke else CASOS):          # smoke: so as usinas, todos os regimes
            for regime in (REGIMES[caso] if nome in COM_EXOG else ["A"]):
                chave = f"{nome}|{caso}|{regime}"
                if chave in tempos and not smoke:
                    continue
                t0 = time.time()
                try:
                    jan = janelas(carrega(caso, regime), caso, exog=(regime != "A"))
                    if smoke:
                        jan = jan[:3]
                    prev = MODELOS[nome](jan, exog=(regime != "A"))
                    p = np.asarray(prev, float)
                    assert p.shape == (len(jan), H) and np.isfinite(p).all(), f"forma {p.shape} ou valores nao finitos"
                    dt = time.time() - t0
                    if smoke:
                        print("SMOKE %-17s %-10s %s  %d janelas  %5.1f s  max %.2f" % (nome, caso, regime, len(jan), dt, p.max()), flush=True)
                        continue
                    grava(nome, caso, regime, jan, prev)
                    tempos = json.loads(LOG.read_text()) if LOG.exists() else {}
                    tempos[chave] = dict(segundos=round(dt, 1), janelas=len(jan))
                    LOG.write_text(json.dumps(tempos, indent=1))
                    print("OK    %-17s %-10s %s  %5d janelas  %6.0f s" % (nome, caso, regime, len(jan), dt), flush=True)
                except Exception as e:
                    print("FALHA %-17s %-10s %s  %s: %s" % (nome, caso, regime, type(e).__name__, str(e)[:300]), flush=True)
                gc.collect()
