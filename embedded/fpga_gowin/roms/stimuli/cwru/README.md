# Suite 1: CWRU In-Domain Motor Bearing Stimuli (`roms/stimuli/cwru/`)

> **Source Testbed:** Case Western Reserve University (CWRU) Motor Bearing Testbed  
> **Bearing:** SKF 6205-2RS (9 balls, 1797 RPM, 12 kHz)  
> **Format:** 512 Samples, Signed INT16 Hex, Peak 4,500 LSB

---

## Files Inventory

| File Name | Physical File Source | Target Condition | Expected FPGA Pred | Vacuity ($u$) |
| :--- | :--- | :--- | :---: | :---: |
| `stimulus_cwru_normal.hex` | `data/CWRU_Dataset/Normal/97.mat` | Healthy baseline | **Normal (Cls 0)** | $< 0.10$ |
| `stimulus_cwru_inner.hex`  | `data/CWRU_Dataset/Train_7mil/InnerRace/105.mat` | Inner race 7-mil | **InnerRace (Cls 1)**| $< 0.10$ |
| `stimulus_cwru_outer.hex`  | `data/CWRU_Dataset/Train_7mil/OuterRace/130.mat` | Outer race 7-mil | **OuterRace (Cls 2)**| $< 0.10$ |
| `stimulus_cwru_ball.hex`   | `data/CWRU_Dataset/Train_7mil/Ball/118.mat` | Ball defect 7-mil | **Ball (Cls 3)** | $< 0.10$ |
| `stimulus_cwru_mixed.hex`  | `data/CWRU_Dataset/Test_Unseen/21mil/OuterRace/197.mat`| Severe compound 21-mil | **Ball / Outer (Cls 3/2)**| $< 0.10$ |
