"""
Polyphase Resampling Engine for Cross-Dataset Bandwidth Alignment.
Resamples raw vibration signals from arbitrary sampling rates (e.g. 97.656 kHz, 64 kHz, 50 kHz, 5.12 kHz)
to the unified target rate fs = 12,000 Hz expected by the Gowin NPU 12-way systolic engine.
Uses Kaiser-windowed sinc interpolation with polyphase decimation/interpolation to eliminate aliasing.
"""

import numpy as np
from scipy import signal
from fractions import Fraction

def resample_vibration_signal(x: np.ndarray, orig_fs: float, target_fs: float = 12000.0) -> np.ndarray:
    """
    Resamples 1D vibration array x from orig_fs to target_fs.
    Uses polyphase filtering via scipy.signal.resample_poly with rational factor L/M.
    """
    if abs(orig_fs - target_fs) < 1.0:
        return x.astype(np.float32)
    
    # Approximate rational fraction with small denominator (limit_denominator=100)
    frac = Fraction(target_fs / orig_fs).limit_denominator(100)
    up, down = frac.numerator, frac.denominator
    
    resampled = signal.resample_poly(x, up, down, axis=0)
    return resampled.astype(np.float32)


def warp_order_spectrum(spectrum: np.ndarray, source_rpm: float = 1750.0, target_rpm: float = 1500.0,
                        source_geom_multiplier: float = 3.05, target_geom_multiplier: float = 5.41,
                        num_bins: int = 257) -> np.ndarray:
    """
    Kinematic Order Tracking & Frequency Warping for Zero-Shot Cross-Machine Transfer.
    Maps a 257-bin spectrum from target machine coordinates (e.g. MFPT @ 16-ball, 1500 RPM)
    onto the source machine coordinate space (e.g. CWRU @ 9-ball, 1750 RPM).
    
    Formula:
      gamma = (target_rpm / source_rpm) * (target_geom_multiplier / source_geom_multiplier)
    Linearly resamples the frequency bins so characteristic fault peaks align with source bins.
    """
    spectrum = np.asarray(spectrum, dtype=np.float32).flatten()
    n = len(spectrum)
    gamma = float((target_rpm / max(1.0, source_rpm)) * (target_geom_multiplier / max(1e-5, source_geom_multiplier)))
    if abs(gamma - 1.0) < 0.01:
        return spectrum
    
    orig_indices = np.arange(n, dtype=np.float32)
    warped_indices = orig_indices * gamma
    warped_spec = np.interp(orig_indices, warped_indices, spectrum, left=float(spectrum[0]), right=float(spectrum[-1]))
    return warped_spec.astype(np.float32)
