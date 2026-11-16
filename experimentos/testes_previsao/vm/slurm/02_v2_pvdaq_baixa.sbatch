#!/bin/bash
#SBATCH --job-name=02_v2_pvdaq_baixa
#SBATCH --partition=gpu_dev
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/10_piloto.sh" prosumer piloto_pvdaq.py baixa
