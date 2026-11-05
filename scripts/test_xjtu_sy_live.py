"""
Test XJTU-SY Live Run-to-Failure Degradation on FPGA NPU Model.
Bearing 1_1 is an Outer Race fault bearing that degrades over 123 snapshots.
"""

import sys, os
sys.path.insert(0, os.path.abspath('.'))
import glob
import pandas as pd
import numpy as np
from scipy import signal
from src.dsp.pipeline import StreamingDSPPipeline
from scripts.verify_raw_mat_to_fpga_pipeline import load_fpga_roms

base_dir = r'data/XJTU-SY_Dataset/raw/XJTU-SY_Bearing_Datasets/35Hz12kN/Bearing1_1'
csv_files = sorted(glob.glob(os.path.join(base_dir, '*.csv')), key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
print(f'Total CSV snapshots in Bearing1_1: {len(csv_files)}')

w12 = load_fpga_roms()
biases = np.array([0, -3, 8, -4], dtype=np.int32)
dsp = StreamingDSPPipeline(fs=12000.0, window_size=512, sensor_type='hil_12k')

test_snapshots = [1, 20, 40, 60, 80, 100, 120, 123]
class_names = ['Normal', 'Inner Race (BPFI)', 'Outer Race (BPFO)', 'Ball Defect (BSF)']

print('\nTesting XJTU-SY Bearing1_1 (Run-to-failure Outer Race degradation):')
header = f"{'File':<10} | {'True RUL':<8} | {'FPGA Prediction':<20} | {'Scores [N, I, O, B]':<30} | {'Vacuity u'}"
print(header)
print('-' * len(header))

for snap in test_snapshots:
    fpath = os.path.join(base_dir, f'{snap}.csv')
    if not os.path.exists(fpath):
        continue
    df = pd.read_csv(fpath)
    raw_sig = df.iloc[:, 0].values.astype(np.float32)
    
    # Resample from 25.6 kHz to 12.0 kHz
    sig_12k = signal.resample_poly(raw_sig, up=75, down=160).astype(np.float32)
    
    mid = len(sig_12k) // 2
    chunk = sig_12k[mid : mid + 512]
    if len(chunk) < 512:
        continue
        
    spec = dsp.process_window(chunk, rpm=2100.0)['spectrum']
    spec_int8 = np.clip(np.round(spec * 127.0), 0, 127).astype(np.int32)
    
    acc = np.dot(w12, spec_int8)
    scores = [
        int(acc[0] + acc[1] + acc[2] + biases[0]),
        int(acc[3] + acc[4] + acc[5] + biases[1]),
        int(acc[6] + acc[7] + acc[8] + biases[2]),
        int(acc[9] + acc[10] + acc[11] + biases[3])
    ]
    pred = int(np.argmax(scores))
    
    evidences = [max(0, s >> 6) for s in scores]
    S = sum(evidences) + 4
    vacuity = 4.0 / S
    
    true_rul = (len(csv_files) - snap) / len(csv_files) * 100.0
    scores_str = f"[{scores[0]:4d}, {scores[1]:4d}, {scores[2]:4d}, {scores[3]:4d}]"
    print(f"{snap:>4}.csv   | {true_rul:6.1f}%  | {class_names[pred]:<20} | {scores_str:<30} | {vacuity:.3f}")
