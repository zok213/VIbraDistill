"""
Streaming DSP Pipeline for VibraDistill-Edge.
Chains:
  x[n] -> Causal 32-Tap FIR -> Causal Envelope Demodulator (|x| + IIR LPF)
       -> Hann Window -> 512-pt Real FFT -> 257-bin Envelope Spectrum
       -> Physics Kinematic Prior Extraction.

Matches the Gowin FPGA hardware streaming datapath cycle-for-cycle.
"""

import numpy as np
from .causal_fir import CausalFIRFilter
from .envelope import CausalEnvelopeDemodulator
from .kinematics import extract_kinematic_energy_prior, SKF6205Geometry

class StreamingDSPPipeline:
    """
    End-to-End DSP Preprocessing Pipeline bit-faithful to Gowin FPGA RTL.
    """
    def __init__(self, fs=12000.0, window_size=512, fir_taps=32, 
                 envelope_cutoff=1000.0, use_rtl_coeffs=True,
                 bearing_geom=SKF6205Geometry):
        self.fs = float(fs)
        self.window_size = int(window_size)
        self.bearing_geom = bearing_geom
        
        # Hardware Stage 1: Causal FIR Filter
        self.fir = CausalFIRFilter(use_rtl_coeffs=use_rtl_coeffs, num_taps=fir_taps, fs=fs)
        
        # Hardware Stage 2: Causal Envelope Demodulator
        self.envelope = CausalEnvelopeDemodulator(fc=envelope_cutoff, fs=fs, use_rtl_coeffs=False)
        
        # Hardware Stage 3: Hann Window (512-point fixed ROM in FPGA)
        self.hann_window = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(self.window_size) / (self.window_size - 1)))
        self.hann_window = self.hann_window.astype(np.float32)
        
    def reset(self):
        """Resets filter delay lines for clean state."""
        self.fir.reset()
        self.envelope.reset()
        
    def process_window(self, raw_samples: np.ndarray, rpm: float = 1797.0):
        """
        Processes a single 512-sample window through the causal FPGA DSP pipeline.
        
        Args:
            raw_samples (np.ndarray): 512 raw acceleration samples (float32)
            rpm (float): Measured or estimated shaft speed in RPM
            
        Returns:
            dict containing:
                - 'spectrum': np.ndarray of shape [257], normalized envelope spectrum
                - 'prior': np.ndarray of shape [4], kinematic energy prior vector
                - 'envelope_time': np.ndarray of shape [512], time-domain envelope
        """
        raw_samples = np.asarray(raw_samples, dtype=np.float32)
        assert len(raw_samples) == self.window_size, f"Expected {self.window_size} samples, got {len(raw_samples)}"
        
        # 1. Bandpass FIR Filter
        y_fir = self.fir.process_block(raw_samples)
        
        # 2. Envelope Demodulation (|x| + IIR LPF)
        env_time = self.envelope.process_block(y_fir)
        
        # 3. Hann Windowing
        windowed = env_time * self.hann_window
        
        # 4. 512-point Real FFT -> 257 positive frequency bins
        fft_complex = np.fft.rfft(windowed, n=self.window_size)
        spectrum_raw = np.abs(fft_complex).astype(np.float32) # [257]
        
        # 5. Normalization: scale maximum to 1.0 (prevents gradient saturation)
        max_val = float(np.max(spectrum_raw))
        if max_val > 1e-6:
            spectrum_norm = spectrum_raw / max_val
        else:
            spectrum_norm = spectrum_raw
            
        # 6. Extract Kinematic Prior Vector [p_BPFO, p_BPFI, p_BSF, p_FTF]
        prior = extract_kinematic_energy_prior(
            spectrum=spectrum_norm,
            rpm=rpm,
            fs=self.fs,
            n_fft=self.window_size,
            geometry=self.bearing_geom
        )
        
        return {
            'spectrum': spectrum_norm,
            'prior': prior,
            'envelope_time': env_time
        }
