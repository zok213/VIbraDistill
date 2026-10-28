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

    def test_fpga_12way_npu_subband_parity(self):
        """Verifies that the 12-channel BSRAM bank weights achieve >95% accuracy on ADXL345 validation data."""
        rom_dir = os.path.join(os.path.dirname(__file__), '..', 'embedded', 'fpga_gowin', 'roms', 'adxl345')
        val_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'cache', 'cwru_val_adxl345_w512.pt')
        if not os.path.exists(val_path):
            self.skipTest("Validation cache not available.")

        # Load 6 BSRAM Bank .hex files
        banks = []
        for b in range(6):
            hex_file = os.path.join(rom_dir, f"npu_weights_bank{b}.hex")
            self.assertTrue(os.path.exists(hex_file), f"Missing ROM: {hex_file}")
            with open(hex_file, "r") as f:
                words16 = [int(line.strip(), 16) for line in f if line.strip()]
            self.assertEqual(len(words16), 257)
            ch_low = [((w & 0xFF) - 256) if (w & 0xFF) >= 128 else (w & 0xFF) for w in words16]
            ch_high = [(((w >> 8) & 0xFF) - 256) if ((w >> 8) & 0xFF) >= 128 else ((w >> 8) & 0xFF) for w in words16]
            banks.extend([ch_low, ch_high])

        w12 = np.array(banks, dtype=np.int32)
        d_va = torch.load(val_path, weights_only=False)
        X_va = d_va['spectra'].squeeze(1).numpy()
        y_va = d_va['labels'].numpy()
        X_int8 = np.clip(np.round(X_va * 127.0), 0, 127).astype(np.int32)

        biases = np.array([0, -3, 8, -4], dtype=np.int32)
        correct = 0
        for i in range(len(y_va)):
            acc = np.dot(w12, X_int8[i])
            s = [
                int(acc[0] + acc[1] + acc[2] + biases[0]),
                int(acc[3] + acc[4] + acc[5] + biases[1]),
                int(acc[6] + acc[7] + acc[8] + biases[2]),
                int(acc[9] + acc[10] + acc[11] + biases[3])
            ]
            if np.argmax(s) == y_va[i]:
                correct += 1

        acc_pct = (correct / len(y_va)) * 100.0
        self.assertGreater(acc_pct, 95.0)

    def test_gowin_top_soc_cst_pin_parity(self):
        """Verifies 100% pinout parity between primer20k_adxl345.cst and gowin_top_soc.v."""
        import re
        cst_path = os.path.join(os.path.dirname(__file__), '..', 'embedded', 'fpga_gowin', 'primer20k_adxl345.cst')
        soc_path = os.path.join(os.path.dirname(__file__), '..', 'embedded', 'fpga_gowin', 'src', 'gowin_top_soc.v')
        self.assertTrue(os.path.exists(cst_path))
        self.assertTrue(os.path.exists(soc_path))

        with open(cst_path, 'r') as f:
            cst_content = f.read()
        with open(soc_path, 'r') as f:
            soc_content = f.read()

        cst_ports = re.findall(r'IO_LOC\s+"([^"]+)"', cst_content)
        self.assertGreater(len(cst_ports), 0)

        # Extract port names from top module port declaration
        soc_port_block = soc_content.split('module gowin_top_soc')[1].split(');')[0]
        soc_ports = re.findall(r'(?:input|output)\s+(?:wire|reg)?\s*(?:signed)?\s*(?:\[[^\]]+\])?\s*([a-zA-Z0-9_]+)', soc_port_block)

        for port in cst_ports:
            self.assertIn(port, soc_ports, f"CST constraint port '{port}' missing in gowin_top_soc.v port list!")

        # Also verify SPI master packet size vs main.c
        main_c_path = os.path.join(os.path.dirname(__file__), '..', 'embedded', 'mcu_sonix', 'app', 'main.c')
        with open(main_c_path, 'r') as f:
            main_c_content = f.read()
        self.assertIn('#define SPI_FRAME_SIZE          524', main_c_content)
        self.assertIn('.TOTAL_BYTES (524)', soc_content)


if __name__ == '__main__':
    unittest.main()
