"""
Quantization-Aware Training (QAT) that mirrors the integer datapath of the NPU emulator.

Design (all derived, nothing hard-coded):
  * Start from the trained FP32 student, fold BatchNorm (exact), then fine-tune the folded network.
  * Fake-quantize exactly where the emulator re-quantizes to INT8:
        input | stage1 out | stage2 out | stage3 out (shared scale with the x3 prior) | fc out | logits
    Weights: per-output-channel symmetric INT8 (same rule as ptq.py). Straight-through estimator.
  * Activation scales come from percentile calibration on the TRAIN split (same function PTQ uses),
    so the exported package and the QAT graph use identical scales.
  * Loss: CE + lambda * MSE(logits, frozen FP32 student logits)  (self-distillation).
  * Model selection uses the VAL split only; test splits are touched once at the end.
"""
import copy
import torch
import torch.nn as nn
import torch.nn.functional as F


def fq_act(x: torch.Tensor, scale: float) -> torch.Tensor:
    """Symmetric INT8 fake-quant with STE; gradient is zero where the value is clipped."""
    lo, hi = -128.0 * scale, 127.0 * scale
    y = torch.clamp(x, lo, hi)
    return y + (torch.round(y / scale) * scale - y).detach()


def fq_weight_per_channel(w: torch.Tensor) -> torch.Tensor:
    c = w.shape[0]
    s = (w.detach().abs().reshape(c, -1).amax(dim=1).clamp_min(1e-12) / 127.0).reshape(-1, *([1] * (w.dim() - 1)))
    y = torch.clamp(w, -128.0 * s, 127.0 * s)
    return y + (torch.round(y / s) * s - y).detach()


class QATMicro(nn.Module):
    """Fake-quantized twin of the folded VibraDistillMicro (use_physics_film=False)."""

    def __init__(self, folded: nn.Module, act_ranges: dict):
        super().__init__()
        self.m = copy.deepcopy(folded)
        s = {k: max(v, 1e-8) / 127.0 for k, v in act_ranges.items()}
        s['stage3'] = max(act_ranges['stage3'], act_ranges['prior3'], 1e-8) / 127.0  # shared, as in ptq.py
        self.s = s

    def _conv(self, conv, x, pad_attr=True):
        return F.conv1d(x, fq_weight_per_channel(conv.weight), conv.bias, padding=conv.padding)

    def _lin(self, lin, x):
        return F.linear(x, fq_weight_per_channel(lin.weight), lin.bias)

    def forward(self, x, prior):
        m, s = self.m, self.s
        if x.dim() == 2:
            x = x.unsqueeze(1)
        x = fq_act(x, s['input'])
        s1 = m.stage1
        f1 = torch.cat([self._conv(s1.conv_k3, x), self._conv(s1.conv_k7, x), self._conv(s1.conv_k15, x)], 1)
        f1 = F.max_pool1d(fq_act(F.relu(f1), s['stage1']), 2)
        f2 = F.max_pool1d(fq_act(F.relu(self._conv(m.stage2[0], f1)), s['stage2']), 2)
        f3 = fq_act(F.relu(self._conv(m.stage3[0], f2)), s['stage3'])
        emb = fq_act(F.adaptive_avg_pool1d(f3, 4).flatten(1), s['stage3'])
        p = fq_act(prior * 3.0, s['stage3'])
        h = fq_act(F.relu(self._lin(m.fusion_fc[0], torch.cat([emb, p], 1))), s['fc'])
        return fq_act(self._lin(m.classifier, h), s['logits']), None

    def export_folded(self) -> nn.Module:
        """Folded float model carrying the QAT-trained weights (re-quantized by ptq.py losslessly)."""
        return copy.deepcopy(self.m)
