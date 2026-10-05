import os
import glob
import json

def build():
    cells_dir = os.path.join(os.path.dirname(__file__), 'cells')
    import re as _re
    # GUARD: only include files whose basenames match the canonical naming scheme
    # (00_header.py  or  cell_NN.py).  Any helper / patch / temp script that
    # starts with _ or does not match is silently excluded so it can never
    # corrupt the assembled notebook.
    _CELL_RE = _re.compile(r'^(00_header|cell_\d+)\.py$')
    cell_files = sorted(
        f for f in glob.glob(os.path.join(cells_dir, '*.py'))
        if _CELL_RE.match(os.path.basename(f))
    )
    
    nb_cells = []
    
    for fpath in cell_files:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Don't create a cell for 00_header.py, but maybe append it to the first cell?
        # Actually, 00_header.py was the text before CELL 1. We can just make it a markdown cell or skip it.
        # Let's just make everything a code cell for simplicity, or if it starts with # =, it's a code cell.
        if '00_header' in fpath:
            # We can make it a raw cell or just merge it into cell 1.
            # Let's just merge it into cell 1's source.
            header_content = content
            continue
            
        if 'cell_01' in fpath:
            content = header_content + '\n\n' + content

        nb_cells.append({
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [line + '\n' for line in content.split('\n')]
        })

    notebook = {
        'cells': nb_cells,
        'metadata': {
            'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python', 'version': '3.10.12'}
        },
        'nbformat': 4,
        'nbformat_minor': 4
    }

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'notebooks', 'VIbraDistill_Master.ipynb')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1)

    print(f'Successfully wrote notebook to {out_path}')

if __name__ == '__main__':
    build()
