# VibraDistill-Edge: A 184-mW, 2.62-µs Streaming DSP and 12-Way Systolic NPU Accelerator with SIL-2 Conformal Safety for Industrial Machinery

**Authors:** Team Porygon (Danang Semiconductor and Artificial Intelligence Center — DSAC, University of Science and Technology — The University of Danang)  
**Target Venue:** IEEE Transactions on Industrial Informatics / IEEE Transactions on Very Large Scale Integration (VLSI) Systems  
**Status:** Certified Release `v1.0-dsac-final` | Commit: `770f43c`

---

## Abstract
Continuous condition monitoring and Remaining Useful Life (RUL) estimation for rotating machinery are critical to prevent catastrophic industrial equipment failures. However, existing commercial edge computing solutions (e.g., NVIDIA Jetson, industrial PCs) consume excessive power (5–15 W) and cost hundreds of dollars, while microcontrollers suffer from millisecond-scale latency and lack functional safety guarantees under mechanical breakdown. 

In this paper, we present **VibraDistill-Edge**, an ultra-low-power heterogeneous hardware/software co-design platform combining a low-cost FPGA (**Gowin GW2A-LV18PG256** @ 100 MHz) with an ARM Cortex-M0 safety supervisor (**Sonix SN32F407** @ 60 MHz). The FPGA architecture integrates a causal 32-tap minimum-phase FIR filter, an 18-bit fixed-point envelope demodulator, a 512-point real FFT core, and a 12-way parallel systolic Neural Processing Unit (NPU) operating across 6 dual-port BSRAM blocks (96-bit on-chip memory bandwidth). The NPU executes a heavily distilled convolutional architecture (8,677 parameters, 130× compression ratio) trained via Decoupled Knowledge Distillation (DKD) and Dirichlet Evidential Deep Learning (EDL). 

Experimental silicon verification demonstrates:
1. An end-to-end inference latency of **2.62 µs** (262 clock cycles @ 100 MHz) at **184 mW** silicon power dissipation;
2. Classification accuracy of **98.05%** (97.34% F1) on industrial CWRU benchmarks and **96.38%** (95.08% F1) on physical ADXL345 vibration sensors;
3. A continuous RUL prognostics pipeline combining NASA piecewise-linear degradation modeling with fixed-point HopACP conformal prediction, achieving **93.60% empirical conformal coverage** and providing advance failure warnings **101.7 minutes** prior to complete mechanical breakdown;
4. An independent hardware safety trip channel meeting IEC 61508 SIL-2 requirements, de-energizing protective relays within **0.75 ms** (well below the 1.0 ms industrial shutdown limit). The entire bill-of-materials (BOM) cost is under **$20 USD**, making ubiquitous industrial deployment viable.

**Index Terms:** Edge AI, Hardware/Software Co-Design, Systolic Array NPU, FPGA, Vibration Demodulation, Remaining Useful Life (RUL), Conformal Prediction, Functional Safety (IEC 61508 SIL-2).

---

## I. Introduction
Rotating machinery (electric motors, pumps, gearboxes, turbines) constitutes the operational backbone of modern industrial infrastructure. Bearing failures account for over 50% of unexpected rotating machinery breakdowns, generating billions of dollars in downtime and secondary mechanical damage annually.

Traditional edge vibration monitoring architectures face a severe trilemma:
* **Cloud/Industrial PC (IPC) Architectures:** Offloading raw high-frequency vibration streams (12–25.6 kHz) incurs unsustainable cellular/Ethernet bandwidth costs, non-deterministic latency (> 100 ms), and cloud dependency, precluding millisecond-scale emergency shutdowns.
* **Embedded GPUs (e.g., NVIDIA Jetson Orin Nano):** Although capable of deep inference, they dissipate 10–15 W, generate significant thermal dissipation requiring active cooling, cost $150–$300 USD, and exceed power budgets for self-powered or loop-powered industrial sensors.
* **Microcontroller-Only (MCU) Platforms:** Resource-constrained MCUs (ARM Cortex-M4/M7) lack dedicated vector SIMD datapaths for concurrent sub-band convolutions, yielding inference latencies of 7–50 ms and failing to guarantee hard real-time tripping under shock loads.

To resolve this trilemma, this paper introduces **VibraDistill-Edge**, an asymmetric heterogeneous co-design architecture that physically decouples hard real-time streaming DSP/AI acceleration (implemented on a cost-effective Gowin GW2A-18 FPGA) from safety supervisor telemetry and conformal calibration (hosted on an ultra-low-cost Sonix SN32F407 ARM Cortex-M0).

---

## II. Mathematical & Algorithmic Formulation

### A. Causal Minimum-Phase FIR Pre-Filtering
Conventional finite impulse response (FIR) anti-aliasing filters employ linear-phase symmetric taps, introducing an effective group delay of:
$$\tau_{\text{linear}} = \frac{N - 1}{2} = 15.5 \text{ samples}$$
At $F_s = 12.0\,\text{kHz}$, this incurs $1.29\,\text{ms}$ of algorithmic latency, severely degrading shock pulse detection. 

In VibraDistill-Edge, all zeroes residing outside the unit circle in the $z$-plane are reflected inside ($z_k \to 1/z_k^*$), synthesizing a 32-tap causal **True Minimum-Phase FIR filter**:
$$H_{\text{min}}(z) = h_0 \prod_{k=1}^{M} (1 - z_k z^{-1}), \quad |z_k| < 1$$
This reduces effective group delay to **3.2 samples**, recovering shock pulses **79.4% faster** than linear-phase counterparts with zero pre-ringing distortion.

### B. Monotonic 18-Bit IIR Envelope Demodulation
Mechanical impacts generate high-frequency structural resonances modulated by bearing fault characteristic frequencies ($\text{BPFI}$, $\text{BPFO}$, $\text{BSF}$). VibraDistill-Edge executes hardware envelope demodulation via full-wave rectification followed by a 2nd-order Butterworth IIR low-pass filter:
$$y[n] = b_0 |x[n]| + b_1 |x[n-1]| + b_2 |x[n-2]| - a_1 y[n-1] - a_2 y[n-2]$$
To preserve the 3rd to 7th fault harmonics ($7 \times \text{BPFI} = 1135.3\,\text{Hz}$), the filter cutoff is fixed at $f_c = 1,200.0\,\text{Hz}$ ($W_n = 0.20$ at $F_s = 12\,\text{kHz}$) utilizing Gowin 18-bit DSP9x9 multipliers with two's complement $-32768$ clamping to prevent numerical overflow.

### C. Decoupled Knowledge Distillation (DKD) & Dirichlet Uncertainty
To compress a multi-layer ResNet teacher ($1.13 \times 10^6$ parameters) into a micro student architecture ($8,677$ parameters), we decouple the classical Kullback-Leibler knowledge distillation loss into Target Class Knowledge Distillation (TCKD) and Non-Target Class Knowledge Distillation (NCKD):
$$\mathcal{L}_{\text{DKD}} = \alpha \cdot \text{TCKD}(p, q) + \beta \cdot \text{NCKD}(p, q)$$
Setting $\alpha = 1.0$ and $\beta = 8.0$ aggressively penalizes ambiguous inter-fault classifications between adjacent inner and outer race spectral components.

Furthermore, we integrate Evidential Deep Learning (EDL) placing a Dirichlet prior $\text{Dir}(\mathbf{p} \mid \boldsymbol{\alpha})$ over class probabilities. The evidential vacuity (epistemic uncertainty) is evaluated as:
$$u^* = \frac{K}{\sum_{k=1}^K (e_k + 1)} \in [0, 1]$$
When sensor disconnections or Out-Of-Distribution (OOD) noise occur, $u^* \to 1.0$, automatically triggering an OOD alert rather than producing overconfident hallucinations.

### D. Piecewise-Linear RUL & Fixed-Point HopACP Conformal Prediction
Standard linear degradation labeling ($RUL(t) = \frac{T - t}{T}$) causes naive regressors to collapse to the empirical dataset mean ($\approx 35\% - 37\%$) because the first $70\% - 80\%$ of bearing operational life consists of stationary Gaussian noise with identical power spectra. 

We adopt the NASA PHM piecewise-linear degradation standard:
$$RUL^*(t) = \begin{cases} 1.0, & t < t_{\text{FDP}} \\ \frac{T - t}{T - t_{\text{FDP}}}, & t \ge t_{\text{FDP}} \end{cases}$$
where $t_{\text{FDP}}$ denotes the First Degradation Point (empirically $73.2\%$ of lifespan). 

To provide distribution-free finite-sample guarantees, the MCU executes HopACP conformal calibration in Q16.16 fixed-point arithmetic:
$$\hat{C}_{1-\alpha}(X_{n+1}) = \left[ \hat{Y}_{n+1} - \hat{q}_{1-\alpha}, \; \hat{Y}_{n+1} + \hat{q}_{1-\alpha} \right]$$
achieving rigorous $\ge 90\%$ statistical coverage without floating-point emulation overhead.

---

## III. Heterogeneous Hardware Architecture

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              FPGA GOWIN GW2A-LV18PG256 (100 MHz)                       │
│                                                                                        │
│  Vibration In   ┌─────────────┐   ┌──────────────┐   ┌────────────┐   ┌─────────────┐  │
│ ───────────────►│ 32-tap FIR  ├──►│ Envelope Dem ├──►│  512 Real  ├──►│  Log-Energy │  │
│  (12kHz / 3.2k) │ (Min-Phase) │   │ (18-bit IIR) │   │  FFT Core  │   │  Normalizer │  │
│                 └─────────────┘   └──────────────┘   └────────────┘   └──────┬──────┘  │
│                                                                              │         │
│  12-Way Systolic NPU Accelerator:                                            │         │
│  ┌───────────────────────────────────────────────────────────────────────────▼──────┐  │
│  │ 6x Dual-Port BSRAM Banks (96-Bit Bus) ──► 12x Parallel INT8 MAC Processing Units │  │
│  │ (Normal, Inner, Outer, Ball x 3 Sub-bands) ──► 32-bit Accumulators (260 Cycles)  │  │
│  │ Head RUL Register: rul_q15 = 32768 - Sat(ΔS * Factor) (1-Cycle 10ns Latency)     │  │
│  └───────────────────────────────────────────────────────────────────────────┬──────┘  │
│                                                                              │         │
│  SPI Master DMA Controller (524-Byte Frame, Hardware CRC-16) ────────────────┼─────────┘
└──────────────────────────────────────────────────────────────────────────────┼──────────
                                                                               │ SPI Bus
┌──────────────────────────────────────────────────────────────────────────────▼──────────┐
│                             MCU SONIX SN32F407 (ARM CORTEX-M0 @ 60 MHz)                │
│                                                                                        │
│  SPI DMA RX Buffer ──► Hardware CRC-16 Check ──► HopACP Q16.16 Conformal Smoothing    │
│                                              │                                         │
│                                              ├──► I2C OLED Maintenance Dashboard      │
│                                              └──► SIL-2 Deterministic Trip Channel     │
│                                                   (GPIO P1.0 Relay Trip < 0.75 ms)     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## IV. Experimental Results & Discussion

### A. Performance, Power, and Area (PPA) Silicon Benchmarking
Table I compares VibraDistill-Edge with commercial off-the-shelf edge diagnostic implementations.

**TABLE I: PPA Silicon & System Benchmark Comparison**

| Metric | Xilinx Zynq-7020 | STM32H7 (Cortex-M7) | NVIDIA Jetson Orin Nano | **VibraDistill-Edge (Ours)** |
| :--- | :---: | :---: | :---: | :---: |
| **Inference Latency** | 12.40 ms | 7.10 ms | 1.00 ms | **2.62 µs (380×–4,700× faster)** |
| **Active Power** | 2,500 mW | 450 mW | 10,000 mW | **184 mW (96% reduction)** |
| **Throughput** | 80 inf/s | 140 inf/s | 1,000 inf/s | **381,679 inf/s** |
| **CWRU Accuracy** | 97.80% | 94.20% | 98.50% | **98.05% (F1: 97.34%)** |
| **ADXL345 Accuracy** | 94.10% | 91.50% | 96.00% | **96.38% (F1: 95.08%)** |
| **SIL-2 Trip Latency** | N/A (> 10 ms) | 5.0 ms | N/A (> 15 ms) | **0.75 ms (< 1.0 ms standard)** |
| **System BOM Cost** | ~$120 USD | ~$35 USD | ~$250 USD | **< $20 USD (< 500,000 VNĐ)** |

### B. Prognostic Reliability & Advance Warning Margin
Evaluated across the full run-to-failure lifecycle of PRONOSTIA `Bearing1_3` (2,375 snapshots, 6.55 hours continuous degradation):
* **Conformal Coverage:** Achieved **93.60%** empirical coverage (exceeding the 90.0% safety threshold) with an average interval width of $\pm 3.535\,\text{hours}$.
* **Advance Warning Margin:** The system triggered an advance maintenance advisory **101.7 minutes** prior to terminal spalling.
* **Deterministic Trip:** When vibration energy surged past $RMS \ge 8.0g$, the MCU de-energized the protective relay in **0.75 ms**, successfully passing SIL-2 verification.

---

## V. Conclusion
VibraDistill-Edge demonstrates that high-performance rotating machinery diagnostics and safety-certified prognostics do not require power-hungry industrial PCs or expensive edge GPUs. By coupling a dedicated streaming DSP and 12-way systolic NPU on a low-cost Gowin FPGA with an ARM Cortex-M0 SIL-2 supervisor, the proposed system delivers microsecond-level latency ($2.62\,\mu\text{s}$), milliwatt-scale power ($184\,\text{mW}$), and sub-millisecond physical emergency tripping ($0.75\,\text{ms}$) at a total BOM cost under $20 USD.

All RTL sources, firmware, testbenches, and benchmark datasets are publicly accessible at:  
[https://github.com/zok213/VIbraDistill](https://github.com/zok213/VIbraDistill) (Release Tag: `v1.0-dsac-final`).
