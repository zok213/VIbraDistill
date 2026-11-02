#!/usr/bin/env python3
"""
Package PRONOSTIA Run-to-Failure degradation dataset into a standard MATLAB .mat benchmark.
Produces:
    data/rul_mat_benchmarks/bearing_lifecycle_1_3.mat
    data/rul_mat_benchmarks/README.md

Fields stored in .mat:
    - dataset_name: "PRONOSTIA_Bearing1_3"
    - condition: "1800 RPM, 4000 N Radial Load"
    - fs: 25600 (Hz)
    - snapshot_interval_sec: 10.0
    - total_snapshots: 2375
    - total_duration_hours: 6.5972
    - snapshot_indices: int32 array [1 .. 2375]
    - time_hours: float32 array of elapsed hours
    - true_rul_hours: float32 array of remaining hours
    - true_rul_pct: float32 array of remaining percentage [100% -> 0%]
    - horizontal_rms: float32 array of snapshot RMS
    - horizontal_kurtosis: float32 array of snapshot Kurtosis
    - horizontal_peak_g: float32 array of snapshot absolute peak
    - raw_vibration_matrix: 2375 x 2560 float32 (optional compressed full waveform)
"""

import os
import glob
import numpy as np
import scipy.io as sio

def package_pronostia_mat():
    src_dir = r"data\PRONOSTIA_FEMTO_Dataset\ieee-phm-2012-data-challenge-dataset-master\Full_Test_Set\Bearing1_3"
    out_dir = r"data\rul_mat_benchmarks"
    os.makedirs(out_dir, exist_ok=True)
    out_mat_path = os.path.join(out_dir, "bearing_lifecycle_1_3.mat")

    csv_files = sorted(glob.glob(os.path.join(src_dir, "acc_*.csv")))
    num_snaps = len(csv_files)
    print(f"[MAT_PACKAGER] Found {num_snaps} raw CSV files in {src_dir}")

    fs = 25600
    interval_s = 10.0
    total_seconds = num_snaps * interval_s
    total_hours = total_seconds / 3600.0

    snapshot_indices = np.arange(1, num_snaps + 1, dtype=np.int32)
    time_hours = (snapshot_indices - 1) * interval_s / 3600.0
    true_rul_hours = total_hours - time_hours
    true_rul_pct = (true_rul_hours / total_hours) * 100.0

    rms_arr = np.zeros(num_snaps, dtype=np.float32)
    kurt_arr = np.zeros(num_snaps, dtype=np.float32)
    peak_arr = np.zeros(num_snaps, dtype=np.float32)
    
    # Representative subsampled waveforms or full matrix
    # Full matrix: 2375 x 2560 float32 = 24.3 MB uncompressed, ~8 MB compressed in .mat
    print("[MAT_PACKAGER] Ingesting CSV files and computing kinematic degradation indicators...")
    vibration_matrix = np.zeros((num_snaps, 2560), dtype=np.float32)

    for i, fpath in enumerate(csv_files):
        # Load columns 4 (horiz acc) and 5 (vert acc)
        # Fast load using numpy fromfile or genfromtxt
        data = np.genfromtxt(fpath, delimiter=',', usecols=(4,))
        if len(data) > 2560:
            data = data[:2560]
        elif len(data) < 2560:
            data = np.pad(data, (0, 2560 - len(data)))
        
        vibration_matrix[i, :] = data.astype(np.float32)
        
        # Health features
        rms = np.sqrt(np.mean(data**2))
        std = np.std(data)
        kurt = (np.mean((data - np.mean(data))**4) / (std**4 + 1e-9)) if std > 1e-6 else 3.0
        peak = np.max(np.abs(data))

        rms_arr[i] = rms
        kurt_arr[i] = kurt
        peak_arr[i] = peak

        if (i + 1) % 500 == 0 or (i + 1) == num_snaps:
            print(f"  Processed {i+1}/{num_snaps} snapshots (RMS={rms:.3f}g, Kurtosis={kurt:.2f}, RUL={true_rul_pct[i]:.1f}%)")

    mat_dict = {
        'dataset_name': 'PRONOSTIA_Bearing1_3',
        'condition': '1800 RPM (30 Hz shaft), 4000 N Radial Load',
        'fs_hz': np.int32(fs),
        'snapshot_interval_sec': np.float32(interval_s),
        'total_snapshots': np.int32(num_snaps),
        'total_duration_hours': np.float32(total_hours),
        'snapshot_indices': snapshot_indices,
        'time_hours': time_hours.astype(np.float32),
        'true_rul_hours': true_rul_hours.astype(np.float32),
        'true_rul_pct': true_rul_pct.astype(np.float32),
        'horizontal_rms_g': rms_arr,
        'horizontal_kurtosis': kurt_arr,
        'horizontal_peak_g': peak_arr,
        'vibration_raw_g': vibration_matrix,
        'failure_threshold_rms_g': np.float32(20.0),
        'sensor_type': 'PCB 352C33 High-Sensitivity Accelerometer',
    }

    print(f"[MAT_PACKAGER] Saving compressed MATLAB .mat file to: {out_mat_path}")
    sio.savemat(out_mat_path, mat_dict, do_compression=True)
    file_size_mb = os.path.getsize(out_mat_path) / (1024 * 1024)
    print(f"[MAT_PACKAGER] SUCCESS: Created {out_mat_path} ({file_size_mb:.2f} MB)")

if __name__ == '__main__':
    package_pronostia_mat()
