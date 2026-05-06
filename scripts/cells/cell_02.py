# CELL 3 — CWRU Bearing Dataset
# Fixes (vs original):
#   Bug 1  — _get_label: searches FULL path, not os.path.basename
#   Bug 2  — LABEL_MAP: unambiguous keys, longest-first priority
#   Bug 12 — severity filter: no empty strings; zero-padded variants added
#   NEW A  — load_conditions actually filters HP-load directory tokens
#   NEW B  — Normal baseline includes 100.mat (load-3); not just 97-99
#   NEW C  — raw_windows (filtered time-domain) stored alongside spectra
#             so CWT is computed on physically meaningful time-domain data
# ============================================================

class CWRUBearingDataset(Dataset):
    """
    Loads CWRU .mat files, applies causal minimum-phase FIR, stores:
      - self.windows     (N, 257) float32 — envelope spectra  → Student input
      - self.raw_windows (N, 512) float32 — filtered signal   → Teacher CWT input
      - self.labels      (N,)    int64

    Labels: 0=Normal, 1=InnerRace, 2=OuterRace, 3=Ball

    Supports both common CWRU Kaggle layout variants:
      Flat:   <root>/InnerRace_007_0HP/105.mat
      Nested: <root>/12k/0HP/InnerRace/007/105.mat
    """

    # Keys sorted longest-first so 'outerrace' is matched before 'outer', etc.
    LABEL_MAP = {
        'innerrace': 1,
        'inner':     1,
        'outerrace': 2,
        'outer':     2,
        'ball':      3,
        'roller':    3,
        'normal':    0,
    }

    # CWRU HP-load directory tokens  (0=0HP, 1=1HP, ...)
    _HP_TOKENS = {
        0: ['0hp', '_0_', '/0/'],
        1: ['1hp', '_1_', '/1/'],
        2: ['2hp', '_2_', '/2/'],
        3: ['3hp', '_3_', '/3/'],
    }

    # Fix B: all four CWRU normal baseline file stems (one per load condition)
    _NORMAL_STEMS = {'97', '98', '99', '100'}

    def __init__(self, cwru_root, load_conditions, severities,
                 fir_coeffs_path=FIR_PATH, window_size=WINDOW_SIZE, min_files=100):
        assert os.path.exists(cwru_root), f"CWRU root not found: {cwru_root}"
        self.window_size = window_size
        self.bins        = window_size // 2 + 1

        self.b_fir = (np.load(fir_coeffs_path)
                      if os.path.exists(fir_coeffs_path)
                      else np.array([1.0]))
        self._delay = (len(self.b_fir) - 1) // 2

        # Precompute Envelope Lowpass Filter once
        self.b_env, self.a_env = signal.butter(2, 1000 / (FS / 2), btype='lowpass')

        self.windows     = []   # (257,) envelope magnitude spectra
        self.raw_windows = []   # (512,) causal filtered time-domain windows
        self.labels      = []

        self._load_all(cwru_root, load_conditions, severities)

        assert len(self.windows) >= min_files, (
            f"Only {len(self.windows)} windows loaded — "
            f"check load_conditions={load_conditions}, severities={severities}."
        )

        self.windows     = np.array(self.windows,     dtype=np.float32)
        self.raw_windows = np.array(self.raw_windows, dtype=np.float32)
        self.labels      = np.array(self.labels,      dtype=np.int64)

        unique, counts = np.unique(self.labels, return_counts=True)
        print(f"  Dataset: {len(self.windows)} windows | "
              f"classes={dict(zip(unique.tolist(), counts.tolist()))}")

        if len(unique) < 2:
            raise ValueError(
                f"Only class {unique.tolist()} loaded — "
                "fault keywords not found in file paths. "
                "Print a few paths from _load_all and verify directory names."
            )

    def _get_label(self, filepath):
        # Fix 1: search FULL lowercased path, not just the file's basename
        fpath = filepath.lower().replace('\\', '/')
        for k in sorted(self.LABEL_MAP, key=len, reverse=True):
            if k in fpath:
                return self.LABEL_MAP[k]
        return 0

    def _matches_load_condition(self, fpath_lower, load_conditions):
        """Returns True if the file's path contains a token for any requested HP load."""
        if not load_conditions:
            return True
        # Check whether ANY hp token appears anywhere in this dataset
        any_hp = any(
            tok in fpath_lower
            for lc_toks in self._HP_TOKENS.values()
            for tok in lc_toks
        )
        if not any_hp:
            # Dataset has no HP encoding in paths — accept all files
            return True
        for lc in load_conditions:
            if any(tok in fpath_lower for tok in self._HP_TOKENS.get(lc, [])):
                return True
        return False

    def _load_all(self, cwru_root, load_conditions, severities):
        mat_files = sorted(
            glob.glob(os.path.join(cwru_root, '**', '*.mat'), recursive=True)
        )
        assert mat_files, f"No .mat files in {cwru_root}"

        # Fix 12: build clean severity set; no empty strings
        # Add zero-padded variants: '7' → {'7', '007'}
        clean_sev = set()
        for s in severities:
            s = str(s).strip().lower()
            if s in ('', 'none'):
                continue
            s = s.replace('-mil', '').replace('mil', '')
            clean_sev.add(s)
            try:
                clean_sev.add(f'{int(s):03d}')   # zero-padded, e.g. '007'
            except ValueError:
                pass

        loaded = skipped_lc = skipped_sev = skipped_key = 0

        for fpath in mat_files:
            fpath_lower = fpath.lower().replace('\\', '/')
            stem        = os.path.splitext(os.path.basename(fpath))[0]

            # Fix A: apply load condition filter
            if not self._matches_load_condition(fpath_lower, load_conditions):
                skipped_lc += 1
                continue

            # Severity filter — normal baselines always pass
            is_normal = stem in self._NORMAL_STEMS
            if not is_normal and clean_sev:
                if not any(sv in fpath_lower for sv in clean_sev):
                    skipped_sev += 1
                    continue

            try:
                mat  = sio.loadmat(fpath)
                keys = [k for k in mat if 'DE_time' in k]
                if not keys:
                    skipped_key += 1
                    continue

                raw = mat[keys[0]].flatten().astype(np.float64)
                lbl = self._get_label(fpath)

                # Causal minimum-phase FIR — lfilter only, never filtfilt
                filtered = signal.lfilter(self.b_fir, [1.0], raw)
                filtered = filtered[self._delay:]   # trim group-delay transient

                # True Causal Envelope (Full-wave rectification + IIR LPF)
                # Replaces non-causal signal.hilbert() which uses full-array FFT
                env = signal.lfilter(self.b_env, self.a_env, np.abs(filtered))
                n_win = len(env) // self.window_size


                for i in range(n_win):
                    sl      = slice(i * self.window_size, (i + 1) * self.window_size)
                    raw_seg = filtered[sl].astype(np.float32)   # time-domain → CWT
                    env_seg = env[sl]

                    spec = np.abs(np.fft.rfft(env_seg))   # 257 bins
                    mx   = spec.max()
                    if mx > 1e-10:
                        spec /= mx

                    self.windows.append(spec.astype(np.float32))
                    self.raw_windows.append(raw_seg)
                    self.labels.append(lbl)

                loaded += 1

            except Exception as e:
                print(f"  Skip {os.path.basename(fpath)}: {e}")

        print(f"  Parsed {loaded}/{len(mat_files)} files "
              f"(skipped: lc={skipped_lc}, sev={skipped_sev}, key={skipped_key})")

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        x = torch.tensor(self.windows[idx]).unsqueeze(0)   # (1, 257)
        return x, torch.tensor(self.labels[idx])


print("Building CWRU DataLoaders (Strict Severity Isolation)...")
# EXPERT: Zero-Leakage Experiment Design
# Train on 7-mil faults only (0-1HP). Test on 14/21-mil faults (2-3HP).
# This enforces cross-severity and cross-load generalization.
train_dataset = CWRUBearingDataset(
    CWRU_ROOT, load_conditions=[0, 1], severities=['7'],
    fir_coeffs_path=FIR_PATH, min_files=100,
)
test_dataset = CWRUBearingDataset(
    CWRU_ROOT, load_conditions=[2, 3], severities=['14', '21'],
    fir_coeffs_path=FIR_PATH, min_files=50,
)

train_dl = DataLoader(train_dataset, batch_size=512, shuffle=True,
                      num_workers=4, pin_memory=True)
test_dl  = DataLoader(test_dataset,  batch_size=512, shuffle=False,
                      num_workers=4, pin_memory=True)
print(f"✓ Train: {len(train_dataset)} samples  |  Test: {len(test_dataset)} samples")
