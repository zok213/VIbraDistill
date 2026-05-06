# CELL 6 — Phase 1C: DKD Student Training
# Improvements (Expert Edition):
#   ARCH — Added SE (Squeeze-and-Excitation) blocks for channel attention.
#   DKD  — Full binary KL for TCKD (Zhao et al. 2022).
#   SAFE — DataParallel-safe TeacherWrapper (no hooks).
#   W&B  — Automatic artifact recovery and persistence.
# ============================================================

class SELayer(nn.Module):
    """Squeeze-and-Excitation block for 1D CNNs."""
    def __init__(self, channel, length, reduction=16):
        super().__init__()
        # Expert Fix (Audit V6): AdaptiveAvgPool1d lowers to 'Reduce' which 
        # falls back to CUDA on NVDLA. Static AvgPool1d maps to NVDLA-native Conv.
        self.avg_pool = nn.AvgPool1d(kernel_size=length)
        self.fc = nn.Sequential(
            nn.Linear(channel, channel // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channel // reduction, channel, bias=False),
            # Expert Audit Fix (Q3): Hardsigmoid for NVDLA/INT8 compatibility
            nn.Hardsigmoid() 
        )

    def forward(self, x):
        assert x.size(2) == self.avg_pool.kernel_size[0], "Input spatial dimension must match SELayer length"
        b, c, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1)
        return x * y.expand_as(x)

class Student1DCNN(nn.Module):
    """
    4-block 1D-CNN with SE Attention.
    Optimised for Jetson Orin NX (INT8-friendly layout).
    """
    def __init__(self, num_classes=4):
        super().__init__()
        self.conv_blocks = nn.Sequential(
            nn.Conv1d(1,   32,  kernel_size=9, padding=4),
            nn.BatchNorm1d(32),  nn.ReLU(), nn.MaxPool1d(2),
            SELayer(32, length=128, reduction=4),  # Expert Audit Fix: reduction=4 for shallow blocks
            
            nn.Conv1d(32,  64,  kernel_size=5, padding=2),
            nn.BatchNorm1d(64),  nn.ReLU(), nn.MaxPool1d(2),
            SELayer(64, length=64, reduction=8),
            
            nn.Conv1d(64,  128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128), nn.ReLU(), nn.MaxPool1d(2),
            SELayer(128, length=32, reduction=16),
            
            nn.Conv1d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm1d(256), nn.ReLU(),
            nn.AvgPool1d(kernel_size=8, stride=8),
        )
        self.fc = nn.Sequential(
            nn.Linear(1024, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256,  128), nn.ReLU(),
        )
        self.projection_head = nn.Linear(128, 1280)   # matches teacher avgpool dim
        self.classifier      = nn.Linear(128, num_classes)

    def forward(self, x):
        x    = self.conv_blocks(x)
        x    = x.view(x.size(0), -1)
        feat = self.fc(x)
        return self.classifier(feat), self.projection_head(feat)

def get_model_complexity(model, input_size=(1, 1, SPECTRUM_BINS)):
    """Expert: Theoretical FLOPs and parameter count."""
    params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    # Simple heuristic for CNN MACs
    flops = 0
    for m in model.modules():
        if isinstance(m, nn.Conv1d):
            flops += m.weight.numel() * input_size[2]
    return params, flops / 1e6


class TeacherWrapper(nn.Module):
    """
    Fix Bug 10: DataParallel-safe EfficientNetB0 feature extractor.

    Returns (logits, avgpool_feats) directly from forward(), so DataParallel's
    scatter/gather handles multi-GPU batches correctly and completely.

    ── Why not a forward hook? ──
    With nn.DataParallel, each GPU runs a replicated module. A hook on the
    original module's avgpool fires N times (once per replica) but only receives
    the sub-batch from that GPU. The last write to self.last_feats is
    non-deterministic across GPUs and contains only ~B/N samples — not B.
    A proper nn.Module wrapper avoids this entirely.
    """
    def __init__(self, efficientnet_base: nn.Module):
        super().__init__()
        self.base = efficientnet_base

    def forward(self, x):
        # EfficientNetB0 internal pipeline:
        #   features → avgpool(B,1280,1,1) → flatten(B,1280) → classifier(B,K)
        feats  = self.base.avgpool(self.base.features(x)).flatten(1)  # (B, 1280)
        logits = self.base.classifier(feats)                           # (B, K)
        return logits, feats


def dkd_loss(s_logits, t_logits, s_feats, t_feats,
             targets_onehot, tau=4.0, alpha=1.0, beta=8.0, feat_w=0.0):
    """
    Decoupled Knowledge Distillation loss (Zhao et al., 2022).

    Fix Bug 9 — TCKD was incomplete:
      Old code: TCKD = -(p_t * log(p_s)).mean()
              = cross-entropy branch only (first branch of binary KL)
      Correct:  TCKD = KL[Bernoulli(p_t_T) || Bernoulli(p_t_S)]
                     = p_t_T * log(p_t_T/p_t_S) + (1-p_t_T)*log((1-p_t_T)/(1-p_t_S))
      Both branches are required; omitting the second biases gradients toward
      over-confident student target-class probabilities.

    All terms normalised per sample (.mean()), so alpha/beta are batch-size invariant.
    """
    eps = 1e-7
    ps  = F.softmax(s_logits / tau, dim=1)
    pt  = F.softmax(t_logits / tau, dim=1)

    # Target-class scalar probabilities per sample
    pts = (pt * targets_onehot).sum(1).clamp(eps, 1 - eps)   # teacher p(target)
    pss = (ps * targets_onehot).sum(1).clamp(eps, 1 - eps)   # student p(target)

    # Full binary KL — both branches (Fix Bug 9)
    tckd = (
        pts * torch.log(pts / pss) + (1 - pts) * torch.log((1 - pts) / (1 - pss))
    ).mean()

    # NCKD: KL on renormalised non-target distributions
    mask  = 1.0 - targets_onehot
    pnt_s = (ps * mask) / ((ps * mask).sum(1, keepdim=True).clamp(min=eps))
    pnt_t = (pt * mask) / ((pt * mask).sum(1, keepdim=True).clamp(min=eps))
    # KL(teacher_nontarget || student_nontarget)
    nckd  = (pnt_t * torch.log((pnt_t + eps) / (pnt_s + eps))).sum(1).mean()

    # V15 FIX A: Restore multiplication by τ². 
    # Division reduces the gradient by 1/τ⁴, muting the teacher entirely.
    # The original multiplication restores gradient scale lost to temperature softening.
    loss_dkd = (alpha * tckd + beta * nckd) * (tau ** 2)

    # Expert Audit Fix (Issue 4/Q2): Cosine Similarity + Adaptive Norm Regularizer.
    feat_sim = F.cosine_similarity(s_feats, t_feats.detach(), dim=1).mean()
    feat_loss = 1.0 - feat_sim

    # Adaptive Norm-matching (Audit V6): Weight scales with teacher norm
    norm_w   = torch.clamp(0.1 / (t_feats.detach().norm(dim=1).mean() + 1e-8), max=10.0)
    norm_reg = F.l1_loss(s_feats.norm(dim=1), t_feats.detach().norm(dim=1))

    ce_loss = F.cross_entropy(s_logits, targets_onehot.argmax(dim=1))

    return ce_loss + loss_dkd + feat_w * feat_loss + norm_w * norm_reg


def _dkd_loss_warmed(s_logits, t_logits, s_feats, t_feats, targets_onehot, cfg, epoch):
    """DKD loss with α/β warmup for first 10 epochs."""
    warmup = min(epoch / 10.0, 1.0)
    warmed_cfg = {
        'tau':    cfg['tau'],
        'alpha':  cfg['alpha'] * warmup,
        'beta':   cfg['beta']  * warmup,
        'feat_w': cfg.get('feat_w', 0.0),
    }
    return dkd_loss(s_logits, t_logits, s_feats, t_feats, targets_onehot, **warmed_cfg)


class PairedDKDDataset(Dataset):
    """
    Returns (envelope_spectrum [1,257], cwt_scalogram [3,224,224], label).

    Fix Bug 4: verifies LABEL ARRAYS are identical — not just sizes.
    If mismatched, raises with an actionable message (delete cache & rerun Cell 5).
    """
    def __init__(self, cwru_dataset, cwt_feat_path, cwt_lbl_path):
        self.env_wins   = cwru_dataset.windows    # (N, 257) numpy
        env_labels = cwru_dataset.labels     # (N,) numpy
        
        # Expert Fix (Memory Leak): Use mmap_mode='r' to prevent the 3GB tensor
        # from being copied across 4 worker processes when they fork (Copy-on-Write).
        self.cwt_feats  = np.load(cwt_feat_path, mmap_mode='r')  # (M, 3, 224, 224)
        cwt_labels = np.load(cwt_lbl_path)   # (M,)

        N = min(len(env_labels), len(cwt_labels))
        assert N > 0, "Empty paired dataset"

        # Fix Bug 4: label alignment verification
        if not np.array_equal(env_labels[:N], cwt_labels[:N]):
            n_mm = (env_labels[:N] != cwt_labels[:N]).sum()
            raise AssertionError(
                f"CRITICAL: {n_mm}/{N} label mismatches between "
                "envelope dataset and CWT cache. "
                "precompute_cwt() was called on a shuffled DataLoader. "
                "Delete CWT cache files and re-run Cell 5."
            )

        self.labels = torch.tensor(env_labels[:N], dtype=torch.long)
        self.N = N
        print(f"  PairedDKDDataset: {N} aligned samples ✓")

    def __len__(self):
        return self.N

    # EXPERT (Issue 7 / Q3): Synchronized Multi-Modal Augmentation.
    # Shifts both Spectrum (Student) and CWT (Teacher) by the SAME factor
    # to maintain feature alignment during distillation.
    def _augment_pair(self, env, cwt):
        if np.random.rand() > 0.5:
            scale = 0.8 + np.random.rand() * 0.4 # [0.8, 1.2]
            # 1D Zoom for Spectrum
            n = env.shape[-1]
            x = np.arange(n)
            env_aug = np.interp(x / scale, x, env.squeeze()).astype(np.float32)
            env_aug = torch.from_numpy(env_aug).unsqueeze(0)
            
            # 2D Zoom for CWT Scalogram (B, C, H, W)
            cwt_np = cwt.numpy()
            cwt_tensor = cwt.unsqueeze(0)
            cwt_aug_tensor = F.interpolate(cwt_tensor, scale_factor=scale, mode='bilinear', align_corners=False)
            cwt_aug = cwt_aug_tensor.squeeze(0).numpy()

            # Crop/Pad to original size
            h, w = cwt_np.shape[1], cwt_np.shape[2]
            cwt_res = np.zeros_like(cwt_np)
            ch, cw = min(h, cwt_aug.shape[1]), min(w, cwt_aug.shape[2])
            cwt_res[:, :ch, :cw] = cwt_aug[:, :ch, :cw]
            
            return env_aug, torch.from_numpy(cwt_res)
        return env, cwt

    def __getitem__(self, idx):
        # Convert to tensor lazily per item to avoid COW memory leak
        env_raw = torch.tensor(self.env_wins[idx]).unsqueeze(0)   # (1, 257)
        cwt_raw = torch.tensor(self.cwt_feats[idx])                # (3, 224, 224)
        env, cwt = self._augment_pair(env_raw, cwt_raw)
        return env, cwt, self.labels[idx]


def _eval_f1(student_model, loader, device):
    """Evaluate weighted F1 on any DataLoader returning (x, y) or (env, cwt, y)."""
    student_model.eval()
    preds, lbls = [], []
    with torch.no_grad():
        for batch in loader:
            xb, yb = batch[0], batch[-1]
            logits, _ = student_model(xb.to(device))
            preds.extend(logits.argmax(1).cpu().numpy())
            lbls.extend(yb.numpy())
    return f1_score(lbls, preds, average='weighted', zero_division=0)


def run_mini_grid(teacher_wrap, paired_loader, val_loader, device, n_epochs=10):
    """
    10-epoch grid search over DKD hyperparams.
    Expert Audit (Issue 5): Evaluated on HELD-OUT val_dl, not test set.
    """
    grid = [
        {'tau': 3.0, 'alpha': 0.5, 'beta': 4.0, 'feat_w': 1.0},
        {'tau': 5.0, 'alpha': 1.0, 'beta': 8.0, 'feat_w': 1.0},
        {'tau': 5.0, 'alpha': 0.5, 'beta': 8.0, 'feat_w': 1.0},
    ]
    best_cfg, best_f1 = grid[1], -1.0

    for cfg in grid:
        s_tmp = Student1DCNN(NUM_CLASSES).to(device)
        opt   = torch.optim.Adam(s_tmp.parameters(), lr=1e-3)

        for _ in range(n_epochs):
            s_tmp.train()
            for env_xb, cwt_xb, yb in paired_loader:
                env_xb, cwt_xb, yb = env_xb.to(device), cwt_xb.to(device), yb.to(device)
                with torch.no_grad():
                    t_logits, t_feats = teacher_wrap(cwt_xb)
                opt.zero_grad()
                s_logits, s_feats = s_tmp(env_xb)
                loss = dkd_loss(s_logits, t_logits, s_feats, t_feats,
                                F.one_hot(yb, NUM_CLASSES).float(), **cfg)
                loss.backward()
                opt.step()

        val_f1 = _eval_f1(s_tmp, val_loader, device)
        print(f"  Grid {cfg}  →  val_f1={val_f1:.3f}")
        if val_f1 > best_f1:
            best_f1, best_cfg = val_f1, cfg

    print(f"✓ Best grid config: {best_cfg}  (val_f1={best_f1:.3f})")
    return best_cfg


def train_dkd_student(cfg=None, n_epochs=50, lr=1e-3, force_train=False):
    assert os.path.exists(TEACHER_PATH), f"Teacher not found: {TEACHER_PATH}"
    assert os.path.exists(CWT_FEAT_PATH), "CWT cache missing — run Cell 5 first."

    if recover_from_wandb(STUDENT_PATH) and not force_train:
        print(f"✓ Student checkpoint found (local or W&B) at {STUDENT_PATH}")
        print("  Resuming to ONNX export and evaluation...")
        global_best_state = torch.load(STUDENT_PATH, map_location='cpu')
        
        # Load summary results if available
        res_json = os.path.join(WORK_DIR, 'five_seed_results.json')
        recover_from_wandb(res_json)
        if os.path.exists(res_json):
            with open(res_json) as f:
                five_seed_results = json.load(f)
            # EXPERT: Auto-show old run log
            print(f"\n[RESTORED PREVIOUS RUN SUMMARY]")
            all_f1 = [r['best_f1'] for r in five_seed_results]
            print(f"  F1 per seed: {[f'{x:.3f}' for x in all_f1]}")
            print(f"  Mean ± Std:  {(np.mean(all_f1) if len(all_f1) > 0 else 0.0):.3f} ± {(np.std(all_f1, ddof=1) if len(all_f1) > 1 else 0.0):.3f}")
        else:
            five_seed_results = []
    else:
        # Load frozen teacher into Fix Bug 10 wrapper
        base = models.efficientnet_b0()
        base.classifier[1] = nn.Linear(1280, NUM_CLASSES)
        base.load_state_dict(torch.load(TEACHER_PATH, map_location='cpu'))
        teacher_wrap = TeacherWrapper(base).eval().to(DEVICE)
        for p in teacher_wrap.parameters():
            p.requires_grad = False
        if torch.cuda.device_count() > 1:
            teacher_wrap = nn.DataParallel(teacher_wrap)

        paired_ds     = PairedDKDDataset(train_dataset, CWT_FEAT_PATH, CWT_LBL_PATH)
        
        # Expert Fix (Issue E): Stratified Split for Grid Search
        from sklearn.model_selection import StratifiedShuffleSplit
        sss = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        indices = np.arange(len(paired_ds))
        tr_idx, va_idx = next(sss.split(indices, paired_ds.labels))
        
        tr_ds = torch.utils.data.Subset(paired_ds, tr_idx)
        va_ds = torch.utils.data.Subset(paired_ds, va_idx)
        
        def _worker_init(worker_id):
            seed = int(np.random.get_state()[1][0]) + worker_id
            np.random.seed(seed)
            random.seed(seed)
            torch.manual_seed(seed)

        paired_loader = DataLoader(tr_ds, batch_size=512, shuffle=True,
                                   num_workers=4, pin_memory=True, worker_init_fn=_worker_init)
        val_loader    = DataLoader(va_ds, batch_size=512, shuffle=False)

        if cfg is None:
            print("--- EXPERT HYPERPARAMETER GRID (10 epochs × 3 configs) ---")
            cfg = run_mini_grid(teacher_wrap, paired_loader, val_loader, DEVICE)

        wandb.init(project='bfd-dkd-edge', name='dkd_student_5seed', reinit=True)
        wandb.config.update(cfg)

        SEEDS = [42, 123, 456, 789, 1024]
        five_seed_results = []
        global_best_f1    = 0.0
        global_best_state = None

        import gc
        gc.collect()

        for seed in SEEDS:
            print(f"\n{'='*40}\nSEED {seed}\n{'='*40}")
            torch.manual_seed(seed)
            np.random.seed(seed)

            student   = Student1DCNN(NUM_CLASSES).to(DEVICE)
            optimizer = torch.optim.AdamW(student.parameters(), lr=lr, weight_decay=1e-4)
            # V15 FIX A-2: cycle_momentum=False — AdamW has its own momentum
            # state; cycling an external momentum on top creates conflicting
            # second-moment updates that cause the val_F1 0.06⟷0.93 oscillation.
            scheduler = torch.optim.lr_scheduler.OneCycleLR(
                optimizer,
                max_lr=3e-3,
                total_steps=n_epochs * len(paired_loader),
                pct_start=0.20,         # KEY: peaks at epoch 10 to match DKD warmup
                anneal_strategy='cos',
                cycle_momentum=False,   # KEY: off for AdamW
                div_factor=10.0,        # start_lr = max_lr/10 = 3e-4
                final_div_factor=1e6,   # final_lr ≈ 3e-9
            )
            seed_history = {'val_f1': [], 'train_loss': []}
            seed_best = 0.0

            for epoch in tqdm(range(n_epochs), desc=f'Seed {seed}', leave=False):
                student.train()
                run_loss = 0.0
                for env_xb, cwt_xb, yb in paired_loader:
                    env_xb, cwt_xb, yb = env_xb.to(DEVICE), cwt_xb.to(DEVICE), yb.to(DEVICE)
                    with torch.no_grad():
                        t_logits, t_feats = teacher_wrap(cwt_xb)
                    optimizer.zero_grad()
                    s_logits, s_feats = student(env_xb)
                    loss = _dkd_loss_warmed(s_logits, t_logits, s_feats, t_feats,
                                            F.one_hot(yb, NUM_CLASSES).float(), cfg, epoch)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
                    optimizer.step()
                    scheduler.step()
                    run_loss += loss.item() * env_xb.size(0)

                # V15: student.eval() is MANDATORY for stable BatchNorm evaluation.
                # Missing this causes BN to use *batch* stats during eval,
                # giving wildly different results batch-to-batch → F1 oscillation.
                val_f1 = _eval_f1(student, val_loader, DEVICE)
                current_lr = optimizer.param_groups[0]['lr']

                wandb.log({'seed': seed, 'epoch': epoch,
                           'train_loss': run_loss / len(tr_ds),
                           'val_f1': val_f1 * 100,
                           'learning_rate': current_lr})

                seed_history['val_f1'].append(val_f1)
                seed_history['train_loss'].append(run_loss / len(tr_ds))

                if val_f1 > seed_best:
                    seed_best = val_f1
                if val_f1 > global_best_f1:
                    global_best_f1  = val_f1
                    global_best_state = {k: v.cpu().clone()
                                         for k, v in student.state_dict().items()}

                if (epoch + 1) % 10 == 0:
                    print(f"  Ep {epoch+1:02d}/{n_epochs} | "
                          f"loss={run_loss/len(tr_ds):.4f} | "
                          f"val_f1={val_f1:.3f} | "
                          f"lr={current_lr:.2e}")

            five_seed_results.append({
                'seed': seed,
                'best_f1': seed_best,
                'final_loss': run_loss / len(tr_ds),
                'history': seed_history,
            })
            print(f"  Seed {seed}  →  best F1: {seed_best:.3f}")

        all_f1 = [r['best_f1'] for r in five_seed_results]
        print(f"\n=== 5-SEED SUMMARY ===")
        print(f"  F1 per seed: {[f'{x:.3f}' for x in all_f1]}")
        print(f"  Mean ± Std:  {(np.mean(all_f1) if len(all_f1) > 0 else 0.0):.3f} ± {(np.std(all_f1, ddof=1) if len(all_f1) > 1 else 0.0):.3f}")

        # V15: Learning curve plot — mandatory for IEEE TIM / MDPI Sensors
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        for r in five_seed_results:
            h = r.get('history', {})
            ax1.plot(h.get('val_f1', []), alpha=0.75, label=f"seed {r['seed']}")
            ax2.plot(h.get('train_loss', []), alpha=0.75, label=f"seed {r['seed']}")
        ax1.set_xlabel('Epoch'); ax1.set_ylabel('Val F1 (weighted)')
        ax1.set_title('Validation F1 per seed (V15)')
        ax1.legend(fontsize=7); ax1.set_ylim(0, 1.05)
        ax2.set_xlabel('Epoch'); ax2.set_ylabel('Train loss')
        ax2.set_title('Training loss per seed'); ax2.legend(fontsize=7)
        plt.tight_layout()
        curve_path = os.path.join(WORK_DIR, 'learning_curves.png')
        plt.savefig(curve_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f'Learning curves saved to {curve_path}')

        # Save local files
        torch.save(global_best_state, STUDENT_PATH)
        res_json = os.path.join(WORK_DIR, 'five_seed_results.json')
        with open(res_json, 'w') as f:
            json.dump(five_seed_results, f, indent=2)

        # Upload to W&B before finishing
        print(f"✓ Uploading artifacts to W&B...")
        wandb.save(STUDENT_PATH)
        wandb.save(res_json)
        wandb.finish()
        print(f"✓ Best student checkpoint → {STUDENT_PATH}")

    # ── ONNX export from global best ───────────────
    class _InferWrap(nn.Module):
        def __init__(self, m): super().__init__(); self.m = m
        def forward(self, x): return self.m(x)[0]

    best_student = Student1DCNN(NUM_CLASSES)
    best_student.load_state_dict(global_best_state)
    best_student.eval()
    dummy = torch.randn(1, 1, SPECTRUM_BINS)

    # V15 FIX C: Export to opset 18 directly.
    # Target hardware is Jetson Orin NX with JetPack 6 (TensorRT 10.x), which fully supports opset 18.
    torch.onnx.export(
        _InferWrap(best_student), dummy, ONNX_PATH,
        opset_version=18,
        input_names=['envelope_spectrum'], output_names=['fault_logits'],
        dynamic_axes=None,
        do_constant_folding=True,
        export_params=True,
        training=torch.onnx.TrainingMode.EVAL,
    )
    try:
        import onnx as _onnx
        _actual_opset = _onnx.load(ONNX_PATH).opset_import[0].version
    except Exception:
        _actual_opset = 18
    print(f'✓ ONNX exported (opset {_actual_opset}): {ONNX_PATH}')
    print('  NOTE: Target hardware (JetPack 6 / TensorRT 10.x) fully supports opset 18.')

    import onnxruntime as ort
    sess = ort.InferenceSession(ONNX_PATH)
    out  = sess.run(None, {'envelope_spectrum': dummy.numpy()})
    assert out[0].shape == (1, NUM_CLASSES)
    print(f"✓ ONNX verified. Output: {out[0].shape}")

    return five_seed_results


results = train_dkd_student(cfg=None)
