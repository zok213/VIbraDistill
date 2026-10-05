"""
07: FP32 vs Folded-BN vs INT8 (integer emulator) parity on real CWRU splits.
Calibration uses the TRAIN split only (no val/test leakage). Writes experiments/int8_parity.json.
"""
import os, sys, json, argparse, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import numpy as np
import torch

from src.datasets.cwru_loader import get_cwru_dataloaders
from src.models.student_micro import VibraDistillMicro
from src.quantization.bn_fold import fold_batchnorm_micro
from src.quantization.ptq import quantize_model_symmetric_int8, quantize_inputs
from src.models.npu_emulator import GowinNPU12WayEmulator
from src.utils.metrics import compute_classification_metrics


@torch.no_grad()
def eval_float(model, loader):
    P, Y = [], []
    for b in loader:
        logits, _ = model(b['spectrum'], b['prior'])
        P += logits.argmax(1).tolist(); Y += b['label'].tolist()
    return np.array(P), np.array(Y)


def eval_int8(pkg, loader):
    em, P, Y = GowinNPU12WayEmulator(), [], []
    for b in loader:
        for x, p, y in zip(b['spectrum'].numpy(), b['prior'].numpy(), b['label'].numpy()):
            xi, pi = quantize_inputs(pkg, x.reshape(-1), p)
            P.append(em.forward_micro(pkg, xi, pi)['prediction']); Y.append(int(y))
    return np.array(P), np.array(Y)


def main(a):
    torch.manual_seed(0)
    L = get_cwru_dataloaders(a.data_dir, batch_size=256, use_augmentation=False)
    ck = torch.load(a.checkpoint, map_location='cpu')
    if 'qat_state' in ck:
        from src.quantization.qat import QATMicro
        base = VibraDistillMicro()
        folded_base = fold_batchnorm_micro(base)
        qat = QATMicro(folded_base, ck['act_ranges'])
        qat.load_state_dict(ck['qat_state'])
        folded = qat.export_folded()
        m = folded  # in QAT, float model is already folded
        pkg = quantize_model_symmetric_int8(folded, act_ranges=ck['act_ranges'])
    else:
        m = VibraDistillMicro()
        m.load_state_dict(ck['model_state_dict']); m.eval()
        folded = fold_batchnorm_micro(m)
        pkg = quantize_model_symmetric_int8(folded, calib_loader=L['train'])
    out = {'checkpoint': a.checkpoint, 'act_ranges': pkg['act_ranges'],
           'requant': {k: {'mult': np.asarray(v['mult']).tolist(), 'shift': np.asarray(v['shift']).tolist()}
                       for k, v in pkg['layers'].items()}, 'splits': {}}
    for split in ['val', 'test_14mil', 'test_21mil']:
        t = time.time()
        pf, y = eval_float(m, L[split]); pb, _ = eval_float(folded, L[split]); pq, _ = eval_int8(pkg, L[split])
        r = {}
        for name, p in [('fp32', pf), ('folded_bn', pb), ('int8_emulator', pq)]:
            mt = compute_classification_metrics(y, p)
            r[name] = {'accuracy': round(mt['accuracy'] * 100, 2), 'macro_f1': round(mt['macro_f1'] * 100, 2)}
        r['int8_vs_fp32_prediction_agreement_pct'] = round(float((pq == pf).mean() * 100), 2)
        r['n_samples'] = int(len(y))
        out['splits'][split] = r
        print(split, json.dumps(r), f'{time.time()-t:.1f}s')
    os.makedirs('experiments', exist_ok=True)
    with open('experiments/int8_parity.json', 'w') as f:
        json.dump(out, f, indent=2)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data_dir', default='data/CWRU_Dataset')
    ap.add_argument('--checkpoint', default='checkpoints/student_dkd/best_student_dkd.pt')
    main(ap.parse_args())
