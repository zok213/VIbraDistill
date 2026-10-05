"""
08: Quantization-Aware Training + integer-emulator verification.
Runs on CPU or CUDA (same script is used locally and on Colab T4: `--device cuda`).
Outputs: checkpoints/student_qat/best_qat.pt, experiments/qat_results.json
"""
import os, sys, json, time, argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import numpy as np
import torch
import torch.nn.functional as F

from src.datasets.cwru_loader import get_cwru_dataloaders
from src.models.student_micro import VibraDistillMicro
from src.quantization.bn_fold import fold_batchnorm_micro
from src.quantization.ptq import quantize_model_symmetric_int8, quantize_inputs, calibrate_activation_ranges
from src.quantization.qat import QATMicro
from src.models.npu_emulator import GowinNPU12WayEmulator
from src.utils.metrics import compute_classification_metrics
from src.utils.seed import set_seed


@torch.no_grad()
def predict(model, loader, device):
    model.eval(); P, Y = [], []
    for b in loader:
        lg, _ = model(b['spectrum'].to(device), b['prior'].to(device))
        P += lg.argmax(1).cpu().tolist(); Y += b['label'].tolist()
    return np.array(P), np.array(Y)


def macro_f1(y, p):
    return compute_classification_metrics(y, p)['macro_f1'] * 100


def emulate(pkg, loader):
    em, P, Y = GowinNPU12WayEmulator(), [], []
    for b in loader:
        for x, p, y in zip(b['spectrum'].numpy(), b['prior'].numpy(), b['label'].numpy()):
            xi, pi = quantize_inputs(pkg, x.reshape(-1), p)
            P.append(em.forward_micro(pkg, xi, pi)['prediction']); Y.append(int(y))
    return np.array(P), np.array(Y)


def main(a):
    set_seed(a.seed)
    dev = torch.device(a.device if (a.device != 'cuda' or torch.cuda.is_available()) else 'cpu')
    L = get_cwru_dataloaders(a.data_dir, batch_size=a.batch_size, use_augmentation=True)
    fp = VibraDistillMicro()
    fp.load_state_dict(torch.load(a.checkpoint, map_location='cpu')['model_state_dict']); fp.eval()
    folded = fold_batchnorm_micro(fp)
    ranges = calibrate_activation_ranges(folded, L['train'], 'cpu')       # TRAIN split only
    qat = QATMicro(folded.to('cpu'), ranges).to(dev)
    teacher = copy.deepcopy(folded).to(dev).eval()
    opt = torch.optim.AdamW(qat.parameters(), lr=a.lr, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs, eta_min=a.lr * 0.05)

    pv, yv = predict(qat, L['val'], dev); print(f'[init QAT, before finetune] val F1 {macro_f1(yv, pv):.2f}')
    best, best_state, log = -1.0, None, []
    for ep in range(1, a.epochs + 1):
        qat.train(); t0 = time.time(); tot = 0.0
        for b in L['train']:
            x, pr, y = b['spectrum'].to(dev), b['prior'].to(dev), b['label'].to(dev)
            with torch.no_grad():
                tl, _ = teacher(x, pr)
            lg, _ = qat(x, pr)
            loss = F.cross_entropy(lg, y) + a.distill * F.mse_loss(lg, tl)
            opt.zero_grad(); loss.backward(); opt.step(); tot += float(loss.detach()) * len(y)
        sched.step()
        pv, yv = predict(qat, L['val'], dev); f1 = macro_f1(yv, pv)
        log.append({'epoch': ep, 'train_loss': tot / len(L['train'].dataset), 'val_f1_fakequant': round(f1, 2)})
        print(f'ep {ep:02d} loss {log[-1]["train_loss"]:.4f} val F1 (fake-quant) {f1:.2f} [{time.time()-t0:.1f}s]')
        if f1 > best:
            best = f1; best_state = {k: v.detach().cpu().clone() for k, v in qat.state_dict().items()}
    qat.load_state_dict(best_state)

    os.makedirs('checkpoints/student_qat', exist_ok=True)
    torch.save({'qat_state': best_state, 'act_ranges': ranges, 'val_f1_fakequant': best}, 'checkpoints/student_qat/best_qat.pt')
    exported = qat.to('cpu').export_folded()
    pkg = quantize_model_symmetric_int8(exported, act_ranges=ranges)   # same ranges as training
    out = {'seed': a.seed, 'epochs': a.epochs, 'device': str(dev), 'act_ranges': ranges, 'train_log': log, 'splits': {}}
    for split in ['val', 'test_14mil', 'test_21mil']:
        pf, y = predict(fp, L[split], 'cpu')
        pq, _ = predict(qat.to('cpu'), L[split], 'cpu')
        pi, _ = emulate(pkg, L[split])
        out['splits'][split] = {
            'fp32_f1': round(macro_f1(y, pf), 2), 'qat_fakequant_f1': round(macro_f1(y, pq), 2),
            'int8_emulator_f1': round(macro_f1(y, pi), 2),
            'int8_emulator_acc': round(float((pi == y).mean() * 100), 2),
            'emulator_vs_fakequant_agreement_pct': round(float((pi == pq).mean() * 100), 2), 'n': int(len(y))}
        print(split, out['splits'][split])
    os.makedirs('experiments', exist_ok=True)
    with open(f'experiments/qat_results_seed{a.seed}.json', 'w') as f:
        json.dump(out, f, indent=2)


if __name__ == '__main__':
    import copy
    ap = argparse.ArgumentParser()
    ap.add_argument('--data_dir', default='data/CWRU_Dataset')
    ap.add_argument('--checkpoint', default='checkpoints/student_dkd/best_student_dkd.pt')
    ap.add_argument('--epochs', type=int, default=15)
    ap.add_argument('--lr', type=float, default=5e-4)
    ap.add_argument('--distill', type=float, default=0.5)
    ap.add_argument('--batch_size', type=int, default=64)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--device', default='cpu')
    main(ap.parse_args())
