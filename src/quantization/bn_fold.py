"""
Mathematically Exact BatchNorm Folding for VibraDistillMicro.
Folds BatchNorm gamma, beta, running_mean, and running_var directly into
Conv1D weight matrices and bias vectors.

Eliminates all runtime BatchNorm floating-point operations prior to INT8 quantization.
"""

import copy
import torch
import torch.nn as nn

def _fold_conv_bn_pair(conv: nn.Conv1d, bn: nn.BatchNorm1d, slice_idx=None) -> tuple:
    """
    Folds a BatchNorm1d layer into a Conv1d layer.
    Supports channel slicing for multi-branch inception blocks.
    """
    gamma = bn.weight
    beta = bn.bias
    mean = bn.running_mean
    var = bn.running_var
    eps = bn.eps
    
    if slice_idx is not None:
        gamma = gamma[slice_idx]
        beta = beta[slice_idx]
        mean = mean[slice_idx]
        var = var[slice_idx]
        
    std = torch.sqrt(var + eps)
    scale = gamma / std # [C_out]
    
    w = conv.weight # [C_out, C_in, K]
    w_folded = w * scale.view(-1, 1, 1)
    
    if conv.bias is not None:
        b = conv.bias
    else:
        b = torch.zeros(conv.out_channels, device=w.device)
        
    b_folded = (b - mean) * scale + beta
    
    # Create new folded Conv1D
    folded_conv = nn.Conv1d(
        in_channels=conv.in_channels,
        out_channels=conv.out_channels,
        kernel_size=conv.kernel_size,
        stride=conv.stride,
        padding=conv.padding,
        bias=True
    ).to(w.device)
    
    folded_conv.weight.data.copy_(w_folded)
    folded_conv.bias.data.copy_(b_folded)
    
    return folded_conv

def fold_batchnorm_micro(model: nn.Module) -> nn.Module:
    """
    Creates a deep copy of VibraDistillMicro with all BatchNorm1d layers folded.
    The resulting model has NO BatchNorm layers (replaced with nn.Identity()).
    
    Args:
        model (VibraDistillMicro): Trained model in eval mode
        
    Returns:
        VibraDistillMicro: Quantization-ready folded model
    """
    model.eval()
    folded = copy.deepcopy(model)
    
    # 1. Fold Stage 1 Multi-Scale FALBlock
    # FALBlock concatenates conv_k3 (8 ch), conv_k7 (8 ch), conv_k15 (8 ch) into bn (24 ch)
    bn1 = folded.stage1.bn
    folded.stage1.conv_k3 = _fold_conv_bn_pair(folded.stage1.conv_k3, bn1, slice(0, 8))
    folded.stage1.conv_k7 = _fold_conv_bn_pair(folded.stage1.conv_k7, bn1, slice(8, 16))
    folded.stage1.conv_k15 = _fold_conv_bn_pair(folded.stage1.conv_k15, bn1, slice(16, 24))
    folded.stage1.bn = nn.Identity()
    
    # 2. Fold Stage 2
    # stage2[0] is Conv1D(24, 32), stage2[1] is BatchNorm1d(32)
    conv2 = folded.stage2[0]
    bn2 = folded.stage2[1]
    folded.stage2[0] = _fold_conv_bn_pair(conv2, bn2)
    folded.stage2[1] = nn.Identity()
    
    # 3. Fold Stage 3
    # stage3[0] is Conv1D(32, 16), stage3[1] is BatchNorm1d(16)
    conv3 = folded.stage3[0]
    bn3 = folded.stage3[1]
    folded.stage3[0] = _fold_conv_bn_pair(conv3, bn3)
    folded.stage3[1] = nn.Identity()
    
    return folded
