# -*- coding: utf-8 -*-
"""Junta todas as previsoes com o real e calcula as metricas.

Horas avaliadas: usinas -> ceu claro > 0; casas_prod -> horas do dia com producao media > 1% do pico;
casas_cons -> todas. Previsoes negativas viram zero (vale para todos).
Metricas: nMAE, nRMSE e MBE normalizados pela media do real nas horas avaliadas; erro da energia diaria;
skill = 1 - RMSE/RMSE_ref (ref: persist_ceu_claro nas usinas, persist_24h nas casas), com IC 95%
por bootstrap de dias inteiros (1000 reamostragens).

v2 (05/10/2026):
  metricas_por_dobra.csv  skill e nRMSE em cada dobra da origem movel (comum.dobras)
  dm_vs_melhor.csv        Diebold-Mariano de cada modelo contra o melhor do mesmo caso e regime
  dm_regimes.csv          Diebold-Mariano entre regimes (usinas): C x A, C x B, C-gfs x C, B-curto x B
Diebold-Mariano: perda = erro quadratico; diferenca media por dia (todas as series e horas avaliadas
do dia), variancia de Newey-West com defasagem floor(T^(1/3)), correcao de Harvey-Leybourne-Newbold
e t de Student com T-1 graus. Holm sobre a familia de cada caso e regime. "Empatado com o melhor":
p de Holm >= 0,05.
Uma nao rejeicao nao prova equivalencia; o melhor foi escolhido neste mesmo teste.
Cada comparacao com a referencia usa as mesmas horas com alvo e previsoes finitos.
"""
import warnings
import numpy as np, pandas as pd
from scipy import stats
warnings.filterwarnings("ignore")
from comum import carrega, dobras, PREV, RES, CASOS

REF = {"usinas": "persist_ceu_claro", "casas_prod": "persist_24h", "casas_cons": "persist_24h"}
REFERENCIAS = {"persist_24h", "semanal_168h", "media_7d", "persist_ceu_claro"}
rng = np.random.default_rng(42)


def real(caso):
    """Alvo do periodo de teste e a mascara de horas avaliadas (biblioteca: `metrics.evaluated_mask`). FV das
    casas: o perfil sai do proprio periodo de teste, como na v2 (igual para todos; achado 3 da revisao de 11/10)."""
    from prosumer.metrics import evaluated_mask
    d = carrega(caso)
    d = d[(d.ds >= CASOS[caso]["ini"])].copy()
    d["avalia"] = evaluated_mask(d, {"usinas": "sun", "casas_prod": "profile", "casas_cons": "all"}[caso])
    return d[["unique_id", "ds", "y", "avalia"]]


def metricas(df):
    e = df.yhat - df.y
    mu = df.y.mean()
    dia = df.assign(dia=df.ds.dt.normalize()).groupby(["unique_id", "dia"])[["y", "yhat"]].sum()
    return dict(nMAE=e.abs().mean() / mu, nRMSE=np.sqrt((e ** 2).mean()) / mu, MBE=e.mean() / mu,
                nMAE_diario=(dia.yhat - dia.y).abs().mean() / dia.y.mean(), RMSE=np.sqrt((e ** 2).mean()),
                R2=1 - (e ** 2).sum() / ((df.y - mu) ** 2).sum(),
                R2_diario=1 - ((dia.yhat - dia.y) ** 2).sum() / ((dia.y - dia.y.mean()) ** 2).sum())


def alinha_previsoes(p, base, ref):
    """Pareia alvo, modelo e referencia, excluindo horas sem previsao valida."""
    chaves = ["unique_id", "ds"]
    r = ref[chaves + ["yhat"]].rename(columns={"yhat": "yhat_ref"})
    m = p.merge(base, on=chaves, validate="one_to_one").merge(r, on=chaves, validate="one_to_one")
    m = m[np.isfinite(m[["y", "yhat", "yhat_ref"]]).all(axis=1)]
    m = m.sort_values(chaves).reset_index(drop=True)
    if m.empty:
        raise ValueError("Sem horas finitas em comum entre modelo, alvo e referencia")
    rr = m[chaves + ["y", "yhat_ref"]].rename(columns={"yhat_ref": "yhat"})
    return m.drop(columns="yhat_ref"), rr


def skill_ic(df, ref):
    """IC do skill reamostrando dias inteiros; df e ref alinhados."""
    k = df.unique_id.astype(str) + "|" + df.ds.dt.normalize().astype(str)
    se = ((df.yhat - df.y) ** 2).groupby(k.values).agg(["sum", "count"])
    sr = ((ref.yhat.values - df.y.values) ** 2)
    sr = pd.Series(sr, index=df.index).groupby(k.values).sum()
    n = len(se)
    idx = rng.integers(0, n, size=(1000, n))
    a, c, r = se["sum"].to_numpy(), se["count"].to_numpy(), sr.to_numpy()
    s = 1 - np.sqrt(a[idx].sum(1) / c[idx].sum(1)) / np.sqrt(r[idx].sum(1) / c[idx].sum(1))
    return np.percentile(s, [2.5, 97.5])


def diebold_mariano(e1, e2):
    """e1, e2: erros quadraticos indexados por (unique_id, ds). Retorna (dif. media relativa, estatistica, p).
    Diferenca positiva = o primeiro erra mais."""
    j = pd.concat([e1.rename("a"), e2.rename("b")], axis=1, join="inner").dropna()
    d = (j.a - j.b).groupby(j.index.get_level_values("ds").normalize()).mean().sort_index().to_numpy()
    T = len(d)
    if T < 10 or np.allclose(d, 0):
        return 0.0, 0.0, 1.0
    db = d.mean(); x = d - db
    L = int(np.floor(T ** (1 / 3)))
    v = x @ x / T + 2 * sum((1 - l / (L + 1)) * (x[l:] @ x[:-l]) / T for l in range(1, L + 1))
    est = db / np.sqrt(max(v, 1e-30) / T) * np.sqrt((T - 1) / T)          # HLN com h = 1 dia
    return db / j.b.mean(), est, 2 * stats.t.sf(abs(est), T - 1)


def holm(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p)
    adj = np.maximum.accumulate((m - np.arange(m)) * p[o]).clip(max=1)
    out = np.empty(m); out[o] = adj
    return out


def avalia():
    global rng
    rng = np.random.default_rng(42)
    todas = pd.concat([pd.read_parquet(f) for f in sorted(PREV.glob("*.parquet"))], ignore_index=True)
    todas["yhat"] = todas.yhat.clip(lower=0)
    linhas, por_serie, por_dobra, erros = [], [], [], {}
    for caso, g in todas.groupby("caso"):
        r = real(caso)
        base = r[r.avalia]
        ref = g[(g.modelo == REF[caso]) & (g.regime == "A")].merge(base, on=["unique_id", "ds"], validate="one_to_one")
        dob = dobras(caso)
        for (modelo, regime), p in g.groupby(["modelo", "regime"]):
            m, rr = alinha_previsoes(p, base, ref)
            met = metricas(m)
            met["skill"] = 1 - met["RMSE"] / np.sqrt(((rr.yhat - rr.y) ** 2).mean())
            met["skill_ic95_inf"], met["skill_ic95_sup"] = skill_ic(m, rr)
            met.update(caso=caso, modelo=modelo, regime=regime, horas=len(m))
            linhas.append(met)
            erros[(caso, regime, modelo)] = pd.Series(((m.yhat - m.y) ** 2).to_numpy(),
                                                      index=pd.MultiIndex.from_arrays([m.unique_id, m.ds]))
            for uid, s in m.groupby("unique_id"):
                ps = metricas(s); ps.update(caso=caso, modelo=modelo, regime=regime, unique_id=uid)
                rs = rr[rr.unique_id == uid]
                ps["skill"] = 1 - ps["RMSE"] / np.sqrt(((rs.yhat - rs.y) ** 2).mean())
                por_serie.append(ps)
            for k, (ini, fim) in enumerate(dob, start=1):
                sel = ((m.ds >= ini) & (m.ds <= fim)).to_numpy()
                if sel.sum() == 0:
                    continue
                e, er = m.yhat[sel] - m.y[sel], rr.yhat[sel] - rr.y[sel]
                por_dobra.append(dict(caso=caso, modelo=modelo, regime=regime, dobra=k, inicio=ini.date(),
                                      fim=fim.date(), skill=1 - np.sqrt((e ** 2).mean()) / np.sqrt((er ** 2).mean()),
                                      nRMSE=np.sqrt((e ** 2).mean()) / m.y[sel].mean(), MBE=e.mean() / m.y[sel].mean()))
    M = pd.DataFrame(linhas)
    S = pd.DataFrame(por_serie)
    D = pd.DataFrame(por_dobra)

    # Diebold-Mariano: cada modelo contra o melhor do mesmo caso e regime
    # (biblioteca: prosumer.metrics.ranking, desde 11/10/2026; mesmo DM, mesmo Holm, mesmo criterio de empate)
    from prosumer.metrics import ranking
    dm = []
    for (caso, regime), g in M.groupby(["caso", "regime"]):
        R = ranking(dict(zip(g.modelo, g.skill)), {m: erros[(caso, regime, m)] for m in g.modelo})
        for r in R[R.model != R.best].itertuples():
            dm.append(dict(caso=caso, regime=regime, modelo=r.model, melhor=r.best, perda_extra=r.extra_loss, dm=r.dm,
                           p=r.p, p_holm=r.p_holm, empatado_com_melhor=bool(r.ties_with_best)))
    DM = pd.DataFrame(dm)

    # Diebold-Mariano entre regimes (usinas): o mesmo modelo, e o melhor de cada regime
    pares = [("C", "A"), ("C", "B"), ("C-gfs", "C"), ("B-curto", "B"), ("B-curto", "C")]
    dr = []
    U = M[M.caso == "usinas"]
    for r1, r2 in pares:
        comuns = sorted(set(U[U.regime == r1].modelo) & set(U[U.regime == r2].modelo) - REFERENCIAS)
        alvo = [(m, m) for m in comuns]
        b1 = U[U.regime == r1].sort_values("skill").iloc[-1].modelo if (U.regime == r1).any() else None
        b2 = U[U.regime == r2].sort_values("skill").iloc[-1].modelo if (U.regime == r2).any() else None
        if b1 and b2:
            alvo.append((b1, b2))
        alvo = list(dict.fromkeys(alvo))
        for m1, m2 in alvo:
            dif, est, p = diebold_mariano(erros[("usinas", r1, m1)], erros[("usinas", r2, m2)])
            s1 = U[(U.regime == r1) & (U.modelo == m1)].skill.iloc[0]; s2 = U[(U.regime == r2) & (U.modelo == m2)].skill.iloc[0]
            dr.append(dict(comparacao=f"{r1} x {r2}", modelo_1=f"{m1} ({r1})", modelo_2=f"{m2} ({r2})",
                           skill_1=s1, skill_2=s2, perda_extra_do_1=dif, dm=est, p=p))
    DR = pd.DataFrame(dr)
    if len(DR):
        DR["p_holm"] = holm(DR.p)

    kw = dict(index=False, sep=";", decimal=",", encoding="utf-8-sig")
    M.to_csv(RES / "metricas.csv", **kw)
    S.to_csv(RES / "metricas_por_serie.csv", **kw)
    D.to_csv(RES / "metricas_por_dobra.csv", **kw)
    DM.to_csv(RES / "dm_vs_melhor.csv", **kw)
    DR.to_csv(RES / "dm_regimes.csv", **kw)
    return M, S, D, DM, DR


if __name__ == "__main__":
    M, S, D, DM, DR = avalia()
    pd.set_option("display.width", 220)
    emp = DM.set_index(["caso", "regime", "modelo"]).empatado_com_melhor if len(DM) else pd.Series(dtype=bool)
    for (caso, regime), g in M.groupby(["caso", "regime"]):
        print("\n=== %s | regime %s (skill contra %s) ===" % (caso, regime, REF[caso]))
        g = g.sort_values("skill", ascending=False).copy()
        g["empate"] = [("melhor" if i == 0 else ("sim" if emp.get((caso, regime, m), False) else "nao"))
                       for i, m in enumerate(g.modelo)]
        dd = D[(D.caso == caso) & (D.regime == regime)].pivot_table(index="modelo", columns="dobra", values="skill")
        g["skill_min_dobra"] = g.modelo.map(dd.min(axis=1)); g["skill_max_dobra"] = g.modelo.map(dd.max(axis=1))
        print(g[["modelo", "nRMSE", "MBE", "R2", "skill", "skill_ic95_inf", "skill_ic95_sup", "skill_min_dobra",
                 "skill_max_dobra", "empate"]].round(3).to_string(index=False))
    if len(DR):
        print("\n=== Diebold-Mariano entre regimes (usinas) ===")
        print(DR.round(4).to_string(index=False))
