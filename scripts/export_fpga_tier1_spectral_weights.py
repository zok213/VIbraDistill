"""
Tier-1 FPGA 12-Way Systolic Spectral Weight Generator and Hex Exporter.

Physics & Mathematical Formulation:
- Hardware Target: Gowin GW2A-LV18 12-Way Systolic MAC Core (npu_12way_core.v).
- Input: 257 envelope spectrum bins from ADXL345 (Fs=3200 Hz, N=512, df=6.25 Hz).
- Quantization: Pure INT8 weights [-128, 127], INT8 activations [0, 127], INT32 bias.
- Architecture: 12 channels = 4 fault classes x 3 sub-bands per class.
    Class 0 (Normal):     Channels 0, 1, 2  (Sub-band 0: 0-400Hz, Band 1: 400-875Hz, Band 2: 875-1600Hz)
    Class 1 (Inner BPFI): Channels 3, 4, 5  (Sub-band 0: 0-400Hz, Band 1: 400-875Hz, Band 2: 875-1600Hz)
    Class 2 (Outer BPFO): Channels 6, 7, 8  (Sub-band 0: 0-400Hz, Band 1: 400-875Hz, Band 2: 875-1600Hz)
    Class 3 (Ball BSF):   Channels 9, 10, 11 (Sub-band 0: 0-400Hz, Band 1: 400-875Hz, Band 2: 875-1600Hz)
- Output: 6 hex files for dual-port BSRAM banks (roms/adxl345/npu_weights_bank0..5.hex).
    Bank b word at address k: {Channel 2b+1 [k] (upper 8-bit), Channel 2b [k] (lower 8-bit)}.
"""

import os
import torch
import numpy as np

def generate_and_export_tier1_weights(output_dir: str = "embedded/fpga_gowin/roms/adxl345"):
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Load cached ADXL345 data
    train_path = "data/cache/cwru_train_adxl345_w512.pt"
    val_path = "data/cache/cwru_val_adxl345_w512.pt"
    
    d_tr = torch.load(train_path, weights_only=False)
    d_va = torch.load(val_path, weights_only=False)
    
    X_scale = 127.0
    X_tr = torch.clamp(torch.round(d_tr['spectra'].squeeze(1) * X_scale), 0, 127)
    y_tr = d_tr['labels']
    X_va = torch.clamp(torch.round(d_va['spectra'].squeeze(1) * X_scale), 0, 127)
    y_va = d_va['labels']
    
    print(f"[Tier-1 Train] Samples: {len(X_tr)} train, {len(X_va)} val. Bins: 257.")
    
    # 2. Train optimal linear spectral discriminator
    torch.manual_seed(42)
    linear = torch.nn.Linear(257, 4, bias=True)
    optimizer = torch.optim.AdamW(linear.parameters(), lr=0.01, weight_decay=1e-3)
    
    for ep in range(300):
        optimizer.zero_grad()
        out = linear(X_tr)
        loss = torch.nn.functional.cross_entropy(out, y_tr)
        loss.backward()
        optimizer.step()
        
    w = linear.weight.data # [4, 257]
    w_scale = 127.0 / torch.max(torch.abs(w))
    w_int8 = torch.clamp(torch.round(w * w_scale), -128, 127).to(torch.int32) # [4, 257]
    b_int32 = torch.round(linear.bias.data * w_scale).to(torch.int32)          # [4]
    
    # 3. Decompose into 12 sub-band channels (3 per class)
    # Band 0: [0..64]   (0 - 400 Hz: Fundamental fault harmonics & fr)
    # Band 1: [65..140] (400 - 875 Hz: 2nd-5th harmonics & modulation sidebands)
    # Band 2: [141..256](875 - 1600 Hz: High-frequency carrier tail)
    w12_int8 = torch.zeros(12, 257, dtype=torch.int32)
    b12_int32 = torch.zeros(12, dtype=torch.int32)
    bands = [(0, 65), (65, 141), (141, 257)]
    
    for c in range(4):
        for s, (b_start, b_end) in enumerate(bands):
            ch_idx = c * 3 + s
            w12_int8[ch_idx, b_start:b_end] = w_int8[c, b_start:b_end]
            if s == 0:
                b12_int32[ch_idx] = b_int32[c]
                
    # 4. Validate bit-true parity
    ch_outs = torch.matmul(X_va.to(torch.int32), w12_int8.t()) + b12_int32
    class_scores = torch.zeros(len(X_va), 4, dtype=torch.int32)
    for c in range(4):
        class_scores[:, c] = ch_outs[:, c*3] + ch_outs[:, c*3 + 1] + ch_outs[:, c*3 + 2]
    preds = torch.argmax(class_scores, dim=1)
    val_acc = (preds == y_va).float().mean().item()
    print(f"[Tier-1 Validation] Bit-True Hardware Emulation Accuracy: {val_acc * 100:.2f}%")
    
    # 5. Pack into 6 dual-port BSRAM banks
    # Bank b word at address k: {Channel 2b+1 [k] (upper byte), Channel 2b [k] (lower byte)}
    w12_np = w12_int8.numpy().astype(np.int8) # [12, 257]
    
    for bank_idx in range(6):
        ch_lower = bank_idx * 2
        ch_upper = bank_idx * 2 + 1
        
        hex_lines = []
        for k in range(257):
            b_low = int(w12_np[ch_lower, k]) & 0xFF
            b_high = int(w12_np[ch_upper, k]) & 0xFF
            word16 = (b_high << 8) | b_low
            hex_lines.append(f"{word16:04X}")
            
        # Write .hex for $readmemh (standard Verilog)
        hex_file = os.path.join(output_dir, f"npu_weights_bank{bank_idx}.hex")
        with open(hex_file, "w") as f:
            for line in hex_lines:
                f.write(f"{line}\n")
                
        # Write .mi for Gowin EDA
        mi_file = os.path.join(output_dir, f"npu_weights_bank{bank_idx}.mi")
        with open(mi_file, "w") as f:
            f.write("#File_Addr_First=0\n")
            f.write(f"#File_Addr_Last={len(hex_lines) - 1}\n")
            for line in hex_lines:
                f.write(f"{line}\n")
                
        print(f"Exported Bank {bank_idx}: {hex_file} and {mi_file} (257 words)")
        
    # 6. Export memory map and bias definition
    map_file = os.path.join(output_dir, "tier1_spectral_weights_map.txt")
    with open(map_file, "w") as f:
        f.write("GOWIN PRIMER 20K TIER-1 SPECTRAL WEIGHT MEMORY MAP\n")
        f.write("===================================================\n")
        f.write("Architecture: 12-Way Systolic Spectral Matcher (< 3us Latency)\n")
        f.write(f"Validation Accuracy: {val_acc * 100:.2f}%\n")
        f.write("Channel Allocation:\n")
        f.write("  - Class 0 (Normal):     Channels 0 (0-400Hz), 1 (400-875Hz), 2 (875-1600Hz)\n")
        f.write("  - Class 1 (Inner BPFI): Channels 3 (0-400Hz), 4 (400-875Hz), 5 (875-1600Hz)\n")
        f.write("  - Class 2 (Outer BPFO): Channels 6 (0-400Hz), 7 (400-875Hz), 8 (875-1600Hz)\n")
        f.write("  - Class 3 (Ball BSF):   Channels 9 (0-400Hz), 10 (400-875Hz), 11 (875-1600Hz)\n")
        f.write("\nChannel Biases (INT32):\n")
        for c in range(4):
            f.write(f"  - Class {c} Bias: {b_int32[c].item()}\n")
    print(f"Exported Documentation: {map_file}")

if __name__ == "__main__":
    generate_and_export_tier1_weights()
