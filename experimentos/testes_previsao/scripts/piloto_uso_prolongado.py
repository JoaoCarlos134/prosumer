"""Piloto V11 (18/11/2026): o aplicativo aprende com o proprio erro? Replay causal nas duas usinas.

Portao em docs/projeto/PILOTOS_F1_F2.md, secao "V11-piloto" (commit 31f5493, ANTES deste script). Resumo:
toda noite o `outlook.forecast_ahead` da biblioteca emite os leads 1-7 com o tempo que existia (Previous Runs,
`previous_day{k}`), so com os dados ate aquela noite; guardamos a previsao (o "banco"); depois comparamos o app
CONGELADO (padroes do Parana) com variantes que ajustam a_k, vies b_k e a faixa do total do dia com os pares
(previsao, real) ja observados, encolhidos para o padrao com n0.

Uso (ambiente da biblioteca, raiz do repo):
  python experimentos/testes_previsao/scripts/piloto_uso_prolongado.py replay Cascavel   # ~35 min, retoma
  python experimentos/testes_previsao/scripts/piloto_uso_prolongado.py replay Curitiba
  python experimentos/testes_previsao/scripts/piloto_uso_prolongado.py avalia            # segundos

Saidas: resultados/pilotos/uso_prolongado__usinas__<serie>.parquet (por hora, dado de usina: fora do git) e
resultados/pilotos/uso_prolongado.json (so metricas agregadas).
"""

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from comum import DADOS, SITIOS  # noqa: E402
from piloto_comum import PILOTOS  # noqa: E402

from prosumer import outlook  # noqa: E402
from prosumer.contracts import EnergySeries  # noqa: E402
from prosumer.diagnostics import roof_orientation  # noqa: E402

FUSO = "Etc/GMT+3"
PRIMEIRO_ALVO, ULTIMO_ALVO = pd.Timestamp("2024-03-07"), pd.Timestamp("2026-05-31")
LEADS = 7
TRUST = np.array(outlook.TRUST)
INICIOS = pd.date_range("2024-09-01", "2025-11-01", freq="2MS")      # 8 inicios
USO_MAX = 365
FAIXAS = [(1, 30), (31, 90), (91, 180), (181, 365)]
N0S = [7, 15, 30, 60, 120, 240]
JAN_A, JAN_B, JAN_C, MIN_C = 365, 90, 60, 30                        # janelas do portao (dias)
B_LIM = (0.7, 1.3)
HISTORICO_LB = 365
SERIES = list(SITIOS)
warnings.filterwarnings("ignore", category=RuntimeWarning)


def arq(serie):
    return PILOTOS / f"uso_prolongado__usinas__{serie}.parquet"


# ------------------------------------------------------------------ replay
def _serie(serie):
    u = pd.read_parquet(DADOS / "usinas_horario.parquet")
    u = u[u.serie == serie].sort_values("ds")
    x = pd.DataFrame({"unique_id": serie, "ds": pd.to_datetime(u.ds).dt.tz_localize(FUSO),
                      "y": (u.y_Wh / 1000.0).where(u.y_valido).to_numpy()})
    x["valid"] = x.y.notna()
    return x.reset_index(drop=True)


def _ate(x, dia):
    """EnergySeries com tudo ANTES de `dia` 00:00 (local)."""
    return EnergySeries(frame=x[x.ds < dia.tz_localize(FUSO)].reset_index(drop=True), unit="kWh",
                        quantity="generation", tz=FUSO, freq="h")


def _tempo(H, primeiro):
    """Tempo que existia na noite antes de `primeiro`: o dia primeiro+k-1 com o lead k. Largo, ghi_<modelo>."""
    partes = [H[(H.lead == k) & (H.dia == primeiro + pd.Timedelta(days=k - 1))] for k in range(1, LEADS + 1)]
    g = pd.concat(partes)
    if g.empty:
        return None
    w = g.pivot_table(index="ds", columns="modelo_nwp", values="ghi", dropna=False)
    w.columns = ["ghi_" + c for c in w.columns]
    w = w.reset_index()
    w["ds"] = pd.to_datetime(w.ds).dt.tz_localize(FUSO)
    return w


def replay(serie):
    site = SITIOS[serie]
    x = _serie(serie)
    H = pd.read_parquet(DADOS / "previsao_tempo_horizonte.parquet")
    H = H[H.serie == serie].copy()
    H["dia"] = pd.to_datetime(H.ds).dt.normalize()
    feitos, antigos = set(), []
    if arq(serie).exists():
        antigos = [pd.read_parquet(arq(serie))]
        feitos = set(pd.to_datetime(antigos[0].emissao).unique())
    telhado, novos, t0 = {}, [], time.time()
    # noite de emissao e (o dia `emissao`, dados ate 23:00); lead 1 = emissao + 1
    emissoes = pd.date_range(PRIMEIRO_ALVO - pd.Timedelta(days=1), ULTIMO_ALVO - pd.Timedelta(days=1), freq="D")
    for i, e in enumerate(emissoes):
        if e in feitos:
            continue
        primeiro = e + pd.Timedelta(days=1)
        mes = primeiro.replace(day=1)
        s = _ate(x, primeiro)
        if mes not in telhado:                     # telhado com os dados antes do 1o dia do mes (causal)
            o = roof_orientation(_ate(x, mes), site).iloc[0]
            telhado[mes] = (float(o.tilt), float(o.azimuth))
        tilt, az = telhado[mes]
        w = _tempo(H, primeiro)
        saida = {}
        for nome, tr in (("F", tuple(TRUST)), ("w", (1.0,) * LEADS), ("s", (0.0,) * LEADS)):
            o = outlook.forecast_ahead(s, site=site, weather=w, start=primeiro, tilt=tilt, azimuth=az, trust=tr)
            saida[nome] = o
        h = saida["F"].hourly
        d = saida["F"].daily.set_index("date")
        dia = h.ds.dt.tz_localize(None).dt.normalize()
        novos.append(pd.DataFrame({
            "emissao": e, "ds": h.ds.dt.tz_localize(None), "lead": h.lead_day.to_numpy(),
            "yF": h.y_hat.to_numpy(), "yw": saida["w"].hourly.y_hat.to_numpy(),
            "ys": saida["s"].hourly.y_hat.to_numpy(), "sol": h.sun.to_numpy(),
            "lowF_dia": d.low.reindex(dia).to_numpy(), "highF_dia": d.high.reindex(dia).to_numpy(),
            "tilt": tilt, "az": az}))
        if len(novos) % 50 == 0:
            _grava(serie, antigos + novos)
            print(f"{serie} {e.date()} ({i + 1}/{len(emissoes)}) {time.time() - t0:.0f} s", flush=True)
    _grava(serie, antigos + novos)
    print(f"{serie}: {len(emissoes)} noites, {time.time() - t0:.0f} s")


def _grava(serie, partes):
    pd.concat(partes, ignore_index=True).to_parquet(arq(serie), index=False)


# ------------------------------------------------------------------ avaliacao
def _pares(serie):
    """Tabela por (emissao, lead): totais do dia Y, F, w, s, faixa F, e as somas das horas de sol para o a_k."""
    r = pd.read_parquet(arq(serie))
    x = _serie(serie)
    y = x.set_index(x.ds.dt.tz_localize(None)).y
    r["y"] = y.reindex(r.ds).to_numpy()
    r["alvo"] = r.ds.dt.normalize()
    r = r[(r.lead >= 1) & (r.lead <= LEADS) & (r.alvo <= ULTIMO_ALVO)]
    # dia sem algum valor medido nas horas de sol nao entra (nem na avaliacao, nem no aprendizado)
    ok = r.groupby(["emissao", "lead"]).apply(lambda g: g.y[g.sol].notna().all() and g.y.notna().any(),
                                               include_groups=False).rename("ok")
    sol = r[r.sol & r.y.notna()].assign(dw=lambda d: d.yw - d.ys, dy=lambda d: d.y - d.ys)
    sxy = (sol.dw * sol.dy).groupby([sol.emissao, sol.lead]).sum().rename("sxy")
    sxx = (sol.dw ** 2).groupby([sol.emissao, sol.lead]).sum().rename("sxx")
    g = r.groupby(["emissao", "lead"])
    t = pd.concat([g.alvo.first(), g.y.sum(min_count=1).rename("Y"), g.yF.sum().rename("F"),
                   g.yw.sum().rename("W"), g.ys.sum().rename("S"), g.lowF_dia.first().rename("lo"),
                   g.highF_dia.first().rename("hi"), sxy, sxx, ok], axis=1).reset_index()
    return t[t.ok].drop(columns="ok").sort_values(["emissao", "lead"]).reset_index(drop=True)


def _variante(t, inicio, n0, historico, com_b=True):
    """Previsao do total do dia e faixa de 80% da variante aprendendo, emissao a emissao (o que o banco veria).
    So pares com alvo <= dia da emissao. L: pares emitidos a partir da noite antes do inicio; LB: tambem os dos
    365 dias antes (o app reconstroi o historico ao instalar; nesses o `Yhat` guardado e o do app de hoje, F).
    a_k e b_k so dependem de S, W, Y e das somas das horas de sol (nao da previsao da variante): somas acumuladas
    por dia-alvo. A faixa usa a previsao como emitida nos 60 dias anteriores."""
    e0 = inicio - pd.Timedelta(days=1)                      # noite da instalacao
    desde = e0 - (pd.Timedelta(days=HISTORICO_LB) if historico else pd.Timedelta(0))
    fim = inicio + pd.Timedelta(days=USO_MAX - 1)
    dias = pd.date_range(PRIMEIRO_ALVO - pd.Timedelta(days=1), ULTIMO_ALVO, freq="D")
    out = []
    for k in range(1, LEADS + 1):
        q = t[(t.lead == k) & (t.emissao >= desde) & (t.alvo <= fim)].set_index("alvo").reindex(dias)
        tem = q.Y.notna().to_numpy()
        z = lambda c: np.where(tem, np.nan_to_num(q[c].to_numpy(float)), 0.0)  # noqa: E731
        C = {c: np.concatenate([[0.0], np.cumsum(z(c))]) for c in ("sxy", "sxx", "Y", "S", "W")}
        C["n"] = np.concatenate([[0.0], np.cumsum(tem.astype(float))])
        ix = np.arange(len(dias))
        e_ix = ix - k                                       # a linha do alvo i foi emitida no dia i-k
        def soma(c, jan):                                   # pares com alvo em (e-jan, e], e = dia da emissao
            hi = np.clip(e_ix + 1, 0, len(dias))
            lo = np.clip(e_ix + 1 - jan, 0, len(dias))
            return C[c][hi] - C[c][lo]
        n = soma("n", JAN_A)
        sxx = soma("sxx", JAN_A)
        a_sit = np.where(sxx > 0, soma("sxy", JAN_A) / np.where(sxx > 0, sxx, 1), TRUST[k - 1])
        a = np.clip((n * a_sit + n0 * TRUST[k - 1]) / (n + n0), 0, 1)
        S, W = q.S.to_numpy(float), q.W.to_numpy(float)
        y_a = S + a * (W - S)
        b = np.ones(len(dias))
        if com_b:
            nb = soma("n", JAN_B)
            den = soma("S", JAN_B) + a * (soma("W", JAN_B) - soma("S", JAN_B))
            b_sit = np.where(den > 0, soma("Y", JAN_B) / np.where(den > 0, den, 1), 1.0)
            b = np.clip((nb * b_sit + n0) / (nb + n0), *B_LIM)
        yhat = b * y_a
        F, lo, hi, Y = (q[c].to_numpy(float) for c in ("F", "lo", "hi", "Y"))
        emitido = np.where((dias - pd.Timedelta(days=k)) < e0, F, yhat)   # o que o banco guardou
        larg = hi - lo
        r = np.where(tem & (larg > 0), (Y - emitido) / np.where(larg > 0, larg, 1), np.nan)
        lo_v, hi_v = yhat - (F - lo), yhat + (hi - F)
        for i in np.flatnonzero(tem):
            j = e_ix[i]
            if j < 0:
                continue
            rr = r[max(j + 1 - JAN_C, 0): j + 1]
            rr = rr[np.isfinite(rr)]
            if len(rr) >= MIN_C and larg[i] > 0:
                lo_v[i], hi_v[i] = yhat[i] + np.quantile(rr, 0.1) * larg[i], yhat[i] + np.quantile(rr, 0.9) * larg[i]
        v = pd.DataFrame({"alvo": dias, "lead": k, "Y": Y, "F": F, "S": S, "lo": lo, "hi": hi, "Yhat": yhat,
                          "lo_v": np.maximum(lo_v, 0), "hi_v": np.maximum(hi_v, 0), "a": a, "b": b})
        out.append(v[tem & ((dias - pd.Timedelta(days=k)) >= e0)])
    v = pd.concat(out, ignore_index=True)
    v["uso"] = (v.alvo - inicio).dt.days + 1
    return v[(v.uso >= 1) & (v.uso <= USO_MAX)]


def _dm(d, lag=7):
    """Diebold-Mariano (HAC Bartlett, lag fixo do portao), p bilateral normal. d = perda1 - perda2 por dia."""
    from scipy import stats
    d = np.asarray(d, float)
    T = len(d)
    if T < 10 or np.allclose(d, 0):
        return 1.0
    x = d - d.mean()
    v = x @ x / T + 2 * sum((1 - j / (lag + 1)) * (x[j:] @ x[:-j]) / T for j in range(1, lag + 1))
    return float(2 * stats.norm.sf(abs(d.mean() / np.sqrt(max(v, 1e-30) / T))))


def _metricas(v):
    """Por (lead, faixa): skill F e variante vs s, ganho, DM (dias de calendario), cobertura de 80%."""
    res = {}
    for k in range(1, LEADS + 1):
        for a, b in FAIXAS:
            q = v[(v.lead == k) & (v.uso >= a) & (v.uso <= b)]
            if len(q) < 10:
                continue
            rm = lambda c: float(np.sqrt(((q.Y - q[c]) ** 2).mean()))  # noqa: E731
            ref = rm("S")
            dia = q.assign(dl=(q.Y - q.Yhat) ** 2 - (q.Y - q.F) ** 2).groupby("alvo").dl.mean().sort_index()
            res[f"lead{k}_{a}-{b}"] = dict(
                n=len(q), skill_F=1 - rm("F") / ref, skill_v=1 - rm("Yhat") / ref,
                ganho=rm("F") / ref - rm("Yhat") / ref, p_dm=_dm(dia.to_numpy()),
                cob_F=float(((q.Y >= q.lo) & (q.Y <= q.hi)).mean()),
                cob_v=float(((q.Y >= q.lo_v) & (q.Y <= q.hi_v)).mean()),
                a_med=float(q.a.mean()), b_med=float(q.b.mean()))
    return res


def _wape(v, lead=1):
    """Relato (pedido de 18/11, fora do portao): erro percentual da energia, soma|real - previsto| / soma real,
    no total do dia, da semana e do mes (somas por inicio, depois juntas), F e variante, por faixa de uso."""
    q = v[v.lead == lead].copy()
    q["semana"] = q.alvo.dt.to_period("W")
    q["mes"] = q.alvo.dt.to_period("M")
    q["ini"] = q.alvo - pd.to_timedelta(q.uso - 1, unit="D")
    res = {}
    for a, b in FAIXAS:
        f = q[(q.uso >= a) & (q.uso <= b)]
        for nivel in ("alvo", "semana", "mes"):
            g = f.groupby(["ini", nivel])[["Y", "F", "Yhat"]].sum(min_count=1)
            if nivel != "alvo":   # so periodos completos
                cont = f.groupby(["ini", nivel]).size()
                g = g[cont >= (6 if nivel == "semana" else 26)]
            if len(g):
                res[f"{nivel}_{a}-{b}"] = dict(
                    F=float((g.Y - g.F).abs().sum() / g.Y.sum()), v=float((g.Y - g.Yhat).abs().sum() / g.Y.sum()),
                    dias_ate_10pct_F=float(((g.Y - g.F).abs() / g.Y <= 0.10).mean()),
                    dias_ate_10pct_v=float(((g.Y - g.Yhat).abs() / g.Y <= 0.10).mean()))
    return res


def _roda(t, n0, historico, com_b=True):
    return pd.concat([_variante(t, s, n0, historico, com_b) for s in INICIOS], ignore_index=True)


def avalia():
    tabs = {s: _pares(s) for s in SERIES}
    rel = {"portao": "docs/projeto/PILOTOS_F1_F2.md, V11-piloto (31f5493)", "n0": {}, "variantes": {}}
    # n0 deixando a usina de fora: escolhido no ganho medio (leads 1-7, faixas, inicios) da OUTRA usina
    ganho_n0 = {}
    for nome, hist in (("L", False), ("LB", True)):
        for s in SERIES:
            for n0 in N0S:
                m = _metricas(_roda(tabs[s], n0, hist))
                ganho_n0[(nome, s, n0)] = float(np.mean([r["ganho"] for r in m.values()]))
                print(nome, s, n0, round(ganho_n0[(nome, s, n0)], 4), flush=True)
    rel["n0"]["ganho_medio"] = {f"{a}|{b}|{c}": g for (a, b, c), g in ganho_n0.items()}
    portao = {}
    for nome, hist in (("L", False), ("LB", True)):
        portao[nome] = {}
        for s in SERIES:
            outra = [o for o in SERIES if o != s][0]
            n0 = max(N0S, key=lambda n: ganho_n0[(nome, outra, n)])
            m = _metricas(_roda(tabs[s], n0, hist))
            vv = _roda(tabs[s], n0, hist)
            m_a = _metricas(_roda(tabs[s], n0, hist, com_b=False))
            rel["variantes"][f"{nome}|{s}"] = dict(n0=n0, a_mais_b=m, so_a=m_a,
                                                    erro_pct_lead1=_wape(vv, 1), erro_pct_lead7=_wape(vv, 7))
            vv.to_parquet(PILOTOS / f"uso_prolongado_{nome}__usinas__{s}.parquet", index=False)  # para a demo
            g1 = m["lead1_91-180"]["ganho"] >= 0.02 and m["lead1_91-180"]["p_dm"] < 0.05
            g2 = all(m[f"lead{k}_1-30"]["ganho"] >= -0.01 for k in range(1, LEADS + 1) if f"lead{k}_1-30" in m)
            g3 = all(0.75 <= m[f"lead{k}_{a}-{b}"]["cob_v"] <= 0.85 for k in range(1, LEADS + 1)
                     for a, b in FAIXAS[1:] if f"lead{k}_{a}-{b}" in m)
            portao[nome][s] = dict(n0=n0, G1=bool(g1), G2=bool(g2), G3=bool(g3))
        portao[nome]["PASSA"] = all(all(portao[nome][s][g] for g in ("G1", "G2", "G3")) for s in SERIES)
    rel["portao_resultado"] = portao
    (PILOTOS / "uso_prolongado.json").write_text(json.dumps(rel, indent=1, default=float), encoding="utf-8")
    print(json.dumps(portao, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "replay":
        replay(sys.argv[2])
    elif sys.argv[1] == "avalia":
        avalia()
