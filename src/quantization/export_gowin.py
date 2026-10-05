"""
Gowin Primer 20K (GW2A-LV18) BSRAM Memory Initialization (.mi & .hex) Exporter.
Packs INT8 weights into 6 dual-port BSRAM banks for the 12-way MAC NPU systolic core.
Produces both Gowin EDA (.mi) and Standard Verilog ($readmemh .hex) formats for co-simulation.
"""

import os
from typing import Dict, Any
import numpy as np

def write_gowin_mi_and_hex(base_path: str, data_bytes: np.ndarray, word_width: int = 16):
    """
    Writes raw bytes to both Gowin EDA .mi and Verilog simulation .hex formats.
    """
    os.makedirs(os.path.dirname(os.path.abspath(base_path)), exist_ok=True)
    raw = data_bytes.astype(np.uint8).flatten()
    bytes_per_word = word_width // 8
    
    # Pad to word boundary
    remainder = len(raw) % bytes_per_word
    if remainder != 0:
        pad_len = bytes_per_word - remainder
        raw = np.pad(raw, (0, pad_len), mode='constant', constant_values=0)
        
    num_words = len(raw) // bytes_per_word
    
    hex_lines = []
    for i in range(num_words):
        word_bytes = raw[i * bytes_per_word : (i + 1) * bytes_per_word]
        # Little-endian word formatting
        hex_val = "".join([f"{b:02X}" for b in reversed(word_bytes)])
        hex_lines.append(hex_val)
        
    # 1. Gowin EDA format (.mi)
    mi_path = base_path if base_path.endswith('.mi') else base_path + '.mi'
    with open(mi_path, 'w') as f:
        f.write("#File_Addr_First=0\n")
        f.write(f"#File_Addr_Last={num_words - 1}\n")
        for line in hex_lines:
            f.write(f"{line}\n")
            
    # 2. Standard Verilog $readmemh format (.hex)
    hex_path = base_path[:-3] + '.hex' if base_path.endswith('.mi') else base_path + '.hex'
    with open(hex_path, 'w') as f:
        for line in hex_lines:
            f.write(f"{line}\n")

def export_gowin_bsram_mi(quantized_package: Dict[str, Any], output_dir: str):
    """
    Exports weights across 6 BSRAM banks to feed the 12-way MAC systolic core.
    Produces both .mi and .hex files for hardware synthesis and testbench co-simulation.
    """
    os.makedirs(output_dir, exist_ok=True)
    layers = quantized_package['layers']
    
    all_weights = []
    layer_map = []
    current_addr = 0
    
    for layer_name, data in layers.items():
        w_flat = data['weight_int8'].flatten()
        all_weights.append(w_flat)
        layer_map.append(f"Layer: {layer_name:30s} | Shape: {str(data['shape']):18s} | Offset: {current_addr:6d} | Length: {len(w_flat):6d}")
        current_addr += len(w_flat)
        
    flat_all_weights = np.concatenate(all_weights)
    
    # Partition weights across 6 BSRAM banks (for 12 MACs, dual-port BSRAM: 6 banks x 2 ports = 12 feeds)
    num_banks = 6
    bank_size = int(np.ceil(len(flat_all_weights) / num_banks))
    
    for bank_idx in range(num_banks):
        start = bank_idx * bank_size
        end = min(len(flat_all_weights), (bank_idx + 1) * bank_size)
        bank_data = flat_all_weights[start:end]
        base_path = os.path.join(output_dir, f"npu_weights_bank{bank_idx}.mi")
        write_gowin_mi_and_hex(base_path, bank_data, word_width=16)
        
    # Write memory map document
    map_path = os.path.join(output_dir, "bsram_memory_map.txt")
    with open(map_path, 'w') as f:
        f.write("GOWIN PRIMER 20K NPU BSRAM MEMORY ALLOCATION MAP\n")
        f.write("==================================================\n")
        f.write(f"Total INT8 Parameters: {len(flat_all_weights)} Bytes\n")
        f.write(f"Memory Architecture:  6 Banks x 2 Ports (16-bit) -> 12 Parallel MAC Feeds\n")
        f.write(f"Total BSRAM Usage:     6 / 46 BSRAM Blocks (13.0% Utilization)\n\n")
        f.write("\n".join(layer_map))
        f.write("\n")
