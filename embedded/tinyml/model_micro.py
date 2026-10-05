"""
VibraDistill-Micro: Frequency-Aware Lightweight 1D-CNN with Physics-Mechanism Prior Fusion
Designed for Sonix SN34F788 (ARM Cortex-M4F @ 192 MHz) with ARM CMSIS-NN INT8 SIMD Execution.

Key Architectural Components:
1. Multi-Scale Frequency-Aware Inception Block (Tian et al., MDPI Sensors, Sept 2026):
   - Branch 1: k=3  (Isolated defect peaks: 1x BPFO, 1x BPFI)
   - Branch 2: k=7  (Harmonic pairs: 2x, 3x BPFO/BPFI)
   - Branch 3: k=15 (Modulation sideband clusters: BPFI +/- n*fr)
2. Physics-Mechanism Prior Fusion Head (Niu & Lu, Springer Nature, Sept 2026):
   - Injects 4-dimensional kinematic energy prior vector: [BPFO, BPFI, BSF, FTF]
3. Decoupled Knowledge Distillation (DKD) Loss (Liao et al., IEEE TIM 2024; Zhao et al., CVPR 2022):
   - Exact tau^2 = 25.0 gradient normalization factor.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class MultiScaleFALBlock(nn.Module):
    """
    Multi-Scale Frequency-Aware Inception Block.
    Processes 257-bin Gowin FPGA envelope spectrum across 3 distinct receptive scales.
    """
    def __init__(self, in_channels=1, out_channels_per_branch=8):
        super(MultiScaleFALBlock, self).__init__()
        # Branch 1: Narrow kernel for isolated Dirac-like harmonics
        self.conv_k3 = nn.Conv1d(in_channels, out_channels_per_branch, kernel_size=3, padding=1, bias=True)
        # Branch 2: Medium kernel for harmonic pairs
        self.conv_k7 = nn.Conv1d(in_channels, out_channels_per_branch, kernel_size=7, padding=3, bias=True)
        # Branch 3: Wide kernel for modulation sideband families
        self.conv_k15 = nn.Conv1d(in_channels, out_channels_per_branch, kernel_size=15, padding=7, bias=True)
        
        self.bn = nn.BatchNorm1d(out_channels_per_branch * 3)
        self.relu = nn.ReLU()
        self.pool = nn.MaxPool1d(kernel_size=2, stride=2)  # 257 -> 128

    def forward(self, x):
        f3 = self.conv_k3(x)
        f7 = self.conv_k7(x)
        f15 = self.conv_k15(x)
        out = torch.cat([f3, f7, f15], dim=1)  # 24 channels
        out = self.bn(out)
        out = self.relu(out)
        out = self.pool(out)
        return out

class VibraDistillMicro(nn.Module):
    """
    Edge-deployable 1D-CNN footprint (<30k parameters, <30 KB INT8 weights).
    """
    def __init__(self, in_bins=257, num_classes=4, physics_dim=4):
        super(VibraDistillMicro, self).__init__()
        self.in_bins = in_bins
        self.physics_dim = physics_dim
        
        # Stage 1: Multi-scale inception (1 -> 24 channels, 257 -> 128 bins)
        self.stage1 = MultiScaleFALBlock(in_channels=1, out_channels_per_branch=8)
        
        # Stage 2: Depthwise separable / standard conv (24 -> 32 channels, 128 -> 64 bins)
        self.stage2 = nn.Sequential(
            nn.Conv1d(24, 32, kernel_size=5, padding=2, bias=True),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2, stride=2)  # 128 -> 64
        )
        
        # Stage 3: Feature aggregation (32 -> 16 channels, 64 -> 32 bins)
        self.stage3 = nn.Sequential(
            nn.Conv1d(32, 16, kernel_size=3, padding=1, bias=True),
            nn.BatchNorm1d(16),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(4)  # Pool to 4 spatial features -> 16 * 4 = 64 dims
        )
        
        # Learned spectral embedding: 64 dimensions
        self.embedding_dim = 64
        
        # Physics fusion layer: 64 spectral features + 4 kinematic prior features = 68 dims
        self.fusion_fc = nn.Sequential(
            nn.Linear(self.embedding_dim + physics_dim, 32),
            nn.ReLU()
        )
        
        # Diagnostic Classifier Head: Normal, Inner Race, Outer Race, Ball
        self.classifier = nn.Linear(32, num_classes)
        
        # Prognostic RUL Head: Normalized remaining life [0.0, 1.0]
        self.rul_head = nn.Sequential(
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )

    def forward(self, x, physics_prior=None):
        """
        x: [B, 1, 257] Gowin envelope spectrum bins
        physics_prior: [B, 4] kinematic energy ratios [BPFO, BPFI, BSF, FTF]
        """
        if x.dim() == 2:
            x = x.unsqueeze(1)
            
        f1 = self.stage1(x)
        f2 = self.stage2(f1)
        f3 = self.stage3(f2)
        
        spec_embed = f3.view(f3.size(0), -1)  # [B, 64]
        
        if physics_prior is None:
            # Fallback zero prior if not provided
            physics_prior = torch.zeros(x.size(0), self.physics_dim, device=x.device)
        else:
            # Amplitude balance: scale binary prior {0, 1} by 3.0 to match spec_embed dynamic range
            physics_prior = physics_prior * 3.0
            
        fused = torch.cat([spec_embed, physics_prior], dim=1)  # [B, 68]
        feat = self.fusion_fc(fused)                           # [B, 32]
        
        logits = self.classifier(feat)                         # [B, 4]
        rul = self.rul_head(feat)                              # [B, 1]
        
        return logits, rul

class DecoupledKnowledgeDistillationLoss(nn.Module):
    """
    Decoupled Knowledge Distillation (DKD) with mathematically proved tau^2 normalization.
    L_total = L_CE + alpha * TCKD + beta * NCKD
    """
    def __init__(self, alpha=1.0, beta=2.0, temperature=5.0):
        super(DecoupledKnowledgeDistillationLoss, self).__init__()
        self.alpha = alpha
        self.beta = beta
        self.temperature = temperature
        self.tau2 = temperature * temperature  # tau^2 = 25.0 gradient scale compensation
        self.ce_loss = nn.CrossEntropyLoss()

    def forward(self, logits_student, logits_teacher, target):
        # Standard Cross-Entropy
        loss_ce = self.ce_loss(logits_student, target)
        
        # Softened probabilities
        p_s = F.softmax(logits_student / self.temperature, dim=1)
        p_t = F.softmax(logits_teacher / self.temperature, dim=1)
        
        # Mask for target class
        batch_size = logits_student.size(0)
        target_mask = torch.zeros_like(p_s, dtype=torch.bool)
        target_mask.scatter_(1, target.unsqueeze(1), True)
        
        # 1. Target Class Probability
        pt_s = p_s[target_mask].view(batch_size, 1)
        pt_t = p_t[target_mask].view(batch_size, 1)
        
        # Binary probabilities for TCKD: [pt, 1 - pt]
        prob_s_bin = torch.cat([pt_s, 1.0 - pt_s], dim=1)
        prob_t_bin = torch.cat([pt_t, 1.0 - pt_t], dim=1)
        
        tckd = self.tau2 * F.kl_div(prob_s_bin.log(), prob_t_bin, reduction='batchmean')
        
        # 2. Non-Target Class Relative Probabilities
        non_target_s = p_s[~target_mask].view(batch_size, -1)
        non_target_t = p_t[~target_mask].view(batch_size, -1)
        
        # Renormalize among non-targets
        norm_s = non_target_s / (1.0 - pt_s + 1e-7)
        norm_t = non_target_t / (1.0 - pt_t + 1e-7)
        
        nckd = self.tau2 * F.kl_div(norm_s.log(), norm_t, reduction='batchmean')
        
        loss_total = loss_ce + self.alpha * tckd + self.beta * nckd
        return loss_total, loss_ce, tckd, nckd

if __name__ == '__main__':
    model = VibraDistillMicro()
    dummy_x = torch.randn(2, 1, 257)
    dummy_prior = torch.rand(2, 4)
    logits, rul = model(dummy_x, dummy_prior)
    
    total_params = sum(p.numel() for p in model.parameters())
    print(f"VibraDistillMicro initialized successfully.")
    print(f"Total Parameters: {total_params} (~{total_params / 1024:.2f} kParams)")
    print(f"INT8 Footprint Estimate: ~{total_params / 1024:.2f} KB")
    print(f"Logits shape: {logits.shape}, RUL shape: {rul.shape}")
