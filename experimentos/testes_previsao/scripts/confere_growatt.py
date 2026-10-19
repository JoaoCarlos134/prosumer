# -*- coding: utf-8 -*-
"""Conferencia (19/10/2026, SEM portao): o leitor de contadores da biblioteca no arquivo Growatt INTEIRO.

ORIGEM. Em 16/10 o `io.auto` lia o `E-Today (kWh)` de um export real da Growatt como energia de cada linha
(~1.000 kWh/dia de 3 kW). O conserto (contador detectado pelos valores, `meter.read_table(kind="cumulative")`)
tem teste de regressao com dois dias reais (`tests/fixtures/growatt_inverter_telemetry_2026-03-13_14.csv`). A
conta no arquivo inteiro foi feita a mao naquele dia (revisao independente de 17/10, F8: guardar como script).

ARQUIVO. `Inverter Telemetry.xlsx` do Kaggle "Residential Solar Power Generation Dataset"
(`anishth/solar-power-output`, CC BY 4.0): 3 kW em Salem, Tamil Nadu, India, Growatt, ~5 min. NAO fica no
repositorio (2 MB, baixado com conta do Kaggle); passe o caminho: `GROWATT_XLSX=... python confere_growatt.py`
ou como 1o argumento. Arquivo baixado = dado nao confiavel: rode com `python -I` e o caminho como argumento.

O QUE CONFERE (sem portao; os limiares do contador estao declarados em `io.auto` e `docs/library/tuning.md`):
- a energia diaria lida (mediana e maximo; 3 kW em Salem deve dar ~10-20 kWh/dia) e o maior valor horario;
- o contador contra a potencia CA integrada nas MESMAS horas: em cada par de leituras seguidas a no maximo 1,5
  passo, energia = media da potencia x intervalo, na hora da leitura anterior (como o leitor faz com o
  contador); por dia, a razao contador / CA nas horas validas das duas.
- as notas do leitor (reinicios, leituras fora da curva, pequenas quedas mantidas).

SAIDA: `resultados/pilotos/growatt_arquivo_inteiro.json` (agregados; nada da serie). Uso (ambiente da biblioteca):
    python -I confere_growatt.py "<caminho>/Inverter Telemetry.xlsx"
"""
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

from prosumer.io import auto

TZ = "Asia/Kolkata"
SAIDA = Path(__file__).resolve().parents[1] / "resultados" / "pilotos" / "growatt_arquivo_inteiro.json"


def ca_horaria(bruto: pd.DataFrame, passo: pd.Timedelta) -> pd.Series:
    """Energia CA (kWh) por hora, da potencia integrada entre leituras seguidas (trapezio), na hora da anterior."""
    b = bruto.sort_values("t")
    t = pd.DatetimeIndex(b["t"])
    p = b["AC Power (W)"].to_numpy(dtype=float)
    dt = (t[1:] - t[:-1]).total_seconds().to_numpy()  # nao `asi8`: a unidade (ns, us) muda com a versao
    ok = (dt > 0) & (dt <= 1.5 * passo.total_seconds())
    e = (p[1:] + p[:-1]) / 2 * dt / 3.6e6
    hora = t[:-1].floor("h")
    return pd.Series(e[ok], index=hora[ok]).groupby(level=0).sum()


def main(caminho: str) -> dict:
    t0 = time.time()
    s = auto.read_energy(caminho, tz=TZ, quantity="generation")
    f = s.frame
    lido = f.loc[f["valid"]].set_index("ds")["y"]
    lido.index = pd.DatetimeIndex(lido.index).tz_localize(None)  # horas locais, como o arquivo
    bruto = pd.read_excel(caminho, engine="openpyxl")
    bruto["t"] = pd.to_datetime(bruto["Timestamp"])
    passo = pd.Timedelta(minutes=5)
    ca = ca_horaria(bruto, passo)
    comum = lido.index.intersection(ca.index)
    j = pd.DataFrame({"contador": lido.loc[comum], "ca": ca.loc[comum]})
    dia = j.groupby(j.index.normalize()).sum()
    dia = dia[dia["ca"] > 0.5]  # dias com energia para a razao ter sentido
    razao = dia["contador"] / dia["ca"]
    diario = lido.groupby(lido.index.normalize()).sum()
    q = [0, 0.05, 0.25, 0.5, 0.75, 0.95, 1]
    return {
        "arquivo": Path(caminho).name,
        "notas_do_leitor": s.provenance.notes,
        "dias": int(diario.size),
        "kwh_dia": {"mediana": round(float(diario.median()), 2), "max": round(float(diario.max()), 2)},
        "kwh_hora_max": round(float(lido.max()), 3),
        "horas_comparadas": int(len(j)),
        "dias_comparados": int(razao.size),
        "razao_contador_ca_por_dia": {
            "quantis": dict(zip([str(x) for x in q], razao.quantile(q).round(4).tolist(), strict=True)),
            "dentro_de_5pct": f"{int(((razao - 1).abs() <= 0.05).sum())} de {razao.size}",
        },
        "razao_no_total": round(float(j["contador"].sum() / j["ca"].sum()), 4),
        "tempo_s": round(time.time() - t0, 1),
    }


if __name__ == "__main__":
    caminho = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GROWATT_XLSX", "")
    if not caminho:
        sys.exit("Passe o caminho do 'Inverter Telemetry.xlsx' (argumento ou GROWATT_XLSX)")
    r = main(caminho)
    SAIDA.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    print(json.dumps(r, indent=1, ensure_ascii=False))
