import os
import zipfile
import shutil

VIBRA_DIR = r"D:\Gitrepo\VIbraDistill"
KAGGLE_DIR = r"D:\Gitrepo\VIbraDistill\kaggle"

# Discover Ottawa root dynamically to avoid encoding issues with special chars
OTTAWA_ROOT = None
for d in os.listdir(VIBRA_DIR):
    if "UORED" in d and os.path.isdir(os.path.join(VIBRA_DIR, d)):
        OTTAWA_ROOT = os.path.join(VIBRA_DIR, d)
        break

if not OTTAWA_ROOT:
    raise RuntimeError("Ottawa dataset folder not found! Check D:\\Gitrepo\\VIbraDistill")

print(f"Ottawa root resolved: {OTTAWA_ROOT}")
print()

def zip_dir(source_dir, zip_path):
    """Zip a directory with Linux-compliant forward slash paths."""
    print(f"  Zipping: {os.path.basename(source_dir)} -> {os.path.basename(zip_path)}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(source_dir))
                arcname = arcname.replace(os.sep, '/')
                zipf.write(file_path, arcname)
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"  Done -> {size_mb:.1f} MB")

# =======================================================
# STEP 1: CWRU Dataset
# =======================================================
print("=" * 60)
print("STEP 1: CWRU Dataset (zero-leakage bearing-wise partition)")
print("=" * 60)
zip_dir(
    os.path.join(VIBRA_DIR, "CWRU_Dataset"),
    os.path.join(KAGGLE_DIR, "cwru_dataset.zip")
)

# =======================================================
# STEP 2: Ottawa .mat files (smallest format, 288 MB actual)
#         scipy.io can read these directly - no MATLAB needed
# =======================================================
print()
print("=" * 60)
print("STEP 2: Ottawa .mat files (scipy.io readable, no MATLAB)")
print("=" * 60)
mat_dir = os.path.join(OTTAWA_ROOT, "3_MatLab_Raw_Data_Files (.mat)")
if os.path.isdir(mat_dir):
    # Count actual files inside
    file_count = sum(len(files) for _, _, files in os.walk(mat_dir))
    print(f"  Found {file_count} .mat files in Ottawa dataset")
    zip_dir(mat_dir, os.path.join(KAGGLE_DIR, "ottawa_mat_dataset.zip"))
else:
    print("  WARNING: .mat folder not found. Falling back to CSV folder.")
    csv_dir = os.path.join(OTTAWA_ROOT, "1_CSV_Raw_Data_Files (.csv)")
    zip_dir(csv_dir, os.path.join(KAGGLE_DIR, "ottawa_mat_dataset.zip"))

# =======================================================
# STEP 3: Ottawa Pre-computed Accelerometer Spectrograms
#         Already a zip, just copy it. Pre-computed = saves
#         CWT computation time on Kaggle quota.
# =======================================================
print()
print("=" * 60)
print("STEP 3: Ottawa Accelerometer Spectrograms (pre-computed)")
print("=" * 60)
# Find the spectrogram zip dynamically
spec_src = None
for f in os.listdir(OTTAWA_ROOT):
    if "Spectrogram" in f and "accelerometer" in f and f.endswith(".zip"):
        spec_src = os.path.join(OTTAWA_ROOT, f)
        break

if spec_src:
    spec_dst = os.path.join(KAGGLE_DIR, "ottawa_spectrograms_accel.zip")
    print(f"  Copying {os.path.basename(spec_src)} ({os.path.getsize(spec_src)/1024/1024:.0f} MB)...")
    shutil.copy2(spec_src, spec_dst)
    print(f"  Done -> {os.path.getsize(spec_dst)/1024/1024:.0f} MB")
else:
    print("  WARNING: Spectrogram zip not found, skipping.")

# =======================================================
# STEP 4: Python Codebase (all Phase*.py + notebook)
# =======================================================
print()
print("=" * 60)
print("STEP 4: Python Codebase (Phase*.py + Master Notebook)")
print("=" * 60)
code_zip = os.path.join(KAGGLE_DIR, "vibra_distill_code.zip")
with zipfile.ZipFile(code_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
    scripts_added = 0
    for file in sorted(os.listdir(VIBRA_DIR)):
        if file.startswith("Phase") and file.endswith(".py"):
            file_path = os.path.join(VIBRA_DIR, file)
            zipf.write(file_path, file)
            scripts_added += 1
    nb_path = os.path.join(KAGGLE_DIR, "notebook", "Master_Kaggle_Runner.ipynb")
    if os.path.exists(nb_path):
        zipf.write(nb_path, "Master_Kaggle_Runner.ipynb")
        print(f"  + Notebook included")
    print(f"  + {scripts_added} Python scripts included")
print(f"  Done -> {os.path.getsize(code_zip)/1024/1024:.1f} MB")

# =======================================================
# SUMMARY
# =======================================================
print()
print("=" * 60)
print("ALL KAGGLE UPLOAD FILES:")
print("=" * 60)
total_mb = 0
for f in sorted(os.listdir(KAGGLE_DIR)):
    fp = os.path.join(KAGGLE_DIR, f)
    if os.path.isfile(fp) and f.endswith(".zip"):
        size_mb = os.path.getsize(fp) / 1024 / 1024
        total_mb += size_mb
        print(f"  {f:<45} {size_mb:>8.1f} MB")
print(f"  {'TOTAL':<45} {total_mb:>8.1f} MB")
print()
print("KAGGLE DATASET MAPPING:")
print("  cwru_dataset.zip              -> Add as Dataset: 'cwru-dataset'")
print("  ottawa_mat_dataset.zip        -> Add as Dataset: 'ottawa-mat'")
print("  ottawa_spectrograms_accel.zip -> Add as Dataset: 'ottawa-spectrograms'")
print("  vibra_distill_code.zip        -> Add as Dataset: 'vibra-distill-code'")
