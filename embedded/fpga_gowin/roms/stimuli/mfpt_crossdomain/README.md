# Suite 2: MFPT Cross-Domain Heavy Bearing Stimuli (`roms/stimuli/mfpt_crossdomain/`)

> **Source Testbed:** Machinery Failure Prevention Technology (MFPT) Test Rig  
> **Bearing:** Nice 1012 (16 balls, 1500 RPM, 270 lbs load)  
> **Format:** 512 Samples, Signed INT16 Hex, Peak 4,500 LSB (Polyphase Resampled to 12 kHz)

---

## Files Inventory

| File Name | Physical File Source | Target Condition | Expected FPGA Pred (PRF02) |
| :--- | :--- | :--- | :---: |
| `stimulus_mfpt_baseline.hex` | `MFPT Fault Data Sets/1 - Three Baseline Conditions/baseline_1.mat` | Healthy baseline | **Normal (Cls 0)** |
| `stimulus_mfpt_inner.hex`    | `MFPT Fault Data Sets/4 - Seven Inner Race Fault Conditions/InnerRaceFault_vload_1.mat` | Inner race fault | **InnerRace (Cls 1)** |
| `stimulus_mfpt_outer.hex`    | `MFPT Fault Data Sets/2 - Three Outer Race Fault Conditions/OuterRaceFault_1.mat` | Outer race fault | **OuterRace (Cls 2)** |
