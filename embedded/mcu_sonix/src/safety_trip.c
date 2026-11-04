#include "safety_trip.h"
#include "hal.h"

static volatile uint8_t  s_latched;
static safety_reason_t   s_reason;
static uint8_t           s_consec;

void Safety_Trip_Init(void)
{
    s_latched = 0U;
    s_reason  = SAFETY_REASON_NONE;
    s_consec  = 0U;
    hal_relay_init();                 /* drives level 0 (relay closed / run) */
}

void Safety_Trip_Actuate(safety_reason_t reason)
{
    hal_relay_set(1U);                /* first statement: minimum latency */
    if (s_latched == 0U) {
        s_reason  = reason;
        s_latched = 1U;
    }
}

uint8_t Safety_Trip_Evaluate(uint8_t cls, uint8_t ood)
{
    safety_reason_t reason = SAFETY_REASON_NONE;

    if (cls == 1U)      { reason = SAFETY_REASON_BPFO; }
    else if (cls == 2U) { reason = SAFETY_REASON_BPFI; }
    else if (cls == 3U) { reason = SAFETY_REASON_BALL; }
    else if ((cls != 0U) || (ood != 0U)) { reason = SAFETY_REASON_OOD; }
    else { /* cls == 0 and in-distribution: healthy */ }

    if (reason == SAFETY_REASON_NONE) {
        s_consec = 0U;
    } else {
        if (s_consec < 255U) { s_consec++; }
        if (s_consec >= SAFETY_TRIP_CONSEC_FRAMES) {
            Safety_Trip_Actuate(reason);
        }
    }
    return s_latched;
}

void Safety_Trip_Refresh(void)
{
    if (s_latched != 0U) { hal_relay_set(1U); }
}

uint8_t Safety_Trip_IsLatched(void)        { return s_latched; }
safety_reason_t Safety_Trip_GetReason(void) { return s_reason; }
