#!/bin/bash
#SBATCH --job-name=v0_ambientes
#SBATCH --partition=gpu_dev
#SBATCH --time=06:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/00_ambientes.sh" "$@"
