"""
Deep inspection of the remaining 6 datasets:
Rotating-Machine, MaFaulDa, Paderborn, Ottawa, PHM2009, NASA-IMS
"""
import os
import glob
import numpy as np

def check_nasa():
    p = "data/NASA_IMS_Dataset"
    data_files = [os.path.join(r, f) for r, _, fs in os.walk(p) for f in fs if not f.endswith(('.pdf', '.txt', '.zip', '.html'))]
    print(f"[NASA IMS] Found {len(data_files)} data files.")
    if data_files:
        sample = data_files[0]
        # read first 5 lines
        with open(sample, 'r') as f:
            lines = [f.readline().strip() for _ in range(3)]
        print(f"  Sample {os.path.basename(sample)} lines:", lines)
        try:
            arr = np.loadtxt(sample, max_rows=5)
            print(f"  Shape: {arr.shape} | Channels: {arr.shape[1] if arr.ndim > 1 else 1}")
        except Exception as e:
            print("  Load error:", e)

def check_mafaulda():
    p = "data/MaFaulDa_Dataset"
    import scipy.io as sio
    mat_files = [f for f in glob.glob(os.path.join(p, "**", "*.mat"), recursive=True) if os.path.isfile(f)]
    print(f"\n[MaFaulDa] Found {len(mat_files)} MAT files:")
    for f in mat_files:
        print(f"  {os.path.basename(f)} ({os.path.getsize(f)/1024/1024:.2f} MB)")
    if mat_files:
        try:
            d = sio.loadmat(mat_files[0])
            keys = [k for k in d.keys() if not k.startswith('__')]
            print(f"  Sample {os.path.basename(mat_files[0])} keys: {keys}")
            for k in keys[:2]:
                arr = d[k]
                print(f"    {k}: shape {getattr(arr, 'shape', None)} dtype {getattr(arr, 'dtype', None)}")
        except Exception as e:
            print("  Load error:", e)

def check_rotating():
    p = "data/Rotating_Machine_Faults_Dataset"
    import scipy.io as sio
    mat_files = [f for f in glob.glob(os.path.join(p, "**", "*.mat"), recursive=True) if os.path.isfile(f)]
    print(f"\n[Rotating Machine Faults] Found {len(mat_files)} MAT files:")
    if mat_files:
        try:
            d = sio.loadmat(mat_files[0])
            keys = [k for k in d.keys() if not k.startswith('__')]
            print(f"  Sample {os.path.basename(mat_files[0])} keys: {keys}")
            for k in keys[:2]:
                arr = d[k]
                print(f"    {k}: shape {getattr(arr, 'shape', None)} dtype {getattr(arr, 'dtype', None)}")
        except Exception as e:
            print("  Load error:", e)

def check_phm2009():
    p = "data/PHM2009_Gearbox_Dataset"
    csv_files = [f for f in glob.glob(os.path.join(p, "**", "*.csv"), recursive=True) if os.path.isfile(f)]
    print(f"\n[PHM2009 Gearbox] Found {len(csv_files)} CSV files:")
    for f in csv_files[:4]:
        print(f"  {os.path.relpath(f, p)} ({os.path.getsize(f)/1024/1024:.2f} MB)")
    if csv_files:
        with open(csv_files[0], 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline().strip() for _ in range(3)]
        print("  Sample CSV lines:", lines)
        try:
            arr = np.genfromtxt(csv_files[0], delimiter=',', max_rows=5)
            print(f"  Sample shape: {arr.shape} | Channels: {arr.shape[1] if arr.ndim > 1 else 1}")
        except Exception as e:
            print("  CSV load error:", e)

def check_paderborn():
    p = "data/Paderborn_Dataset"
    import scipy.io as sio
    mat_files = [f for f in glob.glob(os.path.join(p, "**", "*.mat"), recursive=True) if os.path.isfile(f)]
    print(f"\n[Paderborn] Found {len(mat_files)} MAT files.")
    if mat_files:
        sample = mat_files[0]
        d = sio.loadmat(sample)
        k = [key for key in d.keys() if not key.startswith('__')][0]
        obj = d[k]
        print(f"  Sample MAT key: {k} | type: {type(obj)} | fields: {obj.dtype.names if hasattr(obj, 'dtype') else 'N/A'}")
        if hasattr(obj, 'dtype') and obj.dtype.names:
            for field in obj.dtype.names[:5]:
                val = obj[field][0, 0]
                print(f"    Field: {field} -> type: {type(val)} shape: {getattr(val, 'shape', None)}")

def check_ottawa():
    p = "data/Ottawa_Dataset"
    import scipy.io as sio
    mat_files = [f for f in glob.glob(os.path.join(p, "**", "*.mat"), recursive=True) if os.path.isfile(f)]
    print(f"\n[Ottawa] Found {len(mat_files)} MAT files.")
    if mat_files:
        sample = mat_files[0]
        d = sio.loadmat(sample)
        keys = [key for key in d.keys() if not key.startswith('__')]
        print(f"  Sample MAT keys: {keys}")
        for k in keys[:3]:
            arr = d[k]
            print(f"    {k}: shape {arr.shape} dtype {arr.dtype}")

if __name__ == '__main__':
    check_nasa()
    check_mafaulda()
    check_rotating()
    check_phm2009()
    check_paderborn()
    check_ottawa()
