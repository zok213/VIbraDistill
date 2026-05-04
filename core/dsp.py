import numpy as np
import scipy.signal as signal
from scipy.fft import fft, ifft

def fast_kurtogram(x, fs=25600, max_level=5):
    """
    Computes a simplified 1D Fast Kurtogram to find the resonance frequency band.
    Returns the center frequency and bandwidth with highest kurtosis.
    """
    best_kurt = -np.inf
    best_fc = 0
    best_bw = 0
    
    n = len(x)
    for level in range(1, max_level + 1):
        num_bands = 2**level
        bw = (fs / 2) / num_bands
        
        for i in range(num_bands):
            fc = bw * i + bw / 2
            
            # Simple bandpass
            nyq = fs / 2
            low = max(0.01, (fc - bw/2) / nyq)
            high = min(0.99, (fc + bw/2) / nyq)
            
            b, a = signal.butter(3, [low, high], btype='band')
            filtered = signal.lfilter(b, a, x)
            
            # Compute kurtosis
            kurt = np.mean((filtered - np.mean(filtered))**4) / (np.var(filtered)**2 + 1e-8) - 3
            
            if kurt > best_kurt:
                best_kurt = kurt
                best_fc = fc
                best_bw = bw
                
    return best_fc, best_bw, best_kurt

def design_minimum_phase_fir(num_taps, bands, desired, fs):
    """
    Designs a causal Minimum-Phase FIR filter via homomorphic transformation
    to minimize group delay for edge latency constraints.
    """
    # 1. Design linear phase prototype
    linear_taps = signal.firls(num_taps*2 - 1, bands, desired, fs=fs)
    
    # 2. Homomorphic conversion to minimum phase
    # Compute cepstrum
    fft_taps = fft(linear_taps, 2048)
    cepstrum = ifft(np.log(np.abs(fft_taps) + 1e-10))
    
    # 3. Fold cepstrum
    cepstrum[1:1024] *= 2
    cepstrum[1025:] = 0
    
    # 4. Invert to get minimum phase sequence
    min_phase_taps = np.real(ifft(np.exp(fft(cepstrum))))
    return min_phase_taps[:num_taps]

def autocorr_rpm_estimator(vibration_signal, fs=25600, min_rpm=1500, max_rpm=4000):
    """
    Robust Autocorrelation-based RPM estimation.
    """
    autocorr = signal.correlate(vibration_signal, vibration_signal, mode='full')
    autocorr = autocorr[len(autocorr)//2:]
    
    min_lag = int(fs / (max_rpm / 60))
    max_lag = int(fs / (min_rpm / 60))
    
    peak_lag = np.argmax(autocorr[min_lag:max_lag]) + min_lag
    estimated_rpm = (fs / peak_lag) * 60
    return estimated_rpm

def causal_stft(x, fs, nperseg=256, noverlap=128):
    """
    True Causal STFT dropping partial frames to prevent lookahead leakage.
    Uses boundary=None and padded=False.
    """
    f, t, Zxx = signal.stft(x, fs=fs, window='hann', nperseg=nperseg, 
                            noverlap=noverlap, boundary=None, padded=False)
    return f, t, np.abs(Zxx)
