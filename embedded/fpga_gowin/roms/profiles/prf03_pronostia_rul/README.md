# Profile PRF03: PRONOSTIA Run-to-Failure Degradation & RUL Head

> **Hardware Target:** Gowin Tang Primer 20K + Sonix SN32F407 (ARM Cortex-M0 HopACP Q16.16)  
> **Source Platform:** FEMTO-ST PRONOSTIA Accelerated Bearing Degradation Platform  
> **Conformal Coverage:** **90.22% Target Guarantee ($1 - \alpha = 0.90$)**  
> **Latency:** **2.62 µs (FPGA NPU)** + **18.2 µs (< 20 cycles Cortex-M0 HopACP Q16.16)**

---

## 1. Machine Kinematics & Specifications
* **Bearing Model:** Miniature deep groove ball bearing (FEMTO-ST platform)
* **Number of Rolling Elements ($N_b$):** 13 balls
* **Operating Conditions:** 1800 RPM ($f_r = 30.0\text{ Hz}$), 4000 N radial load
* **Native Sampling Rate:** 25,600 Hz
* **Unified Rate for NPU:** 12,000 Hz (Polyphase Sinc)
* **Continuous Degradation Horizon:** 100% (Early life) $\to$ 50% (Incipient wear) $\to$ 8% (Terminal spalling)

---

## 2. Hardware Roles (Co-Processing Partition)
1. **Gowin FPGA Tang Primer 20K:**
   - Computes envelope spectrum and 12-channel dot product ($2.62\,\mu\text{s}$).
   - Streams 524-byte packet via SPI DMA to MCU.
2. **Sonix SN32F407 Cortex-M0 SIL-2 Supervisor:**
   - Evaluates ANSI C HopACP Q16.16 conformal update:
     $$\hat{q}_{t+1} = \text{clamp}(\hat{q}_t + \beta \cdot v_t + \Delta_t, q_\text{min}, q_\text{max})$$
   - Computes statistical confidence interval: $[\widehat{\text{RUL}} - \hat{q}, \widehat{\text{RUL}} + \hat{q}]$.
   - Trips P1.0 relay when $\text{RUL} < 10.0\text{ hours}$ (or $< 10\%$).
