"""Piloto do HORIZONTE LONGO (12/10/2026): previsao para a proxima semana (e alem), por hora e por total do dia.

Pergunta: uma casa quer marcar cargas pesadas na semana. A previsao do tempo perde qualidade depois de ~1 semana.
Ate que antecedencia k (dias) a previsao do tempo ainda ajuda a geracao FV, contra a climatologia? Qual metodo a
biblioteca usa como padrao, e quanto ela confia no tempo em cada antecedencia (fator de encolhimento a_k)? No
consumo (sem clima), qual metodo de historico serve de 1 a 14 dias?

Antecedencia k: a previsao do dia D emitida as 00:00 do dia D-k+1, so com o que se observou ate 23:00 de D-k
(k = 1 e o benchmark). Tempo na antecedencia k = `previous_day{k}` da Open-Meteo Previous Runs (a mesma convencao
do regime C para k = 1: o valor que o modelo previa k dias antes para aquela hora).

GERACAO (as duas usinas, teste do benchmark 01/08/2025 -> 31/05/2026; historico antes):
  Tempo: Previous Runs, previous_day1..7, GHI, os seis `prosumer.io.open_meteo.DEFAULT_MODELS`, nos pontos do
  benchmark (`comum.SITIOS`), baixado com `fetch_previous_runs(lead_days=k)`; cache em
  dados/previsao_tempo_horizonte.parquet (formato longo com `lead`). O lead 1 tem de reproduzir os arquivos do
  benchmark (previsao_tempo.parquet + previsao_tempo_extra.parquet): diferenca maxima relatada.
  Alem de 7 dias: Single Runs API (`single-runs-api.open-meteo.com`, `run=`), uma rodada das 12 UTC por dia, IFS e
  GFS. Sondado ANTES de escrever este portao (12/10/2026, so disponibilidade, nenhum numero de previsao): o
  arquivo de rodadas comeca em ~02-03/04/2026 (01/04 12 UTC indisponivel, 03/04 disponivel), IFS ate 360 h, GFS
  ate 384 h. Entao os leads 8-15 so podem ser vistos em ~2 meses do fim do teste (abr-mai/2026), SEM periodo
  anterior ao teste para ajustar o `ajustado` nem o a_k. Para a rodada das 12 UTC do dia D-k (09:00 local, ja
  publicada antes das 00:00 de D-k+1), o dia D e o lead k; um modelo so entra num dia se cobre as 24 horas.

  Filtro de qualidade do tempo (aviso da sessao principal em 12/10, ANTES de rodar: o meteofrance_seamless da
  Forecast API deu 2.750 W/m2 ao meio-dia no 4o dia em Cascavel): para cada (modelo, dia, lead), se alguma hora
  tem GHI > 1,2 x GHI de ceu claro (`physics.clear_sky_ghi`) + 50 W/m2, o modelo sai da media naquele dia. E um
  filtro de dado fisicamente impossivel, nao um ajuste; os modelo-dias descartados por modelo e lead sao relatados.
  Orientacao do telhado: `diagnostics.roof_orientation` sobre a serie ANTES do teste (fixa). POA de ceu claro e
  POA prevista: `physics.poa_isotropic` com essa orientacao (POA prevista a partir da media do GHI dos modelos
  disponiveis naquela hora). Dias claros CAUSAIS: razao do dia (`clear_days`.ratio, energia / GHI de ceu claro)
  >= 0,9 x percentil 90 da janela de 31 dias que TERMINA no dia (a da biblioteca e centrada, olharia 15 dias a
  frente). kW_eff(emissao) = mediana do `performance_index` (sem kwp) dos dias claros dos 60 dias anteriores a
  emissao (se nao houver nenhum, 120 dias).
  Metodos para (D, k), emissao t = D-k+1:
   1. fisico       kW_eff(t) x POA_prev_k(D, h)
   2. ajustado     b x POA_prev_k(D, h); b = minimos quadrados sem intercepto, horas de sol, dias [t-90, t-1],
                   com o arquivo do proprio lead k
   3. climatologia kW_eff(t) x POA_ceu_claro(D, h) x mediana da claridade do mesmo mes do calendario em anos
                   anteriores (claridade do dia d = energia / (kW_eff(d) x POA_ceu_claro do dia)); se houver menos
                   de 5 dias assim, a mediana dos 30 dias anteriores a t
   4. persist_cs   indice de ceu claro (energia / POA_ceu_claro do dia) do ultimo dia completo observado (ate 7
                   dias para tras) x POA_ceu_claro(D, h)
   5. encolhido    climatologia + a_k (fisico - climatologia); a_k MSE-otimo por lead, ajustado nos dias-alvo de
                   07/03/2024 a 31/07/2025 (antes do teste), horas de sol, as duas usinas JUNTAS com cada uma
                   dividida pela sua media nas horas de sol desse periodo (a_k de cada usina tambem e relatado)
  Metricas por lead e usina: skill = 1 - RMSE/RMSE_ref contra `climatologia` e contra `persist_cs`, por hora (horas
  de sol: `prosumer.metrics.evaluated_mask(how="sun")` com o GHI de ceu claro; hora valida e todos os metodos com
  valor) e no total do dia (dias com todas as horas de sol validas). Diebold-Mariano (`prosumer.metrics`, como no
  piloto_comum) de cada metodo de tempo contra a climatologia, por hora e no total do dia.
  Espalhamento: por dia, soma do desvio do GHI entre os modelos / soma da media (horas de sol), contra o erro
  absoluto do total do dia do metodo escolhido dividido pelo total esperado de ceu claro (kW_eff x POA_ceu_claro do
  dia); Spearman por lead e usina (o erro absoluto em kWh tambem e relatado).

CONSUMO (casas_cons, 20 casas de Dingle, teste 01/10/2020 -> 31/12/2020, so historico): leads 1..14.
  L = D-k o ultimo dia observado. `persist` = dia L repetido (a referencia); `semana` = o dia mais recente <= L com o
  mesmo dia da semana de D (D-7, ou D-14 para k > 7); `media_4sem` = media dos 4 ultimos desses; `media_7d` = media
  por hora dos dias L-6..L; `perfil_dia_util` = media por hora dos dias de L-27..L da mesma classe de D (dia util ou
  fim de semana). Skill contra `persist`, por hora (todas as horas) e no total do dia; DM contra `persist`.

PORTAO (escrito e versionado ANTES de rodar qualquer coisa; nao muda depois de ver os resultados):
  G1. Metodo de tempo escolhido = entre fisico, ajustado e encolhido, o de maior skill MEDIO contra a
      climatologia no TOTAL DO DIA, media dos leads 1-7 nas duas usinas (14 numeros). E o padrao da biblioteca;
      os a_k do encolhido ficam registrados de qualquer forma.
  G2. A geracao usa o tempo no lead k (1-7) so se o metodo escolhido bate a climatologia no total do dia com
      skill > 0 e DM p < 0,05 nas DUAS usinas. Nos leads que nao passam, o padrao e a climatologia.
  G3. Leads 8-15 (rodadas unicas, ~2 meses, sem calibracao antes do teste): so relato. O tempo NAO e usado alem
      do lead 7 com base neste piloto; se o fisico bater a climatologia no total do dia com p < 0,05 nas duas
      usinas, o lead fica marcado "indicativo" (pede validacao mais longa), nada mais.
  G4. Consumo: padrao = o metodo de maior skill medio POR HORA contra `persist` nos leads 1-14, desde que bata
      `persist` em TODOS os leads (skill por hora > 0 e DM p < 0,05). Senao, falha relatada como falha.

Uso (ambiente da biblioteca, .venv; rede so no baixa/rodadas):
  python piloto_horizonte.py baixa [Cascavel|Curitiba]   # Previous Runs leads 1-7 (cache por pedaco)
  python piloto_horizonte.py rodadas                     # Single Runs (12 UTC, IFS e GFS)
  python piloto_horizonte.py usina Cascavel              # metodos de uma usina (medir o tempo)
  python piloto_horizonte.py avalia                      # a_k, metricas, portao G1-G3 (as duas usinas)
  python piloto_horizonte.py casas                       # consumo, portao G4
Saidas: resultados/pilotos/horizonte.json (+ horizonte_usina_<serie>.parquet). Nunca previsoes/ nem metricas.csv.
"""
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings

import numpy as np
import pandas as pd
from comum import DADOS, SITIOS
from piloto_comum import PILOTOS

from prosumer import metrics as pm
from prosumer import physics
from prosumer.contracts import EnergySeries
from prosumer.diagnostics import clear_days, performance_index, roof_orientation
from prosumer.io import open_meteo as om

FUSO = "Etc/GMT+3"
INI_TESTE, FIM = pd.Timestamp("2025-08-01"), pd.Timestamp("2026-05-31")
INI_CAL = pd.Timestamp("2024-03-07")            # primeiro dia-alvo da calibracao do a_k (arquivo do IFS)
INI_ARQ = "2024-03-01"                          # inicio do download (margem antes do INI_CAL)
LEADS = range(1, 8)
LEADS_RODADAS = range(1, 16)
MODELOS = list(om.DEFAULT_MODELS)
MODELOS_RODADAS = ["ecmwf_ifs025", "gfs_seamless"]
URL_RODADAS = "https://single-runs-api.open-meteo.com/v1/forecast"
INI_RODADAS, FIM_RODADAS = pd.Timestamp("2026-03-28"), pd.Timestamp("2026-05-30")
PAUSA = 3.0                                     # segundos entre pedidos (API gratuita)
CACHE = DADOS / "_cache"                        # ignorado pelo git
ARQ_PREV = DADOS / "previsao_tempo_horizonte.parquet"
ARQ_ROD = DADOS / "previsao_tempo_rodadas.parquet"
SAIDA = PILOTOS / "horizonte.json"
TEMPO = ["fisico", "ajustado", "encolhido"]
METODOS = TEMPO + ["climatologia", "persist_cs"]
CONTA = dict(pedidos=0, bytes=0, espera_429_s=0.0)
warnings.filterwarnings("ignore", category=RuntimeWarning)   # medias de fatias vazias viram NaN, de proposito


# ------------------------------------------------------------------ rede
def _ctx():
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return None


CTX = _ctx()


class SemRodada(Exception):
    pass


def pega(url, params):
    """GET com espera longa no 429 (limite da API gratuita) e SemRodada no 400 (rodada fora do arquivo)."""
    q = url + "?" + urllib.parse.urlencode(params)
    for k in range(40):
        try:
            with urllib.request.urlopen(q, timeout=300, context=CTX) as r:
                corpo = r.read()
            CONTA["pedidos"] += 1
            CONTA["bytes"] += len(corpo)
            d = json.loads(corpo.decode("utf-8"))
            if d.get("error"):
                raise RuntimeError(d.get("reason"))
            return d
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            CONTA["pedidos"] += 1
            if e.code == 429:
                print(f"    429 (limite): espero 70 s ({msg[:80]})", flush=True)
                CONTA["espera_429_s"] += 70
                time.sleep(70)
                continue
            if e.code == 400 and "not available" in msg:
                raise SemRodada(msg)
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if k >= 5:
                raise
            print(f"    rede: {e!r}; nova tentativa", flush=True)
            time.sleep(10 * (k + 1))
    raise RuntimeError("40 tentativas sem resposta")


def baixa(series):
    """Previous Runs, leads 1-7, seis modelos, por usina; um pedaco por (usina, modelo, lead) no cache."""
    pasta = CACHE / "horizonte"
    pasta.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for serie in series:
        lat, lon = SITIOS[serie]
        for m in MODELOS:
            for k in LEADS:
                f = pasta / f"{serie}__{m}__{k}.parquet"
                if f.exists():
                    continue
                df = om.fetch_previous_runs(lat, lon, start=INI_ARQ, end=FIM, models=[m], variables=("ghi",),
                                            lead_days=k, tz=FUSO, get=pega, pause_s=0)
                df = pd.DataFrame(dict(serie=serie, modelo_nwp=m, lead=k, ds=df.ds.dt.tz_localize(None),
                                       ghi=df.ghi.astype("float32")))
                df.to_parquet(f, index=False)
                ok = df.dropna(subset=["ghi"])
                print(f"  {serie} {m:22s} lead {k}: {len(ok)} h com valor, de {ok.ds.min()} a {ok.ds.max()} "
                      f"({time.time() - t0:.0f} s, {CONTA['pedidos']} pedidos)", flush=True)
                time.sleep(PAUSA)
    partes = sorted(pasta.glob("*.parquet"))
    if len(partes) == len(SITIOS) * len(MODELOS) * len(LEADS):
        P = pd.concat([pd.read_parquet(f) for f in partes], ignore_index=True)
        P["lead"] = P["lead"].astype("int8")
        P.sort_values(["serie", "modelo_nwp", "lead", "ds"]).to_parquet(ARQ_PREV, index=False)
        print(f"  gravado {ARQ_PREV.name}: {len(P)} linhas, {ARQ_PREV.stat().st_size / 1e6:.1f} MB", flush=True)
    grava({"download_previous_runs": dict(segundos=round(time.time() - t0), **CONTA)}, junta=True)


def confere_lead1():
    """Lead 1 baixado agora x arquivos do regime C do benchmark (mesma conversao: rotulo h+1 -> hora h)."""
    P = pd.read_parquet(ARQ_PREV)
    P = P[P.lead == 1]
    B = pd.concat([pd.read_parquet(DADOS / "previsao_tempo.parquet"),
                   pd.read_parquet(DADOS / "previsao_tempo_extra.parquet")])
    out = {}
    for (serie, m), g in P.groupby(["serie", "modelo_nwp"]):
        b = B[(B.serie == serie) & (B.modelo_nwp == m)].set_index("ds").sort_index().ghi_prev.shift(-1)
        a = g.set_index("ds").ghi.astype(float)
        b = b.reindex(a.index)
        ambos = a.notna() & b.notna()
        out[f"{serie}|{m}"] = dict(horas_comuns=int(ambos.sum()),
                                   max_dif=round(float((a[ambos] - b[ambos]).abs().max()), 4) if ambos.any() else None,
                                   so_novo=int((a.notna() & b.isna()).sum()), so_benchmark=int((a.isna() & b.notna()).sum()))
    return out


def rodadas():
    """Single Runs: rodada das 12 UTC de cada dia, IFS e GFS, ate 16 dias; um pedaco por pedido no cache."""
    pasta = CACHE / "horizonte_rodadas"
    pasta.mkdir(parents=True, exist_ok=True)
    t0, indisp = time.time(), []
    for serie, (lat, lon) in SITIOS.items():
        for m in MODELOS_RODADAS:
            for dia in pd.date_range(INI_RODADAS, FIM_RODADAS, freq="D"):
                run = f"{dia.date()}T12:00"
                f = pasta / f"{serie}__{m}__{dia.date()}.parquet"
                if f.exists():
                    continue
                params = dict(latitude=lat, longitude=lon, models=m, run=run, hourly="shortwave_radiation",
                              timezone="GMT", forecast_days=16)
                try:
                    h = pega(URL_RODADAS, params)["hourly"]
                except SemRodada:
                    indisp.append(f"{serie}|{m}|{run}")
                    time.sleep(1.0)
                    continue
                df = om.parse_hourly(h, {"shortwave_radiation": "ghi"}, tz=FUSO)
                df = pd.DataFrame(dict(serie=serie, modelo_nwp=m, run=pd.Timestamp(run), ds=df.ds.dt.tz_localize(None),
                                       ghi=df.ghi.astype("float32")))
                df.to_parquet(f, index=False)
                time.sleep(1.0)
            print(f"  {serie} {m}: {time.time() - t0:.0f} s, {CONTA['pedidos']} pedidos", flush=True)
    partes = sorted(pasta.glob("*.parquet"))
    R = pd.concat([pd.read_parquet(f) for f in partes], ignore_index=True)
    R.sort_values(["serie", "modelo_nwp", "run", "ds"]).to_parquet(ARQ_ROD, index=False)
    primeira = {m: str(R[R.modelo_nwp == m].run.min()) for m in MODELOS_RODADAS}
    print(f"  gravado {ARQ_ROD.name}: {len(R)} linhas, {ARQ_ROD.stat().st_size / 1e6:.1f} MB; primeira rodada {primeira}")
    grava({"download_single_runs": dict(segundos=round(time.time() - t0), primeira_rodada=primeira,
                                        indisponiveis=len(indisp), exemplos_indisponiveis=indisp[:6], **CONTA)},
          junta=True)


# ------------------------------------------------------------------ usinas
def grade_usina(serie):
    """Matrizes dia x hora: y (NaN invalido), GHI e POA de ceu claro; a serie da biblioteca; a orientacao."""
    u = pd.read_parquet(DADOS / "usinas_horario.parquet")
    u = u[u.serie == serie].set_index("ds").sort_index()
    y = (u.y_Wh / 1000.0).where(u.y_valido)
    dias = pd.date_range(u.index.min().normalize(), FIM, freq="D")
    horas = pd.date_range(dias[0], FIM + pd.Timedelta(hours=23), freq="h")
    y = y.reindex(horas)
    site = SITIOS[serie]
    aw = horas.tz_localize(FUSO)
    x = pd.DataFrame({"unique_id": serie, "ds": aw, "y": y.to_numpy()})
    x["valid"] = x.y.notna()
    s = EnergySeries(frame=x, unit="kWh", quantity="generation", tz=FUSO, freq="h")
    antes = EnergySeries(frame=x[x.ds < INI_TESTE.tz_localize(FUSO)].reset_index(drop=True), unit="kWh",
                         quantity="generation", tz=FUSO, freq="h")
    ori = roof_orientation(antes, site).iloc[0]
    tilt, az = float(ori.tilt), float(ori.azimuth)
    sun = physics.mean_sun(aw, *site)
    cs = physics.clear_sky_ghi(aw, *site)
    poa_cs = physics.poa_isotropic(cs, sun, tilt, az) / 1000.0
    nd = len(dias)
    G = dict(dias=dias, horas=horas, Y=y.to_numpy().reshape(nd, 24), CS=cs.reshape(nd, 24),
             PCS=poa_cs.reshape(nd, 24), sun=sun, tilt=tilt, az=az, r2=float(ori.r2), serie=serie, s=s, site=site)
    return G


def dias_claros_causais(s, site):
    """Dias claros com a janela de 31 dias que TERMINA no dia (sem olhar para frente)."""
    c = clear_days(s, site)[["unique_id", "date", "ratio"]]
    r = c.set_index("date").ratio.sort_index()
    r = r.reindex(pd.date_range(r.index.min(), r.index.max(), freq="D"))
    top = r.rolling(31, min_periods=10).quantile(0.9)
    c["top"] = top.reindex(c.date).to_numpy()
    c["clear"] = (c.ratio >= 0.9 * c.top) & (c.ratio > 0)
    return c


def kw_eff_por_emissao(idx, dias, janela=60, reserva=120):
    """kW_eff para emissao em cada dia t: mediana do indice dos dias claros em [t-janela, t-1]."""
    d = pd.DatetimeIndex(idx.date).to_numpy()
    v = idx["index"].to_numpy(float)
    ordem = np.argsort(d)
    d, v = d[ordem], v[ordem]
    out = np.full(len(dias), np.nan)
    for i, t in enumerate(dias.to_numpy()):
        for w in (janela, reserva):
            a = np.searchsorted(d, t - np.timedelta64(w, "D"))
            b = np.searchsorted(d, t)
            if b > a:
                out[i] = np.median(v[a:b])
                break
    return out


def poa_prevista(G, ghi):
    """POA (kWh/m2 por hora) a partir de uma matriz dia x hora de GHI previsto (NaN fica NaN)."""
    g = ghi.reshape(-1)
    p = np.full(g.shape, np.nan)
    ok = np.isfinite(g)
    p[ok] = physics.poa_isotropic(g[ok], G["sun"].loc[ok], G["tilt"], G["az"]) / 1000.0
    return p.reshape(ghi.shape)


def ghi_por_lead(G, P):
    """{lead: (media, espalhamento, n_modelos)} matrizes dia x hora, a partir do formato longo, e a contagem de
    modelo-dias descartados pelo filtro de qualidade (GHI > 1,2 x ceu claro + 50 W/m2 em alguma hora do dia)."""
    out, descartes = {}, {}
    nd = len(G["dias"])
    teto = (1.2 * G["CS"] + 50.0).reshape(-1)
    for k, g in P.groupby("lead"):
        w = g.pivot_table(index="ds", columns="modelo_nwp", values="ghi", dropna=False).reindex(G["horas"])
        a = w.to_numpy(float)
        # filtro de qualidade: um modelo com GHI fisicamente impossivel em alguma hora sai da media no dia todo
        ruim = (a > teto[:, None]).reshape(nd, 24, -1).any(axis=1)          # dia x modelo
        a = np.where(np.repeat(ruim, 24, axis=0), np.nan, a)
        descartes[int(k)] = {str(m): int(ruim[:, j].sum()) for j, m in enumerate(w.columns)}
        n = np.isfinite(a).sum(1)
        media = np.nanmean(a, axis=1)                      # media dos modelos com valor naquela hora
        desv = np.nanstd(a, axis=1)
        out[int(k)] = (media.reshape(nd, 24), desv.reshape(nd, 24), n.reshape(nd, 24))
    return out, descartes


def metodos_usina(G, ghi, leads, com_ajustado=True):
    """Previsoes (dia x hora) de cada metodo e lead, para todos os dias-alvo com emissao possivel."""
    Y, PCS, sol = G["Y"], G["PCS"], G["CS"] > 0
    dias = G["dias"]
    nd = len(dias)
    completo = np.all(np.isfinite(Y) | ~sol, axis=1)
    E = np.where(completo, np.nansum(np.where(sol, Y, 0.0), axis=1), np.nan)
    PCSd = PCS.sum(1)
    claros = dias_claros_causais(G["s"], G["site"])
    idx = performance_index(G["s"], G["site"], orientation=(G["tilt"], G["az"]), clear=claros)
    kw = kw_eff_por_emissao(idx, dias)                      # kw[i] = kW_eff para emissao no dia i
    claridade = E / (kw * PCSd)
    mes, ano = dias.month.to_numpy(), dias.year.to_numpy()
    ind_cs = E / PCSd                                       # indice de ceu claro do dia (persist_cs)
    out = {}
    for k in leads:
        if k not in ghi:
            continue
        media, desv, _ = ghi[k]
        POAf = poa_prevista(G, media)
        # ajustado: somas diarias de y*x e x*x nas horas de sol validas
        ok = sol & np.isfinite(Y) & np.isfinite(POAf)
        sxy = np.where(ok, Y * POAf, 0.0).sum(1)
        sxx = np.where(ok, POAf * POAf, 0.0).sum(1)
        cxy, cxx, cnt = (np.concatenate([[0.0], np.cumsum(v)]) for v in (sxy, sxx, ok.any(1).astype(float)))
        res = {m: np.full((nd, 24), np.nan) for m in METODOS if m != "encolhido"}
        espal = np.full(nd, np.nan)
        b_lst = np.full(nd, np.nan)
        for iD in range(nd):
            it = iD - k + 1                                 # emissao (00:00 do dia it)
            if it < 1 or dias[iD] < INI_CAL:
                continue
            kwt = kw[it]
            if not np.isfinite(kwt):
                continue
            res["fisico"][iD] = kwt * POAf[iD]
            if com_ajustado:
                a = max(it - 90, 0)
                if cnt[it] - cnt[a] >= 20 and cxx[it] - cxx[a] > 0:
                    b_lst[iD] = (cxy[it] - cxy[a]) / (cxx[it] - cxx[a])
                    res["ajustado"][iD] = b_lst[iD] * POAf[iD]
            prev = np.arange(it)
            mm = prev[(mes[:it] == mes[iD]) & (ano[:it] < ano[iD]) & np.isfinite(claridade[:it])]
            if len(mm) >= 5:
                med = np.median(claridade[mm])
            else:
                c30 = claridade[max(it - 30, 0):it]
                med = np.median(c30[np.isfinite(c30)]) if np.isfinite(c30).any() else np.nan
            res["climatologia"][iD] = kwt * PCS[iD] * med
            for j in range(it - 1, max(it - 8, -1), -1):
                if np.isfinite(ind_cs[j]):
                    res["persist_cs"][iD] = ind_cs[j] * PCS[iD]
                    break
            s_sum = np.nansum(np.where(sol[iD], media[iD], 0.0))
            if s_sum > 0 and np.isfinite(media[iD][sol[iD]]).all():
                espal[iD] = np.nansum(np.where(sol[iD], desv[iD], 0.0)) / s_sum
        out[k] = dict(prev=res, espalhamento=espal, kw=np.array([kw[i - k + 1] if i - k + 1 >= 0 else np.nan
                                                                   for i in range(nd)]))
    return out, dict(kw=kw, n_claros=int(claros.clear.sum()))


def longo(G, k, r):
    """Formato longo (serie, lead, ds, y, cs, metodos, espalhamento do dia, kw) das horas do periodo util."""
    nd = len(G["dias"])
    d = pd.DataFrame({"serie": G["serie"], "lead": k, "ds": G["horas"], "y": G["Y"].reshape(-1),
                      "cs": G["CS"].reshape(-1), "pcs": G["PCS"].reshape(-1)})
    for m, a in r["prev"].items():
        d[m] = a.reshape(-1)
    d["espalhamento"] = np.repeat(r["espalhamento"], 24)
    d["kw"] = np.repeat(r["kw"], 24)
    d["dia"] = d.ds.dt.normalize()
    assert len(d) == nd * 24
    return d[d.dia >= INI_CAL]


def usina(serie):
    t0 = time.time()
    G = grade_usina(serie)
    P = pd.read_parquet(ARQ_PREV)
    ghi, descartes = ghi_por_lead(G, P[P.serie == serie])
    out, info = metodos_usina(G, ghi, LEADS)
    tab = pd.concat([longo(G, k, r) for k, r in out.items()], ignore_index=True)
    tab.to_parquet(PILOTOS / f"horizonte_usina_{serie}.parquet", index=False)
    res = dict(inclinacao=G["tilt"], azimute=G["az"], r2=round(G["r2"], 3), dias_claros=info["n_claros"],
               kw_eff_mediana_teste=round(float(np.nanmedian(info["kw"][G["dias"] >= INI_TESTE])), 3),
               segundos=round(time.time() - t0, 1),
               descartes_qualidade={str(k): v for k, v in descartes.items()})
    if ARQ_ROD.exists():
        R = pd.read_parquet(ARQ_ROD)
        R = R[R.serie == serie].copy()
        R["dia"] = R.ds.dt.normalize()
        R["lead"] = (R.dia - R.run.dt.normalize()).dt.days
        cheio = R.dropna(subset=["ghi"]).groupby(["modelo_nwp", "run", "dia"]).ghi.transform("size") == 24
        R = R.loc[R.ghi.notna()][cheio.to_numpy()]          # modelo entra no dia so com as 24 horas
        R = R[R.lead.between(1, max(LEADS_RODADAS))]
        ghi2, descartes2 = ghi_por_lead(G, R[["lead", "ds", "modelo_nwp", "ghi"]])
        res["descartes_qualidade_rodadas"] = {str(k): v for k, v in descartes2.items()}
        o2, _ = metodos_usina(G, ghi2, LEADS_RODADAS,
                              com_ajustado=False)
        t2 = pd.concat([longo(G, k, r) for k, r in o2.items()], ignore_index=True)
        t2.to_parquet(PILOTOS / f"horizonte_usina_{serie}_rodadas.parquet", index=False)
        res["leads_rodadas"] = sorted(int(k) for k in o2)
    res["segundos"] = round(time.time() - t0, 1)
    print(f"  {serie}: {res}", flush=True)
    grava({"usinas": {serie: res}}, junta=True)


# ------------------------------------------------------------------ avaliacao
def _ek(df, col, dia=False):
    s = (df[col] - df.y) ** 2
    idx = pd.MultiIndex.from_arrays([df.serie, df.dia if dia else df.ds], names=["unique_id", "ds"])
    return pd.Series(s.to_numpy(), index=idx)


def skill(df, col, ref):
    return float(1 - np.sqrt(np.mean((df[col] - df.y) ** 2)) / np.sqrt(np.mean((df[ref] - df.y) ** 2)))


def avalia_lead(t, metodos, refs=("climatologia", "persist_cs"), dm_contra="climatologia"):
    """Skill por hora e no total do dia + DM dos metodos de tempo contra a climatologia."""
    sol = pm.evaluated_mask(t.rename(columns={"cs": "cs_ghi"}), "sun", sun_column="cs_ghi")
    h = t[sol & t.y.notna()].dropna(subset=metodos)
    # dia completo: todas as horas de sol com y valido e todos os metodos
    ts = t[sol]
    ok = ts.y.notna() & ts[metodos].notna().all(axis=1)
    dias_ok = ok.groupby([ts.serie, ts.dia]).all()
    dias_ok = dias_ok[dias_ok].index
    d = h.groupby(["serie", "dia"])[["y"] + metodos].sum().loc[dias_ok].reset_index()
    r = dict(horas=len(h), dias=len(d))
    for nivel, df in (("hora", h), ("dia", d)):
        r[nivel] = {m: {f"skill_vs_{ref}": round(skill(df, m, ref), 4) for ref in refs if ref != m} for m in metodos}
        for m in metodos:
            if m in TEMPO or m == "fisico":
                _, _, p = pm.diebold_mariano(_ek(df, m, nivel == "dia"), _ek(df, dm_contra, nivel == "dia"))
                r[nivel][m][f"dm_p_vs_{dm_contra}"] = round(float(p), 4)
    return r, h, d


def ajusta_ak(tabs):
    """a_k MSE-otimo (encolhido), so dias-alvo antes do teste, horas de sol; por usina e junto (normalizado)."""
    out = {}
    for k in LEADS:
        partes, por = [], {}
        for serie, t in tabs.items():
            c = t[(t.lead == k) & (t.dia < INI_TESTE) & (t.cs > 0)].dropna(subset=["y", "fisico", "climatologia"])
            esc = float(c.y.mean())
            e, f = (c.y - c.climatologia) / esc, (c.fisico - c.climatologia) / esc
            por[serie] = dict(a=round(float((e * f).sum() / (f * f).sum()), 4), horas=len(c))
            partes.append((e, f))
        e = pd.concat([p[0] for p in partes])
        f = pd.concat([p[1] for p in partes])
        out[k] = dict(a=float((e * f).sum() / (f * f).sum()), por_usina=por)
    return out


def spearman(x, y):
    from scipy import stats
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10:
        return None, None
    r, p = stats.spearmanr(x[ok], y[ok])
    return round(float(r), 3), round(float(p), 4)


def avalia():
    tabs = {s: pd.read_parquet(PILOTOS / f"horizonte_usina_{s}.parquet") for s in SITIOS}
    ak = ajusta_ak(tabs)
    for t in tabs.values():
        t["encolhido"] = t.climatologia + t.lead.map({k: v["a"] for k, v in ak.items()}) * (t.fisico - t.climatologia)
    res = {"a_k": {str(k): dict(a=round(v["a"], 4), por_usina=v["por_usina"]) for k, v in ak.items()},
           "leads": {}}
    dia_tabs = {}
    for serie, t in tabs.items():
        tt = t[t.dia >= INI_TESTE]
        for k in LEADS:
            r, h, d = avalia_lead(tt[tt.lead == k], METODOS)
            res["leads"].setdefault(str(k), {})[serie] = r
            dia_tabs[(serie, k)] = (h, d)
    # G1: metodo escolhido = maior skill medio contra a climatologia no total do dia, leads 1-7, duas usinas
    medias = {m: float(np.mean([res["leads"][str(k)][s]["dia"][m]["skill_vs_climatologia"]
                                for k in LEADS for s in SITIOS])) for m in TEMPO}
    escolhido = max(medias, key=medias.get)
    res["G1"] = dict(skill_medio_dia_vs_climatologia={m: round(v, 4) for m, v in medias.items()}, escolhido=escolhido,
                     a_k_padrao={str(k): round(v["a"], 4) for k, v in ak.items()})
    # G2 por lead
    g2 = {}
    for k in LEADS:
        cada = {s: res["leads"][str(k)][s]["dia"][escolhido] for s in SITIOS}
        passa = all(c["skill_vs_climatologia"] > 0 and c["dm_p_vs_climatologia"] < 0.05 for c in cada.values())
        g2[str(k)] = dict(passa=passa, **{s: dict(skill=c["skill_vs_climatologia"], p=c["dm_p_vs_climatologia"])
                                          for s, c in cada.items()})
    res["G2"] = g2
    # espalhamento x erro (metodo escolhido), total do dia
    esp = {}
    for k in LEADS:
        for s in SITIOS:
            t = tabs[s]
            t = t[(t.dia >= INI_TESTE) & (t.lead == k)]
            _, d = dia_tabs[(s, k)]
            info = t.groupby("dia")[["espalhamento", "kw"]].first()
            pcs = t[t.cs > 0].groupby("dia").pcs.sum()
            dd = d[d.serie == s].set_index("dia")
            erro = (dd[escolhido] - dd.y).abs()
            rel = erro / (info.kw.reindex(dd.index) * pcs.reindex(dd.index))
            x = info.espalhamento.reindex(dd.index).to_numpy(float)
            rho, p = spearman(x, rel.to_numpy(float))
            rho2, p2 = spearman(x, erro.to_numpy(float))
            esp.setdefault(str(k), {})[s] = dict(spearman_rel=rho, p_rel=p, spearman_kwh=rho2, p_kwh=p2,
                                                 espalhamento_mediano=round(float(np.nanmedian(x)), 3))
    res["espalhamento_x_erro"] = esp
    # G3: rodadas unicas, leads 1-15, so fisico x climatologia x persist_cs
    rod = {}
    for s in SITIOS:
        f = PILOTOS / f"horizonte_usina_{s}_rodadas.parquet"
        if not f.exists():
            continue
        t = pd.read_parquet(f)
        t = t[t.dia >= INI_TESTE]
        for k in sorted(t.lead.unique()):
            tk = t[t.lead == k]
            if tk.fisico.notna().sum() == 0:
                continue
            r, _, d = avalia_lead(tk, ["fisico", "climatologia", "persist_cs"])
            r["primeiro_dia"], r["ultimo_dia"] = str(d.dia.min().date()), str(d.dia.max().date())
            rod.setdefault(str(int(k)), {})[s] = r
    g3 = {}
    for k, v in rod.items():
        if len(v) == len(SITIOS):
            g3[k] = dict(indicativo=all(v[s]["dia"]["fisico"]["skill_vs_climatologia"] > 0
                                        and v[s]["dia"]["fisico"]["dm_p_vs_climatologia"] < 0.05 for s in SITIOS))
    res["rodadas"] = rod
    res["G3"] = g3
    grava({"geracao": res}, junta=True)
    imprime_geracao(res)


def imprime_geracao(res):
    print("\na_k:", {k: v["a"] for k, v in res["a_k"].items()})
    print("G1:", res["G1"])
    for nivel in ("hora", "dia"):
        print(f"\n== skill contra climatologia / persist_cs ({nivel}) ==")
        for k, v in res["leads"].items():
            for s, r in v.items():
                cel = "  ".join(f"{m}:{r[nivel][m].get('skill_vs_climatologia', 0):+.3f}/"
                                f"{r[nivel][m].get('skill_vs_persist_cs', 0):+.3f}" for m in METODOS)
                print(f" k={k} {s:9s} n={r['dias']:3d} {cel}")
    print("\nG2:", json.dumps(res["G2"]))
    print("espalhamento:", json.dumps(res["espalhamento_x_erro"]))
    for k, v in res["rodadas"].items():
        for s, r in v.items():
            print(f" rodadas k={k} {s:9s} dias={r['dias']} fisico dia {r['dia']['fisico']}")
    print("G3:", res["G3"])


# ------------------------------------------------------------------ consumo
def casas():
    t0 = time.time()
    c = pd.read_parquet(DADOS / "casas_horario.parquet")
    dias = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    horas = pd.date_range(dias[0], dias[-1] + pd.Timedelta(hours=23), freq="h")
    ids = sorted(c.casa.unique(), key=lambda s: int(s[1:]))
    Y = np.stack([c[c.casa == u].set_index("ds").cons_kWh.reindex(horas).to_numpy(float).reshape(len(dias), 24)
                  for u in ids])                                        # casa x dia x hora
    fds = dias.dayofweek.to_numpy() >= 5
    teste = np.where((dias >= "2020-10-01") & (dias <= "2020-12-31"))[0]
    nomes = ["persist", "semana", "media_4sem", "media_7d", "perfil_dia_util"]
    res = {}
    for k in range(1, 15):
        P = {m: np.full((len(ids), len(teste), 24), np.nan) for m in nomes}
        for j, iD in enumerate(teste):
            L = iD - k
            s = 7 * int(np.ceil(k / 7))
            P["persist"][:, j] = Y[:, L]
            P["semana"][:, j] = Y[:, iD - s]
            with np.errstate(all="ignore"):
                P["media_4sem"][:, j] = np.nanmean(Y[:, [iD - s - 7 * q for q in range(4)]], axis=1)
                P["media_7d"][:, j] = np.nanmean(Y[:, L - 6:L + 1], axis=1)
                jan = np.arange(L - 27, L + 1)
                P["perfil_dia_util"][:, j] = np.nanmean(Y[:, jan[fds[jan] == fds[iD]]], axis=1)
        y = Y[:, teste]
        ok = np.isfinite(y) & np.all([np.isfinite(P[m]) for m in nomes], axis=0)
        ds = (dias[teste].to_numpy()[None, :, None] + np.arange(24)[None, None, :] * np.timedelta64(1, "h"))
        ds = np.broadcast_to(ds, y.shape)
        uid = np.broadcast_to(np.array(ids)[:, None, None], y.shape)
        h = pd.DataFrame({"serie": uid[ok], "ds": ds[ok], "y": y[ok], **{m: P[m][ok] for m in nomes}})
        h["dia"] = h.ds.dt.normalize()
        cheio = ok.all(axis=2)
        dsd = np.broadcast_to(dias[teste].to_numpy()[None, :], cheio.shape)
        uidd = np.broadcast_to(np.array(ids)[:, None], cheio.shape)
        d = pd.DataFrame({"serie": uidd[cheio], "dia": dsd[cheio], "y": y.sum(2)[cheio],
                          **{m: P[m].sum(2)[cheio] for m in nomes}})
        r = dict(horas=len(h), dias_casa=len(d))
        for nivel, df in (("hora", h), ("dia", d)):
            r[nivel] = {}
            for m in nomes[1:]:
                _, _, p = pm.diebold_mariano(_ek(df, m, nivel == "dia"), _ek(df, "persist", nivel == "dia"))
                r[nivel][m] = dict(skill_vs_persist=round(skill(df, m, "persist"), 4), dm_p_vs_persist=round(float(p), 4))
        res[str(k)] = r
    medias = {m: float(np.mean([res[str(k)]["hora"][m]["skill_vs_persist"] for k in range(1, 15)])) for m in nomes[1:]}
    esc = max(medias, key=medias.get)
    falhas = [k for k in range(1, 15) if not (res[str(k)]["hora"][esc]["skill_vs_persist"] > 0
                                              and res[str(k)]["hora"][esc]["dm_p_vs_persist"] < 0.05)]
    g4 = dict(skill_medio_hora={m: round(v, 4) for m, v in medias.items()}, escolhido=esc, passa=not falhas,
              leads_que_falham=falhas)
    bench = pd.read_csv(PILOTOS.parent / "metricas.csv", sep=";", decimal=",", encoding="utf-8-sig")
    bench = bench[(bench.caso == "casas_cons") & (bench.regime == "A")].set_index("modelo").skill
    conf = dict(media_7d_lead1=res["1"]["hora"]["media_7d"]["skill_vs_persist"],
                media_7d_benchmark=round(float(bench.get("media_7d", np.nan)), 4),
                semana_lead1=res["1"]["hora"]["semana"]["skill_vs_persist"],
                semanal_168h_benchmark=round(float(bench.get("semanal_168h", np.nan)), 4))
    grava({"consumo": dict(leads=res, G4=g4, conferencia_lead1=conf, segundos=round(time.time() - t0, 1))}, junta=True)
    for nivel in ("hora", "dia"):
        print(f"\n== consumo, skill contra persist ({nivel}) ==")
        for k, r in res.items():
            print(f" k={k:2s} " + "  ".join(f"{m}:{v['skill_vs_persist']:+.3f}(p{v['dm_p_vs_persist']:.3f})"
                                           for m, v in r[nivel].items()))
    print("G4:", g4, "\nconferencia:", conf, f"\n{time.time() - t0:.0f} s")


# ------------------------------------------------------------------ saida
def grava(parte, junta=True):
    tudo = json.loads(SAIDA.read_text(encoding="utf-8")) if SAIDA.exists() else {}
    for k, v in parte.items():
        if junta and isinstance(v, dict) and isinstance(tudo.get(k), dict):
            tudo[k].update(v)
        else:
            tudo[k] = v
    tudo["data"] = "2026-10-12"
    SAIDA.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "baixa":
        baixa(sys.argv[2:] or list(SITIOS))
        if ARQ_PREV.exists():
            conf = confere_lead1()
            print(json.dumps(conf, indent=1))
            grava({"conferencia_lead1": conf}, junta=False)
    elif cmd == "rodadas":
        rodadas()
    elif cmd == "usina":
        for s in sys.argv[2:] or list(SITIOS):
            usina(s)
    elif cmd == "avalia":
        avalia()
    elif cmd == "casas":
        casas()
    else:
        raise SystemExit(__doc__)
