"""
11: Canonical Industrial Cross-Load Adaptability Benchmark.
Trains on Loads 0, 1, 2 HP (1797, 1772, 1750 RPM) across all severities (7, 14, 21-mil).
Tests on Unseen Load 3 HP (~1725 RPM) across all severities (7, 14, 21-mil).
Evaluates both Teacher (1D-ResNet) and Student (VibraDistillMicro) under DKD and EDL.
Outputs: experiments/cross_load_results.json
"""

import os
import sys
import json
import time
import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.datasets.cwru_loader import get_cwru_dataloaders
from src.models.teacher_resnet import Teacher1DResNet
from src.models.student_micro import VibraDistillMicro
from src.losses.dkd_loss import DecoupledKnowledgeDistillationLoss
from src.losses.edl_loss import EvidentialLoss, compute_dirichlet_vacuity
from src.utils.seed import set_seed
from src.utils.metrics import compute_classification_metrics


def eval_model(model, loader, device):
    model.eval()
    P, Y, vacuities = [], [], []
    with torch.no_grad():
        for b in loader:
            spec = b['spectrum'].to(device)
            prior = b['prior'].to(device)
            labels = b['label']
            lg, alpha = model(spec, prior)
            pred = lg.argmax(1).cpu().tolist()
            P += pred
            Y += labels.tolist()
            if alpha is not None:
                S = alpha.sum(dim=-1).cpu().numpy()
                u = 4.0 / np.maximum(S, 1e-4)
                vacuities.extend(u.tolist())
    metrics = compute_classification_metrics(Y, P)
    mean_vacuity = float(np.mean(vacuities)) if vacuities else 0.0
    return {
        'accuracy': round(metrics['accuracy'] * 100, 2),
        'macro_f1': round(metrics['macro_f1'] * 100, 2),
        'precision': round(float(np.mean(metrics['per_class_precision'])) * 100, 2),
        'recall': round(float(np.mean(metrics['per_class_recall'])) * 100, 2),
        'mean_vacuity': round(mean_vacuity, 4),
        'n_samples': len(Y)
    }


def main():
    parser = argparse.ArgumentParser(description="Cross-Load Benchmark")
    parser.add_argument("--data_dir", default="data/CWRU_Dataset")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device(args.device)

    print("=" * 80)
    print("  CANONICAL INDUSTRIAL CROSS-LOAD GENERALIZATION BENCHMARK (IEEE TII / TIE)")
    print(f"  Train: Loads 0, 1, 2 HP (1750-1797 RPM) | Test: Unseen Load 3 HP (~1725 RPM)")
    print(f"  Device: {device} | Epochs: {args.epochs} | Batch Size: {args.batch_size}")
    print("=" * 80)

    # 1. Load DataLoaders
    loaders = get_cwru_dataloaders(
        args.data_dir,
        batch_size=args.batch_size,
        protocol='cross_load',
        use_augmentation=True
    )
    train_loader = loaders['train']
    val_loader = loaders['val']
    test_loader = loaders['test']

    print(f"  Dataset sizes: Train={len(train_loader.dataset)} | Val={len(val_loader.dataset)} | Test (Load 3)={len(test_loader.dataset)}")

    # 2. Train Teacher Oracle
    print("\n[Step 1/2] Training 1D-ResNet Teacher Oracle...")
    teacher = Teacher1DResNet(in_channels=1, num_classes=4, physics_dim=4).to(device)
    optimizer_t = optim.AdamW(teacher.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler_t = CosineAnnealingLR(optimizer_t, T_max=args.epochs)
    criterion_ce = nn.CrossEntropyLoss()

    best_val_f1_t = 0.0
    for epoch in range(1, args.epochs + 1):
        teacher.train()
        tot_loss = 0.0
        for b in train_loader:
            spec = b['spectrum'].to(device)
            prior = b['prior'].to(device)
            labels = b['label'].to(device)
            optimizer_t.zero_grad()
            lg, _ = teacher(spec, prior)
            loss = criterion_ce(lg, labels)
            loss.backward()
            optimizer_t.step()
            tot_loss += loss.item() * len(labels)
        scheduler_t.step()

        val_m = eval_model(teacher, val_loader, device)
        if val_m['macro_f1'] > best_val_f1_t:
            best_val_f1_t = val_m['macro_f1']
            torch.save(teacher.state_dict(), "checkpoints/teacher/best_teacher_cross_load.pt")

    teacher.load_state_dict(torch.load("checkpoints/teacher/best_teacher_cross_load.pt", map_location=device))
    teacher.eval()
    teacher_test_m = eval_model(teacher, test_loader, device)
    print(f"  Teacher Test (Load 3 HP): Accuracy = {teacher_test_m['accuracy']}% | Macro-F1 = {teacher_test_m['macro_f1']}%")

    # 3. Train Student VibraDistillMicro via DKD + EDL
    print("\n[Step 2/2] Distilling into Student VibraDistillMicro (8,677 params) via DKD + EDL...")
    student = VibraDistillMicro(in_channels=1, num_classes=4, physics_dim=4).to(device)
    optimizer_s = optim.AdamW(student.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler_s = CosineAnnealingLR(optimizer_s, T_max=args.epochs)
    dkd_loss_fn = DecoupledKnowledgeDistillationLoss(alpha=1.0, beta=2.0, temperature=4.0)
    edl_loss_fn = EvidentialLoss(num_classes=4, loss_type='log')

    best_val_f1_s = 0.0
    for epoch in range(1, args.epochs + 1):
        student.train()
        tot_loss = 0.0
        for b in train_loader:
            spec = b['spectrum'].to(device)
            prior = b['prior'].to(device)
            labels = b['label'].to(device)
            optimizer_s.zero_grad()

            with torch.no_grad():
                t_logits, _ = teacher(spec, prior)

            s_logits, s_alpha = student(spec, prior)
            loss_dkd = dkd_loss_fn(s_logits, t_logits, labels)
            loss_edl = edl_loss_fn(s_alpha, labels, epoch=epoch, max_epochs=args.epochs)
            loss = loss_dkd + 0.5 * loss_edl
            loss.backward()
            optimizer_s.step()
            tot_loss += loss.item() * len(labels)
        scheduler_s.step()

        val_s = eval_model(student, val_loader, device)
        if val_s['macro_f1'] > best_val_f1_s:
            best_val_f1_s = val_s['macro_f1']
            torch.save({
                'model_state_dict': student.state_dict(),
                'val_f1': best_val_f1_s
            }, "checkpoints/student_dkd/best_student_cross_load.pt")

    student.load_state_dict(torch.load("checkpoints/student_dkd/best_student_cross_load.pt", map_location=device)['model_state_dict'])
    student.eval()
    student_test_m = eval_model(student, test_loader, device)
    print(f"  Student Test (Load 3 HP): Accuracy = {student_test_m['accuracy']}% | Macro-F1 = {student_test_m['macro_f1']}% (Vacuity: {student_test_m['mean_vacuity']})")

    # 4. Save results
    results = {
        'protocol': 'Canonical Industrial Cross-Load Generalization (IEEE TII/TIE)',
        'train_conditions': 'Loads 0, 1, 2 HP (1797, 1772, 1750 RPM) across 7, 14, 21-mil faults',
        'test_condition': 'Load 3 HP (~1725 RPM) across 7, 14, 21-mil faults (Completely Unseen)',
        'teacher_resnet_18': {
            'val_f1': best_val_f1_t,
            'test_load3': teacher_test_m
        },
        'student_vibradistill_micro': {
            'val_f1': best_val_f1_s,
            'test_load3': student_test_m
        }
    }

    os.makedirs("experiments", exist_ok=True)
    with open("experiments/cross_load_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print("  CROSS-LOAD GENERALIZATION BENCHMARK SUMMARY")
    print(f"  Teacher ResNet-18 (1.0M params)  -> Test Acc: {teacher_test_m['accuracy']}% | F1: {teacher_test_m['macro_f1']}%")
    print(f"  Student Micro     (8,677 params)  -> Test Acc: {student_test_m['accuracy']}% | F1: {student_test_m['macro_f1']}%")
    print("  Results saved to: experiments/cross_load_results.json")
    print("=" * 80)


if __name__ == '__main__':
    main()
