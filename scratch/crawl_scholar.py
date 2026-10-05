import urllib.request
import urllib.parse
import time
import json
from bs4 import BeautifulSoup

cookies = (
    'GSP=SRD=1:ATS=3:ATD=20718:LM=1790078244:S=0J8gJzhaBaEX1XDU; '
    'NID=CpcECAESyQMBOxGDSDo--LHVCbqnJDgpMqb6yGmhY52rxJZsumvWfRHtFjte0CCm2VGO9xYgokc1RB1afMwHjR-LRsqkrn0WoAY9Cw5v3Pns45bITXquND-LY8ZOVbctORTNHMinfLI2OUowRSBIAlhdvkpWOMj0rD2vN4ypEGlNpEx-gfpl-BVsWlIlk317UtSdEF8N_kfyFLPlblEpcfE_6das9d_gVg-tQ-Fx88Y9IBSwvmsIahvsTOrFnArQE2-ngqcmCtN_k89Q-f0pngu_0YbRYhnRrEb-JLG9QbZ4ojEvFjfy5VTovO7-OmK-4a9lU7_Q7iGjbfAlS3kQBQgGoziY6Rlu-Byh3bd0x2CrcbAC0A5olj6ZtQ00oJ2p7BfnYFM9JBFB5yS0DFhDxOP8YcBpq1HPkPZKdnHJkKeicJ4Pr9TWcGu7EU8l7bnT8z6GD7O1u2DCEWbTjC5IFIlpj-NT-DQ5HpGxIDySVDUGrVdWzxaf1cP1PjxMDWWuXJyWuEuaJ3fDZoKlUATAfR1v-Ito6htqiPeIv1axt8xCXbZBFqYEuVyP9CctozQ3TL8Yg_FjmI5xIYzOm517wBF8980TVi2pLYzrbcfefe_lKAEyRQHSrAfPW1EBUnSV8QdOgx1KCEJkwNtaU2yJ9iLeeWf0IDzZD5ywb1kUjQ-jOg21k5zy16QWwyDnq_tCpy7sFSEZTrRHCg; '
    'SID=g.a000DQkWwyCEgCFh96eryREwIB-ESUgHk9FiMssUA7dZH4YyWKIAsRQgo1htAItRb-esn3cYqgACgYKAV0SARASFQHGX2MihwX2o3VJjHTiqVkEQFS5ehoVAUF8yKoNMwF6rpQx_FyT4P8bf3s10076; '
    'HSID=AKg7vjWwiB0Nc65o-; SSID=AhnmXrenOuft6eTRo; APISID=dawf7OsDDIC-_Vzx/AIDCzP5PNVT4fE5W5; SAPISID=8uI2MGeg049-WKuJ/AQMS1QyeELHIjvywl; '
    '__Secure-1PAPISID=8uI2MGeg049-WKuJ/AQMS1QyeELHIjvywl; '
    '__Secure-1PSID=g.a000DQkWwyCEgCFh96eryREwIB-ESUgHk9FiMssUA7dZH4YyWKIAZQrXvxm--LdmVwPNem7V2QACgYKAXUSARASFQHGX2MiqHTeLAwczzbcitMem2bhXBoVAUF8yKp_i9c0-Cw1JV39MInZB3MV0076; '
    '__Secure-3PAPISID=8uI2MGeg049-WKuJ/AQMS1QyeELHIjvywl; '
    '__Secure-3PSID=g.a000DQkWwyCEgCFh96eryREwIB-ESUgHk9FiMssUA7dZH4YyWKIABwMREZqW7nfoMw6yq7_C2gACgYKAakSARASFQHGX2Mi10VGVF1EbXnBA_Thj-Cz_hoVAUF8yKoF2BeKp-BJbyyoHAV5wPao0076'
)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Cookie': cookies,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

results = []
pages = [40, 50, 60, 70, 80, 90, 100]

for start in pages:
    url = f'https://scholar.google.com/scholar?start={start}&q=fault+bearing&hl=en&as_sdt=0,5&as_ylo=2026'
    print(f'Fetching start={start}...')
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')
            articles = soup.find_all('div', class_='gs_ri')
            for art in articles:
                title_elem = art.find('h3', class_='gs_rt')
                title = title_elem.get_text() if title_elem else 'No Title'
                link_elem = title_elem.find('a') if title_elem else None
                link = link_elem.get('href') if link_elem else ''
                pub_info = art.find('div', class_='gs_a')
                pub = pub_info.get_text() if pub_info else ''
                snippet_elem = art.find('div', class_='gs_rs')
                snippet = snippet_elem.get_text() if snippet_elem else ''
                results.append({
                    'title': title,
                    'link': link,
                    'pub_info': pub,
                    'snippet': snippet,
                    'page_start': start
                })
        print(f' Page {start} success! Total items so far: {len(results)}')
    except Exception as e:
        print(f' Error on page {start}: {e}')
    time.sleep(2.0)  # Safe delay to avoid rate limits

with open('scratch/scholar_2026_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f'\nTotal scraped: {len(results)} papers from Google Scholar 2026!')
