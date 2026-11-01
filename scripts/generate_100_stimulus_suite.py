#!/usr/bin/env python3
"""
Generate Massive 100-Vector Industrial Stimulus Suite for FPGA Testing
Directly sourced from real CWRU physical vibration .mat files across all operating loads.
25 Normal + 25 Inner Race + 25 Outer Race + 25 Ball Fault = 100 Test Vectors.
"""

import os
import json
import numpy as np
import scipy.io as sio
import scipy.signal as signal

def load_mat_signal(mat_path):
    mat = sio.loadmat(mat_path)
    for k in mat.keys():
        if 'DE' in k:
            return mat[k].flatten().astype(np.float32)
    for k, v in mat.items():
        if isinstance(v, np.ndarray) and v.ndim == 2 and v.shape[1] == 1 and v.shape[0] > 1000:
            return v.flatten().astype(np.float32)
    raise ValueError(f"Could not find DE vibration channel in {mat_path}")

def normalize_to_int16(signal_window):
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
            u16 = int(s) & 0xFFFF
            f.write(f"{u16:04X}\n")

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    cwru_dir = os.path.join(base_dir, 'data', 'CWRU_Dataset')
    out_dir = os.path.join(base_dir, 'embedded', 'fpga_gowin', 'roms', 'stimulus_suite_100')
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 76)
    print(" GENERATING 100 INDUSTRIAL STIMULUS VECTORS FOR EXTENSIVE FPGA TESTING")
    print(" Domain: ADXL345 Physical Accelerometer Rate (3.2 kHz Causal Decimation)")
    print(f" Output Directory: {out_dir}")
    print("=" * 76)

    # Class 0: Normal files
    normal_sources = [
        (os.path.join(cwru_dir, 'Normal', '97.mat'), '0 HP / 1797 RPM'),
        (os.path.join(cwru_dir, 'Normal', '98.mat'), '1 HP / 1772 RPM'),
        (os.path.join(cwru_dir, 'Normal', '99.mat'), '2 HP / 1750 RPM'),
        (os.path.join(cwru_dir, 'Normal', '100.mat'), '3 HP / 1730 RPM')
    ]

    # Class 1: Inner Race files
    inner_sources = [
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '105.mat'), '7mil / 0 HP (1797 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '106.mat'), '7mil / 1 HP (1772 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '107.mat'), '7mil / 2 HP (1750 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '108.mat'), '7mil / 3 HP (1730 RPM)'),
        (os.path.join(cwru_dir, 'Test_Unseen', '14mil', 'InnerRace', '170.mat'), '14mil / 1 HP (Unseen)'),
        (os.path.join(cwru_dir, 'Test_Unseen', '21mil', 'InnerRace', '210.mat'), '21mil / 1 HP (Severe)')
    ]

    # Class 2: Outer Race files
    outer_sources = [
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '130.mat'), '7mil / 0 HP (1797 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '131.mat'), '7mil / 1 HP (1772 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '132.mat'), '7mil / 2 HP (1750 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '133.mat'), '7mil / 3 HP (1730 RPM)'),
        (os.path.join(cwru_dir, 'Test_Unseen', '14mil', 'OuterRace', '198.mat'), '14mil / 1 HP (Unseen)'),
        (os.path.join(cwru_dir, 'Test_Unseen', '21mil', 'OuterRace', '235.mat'), '21mil / 1 HP (Severe)')
    ]

    # Class 3: Ball Fault files
    ball_sources = [
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '118.mat'), '7mil / 0 HP (1797 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '119.mat'), '7mil / 1 HP (1772 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '120.mat'), '7mil / 2 HP (1750 RPM)'),
        (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '121.mat'), '7mil / 3 HP (1730 RPM)'),
        (os.path.join(cwru_dir, 'Test_Unseen', '14mil', 'Ball', '186.mat'), '14mil / 1 HP (Unseen)'),
        (os.path.join(cwru_dir, 'Test_Unseen', '21mil', 'Ball', '223.mat'), '21mil / 1 HP (Severe)')
    ]

    manifest = []
    vector_id = 1

    def extract_25_windows(sources, cls_id, cls_prefix, cls_name):
        nonlocal vector_id
        count = 0
        src_idx = 0
        offsets = [512, 1024, 1536, 2048, 2560, 3072, 3584, 4096]
        
        while count < 25:
            mat_path, cond = sources[src_idx % len(sources)]
            offset = offsets[(count // len(sources)) % len(offsets)]
            raw_sig = load_mat_signal(mat_path)
            
            # Decimate 12.0 kHz -> 3.2 kHz (exact physical rate of ADXL345 accelerometer)
            sig_3k2 = signal.resample_poly(raw_sig, up=4, down=15).astype(np.float32)
            
            if len(sig_3k2) < offset + 512:
                offset = 100
            window = sig_3k2[offset : offset + 512]
            int16_samples = normalize_to_int16(window)
            
            filename = f"stimulus_{vector_id:03d}_{cls_prefix}_vec{count+1:02d}.hex"
            export_hex(int16_samples, os.path.join(out_dir, filename))
            
            mat_basename = os.path.basename(mat_path)
            manifest.append({
                "id": vector_id,
                "file": filename,
                "class_id": cls_id,
                "class_name": cls_name,
                "condition": cond,
                "source_mat": mat_basename,
                "offset": offset,
                "expected_trip": (cls_id != 0)
            })
            
            print(f"  [{vector_id:03d}/100] {filename:35s} | Class {cls_id} ({cls_name:7s}) | {mat_basename:8s} | {cond}")
            vector_id += 1
            count += 1
            src_idx += 1

    print("\n--- [1/4] Extracting 25 Normal Baseline Vectors ---")
    extract_25_windows(normal_sources, 0, "normal", "Normal")

    print("\n--- [2/4] Extracting 25 Inner Race Fault (BPFI) Vectors ---")
    extract_25_windows(inner_sources, 1, "inner", "Inner")

    print("\n--- [3/4] Extracting 25 Outer Race Fault (BPFO) Vectors ---")
    extract_25_windows(outer_sources, 2, "outer", "Outer")

    print("\n--- [4/4] Extracting 25 Ball Defect (BSF) Vectors ---")
    extract_25_windows(ball_sources, 3, "ball", "Ball")

    # Save manifest JSON
    manifest_path = os.path.join(out_dir, "stimulus_100_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Saved 100-vector JSON manifest to: {manifest_path}")

    # Save Markdown Catalog
    catalog_path = os.path.join(out_dir, "STIMULUS_100_CATALOG.md")
    with open(catalog_path, 'w', encoding='utf-8') as f:
        f.write("# KHO 100 TỆP SÓNG RUNG KIỂM THỬ ĐỘC LẬP TRÊN FPGA\n")
        f.write("## (100 INDUSTRIAL STIMULUS VECTORS SUITE FOR FPGA VERIFICATION)\n\n")
        f.write("> **Thư mục:** `embedded/fpga_gowin/roms/stimulus_suite_100/`  \n")
        f.write("> **Quy cách:** 100 tệp `.hex`, mỗi tệp gồm 512 mẫu sóng rung thời gian 16-bit signed trích từ 15 file `.mat` CWRU.  \n")
        f.write("> **Cơ cấu mẫu:** 25 Normal + 25 Inner Race (BPFI) + 25 Outer Race (BPFO) + 25 Ball Fault (BSF).\n\n")
        f.write("| ID | Tên Tệp `.hex` | Lớp Thật | File `.mat` Gốc | Điều Kiện Tải / Mức Nứt | Rơ-le An Toàn SIL-2 Dự Kiến |\n")
        f.write("| :-: | :--- | :---: | :---: | :--- | :---: |\n")
        for m in manifest:
            trip_str = "TRIP CẮT NGUỒN (<1.0ms)" if m["expected_trip"] else "BÌNH THƯỜNG (NC Đóng)"
            f.write(f"| {m['id']:03d} | `{m['file']}` | **{m['class_name']}** | `{m['source_mat']}` | {m['condition']} | {trip_str} |\n")
    print(f"[+] Saved Markdown Catalog to: {catalog_path}")

if __name__ == '__main__':
    main()
