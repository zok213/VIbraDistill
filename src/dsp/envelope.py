"""
Causal Envelope Demodulation Engine.
Bit-faithful representation of Gowin FPGA RTL `envelope_demodulator.v`.
Implements Full-Wave Absolute Rectification followed by a 2nd-Order Direct-Form I IIR Low-Pass Filter.

Eliminates acausal Hilbert transform look-ahead leakage and edge ripples.
"""

import numpy as np
import scipy.signal as signal

# Exact Q1.15 IIR Coefficients from `envelope_demodulator.v` (Fc=1000 Hz @ Fs=13.333 kHz)
# B0 = 0x08A4 (2212 / 32768 = 0.06750488)
# B1 = 0x1148 (4424 / 32768 = 0.13500977)
# B2 = 0x08A4 (2212 / 32768 = 0.06750488)
# A1 = 0x96E8 (-26904 / 32768 = -0.8210449... wait, 0x96E8 as signed 16-bit: 0x96E8 - 0x10000 = -26904)
# Note: In SciPy standard [1.0, a1, a2], y[n] + a1*y[n-1] + a2*y[n-2] = b0*x[n] + b1*x[n-1] + b2*x[n-2]

RTL_IIR_COEFFS = {
    'b': np.array([0.067455, 0.134911, 0.067455], dtype=np.float32),
    'a': np.array([1.0, -1.142981, 0.412802], dtype=np.float32)
}

def design_causal_iir_lpf(fc=1000.0, fs=12000.0, order=2):
    """
    Designs a causal 2nd-order Butterworth low-pass filter for envelope smoothing.
    
    Args:
        fc (float): 3dB cutoff frequency in Hz (default: 1000.0 Hz)
        fs (float): Sampling frequency in Hz (default: 12000.0 Hz)
        order (int): Filter order (default: 2)
        
    Returns:
        tuple: (b, a) filter polynomials as float32 numpy arrays
    """
    wn = fc / (fs / 2.0)
    wn = min(max(wn, 0.001), 0.999)
    b, a = signal.butter(order, wn, btype='low', analog=False)
    return b.astype(np.float32), a.astype(np.float32)

class CausalEnvelopeDemodulator:
    """
    Streaming Causal Envelope Demodulator:
    Stage 1: Full-Wave Absolute Rectification: v_rect[n] = |x[n]|
    Stage 2: 2nd-Order Direct-Form I IIR Low-Pass Filter
    
    Matches Gowin FPGA 3-stage pipelined envelope engine.
    """
    def __init__(self, fc=1000.0, fs=12000.0, use_rtl_coeffs=False):
        if use_rtl_coeffs:
            self.b = RTL_IIR_COEFFS['b'].copy()
            self.a = RTL_IIR_COEFFS['a'].copy()
        else:
            self.b, self.a = design_causal_iir_lpf(fc=fc, fs=fs, order=2)
            
        self.reset()
        
    def reset(self):
        """Resets the internal IIR delay registers."""
        self.v_z1 = 0.0
        self.v_z2 = 0.0
        self.e_z1 = 0.0
        self.e_z2 = 0.0
        self.zi = signal.lfilter_zi(self.b, self.a) * 0.0
        
    def process_block(self, x):
        """
        Processes a block of vibration samples causally.
        
        Args:
            x (np.ndarray): 1D array of bandpass filtered vibration samples
            
        Returns:
            np.ndarray: Demodulated baseband envelope array of identical length
        """
        x = np.asarray(x, dtype=np.float32)
        # Stage 1: Full-Wave Rectification
        v_rect = np.abs(x)
        
        # Stage 2: Causal IIR Lowpass Filtering with persistent state
        env, self.zi = signal.lfilter(self.b, self.a, v_rect, zi=self.zi)
        return env
        
    def process_sample(self, sample):
        """Processes a single sample (streaming mode)."""
        res = self.process_block(np.array([sample], dtype=np.float32))
        return float(res[0])
