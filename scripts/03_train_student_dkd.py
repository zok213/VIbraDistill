"""
03: Student VibraDistillMicro DKD Distillation & EDL Calibration Script.
Distills the 1D-ResNet Teacher (~1.0M params) into VibraDistillMicro (8,677 params)
using Decoupled Knowledge Distillation (DKD: tau=5.0, tau^2=25.0) and Evidential Deep Learning (EDL).
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

from src.datasets.cwru_loader import get_cwru_dataloaders
from src.models.student_micro import VibraDistillMicro
from src.models.teacher_resnet import Teacher1DResNet
from src.losses.dkd_loss import DecoupledKnowledgeDistillationLoss
from src.losses.edl_loss import EvidentialLoss, compute_dirichlet_vacuity
from src.utils.seed import set_seed
from src.utils.metrics import compute_classification_metrics

def train_student_dkd(args):
    set_seed(args.seed)
    if hasattr(args, 'device') and args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() and not args.cpu else 'cpu')
    print("=" * 70)
    print(f"  DISTILLING TEACHER INTO VIBRADISTILL-{args.model_type.upper()} VIA DKD")
    print(f"  Device: {device} | Epochs: {args.epochs} | Tau: {args.temperature} | Alpha: {args.alpha} | Beta: {args.beta}")
    print("=" * 70)
    
    # 1. Load DataLoaders
    loaders = get_cwru_dataloaders(
        data_dir=args.data_dir,
        batch_size=args.batch_size,
        cache_dir=args.cache_dir,
        use_augmentation=args.use_augmentation
    )
    train_loader = loaders['train']
    val_loader = loaders['val']
    
    # 2. Load and Freeze Teacher
    print(f"\n[1] Loading Pre-trained Teacher from: {args.teacher_ckpt}")
    teacher = Teacher1DResNet(in_channels=1, num_classes=4, physics_dim=4).to(device)
    if os.path.exists(args.teacher_ckpt):
        ckpt = torch.load(args.teacher_ckpt, map_location=device)
        teacher.load_state_dict(ckpt['model_state_dict'])
        print(f"  - Teacher successfully loaded (Val F1: {ckpt.get('val_f1', 0.0):.2f}%).")
    else:
        print(f"  WARNING: Teacher checkpoint {args.teacher_ckpt} not found! Initializing untrained teacher for test run.")
    teacher.eval()
    for param in teacher.parameters():
        param.requires_grad = False
        
    # 3. Instantiate Student Model
    if args.model_type == 'tang20k':
        physics_dim = args.physics_dim if args.physics_dim is not None else 8
        print(f"\n[2] Initializing Student VibraDistillTang20K Model (physics_dim={physics_dim})...")
        from src.models.student_micro import VibraDistillTang20K
        student = VibraDistillTang20K(in_bins=257, num_classes=4, physics_dim=physics_dim).to(device)
    else:
        physics_dim = args.physics_dim if args.physics_dim is not None else 4
        print(f"\n[2] Initializing Student VibraDistillMicro Model (physics_dim={physics_dim})...")
        student = VibraDistillMicro(in_bins=257, num_classes=4, physics_dim=physics_dim).to(device)
        
    total_params = sum(p.numel() for p in student.parameters())
    print(f"  - Student Parameters: {total_params:,} (~{total_params/1024:.2f} KB INT8 weights)")
    
    # 4. Losses & Optimizer
    dkd_criterion = DecoupledKnowledgeDistillationLoss(
        alpha=args.alpha,
        beta=args.beta,
        temperature=args.temperature,
        ce_weight=args.ce_weight
    )
    edl_criterion = EvidentialLoss(num_classes=4, annealing_epochs=args.annealing_epochs)
    rul_criterion = nn.MSELoss()
    
    optimizer = optim.AdamW(student.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.min_lr)
    
    os.makedirs(args.save_dir, exist_ok=True)
    best_val_f1 = 0.0
    save_filename = f"best_student_dkd_{args.model_type}.pt" if args.model_type != 'micro' else "best_student_dkd.pt"
    best_path = os.path.join(args.save_dir, save_filename)
    
    start_time = time.time()
    
    print("\n[3] Starting Knowledge Distillation Loop...")
    for epoch in range(1, args.epochs + 1):
        student.train()
        running_loss = 0.0
        
        for batch in train_loader:
            x = batch['spectrum'].to(device)
            prior = batch['prior'].to(device)
            y = batch['label'].to(device)
            
            optimizer.zero_grad()
            
            # Forward student and teacher
            s_logits, s_rul = student(x, prior)
            with torch.no_grad():
                t_logits, _ = teacher(x, prior)
                
            # Losses
            loss_dkd, l_ce, l_distill = dkd_criterion(s_logits, t_logits, y)
            loss_edl = edl_criterion(s_logits, y, epoch=epoch)
            
            rul_target = torch.where(y == 0, 1.0, 0.5).unsqueeze(1).float()
            loss_rul = rul_criterion(s_rul, rul_target)
            
            loss = loss_dkd + args.edl_weight * loss_edl + 0.5 * loss_rul
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * x.size(0)
            
        scheduler.step()
        train_loss = running_loss / len(loaders['datasets']['train'])
        
        # Validation
        student.eval()
        all_preds = []
        all_targets = []
        all_vacuities = []
        
        with torch.no_grad():
            for batch in val_loader:
                x = batch['spectrum'].to(device)
                prior = batch['prior'].to(device)
                y = batch['label'].to(device)
                
                logits, _ = student(x, prior)
                probs, vacuity = compute_dirichlet_vacuity(logits)
                preds = torch.argmax(logits, dim=1)
                
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(y.cpu().numpy())
                all_vacuities.extend(vacuity.cpu().numpy())
                
        metrics = compute_classification_metrics(all_targets, all_preds, num_classes=4)
        val_acc = metrics['accuracy'] * 100.0
        val_f1 = metrics['macro_f1'] * 100.0
        mean_vac = float(torch.tensor(all_vacuities).mean())
        
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            torch.save({
                'epoch': epoch,
                'model_state_dict': student.state_dict(),
                'val_f1': val_f1,
                'val_acc': val_acc,
                'mean_vacuity': mean_vac,
                'args': vars(args)
            }, best_path)
            mark = "(*) BEST"
        else:
            mark = ""
            
        if epoch % 5 == 0 or epoch == 1 or mark != "":
            print(f"  Epoch [{epoch:02d}/{args.epochs:02d}] | Train Loss: {train_loss:.4f} | "
                  f"Val Acc: {val_acc:.2f}% | Val Macro-F1: {val_f1:.2f}% | Vacuity: {mean_vac:.3f} {mark}")
                  
    elapsed = time.time() - start_time
    print(f"\nDistillation finished in {elapsed:.1f}s. Best Val Macro-F1: {best_val_f1:.2f}%")
    print(f"Best student model saved to: {best_path}")
    
    # Holdout Test Evaluation
    print("\nEvaluating Best Distilled Student on Unseen Hold-out Sets...")
    checkpoint = torch.load(best_path, map_location=device)
    student.load_state_dict(checkpoint['model_state_dict'])
    student.eval()
    
    for split_name in ['test_14mil', 'test_21mil']:
        test_loader = loaders[split_name]
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for batch in test_loader:
                x = batch['spectrum'].to(device)
                prior = batch['prior'].to(device)
                y = batch['label'].to(device)
                logits, _ = student(x, prior)
                preds = torch.argmax(logits, dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(y.cpu().numpy())
                
        m = compute_classification_metrics(all_targets, all_preds, num_classes=4)
        print(f"  [{split_name:10s}] Accuracy: {m['accuracy']*100:.2f}% | Macro-F1: {m['macro_f1']*100:.2f}%")
        print(f"                 Per-Class F1 [Normal, IR, OR, Ball]: {[round(v*100, 2) for v in m['per_class_f1']]}")
        
    print("=" * 70)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Distill Teacher into VibraDistillMicro / VibraDistillTang20K via DKD")
    parser.add_argument('--model_type', type=str, default='micro', choices=['micro', 'tang20k'],
                        help="Student architecture: 'micro' (8,677 params) or 'tang20k' (41,829 params)")
    parser.add_argument('--physics_dim', type=int, default=None,
                        help="Kinematic prior dimension: 4 (standard) or 8 (harmonic). Defaults: 4 for micro, 8 for tang20k.")
    parser.add_argument('--data_dir', type=str, default='data/CWRU_Dataset')
    parser.add_argument('--cache_dir', type=str, default='data/cache')
    parser.add_argument('--teacher_ckpt', type=str, default='checkpoints/teacher/best_teacher.pt')
    parser.add_argument('--save_dir', type=str, default='checkpoints/student_dkd')
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--lr', type=float, default=0.002)
    parser.add_argument('--weight_decay', type=float, default=5e-5)
    parser.add_argument('--min_lr', type=float, default=2e-5)
    parser.add_argument('--temperature', type=float, default=5.0)
    parser.add_argument('--alpha', type=float, default=1.0)
    parser.add_argument('--beta', type=float, default=2.0)
    parser.add_argument('--ce_weight', type=float, default=1.0)
    parser.add_argument('--edl_weight', type=float, default=0.5)
    parser.add_argument('--annealing_epochs', type=int, default=10)
    parser.add_argument('--use_augmentation', action='store_true', default=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cpu', action='store_true', default=False)
    parser.add_argument('--device', type=str, default=None, help="Device (e.g. cuda, cuda:0, cuda:1, cpu)")
    args = parser.parse_args()
    
    train_student_dkd(args)
