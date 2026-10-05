"""
Automatic hardware profiler (forward-hook based; no per-model hard-coded numbers).

Measured exactly from the model graph:
  - params, INT8 weight bytes, MACs (Conv1d / Linear / GRU / LSTM), activation tensor sizes.
Estimated (clearly labelled, parameters exposed):
  - Cortex-M0 latency  = MACs * cycles_per_mac / f_clk   (cycles_per_mac is an ASSUMPTION;
    replace with on-target DWT/SysTick measurements once firmware runs)
  - FPGA latency       = MACs / (parallel_macs * f_clk)  (ideal, ignores memory stalls/control)
  - peak_act_bytes     = max over layers of (input + output) INT8 activation bytes, i.e. the
    minimum ping-pong buffer for a layer-by-layer executor.
"""
import torch
import torch.nn as nn


def _rnn_macs(mod, inp, out):
    x = inp[0]
    T = x.shape[1] if mod.batch_first else x.shape[0]
    gates = 4 if isinstance(mod, nn.LSTM) else 3
    dirs = 2 if mod.bidirectional else 1
    macs, in_sz = 0, mod.input_size
    for _ in range(mod.num_layers):
        macs += dirs * T * gates * (in_sz * mod.hidden_size + mod.hidden_size * mod.hidden_size)
        in_sz = mod.hidden_size * dirs
    return macs


def profile_model_hardware(model: nn.Module, in_bins: int = 257, physics_dim: int = 4,
                           m0_cycles_per_mac: float = 4.0, m0_clk_hz: float = 60e6,
                           fpga_parallel_macs: int = 12, fpga_clk_hz: float = 100e6,
                           device='cpu') -> dict:
    model = model.to(device).eval()
    stats = {'macs': 0, 'peak_act_bytes': 0}
    hooks = []

    def hook(mod, inp, out):
        o = out[0] if isinstance(out, tuple) else out
        if isinstance(mod, nn.Conv1d):
            stats['macs'] += o.numel() // o.shape[0] * (mod.in_channels // mod.groups) * mod.kernel_size[0]
        elif isinstance(mod, nn.Linear):
            stats['macs'] += mod.in_features * mod.out_features
        elif isinstance(mod, (nn.GRU, nn.LSTM)):
            stats['macs'] += _rnn_macs(mod, inp, out)
        if isinstance(mod, (nn.Conv1d, nn.Linear, nn.GRU, nn.LSTM)):
            ib = inp[0][0].numel() if torch.is_tensor(inp[0]) else 0
            stats['peak_act_bytes'] = max(stats['peak_act_bytes'], ib + o[0].numel())

    for m in model.modules():
        if isinstance(m, (nn.Conv1d, nn.Linear, nn.GRU, nn.LSTM)):
            hooks.append(m.register_forward_hook(hook))
    with torch.no_grad():
        model(torch.zeros(1, 1, in_bins, device=device), torch.zeros(1, physics_dim, device=device))
    for h in hooks:
        h.remove()

    params = sum(p.numel() for p in model.parameters())
    macs = int(stats['macs'])
    return {
        'params': params,
        'flash_kb_int8': params / 1024.0,
        'flash_kb_fp32': params * 4 / 1024.0,
        'macs': macs,
        'sram_peak_bytes': int(stats['peak_act_bytes']),
        'cortex_m0_latency_ms': macs * m0_cycles_per_mac / m0_clk_hz * 1e3,
        'gowin_fpga_latency_ms': macs / (fpga_parallel_macs * fpga_clk_hz) * 1e3,
        'assumptions': {'m0_cycles_per_mac': m0_cycles_per_mac, 'm0_clk_hz': m0_clk_hz,
                        'fpga_parallel_macs': fpga_parallel_macs, 'fpga_clk_hz': fpga_clk_hz,
                        'latency_is_estimate': True},
    }
