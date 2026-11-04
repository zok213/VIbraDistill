#include "oled_ssd1306.h"
#include "hal.h"
#include <string.h>

#define OLED_RETRY_MS  500U

/* Classic 5x7 font, ASCII 0x20..0x5A, column-major, bit0 = top row. */
#define FONT_FIRST 0x20U
#define FONT_LAST  0x5AU
static const uint8_t k_font[(FONT_LAST - FONT_FIRST) + 1U][5] = {
    {0x00,0x00,0x00,0x00,0x00},{0x00,0x00,0x5F,0x00,0x00},{0x00,0x07,0x00,0x07,0x00},{0x14,0x7F,0x14,0x7F,0x14},
    {0x24,0x2A,0x7F,0x2A,0x12},{0x23,0x13,0x08,0x64,0x62},{0x36,0x49,0x56,0x20,0x50},{0x00,0x08,0x07,0x03,0x00},
    {0x00,0x1C,0x22,0x41,0x00},{0x00,0x41,0x22,0x1C,0x00},{0x2A,0x1C,0x7F,0x1C,0x2A},{0x08,0x08,0x3E,0x08,0x08},
    {0x00,0x80,0x70,0x30,0x00},{0x08,0x08,0x08,0x08,0x08},{0x00,0x00,0x60,0x60,0x00},{0x20,0x10,0x08,0x04,0x02},
    {0x3E,0x51,0x49,0x45,0x3E},{0x00,0x42,0x7F,0x40,0x00},{0x72,0x49,0x49,0x49,0x46},{0x21,0x41,0x49,0x4D,0x33},
    {0x18,0x14,0x12,0x7F,0x10},{0x27,0x45,0x45,0x45,0x39},{0x3C,0x4A,0x49,0x49,0x31},{0x41,0x21,0x11,0x09,0x07},
    {0x36,0x49,0x49,0x49,0x36},{0x46,0x49,0x49,0x29,0x1E},{0x00,0x00,0x14,0x00,0x00},{0x00,0x40,0x34,0x00,0x00},
    {0x00,0x08,0x14,0x22,0x41},{0x14,0x14,0x14,0x14,0x14},{0x00,0x41,0x22,0x14,0x08},{0x02,0x01,0x59,0x09,0x06},
    {0x3E,0x41,0x5D,0x59,0x4E},{0x7C,0x12,0x11,0x12,0x7C},{0x7F,0x49,0x49,0x49,0x36},{0x3E,0x41,0x41,0x41,0x22},
    {0x7F,0x41,0x41,0x41,0x3E},{0x7F,0x49,0x49,0x49,0x41},{0x7F,0x09,0x09,0x09,0x01},{0x3E,0x41,0x41,0x51,0x73},
    {0x7F,0x08,0x08,0x08,0x7F},{0x00,0x41,0x7F,0x41,0x00},{0x20,0x40,0x41,0x3F,0x01},{0x7F,0x08,0x14,0x22,0x41},
    {0x7F,0x40,0x40,0x40,0x40},{0x7F,0x02,0x1C,0x02,0x7F},{0x7F,0x04,0x08,0x10,0x7F},{0x3E,0x41,0x41,0x41,0x3E},
    {0x7F,0x09,0x09,0x09,0x06},{0x3E,0x41,0x51,0x21,0x5E},{0x7F,0x09,0x19,0x29,0x46},{0x26,0x49,0x49,0x49,0x32},
    {0x03,0x01,0x7F,0x01,0x03},{0x3F,0x40,0x40,0x40,0x3F},{0x1F,0x20,0x40,0x20,0x1F},{0x3F,0x40,0x38,0x40,0x3F},
    {0x63,0x14,0x08,0x14,0x63},{0x03,0x04,0x78,0x04,0x03},{0x61,0x59,0x49,0x4D,0x43}
};

static const uint8_t k_init_cmds[] = {
    0xAE, 0xD5,0x80, 0xA8,0x3F, 0xD3,0x00, 0x40, 0x8D,0x14, 0x20,0x02,
    0xA1, 0xC8, 0xDA,0x12, 0x81,0xCF, 0xD9,0xF1, 0xDB,0x40, 0xA4, 0xA6, 0xAF
};

static const char *const k_status_txt[] = {
    "STATUS: WAITING", "STATUS: NORMAL", "FAULT: BPFO", "FAULT: BPFI",
    "FAULT: BALL", "FAULT: OOD", "STATUS: NO SPEED"
};

static uint8_t        s_page_buf[OLED_COLS];       /* the ONLY display buffer: 128 B */
static oled_view_t    s_view;
static const int8_t  *s_spectrum;
static uint8_t        s_page;
static uint8_t        s_ready;
static uint32_t       s_retry_ms;
static uint8_t        s_tried;

/* ---- tiny formatter (no printf, no float) --------------------------------- */
static char *put_str(char *p, const char *s)
{
    while (*s != '\0') { *p = *s; p++; s++; }
    return p;
}

static char *put_uint(char *p, uint32_t v, uint8_t width, char pad)
{
    char    tmp[10];
    uint8_t n = 0U;
    do { tmp[n] = (char)('0' + (char)(v % 10UL)); n++; v /= 10UL; } while ((v != 0UL) && (n < 10U));
    while (width > n) { *p = pad; p++; width--; }
    while (n > 0U)    { n--; *p = tmp[n]; p++; }
    return p;
}

static void build_line(uint8_t line, char *buf /* >= 24 */)
{
    char *p = buf;
    switch (line) {
    case 0U:
        p = put_str(p, k_status_txt[(uint8_t)s_view.status]);
        break;
    case 1U:
        p = put_str(p, "RPM:");
        p = put_uint(p, s_view.rpm, 4U, ' ');
        p = put_str(p, " PK:");
        p = put_uint(p, (uint32_t)(s_view.peak_dhz / 10U), 4U, ' ');
        *p = '.'; p++;
        p = put_uint(p, (uint32_t)(s_view.peak_dhz % 10U), 1U, '0');
        p = put_str(p, "HZ");
        break;
    default:
        p = put_str(p, "RUL:");
        p = put_uint(p, s_view.rul_pct, 3U, ' ');
        p = put_str(p, "% VAC:");
        p = put_uint(p, (uint32_t)(s_view.vac_x100 / 100U), 1U, '0');
        *p = '.'; p++;
        p = put_uint(p, (uint32_t)(s_view.vac_x100 % 100U), 2U, '0');
        break;
    }
    *p = '\0';
}

static void render_text(uint8_t *out, const char *s)
{
    uint16_t x = 0U;
    uint8_t  k;
    (void)memset(out, 0, OLED_COLS);
    while ((*s != '\0') && ((x + 6U) <= OLED_COLS)) {
        char c = *s;
        const uint8_t *g;
        if ((c >= 'a') && (c <= 'z')) { c = (char)(c - 32); }
        if (((uint8_t)c < FONT_FIRST) || ((uint8_t)c > FONT_LAST)) { c = '?'; }
        g = k_font[(uint8_t)c - FONT_FIRST];
        for (k = 0U; k < 5U; k++) { out[x + k] = g[k]; }
        x += 6U;
        s++;
    }
}

/* 257 bins -> 128 columns; bins 2..256 only (255 bins), never the DC bins. */
static uint8_t column_height(const int8_t *spec, uint8_t col)
{
    uint16_t start = (uint16_t)(2U + (((uint16_t)col * 255U) >> 7));
    uint16_t end   = (uint16_t)(2U + ((((uint16_t)col + 1U) * 255U) >> 7));
    int16_t  maxv  = 0;
    uint16_t b;
    uint16_t h;

    if (end <= start) { end = (uint16_t)(start + 1U); }
    if (end > 257U)   { end = 257U; }
    for (b = start; b < end; b++) {
        if ((int16_t)spec[b] > maxv) { maxv = (int16_t)spec[b]; }
    }
    h = (uint16_t)(((uint16_t)maxv * OLED_CHART_ROWS) >> 7);
    if ((h == 0U) && (maxv > 0)) { h = 1U; }
    return (uint8_t)h;
}

static void render_chart(uint8_t *out, uint8_t chart_page)
{
    uint8_t  col;
    uint8_t  bit;
    uint16_t top = (uint16_t)chart_page * 8U;

    (void)memset(out, 0, OLED_COLS);
    if (s_spectrum == 0) { return; }
    for (col = 0U; col < (uint8_t)OLED_COLS; col++) {
        uint16_t h = column_height(s_spectrum, col);
        uint8_t  v = 0U;
        for (bit = 0U; bit < 8U; bit++) {
            if ((top + bit) >= (OLED_CHART_ROWS - h)) { v |= (uint8_t)(1U << bit); }
        }
        out[col] = v;
    }
}

void Oled_RenderPage(uint8_t page, uint8_t *out_128)
{
    if (page < OLED_TEXT_PAGES) {
        char line[24];
        build_line(page, line);
        render_text(out_128, line);
    } else {
        render_chart(out_128, (uint8_t)(page - OLED_TEXT_PAGES));
    }
}

static int oled_send_init(void)
{
    if (hal_i2c_init() != 0) { return -1; }
    return hal_i2c_write(OLED_I2C_ADDR7, 0x00U, k_init_cmds, (uint16_t)sizeof(k_init_cmds));
}

void Oled_Init(void)
{
    s_view.status = OLED_ST_WAIT; s_view.rpm = 0U; s_view.peak_dhz = 0U;
    s_view.rul_pct = 0U; s_view.vac_x100 = 0U;
    s_spectrum = 0;
    s_page = 0U;
    s_tried = 1U;
    s_retry_ms = hal_millis();
    s_ready = (oled_send_init() == 0) ? 1U : 0U;
}

void Oled_SetView(const oled_view_t *view, const int8_t *spectrum_257)
{
    s_view     = *view;
    s_spectrum = spectrum_257;
}

void Oled_Task(void)
{
    uint8_t cmd[3];

    if (s_ready == 0U) {
        if ((s_tried != 0U) && ((uint32_t)(hal_millis() - s_retry_ms) < OLED_RETRY_MS)) { return; }
        s_tried = 1U;
        s_retry_ms = hal_millis();
        s_ready = (oled_send_init() == 0) ? 1U : 0U;
        return;
    }

    Oled_RenderPage(s_page, s_page_buf);
    cmd[0] = (uint8_t)(0xB0U | s_page);   /* page address   */
    cmd[1] = 0x00U;                       /* column low  = 0 */
    cmd[2] = 0x10U;                       /* column high = 0 */
    if ((hal_i2c_write(OLED_I2C_ADDR7, 0x00U, cmd, 3U) != 0) ||
        (hal_i2c_write(OLED_I2C_ADDR7, 0x40U, s_page_buf, (uint16_t)OLED_COLS) != 0)) {
        s_ready = 0U;                     /* bus fault: re-init after back-off */
        s_retry_ms = hal_millis();
        return;
    }
    s_page = (uint8_t)((s_page + 1U) & (OLED_PAGES - 1U));
}
