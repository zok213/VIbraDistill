"""
Automated Downloader & Extractor for XJTU-SY Run-to-Failure Bearing Dataset.
Downloads all 6 multi-part RAR archives from official Google Drive mirror and
extracts using UnRAR.exe into `data/XJTU-SY_Dataset/raw/`.
"""

import os
import sys
import subprocess
import gdown

# Force UTF-8 IO
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

XJTU_PARTS = [
    ("part01", "1ATvZuD6j3bPxhyR07Zm-PURmOC4b4uRn", "XJTU-SY_Bearing_Datasets.part01.rar"),
    ("part02", "162KvWNIpBGtd7EDWo4yP1j5XsaoNHOYU", "XJTU-SY_Bearing_Datasets.part02.rar"),
    ("part03", "1NvzrGW-KOSy48OZmiFxlE3TPV4CKAcw0", "XJTU-SY_Bearing_Datasets.part03.rar"),
    ("part04", "1VuQ5-mK11p1S2pTxUZaH_IxOwUlsmN0S", "XJTU-SY_Bearing_Datasets.part04.rar"),
    ("part05", "1WH4OU4MLaMGQkbh6DghxPA5Dwvsq8tEf", "XJTU-SY_Bearing_Datasets.part05.rar"),
    ("part06", "1wzQzQUx6-J8DuGczT81OkrkTgOUwL-I_", "XJTU-SY_Bearing_Datasets.part06.rar"),
]

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    download_dir = os.path.join(root_dir, 'data', 'XJTU-SY_Dataset', 'downloads')
    extract_dir = os.path.join(root_dir, 'data', 'XJTU-SY_Dataset', 'raw')
    os.makedirs(download_dir, exist_ok=True)
    os.makedirs(extract_dir, exist_ok=True)
    
    # 1. Recover part01 from test_part01.tmp if present
    tmp_part1 = os.path.join(root_dir, 'test_part01.tmp')
    target_part1 = os.path.join(download_dir, 'XJTU-SY_Bearing_Datasets.part01.rar')
    if os.path.exists(tmp_part1) and not os.path.exists(target_part1):
        print(f"Moving {tmp_part1} -> {target_part1}...")
        os.rename(tmp_part1, target_part1)
        
    # 2. Download missing parts
    print("=" * 70)
    print("  DOWNLOADING XJTU-SY RUN-TO-FAILURE BEARING DATASETS")
    print("=" * 70)
    
    for tag, gdrive_id, filename in XJTU_PARTS:
        dest_path = os.path.join(download_dir, filename)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 100 * 1024 * 1024:
            print(f"[{tag.upper()}] Already downloaded ({os.path.getsize(dest_path)/(1024**2):.1f} MB) -> {filename}")
            continue
            
        print(f"\n[{tag.upper()}] Downloading {filename} from Google Drive (id: {gdrive_id})...")
        url = f"https://drive.google.com/uc?id={gdrive_id}"
        gdown.download(url, dest_path, quiet=False, fuzzy=True)
        print(f"Downloaded {filename}: {os.path.getsize(dest_path)/(1024**2):.1f} MB.")
        
    print("\nAll 6 RAR parts successfully downloaded!")
    
    # 3. Extract archives using UnRAR.exe
    unrar_path = r"C:\Program Files\WinRAR\UnRAR.exe"
    if not os.path.exists(unrar_path):
        unrar_path = r"C:\Program Files\WinRAR\WinRAR.exe"
        
    if os.path.exists(unrar_path):
        part1_archive = os.path.join(download_dir, 'XJTU-SY_Bearing_Datasets.part01.rar')
        print(f"\nExtracting multi-part RAR using {unrar_path}...")
        print(f"Destination: {extract_dir}")
        cmd = [unrar_path, "x", "-y", "-o+", part1_archive, extract_dir]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("Extraction return code:", res.returncode)
        if res.returncode == 0:
            print("Extraction successfully completed!")
        else:
            print("Extraction output / warnings:\n", res.stdout[-500:] if res.stdout else res.stderr)
    else:
        print("Warning: UnRAR.exe not found at standard path. Please extract manually.")
        
    # 4. Verify extracted contents
    print("\nAuditing extracted datasets in:", extract_dir)
    items = []
    for root, dirs, files in os.walk(extract_dir):
        if files:
            csv_count = len([f for f in files if f.endswith('.csv')])
            rel_dir = os.path.relpath(root, extract_dir)
            items.append(f"  Folder: {rel_dir} | CSV files: {csv_count}")
            
    print(f"Total subdirectories with data: {len(items)}")
    for item in items[:15]:
        print(item)
    print("=" * 70)

if __name__ == '__main__':
    main()
