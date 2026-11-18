"""C6 / P4 (servidor, 18/11/2026): a conversao tempo -> kWh, separada do erro do tempo, nas usinas FIXAS do BR-PVGen.

Portao em docs/projeto/PILOTOS_F1_F2.md, "P4" (commitado antes de rodar). BR-PVGen v2 (de Jesus, Ferreira, de Aguiar,
IEEE Access 14:161563, 2026; doi:10.1109/ACCESS.2026.3744444; CC BY 4.0): estacao com GHI, POA, temperatura do painel e
do ar, e potencia AC dos inversores, 15 min, UTC. So as 21 usinas de estrutura FIXED (todas bifaciais: o ganho
traseiro nao e modelado em nenhum braco, entao entra igual nos dois).
  Posicao: a do C9 se a validacao do C9 PASSOU e a estimativa cai dentro do estado; senao o centro da caixa do estado
  (declarado; mexe igual nos dois bracos de cada comparacao).
  Divisao no tempo: primeira metade dos dias = ajuste, segunda = avaliacao. So amostras com sol (cos zenite > 0,1).
  (a) Transposicao, GHI medido -> POA: isotropica da biblioteca (`physics.poa_isotropic`, Erbs) x Hay-Davies e Perez
      (pvlib, Erbs para separar). Plano (inclinacao 0-40 a cada 2, azimute a cada 10) ajustado POR MODELO na metade de
      ajuste contra a POA medida. Metrica: RMSE da POA na metade de avaliacao.
  (b) Temperatura, POA medida -> potencia: P = k POA x P = k POA (1 + gama (Tc - 25)), gama = -coeficiente do metadata
      (%/K), Tc = Tar + 0,03 POA (Ross; o que o app tem com a temperatura prevista) e, como diagnostico, Tc = painel medido.
      k por minimos quadrados na metade de ajuste, sem as amostras com P >= 0,98 do maximo (limitacao do inversor).
      Metrica: RMSE da potencia na metade de avaliacao.

Uso (ambiente p4 = biblioteca + pvlib): python piloto_p4_conversao.py
Saida: resultados/pilotos/p4_conversao.json (agregados por usina).
"""

import json
import sys
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

sys.path.insert(0, str(Path(__file__).parent))
from piloto_c9_posicao import BR, ESTADOS  # noqa: E402
from piloto_comum import PILOTOS  # noqa: E402

from prosumer import physics  # noqa: E402

warnings.filterwarnings("ignore")
SAIDA = PILOTOS / "p4_conversao.json"


def posicao(ps, uf):
    c9 = json.loads((PILOTOS / "c9_posicao.json").read_text()) if (PILOTOS / "c9_posicao.json").exists() else {}
    ok = c9.get("validacao", {}).get("PORTAO", {}).get("PASSA", False)
    f = PILOTOS / "c9_posicao_brpvgen.csv"
    if ok and f.exists():
        t = pd.read_csv(f).set_index("id")
        if ps in t.index and bool(t.loc[ps, "dentro_do_estado"]):
            return float(t.loc[ps, "lat"]), float(t.loc[ps, "lon"]), "C9"
    cx = ESTADOS[uf]
    return (cx[0] + cx[1]) / 2, (cx[2] + cx[3]) / 2, "centro_do_estado"


def le(z, pasta, ps, cols):
    with z.open(f"{pasta}/{ps}.csv") as fh:
        return pd.read_csv(fh, usecols=cols)


def rmse(a, b):
    return float(np.sqrt(np.nanmean((np.asarray(a) - np.asarray(b)) ** 2)))


def roda():
    meta = pd.read_csv(BR / "BR-PVGen_metadata.csv").set_index("id")
    fixas = meta[meta.structure_type == "FIXED"].index
    rel = {}
    zm = zipfile.ZipFile(BR / "BR-PVGen_meteorological.zip")
    zi = zipfile.ZipFile(BR / "BR-PVGen_inverter.zip")
    for ps in fixas:
        uf = meta.loc[ps, "brazil_federative_unit"]
        lat, lon, origem = posicao(ps, uf)
        m = le(zm, "BR-PVGen_meteorological", ps, ["datetime", "poa_irradiance_wm2", "ghi_irradiance_wm2",
                                                   "panel_temperature_celsius", "ambient_temperature_celsius"])
        m.index = pd.to_datetime(m.pop("datetime"), utc=True)
        inv = le(zi, "BR-PVGen_inverter", ps, ["datetime", "total_active_power_w"])
        p = inv.groupby(pd.to_datetime(inv.datetime, utc=True)).total_active_power_w.sum(min_count=1)
        d = m.join(p.rename("p"), how="inner").apply(pd.to_numeric, errors="coerce")
        d = d[~d.index.duplicated()].sort_index()
        sp = pvlib.solarposition.get_solarposition(d.index, lat, lon)
        d = d[np.cos(np.radians(sp.apparent_zenith)) > 0.1]
        sp = sp.loc[d.index]
        dias = d.index.normalize().unique()
        if len(dias) < 120:
            rel[ps] = dict(uf=uf, pulada=f"{len(dias)} dias")
            continue
        corte = dias[len(dias) // 2]
        aj, av = d.index < corte, d.index >= corte
        ghi, poa = d.ghi_irradiance_wm2.to_numpy(), d.poa_irradiance_wm2.to_numpy()
        # (a) transposicao
        # carimbo = instante (media movel ponderada): a media do sol nos 15 min centrados nele
        sun = physics.mean_sun(d.index - pd.Timedelta(minutes=7.5), lat, lon, interval="15min", samples=3)
        dni_dhi = pvlib.irradiance.erbs(ghi, sp.zenith, d.index)
        dni_extra = pvlib.irradiance.get_extra_radiation(d.index)

        def modelo(nome, tilt, az):
            if nome == "isotropica_biblioteca":
                return physics.poa_isotropic(ghi, sun, tilt, az)
            return pvlib.irradiance.get_total_irradiance(
                tilt, az, sp.apparent_zenith, sp.azimuth, dni_dhi["dni"], ghi, dni_dhi["dhi"], dni_extra=dni_extra,
                model="haydavies" if nome == "hay_davies" else "perez", albedo=0.2)["poa_global"].to_numpy()

        ok = np.isfinite(ghi) & np.isfinite(poa)
        res_a = {}
        for nome in ("isotropica_biblioteca", "hay_davies", "perez"):
            melhor = None
            for tilt in range(0, 41, 2):
                for az in (range(0, 360, 10) if tilt else [0]):
                    e = rmse(modelo(nome, tilt, az)[aj & ok], poa[aj & ok])
                    if melhor is None or e < melhor[0]:
                        melhor = (e, tilt, az)
            _, tilt, az = melhor
            res_a[nome] = dict(tilt=tilt, az=az, rmse_poa=rmse(modelo(nome, tilt, az)[av & ok], poa[av & ok]))
        # (b) temperatura
        gama = -float(meta.loc[ps, "panel_temperature_coefficient"]) / 100
        pw = d.p.to_numpy()
        ok = np.isfinite(pw) & np.isfinite(poa) & (pw >= 0)
        sem_corte = pw < 0.98 * np.nanmax(pw)
        tc_ross = d.ambient_temperature_celsius.to_numpy() + 0.03 * poa
        tc_med = d.panel_temperature_celsius.to_numpy()
        res_b = {}
        for nome, x in (("linear", poa), ("ross", poa * (1 + gama * (tc_ross - 25))),
                        ("painel_medido", poa * (1 + gama * (tc_med - 25)))):
            sel = aj & ok & sem_corte & np.isfinite(x)
            k = float(np.sum(x[sel] * pw[sel]) / np.sum(x[sel] ** 2))
            s2 = av & ok & sem_corte & np.isfinite(x)
            res_b[nome] = dict(k=k, rmse_p=rmse(k * x[s2], pw[s2]) / float(np.nanmean(pw[s2])))
        rel[ps] = dict(uf=uf, origem_posicao=origem, dias=len(dias), transposicao=res_a, temperatura=res_b,
                       ganho_perez=1 - res_a["perez"]["rmse_poa"] / res_a["isotropica_biblioteca"]["rmse_poa"],
                       ganho_hay=1 - res_a["hay_davies"]["rmse_poa"] / res_a["isotropica_biblioteca"]["rmse_poa"],
                       ganho_ross=1 - res_b["ross"]["rmse_p"] / res_b["linear"]["rmse_p"])
        print(ps, json.dumps({k: rel[ps][k] for k in ("ganho_perez", "ganho_hay", "ganho_ross")}, default=float), flush=True)
    usadas = [v for v in rel.values() if "ganho_perez" in v]
    n = len(usadas)
    rel["PORTAO"] = dict(n=n, perez_ganha=sum(v["ganho_perez"] >= 0.05 for v in usadas),
                         hay_ganha=sum(v["ganho_hay"] >= 0.05 for v in usadas),
                         ross_ganha=sum(v["ganho_ross"] >= 0.02 for v in usadas))
    rel["PORTAO"]["PASSA_transposicao"] = n > 0 and rel["PORTAO"]["perez_ganha"] >= 2 * n / 3
    rel["PORTAO"]["PASSA_temperatura"] = n > 0 and rel["PORTAO"]["ross_ganha"] >= 2 * n / 3
    SAIDA.write_text(json.dumps(rel, indent=1, default=float))
    print(json.dumps(rel["PORTAO"], indent=1))


if __name__ == "__main__":
    roda()
