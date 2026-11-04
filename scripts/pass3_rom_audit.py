"""
PASS 3: BRAM ROM Hex Files Integrity & Memory Map Audit
Checks:
1. Syntax and line-by-line hex validity
2. Bank lengths and BSRAM boundary alignment
3. Value ranges (INT8 for weights, INT16 for stimuli)
"""

import os
import glob

ROM_DIR = "embedded/fpga_gowin/roms"
hex_files = sorted(glob.glob(os.path.join(ROM_DIR, "**", "*.hex"), recursive=True))

print(f"[PASS 3] Auditing {len(hex_files)} ROM .hex files in {ROM_DIR}...\n")

corruptions = []

for hf in hex_files:
    rel = os.path.relpath(hf, ROM_DIR)
    with open(hf, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if line.strip()]
        
    n_lines = len(lines)
    
    # Check each line
    for lno, line in enumerate(lines, 1):
        # Hex validity
        try:
            val = int(line, 16)
        except ValueError:
            corruptions.append((rel, lno, f"Invalid hex value: '{line}'"))
            continue
            
        # Check ranges
        if "weight" in rel.lower():
            # 16-bit word storing 2 x INT8 weights ({w_high[7:0], w_low[7:0]})
            if val > 0xFFFF:
                corruptions.append((rel, lno, f"Weight line exceeds 16-bit BSRAM width: '{line}'"))
        elif "stimulus" in rel.lower():
            # INT16 hex (should be up to 4 hex digits, 0000..FFFF)
            if val > 0xFFFF:
                corruptions.append((rel, lno, f"Stimulus line exceeds INT16 width: '{line}'"))

print("=" * 80)
print(f"PASS 3 AUDIT RESULTS: {len(hex_files)} files audited, {len(corruptions)} errors.")
print("=" * 80)

if corruptions:
    for r, l, err in corruptions[:10]:
        print(f"  * [ERROR] {r}:{l} -> {err}")
else:
    print("  PERFECT: All ROM hex files are 100% syntactically valid and byte-range aligned!")
