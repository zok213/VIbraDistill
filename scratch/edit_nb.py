import json

def md_cell(text):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip().split("\n")]
    }

def code_cell(code):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in code.strip().split("\n")]
    }

cells = []

cells.append(md_cell("""# ⚡ VibraDistill-Edge: Cloud GPU Training & Quantization Pipeline
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zok213/VIbraDistill/blob/master/notebooks/VibraDistill_Colab_GPU.ipynb)

> **Project:** VibraDistill-Edge (Cuộc thi Thiết kế FPGA và MCU Mở rộng Khu vực Miền Trung 2026)
> **Target Hardware:** Gowin Primer 20K FPGA (12-way INT8 NPU @ 100 MHz) + Sonix SN32F407 MCU (ARM Cortex-M0 @ 60 MHz)
> **Objective:** Zero-Leakage Bearing Fault Diagnosis & Adaptive Conformal RUL Estimation via DKD and Physics-Informed Edge AI.
> **Memory Budget:** ≤ 10 KB INT8 weights (8,677 parameters)."""))

cells.append(md_cell("## 1. Verify GPU Accelerator & Environment Setup\nChecks that a GPU (NVIDIA T4 / V100 / A100) is allocated."))
cells.append(code_cell("""!nvidia-smi
import torch
print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")"""))

cells.append(md_cell("## 2. Clone Repository & Install Dependencies"))
cells.append(code_cell("""import os
if not os.path.exists('VIbraDistill'):
    !git clone https://github.com/zok213/VIbraDistill.git
    %cd VIbraDistill
else:
    %cd VIbraDistill
    !git pull

!pip install -r requirements.txt gdown colab_ssh"""))

cells.append(md_cell("## 3. (Optional) Control Colab GPU directly from your Local PC via VS Code Remote-SSH\nIf you want to control this Colab GPU directly from your local terminal or local VS Code with full terminal access, debugging, and live file editing, run this cell.\nIt creates a secure Cloudflare tunnel and outputs the exact SSH command for your local PC."))
cells.append(code_cell("""# To enable Remote SSH from local VS Code, uncomment and run:
# from colab_ssh import launch_ssh_cloudflared
# launch_ssh_cloudflared(password="vibradistill2026")"""))

cells.append(md_cell("## 4. Verify Bit-True Causal Hardware DSP Pipeline"))
cells.append(code_cell("!python scripts/01_verify_dsp.py"))

cells.append(md_cell("## 5. Train Teacher Oracle (1D-ResNet, ~150k params) on GPU\nTrains on CWRU `Train_7mil` across all 4 motor load conditions (0, 1, 2, 3 HP) on CUDA GPU."))
cells.append(code_cell("!python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --lr 0.001 --device cuda"))

cells.append(md_cell("## 6. Distill Teacher into VibraDistillMicro (8,677 params) via DKD & EDL\nTransfers inter-class semantic dark knowledge using Decoupled Knowledge Distillation ($\\tau=5.0, \\tau^2=25.0, \\alpha=1.0, \\beta=2.0$) and calibrates epistemic uncertainty with Dirichlet Evidential Deep Learning."))
cells.append(code_cell("!python scripts/03_train_student_dkd.py --epochs 35 --batch_size 64 --temperature 5.0 --alpha 1.0 --beta 2.0 --edl_weight 0.5 --device cuda"))

cells.append(md_cell("## 7. Strict Zero-Leakage Benchmark Evaluation\nEvaluates on physically unseen bearing fault datasets (`14mil` holdout and `21mil` holdout)."))
cells.append(code_cell("!python scripts/04_evaluate_zero_leakage.py"))

cells.append(md_cell("## 8. Quantization-Aware Training (QAT) with Straight-Through Estimators (STE)\nFine-tunes the folded student network with simulated INT8 clipping and rounding to completely eliminate quantization collapse on edge hardware."))
cells.append(code_cell("!python scripts/08_qat_train.py --device cuda --epochs 15 --batch_size 64 --lr 0.0005"))

cells.append(md_cell("## 9. Verify 100% Bit-True Parity on Gowin NPU 12-Way Hardware Emulator\nRuns the integer silicon emulator on all test splits and confirms exact agreement."))
cells.append(code_cell("!python scripts/07_verify_int8_parity.py --checkpoint checkpoints/student_qat/best_qat.pt"))

cells.append(md_cell("## 10. Post-Training Quantization (PTQ) & Hardware Silicon Export\nGenerates:\n- 6-bank BSRAM `.mi` hex ROM files for Gowin Primer 20K FPGA\n- ANSI C header `vibradistill_weights.h` and model headers for Sonix SN32F407 MCU"))
cells.append(code_cell("!python scripts/05_quantize_and_export.py --checkpoint checkpoints/student_qat/best_qat.pt"))

cells.append(md_cell("## 11. Multi-Model Baseline Benchmark\nCompares VibraDistillMicro against SingleKernelCNN, GRU, BiLSTM, and MLP baselines under identical training budgets."))
cells.append(code_cell("!python scripts/100_runs_ablation_benchmark.py --num_runs 5 --device cuda"))

cells.append(md_cell("## 12. Export Checkpoints, Evaluation Logs & Hardware ROMs to Google Drive"))
cells.append(code_cell("""from google.colab import drive
drive.mount('/content/drive')

!mkdir -p /content/drive/MyDrive/VibraDistill_Artifacts
!cp -r checkpoints /content/drive/MyDrive/VibraDistill_Artifacts/
!cp -r experiments /content/drive/MyDrive/VibraDistill_Artifacts/
!cp -r embedded/fpga_gowin/roms /content/drive/MyDrive/VibraDistill_Artifacts/
!cp embedded/mcu_sonix/app/vibradistill_weights.h /content/drive/MyDrive/VibraDistill_Artifacts/
print("All trained artifacts, JSON benchmark logs, and hardware ROMs successfully exported to Google Drive!")"""))

nb = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {
            "provenance": [],
            "gpuType": "T4"
        },
        "kernelspec": {
            "display_name": "Python 3",
            "name": "python3"
        },
        "language_info": {
            "name": "python"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 0
}

with open('notebooks/VibraDistill_Colab_GPU.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print(f"Successfully generated notebooks/VibraDistill_Colab_GPU.ipynb with {len(cells)} cells!")
