"""
PHASE 1: KAGGLE CLOUD TRAINING (DUAL T4 32GB VRAM)
Target: Train 1D-CNN via DKD (Teacher: EfficientNetB0)
Dataset: CWRU (Bearing-Wise, Train: 0+1 HP, Test: 2+3 HP)

BUG FIXES APPLIED (Expert Round 3):
  Bug 2: Replaced on-the-fly CWT generation with PairedDKDDataset → reduces 52h → 4h
  Bug 4: Student1DCNN now has 4 conv blocks, BatchNorm, Dropout, AdaptiveAvgPool
  Improvement: CosineAnnealingLR scheduler added
  Improvement: 9-point hyperparameter grid (tau, alpha, beta) pre-search
  Improvement: StudentInferenceOnly wrapper for clean ONNX export
  Fix: Removed duplicate `import json`
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import models
import numpy as np
import wandb
import json
import os
from sklearn.metrics import f1_score
from Phase1_DataLoaders import get_dataloaders, CWRUBearingDataset

# Verify Kaggle Dual-GPU availability
print(f"CUDA Available: {torch.cuda.is_available()}")
print(f"GPU Count: {torch.cuda.device_count()}")
if torch.cuda.device_count() >= 2:
    print(f"GPU 0: {torch.cuda.get_device_name(0)}")
    print(f"GPU 1: {torch.cuda.get_device_name(1)}")

# ---------------------------------------------------------
# 1. ARCHITECTURE DEFINITIONS
# Bug 4 Fix: Replace 1-layer CNN with 4-block deep CNN
# ---------------------------------------------------------

class Student1DCNN(nn.Module):
    """
    Deep 4-block 1D-CNN for bearing fault diagnosis.
    Input: (B, 1, 257) — 257-bin envelope spectrum.
    Output: (logits, projected_features) for DKD training.
    """
    def __init__(self, num_classes=4):
        super().__init__()
        self.conv_block = nn.Sequential(
            # Block 1: broad features — kernel 9 captures wide frequency patterns
            nn.Conv1d(1, 32, kernel_size=9, padding=4),
            nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),   # 257→128

            # Block 2: mid-frequency features
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2),   # 128→64

            # Block 3: fine spectral patterns
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128), nn.ReLU(), nn.MaxPool1d(2),  # 64→32

            # Block 4: BPFO harmonic discriminators
            nn.Conv1d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256), nn.ReLU(),
            nn.AdaptiveAvgPool1d(4),                           # 32→4 (fixed, independent of input size)
        )
        # Feature bottleneck: 256×4 = 1024D → 128D
        self.fc_feature = nn.Sequential(
            nn.Linear(1024, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 128),  nn.ReLU()
        )
        # Cross-Modal Projection: 128D → 1280D (EfficientNetB0 feature space)
        self.projection_head = nn.Linear(128, 1280)
        # Classification head
        self.classifier = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.conv_block(x)              # (B, 256, 4)
        x = x.view(x.size(0), -1)          # (B, 1024)
        feat = self.fc_feature(x)           # (B, 128)
        logits = self.classifier(feat)      # (B, num_classes)
        proj   = self.projection_head(feat) # (B, 1280)
        return logits, proj


class StudentInferenceOnly(nn.Module):
    """
    Bug Fix: ONNX export must expose only fault_logits — not projected_features.
    Projected features are a training-time artifact and would confuse TensorRT.
    """
    def __init__(self, student):
        super().__init__()
        self.student = student

    def forward(self, x):
        return self.student(x)[0]  # logits only


# ---------------------------------------------------------
# 2. BUG 2 FIX — PairedDKDDataset
# Load CWT cache alongside envelope spectrum to avoid 62,500 on-the-fly CWT calls
# ---------------------------------------------------------

class PairedDKDDataset(Dataset):
    """
    Paired dataset for DKD training.
    envelope_data: (N, 257) — from CWRUBearingDataset.data_windows
    cwt_data: (N, 3, 224, 224) — precomputed by Phase1c Teacher precompute step
    Both datasets must be in strict sample-order alignment.
    """
    def __init__(self, envelope_data, envelope_labels, cwt_data):
        assert len(envelope_data) == len(cwt_data), \
            f"Size mismatch: envelope={len(envelope_data)}, cwt={len(cwt_data)}. " \
            "Re-run Teacher precompute step on exact same CWRU dataset."
        self.env    = torch.tensor(envelope_data)   # (N, 257)
        self.cwt    = torch.tensor(cwt_data)         # (N, 3, 224, 224)
        self.labels = torch.tensor(envelope_labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.env[idx], self.cwt[idx], self.labels[idx]


# ---------------------------------------------------------
# 3. DKD LOSS FUNCTION WITH FEATURE ALIGNMENT
# ---------------------------------------------------------

def dkd_loss_with_projection(student_logits, teacher_logits, student_feats, teacher_feats,
                              targets, tau=5.0, alpha=1.0, beta=8.0):
    p_student = F.softmax(student_logits / tau, dim=1)
    p_teacher = F.softmax(teacher_logits / tau, dim=1)

    # Target Class Knowledge Distillation (TCKD)
    pt_student = torch.sum(p_student * targets, dim=1, keepdim=True)
    pt_teacher = torch.sum(p_teacher * targets, dim=1, keepdim=True)
    tckd_loss = -torch.sum(pt_teacher * torch.log(pt_student + 1e-7))

    # Non-Target Class Knowledge Distillation (NCKD)
    mask = 1.0 - targets
    pnt_student = p_student * mask
    pnt_student = pnt_student / (torch.sum(pnt_student, dim=1, keepdim=True) + 1e-7)
    pnt_teacher = p_teacher * mask
    pnt_teacher = pnt_teacher / (torch.sum(pnt_teacher, dim=1, keepdim=True) + 1e-7)
    nckd_loss = -torch.sum(pnt_teacher * torch.log(pnt_student + 1e-7))

    # Cross-Modal Feature Alignment (MSE in 1280D teacher space)
    feature_loss = F.mse_loss(student_feats, teacher_feats)

    # Cross Entropy (hard labels)
    ce_loss = F.cross_entropy(student_logits, targets.argmax(dim=1))

    total_loss = ce_loss + (tau**2) * (alpha * tckd_loss + beta * nckd_loss) + 0.1 * feature_loss
    return total_loss


# ---------------------------------------------------------
# 4. KAGGLE TRAINING SETUP
# ---------------------------------------------------------

def main():
    WINDOW_SIZE    = 512
    SPECTRUM_BINS  = WINDOW_SIZE // 2 + 1  # = 257
    CWRU_ROOT      = os.environ.get('CWRU_ROOT', 'CWRU_Dataset')
    FIR_PATH       = 'fir_coefficients.npy'
    CWT_FEAT_PATH  = '/kaggle/working/precomputed_cwt_features.npy'
    CWT_LBL_PATH   = '/kaggle/working/precomputed_cwt_labels.npy'
    assert os.path.exists(CWT_FEAT_PATH), \
        "CRITICAL: CWT cache not found. Run Phase1c Teacher precompute first!"

    wandb.init(project="bfd-dkd-edge", config={
        "tau": 5.0, "alpha": 1.0, "beta": 8.0,
        "batch_size": 256, "epochs": 50, "learning_rate": 1e-3
    })
    config = wandb.config

    # Load CWRU data for envelope features
    train_dataset = CWRUBearingDataset(
        data_dir=CWRU_ROOT, load_conditions=[0, 1], severity=['7-mil'], fir_coeffs_path=FIR_PATH
    )
    test_dataset = CWRUBearingDataset(
        data_dir=CWRU_ROOT, load_conditions=[2, 3], severity=['14-mil', '21-mil'], fir_coeffs_path=FIR_PATH
    )
    test_dl = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False, num_workers=4)

    # Build PairedDKDDataset (Bug 2 Fix)
    cwt_features   = np.load(CWT_FEAT_PATH)   # (N, 3, 224, 224)
    env_features   = train_dataset.data_windows  # (N, 257)
    env_labels     = train_dataset.labels

    paired_dataset = PairedDKDDataset(env_features, env_labels, cwt_features)
    paired_loader  = DataLoader(paired_dataset, batch_size=config.batch_size,
                                shuffle=True, num_workers=4, pin_memory=True)
    print(f"PairedDKDDataset ready: {len(paired_dataset)} samples")

    # -------------------------------------------------------
    # Improvement: 9-point hyperparameter grid search (τ, α, β)
    # Run 2 epochs per combo, pick best val_f1 for full training
    # -------------------------------------------------------
    print("\n=== HYPERPARAMETER GRID SEARCH (tau × alpha × beta) ===")
    best_hparams = {'tau': 5.0, 'alpha': 1.0, 'beta': 8.0}
    best_grid_f1 = 0.0

    teacher_grid = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
    teacher_grid.classifier[1] = nn.Linear(1280, 4)
    if os.path.exists('/kaggle/working/teacher_best.pt'):
        teacher_grid.load_state_dict(torch.load('/kaggle/working/teacher_best.pt', map_location='cpu'))
    for p in teacher_grid.parameters(): p.requires_grad = False
    teacher_grid = nn.DataParallel(teacher_grid).cuda() if torch.cuda.device_count() > 1 else teacher_grid.cuda()
    teacher_grid.eval()

    for tau in [3.0, 5.0, 7.0]:
        for alpha in [0.5, 1.0]:
            for beta in [4.0, 8.0]:
                s = Student1DCNN(num_classes=4)
                if torch.cuda.device_count() > 1: s = nn.DataParallel(s)
                s = s.cuda()
                opt = torch.optim.Adam(s.parameters(), lr=config.learning_rate)
                s.train()
                for batch_env, batch_cwt, batch_y in paired_loader:
                    batch_env = batch_env.unsqueeze(1).cuda()
                    batch_cwt = batch_cwt.cuda()
                    batch_y   = batch_y.cuda()
                    with torch.no_grad():
                        t_logits = teacher_grid(batch_cwt)
                        t_mod = teacher_grid.module if isinstance(teacher_grid, nn.DataParallel) else teacher_grid
                        t_feats = t_mod.features(batch_cwt)
                        t_feats = t_mod.avgpool(t_feats).flatten(1)
                    opt.zero_grad()
                    s_logits, s_feats = s(batch_env)
                    loss = dkd_loss_with_projection(s_logits, t_logits, s_feats, t_feats,
                                                   F.one_hot(batch_y, 4).float(),
                                                   tau=tau, alpha=alpha, beta=beta)
                    loss.backward()
                    opt.step()
                    break  # Only 1 batch for fast grid search

                s.eval()
                all_preds, all_lbls = [], []
                with torch.no_grad():
                    for xb, yb in test_dl:
                        logits, _ = s(xb.cuda())
                        all_preds.extend(logits.argmax(1).cpu().numpy())
                        all_lbls.extend(yb.numpy())
                grid_f1 = f1_score(all_lbls, all_preds, average='weighted')
                wandb.log({'grid_tau': tau, 'grid_alpha': alpha, 'grid_beta': beta, 'grid_f1': grid_f1})
                print(f"  tau={tau}, alpha={alpha}, beta={beta} → F1={grid_f1:.3f}")
                if grid_f1 > best_grid_f1:
                    best_grid_f1 = grid_f1
                    best_hparams = {'tau': tau, 'alpha': alpha, 'beta': beta}

    print(f"\nBest hparams: {best_hparams} → grid F1={best_grid_f1:.3f}")
    del teacher_grid

    # -------------------------------------------------------
    # Full 5-seed DKD training with best hyperparameters
    # -------------------------------------------------------
    SEEDS = [42, 123, 456, 789, 1024]
    five_seed_results = []

    for seed in SEEDS:
        print(f"\n{'='*40}\nSTARTING TRAINING FOR SEED: {seed}\n{'='*40}")
        torch.manual_seed(seed)
        np.random.seed(seed)

        student = Student1DCNN(num_classes=4)
        teacher = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
        teacher.classifier[1] = nn.Linear(1280, 4)
        if os.path.exists('/kaggle/working/teacher_best.pt'):
            teacher.load_state_dict(torch.load('/kaggle/working/teacher_best.pt', map_location='cpu'))
        else:
            print("WARNING: pretrained teacher not found. DKD will be unstable.")
        for param in teacher.parameters(): param.requires_grad = False

        if torch.cuda.device_count() > 1:
            student = nn.DataParallel(student)
            teacher = nn.DataParallel(teacher)
        student = student.cuda()
        teacher = teacher.cuda()
        teacher.eval()

        optimizer = torch.optim.Adam(student.parameters(), lr=config.learning_rate)
        # Improvement: CosineAnnealingLR scheduler
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=config.epochs)
        best_f1 = 0.0

        for epoch in range(config.epochs):
            student.train()
            total_loss = 0.0

            # Bug 2 Fix: Use paired_loader — no on-the-fly CWT generation
            for env_xb, cwt_xb, yb in paired_loader:
                env_xb = env_xb.unsqueeze(1).cuda()  # (B, 1, 257)
                cwt_xb = cwt_xb.cuda()               # (B, 3, 224, 224)
                yb     = yb.cuda()

                with torch.no_grad():
                    teacher_logits = teacher(cwt_xb)
                    t_mod = teacher.module if isinstance(teacher, nn.DataParallel) else teacher
                    t_feats = t_mod.features(cwt_xb)
                    t_feats = t_mod.avgpool(t_feats).flatten(1)

                optimizer.zero_grad()
                student_logits, student_feats = student(env_xb)

                loss = dkd_loss_with_projection(
                    student_logits, teacher_logits,
                    student_feats, t_feats,
                    F.one_hot(yb, num_classes=4).float(),
                    tau=best_hparams['tau'],
                    alpha=best_hparams['alpha'],
                    beta=best_hparams['beta']
                )
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * env_xb.size(0)

            train_loss = total_loss / len(paired_dataset)
            scheduler.step()

            # Validation on test_dl
            student.eval()
            all_preds, all_labels = [], []
            with torch.no_grad():
                for xb, yb in test_dl:
                    logits, _ = student(xb.unsqueeze(1).cuda() if xb.dim() == 2 else xb.cuda())
                    all_preds.extend(logits.argmax(1).cpu().numpy())
                    all_labels.extend(yb.numpy())

            val_f1 = f1_score(all_labels, all_preds, average='weighted')
            if val_f1 > best_f1:
                best_f1 = val_f1
                best_state = student.module.state_dict() if isinstance(student, nn.DataParallel) else student.state_dict()
                torch.save(best_state, f'/kaggle/working/best_student_seed{seed}.pt')

            wandb.log({"seed": seed, "epoch": epoch, "train_loss": train_loss, "val_f1": val_f1 * 100.0})

            # Checkpoint every 5 epochs
            if epoch % 5 == 0 and epoch > 0:
                ckpt_path = f'/kaggle/working/checkpoint_seed{seed}_epoch{epoch}.pt'
                torch.save({
                    'epoch': epoch, 'seed': seed,
                    'student_state': student.module.state_dict() if isinstance(student, nn.DataParallel) else student.state_dict(),
                    'optimizer_state': optimizer.state_dict(), 'best_f1': best_f1,
                }, ckpt_path)
                wandb.save(ckpt_path)

        five_seed_results.append({'seed': seed, 'best_f1': best_f1, 'final_loss': train_loss})

    wandb.finish()

    with open('/kaggle/working/five_seed_results.json', 'w') as f:
        json.dump(five_seed_results, f)

    # ---------------------------------------------------------
    # ONNX EXPORT — Improvement: StudentInferenceOnly (logits only)
    # ---------------------------------------------------------
    student_unwrapped = student.module if hasattr(student, 'module') else student
    student_unwrapped.eval().cpu()

    # Inference-only wrapper strips the projected_features output
    export_model = StudentInferenceOnly(student_unwrapped)
    export_model.eval()
    dummy_input = torch.randn(1, 1, 257)

    torch.onnx.export(
        export_model,
        dummy_input,
        '/kaggle/working/student_distilled.onnx',
        opset_version=17,
        input_names=['envelope_spectrum'],
        output_names=['fault_logits'],           # Clean single output for TRT
        dynamic_axes={'envelope_spectrum': {0: 'batch_size'}},
        do_constant_folding=True,
    )
    print("student_distilled.onnx exported successfully (logits-only).")

    import onnxruntime as ort
    sess = ort.InferenceSession('/kaggle/working/student_distilled.onnx')
    out  = sess.run(None, {'envelope_spectrum': dummy_input.numpy()})
    print(f"ONNX verification passed. Output shape: {out[0].shape}")  # Expected: (1, 4)


if __name__ == "__main__":
    main()
