"""G1 / P1-gpu (servidor, 18/11/2026): fundacionais com as 6 NWP como covariaveis, leads 1-7, nas duas usinas,
contra a cadeia fisica do app (`outlook.forecast_ahead`) e o LightGBM 6-NWP do F2(a).

Portao em docs/projeto/PILOTOS_F1_F2.md, "G1" (commitado antes de rodar). Resumo do metodo:
  Toda noite e (dados ate 23:00 de e), uma previsao de 168 h (dias e+1 .. e+7 = leads 1-7). Alvo: kWh por hora.
  Covariaveis por hora: poa_ceu_claro (geometria) e, para cada um dos 6 modelos padrao (`io.open_meteo.DEFAULT_MODELS`),
  poa_<m> = poa_ceu_claro * clip(ghi_<m> / ghi_ceu_claro, 0, 1,3) (a conversao do regime C), mais poa_media e
  poa_desvio. Futuro: o dia e+k usa o `previous_day{k}` (o que existia na noite e). Passado (1024 h): o lead 1.
  Modelo sem valor numa hora: a media dos outros; nenhum: poa_ceu_claro * 0,6 (raro; contado). Historico do alvo:
  buracos interpolados (ate 6 h), o resto 0. Previsao < 0 vira 0; noite (poa_ceu_claro = 0) vira 0.
  Modelos: Chronos-2 (mediana; ambiente previsao) e TabPFN-TS (pesos v2 abertos, LOCAL; ambiente lote2).
  Referencia fisica: o replay do app de hoje (`piloto_uso_prolongado.replay`, padroes, nada reajustado).

Uso:
  python piloto_p1_gpu.py fisico Cascavel|Curitiba     (ambiente da biblioteca, CPU; replay do app, retoma)
  python piloto_p1_gpu.py prever Chronos-2|TabPFN-TS   (ambiente previsao | lote2; GPU; retoma por usina)
  python piloto_p1_gpu.py avalia                       (ambiente da biblioteca)
Saidas: resultados/pilotos/p1gpu_<modelo>__usinas__<serie>.parquet, fisico_g1__usinas__<serie>.parquet (privados,
fora do git) e resultados/pilotos/p1gpu.json (agregados).
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from comum import DADOS, SITIOS, ghi_ceu_claro  # noqa: E402
from piloto_comum import PILOTOS  # noqa: E402

MODELOS_NWP = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "meteofrance_seamless", "gem_seamless",
               "cma_grapes_global"]
PRIMEIRO, ULTIMO = pd.Timestamp("2025-08-01"), pd.Timestamp("2026-11-15")
TESTE = (pd.Timestamp("2025-08-01"), pd.Timestamp("2026-05-31"))
INTOCADO = (pd.Timestamp("2026-06-01"), pd.Timestamp("2026-11-15"))
CTX, HOR, LEADS = 1024, 168, 7
DEV = os.environ.get("DISPOSITIVO", "cuda")


def arq(modelo, serie):
    return PILOTOS / f"p1gpu_{modelo}__usinas__{serie}.parquet"


def entradas(serie):
    """Grade horaria da usina: y (kWh, NaN invalido), cs, e o tempo por lead (dict lead -> DataFrame poa_<m>)."""
    u = pd.read_parquet(DADOS / "usinas_horario_v1.parquet")
    u = u[u.serie == serie].set_index("ds").sort_index()
    y = (u.y_Wh / 1000).where(u.y_valido)
    cs = u.poa_ceu_claro
    gcs = ghi_ceu_claro(serie, u.index).where(lambda x: x > 20)
    H = pd.read_parquet(DADOS / "previsao_tempo_horizonte_v1.parquet")
    H = H[H.serie == serie]
    por_lead, faltas = {}, 0
    for k in range(1, LEADS + 1):
        w = H[H.lead == k].pivot_table(index="ds", columns="modelo_nwp", values="ghi").reindex(u.index)
        poa = pd.DataFrame({f"poa_{m}": (cs * (w[m] / gcs).clip(0, 1.3)) if m in w else np.nan for m in MODELOS_NWP})
        poa = poa.where(cs > 0, 0.0)
        media = poa.mean(axis=1)
        faltas += int((media.isna() & (cs > 0) & (cs.index >= PRIMEIRO)).sum())   # so no periodo avaliado
        media = media.fillna(cs * 0.6)
        poa = poa.apply(lambda c: c.fillna(media))
        poa["poa_media"], poa["poa_desvio"] = poa.mean(axis=1), poa.std(axis=1).fillna(0.0)
        poa["poa_ceu_claro"] = cs
        por_lead[k] = poa.astype("float32")
    return y, cs, por_lead, faltas


def janela(y, por_lead, e):
    """Entradas da noite e: alvo (CTX h), covariaveis passadas (lead 1) e futuras (dia e+k = lead k)."""
    ini_fut = e + pd.Timedelta(days=1)
    hist = pd.date_range(end=ini_fut - pd.Timedelta(hours=1), periods=CTX, freq="h")
    alvo = y.reindex(hist).interpolate(limit=6, limit_area="inside").fillna(0.0).to_numpy("float32")
    passado = por_lead[1].reindex(hist).fillna(0.0)
    fut = pd.concat([por_lead[k].reindex(pd.date_range(ini_fut + pd.Timedelta(days=k - 1), periods=24, freq="h"))
                     for k in range(1, LEADS + 1)]).fillna(0.0)
    return alvo, passado, fut


def chronos2(lote):
    global _P
    if "_P" not in globals():
        from chronos import BaseChronosPipeline
        _P = BaseChronosPipeline.from_pretrained("amazon/chronos-2", device_map=DEV)
    qs = list(_P.quantiles)
    i50 = int(np.argmin(np.abs(np.array(qs) - 0.5)))
    ent = [{"target": a, "past_covariates": {c: p[c].to_numpy() for c in p},
            "future_covariates": {c: f[c].to_numpy() for c in f}} for a, p, f in lote]
    return [x[0, i50].cpu().numpy() for x in _P.predict(ent, prediction_length=HOR)]


def tabpfn(lote):
    global _T
    if "_T" not in globals():
        from tabpfn import TabPFNRegressor
        from tabpfn.constants import ModelVersion
        from tabpfn_time_series import TabPFNMode, TabPFNTSPipeline
        v2 = TabPFNRegressor.create_default_for_version(ModelVersion.V2).model_path
        _T = TabPFNTSPipeline(max_context_length=CTX, tabpfn_mode=TabPFNMode.LOCAL,
                              tabpfn_model_config={"model_path": v2, "ignore_pretraining_limits": True})
    ctx, fut = [], []
    for k, (a, p, f) in enumerate(lote):
        c = pd.DataFrame(dict(item_id=k, timestamp=p.index, target=a)).reset_index(drop=True)
        g = pd.DataFrame(dict(item_id=k, timestamp=f.index)).reset_index(drop=True)
        for col in p.columns:
            c[col] = p[col].to_numpy(); g[col] = f[col].to_numpy()
        ctx.append(c); fut.append(g)
    r = _T.predict_df(pd.concat(ctx, ignore_index=True), future_df=pd.concat(fut, ignore_index=True), quantiles=[0.5])
    r = r.reset_index() if "item_id" not in r.columns else r
    return [r[r.item_id == k].sort_values("timestamp").target.to_numpy(float)[:HOR] for k in range(len(lote))]


MODELOS = {"Chronos-2": (chronos2, 32), "TabPFN-TS": (tabpfn, 8)}


def prever(nome):
    fn, n_lote = MODELOS[nome]
    rel_t = {}
    for serie in SITIOS:
        y, cs, por_lead, faltas = entradas(serie)
        noites = pd.date_range(PRIMEIRO - pd.Timedelta(days=1), ULTIMO - pd.Timedelta(days=1), freq="D")
        antigos = pd.read_parquet(arq(nome, serie)) if arq(nome, serie).exists() else None
        feitas = set(pd.to_datetime(antigos.emissao).unique()) if antigos is not None else set()
        faltam = [e for e in noites if e not in feitas]
        partes = [antigos] if antigos is not None else []
        t0 = time.time()
        for i in range(0, len(faltam), n_lote):
            lote_e = faltam[i:i + n_lote]
            lote = [janela(y, por_lead, e) for e in lote_e]
            prev = fn(lote)
            for e, (_, _, f), p in zip(lote_e, lote, prev):
                p = np.clip(np.asarray(p, float)[:HOR], 0, None) * (cs.reindex(f.index).to_numpy() > 0)
                partes.append(pd.DataFrame({"emissao": e, "ds": f.index, "lead": np.repeat(np.arange(1, LEADS + 1), 24),
                                            "yhat": p}))
            pd.concat(partes, ignore_index=True).to_parquet(arq(nome, serie), index=False)
            print(f"{nome} {serie} {i + len(lote_e)}/{len(faltam)} noites, {time.time() - t0:.0f} s", flush=True)
        # tempo de inferencia por sitio na CPU (regra de velocidade de 16/10): 7 noites, uma por vez
        if nome == "Chronos-2":
            global _P
            dev_ant = DEV
            globals()["DEV"] = "cpu"
            _P = None
            del globals()["_P"]
            t1 = time.time()
            for e in noites[-7:]:
                fn([janela(y, por_lead, e)])
            rel_t[serie] = dict(cpu_s_por_noite=round((time.time() - t1) / 7, 2), horas_sem_nwp=faltas)
            globals()["DEV"] = dev_ant
            del globals()["_P"]
        else:
            rel_t[serie] = dict(horas_sem_nwp=faltas)
    f = PILOTOS / "p1gpu_tempos.json"
    atual = json.loads(f.read_text()) if f.exists() else {}
    atual[nome] = rel_t
    f.write_text(json.dumps(atual, indent=1))


def fisico(serie):
    import piloto_uso_prolongado as V
    V.ARQ_USINAS, V.ARQ_HORIZONTE = "usinas_horario_v1.parquet", "previsao_tempo_horizonte_v1.parquet"
    V.PRIMEIRO_ALVO, V.ULTIMO_ALVO = PRIMEIRO, ULTIMO
    V.arq = lambda s: PILOTOS / f"fisico_g1__usinas__{s}.parquet"
    V.replay(serie)


def avalia():
    import piloto_uso_prolongado as V
    rel = {"portao": "docs/projeto/PILOTOS_F1_F2.md, G1"}
    tempos = json.loads((PILOTOS / "p1gpu_tempos.json").read_text()) if (PILOTOS / "p1gpu_tempos.json").exists() else {}
    rel["tempos"] = tempos
    passa = {m: True for m in MODELOS}
    for serie in SITIOS:
        y, cs, _, _ = entradas(serie)
        F = pd.read_parquet(PILOTOS / f"fisico_g1__usinas__{serie}.parquet")[["emissao", "ds", "lead", "yF", "ys", "sol"]]
        tabs = {}
        for m in MODELOS:
            if arq(m, serie).exists():
                tabs[m] = pd.read_parquet(arq(m, serie)).rename(columns={"yhat": m})
        L = PILOTOS / "LightGBM-C-multi6__usinas__C.parquet"
        lgb = pd.read_parquet(L) if L.exists() else None
        if lgb is not None:
            lgb = lgb[lgb.unique_id == serie][["ds", "yhat"]].rename(columns={"yhat": "LightGBM-6NWP"})
        T = F.copy()
        for m, t in tabs.items():
            T = T.merge(t, on=["emissao", "ds", "lead"], how="left")
        if lgb is not None:
            T = T.merge(lgb.assign(lead=1), on=["ds", "lead"], how="left")
        T["y"] = y.reindex(T.ds).to_numpy()
        T["alvo"] = T.ds.dt.normalize()
        ok = T.groupby(["emissao", "lead"]).apply(lambda g: g.y[g.sol].notna().all(), include_groups=False)
        cols = ["y", "yF", "ys"] + list(tabs) + (["LightGBM-6NWP"] if lgb is not None else [])
        D = T.groupby(["emissao", "lead"])[cols].sum(min_count=1)
        D["alvo"] = T.groupby(["emissao", "lead"]).alvo.first()
        D = D[ok.reindex(D.index).fillna(False)].reset_index()
        hor = T[T.sol & T.y.notna()]
        R = {}
        for nome_p, (a, b) in (("teste", TESTE), ("intocado", INTOCADO)):
            for k in range(1, LEADS + 1):
                q = D[(D.lead == k) & (D.alvo >= a) & (D.alvo <= b)]
                h = hor[(hor.lead == k) & (hor.alvo >= a) & (hor.alvo <= b)]
                if len(q) < 10:
                    continue
                rm = lambda c, x=q: float(np.sqrt(((x.y - x[c]) ** 2).mean()))  # noqa: E731
                cel = dict(n_dias=len(q), skill_dia_fisico=1 - rm("yF") / rm("ys"))
                for m in list(tabs) + (["LightGBM-6NWP"] if (k == 1 and lgb is not None) else []):
                    qq = q.dropna(subset=[m])
                    hh = h.dropna(subset=[m])
                    sk = 1 - rm(m, qq) / rm("ys", qq)
                    skF = 1 - rm("yF", qq) / rm("ys", qq)
                    dl = ((qq.y - qq[m]) ** 2 - (qq.y - qq.yF) ** 2).groupby(qq.alvo).mean().sort_index()
                    rh = lambda c, x=hh: float(np.sqrt(((x.y - x[c]) ** 2).mean()))  # noqa: E731
                    cel[m] = dict(n=len(qq), skill_dia=sk, ganho_sobre_fisico=sk - skF, p_dm=V._dm(-dl.to_numpy()),
                                  skill_hora=1 - rh(m) / rh("ys"), skill_hora_fisico=1 - rh("yF") / rh("ys"))
                R[f"{nome_p}_lead{k}"] = cel
        rel[serie] = R
        for m in MODELOS:
            c = R.get("teste_lead1", {}).get(m)
            passa[m] = passa[m] and bool(c and c["ganho_sobre_fisico"] >= 0.02 and c["p_dm"] < 0.05)
    rel["PASSA"] = passa
    rel["nota"] = "o periodo intocado so e lido como confirmacao do modelo que PASSA no teste (portao G1)"
    (PILOTOS / "p1gpu.json").write_text(json.dumps(rel, indent=1, default=float), encoding="utf-8")
    print(json.dumps({s: rel[s].get("teste_lead1") for s in SITIOS}, indent=1, default=float))
    print("PASSA", passa)


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "fisico":
        fisico(sys.argv[2])
    elif c == "prever":
        prever(sys.argv[2])
    elif c == "avalia":
        avalia()
