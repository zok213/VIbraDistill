#!/usr/bin/env python3
"""
TRAIN & EXPORT HARDWARE PRONOSTIA RUL REGRESSION MODEL FOR GOWIN PRIMER 20K FPGA
================================================================================
Platform: Gowin GW2A-LV18 (Tang Primer 20K FPGA)
Inputs:   257 envelope spectrum bins (INT8 [0, 127]) + 4 kinematic priors (INT8)
Dataset:  FEMTO-ST PRONOSTIA Bearing Degradation Challenge
          - Training: Bearing1_1 & Bearing1_2 (500 life snapshots)
          - Testing:  Bearing1_3 (300 holdout snapshots, unseen testbed)
Output:
  - roms/pronostia_rul_weights.hex (261 INT8 hex lines: 257 bins + 4 priors)
  - roms/pronostia_rul_params.json (Parameters: BIAS, SCALE, SHIFT, MAE)
================================================================================
"""

import os
import sys
import json
import shutil
import numpy as np
import torch
import torch.nn as nn

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, base_dir)

train_path = os.path.join(base_dir, 'data', 'cache', 'pronostia', 'pronostia_Bearing1_1_Bearing1_2_250_knee55.pt')
test_path  = os.path.join(base_dir, 'data', 'cache', 'pronostia', 'pronostia_Bearing1_3_300_knee55.pt')

print("=" * 84)
print("  TRAINING HARDWARE INT8 RUL REGRESSION MODEL FOR GOWIN TANG PRIMER 20K FPGA")
print("=" * 84)

# 1. Load PRONOSTIA datasets
train_data = torch.load(train_path, map_location='cpu', weights_only=False)
test_data  = torch.load(test_path, map_location='cpu', weights_only=False)

# Convert spectrum [0.0..1.0] to INT8 activation [0..127]
X_tr_list = []
y_tr_list = []
for s in train_data:
    spec_int8 = torch.clamp(torch.round(s['spectrum'] * 127.0), 0, 127)
    prior_int8 = s['prior'].float()
    feat = torch.cat([spec_int8, prior_int8])
    X_tr_list.append(feat)
    y_tr_list.append(s['rul'])

X_tr = torch.stack(X_tr_list) # [500, 261]
y_tr = torch.stack(y_tr_list).squeeze(1) # [500]

X_te_list = []
y_te_list = []
for s in test_data:
    spec_int8 = torch.clamp(torch.round(s['spectrum'] * 127.0), 0, 127)
    prior_int8 = s['prior'].float()
    feat = torch.cat([spec_int8, prior_int8])
    X_te_list.append(feat)
    y_te_list.append(s['rul'])

X_te = torch.stack(X_te_list) # [300, 261]
y_te = torch.stack(y_te_list).squeeze(1) # [300]

print(f"[1] Ingested PRONOSTIA dataset:")
print(f"  * Training Set (Bearing1_1, Bearing1_2): {len(X_tr)} samples, 261 features")
print(f"  * Holdout Test (Bearing1_3):            {len(X_te)} samples, 261 features")

# 2. Train Linear Regression Model with SmoothL1Loss and L2 Weight Decay
torch.manual_seed(42)
regressor = nn.Linear(261, 1, bias=True)
optimizer = torch.optim.AdamW(regressor.parameters(), lr=0.005, weight_decay=1e-3)
criterion = nn.SmoothL1Loss()

for epoch in range(1, 1201):
    optimizer.zero_grad()
    pred = torch.clamp(regressor(X_tr).squeeze(1), 0.0, 1.0)
    loss = criterion(pred, y_tr)
    loss.backward()
    optimizer.step()

with torch.no_grad():
    p_tr = torch.clamp(regressor(X_tr).squeeze(1), 0.0, 1.0)
    p_te = torch.clamp(regressor(X_te).squeeze(1), 0.0, 1.0)
    mae_tr = torch.mean(torch.abs(p_tr - y_tr)).item()
    mae_te = torch.mean(torch.abs(p_te - y_te)).item()
    total_hours = 6.5972
    mae_hours = mae_te * total_hours

print(f"\n[2] Model Training Converged:")
print(f"  * Training MAE:   {mae_tr:.4f} ({mae_tr * total_hours:.2f} hours)")
print(f"  * Test MAE:       {mae_te:.4f} ({mae_hours:.2f} hours) -> PASS: {mae_hours <= 1.85}")

# 3. Quantize Weights to INT8 and Bias to INT32
w_float = regressor.weight.data.squeeze(0).numpy() # [261]
b_float = float(regressor.bias.data.item())

max_abs_w = np.max(np.abs(w_float))
# Scale factor so max weight is within [-128, 127]
w_scale = 127.0 / max_abs_w
w_int8 = np.clip(np.round(w_float * w_scale), -128, 127).astype(np.int8)

# Fixed-point requantization for FPGA datapath
# acc = sum(input[k] * w_int8[k])
# Target: RUL_Q15 = clamp( (acc * MULT + BIAS_SCALED) >> SHIFT, 0, 32768 )
# Let's calibrate MULT, SHIFT, and BIAS for exact bit-true mapping to [0, 32768]:
acc_tr = np.dot(X_tr.numpy(), w_int8.astype(np.int32))
acc_min, acc_max = np.min(acc_tr), np.max(acc_tr)

# Linear mapping from acc to Q0.15 [0, 32768]:
# When y_tr = 1.0 (new), acc is positive/high; when y_tr = 0.0 (dead), acc is low.
from scipy.stats import linregress
slope, intercept, r_value, p_value, std_err = linregress(acc_tr, y_tr.numpy() * 32768.0)

# slope ~ MULT / 2^SHIFT
shift = 10
mult = int(np.round(slope * (1 << shift)))
bias_int32 = int(np.round(intercept))

# Bit-true hardware simulation:
def hardware_rul_sim(x_261):
    acc = np.dot(x_261.astype(np.int32), w_int8.astype(np.int32))
    val = (acc * mult) >> shift
    rul_q15 = val + bias_int32
    return np.clip(rul_q15, 0, 32768).astype(np.uint16)

sim_ruls_te = [hardware_rul_sim(x) for x in X_te.numpy()]
sim_ruls_float = np.array(sim_ruls_te) / 32768.0
hw_mae = np.mean(np.abs(sim_ruls_float - y_te.numpy())) * total_hours

print(f"\n[3] INT8 Quantization & Fixed-Point Calibration:")
print(f"  * Weight Scale Factor:  {w_scale:.2f}")
print(f"  * Multiplier (MULT):    {mult}")
print(f"  * Right Shift (SHIFT):  {shift}")
print(f"  * Base Bias (BIAS):     {bias_int32}")
print(f"  * Bit-True HW Test MAE: {hw_mae:.2f} hours (Target <= 1.85h)")

# 4. Export Hex File for FPGA Block RAM (261 lines)
rom_dirs = [
    os.path.join(base_dir, 'embedded', 'fpga_gowin', 'roms'),
    os.path.join(base_dir, 'embedded', 'fpga_gowin', 'src', 'test_npu', 'roms'),
    r"C:\Users\Admin\Downloads\FPGA_FINAL\src\test_npu\roms",
    r"C:\Users\Admin\Downloads\FPGA_FINAL\src\roms"
]

hex_lines = []
for val in w_int8:
    u8 = int(val) & 0xFF
    hex_lines.append(f"{u8:02X}\n")

# Pad to 1024 lines if needed for BSRAM address depth
padded_hex = hex_lines + ["00\n"] * (1024 - len(hex_lines))

for rdir in rom_dirs:
    if os.path.exists(rdir):
        out_hex = os.path.join(rdir, "pronostia_rul_weights.hex")
        with open(out_hex, "w") as f:
            f.writelines(padded_hex)
        print(f"  [SAVED] {out_hex}")

# Save JSON parameter metadata
meta = {
    "model_name": "PRONOSTIA_FPGA_RUL_REGRESSOR",
    "architecture": "Single-Cycle Streaming INT8 MAC (261 taps)",
    "dataset": "PRONOSTIA FEMTO-ST Run-to-Failure (NSK 6804RS @ 1800 RPM)",
    "training_bearings": ["Bearing1_1", "Bearing1_2"],
    "test_bearing": "Bearing1_3",
    "num_weights": 261,
    "quantization": "INT8 weights, INT32 accumulator, Q0.15 output",
    "hardware_mult": mult,
    "hardware_shift": shift,
    "hardware_bias": bias_int32,
    "test_mae_hours": float(hw_mae),
    "target_mae_hours": 1.85
}

meta_path = os.path.join(base_dir, 'embedded', 'fpga_gowin', 'roms', 'pronostia_rul_params.json')
with open(meta_path, 'w') as f:
    json.dump(meta, f, indent=2)
print(f"  [SAVED] {meta_path}")

print("\n" + "=" * 84)
print("  FPGA HARDWARE PRONOSTIA RUL REGRESSION WEIGHTS SUCCESSFULLY GENERATED!")
print("================================================================================")
