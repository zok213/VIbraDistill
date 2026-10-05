# 🚀 `scripts/` Operational CLI Workflows & Runbook

This directory contains standalone, production-grade CLI executable scripts covering the end-to-end research and deployment pipeline: from hardware DSP verification to model distillation, zero-leakage holdout benchmarking, and silicon export.

---

## 📋 Execution Runbook (Step-by-Step)

### Step 1: Verify Hardware-Faithful DSP Pipeline
Verifies the bit-true agreement between Python signal processing and Gowin Verilog RTL (`fir_minphase_32.v` and `envelope_demodulator.v`), and validates SKF 6205 kinematic defect frequencies.
```bash
python scripts/01_verify_dsp.py
```
*Expected Output:* Confirms 32-tap minimum-phase causal FIR response (2.417 ms group delay), strictly positive causal envelope demodulation, and SKF 6205 multipliers: $\text{BPFO}=3.5848\times$, $\text{BPFI}=5.4152\times$, $\text{BSF}=2.3567\times$, $\text{FTF}=0.3983\times$.

---

### Step 2: Train the Teacher 1D-ResNet Oracle
Trains the high-capacity residual network (~1.0M parameters) on CWRU `Train_7mil` across all 4 motor loads:
```bash
python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --lr 0.001
```
*Key Arguments:*
* `--epochs`: Training epochs (default: 30)
* `--batch_size`: Batch size (default: 64)
* `--lr`: Initial AdamW learning rate with cosine decay (default: 0.001)
* `--data_dir`: Root CWRU path (`data/CWRU_Dataset`)
* `--save_dir`: Output directory for checkpoints (`checkpoints/teacher/`)
*Artifacts Produced:* `checkpoints/teacher/best_teacher.pt`

---

### Step 3: Distill into Student VibraDistillMicro via DKD & EDL
Transfers knowledge from the pre-trained Teacher to the edge student model (`VibraDistillMicro`, 8,677 parameters) using Decoupled Knowledge Distillation ($\tau=5.0, \tau^2=25.0, \alpha=1.0, \beta=2.0$) and Evidential Deep Learning:
```bash
python scripts/03_train_student_dkd.py --epochs 35 --batch_size 64 --temperature 5.0 --alpha 1.0 --beta 2.0 --edl_weight 0.5
```
*Key Arguments:*
* `--teacher_ckpt`: Path to pre-trained teacher checkpoint (`checkpoints/teacher/best_teacher.pt`)
* `--temperature`: Softening temperature $\tau$ (default: 5.0)
* `--alpha`: Target-Class Knowledge Distillation (TCKD) weight (default: 1.0)
* `--beta`: Non-Target Class Knowledge Distillation (NCKD) weight (default: 2.0)
* `--edl_weight`: Evidential Deep Learning loss weight (default: 0.5)
*Artifacts Produced:* `checkpoints/student_dkd/best_student_dkd.pt`

---

### Step 4: Zero-Leakage Comprehensive Evaluation
Evaluates the distilled student and teacher on physically unseen bearing fault datasets (`14mil` and `21mil` holdouts):
```bash
python scripts/04_evaluate_zero_leakage.py
```
*Metrics Computed:*
* Overall Accuracy (%)
* Macro-F1 (%)
* Per-Class Precision, Recall, and F1-Scores
* Confusion Matrix
* Expected Calibration Error (ECE %)
* Dirichlet Vacuity (epistemic uncertainty) distribution

---

### Step 5: Post-Training Quantization (PTQ) & Hardware Silicon Export
Performs mathematically exact BatchNorm folding, symmetric INT8 quantization, and exports hardware deployment files:
```bash
python scripts/05_quantize_and_export.py
```
*Artifacts Produced:*
1. **Gowin Primer 20K FPGA**:
   - `embedded/fpga_gowin/roms/npu_weights_bank0.mi` through `bank5.mi` (6 BSRAM banks for 12-way MAC systolic core).
   - `embedded/fpga_gowin/roms/bsram_memory_map.txt` (Full silicon memory budgeting map).
2. **Sonix SN32F407 MCU**:
   - `embedded/mcu_sonix/app/vibradistill_weights.h` (C const arrays for INT8 weights and INT32 biases).
   - `embedded/mcu_sonix/app/vibradistill_model.h` (C API header).
