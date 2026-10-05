import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.dsp.causal_fir import CausalFIRFilter
from src.dsp.envelope import CausalEnvelopeDemodulator
from src.dsp.kinematics import BearingKinematics, BearingGeometry, SKF_6205_GEOMETRY
from src.dsp.pipeline import StreamingDSPPipeline

class TestDSPPipeline(unittest.TestCase):
    def test_causal_fir_dimensions(self):
        fir = CausalFIRFilter()
        sig = np.random.randn(512).astype(np.float32)
        out = fir.process_block(sig)
        self.assertEqual(len(out), 512)
        self.assertTrue(np.all(np.isfinite(out)))

    def test_envelope_demodulator(self):
        env = CausalEnvelopeDemodulator()
        sig = np.sin(np.linspace(0, 10 * np.pi, 512)).astype(np.float32)
        out = env.process_block(sig)
        self.assertEqual(len(out), 512)
        self.assertTrue(np.all(out >= 0.0))  # Rectified envelope must be non-negative

    def test_kinematic_fault_multipliers(self):
        kin = BearingKinematics(SKF_6205_GEOMETRY)
        mults = kin.get_multipliers()
        # Analytical fault multipliers for SKF 6205:
        # BPFO ~ 3.585, BPFI ~ 5.415, BSF ~ 2.357, FTF ~ 0.398
        self.assertAlmostEqual(mults['BPFO'], 3.5848, places=3)
        self.assertAlmostEqual(mults['BPFI'], 5.4152, places=3)
        self.assertAlmostEqual(mults['BSF'], 2.3567, places=3)
        self.assertAlmostEqual(mults['FTF'], 0.3983, places=3)

    def test_streaming_pipeline_end_to_end(self):
        pipeline = StreamingDSPPipeline(fs=12000.0, window_size=512)
        raw_win = np.random.randn(512).astype(np.float32)
        res = pipeline.process_window(raw_win, rpm=1772.0)
        self.assertIn('spectrum', res)
        self.assertIn('prior', res)
        # Envelope spectrum must have 257 bins (512-point FFT single-sided)
        self.assertEqual(res['spectrum'].shape, (257,))
        # Kinematic prior must have 4 dims
        self.assertEqual(res['prior'].shape, (4,))
        self.assertTrue(np.all(res['spectrum'] >= 0.0))
        self.assertTrue(np.all(res['prior'] >= 0.0))

    def test_8d_kinematic_prior(self):
        from src.dsp.kinematics import extract_kinematic_energy_prior
        spec = np.random.rand(257).astype(np.float32)
        prior_8d = extract_kinematic_energy_prior(spec, rpm=1750.0, prior_dim=8)
        self.assertEqual(prior_8d.shape, (8,))
        self.assertTrue(np.all(prior_8d >= 0.0))
        # First 7 elements should sum to 1.0 (or uniform)
        self.assertAlmostEqual(float(np.sum(prior_8d[:7])), 1.0, places=4)

    def test_tacholess_speed_estimation(self):
        from src.dsp.kinematics import estimate_shaft_speed_tacholess
        # Create a synthetic signal with known 30 Hz shaft frequency (1800 RPM)
        fs = 12000.0
        t = np.arange(4096) / fs
        # 1x harmonic at 30 Hz, 2x at 60 Hz
        sig = (np.sin(2 * np.pi * 30.0 * t) + 0.5 * np.sin(2 * np.pi * 60.0 * t)).astype(np.float32)
        est_rpm = estimate_shaft_speed_tacholess(sig, fs=fs, min_rpm=1200.0, max_rpm=2400.0, is_raw_signal=True)
        # Should be within +/- 50 RPM of 1800 RPM
        self.assertAlmostEqual(est_rpm, 1800.0, delta=60.0)

    def test_warp_order_spectrum(self):
        from src.dsp.resample import warp_order_spectrum
        spec = np.zeros(257, dtype=np.float32)
        spec[20] = 5.0  # Peak at bin 20
        warped = warp_order_spectrum(spec, source_rpm=1750.0, target_rpm=1500.0,
                                     source_geom_multiplier=3.05, target_geom_multiplier=5.41)
        self.assertEqual(len(warped), 257)
        self.assertTrue(np.all(np.isfinite(warped)))

if __name__ == '__main__':
    unittest.main()
