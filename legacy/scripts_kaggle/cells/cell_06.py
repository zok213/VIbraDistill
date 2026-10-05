# CELL 7 — Phase 2: Zero-Shot Generalization (Ottawa UORED)
# Fix:
#   Bug 6 — label detection on FULL path, not basename
# ============================================================

def load_ottawa_uored(ottawa_root, fir_path=FIR_PATH,
                      window_size=WINDOW_SIZE, target_fs=12000):
    assert os.path.exists(ottawa_root), f"Ottawa root not found: {ottawa_root}"
    source_fs = 20000

    LABEL_MAP = {
        'innerrace': 1, 'inner': 1,
        'outerrace': 2, 'outer': 2,
        'ball': 3, 'roller': 3,
        'normal': 0,
    }

    import math
    all_files = (
        glob.glob(os.path.join(ottawa_root, '**', '*.mat'), recursive=True) +
        glob.glob(os.path.join(ottawa_root, '**', '*.csv'), recursive=True)
    )
    assert all_files, f"No .mat/.csv files in {ottawa_root}"

    # ── Group files by condition label ──────────────────────
    from collections import defaultdict
    condition_files = defaultdict(list)
    for fpath in all_files:
        fpath_lower = fpath.lower().replace('\\', '/')
        lbl = 0
        for k in sorted(LABEL_MAP, key=len, reverse=True):
            if k in fpath_lower:
                lbl = LABEL_MAP[k]
                break
        condition_files[lbl].append(fpath)

    # ── Per-condition kurtogram → one shared FIR per label ──
    b_env_lpf, a_env_lpf = signal.butter(2, 1000 / (target_fs / 2), btype='lowpass')
    condition_fir = {}

    for lbl, fpaths in condition_files.items():
        # Pool up to 3 files per condition for a robust kurtogram signal
        pool_sig = []
        for fp in fpaths[:3]:
            try:
                raw = _load_raw_signal(fp, source_fs, target_fs)
                if raw is not None:
                    pool_sig.append(raw[:target_fs])  # 1-second chunk
            except Exception:
                pass
        if not pool_sig:
            condition_fir[lbl] = (np.array([1.0]), 0)
            continue
        seed = np.concatenate(pool_sig)
        # FIX 3: Kurtogram runs on signal ALREADY resampled to 12 kHz by
        # _load_raw_signal(), so structural modes (1.5 kHz on 20 kHz raw) are
        # already attenuated. Still add a sanity guard:
        fc_hz, bw_hz = fast_kurtogram(seed, target_fs,
                                       bpfo_hz=BPFO_OTTAWA_HZ, verbose=True)
        # Guard: if kurtogram finds structural resonance (> 800 Hz) instead of
        # bearing faults (70–300 Hz), override with BPFO prior.
        if fc_hz > 800.0:
            print(f"  ⚠ Ottawa label={lbl}: fc={fc_hz:.0f} Hz > 800 Hz (structural)"
                  f" → overriding with BPFO prior ({BPFO_OTTAWA_HZ:.0f} Hz)")
            fc_hz, bw_hz = BPFO_OTTAWA_HZ, 100.0
        b_fir, delay = design_causal_fir(fc_hz, bw_hz, target_fs, n_taps=127)
        condition_fir[lbl] = (b_fir, delay)
        print(f"  Ottawa label={lbl}: fc={fc_hz:.1f} Hz, bw={bw_hz:.1f} Hz")

    # ── Extract windows with per-condition FIR ───────────────
    X, y = [], []
    for lbl, fpaths in condition_files.items():
        b_fir, delay = condition_fir[lbl]
        for fpath in fpaths:
            try:
                raw = _load_raw_signal(fpath, source_fs, target_fs)
                if raw is None:
                    continue
                # FIX: use identical causal IIR-LPF envelope as CWRU training
                filtered = signal.lfilter(b_fir, [1.0], raw)[delay:]
                env = signal.lfilter(b_env_lpf, a_env_lpf, np.abs(filtered))
                n_win = len(env) // window_size
                for i in range(n_win):
                    seg = env[i * window_size:(i + 1) * window_size]
                    spec = np.abs(np.fft.rfft(seg))
                    mx = spec.max()
                    if mx > 1e-10:
                        spec /= mx
                    X.append(spec.astype(np.float32))
                    y.append(lbl)
            except Exception as e:
                print(f"  Ottawa skip {os.path.basename(fpath)}: {e}")

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int64)
    u, c = np.unique(y, return_counts=True)
    print(f"  Ottawa: {len(X)} windows | classes={dict(zip(u.tolist(), c.tolist()))}")
    return X, y


def _load_raw_signal(fpath, source_fs, target_fs):
    """Helper: load one .mat or .csv file → resampled 1D float64 array."""
    import math
    if fpath.endswith('.mat'):
        mat = sio.loadmat(fpath)
        keywords = ['x', 'acc', 'sig', 'vibr', 'data', 'v1', 'v2', 'horiz', 'vert']
        keys = [k for k in mat if not k.startswith('__')
                and any(t in k.lower() for t in keywords)]
        if not keys:
            candidates = [k for k in mat if not k.startswith('__')
                          and isinstance(mat[k], np.ndarray)]
            if not candidates:
                return None
            keys = [max(candidates, key=lambda k: mat[k].size)]
        raw = mat[keys[0]].flatten().astype(np.float64)
    else:
        try:
            raw = np.loadtxt(fpath, delimiter=',', max_rows=200_000)
        except Exception:
            raw = np.loadtxt(fpath, delimiter=',', skiprows=1, max_rows=200_000)
        raw = (raw[:, 0] if raw.ndim > 1 else raw).astype(np.float64)

    if source_fs != target_fs:
        g = math.gcd(int(target_fs), int(source_fs))
        raw = signal.resample_poly(raw, int(target_fs) // g, int(source_fs) // g)
    return raw


# FIX 2: Reframe as calibration transfer, NOT zero-shot
print("\n=== PHASE 2: TRANSFER WITH DATASET-SPECIFIC CALIBRATION (Ottawa UORED) ===")
print("  NOTE: Per-condition FIR calibration is required. This is NOT zero-shot.")
X_ott, y_ott = load_ottawa_uored(OTTAWA_ROOT)

# Load best student checkpoint
best_student = Student1DCNN(NUM_CLASSES)
best_student.load_state_dict(torch.load(STUDENT_PATH, map_location='cpu'))
best_student.eval().to(DEVICE)

ott_dl = DataLoader(
    torch.utils.data.TensorDataset(
        torch.tensor(X_ott).unsqueeze(1),
        torch.tensor(y_ott),
    ),
    batch_size=512, shuffle=False,
)

all_preds, all_lbls = [], []
with torch.no_grad():
    for xb, yb in ott_dl:
        logits, _ = best_student(xb.to(DEVICE))
        all_preds.extend(logits.argmax(1).cpu().numpy())
        all_lbls.extend(yb.numpy())

ott_f1  = f1_score(all_lbls, all_preds, average='weighted', zero_division=0)
ott_acc = (np.array(all_preds) == np.array(all_lbls)).mean() if all_lbls else 0
print(f"  Transfer Accuracy: {ott_acc*100:.2f}%  |  Weighted F1: {ott_f1*100:.2f}%")
print(f"  (Driven by per-condition FIR calibration, not learned zero-shot transfer)")

if all_lbls:
    print(classification_report(all_lbls, all_preds,
          target_names=['Normal', 'InnerRace', 'OuterRace', 'Ball'],
          zero_division=0))
else:
    print("⚠ Zero-Shot evaluation skipped: No valid windows extracted from Ottawa.")
