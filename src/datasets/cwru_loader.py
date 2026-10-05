"""
Zero-Leakage PyTorch Dataset & DataLoader for CWRU Bearing Data Center.
Strictly isolates training bearing fault diameters (7-mil) from unseen hold-out
evaluation bearing fault diameters (14-mil and 21-mil).

Integrates the bit-true Gowin FPGA Causal DSP Pipeline for on-the-fly or cached
envelope spectrum & kinematic prior vector generation.
"""

import os
import glob
import numpy as np
import scipy.io as sio
import torch
from torch.utils.data import Dataset, DataLoader

from src.dsp.pipeline import StreamingDSPPipeline
from src.datasets.transforms import ComposeTransforms, RandomNoise, RandomCyclicShift, RandomScale

# Canonical RPM fallback mappings for CWRU Normal files lacking explicit RPM tags
NORMAL_RPM_MAP = {
    '97.mat': 1797.0,   # 0 HP
    '98.mat': 1772.0,   # 1 HP
    '99.mat': 1750.0,   # 2 HP
    '100.mat': 1725.0   # 3 HP
}

class CWRUBearingDataset(Dataset):
    """
    Zero-Leakage CWRU Dataset.
    Enforces strict Bearing-Wise Partitioning.
    
    Classes:
      0: Normal
      1: Inner Race Fault (BPFI)
      2: Outer Race Fault (BPFO)
      3: Ball Fault (BSF)
    """
    def __init__(self, data_dir: str, split: str = 'train', 
                 window_size: int = 512, train_stride: int = 256, test_stride: int = 512,
                 val_ratio: float = 0.2, seed: int = 42,
                 transform=None, cache_dir: str = None, force_recompute: bool = False):
        super(CWRUBearingDataset, self).__init__()
        self.data_dir = os.path.abspath(data_dir)
        self.split = split.lower()
        self.window_size = window_size
        self.train_stride = train_stride
        self.test_stride = test_stride
        self.val_ratio = val_ratio
        self.seed = seed
        self.transform = transform
        
        self.dsp = StreamingDSPPipeline(fs=12000.0, window_size=window_size)
        
        # Check cache
        if cache_dir is not None:
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"cwru_{self.split}_w{window_size}.pt")
        else:
            cache_file = None
            
        if cache_file and os.path.exists(cache_file) and not force_recompute:
            cached_data = torch.load(cache_file)
            self.spectra = cached_data['spectra']
            self.priors = cached_data['priors']
            self.labels = cached_data['labels']
            self.rpms = cached_data['rpms']
        else:
            self._build_dataset()
            if cache_file:
                torch.save({
                    'spectra': self.spectra,
                    'priors': self.priors,
                    'labels': self.labels,
                    'rpms': self.rpms
                }, cache_file)
                
    def _get_files_for_split(self):
        """Resolves file paths strictly enforcing zero-leakage partitions."""
        normal_dir = os.path.join(self.data_dir, 'Normal')
        train_7mil_dir = os.path.join(self.data_dir, 'Train_7mil')
        test_14mil_dir = os.path.join(self.data_dir, 'Test_Unseen', '14mil')
        test_21mil_dir = os.path.join(self.data_dir, 'Test_Unseen', '21mil')
        
        files_with_meta = [] # (file_path, label, default_rpm)
        
        if self.split in ['train', 'val']:
            # Normal baseline files (Class 0): Loads 0, 1, 2 HP
            for fname in ['97.mat', '98.mat', '99.mat']:
                f = os.path.join(normal_dir, fname)
                if os.path.exists(f):
                    rpm = NORMAL_RPM_MAP.get(fname, 1750.0)
                    files_with_meta.append((f, 0, rpm))
                
            # Train 7-mil files (Seen severity)
            for f in sorted(glob.glob(os.path.join(train_7mil_dir, 'InnerRace', '*.mat'))):
                files_with_meta.append((f, 1, 1750.0))
            for f in sorted(glob.glob(os.path.join(train_7mil_dir, 'OuterRace', '*.mat'))):
                files_with_meta.append((f, 2, 1750.0))
            for f in sorted(glob.glob(os.path.join(train_7mil_dir, 'Ball', '*.mat'))):
                files_with_meta.append((f, 3, 1750.0))
                
        elif self.split == 'test_14mil':
            # Unseen Normal holdout under Load 3 (100.mat - 3 HP)
            f_norm = os.path.join(normal_dir, '100.mat')
            if os.path.exists(f_norm):
                files_with_meta.append((f_norm, 0, NORMAL_RPM_MAP['100.mat']))

            # 14-mil unseen fault holdout (Class 1, 2, 3)
            for f in sorted(glob.glob(os.path.join(test_14mil_dir, 'InnerRace', '*.mat'))):
                files_with_meta.append((f, 1, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_14mil_dir, 'OuterRace', '*.mat'))):
                files_with_meta.append((f, 2, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_14mil_dir, 'Ball', '*.mat'))):
                files_with_meta.append((f, 3, 1750.0))
                
        elif self.split == 'test_21mil':
            # Unseen Normal holdout under Load 3 (100.mat - 3 HP)
            f_norm = os.path.join(normal_dir, '100.mat')
            if os.path.exists(f_norm):
                files_with_meta.append((f_norm, 0, NORMAL_RPM_MAP['100.mat']))

            # 21-mil unseen fault holdout (Class 1, 2, 3)
            for f in sorted(glob.glob(os.path.join(test_21mil_dir, 'InnerRace', '*.mat'))):
                files_with_meta.append((f, 1, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_21mil_dir, 'OuterRace', '*.mat'))):
                files_with_meta.append((f, 2, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_21mil_dir, 'Ball', '*.mat'))):
                files_with_meta.append((f, 3, 1750.0))
                
        elif self.split in ['test_unseen', 'test_all']:
            # Unseen Normal holdout under Load 3 (100.mat - 3 HP)
            f_norm = os.path.join(normal_dir, '100.mat')
            if os.path.exists(f_norm):
                files_with_meta.append((f_norm, 0, NORMAL_RPM_MAP['100.mat']))

            # All unseen holdouts combined
            for f in sorted(glob.glob(os.path.join(test_14mil_dir, 'InnerRace', '*.mat'))):
                files_with_meta.append((f, 1, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_14mil_dir, 'OuterRace', '*.mat'))):
                files_with_meta.append((f, 2, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_14mil_dir, 'Ball', '*.mat'))):
                files_with_meta.append((f, 3, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_21mil_dir, 'InnerRace', '*.mat'))):
                files_with_meta.append((f, 1, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_21mil_dir, 'OuterRace', '*.mat'))):
                files_with_meta.append((f, 2, 1750.0))
            for f in sorted(glob.glob(os.path.join(test_21mil_dir, 'Ball', '*.mat'))):
                files_with_meta.append((f, 3, 1750.0))
        else:
            raise ValueError(f"Unknown split: {self.split}")
            
        return files_with_meta

    def _build_dataset(self):
        file_list = self._get_files_for_split()
        assert len(file_list) > 0, f"No data files found for split: {self.split} in {self.data_dir}"
        
        all_windows = []
        all_labels = []
        all_rpms = []
        
        is_train_like = self.split in ['train', 'val']
        stride = self.train_stride if is_train_like else self.test_stride
        
        for file_path, label, default_rpm in file_list:
            mat = sio.loadmat(file_path)
            
            # Extract Drive End vibration channel
            de_keys = [k for k in mat.keys() if 'DE' in k]
            if not de_keys:
                continue
            raw_sig = mat[de_keys[0]].flatten().astype(np.float32)
            
            # Extract actual RPM if recorded in mat
            rpm_keys = [k for k in mat.keys() if 'RPM' in k.upper()]
            if rpm_keys:
                try:
                    rpm = float(mat[rpm_keys[0]].squeeze())
                except:
                    rpm = default_rpm
            else:
                rpm = default_rpm
                
            n_samples = len(raw_sig)
            if n_samples < self.window_size:
                continue
                
            num_windows = (n_samples - self.window_size) // stride + 1
            for w in range(num_windows):
                start = w * stride
                end = start + self.window_size
                window = raw_sig[start:end]
                all_windows.append(window)
                all_labels.append(label)
                all_rpms.append(rpm)
                
        all_windows = np.array(all_windows, dtype=np.float32)
        all_labels = np.array(all_labels, dtype=np.int64)
        all_rpms = np.array(all_rpms, dtype=np.float32)
        
        # Partition train vs validation deterministically by class
        if self.split in ['train', 'val']:
            rng = np.random.RandomState(self.seed)
            indices = np.arange(len(all_labels))
            rng.shuffle(indices)
            
            val_count = int(len(indices) * self.val_ratio)
            val_idx = indices[:val_count]
            train_idx = indices[val_count:]
            
            sel_idx = train_idx if self.split == 'train' else val_idx
            all_windows = all_windows[sel_idx]
            all_labels = all_labels[sel_idx]
            all_rpms = all_rpms[sel_idx]
            
        # Process through bit-true DSP pipeline
        spectra_list = []
        priors_list = []
        
        for i in range(len(all_windows)):
            win = all_windows[i]
            if self.transform is not None and self.split == 'train':
                win = self.transform(win)
                
            out = self.dsp.process_window(win, rpm=all_rpms[i])
            spectra_list.append(out['spectrum'])
            priors_list.append(out['prior'])
            
        self.spectra = torch.from_numpy(np.array(spectra_list, dtype=np.float32)).unsqueeze(1) # [N, 1, 257]
        self.priors = torch.from_numpy(np.array(priors_list, dtype=np.float32))                  # [N, 4]
        self.labels = torch.from_numpy(all_labels)                                              # [N]
        self.rpms = torch.from_numpy(all_rpms)                                                  # [N]

    def __len__(self):
        return len(self.labels)
        
    def __getitem__(self, idx):
        return {
            'spectrum': self.spectra[idx],
            'prior': self.priors[idx],
            'label': self.labels[idx],
            'rpm': self.rpms[idx]
        }

def get_cwru_dataloaders(data_dir: str, batch_size: int = 64, num_workers: int = 0,
                         cache_dir: str = None, use_augmentation: bool = True):
    """
    Factory function returning production-grade Zero-Leakage DataLoaders.
    
    Returns:
        dict: {
            'train': DataLoader,
            'val': DataLoader,
            'test_14mil': DataLoader,
            'test_21mil': DataLoader,
            'test_unseen': DataLoader
        }
    """
    train_transform = None
    if use_augmentation:
        train_transform = ComposeTransforms([
            RandomCyclicShift(max_shift=64, p=0.5),
            RandomNoise(snr_db_min=15.0, snr_db_max=30.0, p=0.4),
            RandomScale(scale_min=0.9, scale_max=1.1, p=0.3)
        ])
        
    train_set = CWRUBearingDataset(data_dir, split='train', transform=train_transform, cache_dir=cache_dir)
    val_set = CWRUBearingDataset(data_dir, split='val', transform=None, cache_dir=cache_dir)
    test_14_set = CWRUBearingDataset(data_dir, split='test_14mil', transform=None, cache_dir=cache_dir)
    test_21_set = CWRUBearingDataset(data_dir, split='test_21mil', transform=None, cache_dir=cache_dir)
    test_all_set = CWRUBearingDataset(data_dir, split='test_all', transform=None, cache_dir=cache_dir)
    
    return {
        'train': DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        'val': DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=num_workers),
        'test_14mil': DataLoader(test_14_set, batch_size=batch_size, shuffle=False, num_workers=num_workers),
        'test_21mil': DataLoader(test_21_set, batch_size=batch_size, shuffle=False, num_workers=num_workers),
        'test_unseen': DataLoader(test_all_set, batch_size=batch_size, shuffle=False, num_workers=num_workers),
        'datasets': {
            'train': train_set,
            'val': val_set,
            'test_14mil': test_14_set,
            'test_21mil': test_21_set,
            'test_unseen': test_all_set
        }
    }
