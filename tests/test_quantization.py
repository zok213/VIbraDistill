import os
import sys
import unittest
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.models.student_micro import VibraDistillMicro
from src.quantization.bn_fold import fold_batchnorm_micro
from src.quantization.ptq import (quantize_model_symmetric_int8, quantize_inputs,
                                  compute_requant_multiplier_shift)
from src.models.npu_emulator import GowinNPU12WayEmulator


def _calib_batches(n=4, bs=16):
    g = torch.Generator().manual_seed(0)
    return [{'spectrum': torch.rand(bs, 1, 257, generator=g) * 0.2,
             'prior': torch.rand(bs, 4, generator=g)} for _ in range(n)]


def _trained_like_model():
    torch.manual_seed(0)
    m = VibraDistillMicro()
    m.train()
    for _ in range(3):  # populate BN running stats so folding is non-trivial
        m(torch.rand(32, 1, 257) * 0.2, torch.rand(32, 4))
    return m.eval()


class TestQuantizationAndNPU(unittest.TestCase):
    def test_batchnorm_folding_exactness(self):
        model = _trained_like_model()
        x, prior = torch.rand(4, 1, 257), torch.rand(4, 4)
        a, _ = model(x, prior)
        b, _ = fold_batchnorm_micro(model)(x, prior)
        self.assertLess(torch.max(torch.abs(a - b)).item(), 1e-4)

    def test_ptq_requires_calibration_data(self):
        with self.assertRaises(ValueError):
            quantize_model_symmetric_int8(fold_batchnorm_micro(_trained_like_model()))

    def test_requant_multiplier_accuracy(self):
        for M in [0.0047, 0.0132, 0.2, 0.75]:
            mult, shift = compute_requant_multiplier_shift(M)
            self.assertLess(abs(mult / 2 ** shift - M) / M, 1e-3)
            self.assertLess(mult, 2 ** 15 + 1)

    def test_ptq_int8_ranges_and_per_channel_params(self):
        pkg = quantize_model_symmetric_int8(fold_batchnorm_micro(_trained_like_model()),
                                            calib_loader=_calib_batches())
        for name, l in pkg['layers'].items():
            self.assertEqual(l['weight_int8'].dtype, np.int8)
            self.assertEqual(l['bias_int32'].dtype, np.int32)
            self.assertEqual(len(l['mult']), l['weight_int8'].shape[0], name)
            self.assertEqual(len(l['shift']), l['weight_int8'].shape[0], name)

    def test_int8_emulator_tracks_float_logits_direction(self):
        """Integer path must be strongly correlated with the float model on in-distribution input.
        (End-to-end accuracy parity is measured on real data by scripts/07_verify_int8_parity.py.)"""
        model = _trained_like_model()
        folded = fold_batchnorm_micro(model)
        batches = _calib_batches()
        pkg = quantize_model_symmetric_int8(folded, calib_loader=batches)
        em = GowinNPU12WayEmulator()
        sims = []
        for b in batches[:1]:
            for x, p in zip(b['spectrum'], b['prior']):
                with torch.no_grad():
                    f, _ = folded(x.unsqueeze(0), p.unsqueeze(0))
                xi, pi = quantize_inputs(pkg, x.numpy().reshape(-1), p.numpy())
                q = em.forward_micro(pkg, xi, pi)
                self.assertEqual(q['logits'].shape, (4,))
                f = f.numpy().ravel(); qq = q['logits_float'].astype(np.float64)
                sims.append(float(f @ qq / (np.linalg.norm(f) * np.linalg.norm(qq) + 1e-12)))
        self.assertGreater(float(np.mean(sims)), 0.5)


if __name__ == '__main__':
    unittest.main()
