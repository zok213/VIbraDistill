#include "tachometer.h"
#include "hal.h"

static uint16_t          s_ring[TACH_AVG_N];
static uint8_t           s_head;
static uint8_t           s_count;
static uint32_t          s_sum;
static uint16_t          s_last_cap;
static uint8_t           s_have_last;
static volatile uint32_t s_last_ms;

static void tach_reset_locked(void)
{
    uint8_t i;
    for (i = 0U; i < TACH_AVG_N; i++) { s_ring[i] = 0U; }
    s_head = 0U; s_count = 0U; s_sum = 0UL; s_have_last = 0U;
}

void Tach_Init(void)
{
    tach_reset_locked();
    s_last_cap = 0U;
    s_last_ms  = hal_millis();
    hal_tach_init();
}

/* ISR: O(1), no division. 16-bit subtraction handles counter wrap. */
void Tach_OnCapture(uint16_t capture)
{
    uint16_t period;

    s_last_ms = hal_millis();
    if (s_have_last == 0U) {
        s_last_cap  = capture;
        s_have_last = 1U;
        return;
    }
    period     = (uint16_t)(capture - s_last_cap);
    s_last_cap = capture;
    if (period < (uint16_t)TACH_MIN_PERIOD_US) {
        return;                                   /* glitch */
    }
    s_sum -= (uint32_t)s_ring[s_head];
    s_ring[s_head] = period;
    s_sum += (uint32_t)period;
    s_head = (uint8_t)((s_head + 1U) & (TACH_AVG_N - 1U));
    if (s_count < TACH_AVG_N) { s_count++; }
}

uint8_t Tach_Get(uint16_t *rpm, float *fr_hz)
{
    uint32_t primask = hal_irq_save();
    uint32_t sum;
    uint8_t  count;
    uint32_t r;

    if ((uint32_t)(hal_millis() - s_last_ms) > TACH_STALE_MS) {
        tach_reset_locked();                      /* motor stopped / wire lost */
    }
    sum   = s_sum;
    count = s_count;
    hal_irq_restore(primask);

    if ((count < TACH_AVG_N) || (sum == 0UL)) {
        return 0U;
    }
    /* rpm = 60 / (T_avg * PPR), T_avg = sum / 8 (us)  ->  16e6 / sum */
    r = (((60UL * TACH_TIMER_HZ) / TACH_PPR) * TACH_AVG_N) / sum;
    if ((r < TACH_MIN_RPM) || (r > TACH_MAX_RPM)) {
        return 0U;
    }
    *rpm   = (uint16_t)r;
    *fr_hz = (float)r / 60.0f;
    return 1U;
}
