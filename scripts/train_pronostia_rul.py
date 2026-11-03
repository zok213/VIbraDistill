#!/usr/bin/env python3
"""
TRAIN REAL RUL PROGNOSTIC HEAD ON PRONOSTIA FEMTO-ST DATASET
================================================================================
Platform: FEMTO-ST Accelerated Degradation Testbed (Bearing 1_1, 1_2, 1_3)
Architecture: VibraDistillMicro (8,677 parameters) + P-FiLM Kinematic Modulation
Target:
  1. Train RUL Head on Learning_set (Bearing1_1, Bearing1_2) without time cheat.
  2. Calibrate Split Conformal Quantile (1 - alpha = 90% coverage).
  3. Evaluate Adaptive Conformal Prediction on Holdout Test Bearing (Bearing1_3).
  4. Save real PyTorch checkpoint to: checkpoints/prognostics/pronostia_rul_micro.pt
================================================================================
"""

import os
import sys
import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, base_dir)

from src.datasets.pronostia_loader import PronostiaBearingDataset
from src.models.student_micro import VibraDistillMicro
from src.utils.seed import set_seed

class BoundedAdaptiveConformalPredictor:
    def __init__(self, q_calibrated: float, alpha: float = 0.10, gamma: float = 0.02,
                 q_min: float = 0.05, q_max: float = 0.80):
        self.alpha = alpha
        self.gamma = gamma
        self.q = float(q_calibrated)
        self.q_min = q_min
        self.q_max = q_max
        self.history_q = []
        self.history_covered = []

    def predict_interval(self, y_pred: float):
        lower = max(0.0, float(y_pred - self.q))
        upper = min(1.0, float(y_pred + self.q))
        return lower, upper, self.q

    def update(self, y_true: float, y_pred: float):
        covered = abs(float(y_true) - float(y_pred)) <= self.q
        err = 0.0 if covered else 1.0
        self.q = max(self.q_min, min(self.q_max, self.q + self.gamma * (err - self.alpha)))
        self.history_q.append(self.q)
        self.history_covered.append(1 if covered else 0)
        return covered


def train_pronostia_prognostics(epochs=15, batch_size=32, lr=1e-3, seed=42):
    set_seed(seed)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print("=" * 82)
    print("  PRONOSTIA REAL RUN-TO-FAILURE PROGNOSTICS & ADAPTIVE CONFORMAL TRAINING")
    print(f"  Device: {device} | Epochs: {epochs} | Batch Size: {batch_size} | LR: {lr}")
    print("=" * 82)

    # 1. Ingest Learning Set: Bearing1_1 & Bearing1_2
    print("\n[1] Loading PRONOSTIA Learning Set (Bearing1_1, Bearing1_2)...")
    full_train_dataset = PronostiaBearingDataset(
        data_root="data/PRONOSTIA_FEMTO_Dataset",
        bearings=('Bearing1_1', 'Bearing1_2'),
        max_samples_per_bearing=250
    )
    n_total = len(full_train_dataset)
    n_calib = int(0.25 * n_total)
    n_train = n_total - n_calib
    train_dataset, calib_dataset = random_split(
        full_train_dataset, [n_train, n_calib],
        generator=torch.Generator().manual_seed(seed)
    )

    # 2. Ingest Test Set: Bearing1_3 (The un-seen test bearing)
    print("\n[2] Loading PRONOSTIA Holdout Test Set (Bearing1_3)...")
    test_dataset = PronostiaBearingDataset(
        data_root="data/PRONOSTIA_FEMTO_Dataset",
        bearings=('Bearing1_3',),
        max_samples_per_bearing=300
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    calib_loader = DataLoader(calib_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    print(f"  * Training Samples:   {len(train_dataset)}")
    print(f"  * Calibration Split:  {len(calib_dataset)}")
    print(f"  * Test Samples:       {len(test_dataset)}")

    # 3. Model Architecture
    model = VibraDistillMicro(in_bins=257, num_classes=4, physics_dim=4).to(device)
    student_ckpt = "checkpoints/student_dkd/best_student_dkd.pt"
    if os.path.exists(student_ckpt):
        ckpt = torch.load(student_ckpt, map_location=device, weights_only=False)
        model.load_state_dict(ckpt['model_state_dict'], strict=False)
        print(f"  * Initialized CNN backbone representations from: {student_ckpt}")

    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion_rul = nn.SmoothL1Loss()

    # 4. Training Loop
    print("\n[3] Training Prognostic RUL Head on PRONOSTIA Lifecycles...")
    model.train()
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for batch in train_loader:
            x = batch['spectrum'].to(device)
            prior = batch['prior'].to(device)
            y_rul = batch['rul'].to(device)

            optimizer.zero_grad()
            _, pred_rul = model(x, prior)
            loss = criterion_rul(pred_rul, y_rul)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / max(1, len(train_loader))
        if epoch % 3 == 0 or epoch == epochs:
            print(f"  Epoch [{epoch:02d}/{epochs:02d}] | SmoothL1 Loss: {avg_loss:.5f}")

    # 5. Conformal Calibration on Holdout Split
    print("\n[4] Computing Finite-Sample Conformal Nonconformity Quantile...")
    model.eval()
    calib_residuals = []
    with torch.no_grad():
        for batch in calib_loader:
            x = batch['spectrum'].to(device)
            prior = batch['prior'].to(device)
            y_rul = batch['rul'].to(device)
            _, pred_rul = model(x, prior)
            residuals = torch.abs(pred_rul - y_rul).cpu().numpy().flatten()
            calib_residuals.extend(residuals)

    calib_residuals = np.array(calib_residuals)
    n_c = len(calib_residuals)
    alpha = 0.10
    q_level = min(1.0, np.ceil((n_c + 1) * (1.0 - alpha)) / n_c)
    q_hat = float(np.quantile(calib_residuals, q_level))
    print(f"  * Calibration points: {n_c}")
    print(f"  * Calibrated Initial Quantile q_0 (1-alpha=90%): {q_hat:.4f}")

    # 6. Evaluate on Unseen Bearing1_3 Test Set
    print("\n[5] Evaluating Adaptive Conformal Prediction on Bearing1_3...")
    acp = BoundedAdaptiveConformalPredictor(q_calibrated=q_hat, alpha=alpha, gamma=0.035)

    test_trues = []
    test_preds = []
    coverages = []
    with torch.no_grad():
        for batch in test_loader:
            x = batch['spectrum'].to(device)
            prior = batch['prior'].to(device)
            y_rul = batch['rul'].to(device)
            _, pred_rul = model(x, prior)

            for yt, yp in zip(y_rul.cpu().numpy().flatten(), pred_rul.cpu().numpy().flatten()):
                cov = acp.update(yt, yp)
                test_trues.append(yt)
                test_preds.append(yp)
                coverages.append(cov)

    test_trues = np.array(test_trues)
    test_preds = np.array(test_preds)
    empirical_coverage = np.mean(coverages) * 100.0
    mae_norm = np.mean(np.abs(test_trues - test_preds))
    rmse_norm = np.sqrt(np.mean((test_trues - test_preds)**2))
    
    # Total hours of Bearing1_3 is 6.597h
    total_hours = 6.5972
    mae_hours = mae_norm * total_hours
    rmse_hours = rmse_norm * total_hours

    print("\n" + "=" * 82)
    print("  PRONOSTIA BEARING1_3 UNSEEN TEST VERIFICATION RESULTS")
    print("=" * 82)
    print(f"  Target Conformal Coverage:    90.00%")
    print(f"  Empirical Coverage Achieved:  {empirical_coverage:.2f}% (PASS: {empirical_coverage >= 88.0}%)")
    print(f"  Normalized MAE [0..1]:        {mae_norm:.4f}")
    print(f"  Absolute Physical MAE:        {mae_hours:.3f} hours (Target: <= 1.85 h)")
    print(f"  Absolute Physical RMSE:       {rmse_hours:.3f} hours (Target: <= 2.65 h)")
    print("=" * 82)

    os.makedirs("checkpoints/prognostics", exist_ok=True)
    out_ckpt = "checkpoints/prognostics/pronostia_rul_micro.pt"
    torch.save({
        'model_state_dict': model.state_dict(),
        'calibrated_q': q_hat,
        'empirical_coverage': empirical_coverage,
        'mae_norm': mae_norm,
        'mae_hours': mae_hours,
        'rmse_hours': rmse_hours,
        'bearing_test': 'Bearing1_3',
        'bearing_train': ('Bearing1_1', 'Bearing1_2')
    }, out_ckpt)
    print(f"  [SAVED] Real PRONOSTIA RUL Checkpoint: {out_ckpt}")
    return model, q_hat, empirical_coverage

if __name__ == '__main__':
    train_pronostia_prognostics()
