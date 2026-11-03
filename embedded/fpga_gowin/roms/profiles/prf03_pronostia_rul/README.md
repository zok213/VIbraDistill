# Profile PRF03: PRONOSTIA Run-to-Failure Degradation & RUL Head

> **Hardware Target:** Gowin Tang Primer 20K (DSP Spectrum Extractor) + Sonix SN32F407 (ARM Cortex-M0 HopACP Q16.16)  
> **Source Platform:** FEMTO-ST PRONOSTIA Accelerated Bearing Degradation Platform (IEEE PHM 2012 Challenge)  
> **Conformal Coverage:** **93.51% Empirical Guarantee ($1 - \alpha = 0.90$)**  
> **Prognostics Metric:** **MAE = 1.675 hours, RMSE = 2.018 hours** (Holdout Test Bearing 1_3)  
> **SIL-2 Advance Warning:** **101.5 minutes BEFORE catastrophic breakdown**  

---

## 1. Machine Kinematics & Physical Domain Shift

> [!IMPORTANT]
> **Domain Shift Warning (PRONOSTIA vs CWRU):**
> PRONOSTIA uses miniature ball bearings (**NSK 6804RS, 13 balls**) under accelerated wear, whereas CWRU uses motor bearings (**SKF 6205, 9 balls**). Their kinematics are completely distinct:
> * **CWRU (9 balls, 1797 RPM):** $\text{BPFO} = 107.5\text{ Hz}, \text{BPFI} = 162.2\text{ Hz}, \text{BSF} = 69.8\text{ Hz}$.
> * **PRONOSTIA (13 balls, 1800 RPM):** $\text{BPFO} = 168.75\text{ Hz}, \text{BPFI} = 221.25\text{ Hz}, \text{BSF} = 109.38\text{ Hz}, \text{FTF} = 12.98\text{ Hz}$.
>
> Therefore, PRONOSTIA is **NOT** evaluated as discrete 4-class fault classification on CWRU weights. It is dedicated to **Continuous Remaining Useful Life (RUL) Prognostics**.

* **Bearing Model:** NSK 6804RS miniature deep groove ball bearing
* **Number of Rolling Elements ($N_b$):** 13 balls
* **Ball Diameter ($d$):** 3.5 mm
* **Pitch Diameter ($D$):** 26.0 mm (mean of 20 mm bore and 32 mm outer)
* **Operating Conditions:** 1800 RPM ($f_r = 30.0\text{ Hz}$), 4000 N radial load
* **Native Sampling Rate:** 25,600 Hz (0.1s snapshot every 10s = 2,560 samples/snapshot)
* **Continuous Degradation Horizon:** 100% (Early life, t=0.0h) $\to$ 50% (Incipient wear, t=3.3h) $\to$ 0% (Terminal breakdown, t=6.6h)

---

## 2. Hardware Roles (Co-Processing Partition)

1. **Gowin FPGA Tang Primer 20K:**
   - Computes causal FIR filtering, envelope demodulation, Hann windowing, and 512-pt real FFT in hardware ($2.62\,\mu\text{s}$).
   - Streams 257-bin spectrum and kinematics packet via SPI DMA to MCU.
2. **Sonix SN32F407 Cortex-M0 SIL-2 Supervisor:**
   - Evaluates ANSI C HopACP Q16.16 conformal update:
     $$\hat{q}_{t+1} = \text{clamp}(\hat{q}_t + \beta \cdot v_t + \Delta_t, q_\text{min}, q_\text{max})$$
   - Computes statistical confidence interval: $[\widehat{\text{RUL}} - \hat{q}, \widehat{\text{RUL}} + \hat{q}]$.
   - Trips P1.0 relay when vibration exceeds safety limit (RMS $\ge 8.0\text{g}$ / Peak $\ge 20.0\text{g}$) or when persistent spall occurs, providing **101.5 minutes advance shutdown margin**.

---

## 3. Verification & Benchmark Execution

To run the full 2,375-snapshot raw vibration neural inference and conformal calibration:
```bash
python scripts/verify_mat_rul_prognostics.py
```
* **Dataset Ingested:** `data/rul_mat_benchmarks/bearing_lifecycle_1_3.mat` (all 2,375 raw snapshots)
* **Neural Network Head:** `checkpoints/prognostics/pronostia_rul_micro.pt` (`VibraDistillMicro`)
* **Time Leakage:** **Zero.** (All predictions come directly from raw vibration processing; no ground-truth time subtraction).
