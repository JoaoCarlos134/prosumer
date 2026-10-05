# -*- coding: utf-8 -*-
"""Teste rapido da correcao do regime B (normalizacao global): GRU com 150 passos, resultado em arquivo."""
import importlib, json, logging, warnings
import numpy as np, torch
warnings.filterwarnings("ignore"); logging.disable(logging.CRITICAL)
torch.set_num_threads(3)
r = importlib.import_module("04_redes_treinadas")
from neuralforecast import NeuralForecast
from neuralforecast import models as M
from comum import carrega, EXOG, RES

d = carrega("usinas"); df = r.df_nf(d, "B")
C = {**r.COMUM, "futr_exog_list": EXOG, "scaler_type": "identity", "max_steps": 150}
nf = NeuralForecast(models=[M.GRU(**C)], freq="h", local_scaler_type="standard")
cv = nf.cross_validation(df=df, n_windows=304, step_size=24, val_size=720, refit=False)
p, y = cv["GRU"].to_numpy(), cv["y"].to_numpy()
out = dict(prev_max=float(p.max()), prev_p999=float(np.percentile(p, 99.9)), real_max=float(y.max()),
           rmse=float(np.sqrt(np.mean((p - y) ** 2))))
(RES / "teste_correcao_B.json").write_text(json.dumps(out, indent=1))
print(out)
