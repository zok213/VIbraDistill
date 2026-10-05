"""
XJTU-SY Run-to-Failure Bearing Dataset Loader for Remaining Useful Life (RUL) Prognostics.
Loads accelerated degradation experiments across 15 bearings under 3 operating conditions:
  - Condition 1: 35.0 Hz (2100 RPM), 12 kN radial load (Bearing1_1 to Bearing1_5)
  - Condition 2: 37.5 Hz (2250 RPM), 11 kN radial load (Bearing2_1 to Bearing2_5)
  - Condition 3: 40.0 Hz (2400 RPM), 10 kN radial load (Bearing3_1 to Bearing3_5)

Calculates ground-truth RUL fractions [1.0 -> 0.0] and extracts envelope spectra
for joint diagnostic-prognostic training with Adaptive Conformal Prediction (ACP).
"""

import os
import glob
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

from src.dsp.pipeline import StreamingDSPPipeline
from src.dsp.kinematics import BearingGeometry

# LDK UER204 Bearing Physical Geometry (used in XJTU-SY test rig)
LDK_UER204_GEOMETRY = BearingGeometry(
    n_balls=8,
    ball_diameter_mm=7.92,     # 0.312 in
    pitch_diameter_mm=34.55,   # 1.360 in
    contact_angle_deg=0.0
)

# Operating Conditions metadata: (Shaft Hz, RPM, Load kN)
CONDITION_META = {
    '35Hz12kN':   {'hz': 35.0,   'rpm': 2100.0, 'load_kn': 12.0},
    '37.5Hz11kN': {'hz': 37.5,   'rpm': 2250.0, 'load_kn': 11.0},
    '40Hz10kN':   {'hz': 40.0,   'rpm': 2400.0, 'load_kn': 10.0},
}

class XJTUSYBearingDataset(Dataset):
    """
    XJTU-SY Run-to-Failure Dataset for Bearing Prognostics.
    """
    def __init__(self, raw_dir: str, condition: str = '35Hz12kN', 
                 train_bearings=('Bearing1_1', 'Bearing1_2', 'Bearing1_3'),
                 test_bearings=('Bearing1_4', 'Bearing1_5'),
                 split: str = 'train', window_size: int = 512,
                 stride_per_csv: int = 4, max_samples_per_bearing: int = 150):
        super(XJTUSYBearingDataset, self).__init__()
        self.raw_dir = os.path.abspath(raw_dir)
        self.condition = condition
        self.split = split.lower()
        self.window_size = window_size
        
        target_bearings = train_bearings if self.split == 'train' else test_bearings
        self.meta = CONDITION_META.get(condition, {'rpm': 2100.0})
        self.dsp = StreamingDSPPipeline(fs=12000.0, window_size=window_size, bearing_geom=LDK_UER204_GEOMETRY)
        
        self.samples = []
        self._load_bearings(target_bearings, stride_per_csv, max_samples_per_bearing)
        
    def _load_bearings(self, target_bearings, stride_per_csv, max_samples_per_bearing):
        cond_dir = os.path.join(self.raw_dir, 'XJTU-SY_Bearing_Datasets', self.condition)
        if not os.path.exists(cond_dir):
            # Fallback direct search
            cond_dir = os.path.join(self.raw_dir, self.condition)
            
        if not os.path.exists(cond_dir):
            print(f"Warning: Directory {cond_dir} not yet accessible.")
            return
            
        for b_name in target_bearings:
            b_path = os.path.join(cond_dir, b_name)
            if not os.path.exists(b_path):
                continue
                
            csv_files = sorted(
                glob.glob(os.path.join(b_path, '*.csv')),
                key=lambda x: int(os.path.splitext(os.path.basename(x))[0]) if os.path.splitext(os.path.basename(x))[0].isdigit() else 0
            )
            total_lifespan = len(csv_files)
            if total_lifespan == 0:
                continue
                
            step = max(1, total_lifespan // max_samples_per_bearing)
            sub_files = csv_files[::step]
            
            for file_idx, f_path in enumerate(sub_files):
                actual_step_idx = int(os.path.splitext(os.path.basename(f_path))[0])
                rul_fraction = max(0.0, min(1.0, (total_lifespan - actual_step_idx) / float(total_lifespan)))
                
                try:
                    df = pd.read_csv(f_path, nrows=self.window_size * 2)
                    col = df.columns[0] # Horizontal vibration channel
                    sig = df[col].values.astype(np.float32)
                    
                    if len(sig) >= self.window_size:
                        win = sig[:self.window_size]
                        dsp_out = self.dsp.process_window(win, rpm=self.meta['rpm'])
                        
                        self.samples.append({
                            'spectrum': torch.from_numpy(dsp_out['spectrum']).unsqueeze(0), # [1, 257]
                            'prior': torch.from_numpy(dsp_out['prior']),                    # [4]
                            'rul': torch.tensor([rul_fraction], dtype=torch.float32),      # [1]
                            'bearing': b_name,
                            'step': actual_step_idx,
                            'lifespan': total_lifespan
                        })
                except Exception as e:
                    pass
                    
        print(f"XJTU-SY [{self.split.upper()}]: Loaded {len(self.samples)} samples from {target_bearings}.")
        
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        return self.samples[idx]

def get_xjtu_sy_dataloaders(raw_dir: str, batch_size: int = 32):
    """Factory function for XJTU-SY RUL prognostics dataloaders."""
    train_set = XJTUSYBearingDataset(raw_dir, split='train')
    test_set = XJTUSYBearingDataset(raw_dir, split='test')
    
    return {
        'train': DataLoader(train_set, batch_size=batch_size, shuffle=True) if len(train_set) > 0 else None,
        'test': DataLoader(test_set, batch_size=batch_size, shuffle=False) if len(test_set) > 0 else None,
        'train_set': train_set,
        'test_set': test_set
    }
