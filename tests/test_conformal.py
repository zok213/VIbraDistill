import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.conformal import (
    BoundedAdaptiveConformalPredictor,
    HigherOrderAdaptiveConformalPredictor,
    FixedPointConformalACP_Q15
)

class TestConformalPrediction(unittest.TestCase):
    def test_acp_initial_interval(self):
        acp = BoundedAdaptiveConformalPredictor(q_calibrated=0.20, alpha=0.10)
        low, high, q = acp.predict_interval(0.50)
        self.assertAlmostEqual(low, 0.30, places=4)
        self.assertAlmostEqual(high, 0.70, places=4)
        self.assertAlmostEqual(q, 0.20, places=4)

    def test_acp_bounding_limits(self):
        acp = BoundedAdaptiveConformalPredictor(q_calibrated=0.10, alpha=0.10, gamma=0.10, q_min=0.05, q_max=0.50)
        for _ in range(20):
            acp.update(y_true=1.0, y_pred=0.0)
        self.assertLessEqual(acp.q, 0.50)
        self.assertGreaterEqual(acp.q, 0.05)

    def test_acp_tracking_adaptation(self):
        acp = BoundedAdaptiveConformalPredictor(q_calibrated=0.15, alpha=0.10, gamma=0.02)
        initial_q = acp.q
        acp.update(y_true=1.0, y_pred=0.0)
        self.assertGreater(acp.q, initial_q)
        q_after_error = acp.q
        acp.update(y_true=0.5, y_pred=0.5)
        self.assertLess(acp.q, q_after_error)

    def test_hop_acp_momentum_response(self):
        # HopACP must respond faster to accelerating errors than standard ACP
        base_acp = BoundedAdaptiveConformalPredictor(q_calibrated=0.10, alpha=0.10, gamma=0.02)
        hop_acp = HigherOrderAdaptiveConformalPredictor(q_calibrated=0.10, alpha=0.10, gamma=0.02, kappa=0.10)
        
        # Simulating sudden damage acceleration: error jumps from 0.05 to 0.35
        base_acp.update(y_true=0.50, y_pred=0.55) # err = 0.05
        hop_acp.update(y_true=0.50, y_pred=0.55)  # err = 0.05
        
        # Sudden failure onset
        base_acp.update(y_true=0.15, y_pred=0.50) # err = 0.35
        hop_acp.update(y_true=0.15, y_pred=0.50)  # err = 0.35
        
        # HopACP's momentum term should have expanded q significantly more than base ACP
        self.assertGreater(hop_acp.q, base_acp.q,
                           f"HopACP q ({hop_acp.q}) should exceed base ACP q ({base_acp.q})")

    def test_fixed_point_q15_conformal(self):
        fp_acp = FixedPointConformalACP_Q15(q_calibrated_float=0.20, alpha_float=0.10)
        SCALE = 32768
        
        y_pred = int(0.50 * SCALE)
        low, high = fp_acp.predict_interval_q15(y_pred)
        
        self.assertAlmostEqual(low / SCALE, 0.30, delta=0.02)
        self.assertAlmostEqual(high / SCALE, 0.70, delta=0.02)
        
        # Trigger an error and verify adaptation
        q_before = fp_acp.q_q15
        fp_acp.update_q15(y_true_q15=int(1.0 * SCALE), y_pred_q15=int(0.0 * SCALE))
        self.assertGreater(fp_acp.q_q15, q_before)

if __name__ == '__main__':
    unittest.main()
