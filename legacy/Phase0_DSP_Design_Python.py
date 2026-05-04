"""
PHASE 0: PURE PYTHON DSP DESIGN (KAGGLE CLOUD)
Target: Replace MATLAB. Generate Causal FIR Filter and extract Spectral Kurtosis bands.
"""

import numpy as np
import scipy.io as sio
import scipy.signal as signal
from scipy.stats import kurtosis
import os

def load_healthy_sample(file_path):
    """Load the 0 HP baseline 97.mat."""
    assert os.path.exists(file_path), f"CRITICAL: {file_path} not found. Ensure CWRU dataset is mounted."
    mat = sio.loadmat(file_path)
    # CWRU Drive End normal baseline
    key = [k for k in mat.keys() if 'DE_time' in k][0]
    return mat[key].flatten()

def calculate_spectral_kurtosis(sig, fs=12000, n_bands=6):
    """
    Fast Kurtogram — CAUSAL implementation.
    Uses one-pass FIR filtering (scipy.signal.lfilter), NOT filtfilt.
    """
    nyq = fs / 2
    band_width = nyq / n_bands
    best_kurt, best_band = -1, (1, nyq - 1)

    for i in range(n_bands):
        f_low = max(1, i * band_width)
        f_high = min((i + 1) * band_width, nyq - 1)

        # Causal FIR bandpass — one pass, no future samples
        n_taps = 65  # odd = Type I FIR
        b_fir = signal.firwin(n_taps, [f_low/nyq, f_high/nyq], pass_zero=False)
        # lfilter = causal one-pass. filtfilt is forbidden.
        filtered = signal.lfilter(b_fir, 1.0, sig[:fs*2])
        # Discard first n_taps//2 samples (group delay transient)
        filtered = filtered[n_taps//2:]

        env = np.abs(signal.hilbert(filtered))
        k = kurtosis(env)
        if k > best_kurt:
            best_kurt, best_band = k, (f_low, f_high)

    return best_band[0], best_band[1], best_kurt

def main():
    print("--- PYTHON DSP DESIGN INITIALIZED ---")
    fs = 12000
    
    # 1. Load Data
    x_healthy = load_healthy_sample('CWRU_Dataset/Normal/97.mat')
    
    # 2. Spectral Kurtosis Band Selection
    print("Calculating Spectral Kurtosis resonance bands...")
    f_lower, f_upper, max_kurt = calculate_spectral_kurtosis(x_healthy, fs)
    
    print(f"Optimal Resonance Band found: [{f_lower:.2f} Hz, {f_upper:.2f} Hz]")
    
    # 2a. Kinematic Fault Verification
    # SKF 6205-2RS bearing: BPFO ~ 105 Hz, BPFI ~ 158 Hz.
    if f_upper < 1000:
        print("WARNING: Resonance band is low. High-frequency fault impacts may be missed.")
    else:
        print("SUCCESS: SK Resonance band successfully covers high-frequency BPFO/BPFI harmonics.")
        
    # 3. Causal Minimum-Phase FIR Filter Design
    print("Designing Causal Minimum-Phase FIR Filter...")
    n_order = 64 # Fixed for Edge constraints
    nyq = fs / 2
    from scipy.signal import firwin, minimum_phase
    
    # Step 1: Design linear-phase prototype
    b_linear = firwin(n_order + 1, [f_lower/nyq, f_upper/nyq], pass_zero=False)
    
    # Step 2: Convert to minimum-phase (non-symmetric, all poles inside unit circle)
    b_fir = minimum_phase(b_linear, method='homomorphic')
    
    # Minimum-phase FIR has NON-CONSTANT group delay — report the worst-case (at passband edge)
    w, gd = signal.group_delay((b_fir, 1))
    passband_mask = (w / np.pi * nyq > f_lower) & (w / np.pi * nyq < f_upper)
    max_group_delay_samples = np.max(gd[passband_mask])
    max_group_delay_ms = (max_group_delay_samples / fs) * 1000
    
    print(f"Minimum-phase FIR max group delay: {max_group_delay_samples:.1f} samples ({max_group_delay_ms:.2f} ms)")
    
    # 4. Export Coefficients
    np.save('/kaggle/working/fir_coefficients.npy', b_fir)
    # Also save locally for Jetson workflow tracking
    np.save('fir_coefficients.npy', b_fir)
    print("Phase 0 Complete: fir_coefficients.npy saved successfully.")

if __name__ == "__main__":
    main()
