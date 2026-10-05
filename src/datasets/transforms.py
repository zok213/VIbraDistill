"""
Physics-Preserving Data Augmentations for Bearing Vibration Signals.
Operates on raw 1D time-domain vibration windows prior to DSP feature extraction.
"""

import numpy as np

class RandomNoise:
    """
    Injects Additive White Gaussian Noise (AWGN) based on a target Signal-to-Noise Ratio (SNR).
    """
    def __init__(self, snr_db_min=12.0, snr_db_max=25.0, p=0.5):
        self.snr_min = float(snr_db_min)
        self.snr_max = float(snr_db_max)
        self.p = float(p)
        
    def __call__(self, x: np.ndarray) -> np.ndarray:
        if np.random.rand() > self.p:
            return x
            
        signal_power = np.mean(x ** 2) + 1e-12
        target_snr_db = np.random.uniform(self.snr_min, self.snr_max)
        snr_linear = 10.0 ** (target_snr_db / 10.0)
        noise_power = signal_power / snr_linear
        noise = np.random.normal(0, np.sqrt(noise_power), size=x.shape).astype(np.float32)
        return x + noise

class RandomCyclicShift:
    """
    Circularly rotates the 1D signal window.
    Preserves periodic fault impact physics while jittering window alignment phase.
    """
    def __init__(self, max_shift=128, p=0.5):
        self.max_shift = int(max_shift)
        self.p = float(p)
        
    def __call__(self, x: np.ndarray) -> np.ndarray:
        if np.random.rand() > self.p:
            return x
        shift = np.random.randint(-self.max_shift, self.max_shift + 1)
        return np.roll(x, shift)

class RandomScale:
    """
    Simulates dynamic load fluctuation by scaling signal amplitude.
    """
    def __init__(self, scale_min=0.85, scale_max=1.15, p=0.5):
        self.scale_min = float(scale_min)
        self.scale_max = float(scale_max)
        self.p = float(p)
        
    def __call__(self, x: np.ndarray) -> np.ndarray:
        if np.random.rand() > self.p:
            return x
        factor = np.random.uniform(self.scale_min, self.scale_max)
        return x * factor

class ComposeTransforms:
    """Chains multiple transforms sequentially."""
    def __init__(self, transforms):
        self.transforms = transforms
        
    def __call__(self, x: np.ndarray) -> np.ndarray:
        for t in self.transforms:
            x = t(x)
        return x
