# Profile PRF02: MFPT Heavy Industrial Bearing (Nice 1012, 16 Balls)

> **Hardware Target:** Gowin Tang Primer 20K (GW2A-LV18)  
> **Source Model:** 12-Channel Systolic Spectral Matcher (MFPT Profile)  
> **Accuracy:** **88.25% Direct Spectral Validation** | **Macro F1:** **87.20%**  
> **Latency:** **2.62 µs** (262 cycles @ 100 MHz)

---

## 1. Machine Kinematics & Specifications
* **Bearing Model:** Rexnord / Nice 1012 heavy machinery ball bearing
* **Number of Rolling Elements ($N_b$):** 16 balls
* **Ball Diameter ($d$):** 7.92 mm
* **Pitch Diameter ($D$):** 35.00 mm
* **Operating Speed:** 1500 RPM ($f_r = 25.0\text{ Hz}$, 270 lbs radial load)
* **Native Sampling Rate:** 97,656 Hz / 48,828 Hz
* **Resampled Rate for NPU:** 12,000 Hz (Polyphase Sinc interpolation)
* **Characteristic Fault Frequencies:**
  * BPFO (Outer Race): $155.8\text{ Hz}$
  * BPFI (Inner Race): $244.2\text{ Hz}$
  * BSF (Ball Spin): $135.2\text{ Hz}$
  * Kinematic Warping Factor ($\gamma$): $1.85$ (Aligns 16-ball Nice 1012 to 9-ball SKF 6205)

---

## 2. Hardware Allocation & Memory Mapping
* **Banks:** 6 BSRAMs (`npu_weights_bank0..5.hex`, 257 16-bit words each)
* **Word Encoding:** `{Channel 2b+1 [15:8], Channel 2b [7:0]}` (Signed INT8 $[-128, 127]$)
* **Class Biases (INT32):** `[+9, -21, +29, -27]`
