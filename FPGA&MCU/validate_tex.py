import re

with open('research_proposal.tex', encoding='utf-8') as f:
    tex = f.read()

# 1. Non-ASCII check
non_ascii = [(i+1, c) for i, c in enumerate(tex) if ord(c) > 127]
print(f'Non-ASCII chars: {len(non_ascii)}')

# 2. Brace balance
opens = tex.count('{')
closes = tex.count('}')
print(f'Brace balance: open={opens}, close={closes}, diff={opens-closes}')

# 3. All \cite keys
cite_keys = set(re.findall(r'\\cite\{([^}]+)\}', tex))
all_cite_keys = set()
for block in cite_keys:
    for k in block.split(','):
        all_cite_keys.add(k.strip())
print(f'Unique cite keys: {len(all_cite_keys)}')

# 4. Load bib keys
with open('references.bib', encoding='utf-8') as f:
    bib = f.read()
bib_keys = set(re.findall(r'@\w+\{(\w+)', bib))
print(f'BibTeX entries: {len(bib_keys)}')

missing = all_cite_keys - bib_keys
if missing:
    print(f'MISSING from bib: {missing}')
else:
    print('Missing from bib: NONE - all OK')

# 5. Figures referenced
figs = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', tex)
print(f'includegraphics references: {figs}')

# 6. Check no placeholder text
for bad in ['[Author Name', '[University', 'TODO', 'FIXME', 'amber']:
    hits = [ln+1 for ln, line in enumerate(tex.splitlines()) if bad in line]
    if hits:
        print(f'WARNING found "{bad}" at lines: {hits[:5]}')
print('Done.')
