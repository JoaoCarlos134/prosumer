#!/bin/bash
# V0 curto: test_auditoria + GPU nos ambientes com torch. Libera a fila V2/V6/V8 (afterok).
#SBATCH --job-name=01a_v0_rapido
#SBATCH --partition=gpu_dev
#SBATCH --gres=gpu:1
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
PARTES="auditoria gpu" RESULTADO=$HOME/Projeto_IA/logs/v0a_resultado.txt bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/01_v0_checagens.sh"
