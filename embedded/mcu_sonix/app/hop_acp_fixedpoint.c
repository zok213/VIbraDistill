/*
 * ============================================================================
 * Project:      VibraDistill-Edge (Team Porygon - DSAC 2026)
 * Module:       HopACP - Higher-Order Adaptive Conformal Prediction (Q16.16)
 * Implementation file
 * ============================================================================
 */

#include "hop_acp.h"

void hop_acp_init(hop_acp_tracker_t *tracker, int32_t init_margin_q16) {
    if (!tracker) return;
    tracker->lambda_q16     = init_margin_q16;
    tracker->lambda_min_q16 = HOP_ACP_DEFAULT_QMIN_Q16;
    tracker->lambda_max_q16 = HOP_ACP_DEFAULT_QMAX_Q16;
    tracker->prev_err       = 0;
    tracker->total_samples  = 0;
    tracker->total_errors   = 0;
}

void hop_acp_predict(const hop_acp_tracker_t *tracker,
                     int32_t point_pred_q16,
                     int32_t *out_lower,
                     int32_t *out_upper) {
    if (!tracker) return;
    
    int32_t margin = tracker->lambda_q16;
    int32_t low    = point_pred_q16 - margin;
    int32_t high   = point_pred_q16 + margin;
    
    /* Physical clamp: RUL or severity score cannot be negative */
    if (low < 0) {
        low = 0;
    }
    
    if (out_lower) *out_lower = low;
    if (out_upper) *out_upper = high;
}

void hop_acp_update_step(hop_acp_tracker_t *tracker, uint8_t miscoverage_event) {
    if (!tracker) return;
    
    tracker->total_samples++;
    
    /* 1. Base integral term gamma * (alpha - err_t) */
    int32_t delta_lambda = 0;
    if (miscoverage_event) {
        tracker->total_errors++;
        delta_lambda += HOP_ACP_DELTA_ERR_Q16; /* +2949 */
    } else {
        delta_lambda += HOP_ACP_DELTA_OK_Q16;  /* -328 */
    }
    
    /* 2. Higher-Order Derivative / Momentum term: beta * (err_t - err_{t-1}) */
    int32_t d_err = (int32_t)miscoverage_event - (int32_t)tracker->prev_err;
    if (d_err > 0) {
        delta_lambda += HOP_ACP_BETA_MOMENTUM_Q16;  /* +3277 instant boost on shock */
    } else if (d_err < 0) {
        delta_lambda -= HOP_ACP_BETA_MOMENTUM_Q16;  /* -3277 rapid relaxation */
    }
    
    tracker->prev_err = miscoverage_event;
    
    /* 3. Apply update with saturation bounding */
    int32_t new_lambda = tracker->lambda_q16 + delta_lambda;
    if (new_lambda > tracker->lambda_max_q16) {
        new_lambda = tracker->lambda_max_q16;
    } else if (new_lambda < tracker->lambda_min_q16) {
        new_lambda = tracker->lambda_min_q16;
    }
    
    tracker->lambda_q16 = new_lambda;
}

void hop_acp_update(hop_acp_tracker_t *tracker,
                    int32_t point_pred_q16,
                    int32_t true_feedback_q16) {
    if (!tracker) return;
    
    int32_t margin = tracker->lambda_q16;
    int32_t low    = point_pred_q16 - margin;
    int32_t high   = point_pred_q16 + margin;
    
    if (low < 0) low = 0;
    
    uint8_t miscovered = (true_feedback_q16 < low || true_feedback_q16 > high) ? 1 : 0;
    hop_acp_update_step(tracker, miscovered);
}

int32_t hop_acp_get_empirical_coverage_q16(const hop_acp_tracker_t *tracker) {
    if (!tracker || tracker->total_samples == 0) return 0;
    
    /* empirical_coverage = (total_samples - total_errors) / total_samples */
    int64_t covered = (int64_t)(tracker->total_samples - tracker->total_errors);
    int32_t coverage_q16 = (int32_t)((covered * HOP_ACP_ONE_Q16) / tracker->total_samples);
    return coverage_q16;
}
