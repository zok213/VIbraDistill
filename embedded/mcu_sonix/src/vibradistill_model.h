/*
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
