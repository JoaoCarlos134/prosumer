#!/bin/bash
# V0 longo: paridade completa (PROSUMER_FULL=1), sem GPU. Nao bloqueia nada; o resultado vale para V1/V3.
#SBATCH --job-name=01b_v0_paridade
#SBATCH --partition=gpu_train
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=20G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
PYTEST_N=8 PARTES="paridade" RESULTADO=$HOME/Projeto_IA/logs/v0b_paridade.txt bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/01_v0_checagens.sh"
