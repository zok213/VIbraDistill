"""
Test MATLAB .mat Run-to-Failure (RUL) benchmark loading and Conformal Prognostics.
Validates:
    - Integrity of data/rul_mat_benchmarks/bearing_lifecycle_1_3.mat
    - Proper dictionary keys and types
    - Health indicators (RMS, Kurtosis) tracking physical fatigue degradation
    - Conformal prediction coverage >= 90%
    - Safety SIL-2 trip logic asserting before catastrophic breakdown
"""

import os
import sys
import pytest
import numpy as np
import scipy.io as sio

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.verify_mat_rul_prognostics import verify_mat_rul

MAT_PATH = "data/rul_mat_benchmarks/bearing_lifecycle_1_3.mat"

def test_mat_file_existence_and_keys():
    """Verify that the .mat benchmark file exists and contains all required prognostic fields."""
    assert os.path.exists(MAT_PATH), f"Missing MATLAB RUL benchmark at {MAT_PATH}"
    mat = sio.loadmat(MAT_PATH)
    
    required_keys = [
        'dataset_name', 'condition', 'fs_hz', 'snapshot_interval_sec',
        'total_snapshots', 'total_duration_hours', 'time_hours',
        'true_rul_hours', 'true_rul_pct', 'horizontal_rms_g',
        'horizontal_kurtosis', 'horizontal_peak_g', 'vibration_raw_g',
        'failure_threshold_rms_g'
    ]
    for key in required_keys:
        assert key in mat, f"Key '{key}' not found in {MAT_PATH}"

    total_snaps = int(mat['total_snapshots'][0][0])
    assert total_snaps == 2375, f"Expected 2375 snapshots, found {total_snaps}"
    assert mat['vibration_raw_g'].shape == (2375, 2560), "Waveform matrix shape mismatch"

def test_mat_physical_degradation_trajectory():
    """Assert that physical vibration exhibits wear-out runaway (terminal RMS > 5x baseline)."""
    mat = sio.loadmat(MAT_PATH)
    rms = mat['horizontal_rms_g'].flatten()
    baseline_rms = np.median(rms[:200])
    terminal_rms = np.mean(rms[-50:])
    
    assert terminal_rms > 5.0 * baseline_rms, (
        f"Terminal RMS ({terminal_rms:.2f}g) did not demonstrate expected runaway vs baseline ({baseline_rms:.2f}g)"
    )

def test_mat_conformal_prognostics_verification():
    """Run verify_mat_rul end-to-end and assert all conformal and SIL-2 criteria pass."""
    success = verify_mat_rul(MAT_PATH)
    assert success is True, "verify_mat_rul failed assertion checks"
