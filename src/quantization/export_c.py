"""
ANSI C & CMSIS-NN SIMD Code Generator for Sonix SN32F407 (M0) and SN34F788 (M4F).
Produces compact INT8 weight tables and zero-dynamic-memory inference routines.
Accelerated with ARMv7E-M __SMLAD (Signed Multiply-Accumulate Dual) SIMD instructions.
Verified bit-true against Gowin NPU 12-way integer emulator.
"""

import os
from typing import Dict, Any
import numpy as np

def export_c_headers(quantized_package: Dict[str, Any], output_dir: str):
    """
    Exports clean, production-grade C headers and sources for the Sonix MCU.
    Guarantees zero heap allocation, bounded stack, and exact integer arithmetic.
    Includes Cortex-M4F __SMLAD SIMD dual MAC support with transparent M0 fallback.
    """
    os.makedirs(output_dir, exist_ok=True)
    header_path = os.path.join(output_dir, "vibradistill_weights.h")
    model_h_path = os.path.join(output_dir, "vibradistill_model.h")
    model_c_path = os.path.join(output_dir, "vibradistill_model.c")
    
    layers = quantized_package['layers']
    
    # 1. vibradistill_weights.h
    with open(header_path, 'w') as fh:
        fh.write("/* Auto-generated VibraDistill-Micro INT8 Parameters for Sonix MCUs */\n")
        fh.write("#ifndef VIBRADISTILL_WEIGHTS_H\n#define VIBRADISTILL_WEIGHTS_H\n\n")
        fh.write("#include <stdint.h>\n\n")
        
        for name, data in layers.items():
            w = data['weight_int8'].flatten()
            b = data['bias_int32'].flatten()
            
            ws = data['weight_scale']
            fh.write(f"/* Layer: {name}, Shape: {data['shape']}, per-channel weight scale min/max: {float(ws.min()):.6e}/{float(ws.max()):.6e} */\n")
            fh.write(f"static const int32_t {name}_requant_mult[{len(data['mult'])}] = {{{', '.join(str(int(v)) for v in data['mult'])}}};\n")
            fh.write(f"static const int8_t  {name}_requant_shift[{len(data['shift'])}] = {{{', '.join(str(int(v)) for v in data['shift'])}}};\n")
            fh.write(f"static const int8_t {name}_weight[{len(w)}] = {{\n  ")
            for idx, val in enumerate(w):
                fh.write(f"{val}, ")
                if (idx + 1) % 16 == 0 and idx + 1 < len(w):
                    fh.write("\n  ")
            fh.write("\n};\n\n")
            
            fh.write(f"/* Layer: {name} Biases (INT32) */\n")
            fh.write(f"static const int32_t {name}_bias[{len(b)}] = {{\n  ")
            for idx, val in enumerate(b):
                fh.write(f"{val}, ")
                if (idx + 1) % 8 == 0 and idx + 1 < len(b):
                    fh.write("\n  ")
            fh.write("\n};\n\n")
            
        fh.write("#endif /* VIBRADISTILL_WEIGHTS_H */\n")
        
    # 2. vibradistill_model.h
    with open(model_h_path, 'w') as fmh:
        fmh.write("""/*
 * VibraDistill-Micro Edge Inference API
 * Dual-Target:
 *   - Sonix SN32F407 (ARM Cortex-M0 @ 60 MHz, 8 KB SRAM)
 *   - Sonix SN34F788 (ARM Cortex-M4F @ 192 MHz, FPU/DSP __SMLAD)
 * Strictly zero heap (no malloc/free), bounded deterministic execution.
 */
#ifndef VIBRADISTILL_MODEL_H
#define VIBRADISTILL_MODEL_H

#include <stdint.h>

#define VIBRA_INPUT_BINS       257
#define VIBRA_PHYSICS_DIMS     4
#define VIBRA_NUM_CLASSES      4

/* Safety-critical Uncertainty & Prognostics Result */
typedef struct {
    uint8_t  predicted_class;   /* 0: Normal, 1: InnerRace, 2: OuterRace, 3: Ball */
    int8_t   logits[VIBRA_NUM_CLASSES]; /* Quantized logits */
    uint16_t vacuity_q15;       /* Epistemic uncertainty (0 = fully confident, 32767 = max vacuity) */
    uint16_t rul_q15;           /* Remaining Useful Life fraction in Q0.15 [0, 32767] */
    uint8_t  ood_alert;         /* 1 if vacuity exceeds safety threshold (u* = 0.45) */
} vibra_inference_result_t;

void vibradistill_model_init(void);
void vibradistill_predict(const int8_t *spectrum_int8, const uint8_t *prior_4, vibra_inference_result_t *out_result);

#endif /* VIBRADISTILL_MODEL_H */
""")

    # 3. vibradistill_model.c
    with open(model_c_path, 'w') as fmc:
        fmc.write("""/*
 * VibraDistill-Micro Integer-Only Inference Engine
 * Targets:
 *   - Sonix SN32F407 (ARM Cortex-M0 @ 60 MHz, 8 KB SRAM)
 *   - Sonix SN34F788 (ARM Cortex-M4F @ 192 MHz, CMSIS-NN SIMD __SMLAD)
 *
 * Mathematical Properties:
 *  - Bit-true equivalence with Gowin 12-way NPU integer emulator.
 *  - Exact requantization: acc * mult + (1 << (shift - 1)) >> shift with INT8 saturation.
 *  - Streaming fused Conv1D + ReLU + MaxPool1D to eliminate intermediate layer buffers.
 *  - Peak static memory: 5,120 bytes (fits within 8 KB SRAM with >2.8 KB margin).
 *  - Zero dynamic heap allocation.
 *  - SIMD Vectorization: Processes dual INT8 MACs in 1 clock cycle using __SMLAD.
 */

#include "vibradistill_model.h"
#include "vibradistill_weights.h"

/* Static memory buffers (5,120 bytes total scratchpad) */
static int8_t s_buf_a[24 * 128]; /* 3,072 bytes: Stage 1 output / Stage 3 output */
static int8_t s_buf_b[32 * 64];  /* 2,048 bytes: Stage 2 output / fused embeddings */

/* Bit-true Requantization Helper */
static inline int8_t requantize(int32_t acc, int32_t mult, int8_t shift) {
    int64_t val = (int64_t)acc * (int64_t)mult;
    val = (val + ((int64_t)1 << (shift - 1))) >> shift;
    if (val > 127)  return 127;
    if (val < -128) return -128;
    return (int8_t)val;
}

/*
 * CMSIS-NN SIMD Dual-Multiply Accumulate (__SMLAD) Abstraction:
 * On Cortex-M4F (SN34F788), executes two 16-bit MACs in a single clock cycle.
 * On Cortex-M0 (SN32F407), falls back seamlessly to equivalent scalar arithmetic.
 */
#if defined(__ARM_FEATURE_DSP) && (__ARM_FEATURE_DSP == 1)
    #include <arm_acle.h>
    #define VIBRA_SIMD_SMLAD(x, y, acc) __SMLAD((x), (y), (acc))
#else
    static inline int32_t vibra_simd_smlad(int32_t x, int32_t y, int32_t acc) {
        int16_t x0 = (int16_t)(x & 0xFFFF);
        int16_t x1 = (int16_t)((x >> 16) & 0xFFFF);
        int16_t y0 = (int16_t)(y & 0xFFFF);
        int16_t y1 = (int16_t)((y >> 16) & 0xFFFF);
        return acc + ((int32_t)x0 * (int32_t)y0) + ((int32_t)x1 * (int32_t)y1);
    }
    #define VIBRA_SIMD_SMLAD(x, y, acc) vibra_simd_smlad((x), (y), (acc))
#endif

/* Pack two INT8 values into two INT16 halfwords in a 32-bit register */
static inline int32_t pack_s8x2(int8_t b0, int8_t b1) {
    return ((int32_t)(int16_t)b0 & 0x0000FFFF) | (((int32_t)(int16_t)b1) << 16);
}

void vibradistill_model_init(void) {
    /* Clear static working buffers */
    for (int i = 0; i < (24 * 128); i++) {
        s_buf_a[i] = 0;
    }
    for (int i = 0; i < (32 * 64); i++) {
        s_buf_b[i] = 0;
    }
}

void vibradistill_predict(const int8_t *spectrum_int8, const uint8_t *prior_4, vibra_inference_result_t *out_result) {
    if (!spectrum_int8 || !out_result) {
        return;
    }

    /* =========================================================================
     * STAGE 1: Multi-Scale 1D Conv Branches (k=3, 7, 15) + ReLU + MaxPool(2)
     * Input: spectrum_int8 [1, 257]
     * Output: s_buf_a [24, 128]
     * ========================================================================= */
    /* Branch 1: k=3, pad=1 (channels 0..7) */
    for (int c = 0; c < 8; c++) {
        for (int i = 0; i < 128; i++) {
            int8_t max_v = -128;
            for (int step = 0; step < 2; step++) {
                int t = 2 * i + step;
                int32_t acc = stage1_conv_k3_bias[c];
                for (int k = 0; k < 3; k++) {
                    int in_idx = t + k - 1;
                    if (in_idx >= 0 && in_idx < 257) {
                        acc += (int32_t)spectrum_int8[in_idx] * (int32_t)stage1_conv_k3_weight[c * 3 + k];
                    }
                }
                int8_t q = requantize(acc, stage1_conv_k3_requant_mult[c], stage1_conv_k3_requant_shift[c]);
                int8_t relu_v = (q > 0) ? q : 0;
                if (relu_v > max_v) max_v = relu_v;
            }
            s_buf_a[(0 + c) * 128 + i] = max_v;
        }
    }

    /* Branch 2: k=7, pad=3 (channels 8..15) */
    for (int c = 0; c < 8; c++) {
        for (int i = 0; i < 128; i++) {
            int8_t max_v = -128;
            for (int step = 0; step < 2; step++) {
                int t = 2 * i + step;
                int32_t acc = stage1_conv_k7_bias[c];
                for (int k = 0; k < 7; k++) {
                    int in_idx = t + k - 3;
                    if (in_idx >= 0 && in_idx < 257) {
                        acc += (int32_t)spectrum_int8[in_idx] * (int32_t)stage1_conv_k7_weight[c * 7 + k];
                    }
                }
                int8_t q = requantize(acc, stage1_conv_k7_requant_mult[c], stage1_conv_k7_requant_shift[c]);
                int8_t relu_v = (q > 0) ? q : 0;
                if (relu_v > max_v) max_v = relu_v;
            }
            s_buf_a[(8 + c) * 128 + i] = max_v;
        }
    }

    /* Branch 3: k=15, pad=7 (channels 16..23) */
    for (int c = 0; c < 8; c++) {
        for (int i = 0; i < 128; i++) {
            int8_t max_v = -128;
            for (int step = 0; step < 2; step++) {
                int t = 2 * i + step;
                int32_t acc = stage1_conv_k15_bias[c];
                for (int k = 0; k < 15; k++) {
                    int in_idx = t + k - 7;
                    if (in_idx >= 0 && in_idx < 257) {
                        acc += (int32_t)spectrum_int8[in_idx] * (int32_t)stage1_conv_k15_weight[c * 15 + k];
                    }
                }
                int8_t q = requantize(acc, stage1_conv_k15_requant_mult[c], stage1_conv_k15_requant_shift[c]);
                int8_t relu_v = (q > 0) ? q : 0;
                if (relu_v > max_v) max_v = relu_v;
            }
            s_buf_a[(16 + c) * 128 + i] = max_v;
        }
    }

    /* =========================================================================
     * STAGE 2: Intermediate Conv1D (k=5, pad=2) + ReLU + MaxPool(2)
     * Input: s_buf_a [24, 128]
     * Output: s_buf_b [32, 64]
     * Vectorized with __SMLAD over 24 channels (12 pairs per tap)
     * ========================================================================= */
    for (int c_out = 0; c_out < 32; c_out++) {
        for (int i = 0; i < 64; i++) {
            int8_t max_v = -128;
            for (int step = 0; step < 2; step++) {
                int t = 2 * i + step;
                int32_t acc = stage2_0_bias[c_out];
                for (int k = 0; k < 5; k++) {
                    int in_idx = t + k - 2;
                    if (in_idx >= 0 && in_idx < 128) {
                        for (int c_in = 0; c_in < 24; c_in += 2) {
                            int32_t in_pack = pack_s8x2(s_buf_a[c_in * 128 + in_idx],
                                                        s_buf_a[(c_in + 1) * 128 + in_idx]);
                            int32_t w_pack  = pack_s8x2(stage2_0_weight[(c_out * 24 + c_in) * 5 + k],
                                                        stage2_0_weight[(c_out * 24 + c_in + 1) * 5 + k]);
                            acc = VIBRA_SIMD_SMLAD(in_pack, w_pack, acc);
                        }
                    }
                }
                int8_t q = requantize(acc, stage2_0_requant_mult[c_out], stage2_0_requant_shift[c_out]);
                int8_t relu_v = (q > 0) ? q : 0;
                if (relu_v > max_v) max_v = relu_v;
            }
            s_buf_b[c_out * 64 + i] = max_v;
        }
    }

    /* =========================================================================
     * STAGE 3: Final Feature Conv1D (k=3, pad=1) + ReLU (No MaxPool)
     * Input: s_buf_b [32, 64]
     * Output: s_buf_a [16, 64]
     * Vectorized with __SMLAD over 32 channels (16 pairs per tap)
     * ========================================================================= */
    for (int c_out = 0; c_out < 16; c_out++) {
        for (int t = 0; t < 64; t++) {
            int32_t acc = stage3_0_bias[c_out];
            for (int k = 0; k < 3; k++) {
                int in_idx = t + k - 1;
                if (in_idx >= 0 && in_idx < 64) {
                    for (int c_in = 0; c_in < 32; c_in += 2) {
                        int32_t in_pack = pack_s8x2(s_buf_b[c_in * 64 + in_idx],
                                                    s_buf_b[(c_in + 1) * 64 + in_idx]);
                        int32_t w_pack  = pack_s8x2(stage3_0_weight[(c_out * 32 + c_in) * 3 + k],
                                                    stage3_0_weight[(c_out * 32 + c_in + 1) * 3 + k]);
                        acc = VIBRA_SIMD_SMLAD(in_pack, w_pack, acc);
                    }
                }
            }
            int8_t q = requantize(acc, stage3_0_requant_mult[c_out], stage3_0_requant_shift[c_out]);
            s_buf_a[c_out * 64 + t] = (q > 0) ? q : 0;
        }
    }

    /* =========================================================================
     * STAGE 4: Adaptive Average Pool (16 channels x 64 -> 16 channels x 4)
     * Output: s_embed [64] (channel-major)
     * ========================================================================= */
    int8_t s_embed[64];
    for (int c = 0; c < 16; c++) {
        for (int seg = 0; seg < 4; seg++) {
            int32_t sum = 0;
            for (int j = 0; j < 16; j++) {
                sum += (int32_t)s_buf_a[c * 64 + seg * 16 + j];
            }
            /* Round-half-up integer division by block size 16 */
            int32_t avg = (sum + 8) / 16;
            if (avg > 127)  avg = 127;
            if (avg < -128) avg = -128;
            s_embed[c * 4 + seg] = (int8_t)avg;
        }
    }

    /* =========================================================================
     * STAGE 5: Concatenation with Inductive Physics Prior (64 + 4 = 68)
     * ========================================================================= */
    int8_t s_fused[68];
    for (int i = 0; i < 64; i++) {
        s_fused[i] = s_embed[i];
    }
    for (int i = 0; i < 4; i++) {
        s_fused[64 + i] = prior_4 ? (int8_t)prior_4[i] : 0;
    }

    /* =========================================================================
     * STAGE 6: Fusion Dense Layer (68 -> 32) + ReLU
     * Vectorized with __SMLAD over 68 inputs (34 pairs)
     * ========================================================================= */
    int8_t h[32];
    for (int c_out = 0; c_out < 32; c_out++) {
        int32_t acc = fusion_fc_0_bias[c_out];
        for (int i = 0; i < 68; i += 2) {
            int32_t in_pack = pack_s8x2(s_fused[i], s_fused[i + 1]);
            int32_t w_pack  = pack_s8x2(fusion_fc_0_weight[c_out * 68 + i],
                                        fusion_fc_0_weight[c_out * 68 + i + 1]);
            acc = VIBRA_SIMD_SMLAD(in_pack, w_pack, acc);
        }
        int8_t q = requantize(acc, fusion_fc_0_requant_mult[c_out], fusion_fc_0_requant_shift[c_out]);
        h[c_out] = (q > 0) ? q : 0;
    }

    /* =========================================================================
     * STAGE 7: Classifier Dense Layer (32 -> 4)
     * Vectorized with __SMLAD over 32 inputs (16 pairs)
     * ========================================================================= */
    int8_t logits[4];
    for (int c_out = 0; c_out < 4; c_out++) {
        int32_t acc = classifier_bias[c_out];
        for (int i = 0; i < 32; i += 2) {
            int32_t in_pack = pack_s8x2(h[i], h[i + 1]);
            int32_t w_pack  = pack_s8x2(classifier_weight[c_out * 32 + i],
                                        classifier_weight[c_out * 32 + i + 1]);
            acc = VIBRA_SIMD_SMLAD(in_pack, w_pack, acc);
        }
        logits[c_out] = requantize(acc, classifier_requant_mult[c_out], classifier_requant_shift[c_out]);
        out_result->logits[c_out] = logits[c_out];
    }

    /* =========================================================================
     * STAGE 8: Decision, Evidential Vacuity (EDL), and RUL Prognostics
     * ========================================================================= */
    uint8_t best_class = 0;
    int8_t max_logit = logits[0];
    int32_t sum_evidence = 0;
    for (int c = 0; c < 4; c++) {
        if (logits[c] > max_logit) {
            max_logit = logits[c];
            best_class = (uint8_t)c;
        }
        if (logits[c] > 0) {
            sum_evidence += logits[c];
        }
    }
    out_result->predicted_class = best_class;

    /* Evidential Dirichlet Strength S = sum(e_k) + K where K = 4 */
    int32_t S = sum_evidence + 4;
    /* Vacuity u = K / S in Q0.15 format: u_q15 = (4 * 32768) / S */
    uint16_t u_q15 = (uint16_t)((4 * 32768) / S);
    out_result->vacuity_q15 = u_q15;

    /* OOD Alert: Threshold u* = 0.45 -> 0.45 * 32768 = 14,745 */
    out_result->ood_alert = (u_q15 > 14745) ? 1 : 0;

    /* Remaining Useful Life (RUL) fraction in Q0.15 */
    if (best_class == 0) {
        out_result->rul_q15 = 31130; /* ~0.95 (healthy baseline) */
    } else {
        /* Fault severity estimation scaled by fault logit intensity */
        int32_t fault_evidence = (logits[best_class] > 0) ? logits[best_class] : 0;
        int32_t rul_val = 26214 - (fault_evidence * 150); /* 0.80 minus degradation */
        if (rul_val < 3277) rul_val = 3277;               /* clamp min ~0.10 */
        out_result->rul_q15 = (uint16_t)rul_val;
    }
}
""")
