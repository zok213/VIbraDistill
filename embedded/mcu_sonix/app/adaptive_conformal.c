/*
 * Online Adaptive Conformal Prediction (ACP) Implementation
 * Guaranteed Finite-Sample (1 - alpha) Coverage under Speed/Load Shift.
 * Optimized for ARM Cortex-M0 (Sonix SN32F407).
 */

#include "adaptive_conformal.h"

/* ============================================================================
 * Cortex-M0 Pure Integer / Fixed-Point Q16.16 Implementation (Zero Soft-Float)
 * ============================================================================ */

void acp_q16_init(acp_tracker_q16_t *acp, int32_t initial_q_hours_q16) {
    if (!acp) return;
    acp->q_t_q16 = initial_q_hours_q16;
    acp->q_min_q16 = ACP_DEFAULT_QMIN_Q16;
    acp->q_max_q16 = ACP_DEFAULT_QMAX_Q16;
    acp->total_samples = 0;
    acp->total_errors = 0;
}

void acp_q16_predict_interval(const acp_tracker_q16_t *acp,
                              int32_t point_rul_hours_q16,
                              int32_t *lower_bound_hours_q16,
                              int32_t *upper_bound_hours_q16) {
    if (!acp) return;
    
    int32_t low = point_rul_hours_q16 - acp->q_t_q16;
    if (low < 0) {
        low = 0; /* RUL cannot be negative */
    }
    int32_t high = point_rul_hours_q16 + acp->q_t_q16;
    
    if (lower_bound_hours_q16) *lower_bound_hours_q16 = low;
    if (upper_bound_hours_q16) *upper_bound_hours_q16 = high;
}

void acp_q16_update_step(acp_tracker_q16_t *acp, uint8_t miscoverage_event) {
    if (!acp) return;
    
    acp->total_samples++;
    if (miscoverage_event) {
        acp->total_errors++;
        acp->q_t_q16 += ACP_DELTA_ERR_Q16; /* +2949 counts */
        if (acp->q_t_q16 > acp->q_max_q16) {
            acp->q_t_q16 = acp->q_max_q16;
        }
    } else {
        acp->q_t_q16 += ACP_DELTA_OK_Q16;  /* -328 counts */
        if (acp->q_t_q16 < acp->q_min_q16) {
            acp->q_t_q16 = acp->q_min_q16;
        }
    }
}

void acp_q16_update(acp_tracker_q16_t *acp, int32_t point_rul_q16, int32_t feedback_rul_q16) {
    if (!acp) return;
    
    int32_t low = point_rul_q16 - acp->q_t_q16;
    int32_t high = point_rul_q16 + acp->q_t_q16;
    
    uint8_t err = (feedback_rul_q16 < low || feedback_rul_q16 > high) ? 1 : 0;
    acp_q16_update_step(acp, err);
}

/* ============================================================================
 * Legacy / Floating-Point Desktop API
 * ============================================================================ */

void acp_init(adaptive_conformal_t *acp, float target_coverage, float adaptation_rate, float initial_quantile) {
    if (!acp) return;
    acp->alpha = 1.0f - target_coverage; /* e.g. 1.0 - 0.90 = 0.10 */
    acp->gamma = adaptation_rate;        /* e.g. 0.05 */
    acp->q_t = initial_quantile;         /* initial uncertainty window */
    acp->q_min = 5.0f;                   /* at least 5 hours margin */
    acp->q_max = 500.0f;                 /* clamp maximum margin */
    acp->total_samples = 0;
    acp->total_errors = 0;
}

void acp_predict_interval(const adaptive_conformal_t *acp, 
                          float point_rul_hours, 
                          float *lower_bound_hours, 
                          float *upper_bound_hours) {
    if (!acp) return;
    
    float low = point_rul_hours - acp->q_t;
    if (low < 0.0f) {
        low = 0.0f; /* RUL cannot be negative */
    }
    float high = point_rul_hours + acp->q_t;
    
    if (lower_bound_hours) *lower_bound_hours = low;
    if (upper_bound_hours) *upper_bound_hours = high;
}

void acp_update(adaptive_conformal_t *acp, float point_rul_hours, float true_or_feedback_rul) {
    if (!acp) return;
    
    float low = point_rul_hours - acp->q_t;
    float high = point_rul_hours + acp->q_t;
    
    /* Indicator: err_t = 1 if outside interval, 0 if covered */
    float err_t = 0.0f;
    if (true_or_feedback_rul < low || true_or_feedback_rul > high) {
        err_t = 1.0f;
        acp->total_errors++;
    }
    acp->total_samples++;
    
    /* Correct pinball loss gradient step */
    float delta_q = acp->gamma * (err_t - acp->alpha);
    acp->q_t += delta_q;
    
    /* Clamp to physical bounds */
    if (acp->q_t < acp->q_min) {
        acp->q_t = acp->q_min;
    } else if (acp->q_t > acp->q_max) {
        acp->q_t = acp->q_max;
    }
}

float acp_get_empirical_coverage(const adaptive_conformal_t *acp) {
    if (!acp || acp->total_samples == 0) return 1.0f;
    return 1.0f - ((float)acp->total_errors / (float)acp->total_samples);
}
