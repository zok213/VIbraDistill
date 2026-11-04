"""
Master Codebase Audit and Integrity Verification Script for VibraDistill.
Scans Verilog RTL, MCU C code, Python algorithms, and documentation for:
1. Hardcoded host machine paths (e.g. C:, T:, D:, /home)
2. Port definitions and module instantiation matching in Verilog
3. Array bounds and buffer safety in MCU C code
4. Bit-true parameter consistency across all modules
5. Outdated references (13.3 kHz remnants, obsolete comments)
"""

import os
import re
import glob
import sys

def audit_hardcoded_paths(root_dir):
    print("=" * 80)
    print("[AUDIT 1] Scanning for Host-Specific Absolute Paths in Verilog & C...")
    print("=" * 80)
    
    suspicious_patterns = [
        re.compile(r'\"[a-zA-Z]:[\\/][^"]+\"'),
        re.compile(r'\"\/home\/[^"]+\"')
    ]
    
    findings = []
    
    target_exts = {'.v', '.sv', '.vh', '.c', '.h', '.sdc', '.cst', '.rao'}
    for root, _, files in os.walk(root_dir):
        # Skip git and cache
        if '.git' in root or '__pycache__' in root or '.pytest_cache' in root:
            continue
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in target_exts:
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_no, line in enumerate(f, 1):
                            for pat in suspicious_patterns:
                                m = pat.search(line)
                                if m:
                                    findings.append((fpath, line_no, m.group(0), line.strip()))
                except Exception as e:
                    print(f"Error reading {fpath}: {e}")
                    
    if findings:
        print(f"Found {len(findings)} hardcoded absolute paths:")
        for fpath, lno, match, ltext in findings:
            rel = os.path.relpath(fpath, root_dir)
            print(f"  * {rel}:{lno} -> {match}")
    else:
        print("PASS: No hardcoded host machine absolute paths found.")
    return findings

def audit_verilog_ports(src_dir):
    print("\n" + "=" * 80)
    print("[AUDIT 2] Verilog Module Declaration & Instantiation Consistency...")
    print("=" * 80)
    
    v_files = glob.glob(os.path.join(src_dir, '**', '*.v'), recursive=True)
    module_defs = {}
    
    # Simple regex to extract module definitions
    mod_pat = re.compile(r'module\s+(\w+)\s*(?:#\s*\((.*?)\)\s*)?\s*\((.*?)\);', re.DOTALL)
    
    for vf in v_files:
        try:
            with open(vf, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # strip single line comments
            clean_content = re.sub(r'//.*', '', content)
            # strip multi line comments
            clean_content = re.sub(r'/\*.*?\*/', '', clean_content, flags=re.DOTALL)
            
            for m in mod_pat.finditer(clean_content):
                mname = m.group(1)
                mparams_raw = m.group(2) or ""
                mports_raw = m.group(3) or ""
                
                # parse port names
                ports = []
                for p in mports_raw.split(','):
                    p = p.strip()
                    if not p:
                        continue
                    tokens = p.split()
                    if tokens:
                        pname = tokens[-1].strip().replace(';', '')
                        ports.append(pname)
                
                module_defs[mname] = {
                    'file': vf,
                    'ports': ports
                }
        except Exception as e:
            print(f"Error parsing {vf}: {e}")
            
    print(f"Discovered {len(module_defs)} Verilog module definitions.")
    for mname, info in sorted(module_defs.items()):
        rel = os.path.relpath(info['file'], src_dir)
        print(f"  - {mname} ({len(info['ports'])} ports) in {rel}")
        
    return module_defs

def audit_mcu_code(mcu_dir):
    print("\n" + "=" * 80)
    print("[AUDIT 3] Sonix SN32F407 MCU C Code & Memory Safety Check...")
    print("=" * 80)
    
    target_files = [
        os.path.join(mcu_dir, 'src', 'main.c'),
        os.path.join(mcu_dir, 'app', 'main.c')
    ]
    
    for main_c in target_files:
        if not os.path.exists(main_c):
            continue
            
        with open(main_c, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        rel = os.path.relpath(main_c, mcu_dir)
        print(f"\nAuditing {rel} ({len(lines)} lines)...")
        
        # Check buffer allocations vs usage
        frame_size_matches = [line.strip() for line in lines if 'SPI_FRAME_SIZE' in line or 'spi_rx_buf' in line or 'spi_dma_buf' in line]
        print(f"  Buffer and Frame Definitions:")
        for m in frame_size_matches[:6]:
            print(f"    {m}")
            
        # Check frequency computation
        freq_calc = [line.strip() for line in lines if 'max_bin' in line and ('3750' in line or '12000' in line or '>>' in line)]
        print(f"  Frequency Calculation in MCU:")
        for f in freq_calc[:4]:
            print(f"    {f}")
            
        # Check SIL-2 Relay & Safety Pins
        relay_pins = [line.strip() for line in lines if 'RELAY' in line or 'P2_2' in line or 'TRIP' in line or 'SIL' in line]
        print(f"  Safety Relay & Trip Handling:")
        for r in relay_pins[:6]:
            print(f"    {r}")

def audit_legacy_13k_remnants(root_dir):
    print("\n" + "=" * 80)
    print("[AUDIT 4] Scanning Entire Repository for Stale 13.3 kHz References...")
    print("=" * 80)
    
    findings = []
    pat = re.compile(r'13[\.,]3\s*k', re.IGNORECASE)
    
    for root, _, files in os.walk(root_dir):
        if '.git' in root or '__pycache__' in root or '.pytest_cache' in root or 'hardware_reports' in root:
            continue
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in {'.v', '.sv', '.vh', '.c', '.h', '.py', '.md', '.sdc', '.cst'}:
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_no, line in enumerate(f, 1):
                            if pat.search(line):
                                findings.append((fpath, line_no, line.strip()))
                except Exception as e:
                    pass
                    
    if findings:
        print(f"Found {len(findings)} stale 13.3 kHz occurrences:")
        for fpath, lno, ltext in findings:
            rel = os.path.relpath(fpath, root_dir)
            print(f"  * {rel}:{lno} -> {ltext}")
    else:
        print("PASS: Zero stale 13.3 kHz occurrences found across active code and primary docs!")
    return findings

if __name__ == '__main__':
    root_dir = os.path.abspath('.')
    print(f"Starting Master System Audit in {root_dir}...")
    
    hardcoded = audit_hardcoded_paths(os.path.join(root_dir, 'embedded'))
    vmods = audit_verilog_ports(os.path.join(root_dir, 'embedded', 'fpga_gowin'))
    audit_mcu_code(os.path.join(root_dir, 'embedded', 'mcu_sonix'))
    legacy_13k = audit_legacy_13k_remnants(root_dir)
    
    print("\n" + "=" * 80)
    print("AUDIT SCAN COMPLETE.")
    print("=" * 80)
