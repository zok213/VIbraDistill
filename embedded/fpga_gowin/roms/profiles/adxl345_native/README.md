# Profile PRF_ADXL: ADXL345 MEMS Accelerometer Native Mode

> **Hardware Target:** Gowin Tang Primer 20K + Analog Devices ADXL345 SPI  
> **Physical Sample Rate:** 3,200 Hz ($F_\text{Nyquist} = 1,600\text{ Hz}$)  
> **Accuracy:** **96.38% Hardware Validation** | **Macro F1:** **95.08%**  
> **Latency:** **2.62 µs** (262 cycles @ 100 MHz)

---

## 1. Physical Sensor Specifications
* **Sensor:** Analog Devices ADXL345 3-Axis Digital MEMS Accelerometer
* **Interface:** 4-Wire SPI (Clock 5.0 MHz)
* **Output Data Rate (ODR):** 3,200 Hz
* **Measurement Range:** $\pm 16\text{ g}$ (13-bit resolution, 3.9 mg/LSB)
* **Frequency Bandwidth:** DC to 1,600 Hz ($F_\text{Nyquist}$)
* **Nyquist Validation:** Mini motor 130 bearing (608ZZ) has $1\times\text{BPFO} = 52.2\text{ Hz}$, $10\times\text{BPFI} = 878\text{ Hz} < 1,600\text{ Hz}$, capturing 100% of harmonics without aliasing.

---

## 2. Hardware Allocation & Memory Mapping
* **Banks:** 6 BSRAMs (`npu_weights_bank0..5.hex`, 257 16-bit words each)
* **Sub-Bands ($F_s = 3200\text{ Hz}$, $\Delta f = 6.25\text{ Hz}$):**
  - Sub-band 0: 0 – 400 Hz (Bins 0 to 64)
  - Sub-band 1: 400 – 875 Hz (Bins 65 to 140)
  - Sub-band 2: 875 – 1600 Hz (Bins 141 to 256)
* **Class Biases (INT32):** `[0, -3, +8, -4]`
