"""
Integer-only reference model of the planned Gowin 12-way INT8 NPU datapath.

Scope (be precise about what this is):
  - It is a NumPy *functional* model of the integer arithmetic the RTL must reproduce:
    INT8 x INT8 -> INT32 accumulate, + INT32 bias, requantize by (mult, shift) with
    round-half-up, saturate to INT8, ReLU, MaxPool, integer AvgPool.
  - It is NOT cycle-accurate and NOT verified against RTL simulation. Its purpose is to be
    the golden vector generator for the future Verilog testbench.
"""

import numpy as np


def _requant(acc: np.ndarray, mult, shift) -> np.ndarray:
    """INT32 acc -> INT8 with per-channel (mult, shift); round-half-up; saturate.
    acc: [C, L] or [C]; mult/shift: scalar or [C]."""
    mult = np.asarray(mult, dtype=np.int64)
    shift = np.asarray(shift, dtype=np.int64)
    if acc.ndim == 2:
        mult, shift = mult.reshape(-1, 1), shift.reshape(-1, 1)
    acc = acc.astype(np.int64) * mult
    acc = (acc + (np.int64(1) << (shift - 1))) >> shift
    return np.clip(acc, -128, 127).astype(np.int8)


class GowinNPU12WayEmulator:
    NUM_MACS = 12  # documented hardware parallelism; affects latency model only

    def conv1d_int8(self, x, weight, bias, mult, shift, pad=0):
        c_out, c_in, k = weight.shape
        xp = np.pad(x.astype(np.int32), ((0, 0), (pad, pad)))
        l_out = xp.shape[1] - k + 1
        # im2col: [c_in*k, l_out]
        cols = np.stack([xp[:, i:i + l_out] for i in range(k)], axis=1).reshape(c_in * k, l_out)
        acc = weight.reshape(c_out, -1).astype(np.int32) @ cols + bias.astype(np.int64)[:, None]
        return _requant(acc, mult, shift)

    @staticmethod
    def relu_int8(x):
        return np.maximum(x, 0).astype(np.int8)

    @staticmethod
    def maxpool1d(x, k=2, s=2):
        l_out = (x.shape[1] - k) // s + 1
        return np.max(np.stack([x[:, i:i + s * l_out:s] for i in range(k)], 0), 0)

    @staticmethod
    def avgpool_int8(x, out_len):
        c, l = x.shape
        assert l % out_len == 0, "AdaptiveAvgPool emulation requires divisible length"
        b = l // out_len
        s = x.astype(np.int32).reshape(c, out_len, b).sum(-1)
        return np.clip((s + b // 2) // b, -128, 127).astype(np.int8)  # round-half-up

    def dense_int8(self, x, weight, bias, mult, shift):
        acc = weight.astype(np.int32) @ x.astype(np.int32) + bias.astype(np.int64)
        return _requant(acc, mult, shift)

    def forward_micro(self, pkg, spectrum_int8, prior_int8):
        L = pkg['layers']
        k3, k7, k15 = L['stage1_conv_k3'], L['stage1_conv_k7'], L['stage1_conv_k15']
        f1 = np.concatenate([
            self.conv1d_int8(spectrum_int8, k3['weight_int8'], k3['bias_int32'], k3['mult'], k3['shift'], 1),
            self.conv1d_int8(spectrum_int8, k7['weight_int8'], k7['bias_int32'], k7['mult'], k7['shift'], 3),
            self.conv1d_int8(spectrum_int8, k15['weight_int8'], k15['bias_int32'], k15['mult'], k15['shift'], 7),
        ], axis=0)
        f1 = self.maxpool1d(self.relu_int8(f1))
        s2 = L['stage2_0']
        f2 = self.maxpool1d(self.relu_int8(
            self.conv1d_int8(f1, s2['weight_int8'], s2['bias_int32'], s2['mult'], s2['shift'], 2)))
        s3 = L['stage3_0']
        f3 = self.relu_int8(self.conv1d_int8(f2, s3['weight_int8'], s3['bias_int32'], s3['mult'], s3['shift'], 1))
        emb = self.avgpool_int8(f3, 4).reshape(-1)          # [64], channel-major like torch flatten
        fused = np.concatenate([emb, prior_int8.astype(np.int8)])
        fc = L['fusion_fc_0']
        h = self.relu_int8(self.dense_int8(fused, fc['weight_int8'], fc['bias_int32'], fc['mult'], fc['shift']))
        cl = L['classifier']
        logits = self.dense_int8(h, cl['weight_int8'], cl['bias_int32'], cl['mult'], cl['shift'])
        return {'logits': logits,
                'logits_float': logits.astype(np.float32) * pkg['act_scales']['logits'],
                'prediction': int(np.argmax(logits))}
