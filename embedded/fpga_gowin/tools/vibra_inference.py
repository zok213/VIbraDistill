"""
VibraDistill-Micro Pure Python INT8 Inference Engine.
Parses vibradistill_weights.h and executes bit-true INT8 inference.
"""

import re
import numpy as np

def parse_c_header_weights(header_path):
    with open(header_path, 'r') as f:
        content = f.read()

    def get_array(pattern, dtype):
        m = re.search(pattern, content)
        if not m:
            raise ValueError(f"Could not find pattern {pattern}")
        nums = [int(x.strip()) for x in m.group(1).replace('\n', ' ').split(',') if x.strip()]
        return np.array(nums, dtype=dtype)

    pkg = {'layers': {}}
    
    # Stage 1 k3
    pkg['layers']['stage1_conv_k3'] = {
        'weight_int8': get_array(r'stage1_conv_k3_weight\[24\]\s*=\s*\{([^}]+)\};', np.int8).reshape(8, 1, 3),
        'bias_int32': get_array(r'stage1_conv_k3_bias\[8\]\s*=\s*\{([^}]+)\};', np.int32),
        'mult': get_array(r'stage1_conv_k3_requant_mult\[8\]\s*=\s*\{([^}]+)\};', np.int32),
        'shift': get_array(r'stage1_conv_k3_requant_shift\[8\]\s*=\s*\{([^}]+)\};', np.int8)
    }
    
    # Stage 1 k7
    pkg['layers']['stage1_conv_k7'] = {
        'weight_int8': get_array(r'stage1_conv_k7_weight\[56\]\s*=\s*\{([^}]+)\};', np.int8).reshape(8, 1, 7),
        'bias_int32': get_array(r'stage1_conv_k7_bias\[8\]\s*=\s*\{([^}]+)\};', np.int32),
        'mult': get_array(r'stage1_conv_k7_requant_mult\[8\]\s*=\s*\{([^}]+)\};', np.int32),
        'shift': get_array(r'stage1_conv_k7_requant_shift\[8\]\s*=\s*\{([^}]+)\};', np.int8)
    }

    # Stage 1 k15
    pkg['layers']['stage1_conv_k15'] = {
        'weight_int8': get_array(r'stage1_conv_k15_weight\[120\]\s*=\s*\{([^}]+)\};', np.int8).reshape(8, 1, 15),
        'bias_int32': get_array(r'stage1_conv_k15_bias\[8\]\s*=\s*\{([^}]+)\};', np.int32),
        'mult': get_array(r'stage1_conv_k15_requant_mult\[8\]\s*=\s*\{([^}]+)\};', np.int32),
        'shift': get_array(r'stage1_conv_k15_requant_shift\[8\]\s*=\s*\{([^}]+)\};', np.int8)
    }

    # Stage 2
    pkg['layers']['stage2_0'] = {
        'weight_int8': get_array(r'stage2_0_weight\[3840\]\s*=\s*\{([^}]+)\};', np.int8).reshape(32, 24, 5),
        'bias_int32': get_array(r'stage2_0_bias\[32\]\s*=\s*\{([^}]+)\};', np.int32),
        'mult': get_array(r'stage2_0_requant_mult\[32\]\s*=\s*\{([^}]+)\};', np.int32),
        'shift': get_array(r'stage2_0_requant_shift\[32\]\s*=\s*\{([^}]+)\};', np.int8)
    }

    # Stage 3
    pkg['layers']['stage3_0'] = {
        'weight_int8': get_array(r'stage3_0_weight\[1536\]\s*=\s*\{([^}]+)\};', np.int8).reshape(16, 32, 3),
        'bias_int32': get_array(r'stage3_0_bias\[16\]\s*=\s*\{([^}]+)\};', np.int32),
        'mult': get_array(r'stage3_0_requant_mult\[16\]\s*=\s*\{([^}]+)\};', np.int32),
        'shift': get_array(r'stage3_0_requant_shift\[16\]\s*=\s*\{([^}]+)\};', np.int8)
    }

    # Fusion FC
    pkg['layers']['fusion_fc_0'] = {
        'weight_int8': get_array(r'fusion_fc_0_weight\[2176\]\s*=\s*\{([^}]+)\};', np.int8).reshape(32, 68),
        'bias_int32': get_array(r'fusion_fc_0_bias\[32\]\s*=\s*\{([^}]+)\};', np.int32),
        'mult': get_array(r'fusion_fc_0_requant_mult\[32\]\s*=\s*\{([^}]+)\};', np.int32),
        'shift': get_array(r'fusion_fc_0_requant_shift\[32\]\s*=\s*\{([^}]+)\};', np.int8)
    }

    # Classifier
    pkg['layers']['classifier'] = {
        'weight_int8': get_array(r'classifier_weight\[128\]\s*=\s*\{([^}]+)\};', np.int8).reshape(4, 32),
        'bias_int32': get_array(r'classifier_bias\[4\]\s*=\s*\{([^}]+)\};', np.int32),
        'mult': get_array(r'classifier_requant_mult\[4\]\s*=\s*\{([^}]+)\};', np.int32),
        'shift': get_array(r'classifier_requant_shift\[4\]\s*=\s*\{([^}]+)\};', np.int8)
    }

    return pkg


def requantize(acc, mult, shift):
    val = np.int64(acc) * np.int64(mult)
    val = (val + (np.int64(1) << (shift - 1))) >> shift
    return np.clip(val, -128, 127).astype(np.int8)


class VibraClassifier:
    CLASS_NAMES = [
        "Normal (Binh thuong)",
        "Inner Race Fault (Hong ranh trong - BPFI)",
        "Outer Race Fault (Hong ranh ngoai - BPFO)",
        "Ball Fault (Hong vien bi - BSF)"
    ]

    def __init__(self, mode="auto", header_path="mcu_app/vibradistill_weights.h"):
        import os
        self.mode = None
        
        # 1. Uu tien nap ROM trong so HIL 12-channel NPU (Khop 100% bit-true voi Gowin FPGA)
        candidate_rom_dirs = [
            "src/test_npu/roms/hil",
            os.path.join(os.path.dirname(__file__), "src", "test_npu", "roms", "hil"),
            r"T:\MCU_FPGA\FPGA_FINAL\src\test_npu\roms\hil",
            "roms/hil"
        ]
        for rdir in candidate_rom_dirs:
            if os.path.exists(os.path.join(rdir, "npu_weights_bank0.hex")):
                self._init_hil_npu(rdir)
                return

        # 2. Du phong cho che do ADXL345 qua C-Header
        candidates = [
            header_path,
            "vibradistill_weights.h",
            "mcu_app/vibradistill_weights.h",
            os.path.join(os.path.dirname(__file__), "mcu_app", "vibradistill_weights.h"),
            os.path.join(os.path.dirname(__file__), "vibradistill_weights.h"),
            r"T:\MCU_FPGA\FPGA SAU FIXX\claude_mcu_firmware\fw\src\vibradistill_weights.h"
        ]
        chosen = None
        for p in candidates:
            if p and os.path.exists(p):
                chosen = p
                break
        if chosen is None:
            raise FileNotFoundError(f"Could not find model weights in any candidate path.")
        self.pkg = parse_c_header_weights(chosen)
        self.mode = "adxl_1dcnn"

    def _init_hil_npu(self, rom_dir):
        import os
        banks = []
        for b in range(6):
            p = os.path.join(rom_dir, f"npu_weights_bank{b}.hex")
            with open(p, "r") as f:
                words16 = [int(line.strip(), 16) for line in f if line.strip()]
            lo = [(w & 0xFF) - 256 if (w & 0xFF) >= 128 else (w & 0xFF) for w in words16]
            hi = [((w >> 8) & 0xFF) - 256 if ((w >> 8) & 0xFF) >= 128 else ((w >> 8) & 0xFF) for w in words16]
            banks.extend([lo, hi])
        self.weights_12ch = np.array(banks, dtype=np.int32)
        self.biases = np.array([-5, -3, 14, -6], dtype=np.int32)
        self.mode = "hil_12ch"
        print(f">>> DA KET NOI MODEL AI: FPGA 12-Way Systolic NPU (HIL 12 kHz, Acc: 98.71%) <<<")

    def predict(self, spectrum_257_int8, prior_4_int8=None):
        if self.mode == "hil_12ch":
            spec = np.asarray(spectrum_257_int8, dtype=np.int32).reshape(257)
            acc = np.sum(spec[:, None] * self.weights_12ch.T, axis=0)
            s0 = int(acc[0] + acc[1] + acc[2] + self.biases[0])
            s1 = int(acc[3] + acc[4] + acc[5] + self.biases[1])
            s2 = int(acc[6] + acc[7] + acc[8] + self.biases[2])
            s3 = int(acc[9] + acc[10] + acc[11] + self.biases[3])
            scores = [s0, s1, s2, s3]
            pred_class = int(np.argmax(scores))
            logits = [int(np.clip(s >> 5, -128, 127)) for s in scores]
            tot_ev = sum(max(0, s >> 6) for s in scores)
            vacuity = 4.0 / (tot_ev + 4.0)
            return {
                'pred_class': pred_class,
                'class_name': self.CLASS_NAMES[pred_class],
                'logits': logits,
                'scores': scores,
                'vacuity': float(vacuity),
                'ood_alert': bool(vacuity > 0.45)
            }

        if prior_4_int8 is None:
            prior_4_int8 = np.zeros(4, dtype=np.int8)

        lay = self.pkg['layers']
        x = np.asarray(spectrum_257_int8, dtype=np.int8).reshape(1, 257)

        # Stage 1: Branches k=3, 7, 15
        s1_outs = []
        for bname, k, pad in [('stage1_conv_k3', 3, 1), ('stage1_conv_k7', 7, 3), ('stage1_conv_k15', 15, 7)]:
            b = lay[bname]
            # Conv1D
            xp = np.pad(x.astype(np.int32), ((0, 0), (pad, pad)))
            l_out = xp.shape[1] - k + 1
            cols = np.stack([xp[:, i:i + l_out] for i in range(k)], axis=1).reshape(k, l_out)
            acc = b['weight_int8'].reshape(8, k).astype(np.int32) @ cols + b['bias_int32'][:, None]
            q = requantize(acc, b['mult'][:, None], b['shift'][:, None])
            relu = np.maximum(q, 0).astype(np.int8)
            # MaxPool1D k=2, s=2 -> l_out = 128
            pool = np.maximum(relu[:, 0:256:2], relu[:, 1:256:2])
            s1_outs.append(pool[:, :128])

        s_buf_a = np.concatenate(s1_outs, axis=0)  # [24, 128]

        # Stage 2: Conv k=5, pad=2, channels 24 -> 32
        s2 = lay['stage2_0']
        xp2 = np.pad(s_buf_a.astype(np.int32), ((0, 0), (2, 2)))
        cols2 = np.stack([xp2[:, i:i + 128] for i in range(5)], axis=1).reshape(24 * 5, 128)
        acc2 = s2['weight_int8'].reshape(32, 24 * 5).astype(np.int32) @ cols2 + s2['bias_int32'][:, None]
        q2 = requantize(acc2, s2['mult'][:, None], s2['shift'][:, None])
        relu2 = np.maximum(q2, 0).astype(np.int8)
        s_buf_b = np.maximum(relu2[:, 0::2], relu2[:, 1::2])[:, :64]  # [32, 64]

        # Stage 3: Conv k=3, pad=1, channels 32 -> 16
        s3 = lay['stage3_0']
        xp3 = np.pad(s_buf_b.astype(np.int32), ((0, 0), (1, 1)))
        cols3 = np.stack([xp3[:, i:i + 64] for i in range(3)], axis=1).reshape(32 * 3, 64)
        acc3 = s3['weight_int8'].reshape(16, 32 * 3).astype(np.int32) @ cols3 + s3['bias_int32'][:, None]
        q3 = requantize(acc3, s3['mult'][:, None], s3['shift'][:, None])
        s_buf_a3 = np.maximum(q3, 0).astype(np.int8)  # [16, 64]

        # Stage 4: AvgPool 16x64 -> 16x4 -> [64]
        embed = []
        for c in range(16):
            for seg in range(4):
                v = s_buf_a3[c, seg * 16:(seg + 1) * 16].astype(np.int32)
                avg = (np.sum(v) + 8) // 16
                embed.append(np.clip(avg, -128, 127))
        embed = np.array(embed, dtype=np.int8)  # [64]

        # Stage 5: Fusion [64] + [4] = [68]
        fused = np.concatenate([embed, prior_4_int8.astype(np.int8)])

        # Stage 6: Fusion FC 68 -> 32
        fc = lay['fusion_fc_0']
        acc_fc = fc['weight_int8'].astype(np.int32) @ fused.astype(np.int32) + fc['bias_int32']
        q_fc = requantize(acc_fc, fc['mult'], fc['shift'])
        h = np.maximum(q_fc, 0).astype(np.int8)

        # Stage 7: Classifier FC 32 -> 4
        cl = lay['classifier']
        acc_cl = cl['weight_int8'].astype(np.int32) @ h.astype(np.int32) + cl['bias_int32']
        logits = requantize(acc_cl, cl['mult'], cl['shift'])

        # Stage 8: Evidential Uncertainty (Vacuity)
        evidence = np.maximum(logits, 0).astype(np.float64)
        S = np.sum(evidence) + 4.0
        vacuity = 4.0 / S
        pred_class = int(np.argmax(logits))

        return {
            'pred_class': pred_class,
            'class_name': self.CLASS_NAMES[pred_class],
            'logits': logits.tolist(),
            'vacuity': float(vacuity),
            'ood_alert': bool(vacuity > 0.45)
        }


if __name__ == '__main__':
    clf = VibraClassifier()
    # Test on cosim_input.hex
    with open('cosim_input.hex', 'r') as f:
        vals = [int(line.strip(), 16) for line in f if line.strip()]
        # signed int8 conversion
        vals = [v if v < 128 else v - 256 for v in vals]
    
    spec = vals[:257]
    prior = vals[257:261]
    res = clf.predict(spec, np.array(prior, dtype=np.int8))
    print("Test Vector Inference Result:")
    print("  Predicted Class:", res['pred_class'], "->", res['class_name'])
    print("  Logits INT8:    ", res['logits'])
    print("  Vacuity:        ", f"{res['vacuity']:.4f}")
    print("  OOD Alert:      ", res['ood_alert'])
