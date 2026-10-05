"""
Statistical Analysis & Publication-Grade Report Generator for 100-Run Ablation Benchmark.
Computes Mean +/- Std, Paired T-Tests (p-values), Hardware-Efficiency Tradeoffs,
and Generates Markdown Summary Artifacts.
"""

import os
import json
import numpy as np
import pandas as pd
from scipy import stats

def analyze_benchmarks(csv_path="experiments/benchmark_100_runs.csv",
                       output_md="experiments/benchmark_100_runs_summary.md",
                       output_json="experiments/benchmark_100_runs_summary.json"):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Cannot find {csv_path}. Benchmark run may still be in progress.")
        
    df = pd.read_csv(csv_path)
    num_trials = len(df)
    print(f"Loaded {num_trials} benchmark trials from {csv_path}")
    
    summary = {
        'total_trials': num_trials,
        'suites': {}
    }
    
    md_lines = []
    md_lines.append("# VibraDistill-Edge: 100-Run Empirical Ablation & Architectural Benchmark Report")
    md_lines.append(f"\n**Total Experimental Runs Analyzed**: {num_trials} trials across 5 distinct research suites.\n")
    
    # -------------------------------------------------------------------------
    # 1. Architectural Benchmarking (Suite 1)
    # -------------------------------------------------------------------------
    s1 = df[df['suite'] == 'Architecture']
    md_lines.append("## 1. Architectural Comparison (Parameter-Matched Baselines)")
    md_lines.append("Comparison of VibraDistillMicro against 1D-CNN, GRU, Bi-LSTM, and MLP baselines under 10 KB parameter budget across 5 seeds.\n")
    
    s1_grouped = s1.groupby('model').agg({
        'val_acc': ['mean', 'std'],
        'val_f1': ['mean', 'std'],
        'test_14mil_f1': ['mean', 'std'],
        'test_21mil_f1': ['mean', 'std'],
        'ece': ['mean', 'std'],
        'params': 'first',
        'macs': 'first',
        'flash_kb_int8': 'first',
        'sram_bytes': 'first',
        'cortex_m0_ms': 'first'
    }).reset_index()
    
    # Markdown Table
    md_lines.append("| Architecture | Params | MACs | SRAM Peak | M0 Latency | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | ECE (%) |")
    md_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    suite1_data = {}
    for _, row in s1_grouped.iterrows():
        m_name = row['model']['']
        val_f1_m, val_f1_s = row['val_f1']['mean'], row['val_f1']['std']
        t14_m, t14_s = row['test_14mil_f1']['mean'], row['test_14mil_f1']['std']
        t21_m, t21_s = row['test_21mil_f1']['mean'], row['test_21mil_f1']['std']
        ece_m, ece_s = row['ece']['mean'], row['ece']['std']
        params = int(row['params']['first'])
        macs = int(row['macs']['first'])
        sram = int(row['sram_bytes']['first'])
        lat = float(row['cortex_m0_ms']['first'])
        
        suite1_data[m_name] = {
            'params': params,
            'macs': macs,
            'sram_bytes': sram,
            'cortex_m0_ms': lat,
            'val_f1_mean': round(float(val_f1_m), 2),
            'val_f1_std': round(float(val_f1_s), 2),
            'test_14mil_mean': round(float(t14_m), 2),
            'test_14mil_std': round(float(t14_s), 2),
            'test_21mil_mean': round(float(t21_m), 2),
            'test_21mil_std': round(float(t21_s), 2),
            'ece_mean': round(float(ece_m), 2),
            'ece_std': round(float(ece_s), 2)
        }
        
        md_lines.append(f"| **{m_name}** | {params:,} | {macs:,} | {sram} B | {lat:.2f} ms | {val_f1_m:.2f} ± {val_f1_s:.2f} | {t14_m:.2f} ± {t14_s:.2f} | {t21_m:.2f} ± {t21_s:.2f} | {ece_m:.2f} ± {ece_s:.2f} |")
        
    summary['suites']['Architecture'] = suite1_data
    
    # Statistical tests: Micro vs others
    micro_val = s1[s1['model'] == 'VibraDistillMicro']['val_f1'].values
    micro_21m = s1[s1['model'] == 'VibraDistillMicro']['test_21mil_f1'].values
    
    md_lines.append("\n### Paired Statistical Significance (VibraDistillMicro vs Baselines across 5 seeds):\n")
    p_values = {}
    for other in ['SingleKernelCNN', 'GRUModel', 'BiLSTMModel', 'MLPBaseline']:
        other_val = s1[s1['model'] == other]['val_f1'].values
        other_21m = s1[s1['model'] == other]['test_21mil_f1'].values
        
        # Paired t-test
        t_stat_val, p_val = stats.ttest_rel(micro_val, other_val)
        t_stat_21, p_21 = stats.ttest_rel(micro_21m, other_21m)
        p_values[other] = {
            'val_p_value': float(p_val),
            'test_21m_p_value': float(p_21)
        }
        md_lines.append(f"- **VibraDistillMicro vs {other}**: Val F1 diff = +{np.mean(micro_val) - np.mean(other_val):.2f}% (p = {p_val:.4e}); Unseen 21-mil F1 diff = +{np.mean(micro_21m) - np.mean(other_21m):.2f}% (p = {p_21:.4e})")
    summary['statistical_tests'] = p_values

    # -------------------------------------------------------------------------
    # 2. Kinematic Prior Ablation (Suite 2)
    # -------------------------------------------------------------------------
    s2 = df[df['suite'] == 'Prior_Ablation']
    md_lines.append("\n## 2. Inductive Kinematic Prior Ablation")
    md_lines.append("Evaluating the physical necessity of Normalized Harmonic Contrast (NHC) kinematic fault priors.\n")
    
    s2_grouped = s2.groupby('variant').agg({
        'val_f1': ['mean', 'std'],
        'test_14mil_f1': ['mean', 'std'],
        'test_21mil_f1': ['mean', 'std'],
        'ece': ['mean', 'std'],
        'mean_vacuity': ['mean', 'std']
    }).reset_index()
    
    md_lines.append("| Prior Configuration | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Mean Vacuity (Uncertainty) | ECE (%) |")
    md_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
    
    suite2_data = {}
    for _, row in s2_grouped.iterrows():
        v_name = row['variant']['']
        val_f1_m, val_f1_s = row['val_f1']['mean'], row['val_f1']['std']
        t14_m, t14_s = row['test_14mil_f1']['mean'], row['test_14mil_f1']['std']
        t21_m, t21_s = row['test_21mil_f1']['mean'], row['test_21mil_f1']['std']
        vac_m, vac_s = row['mean_vacuity']['mean'], row['mean_vacuity']['std']
        ece_m, ece_s = row['ece']['mean'], row['ece']['std']
        
        suite2_data[v_name] = {
            'val_f1_mean': round(float(val_f1_m), 2),
            'test_21mil_mean': round(float(t21_m), 2),
            'mean_vacuity': round(float(vac_m), 3)
        }
        md_lines.append(f"| **{v_name}** | {val_f1_m:.2f} ± {val_f1_s:.2f} | {t14_m:.2f} ± {t14_s:.2f} | {t21_m:.2f} ± {t21_s:.2f} | {vac_m:.3f} ± {vac_s:.3f} | {ece_m:.2f} ± {ece_s:.2f} |")
    summary['suites']['Prior_Ablation'] = suite2_data

    # -------------------------------------------------------------------------
    # 3. Distillation Loss Ablation (Suite 3)
    # -------------------------------------------------------------------------
    s3 = df[df['suite'] == 'Distillation']
    md_lines.append("\n## 3. Knowledge Distillation & Uncertainty Loss Ablation")
    md_lines.append("Evaluating Decoupled Knowledge Distillation (DKD) vs Vanilla Hinton KD vs Standard Cross-Entropy vs Evidential Dirichlet Learning (EDL).\n")
    
    s3_grouped = s3.groupby('variant').agg({
        'val_f1': ['mean', 'std'],
        'test_14mil_f1': ['mean', 'std'],
        'test_21mil_f1': ['mean', 'std'],
        'ece': ['mean', 'std'],
        'mean_vacuity': ['mean', 'std']
    }).reset_index()
    
    md_lines.append("| Training Objective | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Expected Calibration Error (ECE) |")
    md_lines.append("| :--- | :---: | :---: | :---: | :---: |")
    
    suite3_data = {}
    for _, row in s3_grouped.iterrows():
        v_name = row['variant']['']
        val_f1_m, val_f1_s = row['val_f1']['mean'], row['val_f1']['std']
        t14_m, t14_s = row['test_14mil_f1']['mean'], row['test_14mil_f1']['std']
        t21_m, t21_s = row['test_21mil_f1']['mean'], row['test_21mil_f1']['std']
        ece_m, ece_s = row['ece']['mean'], row['ece']['std']
        
        suite3_data[v_name] = {
            'val_f1_mean': round(float(val_f1_m), 2),
            'test_21mil_mean': round(float(t21_m), 2),
            'ece_mean': round(float(ece_m), 2)
        }
        md_lines.append(f"| **{v_name}** | {val_f1_m:.2f} ± {val_f1_s:.2f} | {t14_m:.2f} ± {t14_s:.2f} | {t21_m:.2f} ± {t21_s:.2f} | {ece_m:.2f} ± {ece_s:.2f} |")
    summary['suites']['Distillation'] = suite3_data

    # -------------------------------------------------------------------------
    # 4. Environmental Stress & Noise Robustness (Suite 4)
    # -------------------------------------------------------------------------
    s4 = df[df['suite'] == 'Noise_Robustness']
    md_lines.append("\n## 4. Environmental Stress & Additive Noise Robustness")
    md_lines.append("Testing VibraDistillMicro under severe white Gaussian noise on the envelope spectrum (down to 0 dB SNR).\n")
    
    s4_grouped = s4.groupby('variant').agg({
        'val_f1': ['mean', 'std'],
        'test_14mil_f1': ['mean', 'std'],
        'test_21mil_f1': ['mean', 'std']
    }).reset_index()
    
    md_lines.append("| Signal-to-Noise Ratio (SNR) | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Retention Ratio vs Clean |")
    md_lines.append("| :--- | :---: | :---: | :---: | :---: |")
    
    clean_val = s4[s4['variant'] == 'Clean']['val_f1'].mean()
    suite4_data = {}
    for _, row in s4_grouped.iterrows():
        v_name = row['variant']['']
        val_f1_m, val_f1_s = row['val_f1']['mean'], row['val_f1']['std']
        t14_m, t14_s = row['test_14mil_f1']['mean'], row['test_14mil_f1']['std']
        t21_m, t21_s = row['test_21mil_f1']['mean'], row['test_21mil_f1']['std']
        retention = (val_f1_m / (clean_val + 1e-8)) * 100.0
        
        suite4_data[v_name] = {
            'val_f1_mean': round(float(val_f1_m), 2),
            'retention_pct': round(float(retention), 1)
        }
        md_lines.append(f"| **{v_name}** | {val_f1_m:.2f} ± {val_f1_s:.2f} | {t14_m:.2f} ± {t14_s:.2f} | {t21_m:.2f} ± {t21_s:.2f} | {retention:.1f}% |")
    summary['suites']['Noise_Robustness'] = suite4_data

    # -------------------------------------------------------------------------
    # 5. Quantization & Bit-True Silicon Emulation (Suite 5)
    # -------------------------------------------------------------------------
    s5 = df[df['suite'] == 'Quantization']
    md_lines.append("\n## 5. Post-Training Quantization & Bit-True Gowin NPU Emulation")
    md_lines.append("Verifying numerical parity from 32-bit floating point to folded BatchNorm and Gowin 12-way Systolic INT8 Engine.\n")
    
    s5_grouped = s5.groupby('variant').agg({
        'val_f1': ['mean', 'std'],
        'test_14mil_f1': ['mean', 'std'],
        'test_21mil_f1': ['mean', 'std']
    }).reset_index()
    
    md_lines.append("| Execution Mode | Val F1 (%) | 14-mil Unseen F1 (%) | 21-mil Unseen F1 (%) | Quantization Degradation (delta F1) |")
    md_lines.append("| :--- | :---: | :---: | :---: | :---: |")
    
    fp32_val = s5[s5['variant'] == 'FP32_Baseline']['val_f1'].mean()
    suite5_data = {}
    for _, row in s5_grouped.iterrows():
        v_name = row['variant']['']
        val_f1_m, val_f1_s = row['val_f1']['mean'], row['val_f1']['std']
        t14_m, t14_s = row['test_14mil_f1']['mean'], row['test_14mil_f1']['std']
        t21_m, t21_s = row['test_21mil_f1']['mean'], row['test_21mil_f1']['std']
        delta = val_f1_m - fp32_val
        
        suite5_data[v_name] = {
            'val_f1_mean': round(float(val_f1_m), 2),
            'delta_f1': round(float(delta), 2)
        }
        sign_str = f"+{delta:.2f}%" if delta >= 0 else f"{delta:.2f}%"
        md_lines.append(f"| **{v_name}** | {val_f1_m:.2f} ± {val_f1_s:.2f} | {t14_m:.2f} ± {t14_s:.2f} | {t21_m:.2f} ± {t21_s:.2f} | {sign_str} |")
    summary['suites']['Quantization'] = suite5_data

    # Save outputs
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
        
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
        
    print(f"\nAnalysis complete! Generated:\n  - {output_md}\n  - {output_json}")

if __name__ == "__main__":
    analyze_benchmarks()
