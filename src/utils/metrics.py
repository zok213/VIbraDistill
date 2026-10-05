"""
Evaluation Metrics Engine for Bearing Fault Diagnosis & Prognostics.
Includes Macro-F1, Confusion Matrix, Expected Calibration Error (ECE),
and Conformal Prediction Empirical Coverage.
"""

from typing import Dict, Any
import numpy as np
import torch
import torch.nn.functional as F

def compute_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int = 4) -> Dict[str, Any]:
    """
    Computes overall Accuracy, Macro-F1, per-class Precision/Recall, and Confusion Matrix.
    """
    y_true = np.asarray(y_true).flatten()
    y_pred = np.asarray(y_pred).flatten()
    
    total = len(y_true)
    correct = int(np.sum(y_true == y_pred))
    accuracy = correct / total if total > 0 else 0.0
    
    conf_matrix = np.zeros((num_classes, num_classes), dtype=np.int32)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            conf_matrix[t, p] += 1
            
    precisions = []
    recalls = []
    f1s = []
    
    for c in range(num_classes):
        tp = conf_matrix[c, c]
        fp = np.sum(conf_matrix[:, c]) - tp
        fn = np.sum(conf_matrix[c, :]) - tp
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        
    macro_f1 = float(np.mean(f1s))
    
    return {
        'accuracy': float(accuracy),
        'macro_f1': macro_f1,
        'per_class_f1': [float(x) for x in f1s],
        'per_class_precision': [float(x) for x in precisions],
        'per_class_recall': [float(x) for x in recalls],
        'confusion_matrix': conf_matrix.tolist()
    }

def compute_calibration_ece(probs: np.ndarray, y_true: np.ndarray, n_bins: int = 10) -> float:
    """
    Computes Expected Calibration Error (ECE).
    """
    probs = np.asarray(probs)
    y_true = np.asarray(y_true).flatten()
    
    confidences = np.max(probs, axis=1)
    predictions = np.argmax(probs, axis=1)
    accuracies = (predictions == y_true)
    
    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    
    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        bin_size = np.sum(in_bin)
        
        if bin_size > 0:
            bin_acc = np.mean(accuracies[in_bin])
            bin_conf = np.mean(confidences[in_bin])
            ece += (bin_size / n) * np.abs(bin_acc - bin_conf)
            
    return float(ece)

def compute_conformal_coverage(y_true: np.ndarray, lower_bounds: np.ndarray, upper_bounds: np.ndarray) -> float:
    """
    Computes empirical coverage rate for Conformal Prediction prediction intervals.
    Coverage = Fraction of true values falling strictly within [lower_bounds, upper_bounds].
    """
    y_true = np.asarray(y_true).flatten()
    lower_bounds = np.asarray(lower_bounds).flatten()
    upper_bounds = np.asarray(upper_bounds).flatten()
    
    covered = (y_true >= lower_bounds) & (y_true <= upper_bounds)
    return float(np.mean(covered))
