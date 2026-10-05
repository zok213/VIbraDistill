"""
MFPT Bearing Dataset Loader with Automatic 12 kHz Polyphase Resampling.
Loads Machinery Failure Prevention Technology (MFPT) benchmark data:
  - Baseline conditions -> Class 0 (Normal)
  - Inner race faults   -> Class 2 (Inner Race)
  - Outer race faults   -> Class 3 (Outer Race)
Resamples signals from original 97,656 Hz to unified 12,000 Hz so spectrum bins
align with the Gowin NPU 12-way systolic engine.
"""

import os
import glob
import numpy as np
import scipy.io as sio
import torch
from torch.utils.data import Dataset

from src.dsp.pipeline import StreamingDSPPipeline
from src.dsp.kinematics import BearingGeometry
from src.dsp.resample import resample_vibration_signal

# Rexnord / Nice 1012 bearing geometry used in MFPT
MFPT_BEARING_GEOM = BearingGeometry(
    n_balls=16,
    ball_diameter_mm=7.92,
    pitch_diameter_mm=35.0,
    contact_angle_deg=0.0
)

class MFPTBearingDataset(Dataset):
    def __init__(self, data_dir: str = 'data/MFPT_Dataset', split: str = 'all',
                 window_size: int = 512, stride: int = 256, max_samples_per_file: int = 50):
        super(MFPTBearingDataset, self).__init__()
        self.data_dir = os.path.abspath(data_dir)
        self.window_size = window_size
        self.stride = stride
        self.max_samples = max_samples_per_file
        
        # We process at unified 12 kHz
        self.dsp = StreamingDSPPipeline(fs=12000.0, window_size=window_size, bearing_geom=MFPT_BEARING_GEOM)
        
        self.samples = []
        self._load_all_files()

    def _load_all_files(self):
        root = os.path.join(self.data_dir, "MFPT Fault Data Sets")
        if not os.path.exists(root):
            # Check alternative path
            root = self.data_dir
        
        categories = [
            ("1 - Three Baseline Conditions", 0),
            ("2 - Three Outer Race Fault Conditions", 3),
            ("3 - Seven More Outer Race Fault Conditions", 3),
            ("4 - Seven Inner Race Fault Conditions", 2)
        ]
        
        for folder_name, label in categories:
            folder_path = os.path.join(root, folder_name)
            if not os.path.exists(folder_path):
                continue
            mat_files = sorted(glob.glob(os.path.join(folder_path, "*.mat")))
            for fpath in mat_files:
                try:
                    d = sio.loadmat(fpath)
                    if 'bearing' not in d:
                        continue
                    b = d['bearing']
                    sr = float(b['sr'][0, 0][0, 0])
                    rate = float(b['rate'][0, 0][0, 0])
                    raw_signal = b['gs'][0, 0].reshape(-1)
                    
                    # Resample from 97.656 kHz (or 48.828 kHz) to 12.0 kHz
                    resampled = resample_vibration_signal(raw_signal, orig_fs=sr, target_fs=12000.0)
                    
                    # Slice into windows
                    n_windows = min(self.max_samples, (len(resampled) - self.window_size) // self.stride)
                    for w_idx in range(n_windows):
                        start = w_idx * self.stride
                        chunk = resampled[start:start + self.window_size]
                        self.samples.append({
                            'signal': chunk,
                            'rpm': rate * 60.0,
                            'label': label,
                            'source': os.path.basename(fpath)
                        })
                except Exception as e:
                    print(f"Warning loading {fpath}: {e}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        sig = item['signal']
        rpm = item['rpm']
        
        feat = self.dsp.process_window(sig, rpm=rpm)
        spec = torch.tensor(feat['spectrum'], dtype=torch.float32).unsqueeze(0)
        prior = torch.tensor(feat['prior'], dtype=torch.float32)
        label = torch.tensor(item['label'], dtype=torch.long)
        
        return {
            'spectrum': spec,
            'prior': prior,
            'label': label,
            'rpm': rpm,
            'source': item['source']
        }
