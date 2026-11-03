"""
PRONOSTIA (FEMTO-ST) Accelerated Run-to-Failure Dataset Loader for Bearing RUL Prognostics.
Platform: FEMTO-ST PRONOSTIA testbed (IEEE PHM 2012 Data Challenge).
Bearing: NSK 6804RS Miniature Ball Bearing:
  - Number of balls: 13
  - Ball diameter: 3.5 mm
  - Pitch diameter: 26.0 mm (Mean of 20mm inner, 32mm outer)
  - Contact angle: 0.0 deg
  - Shaft speed: 1800 RPM (30.0 Hz)
  - Radial load: 4000 N
  - Sampling rate: 25,600 Hz (0.1s snapshots recorded every 10s = 2560 samples/snapshot)
"""

import os
import glob
import numpy as np
import torch
from torch.utils.data import Dataset

from src.dsp.pipeline import StreamingDSPPipeline
from src.dsp.kinematics import BearingGeometry

PRONOSTIA_NSK6804RS_GEOMETRY = BearingGeometry(
    n_balls=13,
    ball_diameter_mm=3.5,
    pitch_diameter_mm=26.0,
    contact_angle_deg=0.0
)

class PronostiaBearingDataset(Dataset):
    """
    PRONOSTIA FEMTO-ST Dataset for Real Bearing RUL Prognostics.
    Loads real vibration snapshots from Learning_set (Bearing1_1, Bearing1_2) and Full_Test_Set (Bearing1_3).
    """
    def __init__(self, data_root: str = "data/PRONOSTIA_FEMTO_Dataset",
                 bearings=('Bearing1_1', 'Bearing1_2'),
                 split: str = 'train',
                 max_samples_per_bearing: int = 500,
                 cache_dir: str = "data/cache/pronostia"):
        super(PronostiaBearingDataset, self).__init__()
        self.data_root = os.path.abspath(data_root)
        self.split = split.lower()
        self.bearings = bearings
        self.max_samples_per_bearing = max_samples_per_bearing
        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

        self.fs = 25600.0
        self.dsp = StreamingDSPPipeline(fs=self.fs, window_size=512, bearing_geom=PRONOSTIA_NSK6804RS_GEOMETRY)

        # Compute theoretical kinematic prior for NSK 6804RS at 1800 RPM (30 Hz)
        # BPFO = 13/2 * 30 * (1 - 3.5/26) = 168.75 Hz
        # BPFI = 13/2 * 30 * (1 + 3.5/26) = 221.25 Hz
        # BSF  = 26 / (2*3.5) * 30 * (1 - (3.5/26)^2) = 109.38 Hz
        # FTF  = 1/2 * 30 * (1 - 3.5/26) = 12.98 Hz
        fr = 30.0
        bpfo = (13.0 / 2.0) * fr * (1.0 - 3.5 / 26.0) / self.fs
        bpfi = (13.0 / 2.0) * fr * (1.0 + 3.5 / 26.0) / self.fs
        bsf = (26.0 / (2.0 * 3.5)) * fr * (1.0 - (3.5 / 26.0)**2) / self.fs
        ftf = 0.5 * fr * (1.0 - 3.5 / 26.0) / self.fs
        self.kinematic_prior = torch.tensor([bpfo, bpfi, bsf, ftf], dtype=torch.float32)

        self.samples = []
        self._load_or_build_cache()

    def _load_or_build_cache(self):
        cache_name = f"pronostia_{'_'.join(self.bearings)}_{self.max_samples_per_bearing}.pt"
        cache_path = os.path.join(self.cache_dir, cache_name)

        if os.path.exists(cache_path):
            cached = torch.load(cache_path, weights_only=False)
            self.samples = cached
            print(f"[PronostiaLoader] Loaded {len(self.samples)} samples from cache: {cache_path}")
            return

        print(f"[PronostiaLoader] Extracting raw features from PRONOSTIA CSV files for: {self.bearings}...")
        base_challenge = os.path.join(self.data_root, 'ieee-phm-2012-data-challenge-dataset-master')

        for b_name in self.bearings:
            # Search in Learning_set or Full_Test_Set
            b_dir = os.path.join(base_challenge, 'Learning_set', b_name)
            if not os.path.exists(b_dir):
                b_dir = os.path.join(base_challenge, 'Full_Test_Set', b_name)
            if not os.path.exists(b_dir):
                print(f"[PronostiaLoader] WARNING: Directory not found for {b_name}: {b_dir}")
                continue

            csv_files = sorted(glob.glob(os.path.join(b_dir, 'acc_*.csv')))
            total_snaps = len(csv_files)
            if total_snaps == 0:
                continue

            step = max(1, total_snaps // self.max_samples_per_bearing)
            sub_files = csv_files[::step][:self.max_samples_per_bearing]

            print(f"  * {b_name}: {total_snaps} snapshots total, subsampled {len(sub_files)} points (step={step})")

            for snap_idx, fpath in enumerate(sub_files):
                # Calculate real ground-truth RUL fraction [1.0 -> 0.0]
                # Find original file index
                base_fname = os.path.splitext(os.path.basename(fpath))[0] # acc_00001
                orig_idx = int(base_fname.split('_')[-1]) if '_' in base_fname else snap_idx + 1
                rul_fraction = max(0.0, float(total_snaps - orig_idx) / float(total_snaps))

                try:
                    data = np.genfromtxt(fpath, delimiter=',', usecols=(4,)) # column 4 = horiz acc
                    if len(data) < 512:
                        continue
                    # Take central 512-sample window
                    center = len(data) // 2
                    chunk = data[center - 256 : center + 256].astype(np.float32)

                    res = self.dsp.process_window(chunk, rpm=1800.0)
                    spec = res['spectrum'] # [257]

                    self.samples.append({
                        'spectrum': torch.from_numpy(spec).float(),
                        'prior': self.kinematic_prior.clone(),
                        'rul': torch.tensor([rul_fraction], dtype=torch.float32),
                        'rms': float(np.sqrt(np.mean(chunk**2))),
                        'kurtosis': float(np.mean((chunk - np.mean(chunk))**4) / (np.std(chunk)**4 + 1e-9)),
                        'bearing': b_name,
                        'snap_idx': orig_idx,
                        'total_snaps': total_snaps
                    })
                except Exception as e:
                    continue

        torch.save(self.samples, cache_path)
        print(f"[PronostiaLoader] Cached {len(self.samples)} samples to: {cache_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]
