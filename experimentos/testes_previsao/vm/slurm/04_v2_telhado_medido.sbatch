#!/bin/bash
#SBATCH --job-name=04_v2_telhado_medido
#SBATCH --partition=gpu_dev
#SBATCH --time=06:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/10_piloto.sh" prosumer piloto_telhado_medido.py
