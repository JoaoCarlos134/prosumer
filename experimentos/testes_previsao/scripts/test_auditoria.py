# -*- coding: utf-8 -*-
"""Regressoes do protocolo: corte temporal, suporte pareado e filas com falhas.

Executar: python -m unittest discover -s scripts -p test_auditoria.py
Nao treina modelos, nao baixa pesos e nao altera resultados.
"""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from comum import normaliza_por_treino


def carrega_modulo(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, Path(__file__).with_name(arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


avalia = carrega_modulo("avalia", "05_avalia.py")


class ProtocoloTest(unittest.TestCase):
    def test_futuro_nao_muda_escala_ou_treino(self):
        datas = pd.date_range("2020-01-01", periods=8, freq="h")
        df = pd.DataFrame({"unique_id": ["a"] * 8, "ds": datas,
                           "y": np.arange(8, dtype=float), "clima": np.arange(8, dtype=float) * 3,
                           "available_mask": 1.0})
        corte = datas[4]
        alterado = df.copy()
        alterado.loc[alterado.ds >= corte, ["y", "clima"]] = 1e9
        a, ea = normaliza_por_treino(df, corte, ["y", "clima"])
        b, eb = normaliza_por_treino(alterado, corte, ["y", "clima"])
        self.assertEqual(ea, eb)
        pd.testing.assert_frame_equal(a[a.ds < corte], b[b.ds < corte])
        self.assertEqual(ea["a"]["y"][0], 1.5)
        np.testing.assert_allclose(a.y * ea["a"]["y"][1] + ea["a"]["y"][0], df.y)

    def test_escala_exclui_alvos_invalidos_e_trata_constante(self):
        df = pd.DataFrame({"unique_id": ["a"] * 3, "ds": pd.date_range("2020-01-01", periods=3, freq="h"),
                           "y": [2.0, 2.0, 1e9], "available_mask": [1.0, 1.0, 0.0]})
        normalizado, escalas = normaliza_por_treino(df, pd.Timestamp("2020-01-02"), ["y"])
        self.assertEqual(escalas["a"]["y"], (2.0, 1.0))
        np.testing.assert_array_equal(normalizado.y[:2], [0, 0])

    def test_metricas_usam_mesmas_horas_finitas(self):
        base = pd.DataFrame({"unique_id": ["a"] * 5, "ds": pd.date_range("2020-01-01", periods=5, freq="h"),
                             "y": [1.0, 2.0, 3.0, 4.0, np.nan]})
        p = base.drop(columns="y").assign(yhat=[1.0, 1e8, np.nan, 8.0, 1.0])
        ref = base.drop(columns="y").assign(yhat=[2.0, np.nan, 2.0, 6.0, 1.0])
        m, r = avalia.alinha_previsoes(p, base, ref)
        self.assertEqual(len(m), 2)
        pd.testing.assert_series_equal(m.ds, r.ds)
        self.assertTrue(np.isfinite(m[["y", "yhat"]]).all().all())
        self.assertTrue(np.isfinite(r[["y", "yhat"]]).all().all())
        self.assertAlmostEqual(avalia.metricas(m)["RMSE"], np.sqrt(8))

    def test_chaves_duplicadas_falham(self):
        base = pd.DataFrame({"unique_id": ["a"], "ds": [pd.Timestamp("2020-01-01")], "y": [1.0]})
        p = base.drop(columns="y").assign(yhat=1.0)
        with self.assertRaises(pd.errors.MergeError):
            avalia.alinha_previsoes(pd.concat([p, p]), base, p)


if __name__ == "__main__":
    unittest.main()
