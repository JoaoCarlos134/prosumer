"""C9 (servidor, 18/11/2026): posicao das usinas do BR-PVGen estimada pelos proprios dados.

Portao em docs/projeto/PILOTOS_F1_F2.md, "C9" (commitado antes de rodar). Metodo:
  Forma da curva de ceu claro. Nos dias claros (curva lisa: soma |variacoes| <= 1,15 x 2 x maximo do dia, e maximo do
  dia >= 0,8 x o maior maximo dos 30 dias em volta; ate 80 dias espalhados no ano), cada dia e dividido pelo proprio
  maximo; o modelo (posicao do sol NOAA simplificada + Haurwitz, plano inclinado com 85% direta / 15% difusa
  isotropica) tambem. Minimiza o erro quadratico medio entre as duas formas em (latitude, longitude[, inclinacao,
  azimute]): grade grossa (latitude -55..55 a cada 2,5 graus; longitude +-12 graus em volta da longitude do meio-dia
  solar medido, a cada 0,5; plano: inclinacao {0,10,20,30,40}, azimute a cada 30) e Nelder-Mead a partir dos 3
  melhores. Tempo de cada amostra: o meio do intervalo (convencao da biblioteca: rotulo = inicio) ou o proprio carimbo
  (BR-PVGen: media movel ponderada numa grade de 15 min, carimbo UTC).
  Validacao (posicao conhecida, NUNCA usada no ajuste): os 6 sistemas do PVDAQ do V2 (potencia AC, plano ajustado junto)
  e as duas usinas (energia horaria, plano ajustado junto; so relato: passo de 1 h).
  BR-PVGen: GHI medido na estacao de cada usina (plano horizontal, so latitude e longitude).

Uso (ambiente da biblioteca, CPU): python piloto_c9_posicao.py valida | brpvgen
Saidas: resultados/pilotos/c9_posicao.json e c9_posicao_brpvgen.csv (dados publicos CC BY 4.0; so posicoes estimadas).
"""

import json
import sys
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).parent))
from piloto_comum import PILOTOS  # noqa: E402

BR = Path.home() / "Projeto_IA" / "dados_publicos" / "br_pvgen"
SAIDA = PILOTOS / "c9_posicao.json"
TOL = 0.5
# caixas aproximadas dos estados (lat_min, lat_max, lon_min, lon_max), para o relato "dentro do estado"
ESTADOS = {"SP": (-25.4, -19.7, -53.2, -44.1), "GO": (-19.6, -12.3, -53.3, -45.9), "RJ": (-23.4, -20.7, -44.9, -40.9),
           "MG": (-22.9, -14.2, -51.1, -39.8), "MS": (-24.1, -17.1, -58.2, -50.9), "PR": (-26.8, -22.5, -54.7, -48.0),
           "BA": (-18.4, -8.5, -46.7, -37.3)}
warnings.filterwarnings("ignore")


# ------------------------------------------------------------------ modelo
def sol(t_utc, lat, lon):
    """cos(zenite) e azimute do sol (graus, 0 = norte, horario). t_utc: DatetimeIndex UTC (ingenuo)."""
    doy = t_utc.dayofyear.to_numpy() if hasattr(t_utc, "dayofyear") else t_utc[0]
    hora = (t_utc.hour + t_utc.minute / 60 + t_utc.second / 3600).to_numpy() if hasattr(t_utc, "hour") else t_utc[1]
    g = 2 * np.pi / 365 * (doy - 1 + (hora - 12) / 24)
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g)
                    - 0.040849 * np.sin(2 * g))
    dec = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
           - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    ha = np.radians((hora * 60 + eot + 4 * lon) / 4 - 180)
    phi = np.radians(lat)
    cz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(ha)
    sz = np.sqrt(np.clip(1 - cz ** 2, 1e-12, None))
    caz = (np.sin(dec) - np.sin(phi) * cz) / (np.cos(phi) * sz)
    az = np.degrees(np.arccos(np.clip(caz, -1, 1)))
    az = np.where(ha > 0, 360 - az, az)
    return cz, az


def forma(tt, lat, lon, tilt=0.0, azp=0.0):
    cz, az = sol(tt, lat, lon)
    czp = np.clip(cz, 0, None)
    ghi = np.where(cz > 0.01, 1098 * czp * np.exp(-0.057 / np.maximum(czp, 0.01)), 0.0)
    if tilt == 0:
        return ghi
    b, sz = np.radians(tilt), np.sqrt(np.clip(1 - cz ** 2, 0, None))
    cth = np.clip(cz * np.cos(b) + sz * np.sin(b) * np.cos(np.radians(az - azp)), 0, None)
    return 0.85 * ghi * cth / np.maximum(czp, 0.05) * (cz > 0.05) + 0.15 * ghi * (1 + np.cos(b)) / 2


# ------------------------------------------------------------------ dias claros e ajuste
def dias_claros(s, n_max=80):
    """s: Series (indice local ingenuo, valor >= 0). Devolve a lista de dias (Timestamp) claros."""
    s = s.clip(lower=0)
    d = s.groupby(s.index.normalize())
    mx = d.max()
    var = d.apply(lambda x: np.abs(np.diff(x.fillna(0).to_numpy())).sum())
    cheio = d.count() >= d.count().median() * 0.9
    teto = mx.rolling(31, center=True, min_periods=5).max()
    ok = (var <= 1.15 * 2 * mx) & (mx >= 0.8 * teto) & (mx > 0) & cheio
    dias = ok[ok].index
    if len(dias) > n_max:
        dias = dias[np.linspace(0, len(dias) - 1, n_max).round().astype(int)]
    return list(dias)


def prepara(s, tz_utc_offset_h, meio_h):
    """Amostras dos dias claros: tempos UTC (com o meio do intervalo), valor normalizado por dia, rotulo do dia."""
    dias = dias_claros(s)
    x = s[s.index.normalize().isin(dias)].dropna()
    t = x.index - pd.Timedelta(hours=tz_utc_offset_h) + pd.Timedelta(hours=meio_h)
    dia = x.index.normalize()
    v = (x / x.groupby(dia).transform("max")).to_numpy()
    codigo = pd.factorize(dia)[0]
    inicios = np.flatnonzero(np.r_[True, np.diff(codigo) != 0])
    return pd.DatetimeIndex(t), v, inicios, len(dias)


def erro(p, tt, v, dia, plano):
    """dia: indices de inicio de cada dia (amostras em ordem de tempo, dias contiguos)."""
    lat, lon = p[0], p[1]
    tilt, azp = (p[2], p[3]) if plano else (0.0, 0.0)
    if not (-70 < lat < 70) or (plano and not (0 <= tilt <= 60)):
        return 1e9
    m = forma(tt, lat, lon, tilt, azp)
    mx = np.maximum.reduceat(m, dia)
    mx = np.repeat(mx, np.diff(np.r_[dia, len(m)]))
    m = m / np.where(mx > 0, mx, 1)
    return float(np.mean((m - v) ** 2))


def ajusta(tt, v, dia, plano):
    """Grade em duas etapas (plano horizontal; depois o plano dos paineis em volta dos 3 melhores) + Nelder-Mead."""
    tt = (tt.dayofyear.to_numpy(), (tt.hour + tt.minute / 60 + tt.second / 3600).to_numpy())
    h = tt[1]
    cont = np.diff(np.r_[dia, len(v)])
    cent = np.add.reduceat(h * v, dia) / np.add.reduceat(v, dia)
    lon0 = 15 * (12 - float(np.median(cent)))
    c1 = sorted((erro((la, lo), tt, v, dia, False), la, lo) for la in np.arange(-55, 55.1, 2.5)
                for lo in np.arange(lon0 - 12, lon0 + 12.1, 0.5))
    cand = [(e, la, lo, 0.0, 0.0) for e, la, lo in c1[:3]]
    if plano:
        cand = []
        for _, la0, lo0 in c1[:3]:
            for la in np.arange(la0 - 5, la0 + 5.1, 1.0):
                for lo in np.arange(lo0 - 3, lo0 + 3.1, 0.5):
                    for ti in (10, 20, 30, 40):
                        for az in range(0, 360, 30):
                            cand.append((erro((la, lo, ti, az), tt, v, dia, True), la, lo, ti, az))
        cand.sort()
    melhor = None
    for c in cand[:3]:
        x0 = np.array(c[1:5] if plano else c[1:3], float)
        r = minimize(erro, x0, args=(tt, v, dia, plano), method="Nelder-Mead",
                     options=dict(xatol=1e-3, fatol=1e-10, maxiter=4000))
        if melhor is None or r.fun < melhor.fun:
            melhor = r
    del cont
    return melhor.x, float(melhor.fun)


# ------------------------------------------------------------------ validacao e BR-PVGen
def valida():
    from comum import DADOS, SITIOS
    from piloto_pvdaq import SISTEMAS, _sistemas, serie_pvdaq
    info = _sistemas()
    rel = {}
    for sid in SISTEMAS:
        s = serie_pvdaq(sid, info)
        f = s.frame
        x = f.set_index(f.ds).y.where(f.valid)
        passo_h = (x.index[1] - x.index[0]).total_seconds() / 3600
        off = pd.Timestamp("2019-01-15", tz=x.index.tz).utcoffset().total_seconds() / 3600
        xs = pd.Series(x.to_numpy(float), index=x.index.tz_convert(f"Etc/GMT{-int(off):+d}").tz_localize(None))
        tt, v, dia, n = prepara(xs, off, passo_h / 2)
        p, e = ajusta(tt, v, dia, plano=True)
        verdade = (info[sid]["latitude"], info[sid]["longitude"])
        rel[f"pvdaq_{sid}"] = dict(passo_min=round(passo_h * 60), dias_claros=n, lat=p[0], lon=p[1], tilt=p[2], az=p[3] % 360,
                                   erro_lat=p[0] - verdade[0], erro_lon=p[1] - verdade[1], mse=e)
        print(sid, rel[f"pvdaq_{sid}"], flush=True)
    u = pd.read_parquet(DADOS / "usinas_horario.parquet")
    for serie, verdade in SITIOS.items():
        g = u[(u.serie == serie) & (u.ds >= "2025-01-01")].set_index("ds")
        tt, v, dia, n = prepara((g.y_Wh.where(g.y_valido)).astype(float), -3, 0.5)
        p, e = ajusta(tt, v, dia, plano=True)
        rel[f"usina_{serie}"] = dict(passo_min=60, dias_claros=n, erro_lat=p[0] - verdade[0], erro_lon=p[1] - verdade[1],
                                     tilt=p[2], az=p[3] % 360, mse=e)
        print(serie, rel[f"usina_{serie}"], flush=True)
    finos = [k for k, r in rel.items() if k.startswith("pvdaq") and r["passo_min"] <= 5]
    ok = [k for k in finos if abs(rel[k]["erro_lat"]) <= TOL and abs(rel[k]["erro_lon"]) <= TOL]
    rel["PORTAO"] = dict(sistemas_finos=finos, dentro_de_0_5_grau=ok, PASSA=len(ok) >= 2,
                         incerteza_declarada=max(max(abs(rel[k]["erro_lat"]), abs(rel[k]["erro_lon"])) for k in finos))
    atual = json.loads(SAIDA.read_text()) if SAIDA.exists() else {}
    atual["validacao"] = rel
    SAIDA.write_text(json.dumps(atual, indent=1, default=float))
    print(json.dumps(rel["PORTAO"], indent=1, default=float))


def brpvgen():
    atual = json.loads(SAIDA.read_text()) if SAIDA.exists() else {}
    meta = pd.read_csv(BR / "BR-PVGen_metadata.csv").set_index("id")
    linhas = []
    with zipfile.ZipFile(BR / "BR-PVGen_meteorological.zip") as z:
        for nome in sorted(n for n in z.namelist() if n.endswith(".csv")):
            ps = Path(nome).stem
            with z.open(nome) as fh:
                m = pd.read_csv(fh, usecols=["datetime", "ghi_irradiance_wm2"])
            t = pd.to_datetime(m.datetime, utc=True).dt.tz_localize(None)
            s = pd.Series(pd.to_numeric(m.ghi_irradiance_wm2, errors="coerce").to_numpy(), index=t).sort_index()
            s = s[~s.index.duplicated()]
            # dias "locais" aproximados: UTC-3 (todo o Brasil das usinas fica entre UTC-3 e UTC-4)
            loc = pd.Series(s.to_numpy(), index=s.index - pd.Timedelta(hours=3))
            try:
                tt, v, dia, n = prepara(loc, -3, 0.0)
                p, e = ajusta(tt, v, dia, plano=False)
            except Exception as ex:  # serie curta ou vazia
                linhas.append(dict(id=ps, erro=str(ex)[:120]))
                continue
            uf = meta.loc[ps, "brazil_federative_unit"] if ps in meta.index else "?"
            cx = ESTADOS.get(uf)
            dentro = bool(cx and cx[0] <= p[0] <= cx[1] and cx[2] <= p[1] <= cx[3])
            linhas.append(dict(id=ps, uf=uf, estrutura=meta.loc[ps, "structure_type"] if ps in meta.index else "?",
                               lat=round(p[0], 3), lon=round(p[1], 3), mse=e, dias_claros=n, dentro_do_estado=dentro))
            print(linhas[-1], flush=True)
    T = pd.DataFrame(linhas)
    T.to_csv(PILOTOS / "c9_posicao_brpvgen.csv", index=False)
    atual["brpvgen"] = dict(n=len(T), dentro_do_estado=int(T.get("dentro_do_estado", pd.Series(dtype=bool)).sum()),
                            validacao_passou=atual.get("validacao", {}).get("PORTAO", {}).get("PASSA"))
    SAIDA.write_text(json.dumps(atual, indent=1, default=float))


if __name__ == "__main__":
    {"valida": valida, "brpvgen": brpvgen}[sys.argv[1]]()
