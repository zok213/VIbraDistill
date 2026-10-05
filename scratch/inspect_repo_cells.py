import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("notebooks/VibraDistill_Kaggle_Dual_T4.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

print("=== CELL 0 (Title) ===")
print("".join(nb['cells'][0]['source']))

print("=== CELL 4 (Setup) ===")
print("".join(nb['cells'][4]['source']))

print("=== CELL 14 (QAT) ===")
print("".join(nb['cells'][14]['source']))

print("=== CELL 18 (Export) ===")
print("".join(nb['cells'][18]['source']))
