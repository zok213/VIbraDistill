import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r"C:\Users\Admin\Downloads\vibradistill.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

for i, c in enumerate(nb['cells']):
    if c['cell_type'] == 'code':
        src = "".join(c['source']).strip().splitlines()[0] if c['source'] else ""
        outs = c.get('outputs', [])
        errs = [o for o in outs if o.get('output_type') == 'error']
        print(f"Cell {i:02d}: {src[:50]} | outputs={len(outs)} | errors={len(errs)}")
        if errs:
            print(f"   --> ERROR in Cell {i}: {errs[0].get('ename')}: {errs[0].get('evalue')}")
            for tb in errs[0].get('traceback', [])[-3:]:
                print(f"       {tb}")
        elif outs:
            for o in outs:
                if 'text' in o:
                    first_lines = "".join(o['text']).strip().splitlines()
                    for l in first_lines[:3]:
                        print(f"       [out] {l}")
                    if len(first_lines) > 3:
                        print(f"       [out] ... ({len(first_lines)} total lines)")
                        print(f"       [out] (last) {first_lines[-1]}")
