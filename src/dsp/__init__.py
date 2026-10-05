"""
Causal DSP & Kinematics Engine for VibraDistill-Edge.
Bit-true to Gowin FPGA RTL (fir_minphase_32.v and envelope_demodulator.v).
"""

from .causal_fir import CausalFIRFilter, design_minimum_phase_fir, RTL_FIR_COEFFS_Q15
from .envelope import CausalEnvelopeDemodulator, RTL_IIR_COEFFS
from .kinematics import (
    BearingKinematics, 
    SKF6205Geometry, 
    compute_kinematic_frequencies, 
    extract_kinematic_energy_prior,
    estimate_shaft_speed_tacholess
)
from .resample import resample_vibration_signal, warp_order_spectrum
from .pipeline import StreamingDSPPipeline

__all__ = [
    "CausalFIRFilter",
    "design_minimum_phase_fir",
    "RTL_FIR_COEFFS_Q15",
    "CausalEnvelopeDemodulator",
    "RTL_IIR_COEFFS",
    "BearingKinematics",
    "SKF6205Geometry",
    "compute_kinematic_frequencies",
    "extract_kinematic_energy_prior",
    "estimate_shaft_speed_tacholess",
    "resample_vibration_signal",
    "warp_order_spectrum",
    "StreamingDSPPipeline",
]
