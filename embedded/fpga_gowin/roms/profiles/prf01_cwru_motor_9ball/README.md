# Profile PRF01: CWRU Motor Bearing (SKF 6205, 9 Balls)

> **Hardware Target:** Gowin Tang Primer 20K (GW2A-LV18)  
> **Source Model:** 12-Channel Systolic Spectral Matcher (HIL Mode)  
> **Accuracy:** **98.71% HIL Validation** | **98.05% on 15 Raw .mat Files (2,767 Windows, Zero Cache)**  
> **Macro F1:** **97.34%** | **Latency:** **2.62 µs** (262 cycles @ 100 MHz)

---

## 1. Machine Kinematics & Specifications
* **Bearing Model:** SKF 6205-2RS deep-groove ball bearing
* **Number of Rolling Elements ($N_b$):** 9 balls
* **Ball Diameter ($d$):** 7.94 mm
* **Pitch Diameter ($D$):** 39.04 mm
* **Nominal Speed:** 1797 RPM ($f_r = 29.95\text{ Hz}$, Load 0 HP)
* **Sampling Rate ($F_s$):** 12,000 Hz ($F_\text{Nyquist} = 6,000\text{ Hz}$)
* **Characteristic Fault Frequencies:**
  * BPFO (Outer Race): $107.5\text{ Hz}$ (Bin 5)
  * BPFI (Inner Race): $162.2\text{ Hz}$ (Bin 7)
  * BSF (Ball Spin): $141.2\text{ Hz}$ (Bin 6)
  * FTF (Cage): $11.9\text{ Hz}$

---

## 2. Hardware Allocation & Memory Mapping
* **Banks:** 6 BSRAMs (`npu_weights_bank0..5.hex`, 257 16-bit words each)
* **Word Encoding:** `{Channel 2b+1 [15:8], Channel 2b [7:0]}` (Signed INT8 $[-128, 127]$)
* **Channel Sub-Band Mapping:**
  * Class 0 (Normal): Channels 0 (0-2000 Hz), 1 (2000-4000 Hz), 2 (4000-6000 Hz)
  * Class 1 (Inner):  Channels 3 (0-2000 Hz), 4 (2000-4000 Hz), 5 (4000-6000 Hz)
  * Class 2 (Outer):  Channels 6 (0-2000 Hz), 7 (2000-4000 Hz), 8 (4000-6000 Hz)
  * Class 3 (Ball):   Channels 9 (0-2000 Hz), 10 (2000-4000 Hz), 11 (4000-6000 Hz)
* **Class Biases (INT32):** `[-5, -3, +14, -6]`
