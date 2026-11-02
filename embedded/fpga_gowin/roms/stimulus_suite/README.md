# 28-Vector Industrial Functional Stimulus Suite (`roms/stimulus_suite/`)

> **Location:** `embedded/fpga_gowin/roms/stimulus_suite/`  
> **Testbench Target:** `embedded/fpga_gowin/sim/tb_gowin_top.v`  
> **Format:** 28 `.hex` files, 512 samples per vector, 16-bit signed two's complement, $12\text{ kHz}$ sampling rate.  
> **Companion Catalog:** See [STIMULUS_CATALOG.md](file:///d:/Gitrepo/VIbraDistill/embedded/fpga_gowin/roms/stimulus_suite/STIMULUS_CATALOG.md) for individual vector properties.

---

## 1. Suite Architecture & Coverage Matrix

This 28-vector suite is designed for **exhaustive functional regression** of the Gowin Primer 20K RTL pipeline, exercising corner cases across all operational variables:

```
+-----------------------------------------------------------------------------------+
|                        28-VECTOR REGRESSION TEST MATRIX                           |
+-----------------------------------+-----------------------------------------------+
| Test Subset                       | Vector IDs & Coverage Focus                   |
+-----------------------------------+-----------------------------------------------+
| Load Variation (0, 1, 2, 3 HP)    | 01 - 16: Tests speed shifts (1730 - 1797 RPM) |
| Fault Severity (7, 14, 21 mils)   | 17 - 22: Tests amplitude dynamic range        |
| Phase Shifts (Sliding Windows)    | 23 - 26: Tests non-synchronized initial phase |
| Synthetic Stress & OOD            | 27 - 28: Low SNR (-5 dB) & Out-of-band tones  |
+-----------------------------------+-----------------------------------------------+
```

---

## 2. Expected Safety Relay & SIL-2 Reactions

| Category | Vector IDs | True Class | Expected Gowin NPU Logit Leader | SIL-2 Relay Output |
| :--- | :--- | :--- | :--- | :--- |
| **Normal Healthy** | 01, 05, 09, 13 | Normal | Class 0 (Normal) | **NC Closed** (Healthy run) |
| **Inner Race BPFI** | 02, 06, 10, 14, 17, 20, 23, 24 | Inner | Class 1 (Inner) | **TRIP** ($< 1.0\text{ ms}$) |
| **Outer Race BPFO** | 03, 07, 11, 15, 18, 21, 25, 26 | Outer | Class 2 (Outer) | **TRIP** ($< 1.0\text{ ms}$) |
| **Ball Fault BSF** | 04, 08, 12, 16, 19, 22 | Ball | Class 3 (Ball) | **TRIP** ($< 1.0\text{ ms}$) |
| **OOD Noise & Tones**| 27, 28 | OOD | High Vacuity ($u \ge 0.85$) | **Alarm** (OOD warning) |

---

## 3. Automated Regression Simulation

To execute all 28 vectors against the Icarus Verilog / ModelSim testbench:
```powershell
python scripts/test_hil_fpga.py --suite 28
```
All 28 vectors must achieve bit-true zero discrepancy and 100% safety relay assertion compliance.
