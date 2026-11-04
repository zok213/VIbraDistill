#!/usr/bin/env python3
"""
VibraDistill-Edge: Real-time Envelope Spectrum Viewer & Edge AI Diagnostic Dashboard
Ket noi voi FPGA Tang Primer 20K qua UART, hien thi pho va chay mo hinh AI (VibraDistill-Micro).
Ho tro tu dong ket noi lai (AUTO-RECONNECT) khi rut/cam cap CP2102 hoac cap USB BL702.

Cach dung:
    # 1. Che do HIL (Tan so 12 kHz, CWRU dataset - Mac dinh cho ban FPGA_FINAL):
    python spectrum_viewer.py --port COM6 --baud 921600 --fs 12000

    # 2. Che do ADXL345 (Tan so 3.2 kHz):
    python spectrum_viewer.py --port COM6 --baud 115200 --fs 3200

    # 3. Kiem tra file offline:
    python spectrum_viewer.py --file raw_spectrum.hex --fs 12000
"""

import argparse
import csv
import sys
import time
import numpy as np

# Load Edge AI Inference Engine
try:
    from vibra_inference import VibraClassifier
    AI_AVAILABLE = True
except Exception as e:
    AI_AVAILABLE = False
    # Bo qua canh bao neu chua co file inference rieng
    pass

FRAME = 518
NBIN = 257

def parse_frames(buf):
    """Tra ve (danh sach (seq, bins), so byte da dung, so khung loi checksum)."""
    out, bad, i = [], 0, 0
    buf_len = len(buf)
    while i + FRAME <= buf_len:
        if buf[i] == 0xAA and buf[i+1] == 0x55:
            f = buf[i:i+FRAME]
            ck = 0
            for b in f[2:517]:
                ck ^= b
            if ck == f[517]:
                # 257 bin, moi bin 16-bit little-endian (lo | hi << 8)
                bins = [f[3+2*k] | (f[4+2*k] << 8) for k in range(NBIN)]
                out.append((f[2], bins))
                i += FRAME
                continue
            else:
                bad += 1
        i += 1
    return out, i, bad

def peak(bins, fs, n=512, skip=4):
    """Tim dinh pho cao nhat (bo qua cac bin DC va chan doc ro tan so thap < 95 Hz)."""
    k = max(range(skip, NBIN), key=lambda j: bins[j])
    freq_hz = k * (fs / n)
    return k, freq_hz, bins[k]

def calculate_priors(rpm=1797.0, fs=12000.0, n_fft=512):
    """
    Tinh 4 chi so vat ly dong hoc (BPFO, BPFI, BSF, FTF) cho SKF 6205:
    Nb=9, d=7.94mm, D=39.04mm, alpha=0 deg
    """
    fr = rpm / 60.0
    bpfo = 3.58 * fr
    bpfi = 5.42 * fr
    bsf  = 2.32 * fr
    ftf  = 0.40 * fr
    
    delta_f = fs / n_fft
    priors_hz = [bpfo, bpfi, bsf, ftf]
    prior_int8 = np.clip(np.array(priors_hz) / (fs / 2.0) * 127.0, -128, 127).astype(np.int8)
    return priors_hz, prior_int8

def open_serial_port(port, baud):
    import serial
    try:
        ser = serial.Serial(port, baud, timeout=0.05)
        return ser
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser(description="VibraDistill Real-time Spectrum & AI Diagnostic")
    ap.add_argument('--port', default='COM6', help='Cong Serial COM (vd: COM6, COM3)')
    ap.add_argument('--baud', type=int, default=921600, 
                    help='Baudrate UART (Mac dinh 921600 cho HIL 12kHz; dung 115200 neu adapter cu)')
    ap.add_argument('--fs', type=float, default=12000.0, 
                    help='Tan so lay mau (Hz) - 12000 Hz cho HIL CWRU, 3200 Hz cho ADXL345')
    ap.add_argument('--rpm', type=float, default=1797.0, help='Toc do quay motor (RPM)')
    ap.add_argument('--xlim', type=float, default=None, 
                    help='Gioi han tan so hien thi truc X (Hz, mac dinh tu dong = Fs/2)')
    ap.add_argument('--file', help='Che do doc file offline')
    ap.add_argument('--csv', help='Ghi log ra file CSV')
    ap.add_argument('--noplot', action='store_true', help='Khong mo cua so do thi')
    a = ap.parse_args()

    # Tu dong dat gioi han hien thi truc tan so theo Nyquist neu khong truyen --xlim
    if a.xlim is None:
        a.xlim = a.fs / 2.0

    fsx = a.fs / 512.0 # Do phan giai moi bin FFT (Hz/bin)
    priors_hz, prior_int8 = calculate_priors(rpm=a.rpm, fs=a.fs, n_fft=512)

    clf = None
    if AI_AVAILABLE:
        try:
            clf = VibraClassifier()
            print(">>> DA KET NOI MODEL AI: VibraDistill-Micro (SKF 6205 INT8) <<<")
        except Exception as e:
            print(f">>> Khong the khoi tao model AI: {e}")

    # Che do doc file offline
    if a.file:
        raw = open(a.file, 'rb').read()
        try:
            buf = bytes(int(t, 16) for t in raw.decode().split())
        except Exception:
            buf = raw
        frames, _, bad = parse_frames(buf)
        print(f"{len(frames)} khung hop le, {bad} loi checksum")
        for seq, bins in frames:
            k, f, v = peak(bins, a.fs)
            ai_info = ""
            if clf:
                if getattr(clf, 'mode', '') == 'hil_12ch' or a.fs > 5000:
                    max_b = max(max(bins), 1)
                    spec_norm = np.clip(((np.array(bins, dtype=np.int32) * 127 + (max_b // 2)) // max_b), 0, 127).astype(np.int8)
                else:
                    max_b = max(max(bins[2:]), 1)
                    spec_norm = np.clip(np.array(bins) / max_b * 127.0, -128, 127).astype(np.int8)
                res = clf.predict(spec_norm, prior_int8)
                ai_info = f" | AI: {res['class_name']} (Vacuity={res['vacuity']:.3f})"
            print(f"seq={seq:3d} | Dinh bin {k:3d} = {f:6.2f} Hz (A={v:5d}){ai_info}")
        return

    import serial
    print("=" * 70)
    print(f"[*] VibraDistill Spectrum Viewer")
    print(f"[*] Cong: {a.port} | Baudrate: {a.baud} | Fs: {a.fs:.1f} Hz (df={fsx:.2f} Hz/bin)")
    print(f"[*] Motor RPM: {a.rpm:.1f} | Truc X: 0 - {a.xlim:.1f} Hz")
    print("=" * 70)

    ser = open_serial_port(a.port, a.baud)
    if ser is None:
        print(f"[!] Chua tim thay {a.port}. He thong se tu dong ket noi khi cam cap vao...")

    plt = None
    if not a.noplot:
        import matplotlib.pyplot as plt
        plt.ion()
        fig, (ax, ax_bar) = plt.subplots(2, 1, figsize=(11, 7), gridspec_kw={'height_ratios': [3, 1]})
        freqs = [k * fsx for k in range(NBIN)]
        line, = ax.plot(freqs, [0]*NBIN, color='#1f77b4', lw=1.8, label='Envelope Spectrum')
        
        # Ve cac vach chi thi dong hoc
        bpfo_hz, bpfi_hz, bsf_hz, ftf_hz = priors_hz
        ax.axvline(a.rpm/60.0, color='gray', linestyle=':', label=f'1X (fr={a.rpm/60.0:.1f}Hz)')
        ax.axvline(bpfo_hz, color='orange', linestyle='--', label=f'BPFO ({bpfo_hz:.1f}Hz)')
        ax.axvline(bpfi_hz, color='red', linestyle='--', label=f'BPFI ({bpfi_hz:.1f}Hz)')
        ax.axvline(bsf_hz, color='purple', linestyle='--', label=f'BSF ({bsf_hz:.1f}Hz)')
        
        ax.set_xlabel('Tan so (Hz)', fontsize=11)
        ax.set_ylabel('Bien do (LSB)', fontsize=11)
        ax.set_xlim(0, a.xlim)
        ax.set_ylim(0, 500)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='upper right', fontsize=9)

        # Thanh trang thai AI
        bar_colors = ['#2ca02c', '#d62728', '#ff7f0e', '#9467bd']
        bars = ax_bar.bar(range(4), [0, 0, 0, 0], color=bar_colors)
        ax_bar.set_xticks(range(4))
        ax_bar.set_xticklabels(['Normal', 'Inner Race (BPFI)', 'Outer Race (BPFO)', 'Ball (BSF)'], fontsize=10, fontweight='bold')
        ax_bar.set_ylabel('Logit INT8')
        ax_bar.set_ylim(-128, 127)
        ax_bar.grid(True, axis='y', linestyle=':', alpha=0.6)

        fig.suptitle('VibraDistill-Edge: Real-time AI Motor Health Diagnostics', fontsize=13, fontweight='bold')
        fig.tight_layout()
        plt.show(block=False)
        plt.pause(0.05)

    w = csv.writer(open(a.csv, 'w', newline='')) if a.csv else None
    buf = bytearray()
    t0 = time.time()
    last_diag = time.time()
    last_draw = time.time()
    total_bytes_rx = 0
    total_frames = 0
    warned_disconnect = False

    print("--- San sang! Dang nhan du lieu tu FPGA va ve pho... ---")

    while True:
        # Xu ly tu dong ket noi lai (Auto-Reconnect) neu CP2102 bi rut ra
        if ser is None or not ser.is_open:
            if not warned_disconnect:
                print(f"\n[CANH BAO] Mat ket noi voi {a.port}! (Co the do ban vua rut cap).")
                print(f"[AUTO-RECONNECT] Dang cho cam lai cap vao cong USB...")
                warned_disconnect = True
            time.sleep(0.5)
            ser = open_serial_port(a.port, a.baud)
            if ser and ser.is_open:
                print(f"[THANH CONG] Da ket noi lai voi {a.port}! Tiep tuc thu thap du lieu...")
                warned_disconnect = False
                buf.clear()
            if plt:
                fig.canvas.draw_idle()
                plt.pause(0.05)
            continue

        chunk = b''
        try:
            chunk = ser.read(1024)
        except Exception:
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            continue

        if chunk:
            buf += chunk
            total_bytes_rx += len(chunk)

        frames, used, bad = parse_frames(bytes(buf))
        buf = buf[used:]

        if bad:
            print(f"[Canh bao] {bad} khung loi checksum (do baudrate lech hoac nhieu duong truyen)")

        for seq, bins in frames:
            total_frames += 1
            k, f, v = peak(bins, a.fs)
            
            ai_res = None
            if clf:
                if getattr(clf, 'mode', '') == 'hil_12ch' or a.fs > 5000:
                    # Che do HIL 12 kHz: Chuan hoa Max toan bo 257 bin bit-true voi FPGA spec_normalizer.v
                    max_b = max(max(bins), 1)
                    spec_norm = np.clip(((np.array(bins, dtype=np.int32) * 127 + (max_b // 2)) // max_b), 0, 127).astype(np.int8)
                    ai_res = clf.predict(spec_norm, prior_int8)
                else:
                    max_b = max(max(bins[2:]), 1)
                    if max_b < 100:
                        ai_res = {'pred_class': 0, 'class_name': 'NORMAL (Baseline / Idle)', 'vacuity': 0.0, 'logits': [60, -60, -60, -60]}
                    else:
                        spec_norm = np.clip(np.array(bins) / max_b * 127.0, -128, 127).astype(np.int8)
                        ai_res = clf.predict(spec_norm, prior_int8)

            pred_txt = ai_res['class_name'] if ai_res else "N/A"
            vac_txt = f"Vacuity={ai_res['vacuity']:.3f}" if ai_res else ""
            print(f"[{time.time()-t0:7.1f}s] seq={seq:3d} | Dinh: {f:6.1f} Hz (Bin {k:2d}, A={v:5d}) | AI: {pred_txt} {vac_txt}")

            if w:
                w.writerow([seq] + bins + ([ai_res['pred_class']] if ai_res else []))

            if plt:
                line.set_ydata(bins[:])
                peak_val = max(bins[2:]) if len(bins) > 2 else 10
                ax.set_ylim(0, max(peak_val * 1.25, 50.0))
                ax.set_title(f'Khung #{seq} | Dinh: {f:.1f} Hz (Bin {k}) | Chan doan AI: {pred_txt}', fontsize=11, fontweight='bold',
                             color='green' if (ai_res and ai_res['pred_class'] == 0) else 'red')

                if ai_res:
                    for bar, logit in zip(bars, ai_res['logits']):
                        bar.set_height(logit)

        # Cap nhat GUI voi tan so toi da 30 FPS de tranh nghen luong UART
        if plt and (time.time() - last_draw > 0.033):
            fig.canvas.draw_idle()
            plt.pause(0.001)
            last_draw = time.time()

        if time.time() - last_diag > 2.0:
            if total_frames == 0:
                print(f"[Dang cho FPGA...] Da nhan {total_bytes_rx} bytes tu {a.port}...")
            last_diag = time.time()

        # Quan ly bo dem an toan: Dong bo theo header 0xAA 0x55 chu khong cat tuy tien
        if len(buf) > 8192:
            last_sync = buf.rfind(b'\xaa\x55')
            if last_sync != -1:
                buf = buf[last_sync:]
            else:
                buf.clear()

if __name__ == '__main__':
    main()
