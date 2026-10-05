"""
Decoupled Knowledge Distillation (DKD) Loss.
Based on: Zhao et al., "Decoupled Knowledge Distillation", CVPR 2022.
Adapted for Edge TinyML Vibration Diagnostic Distillation.

Key Formulation:
  L_DKD = alpha * TCKD + beta * NCKD
where:
  - TCKD transfers knowledge about the target class probability.
  - NCKD transfers rich non-target inter-class semantic correlations.
  - Scaled by tau^2 = 25.0 for gradient magnitude normalization.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

def _get_gt_mask(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    target = target.reshape(-1)
    mask = torch.zeros_like(logits, dtype=torch.bool).scatter_(1, target.unsqueeze(1), True)
    return mask

def _get_other_mask(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    target = target.reshape(-1)
    mask = torch.ones_like(logits, dtype=torch.bool).scatter_(1, target.unsqueeze(1), False)
    return mask

def cat_mask(t: torch.Tensor, mask1: torch.Tensor, mask2: torch.Tensor) -> torch.Tensor:
    t1 = (t * mask1).sum(dim=1, keepdim=True)
    t2 = (t * mask2).sum(dim=1, keepdim=True)
    return torch.cat([t1, t2], dim=1)

def dkd_loss(logits_student: torch.Tensor, logits_teacher: torch.Tensor, 
             target: torch.Tensor, alpha: float = 1.0, beta: float = 2.0, 
             temperature: float = 5.0) -> torch.Tensor:
    """
    Computes Decoupled Knowledge Distillation Loss.
    """
    gt_mask = _get_gt_mask(logits_student, target)
    other_mask = _get_other_mask(logits_student, target)
    
    # Soften logits by temperature tau
    pred_s = F.softmax(logits_student / temperature, dim=1)
    pred_t = F.softmax(logits_teacher / temperature, dim=1)
    
    # Binary probabilities for TCKD: [p_target, 1 - p_target]
    pred_s_bin = cat_mask(pred_s, gt_mask, other_mask)
    pred_t_bin = cat_mask(pred_t, gt_mask, other_mask)
    
    # TCKD: Binary KL divergence
    log_pred_s_bin = torch.log(pred_s_bin + 1e-8)
    tckd = F.kl_div(log_pred_s_bin, pred_t_bin, reduction='batchmean')
    
    # NCKD: Relative non-target distribution
    # Reshape non-target probabilities per sample
    batch_size = logits_student.size(0)
    pred_s_other = pred_s[other_mask].view(batch_size, -1)
    pred_t_other = pred_t[other_mask].view(batch_size, -1)
    
    # Renormalize among non-targets
    norm_s = pred_s_other / (pred_s_other.sum(dim=1, keepdim=True) + 1e-8)
    norm_t = pred_t_other / (pred_t_other.sum(dim=1, keepdim=True) + 1e-8)
    
    log_norm_s = torch.log(norm_s + 1e-8)
    nckd = F.kl_div(log_norm_s, norm_t, reduction='batchmean')
    
    # Scale by tau^2 for gradient conservation
    tau2 = temperature * temperature
    return tau2 * (alpha * tckd + beta * nckd)

class DecoupledKnowledgeDistillationLoss(nn.Module):
    """
    PyTorch Module wrapper for Decoupled Knowledge Distillation.
    Combined loss:
      L_total = L_CE + alpha * TCKD + beta * NCKD
    """
    def __init__(self, alpha: float = 1.0, beta: float = 2.0, temperature: float = 5.0, ce_weight: float = 1.0):
        super(DecoupledKnowledgeDistillationLoss, self).__init__()
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.temperature = float(temperature)
        self.ce_weight = float(ce_weight)
        self.ce_loss = nn.CrossEntropyLoss()
        
    def forward(self, logits_student: torch.Tensor, logits_teacher: torch.Tensor, target: torch.Tensor):
        loss_ce = self.ce_loss(logits_student, target)
        loss_dkd = dkd_loss(
            logits_student=logits_student,
            logits_teacher=logits_teacher,
            target=target,
            alpha=self.alpha,
            beta=self.beta,
            temperature=self.temperature
        )
        total_loss = self.ce_weight * loss_ce + loss_dkd
        return total_loss, loss_ce, loss_dkd
