"""
04: Zero-Leakage Comprehensive Evaluation Script.
Evaluates Teacher vs Distilled Student on physically unseen bearing fault datasets:
- 14-mil defect holdout (InnerRace, OuterRace, Ball across 4 motor loads)
- 21-mil defect holdout (InnerRace, OuterRace, Ball across 4 motor loads)

Computes Accuracy, Macro-F1, Confusion Matrix, Expected Calibration Error (ECE),
and Dirichlet Vacuity Epistemic Uncertainty.
"""

import sys
import os
import argparse
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import torch
from src.datasets.cwru_loader import get_cwru_dataloaders
from src.models.student_micro import VibraDistillMicro
from src.models.teacher_resnet import Teacher1DResNet
from src.losses.edl_loss import compute_dirichlet_vacuity
from src.utils.metrics import compute_classification_metrics, compute_calibration_ece

CLASS_NAMES = ["Normal", "InnerRace", "OuterRace", "Ball"]

def evaluate_model_on_loader(model, loader, device):
    model.eval()
    all_preds = []
    all_targets = []
    all_probs = []
    all_vacuities = []
    
    with torch.no_grad():
        for batch in loader:
            x = batch['spectrum'].to(device)
            prior = batch['prior'].to(device)
            y = batch['label'].to(device)
            
            logits, _ = model(x, prior)
            probs, vacuity = compute_dirichlet_vacuity(logits)
            preds = torch.argmax(logits, dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_targets.extend(y.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            all_vacuities.extend(vacuity.cpu().numpy())
            
    metrics = compute_classification_metrics(all_targets, all_preds, num_classes=4)
    ece = compute_calibration_ece(all_probs, all_targets)
    metrics['ece'] = ece
    metrics['mean_vacuity'] = float(np.mean(all_vacuities))
    return metrics

def run_evaluation(args):
    if hasattr(args, 'device') and args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() and not args.cpu else 'cpu')
    print("=" * 80)
    print("  ZERO-LEAKAGE BENCHMARK EVALUATION ON UNSEEN CWRU BEARING DEFECTS")
    print(f"  Hold-out Sets: 14-mil (Unseen Severity) & 21-mil (Unseen Severity)")
    print("=" * 80)
    
    loaders = get_cwru_dataloaders(data_dir=args.data_dir, batch_size=args.batch_size, cache_dir=args.cache_dir)
    
    # 1. Evaluate Student Model
    if args.model_type == 'tang20k':
        physics_dim = args.physics_dim if args.physics_dim is not None else 8
        print(f"\n[1] Evaluating Student VibraDistillTang20K (41,829 parameters, physics_dim={physics_dim})...")
        from src.models.student_micro import VibraDistillTang20K
        student = VibraDistillTang20K(in_bins=257, num_classes=4, physics_dim=physics_dim).to(device)
        default_ckpt = 'checkpoints/student_dkd/best_student_dkd_tang20k.pt'
    else:
        physics_dim = args.physics_dim if args.physics_dim is not None else 4
        print(f"\n[1] Evaluating Student VibraDistillMicro (8,677 parameters, physics_dim={physics_dim})...")
        student = VibraDistillMicro(in_bins=257, num_classes=4, physics_dim=physics_dim).to(device)
        default_ckpt = 'checkpoints/student_dkd/best_student_dkd.pt'
        
    ckpt_path = args.student_ckpt
    if (args.model_type == 'tang20k' and ckpt_path == 'checkpoints/student_dkd/best_student_dkd.pt') or not os.path.exists(ckpt_path):
        if os.path.exists(default_ckpt):
            ckpt_path = default_ckpt

    if os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location=device)
        student.load_state_dict(ckpt['model_state_dict'])
        print(f"  - Loaded checkpoint: {ckpt_path}")
    else:
        print(f"  - Checkpoint {ckpt_path} not found! Evaluating initialized weights.")
        
    for split_name in ['test_14mil', 'test_21mil', 'test_unseen']:
        loader = loaders[split_name]
        m = evaluate_model_on_loader(student, loader, device)
        print(f"\n  >> Student on [{split_name.upper()}]:")
        print(f"     Accuracy: {m['accuracy']*100:.2f}% | Macro-F1: {m['macro_f1']*100:.2f}% | ECE: {m['ece']*100:.2f}% | Mean Vacuity: {m['mean_vacuity']:.3f}")
        print(f"     Per-Class F1:")
        for c, name in enumerate(CLASS_NAMES):
            print(f"       {name:10s}: {m['per_class_f1'][c]*100:.2f}% (P: {m['per_class_precision'][c]*100:.1f}%, R: {m['per_class_recall'][c]*100:.1f}%)")
        print("     Confusion Matrix:")
        for row in m['confusion_matrix']:
            print(f"       {row}")
            
    # 2. Evaluate Teacher Model if available
    if os.path.exists(args.teacher_ckpt):
        print(f"\n[2] Evaluating Teacher 1D-ResNet (~1.0M parameters)...")
        teacher = Teacher1DResNet().to(device)
        ckpt_t = torch.load(args.teacher_ckpt, map_location=device)
        teacher.load_state_dict(ckpt_t['model_state_dict'])
        
        for split_name in ['test_14mil', 'test_21mil']:
            loader = loaders[split_name]
            m_t = evaluate_model_on_loader(teacher, loader, device)
            print(f"  >> Teacher on [{split_name.upper()}]: Accuracy: {m_t['accuracy']*100:.2f}% | Macro-F1: {m_t['macro_f1']*100:.2f}% | ECE: {m_t['ece']*100:.2f}%")
            
    print("\n" + "=" * 80)
    print("Zero-Leakage Benchmark Evaluation Complete.")
    print("=" * 80)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Evaluate on Unseen CWRU Datasets")
    parser.add_argument('--model_type', type=str, default='micro', choices=['micro', 'tang20k'],
                        help="Model architecture to evaluate: 'micro' (8,677 params) or 'tang20k' (41,829 params)")
    parser.add_argument('--physics_dim', type=int, default=None,
                        help="Kinematic prior dimension: 4 (standard) or 8 (harmonic). Defaults: 4 for micro, 8 for tang20k.")
    parser.add_argument('--data_dir', type=str, default='data/CWRU_Dataset')
    parser.add_argument('--cache_dir', type=str, default='data/cache')
    parser.add_argument('--student_ckpt', type=str, default='checkpoints/student_dkd/best_student_dkd.pt')
    parser.add_argument('--teacher_ckpt', type=str, default='checkpoints/teacher/best_teacher.pt')
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--cpu', action='store_true', default=False)
    parser.add_argument('--device', type=str, default=None, help="Device (e.g. cuda, cuda:0, cpu)")
    args = parser.parse_args()
    
    run_evaluation(args)
