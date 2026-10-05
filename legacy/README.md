# 🏛️ `legacy/` Historical Research Archive & Evolution Log

This directory archives earlier exploratory prototypes, legacy research scripts, and historical hardware implementations developed prior to the migration to the **Gowin Primer 20K FPGA + Sonix SN32F407 MCU** dual-platform edge architecture.

---

## 📜 Architectural Evolution History

### Phase 1: MATLAB & Offline PoC (Early 2026)
* Exploratory offline DSP design and initial dataset extraction scripts (`Phase0_DSP_Design_Python.py`, `Phase1_2_DataPartition_DSP.m`, `main.m`).
* Explored acausal Hilbert transforms and standard Kurtogram bandpass filtering.

### Phase 2: Kaggle / Cloud Research & Jetson Orin NX (Mid 2026)
* `deployment_jetson/`: Benchmarking scripts targeting the NVIDIA Jetson Orin NX 8GB platform via TensorRT INT8 and NVDLA cores.
* `scripts_kaggle/` & `notebooks/`: Cloud Jupyter notebook builders and automated submission pipelines (`build_notebook.py`, `generate_notebook.py`).
* *Limitation Identified:* While Jetson provided powerful compute (~10W), true industrial edge vibration monitoring demands ultra-low-power (< 0.5W), deterministic sub-millisecond hardware acceleration, and zero non-causal lookahead.

### Phase 3: Silicon Co-Design on Gowin Primer 20K & Sonix SN32F407 (Present Architecture)
* Complete migration to custom Verilog RTL on the Gowin Primer 20K FPGA:
  - 32-tap folded minimum-phase FIR filter (`fir_minphase_32.v`).
  - True causal envelope demodulator (`envelope_demodulator.v`).
  - 12-way INT8 MAC systolic NPU core executing in 0.40 ms @ 100 MHz.
* Sonix SN32F407 MCU acting as Safety Host Supervisor (Q16.16 Adaptive Conformal Prediction, page-banded OLED, LoRaWAN / RS485).
* All active research, training, and deployment files now reside in the root `src/`, `scripts/`, `data/`, and `embedded/` directories.
