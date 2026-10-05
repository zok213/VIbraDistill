import os
import sys
import unittest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.datasets.cwru_loader import CWRUBearingDataset
from src.datasets.xjtu_sy_loader import XJTUSYBearingDataset

class TestDatasets(unittest.TestCase):
    def test_cwru_dataset_sample(self):
        cwru_dir = os.path.join("data", "CWRU_Dataset")
        if not os.path.exists(cwru_dir):
            self.skipTest("CWRU dataset not found")
            
        ds = CWRUBearingDataset(data_dir=cwru_dir, split='train')
        self.assertGreater(len(ds), 0)
        sample = ds[0]
        self.assertIn('spectrum', sample)
        self.assertIn('prior', sample)
        self.assertIn('label', sample)
        self.assertEqual(sample['spectrum'].shape, (1, 257))
        self.assertEqual(sample['prior'].shape, (4,))
        self.assertIn(sample['label'].item(), [0, 1, 2, 3])

    def test_xjtu_sy_dataset_sample(self):
        xjtu_raw = os.path.join("data", "XJTU-SY_Dataset", "raw")
        if not os.path.exists(xjtu_raw):
            self.skipTest("XJTU-SY raw dataset not found")
            
        ds = XJTUSYBearingDataset(raw_dir=xjtu_raw, condition='35Hz12kN', split='train', max_samples_per_bearing=5)
        self.assertGreater(len(ds), 0)
        sample = ds[0]
        self.assertIn('spectrum', sample)
        self.assertIn('prior', sample)
        self.assertIn('rul', sample)
        self.assertEqual(sample['spectrum'].shape, (1, 257))
        self.assertEqual(sample['prior'].shape, (4,))
        self.assertTrue(0.0 <= sample['rul'].item() <= 1.0)

    def test_mfpt_dataset_sample(self):
        mfpt_dir = os.path.join("data", "MFPT_Dataset")
        if not os.path.exists(mfpt_dir):
            self.skipTest("MFPT dataset not found")
        from src.datasets.mfpt_loader import MFPTBearingDataset
        ds = MFPTBearingDataset(data_dir=mfpt_dir, max_samples_per_file=2)
        self.assertGreater(len(ds), 0)
        sample = ds[0]
        self.assertIn('spectrum', sample)
        self.assertIn('prior', sample)
        self.assertIn('label', sample)
        self.assertEqual(sample['spectrum'].shape, (1, 257))
        self.assertEqual(sample['prior'].shape, (4,))
        self.assertIn(sample['label'].item(), [0, 2, 3])

if __name__ == '__main__':
    unittest.main()
