import glob, ast, sys, os
from scripts import build_notebook

print('--- SYNTAX CHECK ---')
cells = sorted(glob.glob('scripts/cells/*.py'))
for f in cells:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            src = fh.read().replace('!pip', '#pip')
            ast.parse(src)
            print(f'OK: {os.path.basename(f)}')
    except Exception as e:
        print(f'ERROR in {os.path.basename(f)}: {e}')

print('\n--- FIX VERIFICATION ---')
with open('scripts/cells/cell_05.py', 'r', encoding='utf-8') as fh: c5 = fh.read()
print('DKD Loss Scaling:', 'OK' if '* (tau ** 2)' in c5 else 'FAIL')
print('Batch Size:', 'OK' if 'batch_size=512' in c5 else 'FAIL')
print('Opset 18:', 'OK' if 'opset_version=18' in c5 else 'FAIL')
print('LR pct_start:', 'OK' if 'pct_start=0.20' in c5 else 'FAIL')
print('GC Collect:', 'OK' if 'gc.collect()' in c5 else 'FAIL')
print('AdamW cycle_momentum:', 'OK' if 'cycle_momentum=False' in c5 else 'FAIL')

with open('scripts/cells/cell_03.py', 'r', encoding='utf-8') as fh: c3 = fh.read()
print('SVM CV Leakage fixed:', 'OK' if 'for seed in [42, 123, 456, 789, 1024]:' in c3 and 'pipe.fit(X_train, y_train)' in c3 else 'FAIL')

with open('scripts/cells/cell_02.py', 'r', encoding='utf-8') as fh: c2 = fh.read()
print('Butter filter outside loop:', 'OK' if "self.b_env, self.a_env = signal.butter(2, 1000 / (FS / 2), btype='lowpass')" in c2 else 'FAIL')

build_notebook.build()
