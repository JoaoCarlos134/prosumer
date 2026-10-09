# -*- coding: utf-8 -*-
"""Figuras dos resultados (PNG em resultados/figuras/).

Cores por familia (paleta categorica de referencia, 3 primeiros slots + cinza neutro para as
referencias). Regime pela forma e pelo preenchimento do marcador, nunca so por cor:
A = circulo vazado, C = quadrado cheio, B = circulo cheio. Nas figuras em que a cor e o proprio
regime (regimes e dobras), A = cinza, C = azul, B = tinta, sempre com rotulo.
Os regimes de diagnostico (B-curto, C-gfs) ficam fora das figuras; estao nas tabelas.
"""
import json
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from comum import RES, PREV, carrega, dobras, CASOS, DIAGNOSTICOS

FIG = RES / "figuras"; FIG.mkdir(exist_ok=True)
INK, INK2, GRADE, FUNDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COR = {"Referencia": "#8a8984", "Arvore / fisica": "#2a78d6", "Rede treinada": "#eb6834", "Fundacional": "#1baf7a",
       "Classico": "#8e5bb5"}
COR_REGIME = {"A": "#8a8984", "C": "#2a78d6", "B": INK}
NOME_REGIME = {"A": "A: só histórico", "C": "C: + previsão do tempo real", "B": "B: + clima do dia (teto)"}
MARCA = {"A": ("o", False), "C": ("s", True), "B": ("o", True)}
FAMILIA = {**{m: "Referencia" for m in ["persist_24h", "semanal_168h", "media_7d", "persist_ceu_claro"]},
           **{m: "Arvore / fisica" for m in ["LightGBM", "linear_fisico"]},
           **{m: "Fundacional" for m in ["Chronos-2", "Chronos-Bolt-small", "TimesFM-2.5", "TiRex", "TTM-r2", "Toto",
                                         "Moirai-2.0-small",
                                         # lote 2: tambem zero-shot, nao sao redes treinadas nestes dados
                                         "Toto-2.0-22m", "Toto-2.0-313m", "TiRex-2", "TabPFN-TS", "Sundial-128m",
                                         "Timer-XL-84m", "Time-MoE-50M", "Moirai-MoE-small",
                                         "FlowState"]},  # entrou em 09/10/2026
           # classicos (passo T): antes caiam no padrao "Rede treinada" e saiam com a cor errada
           **{m: "Classico" for m in ["Ridge", "RandomForest", "MLP", "kNN",
                                      "AutoARIMA", "AutoETS", "AutoTheta", "MSTL"]}}
TITULO = {"usinas": "Usinas (Cascavel + Curitiba) — ganho sobre a persistência de céu claro",
          "casas_prod": "Geração FV das 10 casas com FV — ganho sobre 'igual a ontem'",
          "casas_cons": "Consumo das 20 casas — ganho sobre 'igual a ontem'"}
NOME_CASO = {"usinas": "Usinas", "casas_prod": "FV das casas", "casas_cons": "Consumo das casas"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRADE, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": FUNDO, "axes.facecolor": FUNDO})


def familia(m):
    return FAMILIA.get(m, "Rede treinada")


def marca(ax, x, y, cor, regime, ms=8):
    mk, cheio = MARCA[regime]
    ax.plot(x, y, mk, ms=ms, mfc=cor if cheio else FUNDO, mec=cor, mew=2)


def limpa(ax, eixo="x"):
    ax.grid(axis=eixo, color=GRADE, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right") + (("left",) if eixo == "x" else ()):
        ax.spines[s].set_visible(False)


def legenda_regimes(regimes, cor=INK2):
    out = []
    for r in regimes:
        mk, cheio = MARCA[r]
        out.append(plt.Line2D([], [], marker=mk, ls="", ms=7, mfc=cor if cheio else FUNDO, mec=cor, mew=2, label=NOME_REGIME[r]))
    return out


def ranking(M):
    for caso, g in M.groupby("caso"):
        g = g.sort_values("skill").reset_index(drop=True)
        fig, ax = plt.subplots(figsize=(8, 0.26 * len(g) + 2.0))
        for i, r in g.iterrows():
            ens = r.modelo.startswith("Ensemble-mediana")
            c = INK if ens else COR[familia(r.modelo)]
            ax.plot([r.skill_ic95_inf, r.skill_ic95_sup], [i, i], color=c, lw=2, solid_capstyle="round", alpha=0.55)
            if ens:
                ax.plot(r.skill, i, "D", ms=8, mfc=c if r.regime != "A" else FUNDO, mec=c, mew=2)
            else:
                marca(ax, r.skill, i, c, r.regime)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_yticks(range(len(g)))
        ax.set_yticklabels([f"{m}  ({rg})" for m, rg in zip(g.modelo, g.regime)], color=INK)
        ax.set_xlabel("skill = 1 − RMSE / RMSE da referência   (barra: IC 95%, bootstrap por dia; origem móvel)")
        limpa(ax)
        ax.set_title(TITULO[caso], loc="left", color=INK, fontsize=10.5, fontweight="bold")
        h = [plt.Line2D([], [], marker="o", ls="", ms=7, mfc=COR[f], mec=COR[f], label=f) for f in COR]
        h += [plt.Line2D([], [], marker="D", ls="", ms=7, mfc=INK, mec=INK, label="Ensemble (mediana de todos)")]
        h += legenda_regimes(sorted(set(g.regime), key="ACB".index))
        ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.45, -0.07), ncol=4, frameon=False, fontsize=8)
        fig.tight_layout(); fig.savefig(FIG / f"ranking_{caso}.png", dpi=150); plt.close(fig)


def regimes(M):
    """Usinas: o mesmo modelo em A, C e B. Mostra quanto da distancia entre A e B a previsao real fecha."""
    # Os fundacionais que tem B e C entram: sem isso o TiRex-2 e o TabPFN-TS (lote 2) sairiam da figura
    # so por estarem em FAMILIA, e a mediana subiria por tirar justamente os dois que fecham menos vao.
    COM_REGIME = {"LightGBM", "linear_fisico", "Chronos-2", "TimesFM-2.5", "TiRex-2", "TabPFN-TS"}
    U = M[(M.caso == "usinas") & ~M.modelo.isin(FAMILIA.keys() - COM_REGIME)]
    P = U.pivot_table(index="modelo", columns="regime", values="skill")
    P = P[P.get("C").notna()].sort_values("C")
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(P) + 1.8))
    for i, (m, r) in enumerate(P.iterrows()):
        xs = [r[k] for k in "ACB" if k in r and pd.notna(r[k])]
        ax.plot([min(xs), max(xs)], [i, i], color=GRADE, lw=3, solid_capstyle="round", zorder=1)
        for k in "ACB":
            if k in r and pd.notna(r[k]):
                marca(ax, r[k], i, COR_REGIME[k], k, ms=9)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(P))); ax.set_yticklabels(P.index, color=INK)
    ax.set_xlabel("skill sobre a persistência de céu claro")
    limpa(ax)
    a, c, b = P.get("A"), P["C"], P.get("B")
    fecha = ((c - a) / (b - a)).dropna()
    ax.set_title("Usinas: a previsão do tempo real fecha %d%% da distância entre\n"
                 "só histórico e clima perfeito (mediana dos modelos)" % round(100 * fecha.median()), loc="left",
                 color=INK, fontsize=10.5, fontweight="bold")
    h = [plt.Line2D([], [], marker=MARCA[k][0], ls="", ms=8, mfc=COR_REGIME[k] if MARCA[k][1] else FUNDO,
                    mec=COR_REGIME[k], mew=2, label=NOME_REGIME[k]) for k in "ACB"]
    fig.legend(handles=h, loc="lower center", ncol=3, frameon=False, fontsize=8)
    fig.tight_layout(rect=[0, 0.07, 1, 1]); fig.savefig(FIG / "regimes_usinas.png", dpi=150); plt.close(fig)


def por_dobra(D, M):
    """Skill da mediana de todos em cada dobra (e dos dois melhores modelos nas casas)."""
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
    for ax, caso in zip(axs, ["usinas", "casas_prod", "casas_cons"]):
        g = D[D.caso == caso]
        MES = "jan fev mar abr mai jun jul ago set out nov dez".split()
        rot = [f"{k}\n{MES[i.month - 1]}–{MES[f.month - 1]}" if i.month != f.month else f"{k}\n{MES[i.month - 1]}"
               for k, (i, f) in enumerate(dobras(caso), start=1)]
        if caso == "usinas":
            series = [("Ensemble-mediana", k, COR_REGIME[k], NOME_REGIME[k].split(":")[0] + ": mediana") for k in "ACB"]
        else:
            top = M[(M.caso == caso) & (M.modelo != "Ensemble-mediana")].sort_values("skill").tail(2).modelo
            series = [("Ensemble-mediana", "A", INK, "mediana de todos")] + \
                     [(m, "A", c, m) for m, c in zip(top[::-1], ["#2a78d6", "#1baf7a"])]
        for m, rg, c, rotulo in series:
            s = g[(g.modelo == m) & (g.regime == rg)].sort_values("dobra")
            ax.plot(s.dobra, s.skill, "-", color=c, lw=2)
            mk, cheio = MARCA[rg] if caso == "usinas" else ("o", True)
            ax.plot(s.dobra, s.skill, mk, ms=8, mfc=c if cheio else FUNDO, mec=c, mew=2, label=rotulo)
        ax.axhline(0, color=INK2, lw=1)
        ax.set_xticks(range(1, len(rot) + 1)); ax.set_xticklabels(rot, fontsize=7.5)
        ax.set_title(NOME_CASO[caso], loc="left", fontsize=10, color=INK)
        limpa(ax, "y"); ax.legend(frameon=False, fontsize=7.5)
    axs[0].set_ylabel("skill na dobra")
    fig.suptitle("Origem móvel: o skill em cada dobra (modelo retreinado no início de cada uma)", x=0.01, ha="left",
                 fontsize=10.5, fontweight="bold", color=INK)
    fig.tight_layout(); fig.savefig(FIG / "skill_por_dobra.png", dpi=150); plt.close(fig)


def dias_exemplo(M):
    """Tres dias de Cascavel: limpo, misto e nublado; real contra a referencia e o melhor de cada regime."""
    todas = pd.concat([pd.read_parquet(f) for f in PREV.glob("*__usinas__*.parquet")])
    r = carrega("usinas"); r = r[(r.unique_id == "Cascavel") & (r.ds >= CASOS["usinas"]["ini"])]
    tot = r.groupby(r.ds.dt.normalize()).y.sum()
    tot = tot[tot > 0]
    dias = [tot.idxmax(), tot.sort_values().index[len(tot) // 2], tot.sort_values().index[int(len(tot) * 0.1)]]
    g = M[M.caso == "usinas"]
    escolha = [("persist_ceu_claro", "A", "#8a8984")] + \
              [(g[g.regime == k].sort_values("skill").iloc[-1].modelo, k, c) for k, c in [("A", "#1baf7a"), ("C", "#2a78d6"), ("B", "#eb6834")]]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.2), sharey=True)
    for ax, dia, nome in zip(axs, dias, ["dia limpo", "dia típico", "dia nublado"]):
        rr = r[r.ds.dt.normalize() == dia]
        ax.plot(rr.ds.dt.hour, rr.y, color=INK, lw=2.4, label="real")
        for m, rg, c in escolha:
            p = todas[(todas.modelo == m) & (todas.regime == rg) & (todas.unique_id == "Cascavel") & (todas.ds.dt.normalize() == dia)]
            ax.plot(p.ds.dt.hour, p.yhat.clip(lower=0), color=c, lw=2, label=f"{m} ({rg})")
        ax.set_title(f"Cascavel, {dia:%d/%m/%Y} — {nome}", loc="left", fontsize=9.5, color=INK)
        ax.set_xlim(5, 20); ax.grid(color=GRADE, lw=0.8); ax.set_xlabel("hora")
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    axs[0].set_ylabel("kWh na hora"); axs[-1].legend(frameon=False, fontsize=7.5, loc="upper right")
    fig.tight_layout(); fig.savefig(FIG / "dias_exemplo_cascavel.png", dpi=150); plt.close(fig)


def custo(M):
    t = {}
    for p in sorted(RES.glob("tempos_*.json")):
        t.update(json.loads(p.read_text()))
    M = M.copy()
    M["segundos"] = [t.get(f"{m}|{c}|{rg}", {}).get("segundos", np.nan) for m, c, rg in zip(M.modelo, M.caso, M.regime)]
    M = M.dropna(subset=["segundos"])
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.6), sharey=False)
    for ax, (caso, g) in zip(axs, M.groupby("caso")):
        for _, r in g.iterrows():
            marca(ax, r.segundos, r.skill, COR[familia(r.modelo)], r.regime)
        top = g.sort_values("skill").tail(3)
        for _, r in top.iterrows():
            ax.annotate(f"{r.modelo} ({r.regime})", (r.segundos, r.skill), xytext=(4, 4), textcoords="offset points",
                        fontsize=7.5, color=INK2)
        ax.set_xscale("log"); ax.axhline(0, color=INK2, lw=1); ax.grid(color=GRADE, lw=0.8)
        ax.set_title(NOME_CASO[caso], loc="left", fontsize=10, color=INK)
        ax.set_xlabel("tempo total, todas as dobras (s, CPU)")
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    axs[0].set_ylabel("skill")
    h = [plt.Line2D([], [], marker="o", ls="", ms=7, mfc=COR[f], mec=COR[f], label=f) for f in ("Rede treinada", "Fundacional")]
    h += legenda_regimes("ACB")
    fig.legend(handles=h, loc="upper center", ncol=5, frameon=False, fontsize=8, bbox_to_anchor=(0.5, 1.02))
    fig.text(0.01, -0.02, "Referências, LightGBM e linear físico não aparecem: rodam em segundos e não tiveram o tempo medido. "
             "Redes: treino em cada dobra (5 nas usinas, 3 nas casas); fundacionais: sem treino.", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=[0, 0, 1, 0.94]); fig.savefig(FIG / "custo_x_skill.png", dpi=150, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    kw = dict(sep=";", decimal=",")
    M = pd.read_csv(RES / "metricas.csv", **kw)
    D = pd.read_csv(RES / "metricas_por_dobra.csv", **kw)
    M, D = M[~M.regime.isin(DIAGNOSTICOS)], D[~D.regime.isin(DIAGNOSTICOS)]
    ranking(M); regimes(M); por_dobra(D, M); dias_exemplo(M); custo(M)
    print("figuras em", FIG)
