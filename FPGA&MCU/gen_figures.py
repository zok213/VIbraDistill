"""
gen_figures.py — generate all 4 proposal figures into figures/
Run:  python gen_figures.py
"""
import os, numpy as np
import scipy.signal as signal
from scipy.fft import rfft
from scipy.signal import hilbert
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

os.makedirs("figures", exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.size": 8,
    "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "figure.dpi": 150, "lines.linewidth": 1.2,
})

# ── Figure 1: FIR ───────────────────────────────────────────────────────────
fs = 12000; M = 64; f_lo, f_hi = 2000, 5000
h_lin = signal.firwin(M, [f_lo, f_hi], pass_zero=False, fs=fs, window="hamming")
h_min = signal.minimum_phase(h_lin, method="homomorphic")
NFFT = 8192
H_lin = np.abs(rfft(h_lin, NFFT))
H_min = np.abs(rfft(h_min, NFFT))
freqs = np.linspace(0, fs/2, NFFT//2+1)
band  = (freqs >= f_lo) & (freqs <= f_hi)
_, gd_lin_w = signal.group_delay((h_lin, [1]), NFFT, fs=fs)
_, gd_min_w = signal.group_delay((h_min, [1]), NFFT, fs=fs)
gd_freqs_all = np.linspace(0, fs, NFFT, endpoint=False)
gd_band = (gd_freqs_all >= f_lo) & (gd_freqs_all <= f_hi) & (gd_freqs_all <= fs/2)
z_lin = np.roots(h_lin); z_min = np.roots(h_min)
zeros_out_min = int(np.sum(np.abs(z_min) > 1 + 1e-6))
zeros_out_lin = int(np.sum(np.abs(z_lin) > 1 + 1e-6))

fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.1))
ax = axes[0]
ax.plot(freqs/1000, 20*np.log10(H_lin+1e-15), color="steelblue", label=r"$|H_\mathrm{lin}|$")
ax.plot(freqs/1000, 20*np.log10(H_min**2+1e-15), color="crimson", ls="--", label=r"$|H_\mathrm{min}|^2$")
ax.axvline(f_lo/1000, color="gray", lw=0.6, ls=":"); ax.axvline(f_hi/1000, color="gray", lw=0.6, ls=":")
ax.set_xlim(0,6); ax.set_ylim(-80,5)
ax.set_xlabel("Freq (kHz)"); ax.set_ylabel("Magnitude (dB)"); ax.set_title("(a) Magnitude", pad=3)
ax.legend(loc="lower right")

ax = axes[1]
gd_f = gd_freqs_all[gd_band]
gd_lin_ms = gd_lin_w[gd_band] / fs * 1000
gd_min_ms = gd_min_w[gd_band] / fs * 1000
ax.plot(gd_f/1000, gd_lin_ms, color="steelblue",
        label=f"Linear ({np.mean(gd_lin_ms):.1f} ms)")
ax.plot(gd_f/1000, np.clip(gd_min_ms, -1, 5), color="crimson", ls="--",
        label=f"Min-phase")
ax.set_xlabel("Freq (kHz)"); ax.set_ylabel("Group delay (ms)"); ax.set_title("(b) Group delay", pad=3)
ax.legend(); ax.set_ylim(-0.3, 3.2)

ax = axes[2]
theta = np.linspace(0, 2*np.pi, 300)
ax.plot(np.cos(theta), np.sin(theta), "k-", lw=0.5)
ax.scatter(z_lin.real, z_lin.imag, s=10, marker="o", color="steelblue",
           label=f"Lin ({zeros_out_lin} out)", alpha=0.7, zorder=3)
ax.scatter(z_min.real, z_min.imag, s=12, marker="x", color="crimson",
           label=f"Min ({zeros_out_min} out)", lw=1.0, zorder=4)
ax.set_aspect("equal"); ax.set_xlim(-1.6,1.6); ax.set_ylim(-1.6,1.6)
ax.set_xlabel("Re"); ax.set_ylabel("Im"); ax.set_title("(c) Zeros", pad=3)
ax.legend(fontsize=6)

plt.tight_layout(pad=0.5)
plt.savefig("figures/fig_fir.pdf", bbox_inches="tight")
plt.savefig("figures/fig_fir.png", bbox_inches="tight", dpi=150)
plt.close(); print("Saved figures/fig_fir.pdf")

# ── Figure 2: Envelope ──────────────────────────────────────────────────────
f_carrier = 3500.0; f_fault = 107.4; fs_e = 12000; N = 4096
rng0 = np.random.default_rng(0)
t = np.arange(N)/fs_e
amp = 1.0 + 0.4*np.cos(2*np.pi*f_fault*t)
y   = amp*np.cos(2*np.pi*f_carrier*t) + rng0.normal(0, 0.3, N)
sos_bp = signal.butter(4, [2000,5500], btype="bandpass", fs=fs_e, output="sos")
y_bp   = signal.sosfilt(sos_bp, y)
sos_lp = signal.butter(2, 1000, btype="lowpass", fs=fs_e, output="sos")
env_rect = signal.sosfilt(sos_lp, np.abs(y_bp)); env_rect -= env_rect.mean()
env_hilb = np.abs(hilbert(y_bp));                env_hilb -= env_hilb.mean()

def fault_snr(env, f0, fs_, N_):
    S = np.abs(rfft(env*np.hanning(N_)))
    bw = fs_/N_; b = int(round(f0/bw))
    sig = np.max(S[max(0,b-1):b+2])**2
    mask = np.ones(len(S), dtype=bool)
    mask[max(0,b-2):b+3] = False
    noise = np.median(S[mask]**2)+1e-30
    return 10*np.log10(sig/noise)

SEEDS = 30
snr_r, snr_h = [], []
for seed in range(SEEDS):
    rng_ = np.random.default_rng(seed)
    t_ = np.arange(N)/fs_e
    amp_ = 1.0 + 0.4*np.cos(2*np.pi*f_fault*t_)
    y_   = amp_*np.cos(2*np.pi*f_carrier*t_) + rng_.normal(0, 0.3, N)
    yb_  = signal.sosfilt(sos_bp, y_)
    er_  = signal.sosfilt(sos_lp, np.abs(yb_)); er_ -= er_.mean()
    eh_  = np.abs(hilbert(yb_));                eh_ -= eh_.mean()
    snr_r.append(fault_snr(er_, f_fault, fs_e, N))
    snr_h.append(fault_snr(eh_, f_fault, fs_e, N))
snr_r = np.array(snr_r); snr_h = np.array(snr_h)

freqs_e = np.linspace(0, fs_e/2, N//2+1)
S_rect = np.abs(rfft(env_rect*np.hanning(N)))
S_hilb = np.abs(rfft(env_hilb*np.hanning(N)))

fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.2))
ax = axes[0]
ax.plot(t[:512]*1000, env_rect[:512], color="crimson", lw=0.8, label="Rectifier+LPF")
ax.plot(t[:512]*1000, env_hilb[:512], color="steelblue", ls="--", lw=0.8, label="Hilbert")
ax.set_xlabel("Time (ms)"); ax.set_ylabel("Amplitude"); ax.set_title("(a) Envelope (time, seed 0)", pad=3)
ax.legend()
ax = axes[1]
ax.plot(freqs_e[:300], S_rect[:300], color="crimson", lw=0.8,
        label=f"Rect ({np.mean(snr_r):.1f} dB, 30 seeds)")
ax.plot(freqs_e[:300], S_hilb[:300], color="steelblue", ls="--", lw=0.8,
        label=f"Hilbert ({np.mean(snr_h):.1f} dB, 30 seeds)")
ax.axvline(f_fault, color="gray", lw=0.7, ls=":", label=f"BPFO={f_fault} Hz")
ax.set_xlabel("Frequency (Hz)"); ax.set_ylabel("|FFT|"); ax.set_title("(b) Envelope spectrum", pad=3)
ax.legend(fontsize=6)
plt.tight_layout(pad=0.5)
plt.savefig("figures/fig_envelope.pdf", bbox_inches="tight")
plt.savefig("figures/fig_envelope.png", bbox_inches="tight", dpi=150)
plt.close(); print("Saved figures/fig_envelope.pdf")

# ── Figure 3: Resolution ────────────────────────────────────────────────────
Nb=9; d=7.94; D=39.04; fr=29.95
c = np.cos(0.0)
bpfo = (Nb/2)*fr*(1 - d/D*c)
bpfi = (Nb/2)*fr*(1 + d/D*c)
bsf  = (D/(2*d))*fr*(1 - (d/D*c)**2)
ftf  = (fr/2)*(1 - d/D*c)
fault_freqs = {"BPFO": bpfo, "BPFI": bpfi, "BSF": bsf, "FTF": ftf}
df_C1 = 12000/512; df_C2 = 2000/512

fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.2))
ax = axes[0]
N_vals = [128,256,512,1024,2048]
ax.plot(N_vals, [12000/n for n in N_vals], "o-", color="crimson", markersize=4, label="C1 (no dec.)")
ax.plot(N_vals, [2000/n  for n in N_vals], "s--",color="steelblue", markersize=4, label="C2 (dec.×6)")
ax.axhline(1.0, color="gray", lw=0.6, ls=":")
ax.set_xlabel("FFT length N"); ax.set_ylabel("Bin width Δf (Hz)")
ax.set_title("(a) Resolution vs N", pad=3); ax.legend()
ax.set_yscale("log"); ax.set_xscale("log")
ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
ax.yaxis.set_major_formatter(ticker.ScalarFormatter())

ax = axes[1]
colors_f = {"BPFO":"tab:blue","BPFI":"tab:orange","BSF":"tab:green","FTF":"tab:red"}
for name, freq in fault_freqs.items():
    ax.axvline(freq, color=colors_f[name], lw=1.3, label=f"{name}={freq:.1f} Hz")
for b in np.arange(0, 450, df_C1):
    ax.axvspan(b, min(b+df_C1,450), alpha=0.08, color="crimson", lw=0)
for b in np.arange(0, 450, df_C2):
    ax.axvspan(b, min(b+df_C2,450), alpha=0.08, color="steelblue", lw=0)
ax.set_xlim(0,450); ax.set_ylim(0,1.2); ax.set_xlabel("Frequency (Hz)")
ax.set_yticks([]); ax.legend(fontsize=6, loc="upper right")
ax.set_title("(b) Fault lines vs bin grids (N=512)", pad=3)
ax.text(0.02, 0.85, f"C1: Δf={df_C1:.1f} Hz", color="crimson", fontsize=6, transform=ax.transAxes)
ax.text(0.02, 0.75, f"C2: Δf={df_C2:.1f} Hz", color="steelblue", fontsize=6, transform=ax.transAxes)
plt.tight_layout(pad=0.5)
plt.savefig("figures/fig_resolution.pdf", bbox_inches="tight")
plt.savefig("figures/fig_resolution.png", bbox_inches="tight", dpi=150)
plt.close(); print("Saved figures/fig_resolution.pdf")

# ── Figure 4: ACP ───────────────────────────────────────────────────────────
T_SIM=3000; alpha_cp=0.10; gamma_cp=0.05; q_init=1.0; N_SEEDS=20

def make_residuals(T, seed):
    rng_ = np.random.default_rng(seed)
    scales = np.ones(T)
    scales[1000:] = 3.0; scales[2000:] = 1.5
    return rng_.normal(0, scales)

def run_acp(residuals, gamma, alpha, q0, sign_correct=True, delay=0):
    T = len(residuals); q = q0; errors = []; issued = []
    for t in range(T):
        err = 1.0 if abs(residuals[t]) > q else 0.0
        errors.append(err); issued.append((q, residuals[t]))
        rt = t - delay
        if 0 <= rt < len(issued):
            q_r, y_r = issued[rt]
            e_r = 1.0 if abs(y_r) > q_r else 0.0
            if sign_correct:
                q = max(0.0, q + gamma*(e_r - alpha))
            else:
                q = max(0.0, q + gamma*(alpha - e_r))
    return np.array(errors)

def rolling(arr, w=200):
    return np.convolve(arr, np.ones(w)/w, mode="same")

wrong_rates, correct_rates = [], []
for seed in range(N_SEEDS):
    res = make_residuals(T_SIM, seed)
    wrong_rates.append(np.mean(run_acp(res, gamma_cp, alpha_cp, q_init, sign_correct=False)))
    correct_rates.append(np.mean(run_acp(res, gamma_cp, alpha_cp, q_init, sign_correct=True)))

fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.3))

# (a) sign
ax = axes[0]
mw = np.mean([rolling(run_acp(make_residuals(T_SIM,s), gamma_cp, alpha_cp, q_init, False)) for s in range(N_SEEDS)], axis=0)
mc = np.mean([rolling(run_acp(make_residuals(T_SIM,s), gamma_cp, alpha_cp, q_init, True))  for s in range(N_SEEDS)], axis=0)
ax.plot(mw, color="crimson", lw=0.9, label=f"Wrong ({np.mean(wrong_rates):.2f})")
ax.plot(mc, color="steelblue", lw=0.9, label=f"Correct ({np.mean(correct_rates):.3f})")
ax.axhline(alpha_cp, color="gray", ls="--", lw=0.7, label=f"Target {alpha_cp}")
ax.axvline(1000, color="orange", ls=":", lw=0.7); ax.axvline(2000, color="orange", ls=":", lw=0.7)
ax.set_ylim(-0.05,1.1); ax.set_xlabel("Time step"); ax.set_ylabel("Rolling miss rate")
ax.set_title("(a) Sign comparison", pad=3); ax.legend(fontsize=5.5)

# (b) delay
ax = axes[1]
for d, col in [(0,"steelblue"),(50,"darkorange"),(200,"crimson")]:
    mr = np.mean([rolling(run_acp(make_residuals(T_SIM,s), gamma_cp, alpha_cp, q_init, delay=d)) for s in range(N_SEEDS)], axis=0)
    ax.plot(mr, color=col, lw=0.9, label=f"d={d}")
ax.axhline(alpha_cp, color="gray", ls="--", lw=0.7)
ax.axvline(1000, color="orange", ls=":", lw=0.7); ax.axvline(2000, color="orange", ls=":", lw=0.7)
ax.set_ylim(-0.05,0.8); ax.set_xlabel("Time step"); ax.set_ylabel("Rolling miss rate")
ax.set_title("(b) Feedback delay", pad=3); ax.legend(fontsize=6)

# (c) gamma
ax = axes[2]
for g, col in [(0.01,"navy"),(0.05,"steelblue"),(0.20,"skyblue")]:
    mr = np.mean([rolling(run_acp(make_residuals(T_SIM,s), g, alpha_cp, q_init)) for s in range(N_SEEDS)], axis=0)
    ax.plot(mr, color=col, lw=0.9, label=f"γ={g}")
ax.axhline(alpha_cp, color="gray", ls="--", lw=0.7)
ax.axvline(1000, color="orange", ls=":", lw=0.7); ax.axvline(2000, color="orange", ls=":", lw=0.7)
ax.set_ylim(-0.05,0.6); ax.set_xlabel("Time step"); ax.set_ylabel("Rolling miss rate")
ax.set_title("(c) Step size γ", pad=3); ax.legend(fontsize=6)

plt.tight_layout(pad=0.5)
plt.savefig("figures/fig_acp.pdf", bbox_inches="tight")
plt.savefig("figures/fig_acp.png", bbox_inches="tight", dpi=150)
plt.close(); print("Saved figures/fig_acp.pdf")

print("\nAll 4 figures written to figures/")
