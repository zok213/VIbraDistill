"""
Kaggle Dataset Archive & Metadata Integrity Validator.
Tests every .zip file in kaggle/datasets for:
- Zip CRC32 integrity check (testzip)
- Valid dataset-metadata.json schema for Kaggle API
- File count & size report
"""

import os
import json
import zipfile
import glob

def validate_datasets(base_dir="kaggle/datasets"):
    print("=" * 80)
    print("  KAGGLE DATASET INTEGRITY & UPLOAD VALIDATION REPORT")
    print("=" * 80)
    
    subdirs = [d for d in glob.glob(os.path.join(base_dir, "*")) if os.path.isdir(d)]
    if not subdirs:
        print("No dataset directories found!")
        return False
    
    total_zips = 0
    all_ok = True
    for d in sorted(subdirs):
        folder_name = os.path.basename(d)
        print(f"\n[DATASET: {folder_name}]")
        
        # Check metadata
        meta_file = os.path.join(d, "dataset-metadata.json")
        if not os.path.exists(meta_file):
            print("  [FAIL] ERROR: Missing dataset-metadata.json!")
            all_ok = False
        else:
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                req_fields = ['title', 'id', 'licenses']
                missing = [k for k in req_fields if k not in meta]
                if missing:
                    print(f"  [FAIL] ERROR: metadata missing required fields: {missing}")
                    all_ok = False
                else:
                    print(f"  [PASS] Metadata valid: Title='{meta['title']}', ID='{meta['id']}'")
            except Exception as e:
                print(f"  [FAIL] ERROR parsing JSON: {e}")
                all_ok = False

        # Check zip archive
        zips = glob.glob(os.path.join(d, "*.zip"))
        if not zips:
            print("  [FAIL] ERROR: No .zip archive found in folder!")
            all_ok = False
        else:
            for zpath in zips:
                total_zips += 1
                size_mb = os.path.getsize(zpath) / (1024 * 1024)
                print(f"  Archive: {os.path.basename(zpath)} ({size_mb:.2f} MB)")
                try:
                    with zipfile.ZipFile(zpath, 'r') as zf:
                        bad_file = zf.testzip()
                        if bad_file:
                            print(f"  [FAIL] ERROR: Corrupted file inside zip: {bad_file}")
                            all_ok = False
                        else:
                            file_count = len(zf.namelist())
                            print(f"  [PASS] CRC32 Integrity PASS! Contains {file_count} files.")
                except Exception as e:
                    print(f"  [FAIL] ERROR opening zip: {e}")
                    all_ok = False

    print("\n" + "=" * 80)
    if all_ok:
        print(f"ALL {total_zips} KAGGLE DATASETS ARE 100% VALID, UNCORRUPTED, AND READY TO UPLOAD!")
    else:
        print("SOME DATASETS HAVE INTEGRITY ISSUES!")
    print("=" * 80)
    return all_ok

if __name__ == '__main__':
    validate_datasets()
