"""
Backward-compatibility forwarder for legacy imports.
Redirects to the canonical `src` package.
"""

from src.dsp import (
    CausalFIRFilter, 
    CausalEnvelopeDemodulator, 
    StreamingDSPPipeline,
    compute_kinematic_frequencies, 
    extract_kinematic_energy_prior
)
from src.models import VibraDistillMicro, Teacher1DResNet
from src.losses import DecoupledKnowledgeDistillationLoss, EvidentialLoss, dkd_loss
from src.datasets import CWRUBearingDataset, get_cwru_dataloaders

__all__ = [
    "CausalFIRFilter",
    "CausalEnvelopeDemodulator",
    "StreamingDSPPipeline",
    "compute_kinematic_frequencies",
    "extract_kinematic_energy_prior",
    "VibraDistillMicro",
    "Teacher1DResNet",
    "DecoupledKnowledgeDistillationLoss",
    "EvidentialLoss",
    "dkd_loss",
    "CWRUBearingDataset",
    "get_cwru_dataloaders",
]
