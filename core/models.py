import torch
import torch.nn as nn

class SELayer(nn.Module):
    """
    Squeeze-and-Excitation (SE) Block using Hardsigmoid for NVDLA INT8 Native execution.
    """
    def __init__(self, channel, length, reduction=16):
        super(SELayer, self).__init__()
        # Use static pooling instead of AdaptiveAvgPool1d to avoid CUDA fallbacks
        self.avg_pool = nn.AvgPool1d(length) 
        self.fc = nn.Sequential(
            nn.Linear(channel, channel // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channel // reduction, channel, bias=False),
            nn.Hardsigmoid()
        )

    def forward(self, x):
        b, c, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1)
        return x * y.expand_as(x)

class Student1DCNN(nn.Module):
    """
    Ultra-lightweight 1D-CNN Student model (20.4k params).
    Target: Jetson Orin NX (NVDLA).
    """
    def __init__(self, num_classes=10):
        super(Student1DCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=15, stride=2, padding=7),
            nn.BatchNorm1d(16),
            nn.ReLU(inplace=True),
            SELayer(16, length=128, reduction=4),
            nn.MaxPool1d(2),
            
            nn.Conv1d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
            SELayer(32, length=64, reduction=8),
            nn.MaxPool1d(2),
            
            nn.Conv1d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            SELayer(64, length=32, reduction=16),
            nn.AvgPool1d(32) # Static pool (32 -> 1)
        )
        self.classifier = nn.Linear(64, num_classes)
        
        # Projection head for DKD feature matching (Student 64 -> Teacher 128)
        self.projector = nn.Linear(64, 128)

    def forward(self, x, return_features=False):
        f = self.features(x).squeeze(-1)
        out = self.classifier(f)
        if return_features:
            return out, self.projector(f)
        return out
