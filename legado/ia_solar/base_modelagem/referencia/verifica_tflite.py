# -*- coding: utf-8 -*-
###############################################################################
# VERIFICACAO DOS 32 MODELOS TFLITE A PARTIR DO ARQUIVO SALVO
#
# compara_modelos_embarcado.py criou os .tflite e mediu R2 e latencia em
# memoria, logo depois da conversao. Nenhum script tinha carregado o arquivo
# de volta. Aqui cada .tflite e lido do disco, roda amostra a amostra (como no
# dispositivo) sobre o mesmo teste (>= 2025-08-01) e o resultado e comparado
# com comparacao_embarcado.csv.
#
# O .tflite guarda so a rede. O pre-processamento (mediana para buracos,
# padronizacao das entradas) e a volta da saida para watts ficaram no Python
# e nunca foram salvos. Eles sao refeitos aqui, exatamente como no script
# original (mesmos dados, mesmo corte), e gravados em
# embarcado/preprocessamento_<usina>_<conjunto>.json: e o que um dispositivo
# precisa junto com o .tflite.
#
# Saidas: embarcado/verificacao_tflite.csv e os JSON de pre-processamento.
# Requisitos: pandas, numpy, scikit-learn, tensorflow (tf.lite.Interpreter)
###############################################################################

import json
import platform
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
import tensorflow as tf  # noqa: E402

pasta_projeto = Path(__file__).resolve().parents[2]
pasta = Path(__file__).resolve().parents[1] / 'embarcado'
USINAS = {
    'Cascavel': pasta_projeto / 'base_modelagem/cascavel/base_Cascavel_5min.parquet',
    'Curitiba': pasta_projeto / 'base_modelagem/curitiba/base_Curitiba_5min.parquet',
}
DATA_CORTE = '2025-08-01'
ALVO = 'potencia_ca_W'
# os mesmos conjuntos de compara_modelos_embarcado.py, na mesma ordem (a ordem e a das entradas da rede)
GEO = ['dia_do_ano', 'hora_solar', 'elevacao_solar', 'cos_zenite', 'poa_ceu_claro']
NASA_H = ['kc_horario', 'poa_estimada', 'ghi_horario', 'dni_horario', 'temp_ar_horaria', 'vento_horario']
NASA_D = ['kt_diario', 'ghi_diario', 'temp_ar_diaria', 'umidade_diaria', 'vento_diario', 'chuva_diaria',
          'nuvens_diaria', 'aerossol_diario']
SUJEIRA = ['estado_sujeira']
CONJUNTOS = {'COMPLETO': GEO + NASA_H + NASA_D + SUJEIRA, 'EMBARCADO': GEO + ['temp_ar_horaria'] + SUJEIRA}
N_LAT, REPETE = 2000, 5


def prepara(caminho, feats):
    d = pd.read_parquet(caminho).sort_values('data_hora')
    d = d.dropna(subset=CONJUNTOS['COMPLETO'] + [ALVO])
    corte = pd.Timestamp(DATA_CORTE)
    tr, te = d[d.data_hora < corte], d[d.data_hora >= corte]
    imp = SimpleImputer(strategy='median').fit(tr[feats])
    esc = StandardScaler().fit(imp.transform(tr[feats]))
    B = esc.transform(imp.transform(te[feats])).astype(np.float32)
    ytr = tr[ALVO].values
    pre = dict(entradas=feats, mediana_buracos=imp.statistics_.tolist(), media=esc.mean_.tolist(),
               desvio=esc.scale_.tolist(), saida_media_W=float(ytr.mean()), saida_desvio_W=float(ytr.std()),
               uso='x = (entrada, com buraco -> mediana, - media) / desvio; potencia_W = max(0, rede(x) * '
                   'saida_desvio_W + saida_media_W). Nos modelos int8 total, quantizar x e desquantizar a '
                   'saida com os parametros de quantizacao do proprio .tflite.')
    return B, te[ALVO].values, pre


def interpretador(arq):
    it = tf.lite.Interpreter(model_path=str(arq))
    it.allocate_tensors()
    ent, sai = it.get_input_details()[0], it.get_output_details()[0]

    def prever(x):
        if ent['dtype'] == np.int8:
            s, z = ent['quantization']
            x = np.clip(np.round(x / s + z), -128, 127).astype(np.int8)
        it.set_tensor(ent['index'], x.astype(ent['dtype']))
        it.invoke()
        o = it.get_tensor(sai['index'])
        if sai['dtype'] == np.int8:
            s, z = sai['quantization']
            o = (o.astype(np.float32) - z) * s
        return o
    return prever, ent, sai


def latencia_us(prever, B):
    """Mediana de REPETE medicoes; cada uma roda N_LAT amostras, uma por vez."""
    x = [B[i:i + 1] for i in range(min(N_LAT, len(B)))]
    for a in x[:50]:
        prever(a)                                    # aquecimento
    med = []
    for _ in range(REPETE):
        t0 = time.perf_counter()
        for a in x:
            prever(a)
        med.append(1e6 * (time.perf_counter() - t0) / len(x))
    return float(np.median(med))


if __name__ == '__main__':
    ref = pd.read_csv(pasta / 'comparacao_embarcado.csv', sep=';', decimal=',', encoding='utf-8-sig')
    ref = ref[ref.familia == 'tflite']
    linhas = []
    for usina, caminho in USINAS.items():
        for conj, feats in CONJUNTOS.items():
            B, yte, pre = prepara(caminho, feats)
            (pasta / f'preprocessamento_{usina}_{conj.lower()}.json').write_text(
                json.dumps(pre, indent=1, ensure_ascii=False), encoding='utf-8')
            for arq in sorted(pasta.glob(f'{usina}_{conj.lower()}_*.tflite')):
                _, _, rot, tipo = arq.stem.split('_', 3)
                prever, ent, sai = interpretador(arq)
                assert ent['shape'][-1] == len(feats), f'{arq.name}: rede espera {ent["shape"]}, conjunto tem {len(feats)}'
                p = np.array([prever(B[i:i + 1]).ravel()[0] for i in range(len(B))])
                p = np.clip(p * pre['saida_desvio_W'] + pre['saida_media_W'], 0, None)
                r2, mae = r2_score(yte, p), mean_absolute_error(yte, p)
                nome = {'float32': 'float32', 'float16': 'float16', 'int8dinamico': 'int8 dinamico',
                        'int8total': 'int8 total'}[tipo]
                rotulo = rot.replace('MLP', 'MLP ')
                o = ref[(ref.usina == usina) & (ref.conjunto == conj) & (ref.modelo == f'TFLite {rotulo} {nome}')]
                r2_ref = float(o.R2.iloc[0]) if len(o) else np.nan
                linhas.append(dict(usina=usina, conjunto=conj, rede=rotulo, conversao=nome, arquivo=arq.name,
                                   KB=round(arq.stat().st_size / 1024, 1), entrada=np.dtype(ent['dtype']).name,
                                   amostras_teste=len(yte), R2_recarregado=round(r2, 4), R2_original=r2_ref,
                                   diferenca_R2=round(r2 - r2_ref, 4), MAE_W=round(mae, 1),
                                   us_por_amostra=round(latencia_us(prever, B), 2),
                                   us_original=float(o.us_por_amostra.iloc[0]) if len(o) else np.nan))
                print('%-9s %-9s %-8s %-13s R2 %.4f (orig %.4f)  %6.2f us' % (
                    usina, conj, rotulo, nome, r2, r2_ref, linhas[-1]['us_por_amostra']), flush=True)
    R = pd.DataFrame(linhas)
    R['cpu'] = platform.processor()
    R.to_csv(pasta / 'verificacao_tflite.csv', index=False, sep=';', decimal=',', encoding='utf-8-sig')
    ok = (R.diferenca_R2.abs() <= 0.001).sum()
    print('\n%d de %d modelos reproduzem o R2 original (|dif| <= 0,001)' % (ok, len(R)))
