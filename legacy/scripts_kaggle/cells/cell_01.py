# CELL 2 — Phase 0: Causal DSP Front-End
# Fast Kurtogram → resonance band → minimum-phase FIR → save
# STRICT: lfilter only. No filtfilt anywhere in the pipeline.
# ============================================================

# Dataset-specific BPFO constants (add near global constants)
BPFO_OTTAWA_HZ = 106.4   # LDK-UER204 @ 2100 RPM
BPFO_XJTU_HZ   = 106.4   # same bearing @ 2100 RPM

def fast_kurtogram(sig, fs, n_levels=6, bpfo_hz=None, verbose=False):
    """
    Spectral kurtosis kurtogram via STFT sub-bands.
    bpfo_hz: dataset-specific BPFO for the K<1 fallback (default: CWRU).
    """
    if bpfo_hz is None:
        try:
            bpfo_hz = BPFO_HZ  # existing CWRU default
        except NameError:
            bpfo_hz = 107.4

    import scipy.signal as signal
    nperseg = min(256, len(sig) // 4)
    # Expert Fix (Audit V6): boundary=None, padded=False is the only truly causal STFT.
    f, t_arr, Zxx = signal.stft(sig, fs=fs, nperseg=nperseg,
                                noverlap=nperseg // 2, boundary=None, padded=False)
    Zxx  = Zxx[:, 1:]
    power = np.abs(Zxx) ** 2

    best_k  = -np.inf
    best_fc = bpfo_hz          # ← dataset-specific default
    best_bw = 500.0

    for level in range(1, n_levels + 1):
        bw = fs / (2 ** (level + 1))
        if bw < 50:
            break
        n_bands = int(fs / 2 / bw)
        for bi in range(n_bands):
            f_lo = bw * bi
            f_hi = f_lo + bw
            mask = (f >= f_lo) & (f < f_hi)
            if mask.sum() < 2:
                continue
            bp = power[mask, :].sum(axis=0)
            mu = bp.mean()
            if mu < 1e-12:
                continue
            kurt = ((bp - mu) ** 4).mean() / (mu ** 2) - 3.0
            if kurt > best_k:
                best_k  = kurt
                best_fc = bw * (bi + 0.5)
                best_bw = bw

    if best_k < 1.0:
        # FIX: use dataset-specific BPFO, not CWRU 2500 Hz
        best_fc = float(bpfo_hz)
        best_bw = 500.0
        if verbose:
            print(f"  ⚠ Low K={best_k:.2f} → fallback fc={best_fc:.1f} Hz (dataset BPFO)")
    elif verbose:
        print(f"  Kurtogram: fc={best_fc:.1f} Hz, bw={best_bw:.1f} Hz, K={best_k:.2f}")

    return best_fc, best_bw


def design_causal_fir(fc_hz, bw_hz, fs, n_taps=127):
    """
    Bandpass minimum-phase FIR via Parks-McClellan prototype + homomorphic conversion.
    Returns (b_min_phase, group_delay_samples).
    """
    nyq   = fs / 2
    lo_n  = float(np.clip((fc_hz - bw_hz / 2) / nyq, 0.001, 0.999))
    hi_n  = float(np.clip((fc_hz + bw_hz / 2) / nyq, 0.001, 0.999))
    if hi_n <= lo_n + 0.001:
        hi_n = min(lo_n + 0.05, 0.999)

    b_proto = signal.firwin(n_taps, [lo_n, hi_n], pass_zero=False)
    b_min   = signal.minimum_phase(b_proto, method='homomorphic')
    return b_min, len(b_min) // 2


def run_phase0(seed_signal=None, save_path=FIR_PATH):
    """Phase 0 entry point. Returns b_fir array."""
    print("=== PHASE 0: Causal DSP Front-End ===")
    if seed_signal is not None:
        fc_hz, bw_hz = fast_kurtogram(seed_signal, FS, verbose=True)
    else:
        fc_hz, bw_hz = BPFO_HZ, 500.0
        print(f"  No seed signal — default fc={fc_hz} Hz, bw={bw_hz} Hz")

    b_fir, delay = design_causal_fir(fc_hz, bw_hz, FS, n_taps=127)
    np.save(save_path, b_fir)
    print(f"  FIR: {len(b_fir)} taps, delay={delay}  →  {save_path}")

    w, h = signal.freqz(b_fir, worN=2048, fs=FS)
    plt.figure(figsize=(7, 3))
    plt.plot(w, 20 * np.log10(np.abs(h) + 1e-10))
    plt.axvline(fc_hz, color='r', ls='--', label=f'fc={fc_hz:.0f} Hz')
    plt.xlabel('Hz'); plt.ylabel('dB')
    plt.title('Minimum-Phase Causal FIR')
    plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(WORK_DIR, 'fir_response.png'), dpi=100)
    plt.close()
    return b_fir


# Seed kurtogram with a real CWRU normal segment if available
_seed = None
_cands = glob.glob(os.path.join(CWRU_ROOT, '**', '97.mat'), recursive=True)
if _cands:
    try:
        _m   = sio.loadmat(_cands[0])
        _key = next((k for k in _m if 'DE_time' in k), None)
        if _key:
            _seed = _m[_key].flatten().astype(np.float64)[:12000]
    except Exception:
        pass

b_fir_global = run_phase0(seed_signal=_seed)
