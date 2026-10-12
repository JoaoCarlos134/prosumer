# -*- coding: utf-8 -*-
"""Piloto E4 (embarcado, redes): SparseTSF e CycleNet do benchmark exportados para C com `prosumer.embedded`.

Pergunta: as duas redes lineares do benchmark (SparseTSF, 32 parametros; CycleNet com backbone linear, ~4-7 mil)
rodam num ESP32 a partir das 168 h brutas do medidor (com buracos), dando a MESMA previsao que o Python?

O que faz, nos tres casos do regime A (casas_cons, casas_prod, usinas):
  gera   (ambiente ~/.venvs/previsao_gpu, torch, DISPOSITIVO=cpu): retreina as duas redes com
         `redes_proprias.treina_proprio` (mesmo laco, mesma semente 42, origem movel do benchmark, uma rede por
         dobra), confere (1) previsao retreinada x a gravada em resultados/previsoes/ (o SparseTSF do benchmark
         rodou em GPU, o CycleNet em CPU: diferenca do SparseTSF e esperada e e so relatada), (2) a rede em numpy
         da biblioteca (`from_torch`) x o torch nas janelas de teste. Grava os pesos de TODAS as dobras, as janelas
         (historico bruto com NaN nos buracos) e as previsoes do torch em resultados/pilotos/Emb-redes__<caso>.npz.
  avalia (ambiente da biblioteca, o .venv do repositorio, com ziglang e node): monta o cabecalho C de cada dobra
         (CycleNet: um por serie, `fix`), compila para WebAssembly e roda no Node (o Smart App Control bloqueia
         .exe locais) com o historico BRUTO; o C preenche os buracos (`causal_fill`), normaliza e preve. As
         previsoes do C viram Emb-<rede>__<caso>__A.parquet (skill com `piloto_comum.avalia_piloto`, que aplica a
         mascara de horas avaliadas do benchmark: na geracao, so as horas de producao).

PORTAO (fixado ANTES de rodar, neste commit; nao afrouxar depois de ver o resultado):
  (a) C == Python: em TODAS as horas de TODAS as janelas de teste (todas as dobras),
      |C - Py| <= 1e-5 * max(|Py|, max|historico valido da janela|) + 1e-7 kWh, com Py = a previsao do torch
      retreinado (cortada em zero, como o C), e o C em float32 a partir das 168 h brutas.
  (b) cabe no ESP32: flash <= 4 MB e RAM <= 320 KB (`embedded.footprint`, por cabecalho; CycleNet por serie).
  (c) skill do C (o que o dispositivo preve) >= skill da MESMA rede no metricas.csv - 0,02, OU empata com o
      melhor modelo do teste (Diebold-Mariano p >= 0,05 sem Holm, `avalia_piloto`, campo grupo_da_frente).
  Passa = (a) e (b) e (c). Leitura honesta de (c): a rede exportada e a mesma do benchmark, entao (c) so falha se
  o C ou o retreino em CPU mudarem a previsao; o que o piloto testa de fato e (a) e (b).

Uso:
    DISPOSITIVO=cpu ~/.venvs/previsao_gpu/Scripts/python.exe piloto_embarcado_redes.py gera <caso>
    .venv/Scripts/python.exe piloto_embarcado_redes.py avalia <caso>
Saidas: resultados/pilotos/Emb-redes__<caso>.npz, Emb-{SparseTSF,CycleNet}__<caso>__A.parquet,
embarcado_redes.json (uma entrada por caso) e entradas em resumo.json. CPU, minutos.
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("DISPOSITIVO", "cpu")      # antes do comum: o CycleNet do benchmark rodou em CPU
AQUI = Path(__file__).resolve().parent
RAIZ_REPO = AQUI.parents[2]
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ_REPO / "src"))

from comum import ENTRADA_NN, H, PREV, RES, carrega, dobras, tarefa  # noqa: E402
from prosumer import embedded as E  # noqa: E402

PILOTOS = RES / "pilotos"
REDES = ("SparseTSF", "CycleNet")
ESP32_FLASH, ESP32_RAM = 4 * 1024 * 1024, 320 * 1024
TOL_REL, TOL_ABS = 1e-5, 1e-7


def periodo(caso):
    """O mesmo do 04_redes_treinadas.PROPRIAS: ciclo de 168 h no consumo, 24 h na geracao."""
    return 168 if caso == "casas_cons" else 24


def arquivo(caso):
    return PILOTOS / f"Emb-redes__{caso}.npz"


def json_saida():
    return PILOTOS / "embarcado_redes.json"


def grava_json(caso, parte, dados):
    f = json_saida()
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo.setdefault(caso, {})[parte] = dados
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ gera (torch)
def gera(caso):
    import torch
    from redes_proprias import DEV, CycleNet, SparseTSF, treina_proprio
    assert DEV.type == "cpu", "rodar com DISPOSITIVO=cpu"
    # o 04_redes_treinadas fixa 5 threads; em CPU o numero de threads muda a ordem das somas e, com ela, o treino
    torch.set_num_threads(int(os.environ.get("THREADS_TORCH", "5")))
    t0 = time.time()
    d = carrega(caso)
    ids = {u: i for i, u in enumerate(sorted(d.unique_id.unique()))}     # a ordem do treina_proprio
    # historico BRUTO de cada janela de teste (NaN onde o protocolo marca buraco): o que o dispositivo teria
    bruto = {}
    for w in tarefa(d, caso, ENTRADA_NN).windows():
        assert len(w.history) == ENTRADA_NN
        bruto[(w.unique_id, w.day.tz_localize(None))] = np.where(w.history_valid, w.history, np.nan)
    fabs = {"SparseTSF": lambda n: SparseTSF(), "CycleNet": lambda n: CycleNet(n, periodo(caso))}
    saida, info = {}, {"torch": torch.__version__, "dispositivo": DEV.type, "periodo_cyclenet": periodo(caso)}
    for nome in REDES:
        t1 = time.time()
        uids, dias, dob, prev, hist = [], [], [], [], []
        dif_np = []
        for k, (ini, fim) in enumerate(dobras(caso)):
            caixa = []

            def fab(n, nome=nome, caixa=caixa):
                m = fabs[nome](n)
                caixa.append(m)
                return m

            jan, p, n_par = treina_proprio(d, caso, fab, ini, fim)
            m = caixa[-1]                                                    # pesos ja com o melhor estado
            for nm, t in m.state_dict().items():
                saida[f"{nome}|{k}|{nm}"] = t.detach().cpu().numpy()
            h = np.stack([bruto[(w["unique_id"], w["dia"])] for w in jan])
            p = np.stack(p).astype(float)
            # rede em numpy (biblioteca) x torch, nas mesmas janelas
            if nome == "SparseTSF":
                pn = E.SparseTSF.from_torch(m).predict(h)
            else:
                lib = E.CycleNet.from_torch(m)
                pn = lib.predict(h, [lib.day_phase(w["dia"]) for w in jan], [ids[w["unique_id"]] for w in jan])
            dif_np.append(float(np.max(np.abs(pn - p))))
            uids += [w["unique_id"] for w in jan]
            dias += [w["dia"] for w in jan]
            dob += [k] * len(jan)
            prev.append(p)
            hist.append(h)
        prev = np.concatenate(prev)
        saida[f"{nome}|prev"] = prev
        saida[f"{nome}|hist"] = np.concatenate(hist)
        saida[f"{nome}|uid"] = np.array(uids)
        saida[f"{nome}|dia"] = np.array(dias, dtype="datetime64[ns]")
        saida[f"{nome}|dobra"] = np.array(dob)
        # retreinada x gravada no benchmark
        ret = pd.DataFrame({"unique_id": np.repeat(uids, H),
                            "ds": np.concatenate([pd.date_range(x, periods=H, freq="h") for x in dias]),
                            "yhat": prev.ravel()})
        grav = pd.read_parquet(PREV / f"{nome}__{caso}__A.parquet")[["unique_id", "ds", "yhat"]]
        j = ret.merge(grav, on=["unique_id", "ds"], how="outer", suffixes=("", "_grav"), indicator=True)
        dd = (j.yhat - j.yhat_grav).abs()
        info[nome] = dict(
            parametros=int(n_par), segundos=round(time.time() - t1, 1), janelas=len(uids),
            max_dif_numpy_vs_torch=max(dif_np),
            retreinada_vs_gravada=dict(max_dif=float(dd.max()), media_dif=float(dd.mean()),
                                       horas_dif_maior_1e6=int((dd > 1e-6).sum()), horas=int(len(j)),
                                       so_num_lado=int((j._merge != "both").sum())))
        print(nome, caso, json.dumps(info[nome]), flush=True)
    saida["ids"] = np.array(sorted(ids, key=ids.get))
    np.savez_compressed(arquivo(caso), **saida)
    info["segundos"] = round(time.time() - t0, 1)
    grava_json(caso, "gera", info)
    print("gera %s: %.0f s" % (caso, time.time() - t0), flush=True)


# ------------------------------------------------------------------ avalia (biblioteca, C)
def modelo_da_dobra(z, nome, k):
    if nome == "SparseTSF":
        return E.SparseTSF(z[f"{nome}|{k}|conv.weight"].reshape(-1).astype(float),
                           z[f"{nome}|{k}|lin.weight"].astype(float))
    return E.CycleNet(z[f"{nome}|{k}|Q"].astype(float), z[f"{nome}|{k}|f.weight"].astype(float),
                      z[f"{nome}|{k}|f.bias"].astype(float))


def roda_c(cab, hist, dows):
    import wasm_c
    corpo = ('#include "net.h"\n'
             "void run(const float *in, long n, float *out) {\n"
             "    for (long i = 0; i < n / 169; i++)\n"
             "        net_forecast_day(in + 169 * i, (int)in[169 * i + 168], 0, 0.0f, out + 24 * i);\n}\n")
    ent = np.c_[hist, dows].astype(np.float32)
    return wasm_c.run(corpo, ent.ravel(), H * len(hist), headers={"net.h": cab}).reshape(len(hist), H)


def avalia(caso):
    sys.path.insert(0, str(RAIZ_REPO / "tests"))
    import test_benchmark_regression as T
    from piloto_comum import avalia_piloto, grava_piloto
    from piloto_embarcado import bytes_cortex_m4
    t0 = time.time()
    z = np.load(arquivo(caso))
    ids = {u: i for i, u in enumerate(z["ids"])}
    pub = T.PUBLISHED[(T.PUBLISHED.caso == caso) & (T.PUBLISHED.regime == "A")].set_index("modelo").skill
    rel = {}
    for nome in REDES:
        uid, dia, dob = z[f"{nome}|uid"], pd.DatetimeIndex(z[f"{nome}|dia"]), z[f"{nome}|dobra"]
        hist, py = z[f"{nome}|hist"], np.clip(z[f"{nome}|prev"], 0, None)
        dows = dia.dayofweek.to_numpy()
        c = np.full_like(py, np.nan)
        py32 = np.full_like(py, np.nan)
        fps, cab0 = [], None
        for k in np.unique(dob):
            m = modelo_da_dobra(z, nome, k)
            grupos = [(None, dob == k)] if nome == "SparseTSF" else \
                [(u, (dob == k) & (uid == u)) for u in np.unique(uid[dob == k])]
            for u, sel in grupos:
                mm = m if u is None else m.fix(ids[u])
                cab = E.to_c(mm, "net")
                cab0 = cab0 or cab
                c[sel] = roda_c(cab, hist[sel], dows[sel])
                py32[sel] = np.stack([mm.forecast_day(h, d0, dtype=np.float32) for h, d0 in zip(hist[sel], dia[sel])])
                fps.append(E.footprint(mm))
        escala = np.nanmax(np.abs(np.where(np.isnan(hist), 0.0, hist)), axis=1, keepdims=True)
        tol = TOL_REL * np.maximum(np.abs(py), escala) + TOL_ABS
        dif = np.abs(c - py)
        jan = [dict(unique_id=u, ds_fut=pd.date_range(d0, periods=H, freq="h")) for u, d0 in zip(uid, dia)]
        grava_piloto(f"Emb-{nome}", caso, "A", jan, c)
        r = avalia_piloto(f"Emb-{nome}", caso, "A")
        grava_piloto(f"Emb-{nome}-torch", caso, "A", jan, py)
        r_py = avalia_piloto(f"Emb-{nome}-torch", caso, "A")
        fp_flash, fp_ram = max(f.flash for f in fps), max(f.ram for f in fps)
        portao = dict(
            c_igual_python=bool((dif <= tol).all()),
            cabe_no_esp32=bool(fp_flash <= ESP32_FLASH and fp_ram <= ESP32_RAM),
            skill_ate_0_02_da_rede_do_benchmark=bool(r["skill"] >= float(pub[nome]) - 0.02),
            empata_com_o_melhor=bool(r["grupo_da_frente"]),
        )
        portao["passa"] = bool(portao["c_igual_python"] and portao["cabe_no_esp32"]
                               and (portao["skill_ate_0_02_da_rede_do_benchmark"] or portao["empata_com_o_melhor"]))
        rel[nome] = dict(
            skill_c=r["skill"], ic95=r["ic95"], R2=r["R2"], MBE=r["MBE"], posicao=r["posicao"],
            dm_p_vs_melhor=r["dm_p_vs_melhor"], melhor=r["melhor"], skill_melhor=r["skill_melhor"],
            skill_torch_retreinado=r_py["skill"], skill_benchmark=round(float(pub[nome]), 4),
            max_dif_c_vs_torch=float(dif.max()), max_razao_dif_tolerancia=float((dif / tol).max()),
            horas_fora_da_tolerancia=int((dif > tol).sum()), horas=int(dif.size),
            max_dif_c_vs_numpy_float32=float(np.abs(c - py32).max()),
            janelas_com_buraco=int(np.isnan(hist).any(axis=1).sum()), janelas=len(hist),
            cabecalhos=len(fps), flash_bytes=fp_flash, ram_bytes=fp_ram, cabecalho_bytes=len(cab0),
            cortex_m4=bytes_cortex_m4(cab0, "net"), portao=portao)
        print(nome, caso, json.dumps(rel[nome], ensure_ascii=False), flush=True)
    rel["segundos"] = round(time.time() - t0, 1)
    grava_json(caso, "avalia", rel)


if __name__ == "__main__":
    etapa, caso = sys.argv[1], sys.argv[2]
    {"gera": gera, "avalia": avalia}[etapa](caso)
