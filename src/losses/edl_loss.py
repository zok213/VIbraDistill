"""
Evidential Deep Learning (EDL) Loss & Dirichlet Vacuity Quantification.
Based on: Sensoy et al., "Evidential Deep Learning to Quantify Classification Uncertainty", NeurIPS 2018.

Quantifies epistemic uncertainty (Vacuity u = K/S) to reject Out-of-Distribution (OOD)
novel mechanical fault anomalies directly on edge silicon without Monte Carlo sampling.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

def relu_evidence(logits: torch.Tensor) -> torch.Tensor:
    return F.relu(logits)

def softplus_evidence(logits: torch.Tensor) -> torch.Tensor:
    return F.softplus(logits)

def robust_evidence(logits: torch.Tensor, evidence_type: str = 'elu') -> torch.Tensor:
    """
    Robust Evidence function avoiding gradient vanishing on tiny models.
    ELU+1 gives non-vanishing gradient for negative logits and linear growth for positive logits.
    """
    clamped = torch.clamp(logits, -10.0, 10.0)
    if evidence_type == 'elu':
        return F.elu(clamped) + 1.0 + 1e-4
    elif evidence_type == 'exp':
        return torch.exp(clamped / 2.0)
    else:
        return F.softplus(clamped)

def compute_dirichlet_vacuity(logits: torch.Tensor, evidence_type: str = 'elu') -> tuple:
    """
    Computes expected class probabilities and epistemic uncertainty (Vacuity u = K/S).
    
    Args:
        logits: [B, K] output logits from model classifier
        evidence_type: 'elu', 'softplus', or 'exp'
        
    Returns:
        tuple: (probabilities [B, K], vacuity [B])
    """
    evidence = robust_evidence(logits, evidence_type=evidence_type)
    alpha = evidence + 1.0
    s = torch.sum(alpha, dim=1, keepdim=True) # [B, 1]
    prob = alpha / s                         # [B, K]
    k = float(logits.size(1))
    vacuity = (k / s).squeeze(-1)             # [B]
    return prob, vacuity

def kl_dirichlet_uniform(alpha: torch.Tensor) -> torch.Tensor:
    """
    Computes KL divergence: KL(Dir(alpha_tilde) || Dir(1)).
    Penalizes misleading evidence on non-ground-truth classes.
    """
    k = alpha.size(1)
    beta = torch.ones_like(alpha)
    s_alpha = torch.sum(alpha, dim=1, keepdim=True)
    s_beta = torch.sum(beta, dim=1, keepdim=True)
    
    ln_b_alpha = torch.sum(torch.lgamma(alpha), dim=1, keepdim=True) - torch.lgamma(s_alpha)
    ln_b_beta = torch.sum(torch.lgamma(beta), dim=1, keepdim=True) - torch.lgamma(s_beta)
    
    dg_alpha = torch.digamma(alpha)
    dg_s_alpha = torch.digamma(s_alpha)
    
    diff_dg = torch.sum((alpha - beta) * (dg_alpha - dg_s_alpha), dim=1, keepdim=True)
    kl = ln_b_beta - ln_b_alpha + diff_dg
    return kl.squeeze(-1)

class EvidentialLoss(nn.Module):
    """
    Evidential Cross-Entropy Loss with Annealed KL Divergence Regularization.
    """
    def __init__(self, num_classes: int = 4, annealing_epochs: int = 10, evidence_type: str = 'elu'):
        super(EvidentialLoss, self).__init__()
        self.num_classes = num_classes
        self.annealing_epochs = annealing_epochs
        self.evidence_type = evidence_type
        
    def forward(self, logits: torch.Tensor, target: torch.Tensor, epoch: int = 0):
        y_one_hot = F.one_hot(target, num_classes=self.num_classes).float()
        
        evidence = robust_evidence(logits, evidence_type=self.evidence_type)
        alpha = evidence + 1.0
        s = torch.sum(alpha, dim=1, keepdim=True)
        
        # 1. Expected Cross-Entropy: E[ -log(p_y) ] = psi(S) - psi(alpha_y)
        loss_ace = torch.sum(y_one_hot * (torch.digamma(s) - torch.digamma(alpha)), dim=1)
        
        # 2. Annealed KL divergence regularization for non-target evidence
        annealing_coef = min(1.0, float(epoch) / max(1, self.annealing_epochs))
        alpha_tilde = y_one_hot + (1.0 - y_one_hot) * alpha
        loss_kl = kl_dirichlet_uniform(alpha_tilde)
        
        loss_total = torch.mean(loss_ace + annealing_coef * loss_kl)
        return loss_total
