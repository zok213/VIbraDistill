#!/usr/bin/env python3
"""
Generate Comprehensive Industrial Stimulus Suite (28 Real Test Vectors)
Target: Gowin Tang Primer 20K FPGA & Sonix SN32F407 MCU
Sources: Raw CWRU 12 kHz .mat files across all 4 Loads (0-3 HP) and 3 Severities (7, 14, 21 mil) + OOD.
"""

import os
import json
import glob
import numpy as np
import scipy.io as sio

def load_mat_signal(mat_path):
    mat = sio.loadmat(mat_path)
    for k in mat.keys():
        if 'DE_time' in k:
            return mat[k].flatten()
    for k, v in mat.items():
        if isinstance(v, np.ndarray) and v.ndim == 2 and v.shape[1] == 1 and v.shape[0] > 1000:
            return v.flatten()
    raise ValueError(f"Could not find vibration signal in {mat_path}")

def normalize_to_int16(signal_window):
    max_val = np.max(np.abs(signal_window))
    if max_val < 1e-6:
        max_val = 1.0
    scale = 26000.0 / max_val
    scaled = np.round(signal_window * scale).astype(np.int32)
    clamped = np.clip(scaled, -32768, 32767).astype(np.int16)
    return clamped

def export_hex(samples_int16, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        for s in samples_int16:
            u16 = int(s) & 0xFFFF
            f.write(f"{u16:04X}\n")

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    cwru_dir = os.path.join(base_dir, 'data', 'CWRU_Dataset')
    out_dir = os.path.join(base_dir, 'embedded', 'fpga_gowin', 'roms', 'stimulus_suite')
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 74)
    print(" GENERATING COMPREHENSIVE INDUSTRIAL STIMULUS SUITE (28 TEST VECTORS)")
    print(f" Target Directory: {out_dir}")
    print("=" * 74)

    # Catalog definition: (filename, mat_pattern, offset, true_class, class_name, condition, description)
    test_specs = [
        # --- BỘ 1: TẢI 0 HP (1797 RPM) - 7 mil ---
        ("01_cwru_normal_0hp.hex", "*97*.mat", 1024, 0, "Normal", "0 HP / 1797 RPM", "Chuẩn vòng bi lành lặn 0 HP"),
        ("02_cwru_inner_7mil_0hp.hex", "*105*.mat", 1024, 1, "Inner", "0 HP / 1797 RPM", "Lỗi vòng trong 7-mil (BPFI ~162Hz)"),
        ("03_cwru_outer_7mil_0hp.hex", "*130*.mat", 1024, 2, "Outer", "0 HP / 1797 RPM", "Lỗi vòng ngoài 7-mil (BPFO ~107Hz)"),
        ("04_cwru_ball_7mil_0hp.hex", "*118*.mat", 1024, 3, "Ball", "0 HP / 1797 RPM", "Lỗi viên bi 7-mil (BSF ~71Hz)"),

        # --- BỘ 2: TẢI 1 HP (1772 RPM) - 7 mil ---
        ("05_cwru_normal_1hp.hex", "*98*.mat", 1024, 0, "Normal", "1 HP / 1772 RPM", "Chuẩn vòng bi lành lặn 1 HP"),
        ("06_cwru_inner_7mil_1hp.hex", "*106*.mat", 1024, 1, "Inner", "1 HP / 1772 RPM", "Lỗi vòng trong 7-mil tải 1 HP"),
        ("07_cwru_outer_7mil_1hp.hex", "*131*.mat", 1024, 2, "Outer", "1 HP / 1772 RPM", "Lỗi vòng ngoài 7-mil tải 1 HP"),
        ("08_cwru_ball_7mil_1hp.hex", "*119*.mat", 1024, 3, "Ball", "1 HP / 1772 RPM", "Lỗi viên bi 7-mil tải 1 HP"),

        # --- BỘ 3: TẢI 2 HP (1750 RPM) - 7 mil ---
        ("09_cwru_normal_2hp.hex", "*99*.mat", 1024, 0, "Normal", "2 HP / 1750 RPM", "Chuẩn vòng bi lành lặn 2 HP"),
        ("10_cwru_inner_7mil_2hp.hex", "*107*.mat", 1024, 1, "Inner", "2 HP / 1750 RPM", "Lỗi vòng trong 7-mil tải 2 HP"),
        ("11_cwru_outer_7mil_2hp.hex", "*132*.mat", 1024, 2, "Outer", "2 HP / 1750 RPM", "Lỗi vòng ngoài 7-mil tải 2 HP"),
        ("12_cwru_ball_7mil_2hp.hex", "*120*.mat", 1024, 3, "Ball", "2 HP / 1750 RPM", "Lỗi viên bi 7-mil tải 2 HP"),

        # --- BỘ 4: TẢI 3 HP (1730 RPM) - 7 mil ---
        ("13_cwru_normal_3hp.hex", "*100*.mat", 1024, 0, "Normal", "3 HP / 1730 RPM", "Chuẩn vòng bi lành lặn 3 HP"),
        ("14_cwru_inner_7mil_3hp.hex", "*108*.mat", 1024, 1, "Inner", "3 HP / 1730 RPM", "Lỗi vòng trong 7-mil tải 3 HP"),
        ("15_cwru_outer_7mil_3hp.hex", "*133*.mat", 1024, 2, "Outer", "3 HP / 1730 RPM", "Lỗi vòng ngoài 7-mil tải 3 HP"),
        ("16_cwru_ball_7mil_3hp.hex", "*121*.mat", 1024, 3, "Ball", "3 HP / 1730 RPM", "Lỗi viên bi 7-mil tải 3 HP"),

        # --- BỘ 5: MỨC ĐỘ HƯ HỎNG CHƯA TỪNG THẤY (14-MIL & 21-MIL) ---
        ("17_cwru_inner_14mil_1hp.hex", "*170*.mat", 1024, 1, "Inner", "1 HP / 14-mil", "Lỗi vòng trong vết nứt 14-mil"),
        ("18_cwru_outer_14mil_1hp.hex", "*198*.mat", 1024, 2, "Outer", "1 HP / 14-mil", "Lỗi vòng ngoài vết nứt 14-mil"),
        ("19_cwru_ball_14mil_1hp.hex", "*186*.mat", 1024, 3, "Ball", "1 HP / 14-mil", "Lỗi viên bi vết nứt 14-mil"),
        ("20_cwru_inner_21mil_1hp.hex", "*210*.mat", 1024, 1, "Inner", "1 HP / 21-mil", "Lỗi vòng trong phá hủy nặng 21-mil"),
        ("21_cwru_outer_21mil_1hp.hex", "*235*.mat", 1024, 2, "Outer", "1 HP / 21-mil", "Lỗi vòng ngoài phá hủy nặng 21-mil"),
        ("22_cwru_ball_21mil_1hp.hex", "*223*.mat", 1024, 3, "Ball", "1 HP / 21-mil", "Lỗi viên bi phá hủy nặng 21-mil"),

        # --- BỘ 6: CÁC CỬA SỔ THỜI GIAN ĐỘC LẬP (TEMPORAL WINDOWS) ---
        ("23_cwru_inner_7mil_win2.hex", "*105*.mat", 4096, 1, "Inner", "0 HP / Window 2", "Cửa sổ thời gian số 2 (Offset 4096)"),
        ("24_cwru_inner_7mil_win3.hex", "*105*.mat", 8192, 1, "Inner", "0 HP / Window 3", "Cửa sổ thời gian số 3 (Offset 8192)"),
        ("25_cwru_outer_7mil_win2.hex", "*130*.mat", 4096, 2, "Outer", "0 HP / Window 2", "Cửa sổ thời gian số 2 (Offset 4096)"),
        ("26_cwru_outer_7mil_win3.hex", "*130*.mat", 8192, 2, "Outer", "0 HP / Window 3", "Cửa sổ thời gian số 3 (Offset 8192)"),

        # --- BỘ 7: KIỂM THỬ ANOMALY & OUT-OF-DISTRIBUTION (OOD) ---
        ("27_ood_high_noise.hex", None, 0, -1, "OOD Anomaly", "Gaussian Noise", "Nhiễu trắng biên độ cao (Test đèn OOD Vacuity)"),
        ("28_ood_synthetic_multitone.hex", None, 0, -1, "OOD Anomaly", "Synthetic Multitone", "Tín hiệu cộng hưởng lạ 450Hz & 850Hz")
    ]

    manifest = []
    
    for filename, mat_pattern, offset, true_cls, cls_name, cond, desc in test_specs:
        out_path = os.path.join(out_dir, filename)
        if mat_pattern is not None:
            files = glob.glob(os.path.join(cwru_dir, '**', mat_pattern), recursive=True)
            if not files:
                raise FileNotFoundError(f"Pattern {mat_pattern} not found in {cwru_dir}")
            mat_file = files[0]
            raw_sig = load_mat_signal(mat_file)
            assert len(raw_sig) >= offset + 512, f"File {mat_file} too short for offset {offset}"
            window = raw_sig[offset:offset+512]
        else:
            # Synthetic OOD
            t = np.linspace(0, 512/12000, 512)
            if "noise" in filename:
                np.random.seed(42)
                window = np.random.randn(512) * 0.8
            else:
                window = 0.5 * np.sin(2 * np.pi * 450 * t) + 0.4 * np.sin(2 * np.pi * 850 * t)
        
        int16_samples = normalize_to_int16(window)
        assert len(int16_samples) == 512, f"Length must be 512, got {len(int16_samples)}"
        export_hex(int16_samples, out_path)
        
        manifest.append({
            "file": filename,
            "true_class_id": true_cls,
            "true_class_name": cls_name,
            "condition": cond,
            "description": desc,
            "size_words": 512
        })
        print(f"  [OK] Exported {filename:32s} | Class: {cls_name:12s} | {cond}")

    # Write manifest json
    manifest_path = os.path.join(out_dir, "stimulus_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Saved manifest metadata to: {manifest_path}")

    # Also copy the 5 legacy files into roms/ for immediate backward compatibility
    import shutil
    shutil.copyfile(os.path.join(out_dir, "01_cwru_normal_0hp.hex"), os.path.join(base_dir, "embedded", "fpga_gowin", "roms", "stimulus_cwru_normal.hex"))
    shutil.copyfile(os.path.join(out_dir, "02_cwru_inner_7mil_0hp.hex"), os.path.join(base_dir, "embedded", "fpga_gowin", "roms", "stimulus_cwru_inner.hex"))
    shutil.copyfile(os.path.join(out_dir, "03_cwru_outer_7mil_0hp.hex"), os.path.join(base_dir, "embedded", "fpga_gowin", "roms", "stimulus_cwru_outer.hex"))
    shutil.copyfile(os.path.join(out_dir, "04_cwru_ball_7mil_0hp.hex"), os.path.join(base_dir, "embedded", "fpga_gowin", "roms", "stimulus_cwru_ball.hex"))
    shutil.copyfile(os.path.join(out_dir, "27_ood_high_noise.hex"), os.path.join(base_dir, "embedded", "fpga_gowin", "roms", "stimulus_cwru_mixed.hex"))
    print("[+] Updated legacy roms/stimulus_cwru_*.hex symlinks/copies.")

    # Write STIMULUS_CATALOG.md
    catalog_md = os.path.join(out_dir, "STIMULUS_CATALOG.md")
    with open(catalog_md, 'w', encoding='utf-8') as f:
        f.write("# DANH MỤC 28 TỆP SÓNG RUNG KIỂM THỬ CÔNG NGHIỆP TRÊN FPGA\n")
        f.write("## (COMPREHENSIVE INDUSTRIAL STIMULUS SUITE CATALOG)\n\n")
        f.write("> Thư mục lưu trữ: `embedded/fpga_gowin/roms/stimulus_suite/`  \n")
        f.write("> Toàn bộ 28 tệp đều có định dạng: **512 mẫu sóng rung thời gian, 16-bit signed hex, tần số trích xuất 12,000 Hz**.\n\n")
        f.write("| STT | Tên Tệp `.hex` | Lớp Chuẩn (True Class) | Điều Kiện Tải / Tốc Độ | Mô Tả Kỹ Thuật | Phản Ứng Dự Kiến Của FPGA |\n")
        f.write("| :---: | :--- | :---: | :--- | :--- | :--- |\n")
        for i, item in enumerate(manifest, 1):
            exp_action = "Trip Rơ-le SIL-2 (< 1.0ms)" if item["true_class_id"] in [1, 2, 3] else ("Bật LED OOD Alert (u > 0.45)" if item["true_class_id"] == -1 else "Bình thường (Relay đóng)")
            f.write(f"| {i:02d} | `{item['file']}` | **{item['true_class_name']}** | {item['condition']} | {item['description']} | {exp_action} |\n")
    print(f"[+] Saved comprehensive documentation catalog to: {catalog_md}")

if __name__ == '__main__':
    main()
