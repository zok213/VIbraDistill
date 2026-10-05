import os
import sys
import unittest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.models.student_micro import VibraDistillMicro
from src.models.teacher_resnet import Teacher1DResNet

class TestModels(unittest.TestCase):
    def test_student_parameter_budget(self):
        model = VibraDistillMicro(in_bins=257, num_classes=4, physics_dim=4)
        total_params = sum(p.numel() for p in model.parameters())
        # The design constraint strictly specifies exactly 8,677 parameters
        self.assertEqual(total_params, 8677, f"Expected 8677 params, got {total_params}")

    def test_student_forward_shapes(self):
        model = VibraDistillMicro(in_bins=257, num_classes=4, physics_dim=4)
        model.eval()
        x = torch.randn(2, 1, 257)
        prior = torch.tensor([[0.5, 0.2, 0.1, 0.2], [0.1, 0.6, 0.2, 0.1]])
        
        logits, rul = model(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))
        # RUL output must be in [0, 1] due to Sigmoid
        self.assertTrue(torch.all(rul >= 0.0) and torch.all(rul <= 1.0))

    def test_student_physics_film_modulation(self):
        # Test 2026 SOTA Physics-FiLM modulation
        model = VibraDistillMicro(in_bins=257, num_classes=4, physics_dim=4, use_physics_film=True)
        model.eval()
        total_params = sum(p.numel() for p in model.parameters())
        self.assertEqual(total_params, 8677 + 240, f"Expected 8917 params, got {total_params}")
        
        x = torch.randn(2, 1, 257)
        prior = torch.tensor([[0.8, 0.1, 0.05, 0.05], [0.1, 0.7, 0.1, 0.1]])
        logits, rul = model(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))

    def test_teacher_forward_shapes(self):
        teacher = Teacher1DResNet(in_channels=1, num_classes=4, physics_dim=4)
        teacher.eval()
        x = torch.randn(2, 1, 257)
        prior = torch.tensor([[0.5, 0.2, 0.1, 0.2], [0.1, 0.6, 0.2, 0.1]])
        
        logits, rul = teacher(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))

    def test_tang20k_model(self):
        from src.models.student_micro import VibraDistillTang20K
        model = VibraDistillTang20K(in_bins=257, num_classes=4, physics_dim=8)
        model.eval()
        total_params = sum(p.numel() for p in model.parameters())
        self.assertEqual(total_params, 41829, f"Expected 41829 params, got {total_params}")
        
        x = torch.randn(2, 1, 257)
        prior = torch.randn(2, 8)
        logits, rul = model(x, prior)
        self.assertEqual(logits.shape, (2, 4))
        self.assertEqual(rul.shape, (2, 1))
        self.assertTrue(torch.all(rul >= 0.0) and torch.all(rul <= 1.0))

if __name__ == '__main__':
    unittest.main()
