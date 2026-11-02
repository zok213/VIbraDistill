# Multi-Dataset Hardware Stimulus Test Suites (`roms/stimuli/`)

> **Location:** `embedded/fpga_gowin/roms/stimuli/`  
> **Format:** 16-Bit Signed Hexadecimal (`0000` to `FFFF` two's complement, 512 samples/file)  
> **Zero FIR Saturation Rule:** Normalized to peak $4,500\text{ LSB}$ ($4,500 \times 5,263 = 23.68\text{M} < 2^{31}-1$).

---

## 1. Stimuli Directory Layout

```
embedded/fpga_gowin/roms/stimuli/
├── README.md                   <- This specification
├── cwru/                       <- In-domain motor bearing vectors (SKF 6205, 12 kHz)
│   ├── stimulus_cwru_normal.hex
│   ├── stimulus_cwru_inner.hex
│   ├── stimulus_cwru_outer.hex
│   ├── stimulus_cwru_ball.hex
│   └── stimulus_cwru_mixed.hex
├── mfpt_crossdomain/           <- Cross-domain heavy bearing vectors (Nice 1012, 12 kHz)
│   ├── stimulus_mfpt_baseline.hex
│   ├── stimulus_mfpt_inner.hex
│   └── stimulus_mfpt_outer.hex
├── ood_gearbox/                <- Mechanical OOD gearbox vectors (SEU & PHM2009, 12 kHz)
│   ├── stimulus_seu_gearbox_health.hex
│   ├── stimulus_seu_gearbox_chipped.hex
│   └── stimulus_phm2009_gear_wear.hex
└── pronostia_degradation/      <- Run-to-failure continuous degradation snapshots (12 kHz)
    ├── stimulus_pronostia_early_life.hex
    ├── stimulus_pronostia_mid_life.hex
    └── stimulus_pronostia_end_of_life.hex
```

---

## 2. Test Execution

To verify all stimuli across all 4 suites in bit-true FPGA hardware co-simulation:
```powershell
python scripts/verify_multi_dataset_fpga.py
```
Expected: **100% BIT-TRUE RTL PARITY across all 4 suites.**
