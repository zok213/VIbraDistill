# VibraDistill-Edge: 100-Run Empirical Ablation & Architectural Benchmark Report

**Total Experimental Runs Analyzed**: 100 trials across 5 distinct research suites.

## 1. Architectural Comparison (Parameter-Matched Baselines)
Comparison of VibraDistillMicro against 1D-CNN, GRU, Bi-LSTM, and MLP baselines under 10 KB parameter budget across 5 seeds.

| Architecture | Params | MACs | SRAM Peak | M0 Latency | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | ECE (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BiLSTMModel** | 8,469 | 97,664 | 4608 B | 16.28 ms | 66.23 ± 2.18 | 35.72 ± 1.41 | 46.62 ± 2.07 | 33.74 ± 2.89 |
| **GRUModel** | 6,933 | 82,048 | 3072 B | 10.94 ms | 61.24 ± 5.87 | 35.30 ± 5.11 | 48.15 ± 5.06 | 32.03 ± 0.83 |
| **MLPBaseline** | 9,525 | 8,764 | 512 B | 0.44 ms | 81.24 ± 2.96 | 45.78 ± 5.57 | 63.10 ± 7.79 | 34.21 ± 1.85 |
| **SingleKernelCNN** | 7,933 | 524,664 | 3328 B | 30.61 ms | 89.26 ± 11.80 | 34.50 ± 5.24 | 51.96 ± 3.49 | 37.42 ± 6.01 |
| **VibraDistillMicro** | 8,677 | 560,144 | 4352 B | 32.68 ms | 15.80 ± 9.30 | 10.73 ± 1.27 | 12.66 ± 5.20 | 52.06 ± 15.32 |

### Paired Statistical Significance (VibraDistillMicro vs Baselines across 5 seeds):

- **VibraDistillMicro vs SingleKernelCNN**: Val F1 diff = +-73.46% (p = 7.7974e-05); Unseen 21-mil F1 diff = +-39.30% (p = 1.1349e-04)
- **VibraDistillMicro vs GRUModel**: Val F1 diff = +-45.44% (p = 5.5759e-04); Unseen 21-mil F1 diff = +-35.49% (p = 1.9717e-04)
- **VibraDistillMicro vs BiLSTMModel**: Val F1 diff = +-50.43% (p = 1.7625e-04); Unseen 21-mil F1 diff = +-33.96% (p = 2.7374e-04)
- **VibraDistillMicro vs MLPBaseline**: Val F1 diff = +-65.44% (p = 2.1432e-04); Unseen 21-mil F1 diff = +-50.44% (p = 2.4127e-04)

## 2. Inductive Kinematic Prior Ablation
Evaluating the physical necessity of Normalized Harmonic Contrast (NHC) kinematic fault priors.

| Prior Configuration | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Mean Vacuity (Uncertainty) | ECE (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Prior_detuned** | 98.95 ± 0.00 | 27.21 ± 0.00 | 45.88 ± 0.00 | 0.282 ± 0.000 | 21.73 ± 0.00 |
| **Prior_none** | 98.41 ± 0.00 | 25.35 ± 0.00 | 42.79 ± 0.00 | 0.289 ± 0.000 | 22.11 ± 0.00 |
| **Prior_normal** | 99.13 ± 0.00 | 29.49 ± 0.00 | 48.06 ± 0.00 | 0.276 ± 0.000 | 21.30 ± 0.00 |
| **Prior_shuffled** | 99.03 ± 0.16 | 28.74 ± 0.11 | 44.54 ± 0.24 | 0.280 ± 0.001 | 21.78 ± 0.17 |

## 3. Knowledge Distillation & Uncertainty Loss Ablation
Evaluating Decoupled Knowledge Distillation (DKD) vs Vanilla Hinton KD vs Standard Cross-Entropy vs Evidential Dirichlet Learning (EDL).

| Training Objective | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Expected Calibration Error (ECE) |
| :--- | :---: | :---: | :---: | :---: |
| **Loss_ce** | 18.47 ± 15.11 | 10.13 ± 0.16 | 15.38 ± 7.25 | 40.60 ± 14.72 |
| **Loss_dkd** | 29.08 ± 24.45 | 19.87 ± 15.32 | 22.81 ± 21.58 | 34.63 ± 16.55 |
| **Loss_dkd_edl** | 45.78 ± 30.74 | 23.97 ± 14.01 | 28.36 ± 17.87 | 30.05 ± 16.91 |
| **Loss_hinton** | 41.90 ± 37.91 | 21.24 ± 15.40 | 29.52 ± 24.68 | 35.49 ± 12.18 |

## 4. Environmental Stress & Additive Noise Robustness
Testing VibraDistillMicro under severe white Gaussian noise on the envelope spectrum (down to 0 dB SNR).

| Signal-to-Noise Ratio (SNR) | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Retention Ratio vs Clean |
| :--- | :---: | :---: | :---: | :---: |
| **Clean** | 99.13 ± 0.00 | 29.49 ± 0.00 | 48.06 ± 0.00 | 100.0% |
| **SNR_0dB** | 15.62 ± 0.00 | 9.99 ± 0.00 | 9.98 ± 0.00 | 15.8% |
| **SNR_12dB** | 52.49 ± 0.76 | 34.01 ± 0.16 | 39.45 ± 0.74 | 53.0% |
| **SNR_6dB** | 16.16 ± 0.17 | 10.14 ± 0.08 | 10.35 ± 0.13 | 16.3% |

## 5. Post-Training Quantization & Bit-True Gowin NPU Emulation
Verifying numerical parity from 32-bit floating point to folded BatchNorm and Gowin 12-way Systolic INT8 Engine.

| Execution Mode | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Quantization Degradation (delta F1) |
| :--- | :---: | :---: | :---: | :---: |
| **FP32_Baseline** | 99.13 ± 0.00 | 29.49 ± 0.00 | 48.06 ± 0.00 | +0.00% |
| **Folded_BatchNorm** | 99.13 ± 0.00 | 29.49 ± 0.00 | 48.06 ± 0.00 | +0.00% |
| **INT8_Gowin_NPU** | 15.62 ± 0.00 | 9.99 ± 0.00 | 9.98 ± 0.00 | -83.51% |