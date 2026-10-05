"""
core/conformal.py: Modern Adaptive Conformal Prediction Suite for Bearing Prognostics.
Includes:
1. BoundedAdaptiveConformalPredictor (1st-Order Baseline ACP, Gibbs & Candès 2021)
2. HigherOrderAdaptiveConformalPredictor (HopACP, 2025/2026 SOTA):
   Incorporates error rate derivative (acceleration) to prevent miscoverage lag
   during rapid exponential bearing degradation.
3. FixedPointConformalACP_Q15: Integer arithmetic implementation for Cortex-M0 without FPU.
"""

from typing import Tuple, Dict, Any, List
import numpy as np

class BoundedAdaptiveConformalPredictor:
    """
    1st-Order Bounded Adaptive Conformal Predictor (Baseline ACP).
    Updates empirical quantile using an Integral controller:
      q_{t+1} = clip(q_t + gamma * (err_t - alpha), q_min, q_max)
    """
    def __init__(self, q_calibrated: float = 0.20, alpha: float = 0.10, gamma: float = 0.02,
                 q_min: float = 0.05, q_max: float = 0.80):
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.q = float(q_calibrated)
        self.q_min = float(q_min)
        self.q_max = float(q_max)
        self.history_q = [self.q]
        self.history_covered = []
        self.history_errors = []
        
    def predict_interval(self, y_pred: float) -> Tuple[float, float, float]:
        """Returns (lower_bound, upper_bound, current_half_width)."""
        lower = max(0.0, float(y_pred - self.q))
        upper = min(1.0, float(y_pred + self.q))
        return lower, upper, self.q
        
    def update(self, y_true: float, y_pred: float) -> bool:
        """
        Observes ground truth, records coverage, and updates quantile threshold.
        """
        abs_err = abs(float(y_true) - float(y_pred))
        covered = abs_err <= self.q
        err_indicator = 0.0 if covered else 1.0
        
        # 1st-Order Integral Step
        self.q = float(np.clip(self.q + self.gamma * (err_indicator - self.alpha), self.q_min, self.q_max))
        
        self.history_q.append(self.q)
        self.history_covered.append(1 if covered else 0)
        self.history_errors.append(abs_err)
        return covered

    def get_metrics(self) -> Dict[str, float]:
        if not self.history_covered:
            return {'coverage': 0.0, 'mean_width': 0.0}
        cov = float(np.mean(self.history_covered))
        # Interval width is 2 * q (clipped at [0, 1])
        widths = [2.0 * min(q_val, 0.5) for q_val in self.history_q[:-1]]
        return {
            'empirical_coverage': cov,
            'nominal_coverage': 1.0 - self.alpha,
            'mean_interval_width': float(np.mean(widths)) if widths else 2.0 * self.q,
            'coverage_gap': cov - (1.0 - self.alpha)
        }


class HigherOrderAdaptiveConformalPredictor:
    """
    Higher-Order Predictor Adaptive Conformal Prediction (HopACP - 2025/2026 SOTA).
    Solves the non-exchangeability lag during accelerating failure in rotating machinery.
    
    Formulation:
      Delta e_t = |e_t| - |e_{t-1}|  (Error Rate Derivative / Acceleration)
      q_{t+1} = clip(q_t + gamma * (err_t - alpha) + kappa * max(0, Delta e_t), q_min, q_max)
    """
    def __init__(self, q_calibrated: float = 0.20, alpha: float = 0.10, gamma: float = 0.02,
                 kappa: float = 0.05, q_min: float = 0.05, q_max: float = 0.80):
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.kappa = float(kappa)
        self.q = float(q_calibrated)
        self.q_min = float(q_min)
        self.q_max = float(q_max)
        
        self.last_abs_err = None
        self.history_q = [self.q]
        self.history_covered = []
        self.history_errors = []
        self.history_derivatives = []
        
    def predict_interval(self, y_pred: float) -> Tuple[float, float, float]:
        lower = max(0.0, float(y_pred - self.q))
        upper = min(1.0, float(y_pred + self.q))
        return lower, upper, self.q
        
    def update(self, y_true: float, y_pred: float) -> bool:
        abs_err = abs(float(y_true) - float(y_pred))
        covered = abs_err <= self.q
        err_indicator = 0.0 if covered else 1.0
        
        # Compute error acceleration derivative
        if self.last_abs_err is None:
            delta_err = 0.0
        else:
            delta_err = abs_err - self.last_abs_err
            
        self.last_abs_err = abs_err
        
        # HopACP update rule: Proportional-Derivative boost
        momentum_term = self.kappa * max(0.0, delta_err)
        integral_term = self.gamma * (err_indicator - self.alpha)
        
        self.q = float(np.clip(self.q + integral_term + momentum_term, self.q_min, self.q_max))
        
        self.history_q.append(self.q)
        self.history_covered.append(1 if covered else 0)
        self.history_errors.append(abs_err)
        self.history_derivatives.append(delta_err)
        return covered

    def get_metrics(self) -> Dict[str, float]:
        if not self.history_covered:
            return {'coverage': 0.0, 'mean_width': 0.0}
        cov = float(np.mean(self.history_covered))
        widths = [2.0 * min(q_val, 0.5) for q_val in self.history_q[:-1]]
        return {
            'empirical_coverage': cov,
            'nominal_coverage': 1.0 - self.alpha,
            'mean_interval_width': float(np.mean(widths)) if widths else 2.0 * self.q,
            'coverage_gap': cov - (1.0 - self.alpha),
            'max_quantile_reached': float(np.max(self.history_q))
        }


class FixedPointConformalACP_Q15:
    """
    Q15 Fixed-Point Bit-True Conformal Predictor for ARM Cortex-M0 MCU.
    Uses 16-bit signed integer arithmetic (scale = 32768).
    Requires ZERO floating point hardware or emulation libraries.
    """
    def __init__(self, q_calibrated_float: float = 0.20, alpha_float: float = 0.10,
                 gamma_float: float = 0.02, kappa_float: float = 0.05):
        self.SCALE = 32768
        self.q_q15 = int(round(q_calibrated_float * self.SCALE))
        self.alpha_q15 = int(round(alpha_float * self.SCALE))
        self.gamma_q15 = int(round(gamma_float * self.SCALE))
        self.kappa_q15 = int(round(kappa_float * self.SCALE))
        self.q_min_q15 = int(round(0.05 * self.SCALE))
        self.q_max_q15 = int(round(0.80 * self.SCALE))
        self.last_err_q15 = None
        
    def predict_interval_q15(self, y_pred_q15: int) -> Tuple[int, int]:
        lower = max(0, y_pred_q15 - self.q_q15)
        upper = min(self.SCALE, y_pred_q15 + self.q_q15)
        return lower, upper
        
    def update_q15(self, y_true_q15: int, y_pred_q15: int) -> bool:
        abs_err = abs(y_true_q15 - y_pred_q15)
        covered = abs_err <= self.q_q15
        
        err_q15 = 0 if covered else self.SCALE
        # Integral term: gamma * (err - alpha) >> 15
        integral = ((err_q15 - self.alpha_q15) * self.gamma_q15) >> 15
        
        # Momentum term
        if self.last_err_q15 is None:
            delta = 0
        else:
            delta = max(0, abs_err - self.last_err_q15)
        self.last_err_q15 = abs_err
        
        momentum = (delta * self.kappa_q15) >> 15
        
        self.q_q15 = max(self.q_min_q15, min(self.q_max_q15, self.q_q15 + integral + momentum))
        return covered
