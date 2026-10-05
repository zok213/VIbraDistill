import os
import urllib.request
import xml.etree.ElementTree as ET
import json

os.makedirs('scratch', exist_ok=True)
url = 'http://export.arxiv.org/api/query?search_query=all:%22bearing+fault+diagnosis%22+AND+(all:%22physics%22+OR+all:%22conformal%22+OR+all:%22distillation%22)&sortBy=submittedDate&sortOrder=descending&max_results=10'
req = urllib.request.Request(url, headers={'User-Agent': 'VibraDistillResearch/1.0'})

try:
    with urllib.request.urlopen(req) as resp:
        data = resp.read()

    root = ET.fromstring(data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    results = []
    for entry in root.findall('atom:entry', ns):
        title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
        summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
        published = entry.find('atom:published', ns).text[:10]
        id_val = entry.find('atom:id', ns).text
        authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
        results.append({
            'id': id_val,
            'published': published,
            'title': title,
            'authors': authors[:4],
            'summary': summary
        })

    with open('scratch/arxiv_sota_papers.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print(f'Successfully fetched {len(results)} recent papers from arXiv:')
    for r in results:
        print(f"[{r['published']}] {r['title']}")
        print(f"  Authors: {', '.join(r['authors'])}")
        print(f"  ID: {r['id']}")
        print(f"  Summary: {r['summary'][:180]}...\n")
except Exception as e:
    print('Error querying arXiv:', e)
