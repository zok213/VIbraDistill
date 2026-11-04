#ifndef SAFETY_TRIP_H
#define SAFETY_TRIP_H

#include <stdint.h>

/* Consecutive faulty frames required before tripping. 1 = trip on first
 * detection (literal spec). Raise only after a safety-case decision. */
#ifndef SAFETY_TRIP_CONSEC_FRAMES
#define SAFETY_TRIP_CONSEC_FRAMES 1U
#endif

typedef enum {
    SAFETY_REASON_NONE = 0,
    SAFETY_REASON_BPFO,
    SAFETY_REASON_BPFI,
    SAFETY_REASON_BALL,
    SAFETY_REASON_OOD
} safety_reason_t;

void            Safety_Trip_Init(void);
/** Drives P1.0 HIGH first, then latches. Safe to call repeatedly. */
void            Safety_Trip_Actuate(safety_reason_t reason);
/** cls: 0 normal, 1 outer race, 2 inner race, 3 ball. Anything else, or
 *  ood != 0, is treated as unsafe. Returns 1 if the relay is now tripped. */
uint8_t         Safety_Trip_Evaluate(uint8_t cls, uint8_t ood);
void            Safety_Trip_Refresh(void);   /* re-assert pin while latched */
uint8_t         Safety_Trip_IsLatched(void);
safety_reason_t Safety_Trip_GetReason(void);

#endif
