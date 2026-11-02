# Out-of-Distribution (OOD) Gearbox Stimulus Suite (`roms/stimuli/ood_gearbox/`)

> **Location:** `embedded/fpga_gowin/roms/stimuli/ood_gearbox/`  
> **Source Datasets:** Southeast University (SEU) Drivetrain Dynamic Simulator & PHM 2009 Gearbox Challenge  
> **Mechanical Target:** Planetary & Spur Gear Drivetrains (Gear Mesh Frequencies $f_m = z \cdot f_r$, tooth chipped, tooth wear)  
> **Signal Format:** 16-Bit Signed Two's Complement Hexadecimal, 512 samples/file, resampled to $12\text{ kHz}$, peak $\le 4,500\text{ LSB}$.

---

## 1. Physical Stimulus Files

| File Name | Physical Source | Operating Condition | Dominant Dynamic Phenomenon | Expected System Response |
| :--- | :--- | :--- | :--- | :--- |
| `stimulus_seu_gearbox_health.hex` | SEU Gearbox (DDS) | 20 Hz / 0 V Load | Baseline gear meshing harmonics ($z_1 \cdot f_r$) | OOD Flagged ($u \ge 0.85$), Safe NC Closed |
| `stimulus_seu_gearbox_chipped.hex` | SEU Gearbox (DDS) | 20 Hz / 0 V Load | Chipped tooth transient impact & sidebands ($f_m \pm k f_r$) | OOD Flagged ($u \ge 0.85$), Alarm "UNKNOWN_DRIVETRAIN" |
| `stimulus_phm2009_gear_wear.hex` | PHM 2009 Challenge | 30 Hz / High Load | Broadened gear wear sideband spectrum | OOD Flagged ($u \ge 0.85$), Alarm "NON_BEARING_VIBRATION" |

---

## 2. Why Classification Accuracy % is NOT Applicable Here

In rotating machinery diagnostics, **a gearbox is not an induction motor bearing**:
1. Motor bearings exhibit impulse trains at ball pass frequencies (BPFO, BPFI, BSF, FTF).
2. Gearboxes exhibit continuous sinusoidal tooth engagement at gear mesh frequencies ($f_m = N_\text{teeth} \times f_\text{shaft}$) modulated by shaft rotation sidebands.
3. If an AI model trained only on motor bearings (CWRU) forces a 4-class classification ("Normal", "Inner", "Outer", "Ball") on a gearbox, it suffers from **Silent Hallucination** (confidently predicting Ball Fault with 99% probability on a broken gear tooth).

### The Scientific Metric: OOD Epistemic Vacuity Rejection Rate ($u$)
Under our Cortex-M0 HopACP / Evidential Dirichlet Framework:
$$u = \frac{K}{\sum_{k=1}^K (\alpha_k + 1)} \ge 0.85$$
- **Target Performance:** Rejection Rate $\ge 90\%$ on mechanical gearbox inputs.
- **Hardware Reaction:** The Gowin NPU delivers ambiguous INT8 logits; the Cortex-M0 firmware detects Dirichlet vacuity $u \ge 0.85$ and issues an OOD Warning to SCADA, refusing to trigger an erroneous bearing trip.

---

## 3. Hardware Co-Simulation Verification

Execute bit-true FPGA co-simulation:
```powershell
python scripts/verify_multi_dataset_fpga.py
```
Verification confirms all 3 gearbox vectors pass with zero FIR accumulator overflow and trigger the expected OOD epistemic vacuity rejection state.
