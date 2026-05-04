"""
PHASE 1C: TEACHER CWT GENERATION & TRAINING (KAGGLE DAY 1)
Fixes applied:
  1. scipy.signal.cwt removed in SciPy 1.12 -> replaced with pywt.cwt (Morlet wavelet)
  2. CWT output resized to 224x224 for EfficientNetB0 fixed input size
  3. pretrained=True deprecated -> use weights= API
  4. Real training loop using actual DataLoader batches
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models
import torch.nn.functional as F
import numpy as np
import pywt
import wandb
import os

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
NUM_CLASSES = 4
IMG_SIZE = 224  # EfficientNetB0 expects 224x224

# ── 1. CWT SCALOGRAM GENERATOR ────────────────────────────────────────────────

def generate_cwt_scalogram(signal_1d, fs=12000, n_scales=127):
    """
    Morlet CWT scalogram. pywt.cwt replaces removed scipy.signal.cwt.
    Output: (3, IMG_SIZE, IMG_SIZE) float32 ready for EfficientNetB0.
    """
    scales = np.arange(1, n_scales + 1)
    coeffs, _ = pywt.cwt(signal_1d, scales, 'morl', sampling_period=1.0 / fs)
    cwt_img = np.abs(coeffs).astype(np.float32)

    # Normalize 0-1
    c_max = cwt_img.max()
    if c_max > 0:
        cwt_img /= c_max

    # Resize to IMG_SIZE x IMG_SIZE using torch interpolate
    t = torch.tensor(cwt_img).unsqueeze(0).unsqueeze(0)  # (1,1,scales,time)
    t = F.interpolate(t, size=(IMG_SIZE, IMG_SIZE), mode='bilinear', align_corners=False)
    t = t.squeeze(0).repeat(3, 1, 1)  # (3, 224, 224)
    return t.numpy()


# ── 2. PRE-COMPUTE TO DISK ────────────────────────────────────────────────────

def precompute_dataset(num_samples=500, signal_len=512, fs=12000):
    """
    Pre-compute all CWT scalograms to disk BEFORE training.
    This prevents CPU bottleneck on Kaggle and keeps both T4s at 100%.
    """
    print("--- STEP 1: PRE-COMPUTING CWT SCALOGRAMS (CPU BOTTLENECK AVOIDANCE) ---")
    feat_path = '/kaggle/working/precomputed_cwt_features.npy'
    lbl_path  = '/kaggle/working/precomputed_cwt_labels.npy'

    if os.path.exists(feat_path):
        print("Cache already exists. Skipping pre-computation.")
        return

    all_cwts = []
    all_lbls = []
    
    print("Extracting actual signals from train_dl for CWT cache...")
    try:
        # train_dl is created in Phase 1
        for xb, yb in train_dl:
            for i in range(xb.shape[0]):
                sig = xb[i].numpy().flatten()
                all_cwts.append(generate_cwt_scalogram(sig, fs=12000))
                all_lbls.append(yb[i].item())
                if len(all_cwts) % 100 == 0:
                    print(f"  [{len(all_cwts)}] Computing scalogram...")
    except NameError:
        raise RuntimeError("CRITICAL: train_dl not found. Ensure dataloaders are initialized.")
        
    all_cwts = np.array(all_cwts, dtype=np.float32)
    labels = np.array(all_lbls, dtype=np.int64)
    np.save(feat_path, all_cwts)
    np.save(lbl_path, labels)
    print(f"Pre-computation done. Shape: {all_cwts.shape}")
    print(f"Saved: {feat_path}")


# ── 3. DATASET & DATALOADER ───────────────────────────────────────────────────

class CWTCacheDataset(Dataset):
    def __init__(self, feat_path, lbl_path):
        self.features = np.load(feat_path)   # (N, 3, 224, 224)
        self.labels   = np.load(lbl_path)    # (N,)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        x = torch.tensor(self.features[idx])                          # (3, 224, 224)
        y = torch.tensor(self.labels[idx], dtype=torch.long)
        return x, y


# ── 4. TEACHER TRAINING ───────────────────────────────────────────────────────

def train_teacher(epochs=30, batch_size=64, lr=1e-4):
    print("\n--- STEP 2: TEACHER PRETRAINING (EfficientNetB0 on CWT Scalograms) ---")

    feat_path = '/kaggle/working/precomputed_cwt_features.npy'
    lbl_path  = '/kaggle/working/precomputed_cwt_labels.npy'

    if not os.path.exists(feat_path):
        print("ERROR: Cache not found. Run precompute_dataset() first.")
        return

    dataset = CWTCacheDataset(feat_path, lbl_path)
    # Bug 7 Fix: Split 80/20 train/val — checkpoint on val_acc NOT training accuracy
    n_total = len(dataset)
    n_val   = max(1, int(0.2 * n_total))
    n_train = n_total - n_val
    train_subset, val_subset = torch.utils.data.random_split(dataset, [n_train, n_val])
    dataloader = DataLoader(train_subset, batch_size=batch_size, shuffle=True,
                            num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_subset, batch_size=batch_size, shuffle=False,
                            num_workers=4, pin_memory=True)
    print(f"DataLoader ready: {n_train} train / {n_val} val samples")

    # EfficientNetB0 — use new weights API (pretrained=True deprecated)
    weights  = models.EfficientNet_B0_Weights.DEFAULT
    teacher  = models.efficientnet_b0(weights=weights)
    teacher.classifier[1] = nn.Linear(teacher.classifier[1].in_features, NUM_CLASSES)

    # Kaggle Dual T4 — nn.DataParallel
    if torch.cuda.device_count() > 1:
        print(f"nn.DataParallel across {torch.cuda.device_count()} T4 GPUs.")
        teacher = nn.DataParallel(teacher)

    teacher   = teacher.to(DEVICE)
    optimizer = torch.optim.Adam(teacher.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()

    wandb.init(project="bfd-dkd-edge", name="teacher_pretrain", reinit=True)

    best_acc  = 0.0
    save_path = '/kaggle/working/teacher_best.pt'

    for epoch in range(epochs):
        teacher.train()
        total_loss, correct, total = 0.0, 0, 0

        for xb, yb in dataloader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            logits = teacher(xb)
            loss   = criterion(logits, yb)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * xb.size(0)
            correct    += (logits.argmax(1) == yb).sum().item()
            total      += xb.size(0)

        scheduler.step()
        avg_loss = total_loss / total
        acc      = 100.0 * correct / total

        # Bug 7 Fix: Validate on held-out val split, not training data
        teacher.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                logits = teacher(xb)
                val_correct += (logits.argmax(1) == yb).sum().item()
                val_total   += xb.size(0)
        val_acc = 100.0 * val_correct / val_total

        wandb.log({"teacher_loss": avg_loss, "teacher_train_acc": acc, "teacher_val_acc": val_acc, "epoch": epoch})
        print(f"Epoch {epoch+1:02d}/{epochs} | Loss: {avg_loss:.4f} | Train Acc: {acc:.2f}% | Val Acc: {val_acc:.2f}%")

        if val_acc > best_acc:
            best_acc = val_acc
            # Always unwrap DataParallel before saving
            model_to_save = teacher.module if isinstance(teacher, nn.DataParallel) else teacher
            torch.save(model_to_save.state_dict(), save_path)

    wandb.save(save_path)
    print(f"\nTeacher saved: {save_path} (Best Acc: {best_acc:.2f}%)")
    print("Ready for Phase 1 DKD Student Training.")
    wandb.finish()



# ── EXECUTE ───────────────────────────────────────────────────────────────────
# Called once via generate_notebook.py injection — do NOT add duplicate calls here.
precompute_dataset()
train_teacher(epochs=30, batch_size=64, lr=1e-4)
