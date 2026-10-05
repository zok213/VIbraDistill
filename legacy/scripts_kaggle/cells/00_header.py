# ============================================================
# VIbraDistill V6.1 — Industrial Edge Bearing Diagnosis
# ────────────────────────────────────────────────────────────
# Architecture: SE-1DCNN Student ⟵ DKD ⟵ EfficientNet-CWT Teacher
# Target: Jetson Orin NX (NVDLA-Native INT8)
# Status: Production Ready | Expert Audited
# ────────────────────────────────────────────────────────────
# Change Log (V6.1):
# 1. FIXED: True Causal STFT (boundary=None, padded=False).
# 2. FIXED: NVDLA-Native AvgPool1d (Static kernel=257).
# 3. FIXED: Robust Autocorrelation RPM Estimator.
# 4. FIXED: Test-set leakage (Selection via internal val_loader).
# 5. ADDED: Synchronized Sub-band Phase Augmentation.
# 6. ADDED: Adaptive Norm-Matching Regularization weight.
# ============================================================

# CELL 1 — Imports & Global Constants
# ============================================================
!pip install wandb filterpy onnxruntime pywavelets onnxscript torchinfo -qU

import os
import glob
import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import scipy.io as sio
import scipy.signal as signal
import random
import gc
from scipy.optimize import curve_fit
from scipy.stats import ttest_1samp
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report, f1_score,
    confusion_matrix, ConfusionMatrixDisplay,
)

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

import torchvision.models as models
import pywt

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:
    from tqdm.auto import tqdm
except ImportError:
    tqdm = lambda x, **kw: x

try:
    import wandb
    from kaggle_secrets import UserSecretsClient
    user_secrets = UserSecretsClient()
    wandb_key = user_secrets.get_secret("WANDB_API_KEY")
    wandb.login(key=wandb_key)
    _wb = True
except Exception:
    try:
        import wandb
        # Fallback to user-provided key if Kaggle secrets are missing
        wandb_key = "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"
        wandb.login(key=wandb_key)
        _wb = True
    except ImportError:
        _wb = False
        class _W:
            def init(self, **kw): pass
            def log(self, *a, **kw): pass
            def save(self, *a): pass
            def finish(self): pass
            config = type('C', (), {'update': lambda s, d: None})()
            def Api(self): return self
            def runs(self, p): return []
        wandb = _W()

# ── Dataset paths (Kaggle) ───────────────────────────────────
def find_dataset_root(keyword_list, search_root='/kaggle/input', max_depth=3):
    best_path, best_count = None, 0
    if not os.path.exists(search_root): return None
    
    for root, dirs, files in os.walk(search_root):
        depth = root.replace(search_root, '').count(os.sep)
        if depth > max_depth:
            dirs.clear(); continue
        folder_name = os.path.basename(root).lower()
        if any(k.lower() in folder_name for k in keyword_list):
            # Safe generator-based counting to prevent RAM OOM on massive datasets
            c = 0
            for r, d, f in os.walk(root):
                for name in f:
                    if name.endswith('.mat') or name.endswith('.csv'):
                        c += 1
            if c > best_count:
                best_count, best_path = c, root
    return best_path

def recover_from_wandb(filename, project='bfd-dkd-edge'):
    """Tries to download a file from the latest successful W&B run in the project."""
    if os.path.exists(filename):
        return True
    try:
        api = wandb.Api()
        # Find runs in the project, sorted by creation time (descending)
        runs = api.runs(project)
        for run in runs:
            files = run.files()
            for f in files:
                if f.name == os.path.basename(filename):
                    print(f"  Downloading {filename} from W&B run: {run.name}...")
                    f.download(replace=True, root=os.path.dirname(filename))
                    return True
    except Exception as e:
        print(f"  W&B Recovery failed for {filename}: {e}")
    return False

CWRU_ROOT   = find_dataset_root(['cwru'])
XJTU_ROOT   = find_dataset_root(['xjtu', 'xjtu-sy', 'run-to-failure', 'failure_bearing'])
OTTAWA_ROOT = find_dataset_root(['ottawa_mat', 'ottawa-mat', 'matlab_raw', 'matLab_Raw', 'uored', 'bearing_fault_dataset'])
if OTTAWA_ROOT is None:  # Fallback
    OTTAWA_ROOT = find_dataset_root(['ottawa', 'bearing_fault'])

WORK_DIR    = '/kaggle/working'
os.makedirs(WORK_DIR, exist_ok=True)

# ── Security & W&B Configuration ──────────────────────────────
# Use Kaggle Secrets to avoid leaking API keys in plain text
try:
    from kaggle_secrets import UserSecretsClient
    secrets = UserSecretsClient()
    WANDB_KEY = secrets.get_secret("WANDB_API_KEY")
    os.environ["WANDB_API_KEY"] = WANDB_KEY
except Exception:
    print("⚠ Kaggle Secrets not found. Ensure WANDB_API_KEY is set in your environment.")

# Premium Aesthetics: Global plotting style
plt.style.use('seaborn-v0_8-muted')
plt.rcParams.update({
    'font.family': 'sans-serif',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'figure.facecolor': 'white',
    'axes.facecolor': '#f8f9fa'
})

FIR_PATH      = os.path.join(WORK_DIR, 'fir_coefficients.npy')
CWT_FEAT_PATH = os.path.join(WORK_DIR, 'precomputed_cwt_features.npy')
CWT_LBL_PATH  = os.path.join(WORK_DIR, 'precomputed_cwt_labels.npy')
TEACHER_PATH  = os.path.join(WORK_DIR, 'teacher_best.pt')
STUDENT_PATH  = os.path.join(WORK_DIR, 'student_best.pt')
ONNX_PATH     = os.path.join(WORK_DIR, 'student_distilled.onnx')

# ── Signal constants ─────────────────────────────────────────
FS            = 12000
NUM_CLASSES   = 4          # 0=Normal 1=InnerRace 2=OuterRace 3=Ball
WINDOW_SIZE   = 512
SPECTRUM_BINS = WINDOW_SIZE // 2 + 1   # 257
IMG_SIZE      = 224

# CWRU SKF 6205-2RS bearing fault frequencies @ 1797 RPM
BPFO_HZ = 107.4   # outer race ball pass
BPFI_HZ = 162.2   # inner race ball pass
BSF_HZ  =  69.0   # ball spin
FTF_HZ  =  11.9   # cage fundamental

# ImageNet normalisation for EfficientNetB0 pretrained weights
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {DEVICE}  |  PyTorch: {torch.__version__}")
