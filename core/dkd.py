import torch
import torch.nn.functional as F

def dkd_loss(logits_student, logits_teacher, target, alpha, beta, temperature):
    """
    Decoupled Knowledge Distillation (DKD) Loss with Full Binary KL Fix.
    """
    gt_mask = _get_gt_mask(logits_student, target)
    other_mask = _get_other_mask(logits_student, target)
    
    pred_student = F.softmax(logits_student / temperature, dim=1)
    pred_teacher = F.softmax(logits_teacher / temperature, dim=1)
    
    pred_student = cat_mask(pred_student, gt_mask, other_mask)
    pred_teacher = cat_mask(pred_teacher, gt_mask, other_mask)
    
    log_pred_student = torch.log(pred_student + 1e-8)
    
    # Target-Class Knowledge Distillation (TCKD) - Full Binary KL
    tckd_loss = (
        F.kl_div(log_pred_student[:, 0:1], pred_teacher[:, 0:1], reduction='batchmean') +
        F.kl_div(torch.log(1 - pred_student[:, 0:1] + 1e-8), 1 - pred_teacher[:, 0:1], reduction='batchmean')
    )
    
    # Non-Target Class Knowledge Distillation (NCKD)
    pred_student_other = F.softmax(logits_student[other_mask].view(logits_student.size(0), -1) / temperature, dim=1)
    pred_teacher_other = F.softmax(logits_teacher[other_mask].view(logits_teacher.size(0), -1) / temperature, dim=1)
    
    nckd_loss = F.kl_div(torch.log(pred_student_other + 1e-8), pred_teacher_other, reduction='batchmean')
    
    return alpha * tckd_loss + beta * nckd_loss

def _get_gt_mask(logits, target):
    target = target.reshape(-1)
    mask = torch.zeros_like(logits).scatter_(1, target.unsqueeze(1), 1).bool()
    return mask

def _get_other_mask(logits, target):
    target = target.reshape(-1)
    mask = torch.ones_like(logits).scatter_(1, target.unsqueeze(1), 0).bool()
    return mask

def cat_mask(t, mask1, mask2):
    t1 = (t * mask1).sum(dim=1, keepdims=True)
    t2 = (t * mask2).sum(1, keepdims=True)
    rt = torch.cat([t1, t2], dim=1)
    return rt

def adaptive_norm_cosine_loss(f_s, f_t):
    """
    Adaptive Norm-Regularized Cosine Similarity to prevent magnitude collapse.
    """
    cos_sim = 1 - F.cosine_similarity(f_s, f_t).mean()
    norm_s = torch.norm(f_s, p=1, dim=1)
    norm_t = torch.norm(f_t, p=1, dim=1)
    
    adaptive_weight = 0.1 / (norm_t.mean() + 1e-8)
    norm_loss = F.l1_loss(norm_s, norm_t) * adaptive_weight
    
    return cos_sim + norm_loss
