# -*- coding: utf-8 -*-
"""Moirai 2.0 (Salesforce), zero-shot, regime A. Roda no ambiente separado (.venvs/moirai),
porque o uni2ts exige versoes antigas de torch/pandas incompativeis com os outros modelos."""
import time, json
import numpy as np, torch
import truststore; truststore.inject_into_ssl()
from uni2ts.model.moirai2 import Moirai2Forecast, Moirai2Module
from comum import carrega, janelas, grava, CASOS, H, RES

torch.set_num_threads(10)
m = Moirai2Forecast(module=Moirai2Module.from_pretrained("Salesforce/moirai-2.0-R-small"), prediction_length=H,
                    context_length=1024, target_dim=1, feat_dynamic_real_dim=0, past_feat_dynamic_real_dim=0)
q = np.array(m.module.quantile_levels); i50 = int(np.argmin(np.abs(q - 0.5)))
LOG = RES / "tempos_fundacionais.json"
tempos = json.loads(LOG.read_text()) if LOG.exists() else {}
for caso in CASOS:
    t0 = time.time()
    jan = janelas(carrega(caso), caso)
    prev = []
    for i in range(0, len(jan), 128):
        out = m.predict([w["y"][:, None] for w in jan[i:i + 128]])
        prev += list(np.asarray(out)[:, i50, :H].reshape(-1, H))
    grava("Moirai-2.0-small", caso, "A", jan, prev)
    tempos[f"Moirai-2.0-small|{caso}|A"] = dict(segundos=round(time.time() - t0, 1), janelas=len(jan))
    print("OK    Moirai-2.0-small %-10s A  %5d janelas  %6.0f s" % (caso, len(jan), time.time() - t0), flush=True)
LOG.write_text(json.dumps(tempos, indent=1))
