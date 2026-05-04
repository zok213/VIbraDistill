"""
PHASE 1B: ZERO-SHOT GENERALIZATION (OTTAWA UORED)
Target: Test Student ONNX model on previously unseen Ottawa bearing dataset.
"""

import os
import onnxruntime as ort
import numpy as np
from sklearn.metrics import f1_score

# 1. Load the ONNX model trained exclusively on CWRU
print("Loading student_distilled.onnx via ONNXRuntime...")
try:
    session = ort.InferenceSession('/kaggle/working/student_distilled.onnx')
    input_name = session.get_inputs()[0].name
except Exception as e:
    raise RuntimeError(f"CRITICAL: student_distilled.onnx not found or failed to load. {e}")

# 2. Ingest Ottawa UORED dataset
ottawa_dir = '/kaggle/input/ottawa-uored'
if not os.path.exists(ottawa_dir):
    print(f"CRITICAL: Ottawa dataset not found at {ottawa_dir}. Skipping Zero-Shot evaluation.")
else:
    print(f"Found Ottawa dataset at {ottawa_dir}. Real ingestion logic to be implemented here.")
    # Implement actual loading when dataset structure is finalized.
    # uored_preds = session.run(None, {input_name: X_uored})[0].argmax(axis=1)
    # uored_f1 = f1_score(y_uored, uored_preds, average='weighted')
    # print(f"\\nZero-shot F1 on Ottawa UORED: {uored_f1:.3f}")
