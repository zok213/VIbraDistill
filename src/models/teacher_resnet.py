"""
Teacher 1D-ResNet Architecture for VibraDistill-Edge.
High-capacity residual network serving as the Oracle Teacher for Decoupled Knowledge Distillation (DKD).
Provides rich inter-class semantic correlations and soft probability targets.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class ResNet1DBlock(nn.Module):
    """Basic 1D Residual Block with 2 Conv1D layers and residual shortcut."""
    def __init__(self, in_channels: int, out_channels: int, stride: int = 1):
        super(ResNet1DBlock, self).__init__()
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm1d(out_channels)
        
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels)
            )
        else:
            self.shortcut = nn.Identity()
            
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = self.shortcut(x)
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = self.relu(out + res)
        return out

class Teacher1DResNet(nn.Module):
    """
    Teacher 1D-ResNet (~1.2M Parameters).
    Trained unconstrained on GPU/Server to extract high-order spectral representations.
    """
    def __init__(self, in_channels: int = 1, num_classes: int = 4, physics_dim: int = 4):
        super(Teacher1DResNet, self).__init__()
        self.num_classes = num_classes
        self.physics_dim = physics_dim
        
        # Stem: Conv1D(1, 32, k=7, s=2, p=3) -> 257 -> 129
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=7, stride=2, padding=3, bias=False),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2, padding=1) # 129 -> 65
        )
        
        # Stage 1: 32 channels (65 -> 65)
        self.stage1 = nn.Sequential(
            ResNet1DBlock(32, 32, stride=1),
            ResNet1DBlock(32, 32, stride=1)
        )
        
        # Stage 2: 64 channels (65 -> 33)
        self.stage2 = nn.Sequential(
            ResNet1DBlock(32, 64, stride=2),
            ResNet1DBlock(64, 64, stride=1)
        )
        
        # Stage 3: 128 channels (33 -> 17)
        self.stage3 = nn.Sequential(
            ResNet1DBlock(64, 128, stride=2),
            ResNet1DBlock(128, 128, stride=1)
        )
        
        # Stage 4: 256 channels (17 -> 9)
        self.stage4 = nn.Sequential(
            ResNet1DBlock(128, 256, stride=2),
            ResNet1DBlock(256, 256, stride=1)
        )
        
        self.global_pool = nn.AdaptiveAvgPool1d(1) # 256 -> 1
        
        # Physics Kinematic Fusion
        self.fc_fusion = nn.Sequential(
            nn.Linear(256 + physics_dim, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.2)
        )
        
        # Classifier & RUL Heads
        self.classifier = nn.Linear(128, num_classes)
        self.rul_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x: torch.Tensor, physics_prior: torch.Tensor = None, return_features: bool = False):
        if x.dim() == 2:
            x = x.unsqueeze(1)
            
        out = self.stem(x)
        out = self.stage1(out)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.stage4(out)
        
        feat = self.global_pool(out).squeeze(-1) # [B, 256]
        
        if physics_prior is None:
            physics_prior = torch.zeros(x.size(0), self.physics_dim, device=x.device)
        else:
            physics_prior = physics_prior * 3.0
            
        fused = torch.cat([feat, physics_prior], dim=1) # [B, 260]
        latent = self.fc_fusion(fused)                   # [B, 128]
        
        logits = self.classifier(latent)                 # [B, 4]
        rul = self.rul_head(latent)                      # [B, 1]
        
        if return_features:
            return logits, rul, latent
        return logits, rul
