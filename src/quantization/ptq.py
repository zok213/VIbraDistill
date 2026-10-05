"""
Post-Training Quantization (PTQ) for VibraDistillMicro (folded BatchNorm).

Static symmetric INT8, per-tensor weights and activations.
  - Activation scales are CALIBRATED on real data (max-abs over a calibration loader).
  - bias_int32 = round(b / (s_in * s_w))
  - Requantization: y_int8 = clip(round(acc * M)), M = s_in*s_w/s_out ~= mult / 2^shift
The kinematic prior (scaled x3 inside the model) is quantized with the SAME scale as the
pooled CNN embedding so both can be concatenated into one INT8 vector for the fusion layer.

Nothing here is hard-coded: every scale is derived from the trained weights and calibration data.
"""

from typing import Dict, Any, Optional
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def quantize_tensor_symmetric(tensor: torch.Tensor, n_bits: int = 8) -> tuple:
    """Symmetric per-tensor quantization. Returns (int array, scale)."""
    arr = tensor.detach().cpu().numpy()
    qmax = (1 << (n_bits - 1)) - 1
    max_val = float(np.max(np.abs(arr)))
    if max_val < 1e-12:
        return np.zeros_like(arr, dtype=np.int8), 1.0
    scale = max_val / qmax
    q_arr = np.clip(np.round(arr / scale), -qmax - 1, qmax).astype(np.int8)
    return q_arr, scale


def compute_requant_multiplier_shift(real_multiplier: float, mult_bits: int = 15) -> tuple:
    """Decompose M into (mult, shift) with M ~= mult / 2^shift and mult in [2^(b-1), 2^b)."""
    if real_multiplier <= 0.0:
        return 0, 0
    shift = 0
    m = real_multiplier
    while m < 0.5 and shift < 40:
        m *= 2.0
        shift += 1
    while m >= 1.0:
        m /= 2.0
        shift -= 1
    mult = int(np.round(m * (1 << mult_bits)))
    shift += mult_bits
    if mult == (1 << mult_bits):  # rounding overflow
        mult >>= 1
        shift -= 1
    return mult, shift


@torch.no_grad()
def calibrate_activation_ranges(folded_model: nn.Module, calib_loader, device='cpu',
                                max_batches: int = 50, percentile: float = 99.9) -> Dict[str, float]:
    """Runs the folded float model on real data and records a high percentile of |t| for every
    tensor crossing an INT8 boundary. Percentile (not max-abs) clipping keeps rare outliers
    from wasting the INT8 range."""
    m = folded_model.to(device).eval()
    keys = ['input', 'stage1', 'stage2', 'stage3', 'prior3', 'fc', 'logits']
    buf = {k: [] for k in keys}
    for i, batch in enumerate(calib_loader):
        if i >= max_batches:
            break
        x = batch['spectrum'].to(device)
        p = batch['prior'].to(device)
        if x.dim() == 2:
            x = x.unsqueeze(1)
        s1 = m.stage1
        f1 = F.relu(torch.cat([s1.conv_k3(x), s1.conv_k7(x), s1.conv_k15(x)], dim=1))
        f1p = F.max_pool1d(f1, 2, 2)
        f2 = F.relu(m.stage2[0](f1p))
        f2p = F.max_pool1d(f2, 2, 2)
        f3 = F.relu(m.stage3[0](f2p))
        emb = F.adaptive_avg_pool1d(f3, 4).flatten(1)
        fused = torch.cat([emb, p * 3.0], dim=1)
        h = F.relu(m.fusion_fc[0](fused))
        logits = m.classifier(h)
        for k, t in [('input', x), ('stage1', f1), ('stage2', f2), ('stage3', f3),
                     ('prior3', p * 3.0), ('fc', h), ('logits', logits)]:
            buf[k].append(t.abs().flatten().cpu())
    return {k: float(np.percentile(torch.cat(v).numpy(), percentile)) for k, v in buf.items()}


def quantize_model_symmetric_int8(folded_model: nn.Module, calib_loader=None,
                                  device='cpu', act_ranges: Optional[Dict[str, float]] = None
                                  ) -> Dict[str, Any]:
    """Produces the INT8 deployment package consumed by GowinNPU12WayEmulator and the C exporter."""
    folded_model.eval()
    if act_ranges is None:
        if calib_loader is None:
            raise ValueError("PTQ requires calib_loader (real data) or explicit act_ranges; "
                             "refusing to guess activation scales.")
        act_ranges = calibrate_activation_ranges(folded_model, calib_loader, device)

    s = {k: max(v, 1e-8) / 127.0 for k, v in act_ranges.items()}
    # Embedding and prior share one scale so they can be concatenated in INT8.
    s['stage3'] = max(act_ranges['stage3'], act_ranges['prior3'], 1e-8) / 127.0

    m = folded_model
    plan = [  # (name, module, s_in, s_out)
        ('stage1_conv_k3', m.stage1.conv_k3, s['input'], s['stage1']),
        ('stage1_conv_k7', m.stage1.conv_k7, s['input'], s['stage1']),
        ('stage1_conv_k15', m.stage1.conv_k15, s['input'], s['stage1']),
        ('stage2_0', m.stage2[0], s['stage1'], s['stage2']),
        ('stage3_0', m.stage3[0], s['stage2'], s['stage3']),
        ('fusion_fc_0', m.fusion_fc[0], s['stage3'], s['fc']),
        ('classifier', m.classifier, s['fc'], s['logits']),
    ]
    pkg = {'layers': {}, 'act_scales': s, 'act_ranges': act_ranges,
           'metadata': {'bitwidth': 8, 'scheme': 'static symmetric per-tensor, calibrated'}}
    for name, mod, s_in, s_out in plan:
        w = mod.weight.data.detach().cpu().numpy()
        c_out = w.shape[0]
        # Per-output-channel symmetric scales (folded BN makes channel magnitudes differ 3-12x)
        s_w = np.maximum(np.abs(w.reshape(c_out, -1)).max(axis=1), 1e-12) / 127.0
        q_w = np.clip(np.round(w / s_w.reshape(-1, *([1] * (w.ndim - 1)))), -128, 127).astype(np.int8)
        b = mod.bias.detach().cpu().numpy() if mod.bias is not None else np.zeros(c_out)
        q_b = np.clip(np.round(b / (s_in * s_w)), -(2**31), 2**31 - 1).astype(np.int32)
        ms = [compute_requant_multiplier_shift(float(s_in * sw / s_out)) for sw in s_w]
        pkg['layers'][name] = {'weight_int8': q_w, 'bias_int32': q_b, 'weight_scale': s_w,
                               'in_scale': s_in, 'out_scale': s_out,
                               'mult': np.array([m for m, _ in ms], dtype=np.int64),
                               'shift': np.array([s for _, s in ms], dtype=np.int64),
                               'shape': list(q_w.shape)}
    pkg['metadata']['total_weights'] = int(sum(l['weight_int8'].size + l['bias_int32'].size
                                               for l in pkg['layers'].values()))
    return pkg


def quantize_inputs(pkg: Dict[str, Any], spectrum: np.ndarray, prior: np.ndarray) -> tuple:
    """Float sensor features -> INT8 tensors using the calibrated scales (no magic constants)."""
    s = pkg['act_scales']
    x = np.clip(np.round(np.asarray(spectrum, dtype=np.float64) / s['input']), -128, 127).astype(np.int8)
    p = np.clip(np.round(np.asarray(prior, dtype=np.float64) * 3.0 / s['stage3']), -128, 127).astype(np.int8)
    return x.reshape(1, -1), p.reshape(-1)
