#ifndef OLED_SSD1306_H
#define OLED_SSD1306_H

#include <stdint.h>

#define OLED_I2C_ADDR7   0x3CU
#define OLED_COLS        128U
#define OLED_PAGES       8U
#define OLED_TEXT_PAGES  3U      /* pages 0..2 = text lines            */
#define OLED_CHART_ROWS  40U     /* pages 3..7 = 40-px spectrum chart  */

typedef enum {
    OLED_ST_WAIT = 0,
    OLED_ST_NORMAL,
    OLED_ST_FAULT_BPFO,
    OLED_ST_FAULT_BPFI,
    OLED_ST_FAULT_BALL,
    OLED_ST_FAULT_OOD,
    OLED_ST_NO_SPEED
} oled_status_t;

typedef struct {
    oled_status_t status;
    uint16_t      rpm;
    uint16_t      peak_dhz;    /* peak frequency in 0.1 Hz units (3125 = 312.5 Hz) */
    uint8_t       rul_pct;     /* 0..100 */
    uint8_t       vac_x100;    /* vacuity * 100, 0..100 */
} oled_view_t;

void Oled_Init(void);
/** Latch new values. spectrum = 257 int8 bins (not copied; must stay valid). */
void Oled_SetView(const oled_view_t *view, const int8_t *spectrum_257);
/** Non-blocking-ish: sends ONE 128-byte page per call (~3 ms at 400 kHz). */
void Oled_Task(void);
/** Render one page into out[128] (exposed for host testing). */
void Oled_RenderPage(uint8_t page, uint8_t *out_128);

#endif
