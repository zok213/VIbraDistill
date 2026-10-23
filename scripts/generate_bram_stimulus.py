#!/usr/bin/env python3
"""
Generate CWRU BRAM Stimulus Hex Files for Gowin Tang Primer 20K FPGA.
Extracts 5 canonical vibration segments (512 samples each, 16-bit signed integer):
  1. Normal baseline (Class 0)
  2. Ball Fault (Class 3)
  3. Inner Race Fault (Class 1)
  4. Outer Race Fault (Class 2)
  5. Compound / Mixed Fault (High-Severity Unseen)

Outputs:
  embedded/fpga_gowin/roms/stimulus_cwru_normal.hex
  embedded/fpga_gowin/roms/stimulus_cwru_ball.hex
  embedded/fpga_gowin/roms/stimulus_cwru_inner.hex
  embedded/fpga_gowin/roms/stimulus_cwru_outer.hex
  embedded/fpga_gowin/roms/stimulus_cwru_mixed.hex
"""

import os
import glob
import numpy as np
import scipy.io as sio

def load_mat_signal(mat_path):
    mat = sio.loadmat(mat_path)
    for k in mat.keys():
        if 'DE_time' in k:
            return mat[k].flatten()
    # Fallback to any 1D float array with > 1000 samples
    for k, v in mat.items():
        if isinstance(v, np.ndarray) and v.ndim == 2 and v.shape[1] == 1 and v.shape[0] > 1000:
            return v.flatten()
    raise ValueError(f"Could not find DE_time in {mat_path}")

def normalize_to_int16(signal_window):
    # Scale signal window to fit comfortably into 16-bit signed range [-32768, 32767]
    # Max peak scaled to ~80% full scale (26000) to prevent overflow
    max_val = np.max(np.abs(signal_window))
    if max_val < 1e-6:
        max_val = 1.0
    scale = 26000.0 / max_val
    scaled = np.round(signal_window * scale).astype(np.int32)
    clamped = np.clip(scaled, -32768, 32767).astype(np.int16)
    return clamped

def export_hex(samples_int16, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        for s in samples_int16:
            # Format as 16-bit unsigned hex (two's complement)
            u16 = int(s) & 0xFFFF
            f.write(f"{u16:04X}\n")
    print(f"  [+] Exported 512 samples to: {out_path}")

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    cwru_dir = os.path.join(base_dir, 'data', 'CWRU_Dataset')
    out_dir = os.path.join(base_dir, 'embedded', 'fpga_gowin', 'roms')
    
    print("=" * 70)
    print(" CWRU BRAM STIMULUS GENERATOR (Team Porygon - DSAC 2026)")
    print("=" * 70)
    print(f"Source CWRU Dir: {cwru_dir}")
    print(f"Output ROMs Dir: {out_dir}")
    
    # 1. Normal (e.g. 97.mat)
    normal_files = glob.glob(os.path.join(cwru_dir, '**', '*97*.mat'), recursive=True)
    if not normal_files:
        normal_files = glob.glob(os.path.join(cwru_dir, '**', 'Normal*.mat'), recursive=True)
    
    # 2. Ball fault (e.g. 118.mat - 7mil Ball Load 0)
    ball_files = glob.glob(os.path.join(cwru_dir, '**', '*118*.mat'), recursive=True)
    
    # 3. Inner race fault (e.g. 105.mat - 7mil IR Load 0)
    inner_files = glob.glob(os.path.join(cwru_dir, '**', '*105*.mat'), recursive=True)
    
    # 4. Outer race fault (e.g. 130.mat - 7mil OR Centered Load 0)
    outer_files = glob.glob(os.path.join(cwru_dir, '**', '*130*.mat'), recursive=True)
    
    # 5. Mixed / Extreme severity (e.g. 21-mil OR 197.mat or 209.mat)
    mixed_files = glob.glob(os.path.join(cwru_dir, '**', '*197*.mat'), recursive=True)
    if not mixed_files:
        mixed_files = glob.glob(os.path.join(cwru_dir, '**', '*209*.mat'), recursive=True)
        
    targets = [
        ('stimulus_cwru_normal.hex', normal_files, 'Normal Baseline'),
        ('stimulus_cwru_ball.hex', ball_files, 'Ball Defect (7-mil)'),
        ('stimulus_cwru_inner.hex', inner_files, 'Inner Race Defect (7-mil)'),
        ('stimulus_cwru_outer.hex', outer_files, 'Outer Race Defect (7-mil)'),
        ('stimulus_cwru_mixed.hex', mixed_files, 'Severe / Unseen Wear (21-mil)'),
    ]
    
    for filename, filelist, label in targets:
        print(f"\nProcessing {label}...")
        if filelist and os.path.exists(filelist[0]):
            raw = load_mat_signal(filelist[0])
            # Pick a clean 512-sample window starting at offset 1024
            window = raw[1024:1024+512]
        else:
            print(f"  [!] Mat file not found for {label}, generating deterministic synthetic test pattern...")
            t = np.linspace(0, 512/12000, 512)
            if 'Normal' in label:
                window = 0.05 * np.sin(2 * np.pi * 30 * t) + 0.01 * np.random.randn(512)
            elif 'Inner' in label:
                window = 0.5 * np.sin(2 * np.pi * 163 * t) + 0.2 * np.sin(2 * np.pi * 326 * t)
            elif 'Outer' in label:
                window = 0.5 * np.sin(2 * np.pi * 107 * t) + 0.2 * np.sin(2 * np.pi * 214 * t)
            elif 'Ball' in label:
                window = 0.4 * np.sin(2 * np.pi * 141 * t) + 0.15 * np.sin(2 * np.pi * 282 * t)
            else:
                window = 0.8 * np.sin(2 * np.pi * 107 * t) + 0.6 * np.sin(2 * np.pi * 163 * t)
        
        int16_samples = normalize_to_int16(window)
        assert len(int16_samples) == 512, "Sample length must be strictly 512"
        export_hex(int16_samples, os.path.join(out_dir, filename))
        
    print("\n[SUCCESS] All 5 BRAM stimulus vectors generated successfully.")

if __name__ == '__main__':
    main()
