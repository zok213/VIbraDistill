#ifndef TACHOMETER_H
#define TACHOMETER_H

#include <stdint.h>

#define TACH_PPR            30UL
#define TACH_TIMER_HZ       1000000UL   /* CT16B0 tick: 1 us                */
#define TACH_AVG_N          8U          /* moving-average window (power of 2) */
#define TACH_MIN_PERIOD_US  200U        /* reject glitches (> 5 kHz)        */
#define TACH_STALE_MS       100U        /* no edge for this long -> invalid */
#define TACH_MIN_RPM        600U
#define TACH_MAX_RPM        3500U

void    Tach_Init(void);
void    Tach_OnCapture(uint16_t capture);   /* call from CT16B0 capture ISR */
/** Returns 1 and fills outputs when 8 fresh periods are averaged and the
 *  speed is inside [TACH_MIN_RPM, TACH_MAX_RPM]; otherwise 0. */
uint8_t Tach_Get(uint16_t *rpm, float *fr_hz);

#endif
