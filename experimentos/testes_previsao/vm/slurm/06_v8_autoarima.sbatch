#!/bin/bash
#SBATCH --job-name=06_v8_autoarima
#SBATCH --partition=gpu_sim
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=64G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
export LIMITE_GB=$(awk "/MemAvailable/ {v=\$2/1048576-4; if (v>56) v=56; printf \"%d\", v}" /proc/meminfo)
echo "limite do vigia: $LIMITE_GB GB (RAM livre do no - 4, maximo 56)"
bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/10_piloto.sh" classicos piloto_autoarima_memoria.py serie=Cascavel regime=B
