# 🏆 `FPGA&MCU/` Competition Registration & Technical Documents

This directory contains the official competition deliverables, academic LaTeX papers, system architecture figures, and registration documents for the **Cuộc thi Thiết kế FPGA và MCU Mở rộng Khu vực Miền Trung 2026**.

---

## 📄 Key Deliverables

* **`BAN_DANG_KY_DE_TAI_FPGA_MCU_2026.docx`**: 
  - Official final registration document submitted to the Organizing Committee.
  - Complete with problem statement, co-design philosophy, hardware budgeting tables, peripheral specifications, and 5-week actionable execution schedule.
* **`research_proposal.tex`**:
  - Full academic IEEE-format conference paper covering the theoretical methodology: Decoupled Knowledge Distillation, Physics-Guided Kinematic Prior Fusion, Dirichlet Evidential Uncertainty, and Bounded-Delay Adaptive Conformal Prediction.
* **`generate_registration_doc.py`**:
  - Python script to programmatically regenerate the official registration DOCX with all tables, formatting, and mathematical symbols.
* **`figures/`**:
  - `system_block_diagram.png` / `.pdf`: Master hardware-software co-design block diagram (14-stage dataflow).
  - `fig_envelope.png` / `.pdf`: Causal envelope demodulation waveforms vs acausal Hilbert transform comparison.
  - `fig_fir.png` / `.pdf`: Minimum-phase 32-tap causal FIR filter response and group delay.
  - `fig_acp.png` / `.pdf`: Bounded-Delay Adaptive Conformal Prediction coverage convergence proof.
  - `fig_resolution.png` / `.pdf`: FFT frequency resolution across decimation stages.

---

## 🛠️ Verification & Generation Commands

To regenerate the official registration DOCX document:
```bash
python "FPGA&MCU/generate_registration_doc.py"
```

To regenerate all technical vector diagrams:
```bash
python "FPGA&MCU/gen_figures.py"
```
