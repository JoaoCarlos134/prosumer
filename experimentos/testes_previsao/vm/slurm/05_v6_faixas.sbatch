#!/bin/bash
#SBATCH --job-name=05_v6_faixas
#SBATCH --partition=gpu_dev
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/10_piloto.sh" prosumer 05c_faixas.py
