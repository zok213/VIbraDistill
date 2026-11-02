# Multi-Profile Block SRAM Architecture (`roms/profiles/`)

> **Location:** `embedded/fpga_gowin/roms/profiles/`  
> **Target:** Gowin GW2A-LV18 12-Way Systolic Core (`npu_12way_core.v`)  
> **Profile Switching:** Hardware register `[2:0] profile_select` selects between profiles without bitstream reload.

---

## 1. Profiles Inventory

| Folder Name | Profile ID | Machinery Target | Sampling Rate | Kinematics ($N_b$) | Primary Metric |
| :--- | :---: | :--- | :---: | :---: | :---: |
| [`prf01_cwru_motor_9ball/`](prf01_cwru_motor_9ball/README.md) | `PRF01` | CWRU Electric Motor (SKF 6205) | 12,000 Hz | 9 balls | **98.71% Acc** |
| [`prf02_mfpt_heavy_16ball/`](prf02_mfpt_heavy_16ball/README.md) | `PRF02` | MFPT Heavy Machinery (Nice 1012) | 12,000 Hz | 16 balls | **88.25% Acc** |
| [`prf03_pronostia_rul/`](prf03_pronostia_rul/README.md) | `PRF03` | PRONOSTIA Run-to-Failure Degradation | 12,000 Hz | 13 balls | **Coverage $\ge 90\%$** |
| [`prf04_gearbox_drivetrain/`](prf04_gearbox_drivetrain/README.md) | `PRF04` | SEU & PHM2009 Planetary Gearbox | 12,000 Hz | Gear mesh | **$u \ge 0.85$ (SIL-2)** |
| [`adxl345_native/`](adxl345_native/README.md) | `PRF_ADXL` | ADXL345 Physical Accelerometer SPI | 3,200 Hz | 9 balls | **96.38% Acc** |

---

## 2. Bank Layout Inside Each Profile

Each profile directory contains:
- `npu_weights_bank0.hex` & `.mi`: BSRAM Bank 0 (Channel 0 lower byte, Channel 1 upper byte, 257 words)
- `npu_weights_bank1.hex` & `.mi`: BSRAM Bank 1 (Channel 2 lower byte, Channel 3 upper byte, 257 words)
- `npu_weights_bank2.hex` & `.mi`: BSRAM Bank 2 (Channel 4 lower byte, Channel 5 upper byte, 257 words)
- `npu_weights_bank3.hex` & `.mi`: BSRAM Bank 3 (Channel 6 lower byte, Channel 7 upper byte, 257 words)
- `npu_weights_bank4.hex` & `.mi`: BSRAM Bank 4 (Channel 8 lower byte, Channel 9 upper byte, 257 words)
- `npu_weights_bank5.hex` & `.mi`: BSRAM Bank 5 (Channel 10 lower byte, Channel 11 upper byte, 257 words)
- `profile.json`: Full machine metadata, kinematics, biases, and validated metrics.
