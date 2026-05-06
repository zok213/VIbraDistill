import re

with open('scripts/create_nb.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. SELayer Hardsigmoid(inplace=True) -> Hardsigmoid()
text = text.replace('nn.Hardsigmoid(inplace=True)', 'nn.Hardsigmoid()')

# 2. & 3. Wrap _svm_f1 in try/except in Cell 9
cell9_marker = "# CELL 9 — Phase 6: Final Statistical Report"
text = text.replace(cell9_marker, cell9_marker + "\n\ntry:\n    _svm_f1 = svm_f1\nexcept NameError:\n    _svm_f1 = 0.0")

# 4. run_loss Division
text = text.replace('run_loss/len(paired_ds)', 'run_loss/len(tr_ds)')
text = text.replace('run_loss / len(paired_ds)', 'run_loss / len(tr_ds)')

# 5. RUL threshold normalization raw fix
# We will just rewrite the fit_degradation_models loop
old_fit = """    fits = []
    for exp in norm_exps:
        n = len(exp)
        t = np.linspace(0, 1, n)"""
new_fit = """    fits = []
    for raw_exp, exp in zip(experiments, norm_exps):
        mx = raw_exp[-1] if raw_exp[-1] > 0 else 1.0
        n = len(exp)
        t = np.linspace(0, 1, n)"""
text = text.replace(old_fit, new_fit)
text = text.replace("'threshold': threshold,", "'threshold': threshold * mx,")

# 6. XJTU-SY BPFO
text = text.replace('BPFO_X = 107.0', 'BPFO_X = 236.4')

# 7. signal.resample
text = text.replace('signal.resample(', 'signal.resample_poly(')

# 8. Jackknife+ Guarantee comments
text = text.replace('95% Coverage', '90% Coverage')
text = text.replace('1 - \\alpha = 95%', '1 - 2\\alpha = 90%')
text = text.replace('alpha=0.05', 'alpha=0.05') # The formula is 1-2a, so alpha=0.05 gives 90%

# 9. SELayer dynamic length
text = text.replace('def __init__(self, channel, reduction=16):', 'def __init__(self, channel, length, reduction=16):')
text = text.replace('self.avg_pool = nn.AvgPool1d(kernel_size=SPECTRUM_BINS)', 'self.avg_pool = nn.AvgPool1d(kernel_size=length)')
# Also update Student1DCNN instances
text = text.replace('SELayer(16, reduction=4)', 'SELayer(16, length=128, reduction=4)')
text = text.replace('SELayer(32, reduction=8)', 'SELayer(32, length=64, reduction=8)')
text = text.replace('SELayer(64, reduction=16)', 'SELayer(64, length=32, reduction=16)')
text = text.replace('SELayer(128, reduction=16)', 'SELayer(128, length=32, reduction=16)') # if it had 128

# 10. Loss Scaling (feat_w=0.0)
text = text.replace('feat_w=1.0', 'feat_w=0.0')

# 11. Move zoom import
text = text.replace('from scipy.ndimage import zoom\n            cwt_aug = zoom', 'cwt_aug = zoom')
text = text.replace('import scipy.signal as signal\n', 'import scipy.signal as signal\nfrom scipy.ndimage import zoom\n')

# 12. AvgPool1d(8) fallback/dynamic
text = text.replace('nn.AvgPool1d(8),', 'nn.AdaptiveAvgPool1d(4),')

# 13. Ottawa source_fs dynamic reading
# We will just change hardcoded 20000 to dynamic if it was hardcoded.
text = text.replace('fs=20000', 'fs=FS')

# 14. Empty five_seed_results NaN guard
text = text.replace('np.mean(all_f1)', '(np.mean(all_f1) if len(all_f1) > 0 else 0.0)')
text = text.replace('np.std(all_f1, ddof=1)', '(np.std(all_f1, ddof=1) if len(all_f1) > 1 else 0.0)')

with open('scripts/create_nb.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patching complete!")
