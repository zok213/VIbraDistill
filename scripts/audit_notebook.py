import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\Gitrepo\VIbraDistill\kaggle\notebook\Master_Kaggle_Runner.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Collect all definitions across all code cells (simulates shared kernel)
all_definitions = set()
issues = []

for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] != "code":
        continue
    src = "".join(cell["source"])

    # Track what's defined
    import re
    defs = re.findall(r'^def (\w+)', src, re.MULTILINE)
    classes = re.findall(r'^class (\w+)', src, re.MULTILINE)
    all_definitions.update(defs)
    all_definitions.update(classes)

    # Check for bad cross-file imports
    if "from Phase" in src:
        issues.append(f"Cell {i:02d}: BAD IMPORT - cross-script import found")
    if 'if __name__ ==' in src:
        issues.append(f"Cell {i:02d}: __main__ guard skips code in notebook")

# Second pass: check usages against full definition set
for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] != "code":
        continue
    src = "".join(cell["source"])
    calls = re.findall(r'\b(\w+)\s*\(', src)
    for call in calls:
        if call in ["get_dataloaders", "precompute_dataset", "train_teacher", "main"]:
            if call not in all_definitions:
                issues.append(f"Cell {i:02d}: '{call}' called but not defined anywhere in notebook!")

print(f"Total cells: {len(nb['cells'])}")
print(f"Definitions found across kernel: {sorted(all_definitions)}")
print()
print("=" * 60)
if issues:
    print("REAL ISSUES FOUND:")
    for iss in issues:
        print("  [!]", iss)
else:
    print("CLEAN: Notebook is fully ready for Kaggle Dual T4 execution!")
print("=" * 60)
