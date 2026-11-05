#!/usr/bin/env python3
"""
scripts/switch_cosim_vector.py
================================================================================
Công cụ chuyển đổi Test Vector đa dạng cho ModelSim Testbench (tb_npu_cosim.v),
Top-level SoC (gowin_top_soc.v) và HIL Streamer.

Hỗ trợ toàn diện 28 Vector Công Nghiệp CWRU (Loads 0-3 HP, Severities 7-21 mil, OOD)
và các Vector Run-to-Failure PRONOSTIA.

Cách dùng:
    python scripts/switch_cosim_vector.py list       (Xem danh sách toàn bộ 31 vector)
    python scripts/switch_cosim_vector.py 1          (Chọn vector theo số thứ tự 1..28)
    python scripts/switch_cosim_vector.py 6          (Inner 7-mil 1 HP)
    python scripts/switch_cosim_vector.py 17         (Inner 14-mil 1 HP)
    python scripts/switch_cosim_vector.py 20         (Inner 21-mil 1 HP - Severe / Trip)
    python scripts/switch_cosim_vector.py pronostia_end (Snapshot phá hủy 98%)
================================================================================
"""

import os
import sys
import shutil
import numpy as np

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Định vị thư mục linh hoạt cho cả khi chạy trong repo VIbraDistill hoặc trong test_npu của Toàn
CUR_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CUR_DIR, '..')) if os.path.basename(CUR_DIR) == 'scripts' else CUR_DIR

# Tìm thư mục test_vectors
candidate_test_dirs = [
    os.path.join(CUR_DIR, 'test_vectors'),
    os.path.join(REPO_ROOT, 'test_vectors'),
    r"C:\Users\Admin\Downloads\FPGA_FINAL\src\test_npu\test_vectors",
    r"d:\Gitrepo\VIbraDistill\test_vectors"
]
TEST_VEC_DIR = next((d for d in candidate_test_dirs if os.path.isdir(d)), os.path.join(REPO_ROOT, 'test_vectors'))

# Tìm thư mục roms
candidate_roms_dirs = [
    os.path.join(CUR_DIR, 'roms'),
    os.path.join(REPO_ROOT, 'embedded', 'fpga_gowin', 'roms'),
    os.path.join(REPO_ROOT, 'roms'),
    r"C:\Users\Admin\Downloads\FPGA_FINAL\src\test_npu\roms",
    r"d:\Gitrepo\VIbraDistill\embedded\fpga_gowin\roms"
]
ROMS_DIR = next((d for d in candidate_roms_dirs if os.path.isdir(d)), os.path.join(REPO_ROOT, 'embedded', 'fpga_gowin', 'roms'))

TOAN_DIR = r"C:\Users\Admin\Downloads\FPGA_FINAL\src\test_npu"

# 28 Comprehensive Vectors + 3 PRONOSTIA Vectors
CATALOG = [
    # --- NHÓM 1: CHUẨN LÀNH LẶN (NORMAL BASELINE) QUA CÁC MỨC TẢI 0-3 HP ---
    ('1',  '01_cwru_normal_0hp',         'CWRU Normal 0 HP (1797 RPM)', 'Vòng bi lành lặn 0 HP, RUL 100%'),
    ('2',  '02_cwru_inner_7mil_0hp',     'CWRU Inner 7-mil 0 HP',       'Lỗi vòng trong 7-mil tải 0 HP'),
    ('3',  '03_cwru_outer_7mil_0hp',     'CWRU Outer 7-mil 0 HP',       'Lỗi vòng ngoài 7-mil tải 0 HP'),
    ('4',  '04_cwru_ball_7mil_0hp',      'CWRU Ball 7-mil 0 HP',        'Lỗi viên bi 7-mil tải 0 HP'),

    ('5',  '05_cwru_normal_1hp',         'CWRU Normal 1 HP (1772 RPM)', 'Vòng bi lành lặn 1 HP, RUL 100%'),
    ('6',  '06_cwru_inner_7mil_1hp',     'CWRU Inner 7-mil 1 HP',       'Lỗi vòng trong 7-mil tải 1 HP'),
    ('7',  '07_cwru_outer_7mil_1hp',     'CWRU Outer 7-mil 1 HP',       'Lỗi vòng ngoài 7-mil tải 1 HP'),
    ('8',  '08_cwru_ball_7mil_1hp',      'CWRU Ball 7-mil 1 HP',        'Lỗi viên bi 7-mil tải 1 HP'),

    ('9',  '09_cwru_normal_2hp',         'CWRU Normal 2 HP (1750 RPM)', 'Vòng bi lành lặn 2 HP, RUL 100%'),
    ('10', '10_cwru_inner_7mil_2hp',     'CWRU Inner 7-mil 2 HP',       'Lỗi vòng trong 7-mil tải 2 HP'),
    ('11', '11_cwru_outer_7mil_2hp',     'CWRU Outer 7-mil 2 HP',       'Lỗi vòng ngoài 7-mil tải 2 HP'),
    ('12', '12_cwru_ball_7mil_2hp',      'CWRU Ball 7-mil 2 HP',        'Lỗi viên bi 7-mil tải 2 HP'),

    ('13', '13_cwru_normal_3hp',         'CWRU Normal 3 HP (1725 RPM)', 'Vòng bi lành lặn 3 HP (Unseen Load)'),
    ('14', '14_cwru_inner_7mil_3hp',     'CWRU Inner 7-mil 3 HP',       'Lỗi vòng trong 7-mil tải 3 HP'),
    ('15', '15_cwru_outer_7mil_3hp',     'CWRU Outer 7-mil 3 HP',       'Lỗi vòng ngoài 7-mil tải 3 HP'),
    ('16', '16_cwru_ball_7mil_3hp',      'CWRU Ball 7-mil 3 HP',        'Lỗi viên bi 7-mil tải 3 HP'),

    # --- NHÓM 2: KHUYẾT TẬT TRUNG BÌNH (14-MIL MODERATE SEVERITY) ---
    ('17', '17_cwru_inner_14mil_1hp',    'CWRU Inner 14-mil 1 HP',      'Khuyết tật vòng trong 14-mil (Gấp đôi 7-mil)'),
    ('18', '18_cwru_outer_14mil_1hp',    'CWRU Outer 14-mil 1 HP',      'Khuyết tật vòng ngoài 14-mil'),
    ('19', '19_cwru_ball_14mil_1hp',     'CWRU Ball 14-mil 1 HP',       'Khuyết tật viên bi 14-mil'),

    # --- NHÓM 3: KHUYẾT TẬT NẶNG / SẮP PHÁ HỦY (21-MIL SEVERE BREAKDOWN) ---
    ('20', '20_cwru_inner_21mil_1hp',    'CWRU Inner 21-mil 1 HP',      'Khuyết tật rãnh trong cực nặng (SIL-2 Trip)'),
    ('21', '21_cwru_outer_21mil_1hp',    'CWRU Outer 21-mil 1 HP',      'Khuyết tật rãnh ngoài cực nặng (SIL-2 Trip)'),
    ('22', '22_cwru_ball_21mil_1hp',     'CWRU Ball 21-mil 1 HP',       'Khuyết tật bi vỡ nát 21-mil (SIL-2 Trip)'),

    # --- NHÓM 4: CỬA SỔ DỊCH TRƯỢT THỜI GIAN (TIME-SHIFTED WINDOWS) ---
    ('23', '23_cwru_inner_7mil_win2',    'CWRU Inner 7-mil Win 2',      'Cửa sổ trượt 2: Kiểm chứng tính bất biến thời gian'),
    ('24', '24_cwru_inner_7mil_win3',    'CWRU Inner 7-mil Win 3',      'Cửa sổ trượt 3'),
    ('25', '25_cwru_outer_7mil_win2',    'CWRU Outer 7-mil Win 2',      'Cửa sổ trượt 2: Rãnh ngoài'),
    ('26', '26_cwru_outer_7mil_win3',    'CWRU Outer 7-mil Win 3',      'Cửa sổ trượt 3: Rãnh ngoài'),

    # --- NHÓM 5: NGOẠI LAI CƠ KHÍ & NHIỄU (OUT-OF-DISTRIBUTION OOD) ---
    ('27', '27_ood_high_noise',          'OOD High Sensor Noise',       'Nhiễu trắng biên độ lớn'),
    ('28', '28_ood_synthetic_multitone', 'OOD Synthetic Multitone',     'Sóng đa tần nhân tạo (Cảnh báo bất định cao)'),

    # --- NHÓM 6: RUN-TO-FAILURE THỰC TẾ (PRONOSTIA DEGRADATION) ---
    ('p1', 'pronostia_early',            'PRONOSTIA Early (t=5%)',      'Đầu đời lành lặn, RUL 100%'),
    ('p2', 'pronostia_mid',              'PRONOSTIA Mid (t=74%)',        'Khởi phát tróc vảy mỏi, RUL 42%'),
    ('p3', 'pronostia_end',              'PRONOSTIA Terminal (t=98%)',   'Giai đoạn phá hủy vỡ nát, SIL-2 Emergency Trip')
]

def load_hil_weights():
    hil_dir = os.path.join(ROMS_DIR, 'profiles', 'prf01_cwru_motor_9ball')
    if not os.path.exists(hil_dir):
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

def load_pronostia_rul_weights():
    rul_candidates = [
        os.path.join(ROMS_DIR, 'pronostia_rul_weights.hex'),
        os.path.join(ROMS_DIR, 'hil', 'pronostia_rul_weights.hex'),
        os.path.join(REPO_ROOT, 'embedded', 'fpga_gowin', 'roms', 'pronostia_rul_weights.hex'),
        os.path.join(TOAN_DIR, 'roms', 'pronostia_rul_weights.hex')
    ]
    for p in rul_candidates:
        if os.path.exists(p):
            with open(p, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
            weights = []
            for l in lines[:261]:
                w = int(l, 16)
                if w >= 128: w -= 256
                weights.append(w)
            return np.array(weights, dtype=np.int32)
    return np.zeros(261, dtype=np.int32)

def compute_golden_continuous(spec_int8, weights, biases, rul_weights=None):
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

    # Dirichlet Epistemic Vacuity (u* = 4 / S)
    ev = np.maximum(np.array(scores) >> 6, 0)
    sum_e = int(np.sum(ev) + 4)
    vac_q15 = int(131072 // sum_e) if sum_e <= 131072 else 1
    vac_float = float(vac_q15) / 32768.0

    # Real PRONOSTIA Hardware RUL Model (Bit-true to npu_12way_core.v)
    if rul_weights is None or len(rul_weights) < 261:
        rul_weights = load_pronostia_rul_weights()
    in_261 = np.zeros(261, dtype=np.int32)
    in_261[:min(len(spec_int8), 261)] = spec_int8[:min(len(spec_int8), 261)]
    
    rul_mac_accum = int(np.dot(in_261, rul_weights))
    RUL_HW_MULT  = -220
    RUL_HW_SHIFT = 10
    RUL_HW_BIAS  = 30504

    rul_scaled = ((rul_mac_accum * RUL_HW_MULT) >> RUL_HW_SHIFT) + RUL_HW_BIAS
    rul_q15 = max(0, min(32768, rul_scaled))
    rul_pct = float(rul_q15) * 100.0 / 32768.0

    ood_alert = 1 if vac_q15 > 14745 else 0

    return pred, scores, packed, vac_q15, vac_float, rul_q15, rul_pct, ood_alert

def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() in ['-h', '--help', 'help', 'list']:
        print("=" * 82)
        print(" DANH SÁCH 28 TEST VECTORS CWRU & RUN-TO-FAILURE PRONOSTIA (CHO TOÀN DEMO)")
        print("=" * 82)
        print(f"{'STT':<4} | {'Mã Phím':<22} | {'Tên Kịch Bản':<30} | {'Mô Tả & Trạng Thái'}")
        print("-" * 82)
        for key, stem, name, desc in CATALOG:
            print(f"[{key:>2}] | {stem:<22} | {name:<30} | {desc}")
        print("=" * 82)
        print("👉 Cách dùng nhanh:")
        print("   python scripts/switch_cosim_vector.py 1    (Chọn Normal 0 HP)")
        print("   python scripts/switch_cosim_vector.py 6    (Chọn Inner 7-mil 1 HP)")
        print("   python scripts/switch_cosim_vector.py 17   (Chọn Inner 14-mil 1 HP - Rung mạnh)")
        print("   python scripts/switch_cosim_vector.py 20   (Chọn Inner 21-mil 1 HP - SIL-2 Emergency Trip)")
        print("   python scripts/switch_cosim_vector.py p3   (PRONOSTIA Cuối Đời 98% Life)")
        print("=" * 82)
        return

    choice = sys.argv[1].strip().lower()
    selected = None
    for key, stem, name, desc in CATALOG:
        if choice in [key.lower(), stem.lower(), f"{int(key):02d}" if key.isdigit() else '']:
            selected = (key, stem, name, desc)
            break

    if selected is None:
        print(f"[!] Lỗi: Không tìm thấy vector '{choice}'. Chạy 'python scripts/switch_cosim_vector.py list' để xem danh sách.")
        return

    key, stem, name, desc = selected

    # Locate source spectrum file
    spec_filename = f"golden_{stem}_spectrum_int8.hex"
    if stem.startswith('pronostia'):
        spec_filename = f"golden_{stem}_life_spectrum_int8.hex" if 'life' not in stem else f"golden_{stem}_spectrum_int8.hex"

    src_spec = os.path.join(TEST_VEC_DIR, spec_filename)
    if not os.path.exists(src_spec):
        # Fallback check
        alt_names = [f for f in os.listdir(TEST_VEC_DIR) if stem in f and f.endswith('.hex') and 'spectrum' in f]
        if alt_names:
            src_spec = os.path.join(TEST_VEC_DIR, alt_names[0])
        else:
            print(f"[!] Lỗi: Chưa tìm thấy tệp phổ {spec_filename} trong {TEST_VEC_DIR}.")
            return

    # Locate raw vibration file (512 samples INT16)
    raw_src = None
    possible_raw_dirs = [
        os.path.join(ROMS_DIR, 'stimulus_suite'),
        ROMS_DIR,
        os.path.join(CUR_DIR, 'roms', 'stimulus_suite'),
        os.path.join(CUR_DIR, 'roms')
    ]
    possible_raw_names = [
        f"{stem}.hex",
        f"stimulus_{stem}.hex",
        f"stimulus_{stem}_life.hex" if stem.startswith('pronostia') and 'life' not in stem else ""
    ]
    for rdir in possible_raw_dirs:
        if os.path.isdir(rdir):
            for rname in possible_raw_names:
                if rname:
                    cand = os.path.join(rdir, rname)
                    if os.path.exists(cand):
                        raw_src = cand
                        break
            if raw_src:
                break

    # Load spectrum input
    spec_data = []
    with open(src_spec, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                val = int(line, 16)
                if val >= 128: val -= 256
                spec_data.append(val)
    spec_arr = np.array(spec_data, dtype=np.int32)

    w = load_hil_weights()
    biases = [-5, -3, 14, -6]
    pred, scores, packed, vac_q15, vac_float, rul_q15, rul_pct, ood_alert = compute_golden_continuous(spec_arr, w, biases)

    # Target directories to sync: Repo, Toan's folder, Current folder
    target_dirs = []
    if os.path.exists(os.path.join(REPO_ROOT, 'test_vectors')) and REPO_ROOT not in target_dirs:
        target_dirs.append(REPO_ROOT)
    if os.path.exists(os.path.join(TOAN_DIR, 'test_vectors')) and TOAN_DIR not in target_dirs:
        target_dirs.append(TOAN_DIR)
    if os.path.exists(os.path.join(CUR_DIR, 'test_vectors')) and CUR_DIR not in target_dirs:
        target_dirs.append(CUR_DIR)

    for t_dir in target_dirs:
        tv_dir = os.path.join(t_dir, 'test_vectors')
        os.makedirs(tv_dir, exist_ok=True)
        cosim_in = os.path.join(tv_dir, 'cosim_input.hex')
        cosim_gold = os.path.join(tv_dir, 'cosim_golden.hex')

        shutil.copyfile(src_spec, cosim_in)
        with open(cosim_gold, 'w') as f:
            f.write(f"{pred:08X}\n")
            f.write(f"{packed:08X}\n")
            f.write("00000000\n")
            f.write("00000000\n")
            f.write("00000000\n")
            f.write(f"{vac_q15:08X}\n")
            f.write(f"{rul_q15:08X}\n")
            f.write(f"{ood_alert:08X}\n")

        if raw_src:
            r_dir = os.path.join(t_dir, 'roms')
            if os.path.exists(r_dir):
                shutil.copyfile(raw_src, os.path.join(r_dir, 'cosim_raw_vibration.hex'))

        tag = "Toàn Workspace" if t_dir == TOAN_DIR else "Repo"
        print(f"[+] [{tag}] Đã cập nhật test_vectors/cosim_input.hex & cosim_golden.hex")

    class_names = ["Normal (Baseline)", "Inner Race (BPFI)", "Outer Race (BPFO)", "Ball Fault (BSF)"]
    trip_str = "EMERGENCY TRIP (Cắt Rơ-le < 1.0ms)" if (pred != 0 and vac_float <= 0.45) else "NOMINAL RUN (Máy chạy bình thường)"

    print("\n" + "=" * 78)
    print(f" CẤU HÌNH THÀNH CÔNG VECTOR [{key}]: {name.upper()}")
    print("=" * 78)
    print(f"  * Mô tả tình trạng cơ khí:       {desc}")
    print(f"  * Sóng Rung Thô (Pre-DSP INT16):  {os.path.basename(raw_src) if raw_src else 'N/A'} (512 mẫu -> roms/cosim_raw_vibration.hex)")
    print(f"  * Phổ Tần Số NPU (Post-DSP INT8): {spec_filename} (257 bins -> test_vectors/cosim_input.hex)")
    print(f"  * Nhận Dạng Lỗi Phần Cứng (FPGA): Lớp {pred} -> {class_names[pred]}")
    print(f"  * Điểm Số Tích Lũy 12 Kênh MAC:  Scores = {scores}")
    print(f"  * RUL Động Liên Tục Phần Cứng:   {rul_pct:5.1f}% (Q15 = {rul_q15})")
    print(f"  * Độ Bất Định Dirichlet (u*):     {vac_float:.4f} (Q15 = {vac_q15})")
    print(f"  * Trạng Thái Rơ-le SIL-2:        {trip_str}")
    print("=" * 78)
    print("👉 Toàn mở ModelSim gõ 'do run.do.txt' để test Lõi NPU với phổ INT8 này!")
    print("👉 Muốn test toàn chuỗi DSP từ sóng thô: nạp roms/cosim_raw_vibration.hex vào Top SoC!")
    print("=" * 78)

if __name__ == '__main__':
    main()
