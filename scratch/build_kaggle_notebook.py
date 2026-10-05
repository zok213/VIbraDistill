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

cells.append(md_cell("""# ⚡ VibraDistill-Edge: Kaggle Dual NVIDIA Tesla T4 GPU Training & Quantization Pipeline
[![Open In Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](https://www.kaggle.com/code)

> **Hardware Target:** Gowin Primer 20K FPGA (12-way INT8 NPU @ 100 MHz) + Sonix SN32F407 MCU (ARM Cortex-M0 @ 60 MHz)
> **Kaggle Configuration:**
> - **Accelerator:** `GPU T4 x2` (30 GB total VRAM)
> - **Persistence:** `Variables and Files`
> - **Internet:** `On`
> **Primary Objective:** Zero-Leakage Bearing Fault Diagnosis with QAT and DKD under strict $\\le 10$ KB INT8 weight budget."""))

cells.append(md_cell("## 1. Verify Dual NVIDIA Tesla T4 GPU Allocation\nDetects both `cuda:0` and `cuda:1` devices."))
cells.append(code_cell("""!nvidia-smi
import torch

print(f"PyTorch Version: {torch.__version__}")
num_gpus = torch.cuda.device_count()
print(f"CUDA Available: {torch.cuda.is_available()} | GPU Count: {num_gpus}")

for i in range(num_gpus):
    props = torch.cuda.get_device_properties(i)
    print(f"  GPU [{i}]: {props.name} | VRAM: {props.total_memory / (1024**3):.2f} GB | Compute Cap: {props.major}.{props.minor}")

if num_gpus < 2:
    print("Notice: GPU T4 x2 is recommended in Kaggle Settings -> Accelerator -> GPU T4 x2.")"""))

cells.append(md_cell("## 2. Setup Codebase & Auto-Link Kaggle Input Datasets\nClones repository and maps any attached Kaggle datasets (`/kaggle/input/...`) to `data/`."))
cells.append(code_cell("""import os, sys, shutil

WORKSPACE_DIR = "/kaggle/working/VIbraDistill" if os.path.exists("/kaggle") else os.getcwd()

if os.path.exists("/kaggle"):
    if not os.path.exists(WORKSPACE_DIR):
        !git clone https://github.com/zok213/VIbraDistill.git {WORKSPACE_DIR}
        %cd {WORKSPACE_DIR}
    else:
        %cd {WORKSPACE_DIR}
        !git pull

!pip install -r requirements.txt gdown

# Link Kaggle Input Datasets if attached
KAGGLE_INPUT_DIR = "/kaggle/input"
os.makedirs("data", exist_ok=True)

DATASET_MAP = {
    "vibradistill-cwru-dataset": "CWRU_Dataset",
    "cwru": "CWRU_Dataset",
    "vibradistill-mfpt-dataset": "MFPT_Dataset",
    "vibradistill-seu-dataset": "SEU_Dataset",
    "vibradistill-phm2009-dataset": "PHM2009_Gearbox_Dataset",
    "vibradistill-rotating-machine-faults": "Rotating_Machine_Faults_Dataset",
    "vibradistill-xjtu-sy-dataset": "XJTU-SY_Dataset",
    "vibradistill-pronostia-femto-dataset": "PRONOSTIA_FEMTO_Dataset"
}

if os.path.exists(KAGGLE_INPUT_DIR):
    for k_name in os.listdir(KAGGLE_INPUT_DIR):
        k_lower = k_name.lower()
        for pattern, local_target in DATASET_MAP.items():
            if pattern in k_lower:
                src = os.path.join(KAGGLE_INPUT_DIR, k_name)
                sub = [os.path.join(src, f) for f in os.listdir(src) if os.path.isdir(os.path.join(src, f))]
                actual_src = sub[0] if (len(sub) == 1 and local_target.lower() in sub[0].lower()) else src
                dst = os.path.join("data", local_target)
                if not os.path.exists(dst):
                    try:
                        os.symlink(actual_src, dst)
                        print(f"Linked: {src} -> {dst}")
                    except Exception:
                        shutil.copytree(actual_src, dst)
                        print(f"Copied: {src} -> {dst}")

# Download CWRU fallback if not present
if not os.path.exists("data/CWRU_Dataset") or len(os.listdir("data/CWRU_Dataset")) < 5:
    print("CWRU dataset not found in /kaggle/input; downloading directly...")
    !python scripts/download_all_benchmarks.py --benchmark cwru"""))

cells.append(md_cell("## 3. Verify Bit-True Causal Hardware DSP Pipeline"))
cells.append(code_cell("!python scripts/01_verify_dsp.py"))

cells.append(md_cell("""## 4. Concurrent Dual-GPU Parallel Orchestrator
Leverages Kaggle Dual T4 GPUs simultaneously:
- **GPU 0 (`cuda:0`)**: Trains Teacher 1D-ResNet Oracle (~150k params)
- **GPU 1 (`cuda:1`)**: Concurrently runs Multi-Model Baseline Benchmark (`SingleKernelCNN`, `GRU`, `BiLSTM`, `MLP`)"""))
cells.append(code_cell("""import subprocess, time
from concurrent.futures import ThreadPoolExecutor

print("=" * 75)
print("LAUNCHING DUAL-GPU CONCURRENT WORKLOADS")
print("=" * 75)

def run_task(cmd, gpu_name):
    t0 = time.time()
    print(f"[{gpu_name} START] {cmd}")
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    dur = time.time() - t0
    if proc.returncode == 0:
        print(f"[{gpu_name} FINISHED] in {dur:.1f}s")
    else:
        print(f"[{gpu_name} FAILED] in {dur:.1f}s:\n{proc.stderr[:500]}")
    return proc.stdout

num_gpus = torch.cuda.device_count()
if num_gpus >= 2:
    with ThreadPoolExecutor(max_workers=2) as ex:
        f0 = ex.submit(run_task, "python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --device cuda:0", "GPU 0")
        f1 = ex.submit(run_task, "python scripts/100_runs_ablation_benchmark.py --num_runs 5 --device cuda:1", "GPU 1")
        print("Both GPU 0 and GPU 1 are active in parallel...")
        f0.result()
        f1.result()
else:
    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"Running sequentially on {dev}...")
    run_task(f"python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --device {dev}", "GPU 0")
    run_task(f"python scripts/100_runs_ablation_benchmark.py --num_runs 5 --device {dev}", "GPU 0")"""))

cells.append(md_cell("## 5. Decoupled Knowledge Distillation (DKD) & Evidential Learning into Student (`VibraDistillMicro`)\nTransfers semantic dark knowledge into the ultra-compact 8,677 parameter model."))
cells.append(code_cell("""dev = "cuda:0" if torch.cuda.is_available() else "cpu"
!python scripts/03_train_student_dkd.py --epochs 35 --batch_size 64 --temperature 5.0 --alpha 1.0 --beta 2.0 --edl_weight 0.5 --device {dev}"""))

cells.append(md_cell("## 6. Strict Zero-Leakage Benchmark Evaluation\nEvaluates generalization on physically unseen bearing fault datasets (`14mil` and `21mil`)."))
cells.append(code_cell("!python scripts/04_evaluate_zero_leakage.py"))

cells.append(md_cell("## 7. Quantization-Aware Training (QAT) with Straight-Through Estimators (STE)\nEliminates post-training quantization collapse on INT8 edge silicon."))
cells.append(code_cell("""dev = "cuda:0" if torch.cuda.is_available() else "cpu"
!python scripts/08_qat_train.py --device {dev} --epochs 15 --batch_size 64 --lr 0.0005"""))

cells.append(md_cell("## 8. Verify Bit-True INT8 Parity on Gowin NPU 12-Way Hardware Emulator\nConfirms exact decision agreement between float simulation and bit-true hardware emulator."))
cells.append(code_cell("!python scripts/07_verify_int8_parity.py --checkpoint checkpoints/student_qat/best_qat.pt"))

cells.append(md_cell("""## 9. Hardware Silicon Export
Generates:
- 6-Bank Gowin Primer 20K BSRAM `.mi` hex ROM files for 12-way NPU
- ANSI C headers `vibradistill_weights.h` and model headers for Sonix SN32F407 MCU"""))
cells.append(code_cell("!python scripts/05_quantize_and_export.py --checkpoint checkpoints/student_qat/best_qat.pt"))

cells.append(md_cell("## 10. Package Output Artifacts for Kaggle 1-Click Download\nCreates an all-in-one ZIP archive in `/kaggle/working/` containing checkpoints, ROM files, C headers, and benchmark JSON logs."))
cells.append(code_cell("""import zipfile

out_zip = "/kaggle/working/vibradistill_kaggle_artifacts.zip" if os.path.exists("/kaggle") else "vibradistill_kaggle_artifacts.zip"
print(f"Creating download archive: {out_zip}...")

with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
    for target in ['checkpoints', 'experiments', 'embedded/fpga_gowin/roms', 'embedded/mcu_sonix/app']:
        if os.path.exists(target):
            for root, _, files in os.walk(target):
                for f in files:
                    fp = os.path.join(root, f)
                    arc = os.path.relpath(fp, '.')
                    z.write(fp, arc)

size_mb = os.path.getsize(out_zip) / (1024 * 1024)
print(f"Successfully packaged {size_mb:.2f} MB!")
print("You can download this archive directly from the Kaggle Notebook Output tab on the right sidebar.")"""))

nb = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {
            "provenance": []
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

with open('notebooks/VibraDistill_Kaggle_Dual_T4.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Successfully created notebooks/VibraDistill_Kaggle_Dual_T4.ipynb with {len(cells)} cells!")
