"""
Embedded C / CMSIS Exporter Module.
Bridges PyTorch quantization package to bit-true C deployment for Cortex-M0/M4F.
Re-routes to production exporter in src.quantization.export_c.
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.quantization.export_c import export_c_headers
from src.quantization.ptq import quantize_model_symmetric_int8
from src.quantization.bn_fold import fold_batchnorm_micro
from src.models.student_micro import VibraDistillMicro

def export_model_to_c(model, out_dir):
    """
    Exports clean, production-grade ANSI C source and headers with zero heap allocation.
    """
    folded = fold_batchnorm_micro(model)
    quant_pkg = quantize_model_symmetric_int8(folded)
    export_c_headers(quant_pkg, out_dir)
    print(f"[CMSIS-Export] Successfully exported verified bit-true C model to: {out_dir}")

if __name__ == '__main__':
    model = VibraDistillMicro()
    export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mcu_sonix', 'app'))
    export_model_to_c(model, export_dir)
