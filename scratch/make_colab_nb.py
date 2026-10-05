import json
import os

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# ⚡ VibraDistill-Edge: Cloud GPU Training & Decoupled Distillation Pipeline\n",
    "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zok213/VIbraDistill/blob/master/notebooks/VibraDistill_Colab_GPU.ipynb)\n",
    "\n",
    "> **Project:** VibraDistill-Edge (Cuộc thi Thiết kế FPGA và MCU Mở rộng Khu vực Miền Trung 2026)\n",
    "> **Target Hardware:** Gowin Primer 20K FPGA (12-way INT8 NPU) + Sonix SN32F407 MCU (ARM Cortex-M0)\n",
    "> **Objective:** Zero-Leakage Bearing Fault Diagnosis & Adaptive Conformal RUL Estimation via DKD and Physics-Informed Edge AI."
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
    "!pip install -r requirements.txt gdown"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. Verify Bit-True Causal Hardware DSP Pipeline"
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
    "## 4. Train Teacher 1D-ResNet Oracle (~1.0M parameters)\n",
    "Trains on CWRU `Train_7mil` across all 4 motor load conditions (0, 1, 2, 3 HP)."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --lr 0.001"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 5. Distill Teacher into VibraDistillMicro (8,677 parameters) via DKD & EDL\n",
    "Transfers inter-class semantic dark knowledge using Decoupled Knowledge Distillation ($\\tau=5.0, \\tau^2=25.0, \\alpha=1.0, \\beta=2.0$) and calibrates epistemic uncertainty with Dirichlet Evidential Deep Learning."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/03_train_student_dkd.py --epochs 35 --batch_size 64 --temperature 5.0 --alpha 1.0 --beta 2.0 --edl_weight 0.5"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 6. Comprehensive Zero-Leakage Benchmark Evaluation\n",
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
    "## 7. Post-Training Quantization (PTQ) & Hardware Silicon Export\n",
    "Folds BatchNorm into Conv1D weights and generates:\n",
    "- 6-bank BSRAM `.mi` files for Gowin Primer 20K FPGA\n",
    "- ANSI C header `vibradistill_weights.h` for Sonix SN32F407 MCU"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!python scripts/05_quantize_and_export.py"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 8. Export Checkpoints & ROMs to Google Drive"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "from google.colab import drive\n",
    "drive.mount('/content/drive')\n",
    "\n",
    "!mkdir -p /content/drive/MyDrive/VibraDistill_Artifacts\n",
    "!cp -r checkpoints /content/drive/MyDrive/VibraDistill_Artifacts/\n",
    "!cp -r embedded/fpga_gowin/roms /content/drive/MyDrive/VibraDistill_Artifacts/\n",
    "!cp embedded/mcu_sonix/app/vibradistill_weights.h /content/drive/MyDrive/VibraDistill_Artifacts/\n",
    "print(\"All trained artifacts and hardware ROMs successfully exported to Google Drive!\")"
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

os.makedirs('notebooks', exist_ok=True)
with open('notebooks/VibraDistill_Colab_GPU.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=1)
print("notebooks/VibraDistill_Colab_GPU.ipynb created successfully!")
