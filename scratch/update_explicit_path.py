import json

path = "notebooks/VibraDistill_Kaggle_Dual_T4.ipynb"
with open(path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

cell4_code = """import os, sys, shutil, subprocess

WORKSPACE_DIR = "/kaggle/working/VIbraDistill" if os.path.exists("/kaggle") else os.getcwd()

# 1. Explicit Candidate Paths (matching your uploaded dataset slug & URLs)
CANDIDATE_PATHS = [
    "/kaggle/input/datasets/zok213/vibradistill-ai1",
    "/kaggle/input/datasets/zok213/vibradistill_ai1",
    "/kaggle/input/vibradistill_ai1",
    "/kaggle/input/vibradistill-ai1",
    "/kaggle/input/vibradistill-all-in-one",
]

ALL_IN_ONE_PATH = None
for cand in CANDIDATE_PATHS:
    if os.path.exists(cand) and os.path.exists(os.path.join(cand, "src")):
        ALL_IN_ONE_PATH = cand
        break

# 2. Universal Auto-Scan in /kaggle/input (finds any directory containing src and scripts)
if not ALL_IN_ONE_PATH and os.path.exists("/kaggle/input"):
    for root, dirs, files in os.walk("/kaggle/input"):
        if "src" in dirs and "scripts" in dirs:
            ALL_IN_ONE_PATH = root
            break

if ALL_IN_ONE_PATH:
    print(f"✅ Đã tìm thấy Master Bundle tại: {ALL_IN_ONE_PATH}")
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    for item in os.listdir(ALL_IN_ONE_PATH):
        src_item = os.path.join(ALL_IN_ONE_PATH, item)
        dst_item = os.path.join(WORKSPACE_DIR, item)
        if item == "data":
            os.makedirs(dst_item, exist_ok=True)
            for d_name in os.listdir(src_item):
                d_src = os.path.join(src_item, d_name)
                d_dst = os.path.join(dst_item, d_name)
                if not os.path.exists(d_dst):
                    try:
                        os.symlink(d_src, d_dst)
                    except Exception:
                        shutil.copytree(d_src, d_dst)
        elif not os.path.exists(dst_item):
            if os.path.isdir(src_item):
                shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
            else:
                shutil.copy2(src_item, dst_item)
    os.chdir(WORKSPACE_DIR)
elif os.path.exists("/kaggle"):
    if not os.path.exists(WORKSPACE_DIR):
        subprocess.run(["git", "clone", "https://github.com/zok213/VIbraDistill.git", WORKSPACE_DIR], check=True)
        os.chdir(WORKSPACE_DIR)
    else:
        os.chdir(WORKSPACE_DIR)
        subprocess.run(["git", "pull"], check=True)

# Install requirements safely without breaking pre-installed Kaggle packages
if os.path.exists("requirements.txt"):
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade-strategy", "only-if-needed"], check=False)

# Link Kaggle Input Datasets if attached individually
KAGGLE_INPUT_DIR = "/kaggle/input"
os.makedirs("data", exist_ok=True)

DATASET_MAP = {
    "vibradistill-cwru-dataset": "CWRU_Dataset",
    "cwru": "CWRU_Dataset",
    "vibradistill-mfpt-dataset": "MFPT_Dataset",
    "vibradistill-seu-dataset": "SEU_Dataset",
    "vibradistill-phm2009-dataset": "PHM2009_Gearbox_Dataset",
    "vibradistill-rotating-machine-faults": "Rotating_Machine_Faults_Dataset",
    "vibradistill-xjtu-sy-dataset": "XJTU-SY_Dataset",
    "vibradistill-pronostia-femto-dataset": "PRONOSTIA_FEMTO_Dataset"
}

if os.path.exists(KAGGLE_INPUT_DIR):
    for k_name in os.listdir(KAGGLE_INPUT_DIR):
        k_lower = k_name.lower()
        for pattern, local_target in DATASET_MAP.items():
            if pattern in k_lower:
                src = os.path.join(KAGGLE_INPUT_DIR, k_name)
                sub = [os.path.join(src, f) for f in os.listdir(src) if os.path.isdir(os.path.join(src, f))]
                actual_src = sub[0] if (len(sub) == 1 and local_target.lower() in sub[0].lower()) else src
                dst = os.path.join("data", local_target)
                if not os.path.exists(dst):
                    try:
                        os.symlink(actual_src, dst)
                        print(f"Linked: {src} -> {dst}")
                    except Exception:
                        shutil.copytree(actual_src, dst)
                        print(f"Copied: {src} -> {dst}")

# Verify CWRU dataset presence (check for actual .mat files in Train_7mil)
cwru_train = "data/CWRU_Dataset/Train_7mil"
if not os.path.exists(cwru_train) or len(os.listdir(cwru_train)) == 0:
    print("CWRU dataset not found in local workspace; downloading directly...")
    subprocess.run([sys.executable, "scripts/download_all_benchmarks.py", "--dataset", "cwru"], check=True)
else:
    print(f"✅ CWRU dataset ready ({len(os.listdir(cwru_train))} files in Train_7mil)")

print(f"\\n[STATUS] Active Working Directory: {os.getcwd()}")
if os.path.exists("data"):
    print(f"[STATUS] Mounted Datasets in data/: {sorted(os.listdir('data'))}")
"""

nb['cells'][4]['source'] = [line + '\n' for line in cell4_code.splitlines()]

with open(path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Updated Cell 4 successfully!")
