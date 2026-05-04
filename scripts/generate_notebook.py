import json
import re
import os

vibra_dir = r"D:\Gitrepo\VIbraDistill"
notebook_path = os.path.join(vibra_dir, "kaggle", "notebook", "Master_Kaggle_Runner.ipynb")

def read_and_fix(path):
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()
    # Fix 1: Remove cross-script imports (they won't exist in notebook env)
    code = re.sub(r'^from Phase\w+ import.*\n', '', code, flags=re.MULTILINE)
    # Fix 2: Remove __main__ guard so code runs directly in notebook cells
    code = re.sub(r'if __name__\s*==\s*["\']__main__["\']:\n(    .+\n?)+', '', code)
    # Fix 3: Call the main() function or exposed functions directly
    return code

cells = []

# --- Cell 0: Title ---
cells.append({
    "cell_type": "markdown",
    "metadata": {},
    "source": ["# VIbraDistill: Master Training Pipeline (Dual T4)\n",
                "Full inline pipeline: DSP → SVM Baseline → Teacher CWT → DKD Student → Zero-Shot → RUL → INT8 Export"]
})

# --- Cell 0b: Bug 1 Fix — Smart Dataset Path Discovery ---
cells.append({
    "cell_type": "code",
    "execution_count": None, "metadata": {}, "outputs": [],
    "source": [
        "import os, glob\n",
        "\n",
        "# === STEP 0: DATASET PATH DISCOVERY ===\n",
        "# Run this cell first to identify exact Kaggle folder names.\n",
        "print('=== KAGGLE INPUT FOLDERS ===')\n",
        "if os.path.exists('/kaggle/input/'):\n",
        "    print(os.listdir('/kaggle/input/'))\n",
        "    input_dir = '/kaggle/input/'\n",
        "else:\n",
        "    print('Not running on Kaggle. Using local paths if available.')\n",
        "    input_dir = '.'\n",
        "\n",
        "cwru_candidates   = [d for d in os.listdir(input_dir) if any(k in d.lower() for k in ['cwru','bearing','case'])] if os.path.exists(input_dir) else []\n",
        "xjtu_candidates   = [d for d in os.listdir(input_dir) if any(k in d.lower() for k in ['xjtu','run-to', 'mpn45f4gxc'])] if os.path.exists(input_dir) else []\n",
        "ottawa_candidates = [d for d in os.listdir(input_dir) if any(k in d.lower() for k in ['ottawa','uored'])] if os.path.exists(input_dir) else []\n",
        "\n",
        "print(f'CWRU candidates:   {cwru_candidates}')\n",
        "print(f'XJTU candidates:   {xjtu_candidates}')\n",
        "print(f'Ottawa candidates: {ottawa_candidates}')\n",
        "\n",
        "CWRU_ROOT   = f'{input_dir}/{cwru_candidates[0]}'   if cwru_candidates   else None\n",
        "XJTU_ROOT   = f'{input_dir}/{xjtu_candidates[0]}'   if xjtu_candidates   else None\n",
        "OTTAWA_ROOT = f'{input_dir}/{ottawa_candidates[0]}' if ottawa_candidates else None\n",
        "\n",
        "for name, path in [('CWRU', CWRU_ROOT), ('XJTU-SY', XJTU_ROOT), ('Ottawa', OTTAWA_ROOT)]:\n",
        "    if path and os.path.exists(path):\n",
        "        files = glob.glob(os.path.join(path, '**', '*'), recursive=True)[:3]\n",
        "        print(f'\\u2713 {name}: {path} ({len(files)}+ files found)')\n",
        "    else:\n",
        "        print(f'\\u2717 {name}: NOT FOUND — please mount dataset')\n",
        "\n",
        "# Inject into environment for downstream scripts\n",
        "os.environ['CWRU_ROOT']   = CWRU_ROOT   or ''\n",
        "os.environ['XJTU_ROOT']   = XJTU_ROOT   or ''\n",
        "os.environ['OTTAWA_ROOT'] = OTTAWA_ROOT or ''\n",
    ]
})

# --- Cell 1: Environment Setup ---
cells.append({
    "cell_type": "code",
    "execution_count": None, "metadata": {}, "outputs": [],
    "source": [
        "!pip install wandb filterpy onnxruntime onnxscript -qU\n",
        "import os, sys, json\n",
        "import numpy as np\n",
        "import torch\n",
        "import torch.nn as nn\n",
        "import torch.nn.functional as F\n",
        "from torch.utils.data import Dataset, DataLoader\n",
        "from torchvision import models\n",
        "import scipy.signal, scipy.io\n",
        "from scipy.stats import kurtosis\n",
        "from scipy.optimize import curve_fit\n",
        "import wandb\n",
        "\n",
        "# --- W&B Login via Kaggle Secrets ---\n",
        "from kaggle_secrets import UserSecretsClient\n",
        "try:\n",
        "    WANDB_API_KEY = UserSecretsClient().get_secret('WANDB_KEY')\n",
        "    wandb.login(key=WANDB_API_KEY)\n",
        "except Exception:\n",
        "    print('Warning: WANDB_KEY secret not found. W&B logging may fail.')\n",
        "\n",
        "# --- Verify Dual T4 ---\n",
        "print(f'CUDA: {torch.cuda.is_available()} | GPUs: {torch.cuda.device_count()}')\n",
        "for i in range(torch.cuda.device_count()):\n",
        "    print(f'  GPU {i}: {torch.cuda.get_device_name(i)}')\n",
        "\n",
        "# --- Kaggle Dataset Discovery ---\n",
        "print('Mounted datasets in /kaggle/input/:')\n",
        "try:\n",
        "    print(os.listdir('/kaggle/input/'))\n",
        "except Exception as e:\n",
        "    print('Could not list /kaggle/input/:', e)\n",
        "\n",
        "# --- Mount CWRU Dataset (symlink from Kaggle input) ---\n",
        "if os.path.exists('/kaggle/input/cwru-bearing-dataset'):\n",
        "    os.system('ln -sf /kaggle/input/cwru-bearing-dataset ./CWRU_Dataset')\n",
        "    print('CWRU Dataset mounted from Kaggle input.')\n",
        "else:\n",
        "    print('Warning: CWRU dataset not found at /kaggle/input/cwru-bearing-dataset')\n",
        "print('Environment ready!')\n"
    ]
})

# --- Cells 2+: Inline Phase Scripts ---
scripts = [
    ("Phase 0: Python DSP (Fast Kurtogram + Causal FIR)", "Phase0_DSP_Design_Python.py", "main()"),
    ("Phase 1: PyTorch DataLoaders", "Phase1_DataLoaders.py", None),
    ("Phase 1a: SVM Baseline", "Phase1a_SVM_Baseline.py", None),
    ("Phase 1c: Teacher CWT Pre-Compute & Train", "Phase1c_Teacher_CWT_Train.py", "precompute_dataset(num_samples=500)\ntrain_teacher()"),
    ("Phase 1: DKD Student Training (Dual T4)", "Phase1_Kaggle_Training.py", "main()"),
    ("Phase 1b: Ottawa Zero-Shot Generalization", "Phase1b_Ottawa_ZeroShot.py", None),
    ("Phase 1 RUL: XJTU-SY Conformal Prognostics", "Phase1_XJTU_RUL.py", None),
]

for title, script, call in scripts:
    path = os.path.join(vibra_dir, script)
    if not os.path.exists(path):
        print(f"WARNING: {script} not found, skipping.")
        continue
    code = read_and_fix(path)
    # Add explicit function call if needed
    if call:
        code = code.rstrip() + f"\n\n# --- Execute ---\n{call}\n"

    cells.append({
        "cell_type": "markdown", "metadata": {},
        "source": [f"## {title}"]
    })
    cells.append({
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": [line + '\n' for line in code.split('\n')]
    })

# --- Final summary cell ---
cells.append({
    "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
    "source": [
        "print('=' * 60)\n",
        "print('CLOUD EXECUTION COMPLETE!')\n",
        "print('Download from /kaggle/working/:')\n",
        "print('  - student_distilled.onnx')\n",
        "print('  - five_seed_results.json')\n",
        "print('  - teacher_best.pt')\n",
        "print('Transfer these to Jetson Orin NX for Phase 3 Edge Profiling & trtexec calibration.')\n",
        "print('=' * 60)\n"
    ]
})

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.12"}
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=1)

print(f"Fixed notebook written to {notebook_path}")
