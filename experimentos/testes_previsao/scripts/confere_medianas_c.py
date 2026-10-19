# -*- coding: utf-8 -*-
"""Conferencia (19/10/2026, SEM portao: so registra numeros): quanto vale a mediana das linhas de regime C
que o `analyze` pode formar, para cada composicao?

ORIGEM. O piloto de composicao (`piloto_composicao_biblioteca.py`, 16/10) mediu UMA composicao no regime C das
usinas, a das quatro linhas de previsao do tempo que a biblioteca tem (LightGBM, Chronos-2 e TiRex-2 com
covariaveis, e o linear fisico): +0,372, 1o de 24. A nota do `median_weather` no `analyze` dizia "1o de 24"
para qualquer composicao (revisao independente de 17/10, F4). Uma conta avulsa de 16/10 (registrada em
`docs/projeto/HISTORICO.md`) deu LightGBM + linear +0,346. Este script refaz essa conta e as outras composicoes
de duas ou mais linhas, para a nota citar so o que foi medido.

METODO: o do piloto de composicao (mesmas funcoes): mediana hora a hora das previsoes GRAVADAS, avaliadas como o
benchmark; posicao entre as linhas publicadas do teste usinas|C; DM contra o melhor (sem Holm). Limite declarado:
o `linear_fisico` do benchmark usa a irradiancia no plano dos modulos; o `weather_linear` do `analyze` usa o GHI
medio (aproximacao).

SAIDA: `resultados/pilotos/medianas_c.json`. Uso (ambiente da biblioteca, CPU, segundos):
    python confere_medianas_c.py
"""
import itertools
import json
import time

import comum
import piloto_composicao_biblioteca as P

LINHAS_C = ["LightGBM", "Chronos-2", "TiRex-2", "linear_fisico"]
SAIDA = comum.RES / "pilotos" / "medianas_c.json"

if __name__ == "__main__":
    t0 = time.time()
    composicoes = {
        "+".join(m): list(m) for k in range(2, len(LINHAS_C) + 1) for m in itertools.combinations(LINHAS_C, k)
    }
    composicoes |= {m: [m] for m in LINHAS_C}  # cada linha sozinha, para comparar
    r = P.teste("usinas", "C", composicoes)
    so = {m: r["composicoes"][m]["skill"] for m in LINHAS_C}
    for nome, membros in composicoes.items():
        if len(membros) > 1:
            x = r["composicoes"][nome]
            x["acima_de_cada_membro"] = x["skill"] > max(so[m] for m in membros)
    acima = [x["acima_de_cada_membro"] for x in r["composicoes"].values() if "acima_de_cada_membro" in x]
    SAIDA.write_text(json.dumps({"pergunta": "mediana das linhas de regime C por composicao (usinas|C)",
                                 "portao": "nenhum (conferencia)", "teste": r,
                                 "acima_de_cada_membro": f"{sum(acima)} de {len(acima)}",
                                 "tempo_s": round(time.time() - t0, 1)}, indent=1, ensure_ascii=False))
    print(f"melhor {r['melhor']} {r['skill_melhor']:+.3f}, Ensemble-mediana {r['skill_ensemble']:+.3f}")
    for nome, x in sorted(r["composicoes"].items(), key=lambda kv: -kv[1]["skill"]):
        acima_txt = {True: " acima de cada membro", False: " ABAIXO de um membro"}.get(
            x.get("acima_de_cada_membro"), "")
        print(f"  {nome:42s} {x['skill']:+.3f} ({x['posicao']}) p {x['dm_p_vs_melhor']:.3f}{acima_txt}")
    print(f"medianas acima de cada membro: {sum(acima)} de {len(acima)}")
