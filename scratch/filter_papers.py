import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open('scratch/scholar_2026_results.json', encoding='utf-8'))

keywords = [
    'lightkd', 'aerogpt', 'sincnet', 'chaos', 'foundation model', 'llm', 'cbam', 
    'atub', 'deconvolution', 'contrastive', 'leptokurtic', 'manifold', 'kurtogram', 
    'speed-invariant', 'beargen', 'prototypical', 'differential-enhanced', 'hopfield'
]

selected = []
for idx, x in enumerate(data):
    title = x.get('title', '').replace('[HTML][HTML]', '').strip()
    link = x.get('link', '')
    pub = x.get('pub_info', '')
    snip = x.get('snippet', '')
    full_str = f"{title} {snip}".lower()
    for kw in keywords:
        if kw in full_str:
            selected.append((idx+1, title, pub, link, kw, snip))
            break

print(f"Total matching high-priority papers: {len(selected)}\n")
for idx, title, pub, link, kw, snip in selected:
    print(f"[{idx:02d}] (Match: '{kw}') {title}\n     Pub: {pub}\n     Link: {link}\n     Snippet: {snip[:130]}...\n")
