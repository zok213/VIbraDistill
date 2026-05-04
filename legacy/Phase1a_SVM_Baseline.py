"""
PHASE 1A: SVM BASELINE (ZERO-LEAKAGE)
Target: 75-85% F1 on CWRU. Train on loads 0+1 HP, Test on loads 2+3 HP.
"""

from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score
import numpy as np

def extract_features(envelope_spectrum):
    """
    Extract 4 engineered features from the 257-bin envelope spectrum.
    Bug 5 Fix: BPFO bin must be computed from frequency resolution.
      fs=12000, window=512 → 257 bins → hz_per_bin = 6000/256 ≈ 23.4 Hz/bin
      BPFO_HZ = 105 Hz → bin index = round(105/23.4) = round(4.49) = 4
      NOT bin 105 (which maps to ~2461 Hz — completely off)
    """
    rms = np.sqrt(np.mean(envelope_spectrum**2))
    kurtosis_val = np.mean((envelope_spectrum - np.mean(envelope_spectrum))**4) / (np.var(envelope_spectrum)**2 + 1e-7)
    crest_factor = np.max(np.abs(envelope_spectrum)) / (rms + 1e-7)
    
    # Correct BPFO bin: SKF 6205-2RS @ ~105 Hz, fs=12000, N=512 (257 bins)
    FS = 12000
    WINDOW_SIZE = 512
    SPECTRUM_BINS = WINDOW_SIZE // 2 + 1  # = 257
    hz_per_bin = (FS / 2) / (SPECTRUM_BINS - 1)  # = 23.4375 Hz/bin
    BPFO_HZ = 105.0
    bpfo_idx = int(round(BPFO_HZ / hz_per_bin))  # = 4
    
    # Sum fundamental + 2nd + 3rd harmonics for richer BPFO feature
    n = len(envelope_spectrum)
    bpfo_amp = (
        envelope_spectrum[min(bpfo_idx, n-1)] +
        envelope_spectrum[min(bpfo_idx*2, n-1)] +
        envelope_spectrum[min(bpfo_idx*3, n-1)]
    ) / 3.0
    
    return [rms, kurtosis_val, crest_factor, bpfo_amp]

print("Extracting features (RMS, Kurtosis, Crest Factor, BPFO) for Loads 0+1 vs 2+3...")
try:
    X_train_features, y_train = [], []
    for xb, yb in train_dl:
        for i in range(xb.shape[0]):
            X_train_features.append(extract_features(xb[i].numpy().flatten()))
            y_train.append(yb[i].item())
            
    X_test_features, y_test = [], []
    for xb, yb in test_dl:
        for i in range(xb.shape[0]):
            X_test_features.append(extract_features(xb[i].numpy().flatten()))
            y_test.append(yb[i].item())
except NameError:
    raise RuntimeError("CRITICAL: train_dl or test_dl not found. Ensure dataloaders are initialized.")

print("Scaling features...")
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train_features)
X_test_scaled = scaler.transform(X_test_features)

print("Training RBF SVM Baseline...")
svm = SVC(kernel='rbf', C=10, gamma='scale', class_weight='balanced')
svm.fit(X_train_scaled, y_train)

print("Evaluating SVM on highly-shifted test loads (2+3 HP)...")
preds = svm.predict(X_test_scaled)
svm_f1 = f1_score(y_test, preds, average='weighted')

print(f"SVM Baseline F1 Score: {svm_f1:.3f}")
if svm_f1 < 0.70:
    print("Warning: F1 below 70%. Feature engineering (DSP) requires revisiting.")
else:
    print("Baseline successfully established. Proceed to 1D-CNN DKD Training.")
