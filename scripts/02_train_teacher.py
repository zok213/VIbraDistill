"""
02: Teacher 1D-ResNet Training Script.
Trains the high-capacity Teacher model on CWRU 7-mil training data to provide
accurate soft probability targets for Decoupled Knowledge Distillation (DKD).
"""

import sys
import os
import argparse
import time
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

from src.datasets.cwru_loader import get_cwru_dataloaders
from src.models.teacher_resnet import Teacher1DResNet
from src.utils.seed import set_seed
from src.utils.metrics import compute_classification_metrics

def train_teacher(args):
    set_seed(args.seed)
    if hasattr(args, 'device') and args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() and not args.cpu else 'cpu')
    print("=" * 70)
    print("  TRAINING TEACHER 1D-RESNET ON CWRU ZERO-LEAKAGE DATASET")
    print(f"  Target Device: {device} | Epochs: {args.epochs} | Batch Size: {args.batch_size}")
    print("=" * 70)
    
    # Load Data
    loaders = get_cwru_dataloaders(
        data_dir=args.data_dir,
        batch_size=args.batch_size,
        cache_dir=args.cache_dir,
        use_augmentation=args.use_augmentation
    )
    train_loader = loaders['train']
    val_loader = loaders['val']
    
    print(f"  - Train windows: {len(loaders['datasets']['train'])} ({len(train_loader)} batches)")
    print(f"  - Val windows:   {len(loaders['datasets']['val'])} ({len(val_loader)} batches)")
    print(f"  - Hold-out Test 14mil: {len(loaders['datasets']['test_14mil'])} windows")
    print(f"  - Hold-out Test 21mil: {len(loaders['datasets']['test_21mil'])} windows")
    
    # Model
    model = Teacher1DResNet(in_channels=1, num_classes=4, physics_dim=4).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"  - Teacher Parameters: {total_params:,} (~{total_params/1e6:.2f}M params)")
    
    criterion_cls = nn.CrossEntropyLoss()
    criterion_rul = nn.MSELoss()
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.min_lr)
    
    os.makedirs(args.save_dir, exist_ok=True)
    best_val_f1 = 0.0
    best_path = os.path.join(args.save_dir, 'best_teacher.pt')
    
    start_time = time.time()
    
    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        
        for batch in train_loader:
            x = batch['spectrum'].to(device)
            prior = batch['prior'].to(device)
            y = batch['label'].to(device)
            
            optimizer.zero_grad()
            logits, rul = model(x, prior)
            
            # Synthetic pseudo-RUL target (1.0 for normal, 0.5 for defect)
            rul_target = torch.where(y == 0, 1.0, 0.5).unsqueeze(1).float()
            
            loss_cls = criterion_cls(logits, y)
            loss_rul = criterion_rul(rul, rul_target)
            loss = loss_cls + 0.5 * loss_rul
            
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * x.size(0)
            
        scheduler.step()
        train_loss = running_loss / len(loaders['datasets']['train'])
        
        # Validation
        model.eval()
        all_preds = []
        all_targets = []
        
        with torch.no_grad():
            for batch in val_loader:
                x = batch['spectrum'].to(device)
                prior = batch['prior'].to(device)
                y = batch['label'].to(device)
                
                logits, _ = model(x, prior)
                preds = torch.argmax(logits, dim=1)
                
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(y.cpu().numpy())
                
        metrics = compute_classification_metrics(all_targets, all_preds, num_classes=4)
        val_acc = metrics['accuracy'] * 100.0
        val_f1 = metrics['macro_f1'] * 100.0
        
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_f1': val_f1,
                'val_acc': val_acc,
                'args': vars(args)
            }, best_path)
            mark = "(*) BEST"
        else:
            mark = ""
            
        if epoch % 5 == 0 or epoch == 1 or mark != "":
            print(f"  Epoch [{epoch:02d}/{args.epochs:02d}] | Train Loss: {train_loss:.4f} | "
                  f"Val Acc: {val_acc:.2f}% | Val Macro-F1: {val_f1:.2f}% {mark}")
                  
    elapsed = time.time() - start_time
    print(f"\nTraining completed in {elapsed:.1f}s. Best Val Macro-F1: {best_val_f1:.2f}%")
    print(f"Checkpoint saved to: {best_path}")
    
    # Hold-out Test Evaluation
    print("\nEvaluating Best Teacher on Unseen Hold-out Sets...")
    checkpoint = torch.load(best_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    for split_name in ['test_14mil', 'test_21mil']:
        test_loader = loaders[split_name]
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for batch in test_loader:
                x = batch['spectrum'].to(device)
                prior = batch['prior'].to(device)
                y = batch['label'].to(device)
                logits, _ = model(x, prior)
                preds = torch.argmax(logits, dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(y.cpu().numpy())
                
        m = compute_classification_metrics(all_targets, all_preds, num_classes=4)
        print(f"  [{split_name:10s}] Accuracy: {m['accuracy']*100:.2f}% | Macro-F1: {m['macro_f1']*100:.2f}%")
        print(f"                 Per-Class F1 [Normal, IR, OR, Ball]: {[round(v*100, 2) for v in m['per_class_f1']]}")
        
    print("=" * 70)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train 1D-ResNet Teacher on CWRU Dataset")
    parser.add_argument('--data_dir', type=str, default='data/CWRU_Dataset')
    parser.add_argument('--cache_dir', type=str, default='data/cache')
    parser.add_argument('--save_dir', type=str, default='checkpoints/teacher')
    parser.add_argument('--epochs', type=int, default=15)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--weight_decay', type=float, default=1e-4)
    parser.add_argument('--min_lr', type=float, default=1e-5)
    parser.add_argument('--use_augmentation', action='store_true', default=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cpu', action='store_true', default=False)
    parser.add_argument('--device', type=str, default=None, help="Device (e.g. cuda, cuda:0, cuda:1, cpu)")
    args = parser.parse_args()
    
    train_teacher(args)
