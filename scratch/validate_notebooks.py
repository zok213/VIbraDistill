"""
Notebook Syntax and Structure Validator.
Parses every code cell with ast.parse to guarantee ZERO syntax errors on Kaggle / Colab.
"""
import json
import ast
import sys

def validate_notebook(nb_path):
    print(f"Validating notebook: {nb_path}")
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    errors = []
    for idx, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            code = "".join(cell['source'])
            # Filter out IPython magic commands (! and % and ?) for AST parsing
            py_lines = []
            for line in code.split("\n"):
                stripped = line.strip()
                if stripped.startswith(('!', '%', '?')):
                    py_lines.append(f"# {line}")  # comment out magic
                else:
                    py_lines.append(line)
            py_code = "\n".join(py_lines)
            try:
                ast.parse(py_code)
            except SyntaxError as e:
                errors.append((idx, e, code))
    
    if errors:
        print(f"FAILED: Found {len(errors)} syntax errors in {nb_path}!")
        for idx, err, snippet in errors:
            print(f"\n--- Cell {idx} Error: {err} ---")
            print("Snippet:")
            for l_i, l in enumerate(snippet.split("\n")):
                print(f"  {l_i+1}: {l}")
        return False
    else:
        print(f"PASSED: All {len(nb['cells'])} cells are 100% syntactically valid!\n")
        return True

if __name__ == '__main__':
    ok1 = validate_notebook("notebooks/VibraDistill_Kaggle_Dual_T4.ipynb")
    ok2 = validate_notebook("notebooks/VibraDistill_Colab_GPU.ipynb")
    if not (ok1 and ok2):
        sys.exit(1)
