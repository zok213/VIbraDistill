# Gowin FPGA ADXL345 Native Synthesis Weights (`roms/adxl345/`)

> **Target Silicon:** Gowin GW2A-LV18PG256C8/I7 (Tang Primer 20K)  
> **Sensor Interface:** Analog Devices ADXL345 3-Axis Digital MEMS Accelerometer (SPI 5 MHz, 3.2 kHz ODR, $\pm 16\text{g}$)  
> **Physical Validation Accuracy:** **96.38%** on physical MEMS testbed vibration  
> **Memory Allocation:** 6 BSRAM Banks (7,880 INT8 Bytes, 13.0% of on-chip BSRAM)

---

## 1. Directory File Inventory

| File Pattern | Format | Function |
| :--- | :--- | :--- |
| `npu_weights_bank[0-5].hex` | ASCII Hex | Bit-true two's complement INT8 weight banks for ADXL345 systolic matcher |
| `npu_weights_bank[0-5].mi` | Gowin MI | Gowin EDA memory initialization files for block RAM IP core instantiation |
| `bsram_memory_map.txt` | Text Map | Byte-level offset and layer shape mapping for all 6 BSRAM banks |
| `tier1_spectral_weights_map.txt` | Text Map | ADXL345 channel allocations, passband boundaries, and INT32 biases |

---

## 2. MEMS-Specific Domain Adaptation

Unlike laboratory piezoresistive sensors (PCB 352C33, 100 mV/g, bandwidth > 10 kHz), industrial MEMS accelerometers have:
1. **Bandwidth Limits:** $f_\text{sample} \le 3,200\text{ Hz}$ (Nyquist $1,600\text{ Hz}$).
2. **Noise Floor:** $\approx 150\text{ }\mu\text{g}/\sqrt{\text{Hz}}$ with low-frequency 1/f flicker noise and DC gravity offset.
3. **Quantization:** 13-bit resolution at $\pm 16\text{g}$ ($3.9\text{ mg/LSB}$).

### Architectural Compensations in this Weight Set
- **DC Nulling Pre-FIR Filter:** High-pass filter coefficients embedded in Stage 1 eliminate the static $1\text{g}$ gravitational vector.
- **Order-Domain Scaling:** Frequencies mapped to lower order bins ($0 - 1,600\text{ Hz}$) capturing $1\times, 2\times, 3\times$ shaft orders and fundamental bearing pass rates.
- **Robustness Training:** Weights trained with additive Brownian low-frequency noise and temperature drift augmentation, achieving **96.38%** physical validation accuracy.

---

## 3. Verification

To verify bit-true execution against ADXL345 SPI streaming stimuli:
```powershell
python scripts/verify_multi_dataset_fpga.py
```
