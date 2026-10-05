import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"C:\Users\Admin\Downloads\vibradistill.ipynb"

if not os.path.exists(nb_path):
    print(f"File NOT found at: {nb_path}")
    sys.exit(1)

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

cells = nb.get("cells", [])
print(f"Loaded notebook successfully! Total cells: {len(cells)}\n")

for i, cell in enumerate(cells):
    c_type = cell.get("cell_type", "")
    src = "".join(cell.get("source", []))
    first_line = src.strip().splitlines()[0] if src.strip() else "[EMPTY]"
    outputs = cell.get("outputs", [])
    
    print("=" * 80)
    print(f"CELL {i} [{c_type.upper()}] - {first_line[:70]}")
    print("=" * 80)
    
    if outputs:
        for out_idx, out in enumerate(outputs):
            out_type = out.get("output_type", "")
            print(f"--- Output {out_idx} ({out_type}) ---")
            if "text" in out:
                txt = "".join(out["text"])
                # print first few lines and last few lines if long
                lines = txt.splitlines()
                if len(lines) > 40:
                    for l in lines[:20]:
                        print(l)
                    print(f"\n... [{len(lines)-35} lines omitted] ...\n")
                    for l in lines[-15:]:
                        print(l)
                else:
                    print(txt)
            elif "data" in out:
                for mime, data in out["data"].items():
                    if mime == "text/plain":
                        print("".join(data)[:500])
                    else:
                        print(f"[{mime} data]")
            elif "ename" in out:
                print(f"ERROR: {out.get('ename')}: {out.get('evalue')}")
                for tb in out.get("traceback", [])[-5:]:
                    print(tb)
    else:
        if c_type == "code":
            print("[NO OUTPUT - CELL NOT EXECUTED OR PRODUCED NO OUTPUT]")
    print()
