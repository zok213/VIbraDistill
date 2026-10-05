import os, sys
sys.path.insert(0, os.path.abspath('.'))
import numpy as np, torch, torch.nn.functional as F
from src.datasets.cwru_loader import get_cwru_dataloaders
from src.models.student_micro import VibraDistillMicro
from src.quantization.bn_fold import fold_batchnorm_micro
from src.quantization.ptq import quantize_model_symmetric_int8, quantize_inputs
from src.models.npu_emulator import GowinNPU12WayEmulator as E

L = get_cwru_dataloaders('data/CWRU_Dataset', batch_size=128, use_augmentation=False)
m = VibraDistillMicro(); m.load_state_dict(torch.load('checkpoints/student_dkd/best_student_dkd.pt', map_location='cpu')['model_state_dict']); m.eval()
fm = fold_batchnorm_micro(m); pkg = quantize_model_symmetric_int8(fm, calib_loader=L['train'])
S, Ly, e = pkg['act_scales'], pkg['layers'], E()
print('ranges', {k: round(v, 3) for k, v in pkg['act_ranges'].items()})
b = next(iter(L['val'])); N = 40
def cos(a, b): a = a.ravel(); b = b.ravel(); return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
acc = {k: [] for k in ['stage1', 'stage2', 'stage3', 'emb', 'fc', 'logits']}; agree = 0
for i in range(N):
    x, p = b['spectrum'][i:i+1], b['prior'][i:i+1]
    with torch.no_grad():
        s1 = fm.stage1; f1 = F.max_pool1d(F.relu(torch.cat([s1.conv_k3(x), s1.conv_k7(x), s1.conv_k15(x)], 1)), 2)
        f2 = F.max_pool1d(F.relu(fm.stage2[0](f1)), 2); f3 = F.relu(fm.stage3[0](f2))
        emb = F.adaptive_avg_pool1d(f3, 4).flatten(1); h = F.relu(fm.fusion_fc[0](torch.cat([emb, p * 3], 1))); lg = fm.classifier(h)
    xi, pi = quantize_inputs(pkg, x.numpy().reshape(-1), p.numpy()[0])
    c = lambda n, inp, pad: e.conv1d_int8(inp, Ly[n]['weight_int8'], Ly[n]['bias_int32'], Ly[n]['mult'], Ly[n]['shift'], pad)
    q1 = e.maxpool1d(e.relu_int8(np.concatenate([c('stage1_conv_k3', xi, 1), c('stage1_conv_k7', xi, 3), c('stage1_conv_k15', xi, 7)], 0)))
    q2 = e.maxpool1d(e.relu_int8(c('stage2_0', q1, 2))); q3 = e.relu_int8(c('stage3_0', q2, 1)); qe = e.avgpool_int8(q3, 4).reshape(-1)
    fc = Ly['fusion_fc_0']; qh = e.relu_int8(e.dense_int8(np.concatenate([qe, pi]), fc['weight_int8'], fc['bias_int32'], fc['mult'], fc['shift']))
    cl = Ly['classifier']; ql = e.dense_int8(qh, cl['weight_int8'], cl['bias_int32'], cl['mult'], cl['shift'])
    for k, qa, fa, sc in [('stage1', q1, f1, S['stage1']), ('stage2', q2, f2, S['stage2']), ('stage3', q3, f3, S['stage3']),
                          ('emb', qe, emb, S['stage3']), ('fc', qh, h, S['fc']), ('logits', ql, lg, S['logits'])]:
        acc[k].append(cos(qa.astype(np.float64) * sc, fa.numpy()))
    agree += int(np.argmax(ql) == int(lg.argmax()))
print({k: round(float(np.mean(v)), 4) for k, v in acc.items()}, 'argmax agree', agree, '/', N)
