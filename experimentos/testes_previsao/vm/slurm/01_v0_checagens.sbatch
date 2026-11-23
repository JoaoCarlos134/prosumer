#!/bin/bash
#SBATCH --job-name=v0_checagens
#SBATCH --partition=gpu_dev
#SBATCH --gres=gpu:1
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --output=/home/%u/Projeto_IA/logs/%x-%j.out
PYTEST_N=4 bash "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/01_v0_checagens.sh"
