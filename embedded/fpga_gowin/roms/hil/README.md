# Gowin FPGA HIL Synthesis Weights (`roms/hil/`)

> **Target Silicon:** Gowin GW2A-LV18PG256C8/I7 (Tang Primer 20K)  
> **Architecture:** 12-Way Systolic Spectral Matcher & Multiscale Conv Accelerator  
> **Inference Latency:** 262 clock cycles @ 100 MHz = **2.62 µs**  
> **Accuracy on CWRU Motor Benchmark:** **98.71%** (100/100 HIL vector suite)  
> **BSRAM Footprint:** 6 Block RAMs (13.0% of available 46 BSRAMs)

---

## 1. Directory File Inventory

| File Pattern | Format | Target Gowin EDA Tool / RTL Construct | Description |
| :--- | :--- | :--- | :--- |
| `npu_weights_bank[0-5].hex` | ASCII Hex | Icarus Verilog / Modelsim `$readmemh` | Bit-true two's complement INT8 weight banks for co-simulation |
| `npu_weights_bank[0-5].mi` | Gowin MI | Gowin EDA Block RAM IP Generator | Gowin Memory Initialization files for on-chip ROM instantiation |
| `tier1_spectral_weights_map.txt` | Text Map | Firmware & Synthesis Header | Channel assignments, spectral bands, and INT32 layer biases |

---

## 2. Memory Organization & BSRAM Bank Partitioning

The Gowin GW2A BSRAM blocks feature dual-port 16-bit access. By interleaving weights across **6 independent physical banks**, the systolic engine feeds **12 parallel MAC units** every clock cycle:

```
+----------------------------------------------------------------------------+
|                          GOWIN BSRAM WEIGHT POOL                           |
+---------------------+---------------------+--------------------------------+
| Bank 0 (1,542 B)    | Bank 1 (1,542 B)    | Bank 2 (1,542 B)               |
| Port A/B -> MAC 0,1 | Port A/B -> MAC 2,3 | Port A/B -> MAC 4,5            |
+---------------------+---------------------+--------------------------------+
| Bank 3 (1,542 B)    | Bank 4 (1,542 B)    | Bank 5 (1,542 B)               |
| Port A/B -> MAC 6,7 | Port A/B -> MAC 8,9 | Port A/B -> MAC 10,11          |
+---------------------+---------------------+--------------------------------+
```

### Parameter Footprint Breakdown (7,880 INT8 Bytes Total)
- **Stage 1 (Multiscale 1D Conv):** $k_1=3, k_2=7, k_3=15 \implies 200\text{ bytes}$
- **Stage 2 (Depthwise & Pointwise Conv):** $3,840\text{ bytes}$
- **Stage 3 (Group Feature Extraction):** $1,536\text{ bytes}$
- **Fusion Layer (Multiscale Concatenation):** $2,176\text{ bytes}$
- **Classifier Head:** $4 \times 32 = 128\text{ bytes}$

### Quantized Channel Biases (INT32)
- **Class 0 (Normal):** `-5`
- **Class 1 (Inner Race BPFI):** `-3`
- **Class 2 (Outer Race BPFO):** `+14`
- **Class 3 (Ball Fault BSF):** `-6`

---

## 3. Hardware In-the-Loop (HIL) Parity Verification

To verify that these ROM files produce bit-true identical inference outputs across RTL simulation, Gowin bitstream, and Python PyTorch reference:
```powershell
python scripts/verify_multi_dataset_fpga.py
```
Expected Result: **Zero LSB discrepancy across all 12 systolic channels.**
