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

    def test_raw_cwru_mat_files_direct_inference(self):
        """Tests end-to-end direct inference from raw .mat files without any cached tensors."""
        import scipy.io as sio
        import scipy.signal as signal
        import numpy as np
        from src.dsp.pipeline import StreamingDSPPipeline
        from scripts.verify_raw_mat_to_fpga_pipeline import load_fpga_roms

        cwru_dir = os.path.join("data", "CWRU_Dataset")
        if not os.path.exists(cwru_dir):
            self.skipTest("CWRU dataset not found")

        w12 = load_fpga_roms()
        biases = np.array([0, -3, 8, -4], dtype=np.int32)
        dsp = StreamingDSPPipeline(fs=3200.0, window_size=512, sensor_type='adxl345')

        raw_test_targets = [
            (os.path.join(cwru_dir, 'Normal', '97.mat'), 0),
            (os.path.join(cwru_dir, 'Train_7mil', 'InnerRace', '105.mat'), 1),
            (os.path.join(cwru_dir, 'Train_7mil', 'OuterRace', '130.mat'), 2),
            (os.path.join(cwru_dir, 'Train_7mil', 'Ball', '118.mat'), 3),
        ]

        for fpath, expected_label in raw_test_targets:
            self.assertTrue(os.path.exists(fpath), f"Raw MAT file missing: {fpath}")
            mat = sio.loadmat(fpath)
            de_key = [k for k in mat if 'DE' in k][0]
            raw_sig = mat[de_key].flatten().astype(np.float32)
            sig_3k2 = signal.resample_poly(raw_sig, up=4, down=15).astype(np.float32)
            
            # Take window 5 (steady state)
            chunk = sig_3k2[5 * 256 : 5 * 256 + 512]
            spec = dsp.process_window(chunk, rpm=1797.0)['spectrum']
            spec_int8 = np.clip(np.round(spec * 127.0), 0, 127).astype(np.int32)

            acc = np.dot(w12, spec_int8)
            scores = [
                int(acc[0] + acc[1] + acc[2] + biases[0]),
                int(acc[3] + acc[4] + acc[5] + biases[1]),
                int(acc[6] + acc[7] + acc[8] + biases[2]),
                int(acc[9] + acc[10] + acc[11] + biases[3])
            ]
            pred = int(np.argmax(scores))
            self.assertEqual(pred, expected_label,
                             f"Raw file {os.path.basename(fpath)} expected Class {expected_label}, got {pred} (scores: {scores})")


if __name__ == '__main__':
    unittest.main()
