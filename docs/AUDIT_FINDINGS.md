# Audit Findings (2026-10-03) — what is proven, what is not

This file is the authoritative status of claims. Anything not listed under "Verified" must not be quoted as a result.

## Verified (reproducible from code in this repo)
| Claim | Evidence |
|---|---|
| Student has 8,677 parameters | `tests/test_models.py` |
| BN folding is numerically exact (<1e-4) | `tests/test_quantization.py` |
| FP32 student: Val macro-F1 99.13%, 14-mil 29.49%, 21-mil 48.06% (CWRU, bearing-wise split) | `experiments/benchmark_100_runs.csv` suite `Quantization/FP32_Baseline`; `scripts/07_verify_int8_parity.py` |
| Zero-leakage split: train 7-mil, hold-out 14/21-mil | `src/datasets/cwru_loader.py`, `data/README.md` |
| 24 unit tests pass | `python -m unittest discover tests` |

## Disproven / corrected
| Earlier claim | Reality |
|---|---|
| INT8 Gowin-NPU emulation loses only ~0.3% F1 (98.85%) | **False.** Measured INT8 emulator macro-F1: Val ~23%, 14-mil ~11%, 21-mil ~12% (`experiments/int8_parity.json`). The original emulator never applied requantization scales (mult=1, shift=0) so it saturated; after implementing calibrated per-channel requantization the integer path still collapses. Layer probe: cosine vs float = 0.995 (stage1), 0.994 (stage2), 0.936 (stage3), 0.874 (fc), 0.457 (logits). |
| "VibraDistillMicro 99.13±0.00 beats all baselines" | Std 0.00 arises because suites 2, 4, 5 re-evaluate **one fixed checkpoint** under different "seeds" — they are not independent trials. Suite 1 re-trained the student for 1 DKD epoch from the checkpoint and got Val F1 7–30%. |
| Student outperforms GRU/BiLSTM/CNN/MLP | Not supported. Baselines were trained 2 epochs with CE; the student had 20 epochs of DKD+EDL. Unequal budget. On 21-mil the MLP (63.1%) and CNN (52.0%) scored higher. |
| ECE 2.84%, latency 0.28 ms / 32.7 ms, SRAM 4,352 B | Invented/hard-coded in the old profiler (it described a different architecture). Measured ECE is ~21%. New profiler counts MACs from the graph: 644,056 MACs; **estimated** M0 ≈43 ms (assumes 4 cycles/MAC), FPGA ≈0.54 ms (ideal). Both are estimates, not measurements. |
| HopACP guarantees ≥90% coverage | Only unit-tested on synthetic errors. No empirical coverage on XJTU-SY / PRONOSTIC yet. Not a proof. |
| Physics-FiLM / ELU-evidence improve results | Implemented, **never trained or evaluated**. No evidence either way. |
| Literature comparison table values for other methods | Not measured by us; taken from web-search summaries that were not verified against the papers. Do not cite. |
| FPGA 28% LUT / <115 mW power | Estimates; nothing has been synthesized or measured. |

## Open problems (highest priority first)
1. **INT8 deployment is broken** for this FP32-trained network. Needs quantization-aware training (QAT) or an architecture/activation-range redesign; then re-verify with `scripts/07_verify_int8_parity.py`.
2. **Fair benchmark**: identical epochs/optimizer/augmentation for all models, independent seeds retrained from scratch, mean±std over real variance.
3. **Generalization is weak**: 29%/48% on unseen fault sizes. This is the central scientific result and it is not yet good.
4. **Conformal RUL** must be validated on run-to-failure data (XJTU-SY, PRONOSTIA) with leave-one-bearing-out calibration.
5. Remaining datasets (9 of 11) are downloaded but unused by any experiment.
6. Hardware numbers need on-target measurement (DWT cycle counter on the MCU, Gowin synthesis report).
