# MATLAB RUL Prognostics Benchmark (`data/rul_mat_benchmarks/`)

> **Location:** `data/rul_mat_benchmarks/`  
> **Source Platform:** FEMTO-ST PRONOSTIA Accelerated Bearing Degradation Testbed  
> **File:** `bearing_lifecycle_1_3.mat`  
> **Target Problem:** Run-to-Failure Continuous Remaining Useful Life (RUL) Prediction with Conformal Uncertainty Bounds

---

## 1. Physical Testbed Specifications

| Parameter | Laboratory Physical Value | Notes |
| :--- | :--- | :--- |
| **Bearing Type** | Miniature Ball Bearing (NSK 6804RS) | Outer diam $32\text{ mm}$, inner $20\text{ mm}$, $13$ balls |
| **Radial Load** | $4,000\text{ N}$ ($400\text{ kg}$) | Constant dynamic force exceeding rated fatigue limit |
| **Shaft Speed** | $1,800\text{ RPM}$ ($f_r = 30.0\text{ Hz}$) | Synchronous induction motor drive |
| **Sampling Rate ($f_s$)** | $25,600\text{ Hz}$ | High-bandwidth piezoelectric sensor |
| **Snapshot Recording** | $2,560\text{ samples}$ every $10\text{ s}$ | $0.1\text{ s}$ recording window per snapshot |
| **Total Test Duration** | $2,375\text{ snapshots} = 23,750\text{ s}$ | **$6.597\text{ hours}$** continuous run until failure |
| **Failure Criterion** | Vibration amplitude $> 20.0\text{g}$ | Severe destructive flaking / race spalling |

---

## 2. MATLAB `.mat` Structure Specification

To inspect or load directly in MATLAB or Python:

```matlab
% In MATLAB:
data = load('bearing_lifecycle_1_3.mat');
plot(data.time_hours, data.horizontal_rms_g);
xlabel('Operating Time (Hours)');
ylabel('RMS Vibration (g)');
```

```python
# In Python:
import scipy.io as sio
mat = sio.loadmat('data/rul_mat_benchmarks/bearing_lifecycle_1_3.mat')
print("Keys:", [k for k in mat.keys() if not k.startswith('__')])
```

### Key Field Descriptions:
- `dataset_name`: String descriptor (`"PRONOSTIA_Bearing1_3"`).
- `condition`: Operating speed and radial load details.
- `fs_hz`: Sampling frequency ($25,600\text{ Hz}$).
- `snapshot_interval_sec`: $10.0\text{ s}$.
- `total_snapshots`: $2,375$.
- `total_duration_hours`: $6.5972\text{ hours}$.
- `time_hours`: Vector of elapsed test hours ($0 \to 6.6\text{ h}$).
- `true_rul_hours`: Exact ground truth remaining hours ($6.6 \to 0\text{ h}$).
- `true_rul_pct`: Ground truth remaining percentage ($100\% \to 0\%$).
- `horizontal_rms_g`: RMS acceleration trajectory across test life.
- `horizontal_kurtosis`: Kurtosis trajectory (detects initial micro-spalling knee point).
- `horizontal_peak_g`: Maximum peak acceleration per snapshot.
- `vibration_raw_g`: Matrix of shape `[2375, 2560]` containing raw time series waveforms.

---

## 3. Conformal Prognostics Verification

To run automated streaming inference, evaluate the HopACP conformal prediction bounds ($1 - \alpha = 90\%$), and verify SIL-2 emergency trip timing:

```powershell
python scripts/verify_mat_rul_prognostics.py
```
Outputs performance metrics:
- **Conformal Coverage:** Target $\ge 90.0\%$
- **MAE:** Target $\le 1.85\text{ hours}$
- **SIL-2 Trip Latency:** Target $< 1.0\text{ ms}$ upon lower bound hitting critical threshold.
