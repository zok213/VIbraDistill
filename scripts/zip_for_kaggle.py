"""
VibraDistill-Edge: Kaggle Dataset Packaging Utility.

Packages dataset folders from data/ into clean, Linux-compliant .zip archives
and generates Kaggle `dataset-metadata.json` for direct 1-click upload
via Kaggle Web UI or Kaggle CLI (`kaggle datasets create -p <dir>`).
"""

import os
import sys
import json
import zipfile
import argparse
import time

DATA_REGISTRY = {
    'cwru': {
        'folder': 'CWRU_Dataset',
        'title': 'VibraDistill - CWRU Bearing Dataset',
        'slug': 'vibradistill-cwru-dataset',
        'desc': 'Case Western Reserve University (CWRU) 12k/48k Drive End vibration signals with zero-leakage partitions.'
    },
    'mfpt': {
        'folder': 'MFPT_Dataset',
        'title': 'VibraDistill - MFPT Bearing Dataset',
        'slug': 'vibradistill-mfpt-dataset',
        'desc': 'Machinery Failure Prevention Technology (MFPT) baseline and fault condition vibration data.'
    },
    'seu': {
        'folder': 'SEU_Dataset',
        'title': 'VibraDistill - SEU Drivetrain Dynamic Simulator Dataset',
        'slug': 'vibradistill-seu-dataset',
        'desc': 'Southeast University (SEU) gearbox and bearing vibration fault dataset under varying speeds and loads.'
    },
    'phm2009': {
        'folder': 'PHM2009_Gearbox_Dataset',
        'title': 'VibraDistill - PHM 2009 Gearbox Challenge Dataset',
        'slug': 'vibradistill-phm2009-dataset',
        'desc': 'PHM 2009 Gearbox data with helical and spur gears under 30-50 Hz loads.'
    },
    'rotating': {
        'folder': 'Rotating_Machine_Faults_Dataset',
        'title': 'VibraDistill - Rotating Machine Faults Dataset',
        'slug': 'vibradistill-rotating-machine-faults',
        'desc': 'Laboratory rotor testbed vibration signals across normal, unbalance, misalignment, and bearing faults.'
    },
    'xjtu_sy': {
        'folder': 'XJTU-SY_Dataset',
        'title': 'VibraDistill - XJTU-SY Bearing Run-to-Failure Dataset',
        'slug': 'vibradistill-xjtu-sy-dataset',
        'desc': 'Xi\'an Jiaotong University & Changxing Sumyoung run-to-failure bearing vibration dataset across 15 full lifespans.'
    },
    'pronostia': {
        'folder': 'PRONOSTIA_FEMTO_Dataset',
        'title': 'VibraDistill - PRONOSTIA FEMTO-ST Run-to-Failure Dataset',
        'slug': 'vibradistill-pronostia-femto-dataset',
        'desc': 'IEEE PHM 2012 Prognostic Challenge PRONOSTIA bearing run-to-failure acceleration signals.'
    },
    'nasa_ims': {
        'folder': 'NASA_IMS_Dataset',
        'title': 'VibraDistill - NASA IMS Bearing Degradation Dataset',
        'slug': 'vibradistill-nasa-ims-dataset',
        'desc': 'NASA Intelligent Maintenance Systems (IMS) endurance run-to-failure vibration data.'
    },
    'paderborn': {
        'folder': 'Paderborn_Dataset',
        'title': 'VibraDistill - Paderborn University Bearing Dataset',
        'slug': 'vibradistill-paderborn-dataset',
        'desc': 'Paderborn University modular bearing testbench data with artificially induced and real accelerated damage.'
    },
    'mafaulda': {
        'folder': 'MaFaulDa_Dataset',
        'title': 'VibraDistill - MaFaulDa Machinery Fault Database',
        'slug': 'vibradistill-mafaulda-dataset',
        'desc': 'Machinery Fault Database (MaFaulDa) 6-accelerometer signals under multiple operating regimes.'
    },
    'ottawa': {
        'folder': 'Ottawa_Dataset',
        'title': 'VibraDistill - Ottawa University Bearing Dataset',
        'slug': 'vibradistill-ottawa-dataset',
        'desc': 'University of Ottawa bearing vibration dataset under time-varying rotational speeds.'
    }
}


def zip_directory(source_dir: str, output_zip: str):
    """Zips a folder with Unix forward slashes for native Kaggle compatibility."""
    t0 = time.time()
    total_files = sum(len(fs) for _, _, fs in os.walk(source_dir))
    print(f"  Compressing {total_files} files from: {source_dir}")
    print(f"  Target: {output_zip}")
    
    os.makedirs(os.path.dirname(output_zip), exist_ok=True)
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        count = 0
        for root, _, files in os.walk(source_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, os.path.dirname(source_dir))
                rel_path = rel_path.replace(os.sep, '/')
                zipf.write(abs_path, rel_path)
                count += 1
                if count % 2000 == 0 or count == total_files:
                    sys.stdout.write(f"\r  Progress: {count}/{total_files} files ({count/total_files*100:.1f}%)")
                    sys.stdout.flush()
    print()
    size_mb = os.path.getsize(output_zip) / (1024 * 1024)
    print(f"  Completed in {time.time()-t0:.1f}s -> Archive Size: {size_mb:.2f} MB\n")
    return size_mb


def write_kaggle_metadata(target_dir: str, title: str, slug: str, desc: str):
    """Generates Kaggle dataset-metadata.json for `kaggle datasets create`."""
    metadata = {
        "title": title,
        "id": f"yourusername/{slug}",
        "licenses": [{"name": "CC0-1.0"}],
        "description": desc
    }
    meta_path = os.path.join(target_dir, "dataset-metadata.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    return meta_path


def main():
    parser = argparse.ArgumentParser(description="Package dataset folders for Kaggle upload")
    parser.add_argument('--dataset', default='cwru', 
                        help="Key of dataset to zip (cwru, mfpt, seu, phm2009, rotating, xjtu_sy, pronostia, nasa_ims, paderborn, mafaulda, ottawa, all_core, all)")
    parser.add_argument('--data_dir', default='data', help="Path to raw data directory")
    parser.add_argument('--output_dir', default='kaggle/datasets', help="Output directory for zip archives")
    args = parser.parse_args()

    print("=" * 75)
    print("  VIBRADISTILL-EDGE: KAGGLE DATASET PACKAGING ENGINE")
    print("=" * 75)

    datasets_to_process = []
    if args.dataset == 'all_core':
        datasets_to_process = ['cwru', 'mfpt', 'rotating', 'seu', 'phm2009']
    elif args.dataset == 'all':
        datasets_to_process = list(DATA_REGISTRY.keys())
    elif args.dataset in DATA_REGISTRY:
        datasets_to_process = [args.dataset]
    else:
        # Check if direct directory name passed
        matched = False
        for k, v in DATA_REGISTRY.items():
            if v['folder'].lower() == args.dataset.lower():
                datasets_to_process = [k]
                matched = True
                break
        if not matched:
            print(f"Error: Unknown dataset '{args.dataset}'. Available keys: {list(DATA_REGISTRY.keys()) + ['all_core', 'all']}")
            sys.exit(1)

    summary = []
    for key in datasets_to_process:
        info = DATA_REGISTRY[key]
        src_path = os.path.join(args.data_dir, info['folder'])
        if not os.path.exists(src_path):
            print(f"Warning: Folder '{src_path}' not found on disk. Skipping.")
            continue
        
        target_dir = os.path.join(args.output_dir, info['slug'])
        os.makedirs(target_dir, exist_ok=True)
        zip_path = os.path.join(target_dir, f"{info['slug']}.zip")
        
        print(f"\n[{key.upper()}] Packaging {info['title']}...")
        size_mb = zip_directory(src_path, zip_path)
        meta_file = write_kaggle_metadata(target_dir, info['title'], info['slug'], info['desc'])
        
        summary.append({
            'key': key,
            'title': info['title'],
            'slug': info['slug'],
            'zip_path': zip_path,
            'size_mb': round(size_mb, 2),
            'target_dir': target_dir
        })

    print("=" * 75)
    print("KAGGLE PACKAGING SUMMARY:")
    for s in summary:
        print(f"  * {s['title']}: {s['size_mb']} MB -> {s['zip_path']}")
    print("\nHOW TO UPLOAD TO KAGGLE:")
    print("  Option 1 (Web UI): Go to https://www.kaggle.com/datasets/new and drag & drop the .zip file.")
    print("  Option 2 (Kaggle CLI):")
    print("     1. Edit `yourusername` in `dataset-metadata.json`")
    print("     2. Run: kaggle datasets create -p <target_dir>")
    print("=" * 75)


if __name__ == '__main__':
    main()
