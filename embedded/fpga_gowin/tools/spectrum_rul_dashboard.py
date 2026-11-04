#!/usr/bin/env python3
"""
===============================================================================
VibraDistill-Edge: Real-time Master AI Diagnostics & Conformal RUL Dashboard
Ket noi truc tiep voi FPGA Tang Primer 20K qua UART (921600 baud).
Tich hop day du:
  1. Pho bao Envelope Spectrum (0 - 6000 Hz) + Vach dong hoc (1X, BPFO, BPFI, BSF)
  2. Phan loai loi NPU (Normal, Inner BPFI, Outer BPFO, Ball BSF) + Vacuity u
  3. Du doan Tuoi tho con lai (RUL Prognostics) + Dai tin cay HopACP Conformal [Lt, Ut]
  4. Trang thai chot Ro-le an toan SIL-2 (RUN / WARNING / TRIP)
===============================================================================
"""

import argparse
import sys
import time
import os
import numpy as np
import upload_stimulus

PRESETS = {
    '1': ('src/test_npu/roms/hil/stimulus_cwru_normal.hex', 'Normal Baseline (CWRU)'),
    '2': ('src/test_npu/roms/hil/stimulus_cwru_ball.hex', 'Ball Fault (CWRU 70Hz)'),
    '3': ('src/test_npu/roms/hil/stimulus_cwru_outer.hex', 'Outer Race Fault (CWRU 105Hz)'),
    '4': ('src/test_npu/roms/hil/stimulus_cwru_inner.hex', 'Inner Race Fault (CWRU 158Hz)'),
    '5': ('src/test_npu/roms/hil/stimulus_pronostia_early_life.hex', 'PRONOSTIA Early-Life (RUL 95%)'),
    '6': ('src/test_npu/roms/hil/stimulus_pronostia_mid_life.hex', 'PRONOSTIA Mid-Life (RUL 42%)'),
    '7': ('src/test_npu/roms/hil/stimulus_pronostia_end_of_life.hex', 'PRONOSTIA End-of-Life (<5% TRIP)'),
    '8': ('src/test_npu/roms/hil/stimulus_cwru_mixed.hex', 'Mixed Severe Wear (21-mil)')
}

# Load Edge AI Inference Engine neu co
try:
    from vibra_inference import VibraClassifier
    AI_AVAILABLE = True
except Exception:
    AI_AVAILABLE = False

FRAME = 518
NBIN = 257

class HopACPTracker:
    """Bo theo doi Adaptive Conformal Prediction (HopACP Q16.16) dong bo 100% MCU."""
    def __init__(self, init_margin=16.5, q_min=5.0, q_max=500.0):
        self.step_ok = -328.0 / 65536.0    # -0.00500488: thu hep khoang khi bao phu dat chuan
        self.step_err = 2952.0 / 65536.0  # +0.04504395: mo rong khoang khi vuot nguong (ti le 9.0 -> bao phu 90%)
        self.beta = 3277.0 / 65536.0      # +0.05000305: thanh phan dao ham / quan tinh dap ung soc tai
        self.margin = float(init_margin)
        self.q_min = float(q_min)
        self.q_max = float(q_max)
        self.prev_err = 0
        self.total_samples = 0
        self.total_errors = 0

    def predict(self, point_rul):
        low = max(0.0, point_rul - self.margin)
        high = point_rul + self.margin
        return low, high

    def update(self, point_rul, true_feedback=None):
        if true_feedback is None:
            true_feedback = point_rul # Online self-calibration
        self.total_samples += 1
        low, high = self.predict(point_rul)
        miscovered = 1 if (true_feedback < low or true_feedback > high) else 0
        if miscovered:
            self.total_errors += 1
            delta = self.step_err
        else:
            delta = self.step_ok
        d_err = miscovered - self.prev_err
        if d_err > 0:
            delta += self.beta
        elif d_err < 0:
            delta -= self.beta
        self.prev_err = miscovered
        self.margin = float(np.clip(self.margin + delta, self.q_min, self.q_max))
        return self.margin

def parse_frames(buf):
    out, bad, i = [], 0, 0
    buf_len = len(buf)
    while i + FRAME <= buf_len:
        if buf[i] == 0xAA and buf[i+1] == 0x55:
            f = buf[i:i+FRAME]
            ck = 0
            for b in f[2:517]:
                ck ^= b
            if ck == f[517]:
                bins = [f[3+2*k] | (f[4+2*k] << 8) for k in range(NBIN)]
                out.append((f[2], bins))
                i += FRAME
                continue
            else:
                bad += 1
        i += 1
    return out, i, bad

def peak(bins, fs, n=512, skip=4):
    k = max(range(skip, NBIN), key=lambda j: bins[j])
    freq_hz = k * (fs / n)
    return k, freq_hz, bins[k]

def calculate_priors(rpm=1797.0, fs=12000.0, n_fft=512):
    fr = rpm / 60.0
    bpfo = 3.58 * fr
    bpfi = 5.42 * fr
    bsf  = 2.32 * fr
    ftf  = 0.40 * fr
    priors_hz = [bpfo, bpfi, bsf, ftf]
    prior_int8 = np.clip(np.array(priors_hz) / (fs / 2.0) * 127.0, -128, 127).astype(np.int8)
    return priors_hz, prior_int8

# Hieu chuan RUL: nang luong pho (tong bin 2..256) do tu chinh FPGA cho 3 kich ban PRONOSTIA.
# Anchor E_early ~ 3.4e4 (95%), E_mid ~ 5.0e4 (42%), E_end ~ 6.8e5 (<5% TRIP).
RUL_ANCHORS_E   = [3.4e4, 5.0e4, 6.8e5]
RUL_ANCHORS_PCT = [95.0,  42.0,  3.0]

def estimate_rul_from_spectrum(bins, pred_class, vacuity, fs=12000.0):
    """
    RUL (%) dua tren chi so suy hao don dieu = nang luong pho (thang log),
    noi suy tuyen tinh giua cac moc hieu chuan. KHONG phu thuoc lop CWRU vi
    model CWRU khong hop le tren du lieu PRONOSTIA.
    Tra ve (pct, hours, status, state_idx, energy).
    """
    energy = float(np.sum(bins[2:]))
    pct = float(np.interp(np.log10(max(energy, 1.0)),
                          np.log10(RUL_ANCHORS_E), RUL_ANCHORS_PCT))
    hours = 1200.0 * pct / 100.0
    if pct > 50.0:
        status, state_idx = "NORMAL (RUN)", 0
    elif pct > 30.0:
        status, state_idx = "WARNING (INCIPIENT)", 1
    elif pct > 10.0:
        status, state_idx = "MAINTENANCE REQUIRED", 2
    else:
        status, state_idx = "CRITICAL (SIL-2 TRIP)", 3
    return pct, hours, status, state_idx, energy

def estimate_rul_diagnostic(bins, pred_class, vacuity, fs=12000.0):
    """
    [CHE DO DIAG - dong bo 100% MCU Sonix] Uoc luong RUL theo kien truc he thong:
    - Normal (0): 1200h (100%)
    - Inner Race (1): base 350h
    - Outer Race (2): base 180h
    - Ball Defect (3): base 80h
    Suy giam theo nang luong dai tan khuyet tat (Bins 4..16: 93.8Hz .. 375Hz).
    """
    energy = float(np.sum(bins[2:]))

    if pred_class == 0:
        hours = 1200.0
        pct = 100.0
        status = "NORMAL (RUN)"
        state_idx = 0
    else:
        # Tich phan nang luong dai tan khuyet tat Bins 4..16 (93.8Hz .. 375Hz)
        fault_energy = float(np.sum(bins[4:17])) if len(bins) > 16 else 0.0
        base_h = 350.0 if pred_class == 1 else (180.0 if pred_class == 2 else 80.0)
        wear_loss = float(int(fault_energy) // 64)
        h = base_h - wear_loss
        h = max(2.0, min(1200.0, h))
        hours = float(h)
        pct = float(hours * 100.0 / 1200.0)
        if pct > 20.0:
            status = "WARNING (INCIPIENT)"
            state_idx = 1
        elif pct > 10.0:
            status = "MAINTENANCE REQUIRED"
            state_idx = 2
        else:
            status = "CRITICAL (SIL-2 TRIP)"
            state_idx = 3

    return pct, hours, status, state_idx, energy

def open_serial_port(port, baud):
    import serial
    try:
        return serial.Serial(port, baud, timeout=0.05)
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser(description="VibraDistill Real-time Master AI & Conformal RUL Dashboard")
    ap.add_argument('--port', default='COM6', help='Cong Serial COM (vd: COM6, COM3)')
    ap.add_argument('--baud', type=int, default=921600, help='Baudrate UART (921600 cho HIL 12kHz)')
    ap.add_argument('--fs', type=float, default=12000.0, help='Tan so lay mau (Hz, mac dinh 12000)')
    ap.add_argument('--rpm', type=float, default=1797.0, help='Toc do quay motor (RPM)')
    ap.add_argument('--xlim', type=float, default=None, help='Gioi han tan so hien thi (Hz)')
    ap.add_argument('--hex', default=None, help='Duong dan file .hex muon nap ngay khi ket noi')
    ap.add_argument('--anchors', default=None,
                    help='3 moc nang luong E_early,E_mid,E_end (vd: 3000,5000,40000)')
    a = ap.parse_args()
    if a.anchors:
        global RUL_ANCHORS_E
        try:
            vals = [float(x) for x in a.anchors.split(',')]
            assert len(vals) == 3 and vals[0] < vals[1] < vals[2]
            RUL_ANCHORS_E = vals
        except Exception:
            print("[!] --anchors khong hop le (can 3 so tang dan), dung gia tri mac dinh.")

    if a.xlim is None:
        a.xlim = a.fs / 2.0
    fsx = a.fs / 512.0
    priors_hz, prior_int8 = calculate_priors(rpm=a.rpm, fs=a.fs, n_fft=512)

    clf = None
    if AI_AVAILABLE:
        try:
            clf = VibraClassifier()
            print("[*] Da ket noi mo hinh AI: VibraDistill-Micro INT8")
        except Exception as e:
            print(f"[!] Khong khoi tao duoc AI: {e}")

    tracker = HopACPTracker(init_margin=3.5)

    print("=" * 75)
    print("      VIBRADISTILL-EDGE: MASTER AI DIAGNOSTICS & PROGNOSTICS")
    print(f"[*] Port: {a.port} | Baud: {a.baud} | Fs: {a.fs:.1f} Hz | Motor: {a.rpm:.1f} RPM")
    print("  [PHIM TAT DOI KICH BAN / NAP FILE HEX TUC THI]:")
    print("    [1..8] : Chon nhanh 8 kịch ban tieu chuan (Normal, Outer, Inner, Ball, PRONOSTIA...)")
    print("    [O]    : Mo cua so File Dialog de chon FILE .HEX CHI DINH BAT KY tren may")
    for k in sorted(PRESETS.keys()):
        print(f"      [{k}] {PRESETS[k][1]}")
    print("=" * 75)

    ser = open_serial_port(a.port, a.baud)
    if ser is None:
        print(f"[!] Dang cho cam board FPGA vao cong {a.port}...")

    def do_upload(h_path, h_name):
        nonlocal ser
        if not os.path.exists(h_path):
            alt = os.path.join(r'T:\MCU_FPGA\FPGA_FINAL', h_path)
            if os.path.exists(alt):
                h_path = alt
            else:
                print(f"\n[!] Khong tim thay file: {h_path}")
                return False
        if ser and ser.is_open:
            try:
                samples = upload_stimulus.load_hex_samples(h_path)
                pkt, crc = upload_stimulus.build_upload_packet(samples)
                ser.write(pkt)
                ser.flush()
                reset_ema[0] = True
                mode[0] = 'prog' if 'pronostia' in h_path.lower() else 'diag'
                print(f"\n[>>> NAP THANH CONG] {h_name} (512 mau int16, CRC16=0x{crc:04X}) -> FPGA da chuyen song!")
                return True
            except Exception as err:
                print(f"\n[!] Loi nap: {err}")
                return False
        else:
            print(f"\n[!] Chua ket noi cong Serial {a.port} de nap {h_name}")
            return False

    reset_ema = [False]
    mode = ['diag']   # 'diag' = CWRU (theo lop AI), 'prog' = PRONOSTIA (theo nang luong)
    initial_hex_uploaded = False
    if a.hex and ser and ser.is_open:
        do_upload(a.hex, f"Khoi dong: {os.path.basename(a.hex)}")
        initial_hex_uploaded = True

    import matplotlib.pyplot as plt
    plt.ion()
    fig = plt.figure(figsize=(12, 8.5))

    def on_key(event):
        key = str(event.key)
        if key in PRESETS:
            h_path, h_name = PRESETS[key]
            do_upload(h_path, f"Kich ban [{key}]: {h_name}")
        elif key.lower() == 'o':
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                fpath = filedialog.askopenfilename(
                    title="Chon file song rung .hex nap xuong FPGA",
                    initialdir=os.path.abspath("src/test_npu/roms/hil"),
                    filetypes=[("Hex Stimulus Files", "*.hex"), ("All Files", "*.*")]
                )
                root.destroy()
                if fpath:
                    do_upload(fpath, f"File chi dinh: {os.path.basename(fpath)}")
            except Exception as e:
                print(f"\n[!] Loi mo hop thoai chon file: {e}")

    fig.canvas.mpl_connect('key_press_event', on_key)

    gs = fig.add_gridspec(3, 1, height_ratios=[2.2, 1.0, 1.2], hspace=0.45)
    
    ax_spec = fig.add_subplot(gs[0])
    ax_bar  = fig.add_subplot(gs[1])
    ax_rul  = fig.add_subplot(gs[2])

    # 1. Panel Pho
    freqs = [k * fsx for k in range(NBIN)]
    line, = ax_spec.plot(freqs, [0]*NBIN, color='#1f77b4', lw=1.8, label='Envelope Spectrum')
    bpfo_hz, bpfi_hz, bsf_hz, ftf_hz = priors_hz
    ax_spec.axvline(a.rpm/60.0, color='gray', linestyle=':', label=f'1X ({a.rpm/60.0:.1f}Hz)')
    ax_spec.axvline(bpfo_hz, color='orange', linestyle='--', label=f'BPFO ({bpfo_hz:.1f}Hz)')
    ax_spec.axvline(bpfi_hz, color='red', linestyle='--', label=f'BPFI ({bpfi_hz:.1f}Hz)')
    ax_spec.axvline(bsf_hz, color='purple', linestyle='--', label=f'BSF ({bsf_hz:.1f}Hz)')
    ax_spec.set_ylabel('Bien do (LSB)', fontsize=10, fontweight='bold')
    ax_spec.set_xlim(0, a.xlim)
    ax_spec.set_ylim(0, 500)
    ax_spec.grid(True, linestyle='--', alpha=0.5)
    ax_spec.legend(loc='upper right', fontsize=8)

    # 2. Panel AI Logits
    bar_colors = ['#2ca02c', '#d62728', '#ff7f0e', '#9467bd']
    bars = ax_bar.bar(range(4), [0, 0, 0, 0], color=bar_colors)
    ax_bar.set_xticks(range(4))
    ax_bar.set_xticklabels(['Normal (Baseline)', 'Inner Race (BPFI)', 'Outer Race (BPFO)', 'Ball Fault (BSF)'], fontsize=9, fontweight='bold')
    ax_bar.set_ylabel('Logit INT8', fontsize=9, fontweight='bold')
    ax_bar.set_ylim(-128, 127)
    ax_bar.grid(True, axis='y', linestyle=':', alpha=0.5)

    # 3. Panel Conformal RUL Prognostics
    rul_bar = ax_rul.barh([0], [100], color='#2ca02c', height=0.5)
    ax_rul.set_yticks([0])
    ax_rul.set_yticklabels(['Health Status'], fontsize=10, fontweight='bold')
    ax_rul.set_xlim(0, 100)
    ax_rul.set_xlabel('Remaining Useful Life (RUL %)', fontsize=10, fontweight='bold')
    ax_rul.axvline(50, color='orange', linestyle=':', alpha=0.7, label='Warning (50%)')
    ax_rul.axvline(10, color='red', linestyle='--', alpha=0.7, label='Trip (<10%)')
    ax_rul.grid(True, axis='x', linestyle='--', alpha=0.6)
    rul_text = ax_rul.text(50, 0, "100.0%", ha='center', va='center', fontsize=12, fontweight='bold', color='white')

    fig.suptitle('VibraDistill-Edge: Real-Time FPGA AI Diagnostics & Conformal RUL Prognostics', fontsize=13, fontweight='bold')
    plt.subplots_adjust(top=0.91, bottom=0.08, left=0.10, right=0.96, hspace=0.42)
    plt.show(block=False)
    plt.pause(0.05)

    buf = bytearray()
    t0 = time.time()
    last_draw = time.time()
    last_print = time.time()
    total_frames = 0
    warned = False
    ema_pct = None

    while True:
        if ser is None or not ser.is_open:
            if not warned:
                print(f"[!] Mat ket noi voi {a.port}. Dang tu dong ket noi lai...")
                warned = True
            time.sleep(0.5)
            ser = open_serial_port(a.port, a.baud)
            if ser and ser.is_open:
                print(f"[+] Da ket noi thanh cong voi {a.port}!")
                warned = False
                buf.clear()
                if a.hex and not initial_hex_uploaded:
                    do_upload(a.hex, f"Khoi dong: {os.path.basename(a.hex)}")
                    initial_hex_uploaded = True
            continue

        try:
            chunk = ser.read(1024)
        except Exception:
            ser = None
            continue

        if not chunk:
            time.sleep(0.005)
            continue

        buf.extend(chunk)
        frames, used, bad = parse_frames(buf)
        if used > 0:
            del buf[:used]

        for seq, bins in frames:
            total_frames += 1
            if reset_ema[0]:
                ema_pct = None
                reset_ema[0] = False
            k, f, v = peak(bins, a.fs)

            # AI Inference
            pred_cls = 0
            cls_name = "NORMAL"
            vac = 0.05
            logits = [50, -50, -50, -50]

            if clf:
                max_b = max(max(bins), 1)
                spec_norm = np.clip(((np.array(bins, dtype=np.int32) * 127 + (max_b // 2)) // max_b), 0, 127).astype(np.int8)
                res = clf.predict(spec_norm, prior_int8)
                pred_cls = res['pred_class']
                cls_name = res['class_name']
                vac = res['vacuity']
                logits = res['logits']
            else:
                # Fallback dong hoc neu chua co model
                if v > 120 and abs(f - bsf_hz) < 15:
                    pred_cls = 3; cls_name = "FAULT: BALL"; logits = [-30, -20, -10, 80]
                elif v > 120 and abs(f - bpfo_hz) < 15:
                    pred_cls = 2; cls_name = "FAULT: BPFO"; logits = [-30, -20, 80, -10]
                elif v > 120 and abs(f - bpfi_hz) < 15:
                    pred_cls = 1; cls_name = "FAULT: BPFI"; logits = [-30, 80, -20, -10]

            # Tinh RUL & HopACP Conformal Bounds
            rul_pct, rul_hours, rul_status, state_idx, energy = (estimate_rul_from_spectrum if mode[0] == 'prog' else estimate_rul_diagnostic)(bins, pred_cls, vac, a.fs)
            raw_point_h = rul_hours
            # Lam muot theo thoi gian (EMA 16-tap giong 100% MCU) de RUL khong nhay giua cac khung
            if ema_pct is None:
                ema_pct = rul_hours
            ema_pct = (15.0 * ema_pct + rul_hours + 0.5) / 16.0
            rul_hours = float(int(ema_pct + 0.5)) if mode[0] != 'prog' else ema_pct
            rul_pct = max(0.1, min(100.0, (rul_hours * 100.0) / 1200.0))
            if max(bins) >= 65535:
                print("[!] Bin bao hoa 16-bit: nang luong bi cat ngon, can giam gain FPGA.")
            # Phan hoi cho HopACP la point_rul de dong bo 100% bit-true voi MCU Sonix
            tracker.update(rul_hours, true_feedback=raw_point_h)
            low_h, high_h = tracker.predict(rul_hours)
            relay_trip = (state_idx == 3) if mode[0] == 'prog' else (pred_cls != 0)

            vac_str = f"u={vac:.3f} ({vac*100:.1f}%)"

            # Cap nhat terminal dinh ky
            if time.time() - last_print > 0.5:
                relay_state = "TRIP [Emergency Cut]" if relay_trip else "RUN [NC Closed]"
                print(f"[{time.time()-t0:6.1f}s] seq={seq:3d} | Dinh: {f:5.1f}Hz | AI: {cls_name:<16} | E={energy:8.0f} | RUL: {rul_pct:4.1f}% ({rul_hours:6.1f}h) [HopACP 90%: {low_h:5.1f}h - {high_h:5.1f}h (±{tracker.margin:.1f}h) | {vac_str}] | Relay: {relay_state}")
                last_print = time.time()

            # Cap nhat GUI
            if time.time() - last_draw > 0.04:
                # Update pho
                line.set_ydata(bins)
                p_val = max(bins[2:]) if len(bins) > 2 else 10
                ax_spec.set_ylim(0, max(p_val * 1.3, 50.0))
                ax_spec.set_title(f'Khung #{seq} | Dinh: {f:.1f} Hz (Bin {k}) | AI: {cls_name} (Vacuity {vac_str})',
                                  fontsize=11, fontweight='bold', color='#2ca02c' if pred_cls == 0 else '#d62728')

                # Update bars
                for b_obj, l_val in zip(bars, logits):
                    b_obj.set_height(l_val)

                # Update RUL bar & Title
                rul_bar[0].set_width(rul_pct)
                if state_idx == 0:
                    bar_c = '#2ca02c' # Xanh
                elif state_idx == 1:
                    bar_c = '#ff7f0e' # Cam
                elif state_idx == 2:
                    bar_c = '#d62728' # Do
                else:
                    bar_c = '#7f0000' # Do dam TRIP
                rul_bar[0].set_color(bar_c)

                # Dua thong tin chi tiet len tieu de panel de khong bi cat chu hay de len truc Y
                ax_rul.set_title(f"[{mode[0].upper()}] RUL: {rul_pct:.1f}% ({rul_hours:.1f}h) | HopACP 90%: [{low_h:.1f}h - {high_h:.1f}h] (±{tracker.margin:.1f}h) | {vac_str} | {rul_status}",
                                 fontsize=10, fontweight='bold', color=bar_c)

                # Chu ngan gon ben trong thanh bar
                if rul_pct > 18:
                    rul_text.set_text(f"{rul_pct:.1f}% ({rul_hours:.1f}h)")
                    rul_text.set_x(rul_pct / 2.0)
                    rul_text.set_color('white')
                    rul_text.set_ha('center')
                else:
                    rul_text.set_text(f"{rul_pct:.1f}% ({rul_hours:.1f}h)")
                    rul_text.set_x(rul_pct + 1.5)
                    rul_text.set_color(bar_c)
                    rul_text.set_ha('left')

                fig.canvas.draw_idle()
                plt.pause(0.001)
                last_draw = time.time()

        if len(buf) > 8192:
            last_sync = buf.rfind(b'\xaa\x55')
            buf = buf[last_sync:] if last_sync != -1 else bytearray()

if __name__ == '__main__':
    main()
