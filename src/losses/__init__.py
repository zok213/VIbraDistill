"""
Loss Functions & Uncertainty Calibration for VibraDistill-Edge.
"""

from .dkd_loss import DecoupledKnowledgeDistillationLoss, dkd_loss
from .edl_loss import EvidentialLoss, compute_dirichlet_vacuity

__all__ = [
    "DecoupledKnowledgeDistillationLoss",
    "dkd_loss",
    "EvidentialLoss",
    "compute_dirichlet_vacuity",
]
