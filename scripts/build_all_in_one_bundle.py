"""
VibraDistill-Edge: All-in-One Kaggle Master Bundle Packager.
Combines:
  1. Complete code (src, scripts, configs, embedded, requirements.txt)
  2. All 6 packaged datasets (CWRU, MFPT, PRONOSTIA, SEU, PHM2009, Rotating Machine)
into ONE single master archive:
  kaggle/datasets/vibradistill-all-in-one/vibradistill-all-in-one.zip
with matching dataset-metadata.json.

Upload this ONE file to Kaggle -> Click "Run All" -> Runs 100% end-to-end!
"""

import os
import sys
import json
import zipfile
import time

TARGET_DIR = "kaggle/datasets/vibradistill-all-in-one"
TARGET_ZIP = os.path.join(TARGET_DIR, "vibradistill-all-in-one.zip")

CODE_DIRS = ['src', 'scripts', 'configs', 'embedded', 'notebooks', 'checkpoints']
CODE_FILES = ['requirements.txt', 'setup.py', 'README.md']

DATASET_FOLDERS = [
    'CWRU_Dataset',
    'MFPT_Dataset',
    'Rotating_Machine_Faults_Dataset',
    'PHM2009_Gearbox_Dataset',
    'SEU_Dataset',
    'PRONOSTIA_FEMTO_Dataset'
]

def build_all_in_one_bundle():
    t0 = time.time()
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    print("=" * 80)
    print("  CREATING VIBRADISTILL-EDGE ALL-IN-ONE MASTER KAGGLE BUNDLE")
    print(f"  Target Archive: {TARGET_ZIP}")
    print("=" * 80)

    # 1. Count total files to be included
    total_files = 0
    for cd in CODE_DIRS:
        if os.path.exists(cd):
            total_files += sum(len(fs) for _, _, fs in os.walk(cd))
    for cf in CODE_FILES:
        if os.path.exists(cf): total_files += 1
    for df in DATASET_FOLDERS:
        dp = os.path.join("data", df)
        if os.path.exists(dp):
            total_files += sum(len(fs) for _, _, fs in os.walk(dp))

    print(f"Total files to package: {total_files}")
    
    with zipfile.ZipFile(TARGET_ZIP, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        count = 0
        
        # Add Code Files
        print("\n[1] Packaging Codebase & Embedded Firmware/RTL...")
        for cd in CODE_DIRS:
            if os.path.exists(cd):
                for root, _, files in os.walk(cd):
                    for f in files:
                        if f.endswith(('.pyc', '.pyo')) or '__pycache__' in root:
                            continue
                        fp = os.path.join(root, f)
                        arc = fp.replace(os.sep, '/')
                        zf.write(fp, arc)
                        count += 1
        for cf in CODE_FILES:
            if os.path.exists(cf):
                zf.write(cf, cf.replace(os.sep, '/'))
                count += 1
        print(f"  Added codebase files ({count} files)")

        # Add Data Folders
        print("\n[2] Packaging Datasets into data/ folder...")
        for df in DATASET_FOLDERS:
            dp = os.path.join("data", df)
            if not os.path.exists(dp):
                print(f"  Warning: {dp} not found, skipping.")
                continue
            df_files = sum(len(fs) for _, _, fs in os.walk(dp))
            print(f"  Adding {df} ({df_files} files)...")
            for root, _, files in os.walk(dp):
                for f in files:
                    fp = os.path.join(root, f)
                    arc = fp.replace(os.sep, '/')
                    zf.write(fp, arc)
                    count += 1
                    if count % 2000 == 0:
                        sys.stdout.write(f"\r  Progress: {count}/{total_files} files ({count/total_files*100:.1f}%)")
                        sys.stdout.flush()

    print()
    size_mb = os.path.getsize(TARGET_ZIP) / (1024 * 1024)
    print(f"  Archive built successfully in {time.time()-t0:.1f}s -> Size: {size_mb:.2f} MB")

    # Generate Kaggle metadata
    meta = {
        "title": "VibraDistill-Edge Master All-in-One Bundle",
        "id": "yourusername/vibradistill-all-in-one",
        "licenses": [{"name": "CC0-1.0"}],
        "description": "Complete self-contained bundle for VibraDistill-Edge containing full codebase and 6 benchmark datasets (CWRU, MFPT, PRONOSTIA, SEU, PHM2009, Rotating Machine)."
    }
    meta_path = os.path.join(TARGET_DIR, "dataset-metadata.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    print(f"  Metadata created: {meta_path}")

    print("\n" + "=" * 80)
    print("ALL-IN-ONE BUNDLE READY!")
    print(f"  Upload file: {TARGET_ZIP}")
    print("  Attach to Kaggle Notebook -> Click 'Run All' once -> Everything runs end-to-end!")
    print("=" * 80)

if __name__ == '__main__':
    build_all_in_one_bundle()
