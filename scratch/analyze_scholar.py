import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open('scratch/scholar_2026_results.json', encoding='utf-8'))
print(f"Total crawled papers: {len(data)}\n")
for i, x in enumerate(data):
    title = x.get('title', '').replace('\n', ' ')
    pub = x.get('pub_info', '').replace('\n', ' ')
    link = x.get('link', '')
    snippet = x.get('snippet', '').replace('\n', ' ')
    print(f"[{i+1:02d}] {title}\n     Pub: {pub}\n     Link: {link}\n     Snippet: {snippet[:120]}...\n")
