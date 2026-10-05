import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"C:\Users\Admin\Downloads\vibradistill (1).ipynb"

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

cells = nb.get("cells", [])
print(f"Total cells: {len(cells)}")

for i, cell in enumerate(cells):
    c_type = cell.get("cell_type", "")
    src = "".join(cell.get("source", []))
    first_line = src.strip().splitlines()[0] if src.strip() else "[EMPTY]"
    outputs = cell.get("outputs", [])
    errs = [o for o in outputs if o.get("output_type") == "error"]
    
    print("=" * 80)
    print(f"CELL {i:02d} [{c_type.upper()}] (outputs: {len(outputs)}, errs: {len(errs)}) - {first_line[:65]}")
    print("=" * 80)
    
    if errs:
        print(f"  ❌ ERROR: {errs[0].get('ename')}: {errs[0].get('evalue')}")
        for tb in errs[0].get('traceback', [])[-5:]:
            print(f"     {tb}")
    elif outputs:
        for out in outputs:
            if "text" in out:
                txt_lines = "".join(out["text"]).splitlines()
                if len(txt_lines) > 25:
                    for l in txt_lines[:12]:
                        print(f"  [out] {l}")
                    print(f"  ... [{len(txt_lines)-20} lines omitted] ...")
                    for l in txt_lines[-8:]:
                        print(f"  [out] {l}")
                else:
                    for l in txt_lines:
                        print(f"  [out] {l}")
    else:
        if c_type == "code":
            print("  [NO OUTPUT]")
    print()
