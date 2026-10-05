"""
Master Benchmark Dataset Downloader & Validator for VibraDistill-Edge.
Sequentially downloads, extracts, and validates all 9 international rotating machinery datasets:
  1. CWRU (Case Western Reserve Univ.) [Already local]
  2. XJTU-SY (Xi'an Jiaotong Univ.) [Already local & extracted]
  3. MFPT (Machinery Failure Prevention Technology)
  4. PRONOSTIA / FEMTO-ST (IEEE PHM 2012 Challenge)
  5. NASA IMS (Rexnord Run-to-Failure)
  6. SEU (Southeast University Planetary Gearbox & Bearing)
  7. Ottawa (UORED - Time-Varying Speed Rig)
  8. Paderborn (PU Bearing Data Center)
  9. MaFaulDa (Machinery Fault Database)
"""

import os
import sys
import shutil
import zipfile
import subprocess
import argparse
import urllib.request
import json
from pathlib import Path

DATA_ROOT = Path("data")

DATASETS_METADATA = {
    "cwru": {
        "name": "CWRU Bearing Dataset",
        "dir": DATA_ROOT / "CWRU_Dataset",
        "type": "preinstalled",
    },
    "xjtu_sy": {
        "name": "XJTU-SY Bearing Dataset",
        "dir": DATA_ROOT / "XJTU-SY_Dataset" / "raw" / "XJTU-SY_Bearing_Datasets",
        "type": "preinstalled",
    },
    "mfpt": {
        "name": "MFPT Fault Datasets",
        "kaggle_ref": "emperorpein/mfpt-fault-datasets",
        "dir": DATA_ROOT / "MFPT_Dataset",
        "type": "kaggle",
    },
    "pronostia": {
        "name": "PRONOSTIA / FEMTO-ST Bearing Dataset (IEEE PHM 2012)",
        "kaggle_ref": "alanhabrony/ieee-phm-2012-data-challenge",
        "dir": DATA_ROOT / "PRONOSTIA_FEMTO_Dataset",
        "type": "kaggle",
    },
    "nasa_ims": {
        "name": "NASA IMS Bearing Dataset",
        "kaggle_ref": "vinayak123tyagi/bearing-dataset",
        "dir": DATA_ROOT / "NASA_IMS_Dataset",
        "type": "kaggle",
    },
    "seu": {
        "name": "SEU Gearbox and Bearing Dynamic Failure Dataset",
        "kaggle_ref": "brjapon/gearbox-fault-diagnosis",
        "github_fallback": "cathysiyu/Mechanical-datasets",
        "dir": DATA_ROOT / "SEU_Dataset",
        "type": "seu",
    },
    "ottawa": {
        "name": "University of Ottawa Rolling-element Dataset (UORED)",
        "kaggle_ref": "mohdsufianbinothman/university-of-ottawa-rolling-element-dataset",
        "dir": DATA_ROOT / "Ottawa_Dataset",
        "type": "kaggle",
    },
    "paderborn": {
        "name": "Paderborn University Bearing Dataset (PU)",
        "kaggle_ref": "alejandromejiao/paderborn",
        "dir": DATA_ROOT / "Paderborn_Dataset",
        "type": "kaggle",
    },
    "mafaulda": {
        "name": "MaFaulDa Machinery Fault Database (UFRJ)",
        "kaggle_ref": "salmanipraveen15999/mafaulda",
        "dir": DATA_ROOT / "MaFaulDa_Dataset",
        "type": "kaggle",
    },
}


def check_disk_space_gb():
    usage = shutil.disk_usage(Path.cwd().anchor)
    return usage.free / (1024 ** 3)


def download_and_extract_kaggle(key, meta):
    target_dir = meta["dir"]
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if already populated
    existing_files = list(target_dir.rglob("*"))
    data_files = [f for f in existing_files if f.is_file() and f.suffix in {".mat", ".csv", ".txt", ".parquet", ".npy"}]
    if len(data_files) > 10:
        print(f"[{key.upper()}] Already extracted: {len(data_files)} data files found in {target_dir}. Skipping download.")
        return True
    
    free_gb = check_disk_space_gb()
    print(f"\n{'='*70}")
    print(f"Downloading [{meta['name']}] from Kaggle: {meta['kaggle_ref']}")
    print(f"Current free disk space: {free_gb:.2f} GB")
    print(f"{'='*70}")
    
    # Run kaggle download with --unzip to automatically delete archive
    cmd = [
        "kaggle", "datasets", "download",
        "-d", meta["kaggle_ref"],
        "-p", str(target_dir),
        "--unzip"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error downloading {key}: {res.stderr}")
        return False
    
    print(res.stdout)
    # Check if zip file remained and clean it up
    for zip_f in target_dir.glob("*.zip"):
        print(f"Removing residual archive: {zip_f}")
        zip_f.unlink()
        
    post_files = [f for f in target_dir.rglob("*") if f.is_file()]
    print(f"[{key.upper()}] Success! Total extracted files: {len(post_files)}")
    print(f"Free disk space after extraction: {check_disk_space_gb():.2f} GB\n")
    return True


def download_seu(meta):
    target_dir = meta["dir"]
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if files already exist
    existing = list(target_dir.rglob("*.csv"))
    if len(existing) >= 8:
        print(f"[SEU] Already extracted: {len(existing)} CSV files found in {target_dir}. Skipping.")
        return True
        
    print(f"\n{'='*70}")
    print(f"Acquiring SEU Gearbox & Bearing Dataset directly from GitHub repository")
    print(f"{'='*70}")
    
    base_url = "https://raw.githubusercontent.com/cathysiyu/Mechanical-datasets/master/gearbox/bearingset/"
    bearing_files = [
        "health_20_0.csv", "health_30_2.csv",
        "inner_20_0.csv", "inner_30_2.csv",
        "outer_20_0.csv", "outer_30_2.csv",
        "ball_20_0.csv", "ball_30_2.csv",
        "comb_20_0.csv", "comb_30_2.csv"
    ]
    
    for fname in bearing_files:
        dest = target_dir / fname
        if dest.exists() and dest.stat().st_size > 1000000:
            print(f"  [SEU] {fname} already exists ({dest.stat().st_size / (1024*1024):.1f} MB).")
            continue
        url = base_url + fname
        print(f"  [SEU] Downloading {fname} from GitHub...")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  [SEU] Saved {fname} ({dest.stat().st_size / (1024*1024):.1f} MB)")
        except Exception as e:
            print(f"  [SEU] Failed to download {fname} via HTTP: {e}. Trying kaggle mirror...")
            cmd = ["kaggle", "datasets", "download", "-d", meta["kaggle_ref"], "-p", str(target_dir), "--unzip"]
            subprocess.run(cmd)
            break
            
    print(f"[SEU] Done. Files in {target_dir}: {len(list(target_dir.glob('*.csv')))}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Download all 9 rotating machinery benchmark datasets.")
    parser.add_argument("--dataset", choices=list(DATASETS_METADATA.keys()) + ["all"], default="all",
                        help="Specific dataset key to download or 'all'")
    parser.add_argument("--benchmark", choices=list(DATASETS_METADATA.keys()) + ["all"], default=None,
                        help="Alias for --dataset")
    args = parser.parse_args()
    
    selected = args.benchmark if args.benchmark is not None else args.dataset
    target_keys = list(DATASETS_METADATA.keys()) if selected == "all" else [selected]
    
    print("=" * 80)
    print("VibraDistill-Edge: 9 International Benchmark Dataset Ingestion Pipeline")
    print(f"Target datasets: {', '.join(target_keys)}")
    print(f"Available free disk space: {check_disk_space_gb():.2f} GB")
    print("=" * 80)
    
    for key in target_keys:
        meta = DATASETS_METADATA[key]
        if meta["type"] == "preinstalled":
            p = meta["dir"]
            count = len(list(p.rglob("*"))) if p.exists() else 0
            print(f"[{key.upper()}] Preinstalled local benchmark at {p}: {count} files found.")
        elif meta["type"] == "seu":
            download_seu(meta)
        elif meta["type"] == "kaggle":
            download_and_extract_kaggle(key, meta)
            
    print("\n" + "=" * 80)
    print("ALL REQUESTED BENCHMARKS STATUS AUDIT:")
    print("=" * 80)
    for key, meta in DATASETS_METADATA.items():
        p = meta["dir"]
        if p.exists():
            files = [f for f in p.rglob("*") if f.is_file()]
            total_size_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
            print(f"  {key.ljust(12)}: [READY] {len(files)} files | {total_size_mb:.1f} MB | {p}")
        else:
            print(f"  {key.ljust(12)}: [MISSING] {p}")
    print("=" * 80)


if __name__ == "__main__":
    main()
