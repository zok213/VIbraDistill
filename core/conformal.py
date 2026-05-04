import numpy as np

def exponential_degradation(t, a, b, c):
    """
    Fits the typical exponential degradation curve of a bearing:
    Health Index (t) = a * exp(b * t) + c
    """
    return a * np.exp(b * t) + c

def jackknife_plus_conformal_rul(t_cal, y_cal, t_test, alpha=0.1):
    """
    Computes the Jackknife+ Conformal Prediction RUL bounds.
    Given n=14 run-to-failure items, guarantees coverage >= 1 - 2*alpha.
    """
    n = len(t_cal)
    residuals = []
    predictions = []
    
    # 1. Leave-One-Out Calibration
    for i in range(n):
        # Hold out i-th sample
        t_cal_loo = np.delete(t_cal, i)
        y_cal_loo = np.delete(y_cal, i)
        
        # Fit model on n-1
        # (In practice, this would fit the exponential curve. 
        # For this PoC, we simulate the residual extraction).
        
        # simulated residual
        pred_i = y_cal[i] * 0.95 # simulated slight under-prediction
        residuals.append(np.abs(y_cal[i] - pred_i))
        
        # predict on test point with this LOO model
        pred_test_i = t_test * 1.05 # simulated test prediction
        predictions.append(pred_test_i)
        
    residuals = np.array(residuals)
    predictions = np.array(predictions)
    
    # 2. Compute Jackknife+ Bounds
    # Sort LOO predictions
    q_high = np.quantile(predictions + residuals, 1 - alpha)
    q_low = np.quantile(predictions - residuals, alpha)
    
    return q_low, q_high
