# Gowin FPGA Tang Primer 20K (GW2A-LV18) Block SRAM ROMs

> **Target Silicon:** Gowin GW2A-LV18PG256C8/I7  
> **On-Chip Memory:** 46 Dual-Port Block SRAMs (18 Kb each = ~103 KB Total)  
> **Memory Utilization:** 30 / 46 BSRAMs (65.22%) for 5 Concurrent Industrial Profiles  
> **Latency:** 262 Cycles @ 100 MHz = 2.62 µs per inference (381,679 inferences/second)  
> **Zero External RAM:** 100% On-Chip BSRAM (Zero DDR3 memory required)

---

## 1. Directory Structure & Organization

```
embedded/fpga_gowin/roms/
├── README.md                       <- This master architectural specification
├── PROFILE_REGISTRY.json           <- Machine-readable registry of 5 industrial profiles
├── STIMULI_MANIFEST.json           <- Master manifest of 512-sample test stimulus vectors
├── bsram_memory_map.txt            <- Hardware BSRAM address and port mapping
├── profiles/                       <- 5 Industrial model profiles (BSRAM Banks 0..5)
│   ├── prf01_cwru_motor_9ball/     <- CWRU motor bearing (SKF 6205, 12 kHz, Acc 98.71%)
│   ├── prf02_mfpt_heavy_16ball/    <- MFPT heavy bearing (Nice 1012, 16 balls, Acc 88.25%)
│   ├── prf03_pronostia_rul/        <- PRONOSTIA FEMTO run-to-failure degradation tracking
│   ├── prf04_gearbox_drivetrain/   <- SEU & PHM2009 gearbox drivetrain OOD monitoring
│   └── adxl345_native/             <- ADXL345 MEMS sensor mode (3.2 kHz, Acc 96.38%)
├── stimuli/                        <- 4 Suites of 512-sample int16 stimulus test vectors
│   ├── cwru/                       <- 5 in-domain motor vectors (Normal, Inner, Outer, Ball, Mixed)
│   ├── mfpt_crossdomain/           <- 3 cross-domain heavy bearing vectors
│   ├── ood_gearbox/                <- 3 mechanical gearbox drivetrain OOD vectors
│   └── pronostia_degradation/      <- 3 continuous degradation lifecycle snapshots
├── hil/                            <- CWRU 12 kHz HIL weights (Backward compatibility)
├── adxl345/                        <- ADXL345 3.2 kHz weights (Backward compatibility)
├── stimulus_suite_100/             <- 100-vector industrial safety verification suite
└── stimulus_cwru_*.hex             <- Root testbench vectors for tb_npu_cosim.v
```

---

## 2. Gowin BSRAM Silicon Allocation Map

Each 12-way parallel systolic core requires **6 BSRAMs** configured in dual-port 16-bit word mode ($257\text{ words} \times 16\text{ bits}$):
- Word format: `{Channel 2b+1 [15:8], Channel 2b [7:0]}` (two INT8 signed channels per word).
- Total for 5 profiles: $5 \times 6 = \mathbf{30 / 46\text{ BSRAMs}}$ (**65.22%**).
- Remaining 16 BSRAMs (34.78%) are reserved for FFT spectrum ping-pong and FIR delay buffers.

| BSRAM Banks | Active Profile | Hardware Purpose | Sample Rate | Metric |
| :---: | :--- | :--- | :---: | :---: |
| **00 .. 05** | `prf01_cwru_motor_9ball` | Standard electric motor bearing (SKF 6205, 9 balls) | 12.0 kHz | **98.71% Acc** |
| **06 .. 11** | `prf02_mfpt_heavy_16ball` | Heavy industrial machinery bearing (Nice 1012, 16 balls) | 12.0 kHz | **88.25% Acc** |
| **12 .. 17** | `prf03_pronostia_rul` | Run-to-failure lifetime degradation tracking | 12.0 kHz | **Coverage $\ge 90\%$** |
| **18 .. 23** | `prf04_gearbox_drivetrain`| Planetary & spur gearbox drivetrain OOD rejection | 12.0 kHz | **$u \ge 0.85$ (SIL-2)** |
| **24 .. 29** | `adxl345_native` | Physical MEMS accelerometer SPI interface | 3.2 kHz | **96.38% Acc** |
| **30 .. 45** | *System Infrastructure* | 512-Point FFT ping-pong buffers & FIR causal taps | — | — |

---

## 3. How to Use in Verilog RTL Testbenches

Load weights in Verilog testbenches using `$readmemh`:
```verilog
// In npu_12way_core.v or testbench:
initial begin
    $readmemh("embedded/fpga_gowin/roms/profiles/prf01_cwru_motor_9ball/npu_weights_bank0.hex", bank0_mem);
    $readmemh("embedded/fpga_gowin/roms/profiles/prf01_cwru_motor_9ball/npu_weights_bank1.hex", bank1_mem);
    $readmemh("embedded/fpga_gowin/roms/profiles/prf01_cwru_motor_9ball/npu_weights_bank2.hex", bank2_mem);
    $readmemh("embedded/fpga_gowin/roms/profiles/prf01_cwru_motor_9ball/npu_weights_bank3.hex", bank3_mem);
    $readmemh("embedded/fpga_gowin/roms/profiles/prf01_cwru_motor_9ball/npu_weights_bank4.hex", bank4_mem);
    $readmemh("embedded/fpga_gowin/roms/profiles/prf01_cwru_motor_9ball/npu_weights_bank5.hex", bank5_mem);
end
```

To switch machine profile at runtime, change the profile base address via register `[2:0] profile_select` without reconfiguring the FPGA bitstream.
