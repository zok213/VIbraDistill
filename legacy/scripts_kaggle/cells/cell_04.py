# CELL 5 — Teacher Pretraining (CWT + EfficientNetB0)
# Fixes (vs original):
#   Bug 3 — precompute iterates dataset.raw_windows by index (no DataLoader)
#   Bug 5 — ImageNet normalisation applied
#   NEW A  — CWT computed on filtered TIME-DOMAIN windows, not spectrum
#             (spectrum CWT has no physical meaning for fault diagnosis)
#   NEW B  — Stratified train/val split for CWTCacheDataset
#   NEW C  — Label smoothing in teacher CrossEntropyLoss
# ============================================================

def generate_cwt_scalogram(raw_window_512, fs=FS, n_scales=64):
    """
    Morlet CWT on a 512-sample filtered vibration window (time-domain).
    Uses geometrically spaced scales covering the fault-frequency band.

    Args:
        raw_window_512: (512,) float32 — causal filtered time-domain signal
    Returns:
        (3, 224, 224) float32 — ImageNet-normalised scalogram
    """
    # Geometric scale spacing: better frequency resolution at low frequencies
    scales    = np.geomspace(1, n_scales, num=n_scales)
    coeffs, _ = pywt.cwt(
        raw_window_512.astype(np.float64), scales, 'morl',
        sampling_period=1.0 / fs,
    )
    img = np.abs(coeffs).astype(np.float32)   # (64, 512)
    mx  = img.max()
    if mx > 0:
        img /= mx   # → [0, 1]

    # Resize (64, 512) → (3, 224, 224) via bilinear interpolation
    t    = torch.tensor(img).unsqueeze(0).unsqueeze(0)    # (1,1,64,512)
    t    = F.interpolate(t, size=(IMG_SIZE, IMG_SIZE),
                         mode='bilinear', align_corners=False)
    img3 = t.squeeze(0).repeat(3, 1, 1)                  # (3,224,224) ∈ [0,1]

    # Fix Bug 5: ImageNet normalisation — required for pretrained EfficientNetB0
    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std  = torch.tensor(IMAGENET_STD).view(3, 1, 1)
    img3 = (img3 - mean) / std

    return img3.numpy()   # (3, 224, 224)


def precompute_cwt(dataset, feat_path, lbl_path):
    """
    Precompute CWT scalograms from dataset.raw_windows (filtered time-domain).

    Fix Bug 3: iterates by INTEGER INDEX — never through a shuffled DataLoader.
    This guarantees CWT[i] aligns with dataset.windows[i] and dataset.labels[i],
    which is the invariant PairedDKDDataset.validate_alignment() checks.
    """
    n = len(dataset)

    if os.path.exists(feat_path) and os.path.exists(lbl_path):
        cached_n = np.load(feat_path, mmap_mode='r').shape[0]
        if cached_n == n:
            print(f"✓ CWT cache valid ({cached_n} scalograms) — skipping")
            return
        print(f"⚠ CWT cache size mismatch ({cached_n} vs {n}) — recomputing")

    print(f"--- PRECOMPUTING {n} CWT SCALOGRAMS (from time-domain windows) ---")
    all_cwts, all_lbls = [], []

    for i in tqdm(range(n), desc='CWT', unit='win'):
        # Fix A: use raw_windows (time-domain), NOT windows (spectrum)
        raw_win = dataset.raw_windows[i]          # (512,) filtered signal
        all_cwts.append(generate_cwt_scalogram(raw_win, fs=FS))
        all_lbls.append(int(dataset.labels[i]))

    arr = np.array(all_cwts, dtype=np.float32)
    np.save(feat_path, arr)
    np.save(lbl_path,  np.array(all_lbls, dtype=np.int64))
    print(f"✓ CWT cache saved: {feat_path}  shape={arr.shape}")


class CWTCacheDataset(Dataset):
    """
    Stratified train / val split over precomputed CWT scalograms.
    Fix B: stratified split (not random permutation) to keep class balance.
    """
    def __init__(self, feat_path, lbl_path, val_split=0.2, mode='train', seed=42):
        self.feats = np.load(feat_path, mmap_mode='r')   # (N, 3, 224, 224)
        labels = np.load(lbl_path)    # (N,)
        N      = len(labels)

        sss = StratifiedShuffleSplit(n_splits=1, test_size=val_split,
                                     random_state=seed)
        tr_idx, va_idx = next(sss.split(np.zeros(N), labels))
        self.chosen_idx = tr_idx if mode == 'train' else va_idx

        self.labels = labels[self.chosen_idx]
        print(f"  CWTCacheDataset [{mode}]: {len(self.chosen_idx)} samples")

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        real_idx = self.chosen_idx[idx]
        return (
            torch.tensor(self.feats[real_idx]),
            torch.tensor(self.labels[idx], dtype=torch.long),
        )


def train_teacher(epochs=30, batch_size=256, lr=1e-4, force_train=False):
    print("\n=== PHASE 1B: TEACHER PRETRAINING (EfficientNetB0 on CWT) ===")
    
    if recover_from_wandb(TEACHER_PATH) and not force_train:
        print(f"✓ Teacher model found (local or W&B) at {TEACHER_PATH}")
        return

    assert os.path.exists(CWT_FEAT_PATH), "Run precompute_cwt() first."

    tr_ds = CWTCacheDataset(CWT_FEAT_PATH, CWT_LBL_PATH, mode='train')
    va_ds = CWTCacheDataset(CWT_FEAT_PATH, CWT_LBL_PATH, mode='val')
    tr_dl = DataLoader(tr_ds, batch_size=batch_size, shuffle=True,
                       num_workers=4, pin_memory=True)
    va_dl = DataLoader(va_ds, batch_size=batch_size, shuffle=False,
                       num_workers=4, pin_memory=True)

    weights  = models.EfficientNet_B0_Weights.DEFAULT
    teacher  = models.efficientnet_b0(weights=weights)
    teacher.classifier[1] = nn.Linear(teacher.classifier[1].in_features, NUM_CLASSES)
    if torch.cuda.device_count() > 1:
        print(f"  DataParallel × {torch.cuda.device_count()} GPUs")
        teacher = nn.DataParallel(teacher)
    teacher = teacher.to(DEVICE)

    optimizer = torch.optim.AdamW(teacher.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    # Fix C: label smoothing → softer teacher targets during distillation
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    best_acc  = 0.0

    wandb.init(project='bfd-dkd-edge', name='teacher_pretrain', reinit=True)

    for epoch in range(epochs):
        teacher.train()
        tr_loss = tr_corr = tr_tot = 0
        for xb, yb in tr_dl:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            out  = teacher(xb)
            loss = criterion(out, yb)
            loss.backward()
            optimizer.step()
            tr_loss += loss.item() * xb.size(0)
            tr_corr += (out.argmax(1) == yb).sum().item()
            tr_tot  += xb.size(0)
        scheduler.step()

        teacher.eval()
        va_corr = va_tot = 0
        with torch.no_grad():
            for xb, yb in va_dl:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                out      = teacher(xb)
                va_corr += (out.argmax(1) == yb).sum().item()
                va_tot  += xb.size(0)

        tr_acc  = 100 * tr_corr / tr_tot
        val_acc = 100 * va_corr / va_tot
        wandb.log({'teacher_train_acc': tr_acc, 'teacher_val_acc': val_acc,
                   'teacher_loss': tr_loss / tr_tot, 'epoch': epoch})

        if (epoch + 1) % 5 == 0:
            print(f"  Ep {epoch+1:02d}/{epochs} | loss={tr_loss/tr_tot:.4f} "
                  f"| train={tr_acc:.1f}% | val={val_acc:.1f}%")

        if val_acc > best_acc:
            best_acc = val_acc
            m = teacher.module if isinstance(teacher, nn.DataParallel) else teacher
            torch.save(m.state_dict(), TEACHER_PATH)

    wandb.save(TEACHER_PATH)
    wandb.finish()
    print(f"✓ Teacher saved  —  best val acc: {best_acc:.2f}%")


# Fix Bug 3: pass DATASET OBJECT, not a DataLoader
precompute_cwt(train_dataset, CWT_FEAT_PATH, CWT_LBL_PATH)
train_teacher(epochs=30, batch_size=256, lr=1e-4)
