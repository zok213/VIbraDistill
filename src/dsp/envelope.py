"""
Causal Envelope Demodulation Engine.
Bit-faithful representation of Gowin FPGA RTL `envelope_demodulator.v`.
Implements Full-Wave Absolute Rectification followed by a 2nd-Order Direct-Form I IIR Low-Pass Filter.

Eliminates acausal Hilbert transform look-ahead leakage and edge ripples.
Supports two hardware profiles:
  - Profile 1: HIL CWRU / PRONOSTIA (Fs = 12,000 Hz, Fc = 1,200 Hz)
  - Profile 2: Native ADXL345       (Fs = 3,200 Hz,  Fc = 400 Hz)
"""

import numpy as np
import scipy.signal as signal

# ============================================================================
# Exact Q3.15 IIR Coefficients matching Gowin FPGA `envelope_demodulator.v`
# Multipliers use 18-bit signed coefficients scaled by 2^15 = 32768.
# ============================================================================

# Profile 1: HIL CWRU / PRONOSTIA (Fs = 12,000 Hz, Fc = 1,200 Hz, Butterworth 2nd-Order)
# Passband: preserves up to 7x-10x fault harmonics (BPFO ~107 Hz, BPFI ~162 Hz)
#   B0 =  2210  (18'sd2210)  ->  2210 / 32768 = 0.06744385
#   B1 =  4421  (18'sd4421)  ->  4421 / 32768 = 0.13491821
#   B2 =  2210  (18'sd2210)  ->  2210 / 32768 = 0.06744385
#   A1 = -37453 (18'sd-37453) -> -37453 / 32768 = -1.14297485
#   A2 =  13527 (18'sd13527)  ->  13527 / 32768 = 0.41281128
RTL_IIR_COEFFS_HIL = {
    'b': np.array([2210, 4421, 2210], dtype=np.float32) / 32768.0,
    'a': np.array([32768, -37453, 13527], dtype=np.float32) / 32768.0,
    'b_fixed': np.array([2210, 4421, 2210], dtype=np.int32),
    'a_fixed': np.array([32768, -37453, 13527], dtype=np.int32),
    'fs': 12000.0,
    'fc': 1200.0
}

# Profile 2: Native ADXL345 (Fs = 3,200 Hz, Fc = 400 Hz, Butterworth 2nd-Order)
# Passband: captures up to 4x motor defect harmonics
#   B0 =  3199  (18'sd3199)  ->  3199 / 32768 = 0.09762573
#   B1 =  6398  (18'sd6398)  ->  6398 / 32768 = 0.19525146
#   B2 =  3199  (18'sd3199)  ->  3199 / 32768 = 0.09762573
#   A1 = -30894 (18'sd-30894) -> -30894 / 32768 = -0.94281006
#   A2 =  10923 (18'sd10923)  ->  10923 / 32768 = 0.33334351
RTL_IIR_COEFFS_ADXL345 = {
    'b': np.array([3199, 6398, 3199], dtype=np.float32) / 32768.0,
    'a': np.array([32768, -30894, 10923], dtype=np.float32) / 32768.0,
    'b_fixed': np.array([3199, 6398, 3199], dtype=np.int32),
    'a_fixed': np.array([32768, -30894, 10923], dtype=np.int32),
    'fs': 3200.0,
    'fc': 400.0
}

# Default backwards-compatible alias (Profile 1: HIL 12 kHz)
RTL_IIR_COEFFS = RTL_IIR_COEFFS_HIL


def design_causal_iir_lpf(fc=1200.0, fs=12000.0, order=2):
    """
    Designs a causal 2nd-order Butterworth low-pass filter for envelope smoothing.
    
    Args:
        fc (float): 3dB cutoff frequency in Hz (default: 1200.0 Hz)
        fs (float): Sampling frequency in Hz (default: 12000.0 Hz)
        order (int): Filter order (default: 2)
        
    Returns:
        tuple: (b, a) filter polynomials as float32 numpy arrays
    """
    wn = fc / (fs / 2.0)
    wn = min(max(wn, 0.001), 0.999)
    b, a = signal.butter(order, wn, btype='low', analog=False)
    return b.astype(np.float32), a.astype(np.float32)


def simulate_rtl_envelope_fixed_point(samples_q15, use_adxl345=False):
    """
    Cycle-accurate and bit-true emulation of `envelope_demodulator.v`.
    
    Args:
        samples_q15: 1D array of 16-bit signed integer samples [-32768, 32767]
        use_adxl345 (bool): Selects Profile 2 (3.2 kHz / 400 Hz) if True,
                            else Profile 1 (12.0 kHz / 1200 Hz).
                            
    Returns:
        np.ndarray: 16-bit signed integer envelope output
    """
    coeffs = RTL_IIR_COEFFS_ADXL345 if use_adxl345 else RTL_IIR_COEFFS_HIL
    b0 = int(coeffs['b_fixed'][0])
    b1 = int(coeffs['b_fixed'][1])
    b2 = int(coeffs['b_fixed'][2])
    a1 = int(coeffs['a_fixed'][1])
    a2 = int(coeffs['a_fixed'][2])
    
    v_z1 = 0
    v_z2 = 0
    e_z1 = 0
    e_z2 = 0
    
    output = np.zeros(len(samples_q15), dtype=np.int16)
    for i, x in enumerate(samples_q15):
        # Step 1: Full-wave rectification with -32768 clamp
        if x == -32768:
            v_rect = 32767
        elif x < 0:
            v_rect = -x
        else:
            v_rect = int(x)
            
        # Stage 1: Multiply (16-bit input * 18-bit coeff = 34-bit signed product)
        prod_b0 = v_rect * b0
        prod_b1 = v_z1 * b1
        prod_b2 = v_z2 * b2
        prod_a1 = e_z1 * a1
        prod_a2 = e_z2 * a2
        
        v_z2 = v_z1
        v_z1 = v_rect
        
        # Stage 2: Accumulate (36-bit signed)
        accum = (prod_b0 + prod_b1 + prod_b2) - (prod_a1 + prod_a2)
        
        # Stage 3: Divide by 2^15 = 32768 with two's complement saturation
        if accum > 1073709056:      # 32767 * 32768
            env_val = 32767
        elif accum < -1073741824:   # -32768 * 32768
            env_val = -32768
        else:
            env_val = (accum >> 15)
            if env_val > 32767:
                env_val = 32767
            elif env_val < -32768:
                env_val = -32768
                
        e_z2 = e_z1
        e_z1 = env_val
        output[i] = env_val
        
    return output


class CausalEnvelopeDemodulator:
    """
    Streaming Causal Envelope Demodulator:
    Stage 1: Full-Wave Absolute Rectification: v_rect[n] = |x[n]|
    Stage 2: 2nd-Order Direct-Form I IIR Low-Pass Filter
    
    Matches Gowin FPGA 3-stage pipelined envelope engine.
    """
    def __init__(self, fc=1200.0, fs=12000.0, use_rtl_coeffs=False, profile=None):
        if profile == 'adxl345' or (abs(fs - 3200.0) < 100.0 and use_rtl_coeffs):
            self.b = RTL_IIR_COEFFS_ADXL345['b'].copy()
            self.a = RTL_IIR_COEFFS_ADXL345['a'].copy()
            self.fs = 3200.0
            self.fc = 400.0
        elif profile == 'hil_12k' or (use_rtl_coeffs and abs(fs - 12000.0) < 500.0):
            self.b = RTL_IIR_COEFFS_HIL['b'].copy()
            self.a = RTL_IIR_COEFFS_HIL['a'].copy()
            self.fs = 12000.0
            self.fc = 1200.0
        else:
            self.b, self.a = design_causal_iir_lpf(fc=fc, fs=fs, order=2)
            self.fs = float(fs)
            self.fc = float(fc)
            
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
