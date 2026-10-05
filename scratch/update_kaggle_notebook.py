import json
import ast

notebook_path = "notebooks/VibraDistill_Kaggle_Dual_T4.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Update Cell 4 (index 4)
cell4_code = """import os, sys, shutil, subprocess

WORKSPACE_DIR = "/kaggle/working/VIbraDistill" if os.path.exists("/kaggle") else os.getcwd()

# 1. Universal auto-detection of codebase / All-in-One Master Bundle in /kaggle/input:
ALL_IN_ONE_PATH = None
if os.path.exists("/kaggle/input"):
    for root, dirs, files in os.walk("/kaggle/input"):
        if "src" in dirs and "scripts" in dirs:
            ALL_IN_ONE_PATH = root
            break

if ALL_IN_ONE_PATH:
    print(f"Detected Codebase / All-in-One Bundle at: {ALL_IN_ONE_PATH}!")
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

subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "gdown"], check=True)

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

# Download CWRU fallback if not present
if not os.path.exists("data/CWRU_Dataset") or len(os.listdir("data/CWRU_Dataset")) < 5:
    print("CWRU dataset not found in /kaggle/input; downloading directly...")
    subprocess.run([sys.executable, "scripts/download_all_benchmarks.py", "--benchmark", "cwru"], check=True)
"""

# Update Cell 8 (index 8)
cell8_code = """import subprocess, time
from concurrent.futures import ThreadPoolExecutor

print("=" * 75)
print("LAUNCHING DUAL-GPU CONCURRENT WORKLOADS")
print("=" * 75)

def run_task(cmd, gpu_name):
    t0 = time.time()
    print(f"[{gpu_name} START] {cmd}")
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    dur = time.time() - t0
    if proc.returncode == 0:
        print(f"[{gpu_name} FINISHED] in {dur:.1f}s")
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        for l in lines[-12:]:
            print(f"  [{gpu_name}] {l}")
    else:
        print(f"[{gpu_name} FAILED] in {dur:.1f}s")
        if proc.stderr:
            print(f"[{gpu_name} STDERR]\\n{proc.stderr}")
        if proc.stdout:
            print(f"[{gpu_name} STDOUT]\\n{proc.stdout}")
        raise RuntimeError(f"{gpu_name} failed with return code {proc.returncode}")
    return proc.stdout

num_gpus = torch.cuda.device_count()
if num_gpus >= 2:
    with ThreadPoolExecutor(max_workers=2) as ex:
        f0 = ex.submit(run_task, "python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --device cuda:0", "GPU 0")
        f1 = ex.submit(run_task, "python scripts/100_runs_ablation_benchmark.py --num_runs 5 --device cuda:1", "GPU 1")
        print("Both GPU 0 and GPU 1 are active in parallel...")
        f0.result()
        f1.result()
else:
    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"Running sequentially on {dev}...")
    run_task(f"python scripts/02_train_teacher.py --epochs 30 --batch_size 64 --device {dev}", "GPU 0")
    run_task(f"python scripts/100_runs_ablation_benchmark.py --num_runs 5 --device {dev}", "GPU 0")
"""

# Update Cell 12 (index 12) to pass device
cell12_code = """dev = "cuda:0" if torch.cuda.is_available() else "cpu"
!python scripts/04_evaluate_zero_leakage.py --device {dev}
"""

nb['cells'][4]['source'] = [line + '\n' for line in cell4_code.splitlines()]
nb['cells'][8]['source'] = [line + '\n' for line in cell8_code.splitlines()]
nb['cells'][12]['source'] = [line + '\n' for line in cell12_code.splitlines()]

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Notebook updated successfully!")
