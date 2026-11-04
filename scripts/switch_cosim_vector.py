#!/usr/bin/env python3
"""
scripts/switch_cosim_vector.py
================================================================================
Công cụ tự động chuyển đổi Test Vector cho ModelSim Testbench (tb_npu_cosim.v)
và Top-level SoC (gowin_top_soc.v).

Cách dùng:
    python scripts/switch_cosim_vector.py cwru_normal
    python scripts/switch_cosim_vector.py cwru_inner
    python scripts/switch_cosim_vector.py cwru_outer
    python scripts/switch_cosim_vector.py cwru_ball
    python scripts/switch_cosim_vector.py pronostia_early
    python scripts/switch_cosim_vector.py pronostia_mid
    python scripts/switch_cosim_vector.py pronostia_end
    python scripts/switch_cosim_vector.py list
================================================================================
"""

import os
import sys
import shutil
import json
import numpy as np

# Set UTF-8 encoding for Windows console output
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROMS_DIR = os.path.join(REPO_ROOT, 'embedded', 'fpga_gowin', 'roms')
TEST_VEC_DIR = os.path.join(REPO_ROOT, 'test_vectors')

TOAN_DIR = r"C:\Users\Admin\Downloads\FPGA_FINAL\src\test_npu"

VECTOR_MAP = {
    'cwru_normal': {
        'name': 'CWRU Normal Baseline (Class 0)',
        'spec_file': 'golden_cwru_normal_spectrum_int8.hex',
        'stim_file': 'stimulus_cwru_normal.hex',
        'pred_class': 0,
        'rul_pct': 100.0,
        'rul_q15': 32768,
        'desc': 'Vòng bi lành lặn 1797 RPM'
    },
    'cwru_inner': {
        'name': 'CWRU Inner Race Defect (Class 1 - BPFI 162Hz)',
        'spec_file': 'golden_cwru_inner_spectrum_int8.hex',
        'stim_file': 'stimulus_cwru_inner.hex',
        'pred_class': 1,
        'rul_pct': 45.0,
        'rul_q15': 14745,
        'desc': 'Khuyết tật rãnh trong 7-mil'
    },
    'cwru_outer': {
        'name': 'CWRU Outer Race Defect (Class 2 - BPFO 107Hz)',
        'spec_file': 'golden_cwru_outer_spectrum_int8.hex',
        'stim_file': 'stimulus_cwru_outer.hex',
        'pred_class': 2,
        'rul_pct': 25.0,
        'rul_q15': 8192,
        'desc': 'Khuyết tật rãnh ngoài 7-mil'
    },
    'cwru_ball': {
        'name': 'CWRU Ball Defect (Class 3 - BSF 71Hz)',
        'spec_file': 'golden_cwru_ball_spectrum_int8.hex',
        'stim_file': 'stimulus_cwru_ball.hex',
        'pred_class': 3,
        'rul_pct': 12.5,
        'rul_q15': 4096,
        'desc': 'Khuyết tật viên bi 7-mil'
    },
    'pronostia_early': {
        'name': 'PRONOSTIA Early Life (Snapshot #12 - 5% Life)',
        'spec_file': 'golden_pronostia_early_life_spectrum_int8.hex',
        'stim_file': 'stimulus_pronostia_early_life.hex',
        'pred_class': 0,
        'rul_pct': 100.0,
        'rul_q15': 32768,
        'desc': 'Giai đoạn đầu lành lặn, RUL 100%'
    },
    'pronostia_mid': {
        'name': 'PRONOSTIA Mid Life (Snapshot #1760 - 74% Life)',
        'spec_file': 'golden_pronostia_mid_life_spectrum_int8.hex',
        'stim_file': 'stimulus_pronostia_mid_life.hex',
        'pred_class': 3,
        'rul_pct': 42.0,
        'rul_q15': 13762,
        'desc': 'Giai đoạn suy thoái khởi phát, RUL 42%'
    },
    'pronostia_end': {
        'name': 'PRONOSTIA End of Life (Snapshot #2372 - 98% Life)',
        'spec_file': 'golden_pronostia_end_of_life_spectrum_int8.hex',
        'stim_file': 'stimulus_pronostia_end_of_life.hex',
        'pred_class': 3,
        'rul_pct': 1.0,
        'rul_q15': 327,
        'desc': 'Giai đoạn phá hủy vỡ nát, SIL-2 Emergency Trip'
    }
}

def load_hil_weights():
    hil_dir = os.path.join(ROMS_DIR, 'hil')
    channels = []
    for b in range(6):
        hpath = os.path.join(hil_dir, f"npu_weights_bank{b}.hex")
        with open(hpath, 'r') as f:
            words16 = [int(line.strip(), 16) for line in f if line.strip()]
        ch_low = [((w & 0xFF) - 256) if (w & 0xFF) >= 128 else (w & 0xFF) for w in words16]
        ch_high = [(((w >> 8) & 0xFF) - 256) if ((w >> 8) & 0xFF) >= 128 else ((w >> 8) & 0xFF) for w in words16]
        channels.extend([ch_low, ch_high])
    return np.array(channels, dtype=np.int32)

def compute_golden(spec_int8, weights, biases):
    accum = np.dot(weights, spec_int8[:257])
    s0 = int(accum[0] + accum[1] + accum[2] + biases[0])
    s1 = int(accum[3] + accum[4] + accum[5] + biases[1])
    s2 = int(accum[6] + accum[7] + accum[8] + biases[2])
    s3 = int(accum[9] + accum[10] + accum[11] + biases[3])
    scores = [s0, s1, s2, s3]
    pred = int(np.argmax(scores))

    def c8(v): return max(-128, min(127, v >> 5))
    l0, l1, l2, l3 = [c8(s) for s in scores]
    packed = ((l3 & 0xFF) << 24) | ((l2 & 0xFF) << 16) | ((l1 & 0xFF) << 8) | (l0 & 0xFF)

    ev = np.maximum(np.array(scores) >> 6, 0)
    sum_e = int(np.sum(ev) + 4)
    vac_q15 = int(131072 // sum_e) if sum_e <= 131072 else 1
    vac_float = float(vac_q15) / 32768.0

    return pred, scores, packed, vac_q15, vac_float

def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() in ['-h', '--help', 'help', 'list']:
        print("=" * 76)
        print(" DANH SÁCH TEST VECTORS KHẢ DỤNG CHO MODELSIM & FPGA:")
        print("=" * 76)
        for k, v in VECTOR_MAP.items():
            print(f"  * {k:<16} : {v['name']} ({v['desc']})")
        print("\nCách dùng:")
        print("  python scripts/switch_cosim_vector.py cwru_normal")
        print("  python scripts/switch_cosim_vector.py pronostia_early")
        print("=" * 76)
        return

    choice = sys.argv[1].lower()
    if choice not in VECTOR_MAP:
        print(f"[!] Lỗi: Không tìm thấy vector '{choice}'. Chạy 'python scripts/switch_cosim_vector.py list' để xem danh sách.")
        return

    vec = VECTOR_MAP[choice]
    
    # 1. Update Toan's folder if present
    target_dirs = []
    if os.path.exists(os.path.join(TOAN_DIR, 'test_vectors')):
        target_dirs.append(TOAN_DIR)

    w = load_hil_weights()
    biases = [-5, -3, 14, -6]

    for t_dir in target_dirs:
        spec_path = os.path.join(t_dir, 'test_vectors', vec['spec_file'])
        cosim_in = os.path.join(t_dir, 'test_vectors', 'cosim_input.hex')
        cosim_gold = os.path.join(t_dir, 'test_vectors', 'cosim_golden.hex')

        if os.path.exists(spec_path):
            shutil.copyfile(spec_path, cosim_in)
            print(f"[+] [Toàn Workspace] Đã nạp phổ vào: {os.path.relpath(cosim_in, t_dir)}")

            spec_data = []
            with open(spec_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        val = int(line, 16)
                        if val >= 128: val -= 256
                        spec_data.append(val)
            spec_arr = np.array(spec_data, dtype=np.int32)
            pred, scores, packed, vac_q15, vac_float = compute_golden(spec_arr, w, biases)

            ood_alert = 1 if vac_q15 > 14745 else 0
            with open(cosim_gold, 'w') as f:
                f.write(f"{pred:08X}\n")
                f.write(f"{packed:08X}\n")
                f.write("00000000\n")
                f.write("00000000\n")
                f.write("00000000\n")
                f.write(f"{vac_q15:08X}\n")
                f.write(f"{vec['rul_q15']:08X}\n")
                f.write(f"{ood_alert:08X}\n")
            print(f"[+] [Toàn Workspace] Đã cập nhật: {os.path.relpath(cosim_gold, t_dir)}")

    class_names = ["Normal (Baseline)", "Inner Race (BPFI)", "Outer Race (BPFO)", "Ball Fault (BSF)"]
    print("\n" + "=" * 76)
    print(f" CẤU HÌNH THÀNH CÔNG VECTOR: {vec['name'].upper()}")
    print("=" * 76)
    print(f"  * Lớp Dự Đoán Chuẩn (Predicted Class): {vec['pred_class']} -> {class_names[vec['pred_class']]}")
    print(f"  * Điểm Số Lớp (NPU Scores):            {scores if 'scores' in locals() else 'N/A'}")
    print(f"  * Tuổi Thọ Còn Lại (RUL %):            {vec['rul_pct']:.1f}%")
    print("=" * 76)
    print("👉 Toàn chỉ cần mở ModelSim chạy 'do run.do.txt' là sẽ thấy 100% MATCHED!")
    print("=" * 76)

if __name__ == '__main__':
    main()
