#!/bin/bash
# Fila do servidor de 18/11/2026: tudo que tem portao commitado em docs/projeto/PILOTOS_F1_F2.md ("Fila do servidor de
# 18/11/2026" e "C1"), em cadeia Slurm, para rodar SEM supervisao. Rodar UMA vez:  bash fila_18nov.sh
# Tres pistas para ficar perto de ~24 threads: GPU (um job de GPU por vez, na ordem G1..G7 da FILA.md), CPU-A e CPU-B
# (um job por vez cada); as avaliacoes sao jobs pequenos que esperam o que precisam. afterany: uma falha nao trava a pista
# (cada job registra a falha no STATUS.md). Os ids vao para ~/Projeto_IA/logs/fila_18nov.ids e para o STATUS.md.
set -u
PROJ=$HOME/Projeto_IA; REPO=$PROJ/prosumer; BENCH=$REPO/experimentos/testes_previsao
S=$BENCH/vm/slurm; V=$HOME/.venvs; LOGS=$PROJ/logs; IDS=$LOGS/fila_18nov.ids
[ -e "$IDS" ] && { echo "ja submetida ($IDS); apague o arquivo para submeter de novo"; exit 1; }
: > "$IDS"
ULT_GPU=""; ULT_A=""; ULT_B=""

# sub NOME PISTA PARTICAO TEMPO CPUS MEM GPU(0/1) DEPS EXPORTS COMANDO
sub() {
  local nome=$1 pista=$2 part=$3 tempo=$4 cpus=$5 mem=$6 gpu=$7 deps=$8 exp=$9; shift 9
  local dep="" ult=""
  case $pista in GPU) ult=$ULT_GPU;; A) ult=$ULT_A;; B) ult=$ULT_B;; esac
  [ -n "$ult" ] && deps="${deps:+$deps:}$ult"
  [ -n "$deps" ] && dep="--dependency=afterany:$deps"
  local g=""; [ "$gpu" = 1 ] && g="--gres=gpu:1"
  local id
  id=$(sbatch --parsable --job-name="$nome" --partition="$part" --time="$tempo" --cpus-per-task="$cpus" --mem="$mem" $g \
       $dep --output="$LOGS/%x-%j.out" --export="ALL${exp:+,$exp}" "$S/22_cmd.sh" "$*") || { echo "FALHOU sbatch $nome"; exit 1; }
  echo "$id $nome pista=$pista deps=${deps:-nenhuma} :: $*" | tee -a "$IDS"
  case $pista in GPU) ULT_GPU=$id;; A) ULT_A=$id;; B) ULT_B=$id;; esac
  ULTIMO=$id
}
PB=$V/prosumer/bin/python; PP=$V/previsao/bin/python; PG=$V/previsao_gpu/bin/python; PL=$V/lote2/bin/python
PH=$V/lote2_hf/bin/python; PM=$V/moirai/bin/python; PC=$V/classicos/bin/python; P4=$V/p4/bin/python
F_CPU="03_fundacionais.py Chronos-2 Chronos-Bolt-small TimesFM-2.5 TiRex TTM-r2 Toto FlowState VisionTS++"
copia() {  # copia previsoes e tempos da v2 para uma pasta de rodada (o 05 compara; os scripts pulam o que ja existe)
  echo "mkdir -p ../$1/previsoes && cp -n ../resultados/previsoes/*.parquet ../$1/previsoes/ && cp -n ../resultados/tempos_*.json ../$1/"
}

# ---------------------------------------------------------------- 0. tempo estendido (C1, termina o download)
sub c1_tempo A gpu_dev 06:00:00 2 8G 0 "" "" "$PB 01b_estende_usinas.py --so-tempo"; C1=$ULTIMO
ULT_B=$C1; ULT_GPU=$C1

# ---------------------------------------------------------------- pista GPU (ordem da FILA.md)
X=DISPOSITIVO=cuda
sub g1_chronos GPU gpu_dev 12:00:00 6 40G 1 "" "$X" "$PP piloto_p1_gpu.py prever Chronos-2"; G1C=$ULTIMO
sub g1_tabpfn GPU gpu_train 2-00:00:00 6 40G 1 "" "$X" "$PL piloto_p1_gpu.py prever TabPFN-TS"; G1T=$ULTIMO
sub g2_v5_redes GPU gpu_train 2-00:00:00 6 20G 1 "" "$X,BENCH_C6=1,BENCH_SAIDA=resultados_v5" \
    "$(copia resultados_v5) && $PP 04_redes_treinadas.py usinas --regimes C6"; G2=$ULTIMO
sub g3_v7 GPU gpu_train 2-00:00:00 6 40G 1 "" "$X,BENCH_SAIDA=resultados_v7" "mkdir -p ../resultados_v7/previsoes && $PP piloto_v7_ajuste_fino.py"; G3=$ULTIMO
sub g4_v1_redes GPU gpu_train 2-00:00:00 6 20G 1 "" "$X,BENCH_TESTE=v1,BENCH_SAIDA=resultados_v1" "$PP 04_redes_treinadas.py usinas --regimes A,C"; G4=$ULTIMO
sub g5_v4_redes GPU gpu_train 2-00:00:00 6 20G 1 "" "$X,BENCH_TESTE=v4,BENCH_SAIDA=resultados_v4" "$PP 04_redes_treinadas.py casas_prod casas_cons --regimes A,B"; G5=$ULTIMO
G6=""
for s in 42 43 44; do
  sub g6_v3_redes_s$s GPU gpu_sim 7-00:00:00 6 20G 1 "" "$X,SEMENTE=$s,BENCH_SAIDA=resultados_v3_s$s" "$PP 04_redes_treinadas.py"
  G6="${G6:+$G6:}$ULTIMO"
done
sub g7_v9_llama GPU gpu_train 2-00:00:00 6 80G 1 "" "$X" "$PG piloto_timellm.py llama7b casas_cons"
sub g7_v9_llama_semllm GPU gpu_train 2-00:00:00 6 80G 1 "" "$X" "$PG piloto_timellm.py llama7b semLLM casas_cons"; G7=$ULTIMO

# ---------------------------------------------------------------- pista CPU-A: fisico do G1, V11-b, V1 e V4 (CPU)
for u in Cascavel Curitiba; do sub a_fisico_$u A gpu_dev 12:00:00 8 20G 0 "" "" "$PB piloto_p1_gpu.py fisico $u"; done; FIS=$ULTIMO
for u in Cascavel Curitiba; do sub a_v11b_$u A gpu_dev 12:00:00 8 20G 0 "" "" "$PB piloto_v11b.py replay $u"; done
sub a_v11b_avalia A gpu_dev 02:00:00 4 20G 0 "" "" "$PB piloto_v11b.py avalia"
for t in v1 v4; do
  E="BENCH_TESTE=$t,BENCH_SAIDA=resultados_$t"
  if [ $t = v1 ]; then C="usinas"; R="--regimes A,C,C-gfs"; RF="--casos usinas --regimes A,C"; else C="casas_prod casas_cons"; R=""; RF=""; fi
  sub a_${t}_ref A gpu_train 2-00:00:00 8 20G 0 "" "$E" "$PP 02_referencias.py $C $R"
  sub a_${t}_fund A gpu_train 2-00:00:00 8 20G 0 "" "$E" "$PP $F_CPU $RF"
  sub a_${t}_moirai A gpu_dev 12:00:00 8 20G 0 "" "$E" "$PM 03b_moirai.py"
  sub a_${t}_lote2 A gpu_train 2-00:00:00 8 20G 0 "" "$E" "$PL 03c_fundacionais_lote2.py Toto-2.0-22m Toto-2.0-313m TiRex-2 TabPFN-TS"
  sub a_${t}_lote2hf A gpu_train 2-00:00:00 8 20G 0 "" "$E" "$PH 03c_fundacionais_lote2.py Sundial-128m Timer-XL-84m Time-MoE-50M"
  sub a_${t}_moiraimoe A gpu_dev 12:00:00 8 20G 0 "" "$E" "$PM 03c_fundacionais_lote2.py Moirai-MoE-small"
  sub a_${t}_classicos A gpu_train 2-00:00:00 8 20G 0 "" "$E" "$PC 02b_classicos.py $C --modelos AutoETS,AutoTheta,MSTL"
  eval "A_$t=$ULTIMO"
done

# ---------------------------------------------------------------- pista CPU-B: P2, C9, P4, V5 (CPU), V3 base
sub b_p2_baixa B gpu_dev 12:00:00 2 8G 0 "" "" "$PB piloto_p2.py baixa"
for u in Cascavel Curitiba; do sub b_p2_$u B gpu_dev 12:00:00 8 20G 0 "" "" "$PB piloto_p2.py replay $u"; done
sub b_p2_avalia B gpu_dev 01:00:00 2 8G 0 "" "" "$PB piloto_p2.py avalia"
sub b_c9_valida B gpu_dev 12:00:00 8 20G 0 "" "" "$PB piloto_c9_posicao.py valida"
sub b_c9_brpvgen B gpu_dev 12:00:00 8 20G 0 "" "" "$PB piloto_c9_posicao.py brpvgen"
sub b_p4 B gpu_train 2-00:00:00 8 20G 0 "" "" "$P4 piloto_p4_conversao.py"
E5="BENCH_C6=1,BENCH_SAIDA=resultados_v5"
sub b_v5_ref B gpu_dev 12:00:00 8 20G 0 "" "$E5" "$(copia resultados_v5) && $PP 02_referencias.py usinas --regimes C6"
sub b_v5_fund B gpu_train 2-00:00:00 8 20G 0 "" "$E5" "$PP 03_fundacionais.py Chronos-2 TimesFM-2.5 --casos usinas --regimes C6"
sub b_v5_lote2 B gpu_train 2-00:00:00 8 20G 0 "" "$E5" "$PL 03c_fundacionais_lote2.py TiRex-2 TabPFN-TS"; B_V5=$ULTIMO
EB="BENCH_SAIDA=resultados_v3_base"
sub b_v3_ref B gpu_train 2-00:00:00 8 20G 0 "" "$EB" "$PP 02_referencias.py"
sub b_v3_classicos B gpu_train 2-00:00:00 8 20G 0 "" "$EB" "$PC 02b_classicos.py --modelos AutoETS,AutoTheta,MSTL"
sub b_v3_fund B gpu_sim 7-00:00:00 8 20G 0 "" "$EB" "$PP $F_CPU"
sub b_v3_moirai B gpu_train 2-00:00:00 8 20G 0 "" "$EB" "$PM 03b_moirai.py"
sub b_v3_lote2 B gpu_sim 7-00:00:00 8 20G 0 "" "$EB" "$PL 03c_fundacionais_lote2.py Toto-2.0-22m Toto-2.0-313m TiRex-2 TabPFN-TS"
sub b_v3_lote2hf B gpu_sim 7-00:00:00 8 20G 0 "" "$EB" "$PH 03c_fundacionais_lote2.py Sundial-128m Timer-XL-84m Time-MoE-50M"
sub b_v3_moiraimoe B gpu_train 2-00:00:00 8 20G 0 "" "$EB" "$PM 03c_fundacionais_lote2.py Moirai-MoE-small"; B_V3=$ULTIMO

# ---------------------------------------------------------------- avaliacoes (pequenas; esperam o que precisam)
ULT_A=""; ULT_B=""; ULT_GPU=""
sub e_g1 E gpu_dev 02:00:00 4 20G 0 "$FIS:$G1C:$G1T" "" "$PB piloto_p1_gpu.py avalia"
sub e_v5 E gpu_dev 04:00:00 4 20G 0 "$B_V5:$G2" "$E5" "$PP 07_ensemble.py && $PP 05_avalia.py && $PP confere_servidor.py v5"
sub e_v7 E gpu_dev 04:00:00 4 20G 0 "$G3" "BENCH_SAIDA=resultados_v7" "$PP 05_avalia.py && $PP confere_servidor.py v7"
sub e_v1 E gpu_dev 04:00:00 4 20G 0 "$A_v1:$G4" "BENCH_TESTE=v1,BENCH_SAIDA=resultados_v1" "$PP 07_ensemble.py && $PP 05_avalia.py && $PP confere_servidor.py v1"
sub e_v4 E gpu_dev 04:00:00 4 20G 0 "$A_v4:$G5" "BENCH_TESTE=v4,BENCH_SAIDA=resultados_v4" "$PP 07_ensemble.py && $PP 05_avalia.py && $PP confere_servidor.py v4"
EV3=""
for s in 42 43 44; do
  sub e_v3_s$s E gpu_dev 06:00:00 4 20G 0 "$B_V3:$G6" "BENCH_SAIDA=resultados_v3_s$s" \
      "cp -n ../resultados_v3_base/previsoes/*.parquet ../resultados_v3_s$s/previsoes/ && $PP 07_ensemble.py && $PP 05_avalia.py"
  EV3="${EV3:+$EV3:}$ULTIMO"
done
sub e_v3 E gpu_dev 01:00:00 2 8G 0 "$EV3" "" "$PP confere_servidor.py v3"
echo "submetidos: $(wc -l < "$IDS") jobs; lista em $IDS"
