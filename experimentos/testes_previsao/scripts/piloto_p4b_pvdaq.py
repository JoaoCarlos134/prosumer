"""P4-b (25/11/2026): a conversao tempo -> kWh em sistemas do PVDAQ com posicao, plano e POA medida.

Portao em docs/projeto/PILOTOS_F1_F2.md, "P4-b" (commitado antes de rodar). Sistemas 34, 50, 1239 e 1433 (os do piloto
de 17/10 com POA, temperatura do ar e do modulo medidas), nos periodos daquele piloto, lidos do cache (os arquivos
diarios ja baixados por `piloto_pvdaq.py baixa`; o GHI da NASA POWER tambem).

Leitura (declarada antes): `measured_on` localizado no fuso da lista de sistemas (`io.pvdaq.zone`; horas que nao
existem ou se repetem na troca de horario de verao saem), passado a UTC; o carimbo marca o INICIO do passo (o
metadata nao diz: `time_interval` vazio), entao cada amostra e deslocada para o centro do passo antes da media
horaria. Hora valida = todas as amostras esperadas do passo presentes com potencia e POA; so horas com cos zenite
> 0,1 no centro da hora. Temperaturas `*_f` em Fahrenheit sao convertidas; modulo = media das colunas `module_temp*`.
  (a) 34 e 50: GHI horario da NASA -> POA no plano do metadata. Isotropica da biblioteca (`physics.poa_isotropic`,
      sol medio da hora) x Hay-Davies x Perez x isotropica do pvlib (Erbs para separar, sol no centro da hora,
      extraterrestre e massa de ar do pvlib, albedo 0,2 como a biblioteca). RMSE da POA horaria no periodo todo.
  (b) os 4: P = k POA x P = k POA (1 + g (Tc - 25)), g = -0,004/K, Tc = Tar + 0,03 POA (Ross). k na primeira metade
      dos dias (minimos quadrados), sem as horas com P >= 0,98 do maximo horario do sistema; RMSE na segunda metade,
      SEM essas horas tambem (o limite do inversor nao e efeito da temperatura). Diagnosticos: Tc = modulo medido;
      g ajustado junto com k.

Uso (ambiente p4 = biblioteca + pvlib): python piloto_p4b_pvdaq.py  -> resultados/pilotos/p4b_pvdaq.json
"""

import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

sys.path.insert(0, str(Path(__file__).parent))
from piloto_comum import PILOTOS  # noqa: E402

from prosumer import physics  # noqa: E402
from prosumer.io import pvdaq  # noqa: E402

warnings.filterwarnings("ignore")
SAIDA = PILOTOS / "p4b_pvdaq.json"
CACHE = Path(os.environ.get("PROSUMER_DATA") or Path.home() / ".cache" / "prosumer") / "pvdaq"
SISTEMAS = {  # id: (inicio, fim, coluna da potencia AC) = os do piloto de 17/10
    34: ("2019-01-01", "2019-12-31", "ac_power_hw"),
    50: ("2022-02-01", "2023-01-31", "ac_power"),
    1239: ("2019-01-01", "2019-12-31", "ac_power_metered_kw"),
    1433: ("2017-01-01", "2017-12-31", "ac_power"),
}
TRANSPOSICAO = (34, 50)
GAMA, ROSS, ALBEDO, CORTE_INV = -0.004, 0.03, 0.2, 0.98


def _col(cols, prefixo):
    achou = [c for c in cols if c.split("__")[0] == prefixo]
    return achou[0] if achou else None


def le(sid):
    ini, fim, col_p = SISTEMAS[sid]
    lista = pvdaq.systems().set_index("system_id")
    tz = pvdaq.zone(lista.loc[sid, "timezone_or_utc_offset"])
    dias = pd.date_range(ini, fim, freq="D")
    partes = []
    for d in dias:
        f = CACHE / str(sid) / f"system_{sid}__date_{d:%Y_%m_%d}.csv"
        if f.exists():
            partes.append(pd.read_csv(f))
    x = pd.concat(partes, ignore_index=True)
    cols = list(x.columns)
    p = _col(cols, col_p)
    poa = next(c for c in cols if c.startswith("poa_irradiance"))
    amb = next(c for c in cols if c.startswith("ambient_temp"))
    mods = [c for c in cols if c.startswith("module_temp")]
    t = pd.to_datetime(x["measured_on"]).dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    f_ = lambda c: (x[c] - 32) * 5 / 9 if "_f__" in c else x[c]  # noqa: E731
    out = pd.DataFrame({"t": t, "P": x[p].astype(float), "POA": x[poa].astype(float), "Tar": f_(amb).astype(float),
                        "Tmod": pd.concat([f_(c) for c in mods], axis=1).mean(axis=1).astype(float)})
    out = out.dropna(subset=["t"]).sort_values("t").drop_duplicates("t")
    out["t"] = out["t"].dt.tz_convert("UTC")
    passo = out["t"].diff().median()
    out["hora"] = (out["t"] + passo / 2).dt.floor("h")
    ok = out["P"].notna() & out["POA"].notna()
    g = out[ok].groupby("hora")
    h = g[["P", "POA", "Tar", "Tmod"]].mean()
    h["n"] = g.size()
    h = h[h["n"] == round(pd.Timedelta("1h") / passo)]
    return h.drop(columns="n"), tz, passo


def sol(idx, meta):
    centro = idx + pd.Timedelta("30min")
    sp = pvlib.solarposition.get_solarposition(centro, meta["latitude"], meta["longitude"])
    return sp.set_index(idx)


def transposicao(sid, h, meta, tz):
    nasa = pd.read_parquet(CACHE / "nasa" / f"{sid}.parquet")
    ghi = nasa.set_index(nasa["ds"].dt.tz_convert("UTC"))["ghi"]
    d = h.join(ghi.rename("GHI"), how="inner").dropna(subset=["GHI", "POA"])
    sp = sol(d.index, meta)
    d = d[np.cos(np.radians(sp["apparent_zenith"])) > 0.1]
    sp = sp.loc[d.index]
    tilt, az = meta["tilt"], meta["azimuth"]
    poa = {"isotropica_biblioteca": physics.poa_isotropic(
        d["GHI"].to_numpy(), physics.mean_sun(pd.DatetimeIndex(d.index), meta["latitude"], meta["longitude"]),
        tilt, az, albedo=ALBEDO)}
    erbs = pvlib.irradiance.erbs(d["GHI"], sp["apparent_zenith"], d.index)
    extra = pvlib.irradiance.get_extra_radiation(d.index)
    am = pvlib.atmosphere.get_relative_airmass(sp["apparent_zenith"])
    for nome, modelo in [("isotropica_pvlib", "isotropic"), ("hay_davies", "haydavies"), ("perez", "perez")]:
        r = pvlib.irradiance.get_total_irradiance(tilt, az, sp["apparent_zenith"], sp["azimuth"], erbs["dni"],
                                                  d["GHI"], erbs["dhi"], dni_extra=extra, airmass=am,
                                                  albedo=ALBEDO, model=modelo)
        poa[nome] = r["poa_global"].fillna(0).to_numpy()
    y = d["POA"].to_numpy()
    rm = {k: float(np.sqrt(np.mean((v - y) ** 2))) for k, v in poa.items()}
    base = rm["isotropica_biblioteca"]
    return dict(horas=len(d), poa_media=float(y.mean()), rmse=rm,
                ganho_vs_isotropica_biblioteca={k: 1 - v / base for k, v in rm.items()},
                PERE_Z_5PCT=bool(rm["perez"] <= 0.95 * base))


def temperatura(h, meta):
    d = h.dropna(subset=["Tar"]).copy()
    sp = sol(d.index, meta)
    d = d[(np.cos(np.radians(sp["apparent_zenith"])) > 0.1) & (d["POA"] > 0)]
    d = d[d["P"] < CORTE_INV * h["P"].max()]
    dias = np.sort(d.index.normalize().unique())
    meio = dias[len(dias) // 2]
    aj, av = d[d.index < meio], d[d.index >= meio]

    def k_de(x, y):
        return float((x @ y) / (x @ x))

    def rmse(x, y, k):
        return float(np.sqrt(np.mean((y - k * x) ** 2)))

    res = {}
    for nome, tc in [("linear", None), ("ross_ar", "ross"), ("modulo_medido", "Tmod")]:
        def xs(q):
            if tc is None:
                return q["POA"].to_numpy()
            t = q["Tar"] + ROSS * q["POA"] if tc == "ross" else q["Tmod"]
            return (q["POA"] * (1 + GAMA * (t - 25))).to_numpy()
        k = k_de(xs(aj), aj["P"].to_numpy())
        res[nome] = rmse(xs(av), av["P"].to_numpy(), k)
    # g ajustado (diagnostico): P = k POA + c POA (Tc - 25), Tc de Ross
    A = np.c_[aj["POA"], aj["POA"] * (aj["Tar"] + ROSS * aj["POA"] - 25)]
    (k, c), *_ = np.linalg.lstsq(A, aj["P"].to_numpy(), rcond=None)
    B = np.c_[av["POA"], av["POA"] * (av["Tar"] + ROSS * av["POA"] - 25)]
    res["ross_g_ajustado"] = float(np.sqrt(np.mean((av["P"].to_numpy() - B @ np.array([k, c])) ** 2)))
    base = res["linear"]
    return dict(horas_ajuste=len(aj), horas_avaliacao=len(av), p_media_avaliacao=float(av["P"].mean()),
                rmse=res, ganho_vs_linear={k_: 1 - v / base for k_, v in res.items()}, g_ajustado=float(c / k),
                ROSS_2PCT=bool(res["ross_ar"] <= 0.98 * base))


def main():
    rel = {"portao": "docs/projeto/PILOTOS_F1_F2.md, P4-b", "gama": GAMA, "ross": ROSS, "albedo": ALBEDO}
    for sid in SISTEMAS:
        meta = pvdaq.site_of(pvdaq.metadata(sid))
        h, tz, passo = le(sid)
        r = dict(tz=tz, passo=str(passo), horas_validas=len(h), plano=[meta["tilt"], meta["azimuth"]])
        if sid in TRANSPOSICAO:
            r["a_transposicao"] = transposicao(sid, h, meta, tz)
        r["b_temperatura"] = temperatura(h, meta)
        rel[str(sid)] = r
        print(sid, json.dumps(r, default=float)[:900], flush=True)
    a = [rel[str(s)]["a_transposicao"]["PERE_Z_5PCT"] for s in TRANSPOSICAO]
    b = [rel[str(s)]["b_temperatura"]["ROSS_2PCT"] for s in SISTEMAS]
    rel["PORTAO"] = dict(a_perez=bool(all(a)), a_sistemas=a, b_ross=bool(sum(b) >= 3), b_sistemas=b)
    SAIDA.write_text(json.dumps(rel, indent=1, default=float), encoding="utf-8")
    print(json.dumps(rel["PORTAO"]))


if __name__ == "__main__":
    main()
