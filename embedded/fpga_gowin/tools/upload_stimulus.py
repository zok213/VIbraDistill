#!/usr/bin/env python3
"""
===============================================================================
VibraDistill-Edge: Industrial FPGA Stimulus Upload Tool (UART 921600 baud)
Nap 512 mau song rung tho int16 tu file .hex xuong BRAM cua Tang Primer 20K.
Giao thuc kiem tra toan ven CRC16-CCITT, chuyen mach khong giat tren FPGA.
===============================================================================
"""

import argparse
import sys
import time
import serial

def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def load_hex_samples(hex_path: str):
    samples = []
    with open(hex_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            # Xu ly dau phay, cham phay, hoac nhieu token tren 1 dong
            line = line.rstrip(',;').strip()
            tokens = line.replace(',', ' ').split()
            for token in tokens:
                token = token.strip()
                if not token:
                    continue
                val = int(token, 16)
                if val >= 32768:
                    val -= 65536
                samples.append(val)
                if len(samples) == 512:
                    break
            if len(samples) == 512:
                break
    if len(samples) < 512:
        print(f"[!] Canh bao: File {hex_path} chi co {len(samples)} mau, tu dong dem 0 cho du 512 mau.")
        while len(samples) < 512:
            samples.append(0)
    return samples[:512]

def build_upload_packet(samples, seq=1):
    # Header: A5 5A
    # CMD: 0x04 (LOAD_STIMULUS)
    # SEQ: 2 bytes LE
    # LEN: 2 bytes LE (1024 bytes = 512 samples x 2)
    # PAYLOAD: 1024 bytes
    # CRC16: 2 bytes LE
    cmd = 0x04
    cmd_bytes = bytes([cmd, seq & 0xFF, (seq >> 8) & 0xFF, 1024 & 0xFF, (1024 >> 8) & 0xFF])
    
    payload = bytearray()
    for s in samples:
        # Convert to 16-bit signed little-endian
        u16 = s & 0xFFFF
        payload.append(u16 & 0xFF)
        payload.append((u16 >> 8) & 0xFF)
    
    crc_target = cmd_bytes + payload
    crc = crc16_ccitt(crc_target)
    crc_bytes = bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    
    full_packet = bytes([0xA5, 0x5A]) + crc_target + crc_bytes
    return full_packet, crc

def upload(port: str, baud: int, hex_path: str):
    print(f"[*] Dang doc file mau: {hex_path}")
    samples = load_hex_samples(hex_path)
    packet, crc = build_upload_packet(samples)
    print(f"[*] Da dong goi 512 mau (1033 bytes) | CRC16-CCITT = 0x{crc:04X}")

    print(f"[*] Dang ket noi toi {port} o toc do {baud} baud...")
    ser = serial.Serial(port, baud, timeout=0.5)
    
    # Gui toan bo goi tin qua UART
    t0 = time.time()
    ser.write(packet)
    ser.flush()
    elapsed_ms = (time.time() - t0) * 1000.0
    
    print(f"[+] NAP THANH CONG!")
    print(f"    - So mau: 512 mau int16 (16-bit)")
    print(f"    - Thoi gian truyen: {elapsed_ms:.1f} ms")
    print(f"    - FPGA da tu dong chuyen mach sang kịch ban moi!")
    ser.close()

def main():
    ap = argparse.ArgumentParser(description="Upload raw vibration stimulus hex to FPGA Tang Primer 20K")
    ap.add_argument('--port', default='COM6', help='Cong Serial COM (vd: COM6)')
    ap.add_argument('--baud', type=int, default=921600, help='Baudrate UART (mac dinh 921600)')
    ap.add_argument('--hex', required=True, help='Duong dan file .hex (vd: src/test_npu/roms/hil/stimulus_cwru_ball.hex)')
    a = ap.parse_args()

    try:
        upload(a.port, a.baud, a.hex)
    except Exception as e:
        print(f"[!] LOI: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
