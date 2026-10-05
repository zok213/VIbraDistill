import os
import sys
import unittest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.models.baselines import SingleKernelCNN, GRUModel, BiLSTMModel, MLPBaseline

class TestBaselineModels(unittest.TestCase):
    def test_single_kernel_cnn(self):
        m = SingleKernelCNN(in_bins=257, num_classes=4, physics_dim=4)
        x = torch.randn(2, 1, 257)
        prior = torch.randn(2, 4)
        logits, rul = m(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))
        params = sum(p.numel() for p in m.parameters())
        self.assertLess(params, 10000)

    def test_gru_model(self):
        m = GRUModel(in_bins=257, num_classes=4, physics_dim=4)
        x = torch.randn(2, 1, 257)
        prior = torch.randn(2, 4)
        logits, rul = m(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))
        params = sum(p.numel() for p in m.parameters())
        self.assertLess(params, 10000)

    def test_bilstm_model(self):
        m = BiLSTMModel(in_bins=257, num_classes=4, physics_dim=4)
        x = torch.randn(2, 1, 257)
        prior = torch.randn(2, 4)
        logits, rul = m(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))
        params = sum(p.numel() for p in m.parameters())
        self.assertLess(params, 10000)

    def test_mlp_model(self):
        m = MLPBaseline(in_bins=257, num_classes=4, physics_dim=4)
        x = torch.randn(2, 1, 257)
        prior = torch.randn(2, 4)
        logits, rul = m(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))
        params = sum(p.numel() for p in m.parameters())
        self.assertLess(params, 10000)

if __name__ == '__main__':
    unittest.main()
