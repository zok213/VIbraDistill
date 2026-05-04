"""
PHASE 1: XJTU-SY RUL PROGNOSTICS (KAGGLE / PYTORCH)
Target: Kalman Filter State Estimation + Exponential Extrapolation + Conformal Prediction

Bug 3 Fix: a_fit, b_fit must come from curve_fit on REAL XJTU-SY experiments,
           not from np.exp(0.04*t) + noise simulation.
"""

import numpy as np
import glob
import os
import scipy.signal as signal
from scipy.optimize import curve_fit
from filterpy.kalman import KalmanFilter

# ---------------------------------------------------------
# 1. LOAD REAL XJTU-SY EXPERIMENTS
# ---------------------------------------------------------

XJTU_ROOT = os.environ.get('XJTU_ROOT', '/kaggle/input/xjtu-sy-dataset')

def load_xjtu_sy_experiments(xjtu_root=XJTU_ROOT):
    """
    Load all 15 run-to-failure experiments from XJTU-SY.
    Supports both original CSV format and Mendeley Processed .mat format (bearing1.mat - bearing15.mat).
    Returns list of health indicator arrays (one per bearing experiment).
    """
    if not os.path.exists(xjtu_root):
        print(f"CRITICAL: XJTU-SY dataset not found at {xjtu_root}. Skipping RUL prognostics.")
        return []
    
    import scipy.io as sio
    experiments = []
    
    # 1. Try Mendeley Processed .mat format first (originaldata/bearing*.mat)
    mat_dir = os.path.join(xjtu_root, 'originaldata')
    if not os.path.exists(mat_dir): 
        mat_dir = os.path.join(xjtu_root, 'mpn45f4gxc-1', 'originaldata')
        
    if os.path.exists(mat_dir):
        mat_files = sorted(glob.glob(os.path.join(mat_dir, 'bearing*.mat')))
        if mat_files:
            for mat_file in mat_files:
                try:
                    data = sio.loadmat(mat_file)
                    if 'rawnet' in data:
                        rawnet = data['rawnet'] # shape (32768, 2, snapshots)
                        num_snapshots = rawnet.shape[2]
                        hi_values = []
                        # Filter setup
                        b_fir = signal.firwin(65, [180/12800, 290/12800], pass_zero=False)
                        
                        for s in range(num_snapshots):
                            sig = rawnet[:, 0, s] # Channel 0 (horizontal)
                            filtered = signal.lfilter(b_fir, 1.0, sig)[33:]
                            env = np.abs(signal.hilbert(filtered))
                            rms = np.sqrt(np.mean(env**2))
                            hi_values.append(rms)
                        
                        if hi_values:
                            experiments.append(np.array(hi_values))
                except Exception:
                    pass
            if experiments:
                return experiments

    # 2. Fallback to original CSV format
    bearing_dirs = sorted(glob.glob(os.path.join(xjtu_root, 'Bearing*_*')))
    for bearing_dir in bearing_dirs:
        csv_files = sorted(glob.glob(os.path.join(bearing_dir, '*.csv')))
        if not csv_files: continue
        hi_values = []
        for csv_file in csv_files:
            try:
                data = np.loadtxt(csv_file, delimiter=',')
                sig = data[:, 0] if data.ndim > 1 else data
                b_fir = signal.firwin(65, [180/12800, 290/12800], pass_zero=False)
                filtered = signal.lfilter(b_fir, 1.0, sig)[33:]
                env = np.abs(signal.hilbert(filtered))
                rms = np.sqrt(np.mean(env**2))
                hi_values.append(rms)
            except Exception:
                pass
        if hi_values:
            experiments.append(np.array(hi_values))
    return experiments

def exp_degradation(t, a, b):
    return a * np.exp(b * t)

def fit_exp_model_on_experiments(train_exps):
    """
    Bug 3 Fix: Fit population exponential model on REAL XJTU-SY training experiments.
    Normalize time to [0, 1] so coefficients are dataset-agnostic.
    """
    all_t, all_hi = [], []
    for exp in train_exps:
        n = len(exp)
        if n < 10: continue
        norm_hi = exp / (np.max(exp) + 1e-9)
        t_norm = np.arange(n) / n  # [0, 1]
        all_t.extend(t_norm)
        all_hi.extend(norm_hi)
    try:
        popt, _ = curve_fit(exp_degradation, all_t, all_hi, p0=(0.1, 2.0), maxfev=10000)
        return popt[0], popt[1]
    except RuntimeError:
        print("WARNING: Exponential model fit failed. Using safe fallback a=0.1, b=2.0")
        return 0.1, 2.0

# Load all experiments
all_experiments = load_xjtu_sy_experiments()

if len(all_experiments) < 15:
    print(f"WARNING: Only {len(all_experiments)} experiments found. Need ≥15 for full Conformal split.")
    # Use whatever we have — degrade gracefully
    n_total = len(all_experiments)
    n_train  = max(1, int(0.6 * n_total))
    n_calib  = max(1, int(0.2 * n_total))
else:
    n_train, n_calib = 10, 3

train_exps   = all_experiments[:n_train]
calib_exps   = all_experiments[n_train:n_train+n_calib]
holdout_exps = all_experiments[n_train+n_calib:]

# Bug 3 Fix: Fit model on REAL training experiments
a_fit, b_fit = fit_exp_model_on_experiments(train_exps)
print(f"Exponential model fitted on real XJTU-SY: a={a_fit:.4f}, b={b_fit:.4f}")

# Use first training experiment as representative for Kalman demonstration
if train_exps:
    raw_hi = train_exps[0]
    normalized_hi = raw_hi / (np.max(raw_hi) + 1e-9)
else:
    raise RuntimeError("CRITICAL: No XJTU-SY experiments loaded. Ensure dataset is mounted.")

time_steps = np.arange(len(normalized_hi))

# Failure threshold: 3× mean of initial 10% healthy run
failure_threshold = 3.0 * np.mean(normalized_hi[:max(1, int(0.1 * len(normalized_hi)))])

# ---------------------------------------------------------
# 2. KALMAN FILTER STATE ESTIMATOR
# ---------------------------------------------------------
kf = KalmanFilter(dim_x=2, dim_z=1)
kf.x = np.array([normalized_hi[0], 0.])
dt = 1.0
kf.F = np.array([[1., dt], [0., 1.]])
kf.H = np.array([[1., 0.]])
R_var = np.var(normalized_hi[:max(1, int(0.1 * len(normalized_hi)))])
kf.R = np.array([[R_var]])
Q_var = 1e-4
kf.Q = np.array([[Q_var, 0.], [0., Q_var]])

smoothed_hi = []
for z in normalized_hi:
    kf.predict()
    kf.update(z)
    smoothed_hi.append(kf.x[0])
smoothed_hi = np.array(smoothed_hi)

# ---------------------------------------------------------
# 3. EXPONENTIAL EXTRAPOLATION ON CURRENT EXPERIMENT
# ---------------------------------------------------------
current_time = len(smoothed_hi) // 2
t_obs = time_steps[:current_time] / (len(time_steps) + 1e-9)  # normalize like fitting
y_obs = smoothed_hi[:current_time]

try:
    popt_local, _ = curve_fit(exp_degradation, t_obs, y_obs, p0=(a_fit, b_fit), maxfev=5000)
    a_local, b_local = popt_local
except RuntimeError:
    a_local, b_local = a_fit, b_fit

# Map failure threshold to normalized time
if b_local > 0 and a_local > 0:
    T_fail_norm = np.log(failure_threshold / a_local) / b_local
    T_fail = T_fail_norm * len(time_steps)
else:
    T_fail = len(time_steps)

RUL_estimate = T_fail - current_time
if RUL_estimate < 0:
    print(f"CRITICAL: Bearing failure predicted to have occurred {abs(RUL_estimate):.1f} steps ago.")
    print("RUL = 0 (immediate maintenance required).")
    RUL_estimate = 0

# ---------------------------------------------------------
# 4. CONFORMAL PREDICTION (95% COVERAGE)
# ---------------------------------------------------------
print("\n--- XJTU-SY RUL PROGNOSTICS (CONFORMAL) ---")


def compute_true_rul(exp_hi, current_time):
    """True RUL = samples remaining until end of run-to-failure experiment."""
    return len(exp_hi) - current_time

def predict_rul(exp_hi_observed, a_pop, b_pop, failure_threshold_multiplier=3.0):
    """Predict RUL using normalized exponential model."""
    if len(exp_hi_observed) < 5: return 999
    norm = exp_hi_observed / (np.max(exp_hi_observed) + 1e-9)
    initial_mean = np.mean(norm[:max(1, int(0.1 * len(norm)))])
    failure_threshold = failure_threshold_multiplier * initial_mean
    t_obs = np.arange(len(norm)) / (len(norm) + 1e-9)
    try:
        popt, _ = curve_fit(exp_degradation, t_obs, norm, p0=(a_pop, b_pop), maxfev=3000)
        a_l, b_l = popt
    except RuntimeError:
        a_l, b_l = a_pop, b_pop
    if b_l <= 0 or a_l <= 0: return 999
    T_fail_norm = np.log(failure_threshold / a_l) / b_l
    T_fail = T_fail_norm * len(exp_hi_observed)
    return max(0, T_fail - len(exp_hi_observed))

# ---- CONFORMAL PREDICTION — using already-split experiments ----
if len(calib_exps) > 0 and len(holdout_exps) > 0:
    # Per-timestep scoring (30%, 50%, 70% of life) across calibration experiments
    calibration_residuals = []
    for exp in calib_exps:
        n = len(exp)
        for t_frac in [0.3, 0.5, 0.7]:
            t = max(1, int(t_frac * n))
            true_rul = compute_true_rul(exp, t)
            predicted_rul = predict_rul(exp[:t], a_fit, b_fit)
            calibration_residuals.append(abs(true_rul - predicted_rul))

    n_calib = len(calibration_residuals)
    conformal_radius = np.quantile(calibration_residuals, min(1.0, np.ceil((n_calib + 1) * 0.95) / n_calib))
    print(f"Calibrated Conformal Radius: ±{conformal_radius:.2f} time units")

    holdout_residuals = []
    covered = 0
    for exp in holdout_exps:
        n = len(exp)
        for t_frac in [0.3, 0.5, 0.7]:
            t = max(1, int(t_frac * n))
            true_rul = compute_true_rul(exp, t)
            predicted_rul = predict_rul(exp[:t], a_fit, b_fit)
            resid = abs(true_rul - predicted_rul)
            holdout_residuals.append(resid)
            if resid <= conformal_radius:
                covered += 1

    empirical_coverage = covered / max(1, len(holdout_residuals))

    print(f"Current Timestep: {current_time}")
    print(f"Estimated RUL: {RUL_estimate:.2f}")
    print(f"95% Conformal Prediction Interval: [{max(0, RUL_estimate - conformal_radius):.2f}, {RUL_estimate + conformal_radius:.2f}]")
    print(f"Empirical coverage on held-out predictions: {empirical_coverage:.1%} ({covered}/{len(holdout_residuals)})")

    if empirical_coverage >= 0.95:
        print("SUCCESS: 95% Mathematical Guarantee Validated on Holdout Data.")
    else:
        print("WARNING: Coverage Failed (< 95%). Increase calibration set size or widen quantile.")
else:
    print("WARNING: Not enough XJTU-SY experiments to run Conformal Prediction. Need ≥15.")



