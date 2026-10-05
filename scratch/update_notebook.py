import json

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# ⚡ VibraDistill-Edge: Cloud GPU Training & Quantization Pipeline\n",
    "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zok213/VIbraDistill/blob/master/notebooks/VibraDistill_Colab_GPU.ipynb)\n",
    "\n",
    "> **Project:** VibraDistill-Edge (Cuộc thi Thiết kế FPGA và MCU Mở rộng Khu vực Miền Trung 2026)\n",
    "> **Target Hardware:** Gowin Primer 20K FPGA (12-way INT8 NPU @ 100 MHz) + Sonix SN32F407 MCU (ARM Cortex-M0 @ 60 MHz)\n",
    "> **Objective:** Zero-Leakage Bearing Fault Diagnosis & Adaptive Conformal RUL Estimation via DKD and Physics-Informed Edge AI.\n",
    "> **Memory Budget:** ≤ 10 KB INT8 weights (8,677 parameters)."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 1. Verify GPU Accelerator & Environment Setup\n",
    "Checks that a GPU (NVIDIA T4 / V100 / A100) is allocated."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!nvidia-smi\n",
    "import torch\n",
    "print(f\"PyTorch Version: {torch.__version__}\")\n",
    "print(f\"CUDA Available: {torch.cuda.is_available()}\")\n",
    "if torch.cuda.is_available():\n",
    "    print(f\"Device Name: {torch.cuda.get_device_name(0)}\")\n",
    "    print(f\"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 2. Clone Repository & Install Dependencies"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os\n",
    "if not os.path.exists('VIbraDistill'):\n",
    "    !git clone https://github.com/zok213/VIbraDistill.git\n",
    "    %cd VIbraDistill\n",
    "else:\n",
    "    %cd VIbraDistill\n",
    "    !git pull\n",
    "\n",
    "!pip install -r requirements.txt gdown colab_ssh"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. (Optional) Control Colab GPU directly from your Local PC via VS Code Remote-SSH\n",
    "If you want to control this Colab GPU directly from your local terminal or local VS Code with full terminal access, debugging, and live file editing, run this cell.\n",
    "It creates a secure Cloudflare tunnel and outputs the exact SSH command for your local PC."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# To enable Remote SSH from local VS Code, uncomment and run:\n",
    "# from colab_ssh import launch_ssh_cloudflared\n",
    "# launch_ssh_cloudflared(password=\"vibradistill2026\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 4. Verify Bit-True Causal Hardware DSP Pipeline"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/01_verify_dsp.py"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 5. Train Teacher 1D-ResNet Oracle (~150k parameters)\n",
    "Trains on CWRU `Train_7mil` across all 4 motor load conditions (0, 1, 2, 3 HP) on CUDA GPU."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --lr 0.001 --device cuda"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 6. Distill Teacher into VibraDistillMicro (8,677 parameters) via DKD & EDL\n",
    "Transfers inter-class semantic dark knowledge using Decoupled Knowledge Distillation ($\\tau=5.0, \\tau^2=25.0, \\alpha=1.0, \\beta=2.0$) and calibrates epistemic uncertainty with Dirichlet Evidential Deep Learning."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/03_train_student_dkd.py --epochs 35 --batch_size 64 --temperature 5.0 --alpha 1.0 --beta 2.0 --edl_weight 0.5 --device cuda"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 7. Strict Zero-Leakage Benchmark Evaluation\n",
    "Evaluates on physically unseen bearing fault datasets (`14mil` holdout and `21mil` holdout)."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/04_evaluate_zero_leakage.py"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 8. Quantization-Aware Training (QAT) with Straight-Through Estimators (STE)\n",
    "Fine-tunes the folded student network with simulated INT8 clipping and rounding to completely eliminate quantization collapse on edge hardware."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/08_qat_train.py --device cuda --epochs 15 --batch_size 64 --lr 0.0005"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 9. Verify 100% Bit-True Parity on Gowin NPU 12-Way Hardware Emulator\n",
    "Runs the integer silicon emulator on all test splits and confirms exact agreement."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/07_verify_int8_parity.py --checkpoint checkpoints/student_qat/best_qat.pt"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 10. Post-Training Quantization (PTQ) & Hardware Silicon Export\n",
    "Generates:\n",
    "- 6-bank BSRAM `.mi` hex ROM files for Gowin Primer 20K FPGA\n",
    "- ANSI C header `vibradistill_weights.h` and model headers for Sonix SN32F407 MCU"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/05_quantize_and_export.py --checkpoint checkpoints/student_qat/best_qat.pt"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 11. Multi-Model Baseline Benchmark\n",
    "Compares VibraDistillMicro against SingleKernelCNN, GRU, BiLSTM, and MLP baselines under identical training budgets."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/100_runs_ablation_benchmark.py --num_runs 5 --device cuda"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 12. Export Checkpoints, Evaluation Logs & Hardware ROMs to Google Drive"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from google.colab import drive\n",
    "drive.mount('/content/drive')\n",
    "\n",
    "!mkdir -p /content/drive/MyDrive/VibraDistill_Artifacts\n",
    "!cp -r checkpoints /content/drive/MyDrive/VibraDistill_Artifacts/\n",
    "!cp -r experiments /content/drive/MyDrive/VibraDistill_Artifacts/\n",
    "!cp -r embedded/fpga_gowin/roms /content/drive/MyDrive/VibraDistill_Artifacts/\n",
    "!cp embedded/mcu_sonix/app/vibradistill_weights.h /content/drive/MyDrive/VibraDistill_Artifacts/\n",
    "print(\"All trained artifacts, JSON benchmark logs, and hardware ROMs successfully exported to Google Drive!\")"
   ]
  }
 ],
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
    json.dump(notebook, f, indent=1, ensure_ascii=False)
print("Updated notebooks/VibraDistill_Colab_GPU.ipynb successfully!")
