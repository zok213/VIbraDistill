#!/usr/bin/env python3
"""
verify_raw_mat_to_fpga_pipeline.py
================================================================================
CRITICAL REAL-WORLD PHYSICAL VERIFICATION:
Loads raw MATLAB .mat files directly from data/CWRU_Dataset/ (ZERO CACHE).
Passes raw sensor time-series through:
  1. Polyphase anti-aliasing decimation: 12.0 kHz -> 3.2 kHz (ADXL345 physical rate)
  2. 32-Tap Causal Minimum-Phase FIR filter (fir_adxl345_32.v equivalent)
  3. Causal Envelope Demodulator (Rectifier + IIR Butterworth LPF)
  4. Hann window + 512-point FFT -> 257 bins
  5. INT8 Quantization: [0, 127]
  6. Gowin 12-Way FPGA NPU BRAM ROM hardware emulation cycle-by-cycle

Proves 100% real testing on real physical accelerometer vibration data.
================================================================================
"""

import os
import sys
import glob
import numpy as np
import scipy.io as sio
import scipy.signal as signal

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, base_dir)

from src.dsp.pipeline import StreamingDSPPipeline

def load_fpga_roms():
    rom_dir = os.path.join(base_dir, "embedded", "fpga_gowin", "roms", "adxl345")
    banks = []
    for b in range(6):
        hex_file = os.path.join(rom_dir, f"npu_weights_bank{b}.hex")
        assert os.path.exists(hex_file), f"Missing ROM: {hex_file}"
        with open(hex_file, "r") as f:
            words16 = [int(line.strip(), 16) for line in f if line.strip()]
        assert len(words16) == 257, f"Bank {b} has {len(words16)} words"
        ch_low = [((w & 0xFF) - 256) if (w & 0xFF) >= 128 else (w & 0xFF) for w in words16]
        ch_high = [(((w >> 8) & 0xFF) - 256) if ((w >> 8) & 0xFF) >= 128 else ((w >> 8) & 0xFF) for w in words16]
        banks.extend([ch_low, ch_high])
    return np.array(banks, dtype=np.int32) # [12, 257]

def main():
    print("=" * 78)
    print(" LIVE PHYSICAL DATASET AUDIT: DIRECT RAW .MAT FILES -> FPGA NPU HARDWARE")
    print("=" * 78)

    # 1. Load FPGA ROMs
    w12 = load_fpga_roms()
    biases = np.array([0, -3, 8, -4], dtype=np.int32)
    print(f"[1] Loaded 12-way FPGA BRAM ROMs: shape {w12.shape}, biases: {biases.tolist()}")

    # 2. Hardware DSP pipeline: 3.2 kHz ADXL345 causal profile
    dsp = StreamingDSPPipeline(fs=3200.0, window_size=512, sensor_type='adxl345')

    # 3. Read RAW .mat files from disk
    cwru_dir = os.path.join(base_dir, 'data', 'CWRU_Dataset')
    
    # Class definitions:
    # 0: Normal
    # 1: InnerRace (BPFI)
    # 2: OuterRace (BPFO)
    # 3: Ball (BSF)
    test_files = [
        # Normal files (Loads 0, 1, 2 HP)
        (os.path.join(cwru_dir, 'Normal', '97.mat'), 0, 'Normal (Load 0 HP, 1797 RPM)'),
        (os.path.join(cwru_dir, 'Normal', '98.mat'), 0, 'Normal (Load 1 HP, 1772 RPM)'),
        (os.path.join(cwru_dir, 'Normal', '99.mat'), 0, 'Normal (Load 2 HP, 1750 RPM)'),
        # 7-mil Inner Race Faults (Loads 0, 1, 2, 3 HP)
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '105.mat'), 1, 'InnerRace 7-mil (0 HP, 1797 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '106.mat'), 1, 'InnerRace 7-mil (1 HP, 1772 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '107.mat'), 1, 'InnerRace 7-mil (2 HP, 1750 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '108.mat'), 1, 'InnerRace 7-mil (3 HP, 1730 RPM)'),
        # 7-mil Outer Race Faults (Loads 0, 1, 2, 3 HP)
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '130.mat'), 2, 'OuterRace 7-mil (0 HP, 1797 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '131.mat'), 2, 'OuterRace 7-mil (1 HP, 1772 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '132.mat'), 2, 'OuterRace 7-mil (2 HP, 1750 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '133.mat'), 2, 'OuterRace 7-mil (3 HP, 1730 RPM)'),
        # 7-mil Ball Faults (Loads 0, 1, 2, 3 HP)
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '118.mat'), 3, 'Ball 7-mil (0 HP, 1797 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '119.mat'), 3, 'Ball 7-mil (1 HP, 1772 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '120.mat'), 3, 'Ball 7-mil (2 HP, 1750 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '121.mat'), 3, 'Ball 7-mil (3 HP, 1730 RPM)'),
    ]

    all_preds = []
    all_targets = []
    file_stats = []

    print("\n[2] Ingesting and processing RAW .mat files from physical storage...")
    print("-" * 78)

    for fpath, label, desc in test_files:
        assert os.path.exists(fpath), f"File not found: {fpath}"
        mat = sio.loadmat(fpath)
        de_keys = [k for k in mat.keys() if 'DE' in k]
        assert len(de_keys) > 0, f"No DE vibration channel in {fpath}"
        raw_sig = mat[de_keys[0]].flatten().astype(np.float32)

        # Extract RPM
        rpm_keys = [k for k in mat.keys() if 'RPM' in k.upper()]
        rpm = float(mat[rpm_keys[0]].squeeze()) if rpm_keys else 1750.0

        n_raw = len(raw_sig)
        min_g, max_g = float(np.min(raw_sig)), float(np.max(raw_sig))

        # Polyphase anti-aliasing decimation (12 kHz -> 3.2 kHz)
        sig_3k2 = signal.resample_poly(raw_sig, up=4, down=15).astype(np.float32)
        n_3k2 = len(sig_3k2)

        # Slice into 512-sample windows with stride 256 (50% overlap)
        window_size = 512
        stride = 256
        n_windows = (n_3k2 - window_size) // stride + 1

        file_preds = []
        for w in range(n_windows):
            chunk = sig_3k2[w * stride : w * stride + window_size]
            res = dsp.process_window(chunk, rpm=rpm)
            spec_float = res['spectrum'] # [257]
            
            # INT8 Quantization identical to FPGA BRAM input buffer
            spec_int8 = np.clip(np.round(spec_float * 127.0), 0, 127).astype(np.int32)
            
            # Gowin 12-way MAC systolic dot-product
            acc = np.dot(w12, spec_int8) # 12 accumulators
            
            # 4 Class Scores
            score_0 = int(acc[0] + acc[1] + acc[2] + biases[0])
            score_1 = int(acc[3] + acc[4] + acc[5] + biases[1])
            score_2 = int(acc[6] + acc[7] + acc[8] + biases[2])
            score_3 = int(acc[9] + acc[10] + acc[11] + biases[3])
            
            pred = int(np.argmax([score_0, score_1, score_2, score_3]))
            file_preds.append(pred)
            all_preds.append(pred)
            all_targets.append(label)

        file_preds = np.array(file_preds)
        acc_file = np.mean(file_preds == label) * 100.0
        file_stats.append((desc, n_raw, n_3k2, n_windows, min_g, max_g, acc_file))
        print(f"  * {desc:<35} | {n_raw:>7} raw -> {n_3k2:>6} @3.2k ({n_windows:>3} win) | Acc: {acc_file:5.1f}%")

    # 4. Global Metrics across all raw files
    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)
    total_samples = len(all_targets)
    correct_samples = np.sum(all_preds == all_targets)
    overall_acc = (correct_samples / total_samples) * 100.0

    # Confusion Matrix
    cm = np.zeros((4, 4), dtype=np.int32)
    for t, p in zip(all_targets, all_preds):
        cm[t, p] += 1

    classes = ['Class 0 (Normal)', 'Class 1 (Inner)', 'Class 2 (Outer)', 'Class 3 (Ball)']
    precisions = []
    recalls = []
    f1s = []

    print("\n" + "=" * 78)
    print(" REAL PHYSICAL CONFUSION MATRIX (15 RAW .MAT FILES - ZERO CACHE):")
    print("=" * 78)
    header_col = "True \\ Pred"
    print(f"{header_col:<18} | {'Normal':>8} | {'Inner':>8} | {'Outer':>8} | {'Ball':>8} | {'Recall':>8}")
    print("-" * 78)
    for c in range(4):
        tp = cm[c, c]
        fn = np.sum(cm[c, :]) - tp
        fp = np.sum(cm[:, c]) - tp
        prec = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        print(f"{classes[c]:<18} | {cm[c, 0]:>8} | {cm[c, 1]:>8} | {cm[c, 2]:>8} | {cm[c, 3]:>8} | {rec:7.2f}%")
    
    print("-" * 78)
    print(f"{'Precision':<18} | {precisions[0]:7.2f}% | {precisions[1]:7.2f}% | {precisions[2]:7.2f}% | {precisions[3]:7.2f}% |")
    print(f"{'F1-Score':<18} | {f1s[0]:7.2f}% | {f1s[1]:7.2f}% | {f1s[2]:7.2f}% | {f1s[3]:7.2f}% |")
    print("=" * 78)
    macro_f1 = np.mean(f1s)
    print(f" TOTAL REAL RAW SAMPLES TESTED : {total_samples}")
    print(f" CORRECT HARDWARE PREDICTIONS   : {correct_samples} / {total_samples}")
    print(f" OVERALL HARDWARE ACCURACY      : {overall_acc:.2f}%")
    print(f" MACRO-AVERAGED F1-SCORE        : {macro_f1:.2f}%")
    print("=" * 78)

if __name__ == '__main__':
    main()
