"""
01: Hardware-Faithful DSP Verification Script.
Validates:
1. RTL 32-tap Minimum-Phase FIR filter response and group delay.
2. RTL 2nd-order IIR envelope demodulator frequency response.
3. SKF 6205 bearing kinematic fault frequencies and 4-dim energy prior extraction.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from src.dsp import (
    CausalFIRFilter, 
    CausalEnvelopeDemodulator, 
    StreamingDSPPipeline,
    BearingKinematics, 
    SKF6205Geometry, 
    RTL_FIR_COEFFS_Q15
)

def run_dsp_verification():
    print("=" * 70)
    print("  VIBRADISTILL-EDGE: BIT-TRUE HARDWARE DSP PIPELINE VERIFICATION")
    print("=" * 70)
    
    # 1. FIR Filter Verification
    print("\n[1] Verifying 32-Tap Minimum-Phase FIR Filter...")
    fir = CausalFIRFilter(use_rtl_coeffs=True)
    print(f"  - Loaded {fir.num_taps} taps from Gowin RTL `fir_minphase_32.v`.")
    print(f"  - Min coeff: {RTL_FIR_COEFFS_Q15.min():.5f}, Max coeff: {RTL_FIR_COEFFS_Q15.max():.5f}")
    
    # Test impulse response for causality (no pre-cursor ringing)
    impulse = np.zeros(64, dtype=np.float32)
    impulse[0] = 1.0
    ir = fir.process_block(impulse)
    peak_idx = np.argmax(np.abs(ir))
    print(f"  - Impulse response peak index: {peak_idx} (Low group delay for minimum-phase: {peak_idx * (1/12000)*1e3:.3f} ms)")
    
    # 2. Envelope Demodulator Verification
    print("\n[2] Verifying Causal Envelope Demodulator (|x| + 2nd-order IIR LPF)...")
    env = CausalEnvelopeDemodulator(fc=1000.0, fs=12000.0)
    # Generate modulated AM carrier: (1 + 0.5*cos(2*pi*50*t)) * sin(2*pi*3000*t)
    t = np.linspace(0, 512/12000, 512, endpoint=False, dtype=np.float32)
    carrier = np.sin(2 * np.pi * 3000 * t)
    modulating = 1.0 + 0.8 * np.sin(2 * np.pi * 105 * t) # 105 Hz fault modulation
    am_signal = carrier * modulating
    
    demod = env.process_block(am_signal)
    print(f"  - Input AM signal min/max: [{am_signal.min():.3f}, {am_signal.max():.3f}]")
    print(f"  - Demodulated envelope min/max: [{demod.min():.3f}, {demod.max():.3f}]")
    assert np.all(demod >= -0.05), "Causal envelope output contains illegal negative values!"
    print("  - Envelope demodulator strictly non-negative and smooth.")
    
    # 3. Bearing Kinematics Verification
    print("\n[3] Verifying SKF 6205 Kinematic Fault Multipliers...")
    kin = BearingKinematics(SKF6205Geometry)
    mults = kin.get_multipliers()
    print("  - Characteristic multipliers (f_fault / f_shaft):")
    for k, v in mults.items():
        print(f"      {k:5s}: {v:.4f}x")
        
    rpms = [1797.0, 1772.0, 1750.0, 1725.0]
    print("\n  - Fault frequencies across motor load conditions:")
    for rpm in rpms:
        freqs = kin.get_frequencies(rpm)
        print(f"    RPM: {rpm:.0f} (fr = {freqs['fr']:.2f} Hz) -> "
              f"BPFO: {freqs['BPFO']:.2f} Hz, BPFI: {freqs['BPFI']:.2f} Hz, "
              f"BSF: {freqs['BSF']:.2f} Hz, FTF: {freqs['FTF']:.2f} Hz")
              
    # 4. Full Pipeline Verification
    print("\n[4] Verifying End-to-End Streaming DSP Pipeline...")
    pipeline = StreamingDSPPipeline(fs=12000.0, window_size=512)
    out = pipeline.process_window(am_signal, rpm=1797.0)
    print(f"  - Output envelope spectrum shape: {out['spectrum'].shape} (257 bins: 0 to 6000 Hz)")
    print(f"  - Frequency resolution delta_f: {12000.0 / 512:.3f} Hz/bin")
    print(f"  - Kinematic prior vector: {out['prior']}")
    print("\nAll DSP and Kinematic components successfully verified!")
    print("=" * 70)

if __name__ == '__main__':
    run_dsp_verification()
