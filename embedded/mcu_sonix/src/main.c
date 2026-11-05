/*
 * ============================================================================
 * Project:      VibraDistill-Edge Embedded System Firmware
 * Target:       Sonix SN32F407 (ARM Cortex-M0 @ 48 MHz IHRC, 32 KB Flash, 8 KB SRAM)
 * Architecture: HARDWARE SPI0 SLAVE + DMA PING-PONG + REAL-TIME FFT SPECTRUM
 * Protocol:     Gowin Tang Primer 20K -> SPI Master (524-byte frame, CRC16-CCITT)
 * ============================================================================
 * KHUNG TIN TRUYỀN TỪ FPGA (524 BYTES CHUẨN ĐÃ ĐỒNG BỘ 100% VỚI SPI_MASTER_PACKET):
 *   [0..1]    : Sync Header (FPGA phát 0x55, 0xAA -> MCU swap thành 0xAA, 0x55)
 *   [2..3]    : Frame Counter (uint16_t Little-Endian -> MCU swap thành Big-Endian)
 *   [4..517]  : 257 FFT Bins x 2 Bytes (Bin 0..256, 514 Bytes, sau swap là Big-Endian)
 *   [518]     : NPU Dirichlet Max Evidence / Vacuity u (Sau swap cặp 518-519)
 *   [519]     : Bit 7: OOD Alert, Bits 1..0: NPU Class (0:Norm, 1:BPFI, 2:BPFO, 3:BSF)
 *   [520..521]: Hardware Status Flags (16-bit Status Flags)
 *   [522..523]: CRC-16-CCITT (Poly 0x1021 across bytes 0..521)
 * ============================================================================
 */

#include "SN32F400.h"
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

/* ============================================================================
 * 1. ĐỊNH NGHĨA PHẦN CỨNG & CẤU HÌNH NGOẠI VI
 * ============================================================================ */

/* Màn hình OLED SSD1306 (I2C Bit-Bang trên P0.10 SCL, P0.11 SDA) */
#define OLED_ADDR               0x78U
#define SCL_HIGH()              (SN_GPIO0->BSET = (1U << 10))
#define SCL_LOW()               (SN_GPIO0->BCLR = (1U << 10))
#define SDA_HIGH()              (SN_GPIO0->BSET = (1U << 11))
#define SDA_LOW()               (SN_GPIO0->BCLR = (1U << 11))
#define OLED_ROTATE_180_DEFAULT 1

/* Đèn LED D1 (P3.8 Active-LOW) */
#define LED_PIN_BIT             8U
#define LED_ON()                (SN_GPIO3->BCLR = (1U << LED_PIN_BIT))
#define LED_OFF()               (SN_GPIO3->BSET = (1U << LED_PIN_BIT))
#define LED_TOGGLE()            (SN_GPIO3->DATA ^= (1U << LED_PIN_BIT))

/* Điều khiển Rơ-le động cơ P2.2 (Active-LOW: 0 = RUN, 1 = STOP) */
#define RELAY_PIN_BIT           2U
#define RELAY_ON()              (SN_GPIO2->BCLR = (1U << RELAY_PIN_BIT))
#define RELAY_OFF()             (SN_GPIO2->BSET = (1U << RELAY_PIN_BIT))

/* Đọc xung Encoder trên Header J7 (P2.8 chính, P2.9 & P2.3 dự phòng) */
#define ENCODER_PIN_MASK        ((1U << 8) | (1U << 9) | (1U << 3))
#define ENCODER_PPR             30U

/* LED 7 Đoạn 4 Số SMG1 (P0.0..P0.7 Segment, P1.9..P1.12 COM) */
#define SEG_MASK                (0x00FFU)
#define COM_MASK                (0x000FU << 9)

/* Ma trận phím 4x4 (Row P1.4..P1.7 Output, Col P2.4..P2.7 Input Pull-up) */
#define ROW_MASK                (0x000FU << 4)
#define COL_MASK                (0x000FU << 4)

/* Giao tiếp SPI0 Slave + DMA (SCK P1.0, SEL P1.8, MOSI P1.2) */
#define SPI_FRAME_LEN           524U
#define NUM_FFT_BINS            257U    /* Đủ 257 Bins (Bin 0..256) từ Byte 4..517 */
#define FFT_SKIP_BINS           4U      /* Bỏ qua 4 bin đầu (DC & hài trục 1X < 93.8Hz) khớp chuẩn Python */
#define SYNC_BYTE_0             0x55U   /* Sync Byte 0 từ FPGA (Little-Endian) */
#define SYNC_BYTE_1             0xAAU   /* Sync Byte 1 từ FPGA (Little-Endian) */
#define CRC16_POLY              0x1021U
#define VIB_TRIP_LIMIT          38000U
#define FAULT_PERSISTENCE_LIMIT 5U      /* 5 khung liên tiếp (~213ms) xác nhận lỗi NPU trước khi Trip */
#define BOOT_GRACE_MS           5000U   /* Thời gian ân hạn 5s khi khởi động chờ link SPI */
#define LINK_TIMEOUT_MS         500U    /* Mất tín hiệu SPI > 500ms khi động cơ chạy sẽ Trip an toàn */

/* --- Định nghĩa Bitfield ngoại vi SPI & DMA --- */
#define FSPI_DL_8               7U
#define FSPI_FRESET_ALL         3U
#define FSPI_RX_DMA_EN          (1UL << 30)

#define FDMA_CLK_EN             (1UL << 2)
#define FDMA_CSR_CH_EN          (1UL << 0)
#define FDMA_CSR_DST_INC        (0UL << 3)
#define FDMA_CSR_SRC_FIX        (2UL << 5)
#define FDMA_CSR_MODE_PERIPH    (1UL << 7)
#define FDMA_CSR_DST_W8         (0UL << 8)
#define FDMA_CSR_SRC_W8         (0UL << 11)
#define FDMA_CSR_ABT            (1UL << 15)
#define FDMA_CSR_BURST_1        (0UL << 16)
#define FDMA_CSR_PRI_LV3        (3UL << 22)
#define FDMA_CSR_RX_CFG         (FDMA_CSR_DST_INC | FDMA_CSR_SRC_FIX | FDMA_CSR_MODE_PERIPH | \
                                 FDMA_CSR_DST_W8 | FDMA_CSR_SRC_W8 | FDMA_CSR_BURST_1 | FDMA_CSR_PRI_LV3)
#define FDMA_CFG_ERR_ABT_MASK   ((1UL << 1) | (1UL << 2))
#define FDMA_CFG_SRC_PERIPH     (1UL << 7)
#define FDMA_CFG_SRC_SPI0_RX    (0x03UL << 16)
#define FDMA_INT_TC_CH0         (1UL << 0)
#define FDMA_INT_ABT_CH0        (1UL << 16)

typedef enum {
    DTC_SYSTEM_NORMAL           = 0x0000,
    DTC_FPGA_HEARTBEAT_TIMEOUT  = 0xE101,
    DTC_SPI_CHECKSUM_FAULT      = 0xE102,
    DTC_CRITICAL_BEARING_TRIP   = 0xF301
} hardware_dtc_t;

typedef enum {
    BEARING_NORMAL              = 0,
    BEARING_INNER_RACE          = 1,
    BEARING_OUTER_RACE          = 2,
    BEARING_BALL_DEFECT         = 3
} bearing_fault_class_t;

typedef enum {
    OLED_MODE_MOTOR_PULSES      = 0,
    OLED_MODE_FPGA_DIAGNOSTICS  = 1,
    OLED_MODE_FFT_SPECTRUM      = 2,
    OLED_MODE_KEYPAD_SAFETY     = 3,
    OLED_MODE_MAX               = 4
} OLED_Mode_t;

/* Trạng thái Động cơ & Encoder */
static volatile uint8_t  g_relay_state    = 0;
static volatile uint32_t g_pulse_count    = 0;
static volatile uint32_t g_pulses_window  = 0;
static volatile uint32_t g_last_pulse_us  = 0;
static volatile uint32_t g_rev_count      = 0;
static volatile uint32_t g_rev_decimal    = 0;
static volatile uint16_t g_measured_rpm   = 0;

/* Trạng thái Telemetry & AI từ FPGA */
static volatile uint32_t g_fpga_packet_count   = 0;
static volatile uint32_t g_fpga_crc_err_count  = 0;
static volatile uint32_t g_fpga_sync_err_count = 0;
static volatile uint8_t  g_dbg_rx[8];                 /* 8 byte đầu của khung lỗi gần nhất */
static volatile uint32_t g_dbg_isr_err = 0;           /* đủ 524 byte nhưng sai header */
static volatile uint32_t g_dbg_wd_err  = 0;           /* kẹt giữa chừng (thiếu byte) */
static volatile uint16_t g_dbg_crc_calc = 0;          /* CRC MCU tính được ở khung lỗi gần nhất */
static volatile uint16_t g_dbg_crc_recv = 0;          /* CRC FPGA gửi ở khung lỗi gần nhất */
static volatile uint32_t g_last_good_frame_ms = 0;    /* thời điểm nhận khung CRC đúng gần nhất */
static volatile uint32_t s_boot_ref_ms         = 0;    /* Mốc thời gian khởi động / reset watchdog */
static volatile bool     s_link_armed          = false;/* Cờ xác nhận đã bắt được link SPI ít nhất 1 lần */
static volatile uint8_t  s_consecutive_faults  = 0;    /* Bộ đếm lọc nhiễu khung lỗi liên tiếp */
static volatile uint16_t g_fpga_frame_count    = 0;
static volatile uint16_t g_fpga_shaft_speed    = 0;
static volatile int16_t  g_fpga_temperature    = 285;
static volatile uint8_t  g_npu_class           = 0;
static volatile uint16_t g_epistemic_vacuity   = 0;
static volatile bool     g_is_ood_alert        = false;
static volatile uint16_t g_fpga_hw_status      = 0;
static volatile uint32_t g_rul_hours          = 1200U;/* Tuổi thọ hữu ích còn lại (Remaining Useful Life in hours) */
static volatile uint16_t g_rul_pct            = 100U; /* Phần trăm RUL (0..100%) */
static volatile uint16_t g_peak_bin_idx        = FFT_SKIP_BINS;
static volatile uint16_t g_peak_bin_mag        = 0;
static volatile uint16_t g_peak_freq_x10       = (uint16_t)(((uint32_t)FFT_SKIP_BINS * 3750U + 8U) >> 4);

/* Cấu hình HopACP - Higher-Order Adaptive Conformal Prediction (Q16.16) */
#define HOP_ACP_DELTA_ERR_Q16   2952L   /* +gamma * (1 - alpha) = 328 * 9.0 = +2952 (Bảo đảm bao phủ 90%) */
#define HOP_ACP_DELTA_OK_Q16    (-328L) /* -gamma * alpha = -328 (Thu hẹp cận khi thỏa mãn) */
#define HOP_ACP_BETA_Q16        3277L   /* Quán tính đạo hàm thích ứng sốc tải = 0.05 * 65536 */
#define HOP_ACP_QMIN_Q16        (5L * 65536L)   /* Biên dưới độ bất định: 5.0h */
#define HOP_ACP_QMAX_Q16        (500L * 65536L) /* Biên trên độ bất định: 500.0h */

static int32_t           s_hop_margin_q16      = (16L * 65536L) + 32768L; /* Biên khởi tạo 16.5h */
static uint8_t           s_hop_prev_err        = 0;

/* Bộ đệm kép Ping-Pong DMA SPI0 */
static uint8_t           s_spi_frame[2][SPI_FRAME_LEN] __attribute__((aligned(4)));
static volatile uint8_t  s_spi_rx_bank         = 0;
static volatile uint8_t  s_spi_work_bank       = 0;
static volatile uint8_t  s_spi_frame_ready     = 0;
static uint8_t           s_col_height[64]      = {0}; /* 64 cột phổ rời rạc với khoảng cách 1px chống dính chùm */
static uint16_t          s_bins[NUM_FFT_BINS];

static volatile hardware_dtc_t g_active_dtc    = DTC_SYSTEM_NORMAL;
static volatile bool     g_safety_tripped      = false;
static volatile OLED_Mode_t g_oled_mode        = OLED_MODE_MOTOR_PULSES;
static volatile int16_t  g_last_pressed_key    = -1;
static volatile uint8_t  g_last_pressed_sw     = 0;
static volatile uint32_t g_key_press_count     = 0;
static volatile uint8_t  g_oled_flip_state     = OLED_ROTATE_180_DEFAULT;
static volatile uint32_t g_sys_tick_ms         = 0;
static volatile uint8_t  g_oled_frame_ready    = 0;
static volatile uint8_t  g_has_key_event       = 0;
static volatile uint8_t  g_key_event           = 0xFF;

/* Mã LED 7 đoạn */
static const uint8_t SEG_CODE_RAW[16] = {
    0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07,
    0x7F, 0x6F, 0x77, 0x7C, 0x39, 0x5E, 0x79, 0x71
};
#define SEG_BLANK 0x00U
#define SEG_DASH  0x40U

static volatile uint8_t  g_7seg_patterns[4]  = { 0x3F, 0x3F, 0x3F, 0x3F };
static volatile uint8_t  g_7seg_active_digit = 0U;
static volatile uint16_t g_7seg_hold_timer   = 0U;

static void SevenSeg_SetNumber(uint16_t num) {
    if (num > 9999U) num = 9999U;
    g_7seg_patterns[3] = SEG_CODE_RAW[num % 10U];
    g_7seg_patterns[2] = (num >= 10U)   ? SEG_CODE_RAW[(num / 10U) % 10U]   : SEG_BLANK;
    g_7seg_patterns[1] = (num >= 100U)  ? SEG_CODE_RAW[(num / 100U) % 10U]  : SEG_BLANK;
    g_7seg_patterns[0] = (num >= 1000U) ? SEG_CODE_RAW[(num / 1000U) % 10U] : SEG_BLANK;
}

static void SevenSeg_ShowKey(uint8_t key) {
    g_7seg_patterns[0] = SEG_DASH; g_7seg_patterns[1] = SEG_DASH;
    g_7seg_patterns[2] = SEG_BLANK;
    g_7seg_patterns[3] = (key <= 0xFU) ? SEG_CODE_RAW[key] : SEG_DASH;
    g_7seg_hold_timer  = 1500U;
}

static const uint8_t KEY_MAP[4][4] = {
    { 0x1, 0x2, 0x3, 0xA },
    { 0x4, 0x5, 0x6, 0xB },
    { 0x7, 0x8, 0x9, 0xC },
    { 0xE, 0x0, 0xF, 0xD }
};

static const uint8_t Font5x7[96][5] = {
    {0x00,0x00,0x00,0x00,0x00}, {0x00,0x00,0x5F,0x00,0x00}, {0x00,0x07,0x00,0x07,0x00}, {0x14,0x7F,0x14,0x7F,0x14},
    {0x24,0x2A,0x7F,0x2A,0x12}, {0x23,0x13,0x08,0x64,0x62}, {0x36,0x49,0x55,0x22,0x50}, {0x00,0x05,0x03,0x00,0x00},
    {0x00,0x1C,0x22,0x41,0x00}, {0x00,0x41,0x22,0x1C,0x00}, {0x08,0x2A,0x1C,0x2A,0x08}, {0x08,0x08,0x3E,0x08,0x08},
    {0x00,0x50,0x30,0x00,0x00}, {0x08,0x08,0x08,0x08,0x08}, {0x00,0x60,0x60,0x00,0x00}, {0x20,0x10,0x08,0x04,0x02},
    {0x3E,0x51,0x49,0x45,0x3E}, {0x00,0x42,0x7F,0x40,0x00}, {0x42,0x61,0x51,0x49,0x46}, {0x21,0x41,0x45,0x4B,0x31},
    {0x18,0x14,0x12,0x7F,0x10}, {0x27,0x45,0x45,0x45,0x39}, {0x3C,0x4A,0x49,0x49,0x30}, {0x01,0x71,0x09,0x05,0x03},
    {0x36,0x49,0x49,0x49,0x36}, {0x06,0x49,0x49,0x29,0x1E}, {0x00,0x36,0x36,0x00,0x00}, {0x00,0x56,0x36,0x00,0x00},
    {0x00,0x08,0x14,0x22,0x41}, {0x14,0x14,0x14,0x14,0x14}, {0x41,0x22,0x14,0x08,0x00}, {0x02,0x01,0x51,0x09,0x06},
    {0x32,0x49,0x79,0x41,0x3E}, {0x7E,0x11,0x11,0x11,0x7E}, {0x7F,0x49,0x49,0x49,0x36}, {0x3E,0x41,0x41,0x41,0x22},
    {0x7F,0x41,0x41,0x22,0x1C}, {0x7F,0x49,0x49,0x49,0x41}, {0x7F,0x09,0x09,0x01,0x01}, {0x3E,0x41,0x49,0x49,0x7A},
    {0x7F,0x08,0x08,0x08,0x7F}, {0x00,0x41,0x7F,0x41,0x00}, {0x20,0x40,0x41,0x3F,0x01}, {0x7F,0x08,0x14,0x22,0x41},
    {0x7F,0x40,0x40,0x40,0x40}, {0x7F,0x02,0x0C,0x02,0x7F}, {0x7F,0x04,0x08,0x10,0x7F}, {0x3E,0x41,0x41,0x41,0x3E},
    {0x7F,0x09,0x09,0x09,0x06}, {0x3E,0x41,0x51,0x21,0x5E}, {0x7F,0x09,0x19,0x29,0x46}, {0x46,0x49,0x49,0x49,0x31},
    {0x01,0x01,0x7F,0x01,0x01}, {0x3F,0x40,0x40,0x40,0x3F}, {0x1F,0x20,0x40,0x20,0x1F}, {0x7F,0x20,0x18,0x20,0x7F},
    {0x63,0x14,0x08,0x14,0x63}, {0x03,0x04,0x78,0x04,0x03}, {0x61,0x51,0x49,0x45,0x43}, {0x00,0x7F,0x41,0x41,0x00},
    {0x02,0x04,0x08,0x10,0x20}, {0x00,0x41,0x41,0x7F,0x00}, {0x04,0x02,0x01,0x02,0x04}, {0x40,0x40,0x40,0x40,0x40},
    {0x00,0x01,0x02,0x04,0x00}, {0x20,0x54,0x54,0x54,0x78}, {0x7F,0x48,0x44,0x44,0x38}, {0x38,0x44,0x44,0x44,0x20},
    {0x38,0x44,0x44,0x48,0x7F}, {0x38,0x54,0x54,0x54,0x18}, {0x08,0x7E,0x09,0x01,0x02}, {0x08,0x14,0x54,0x54,0x3C},
    {0x7F,0x08,0x04,0x04,0x78}, {0x00,0x44,0x7D,0x40,0x00}, {0x20,0x40,0x44,0x3D,0x00}, {0x00,0x7F,0x10,0x28,0x44},
    {0x00,0x41,0x7F,0x40,0x00}, {0x7C,0x04,0x18,0x04,0x78}, {0x7C,0x08,0x04,0x04,0x78}, {0x38,0x44,0x44,0x44,0x38},
    {0x7C,0x14,0x14,0x14,0x08}, {0x08,0x14,0x14,0x18,0x7C}, {0x7C,0x08,0x04,0x04,0x08}, {0x48,0x54,0x54,0x54,0x20},
    {0x04,0x3F,0x44,0x40,0x20}, {0x3C,0x40,0x40,0x20,0x7C}, {0x1C,0x20,0x40,0x20,0x1C}, {0x3C,0x40,0x30,0x40,0x3C},
    {0x44,0x28,0x10,0x28,0x44}, {0x0C,0x50,0x50,0x50,0x3C}, {0x44,0x64,0x54,0x4C,0x44}, {0x00,0x08,0x36,0x41,0x00},
    {0x00,0x00,0x7F,0x00,0x00}, {0x00,0x41,0x36,0x08,0x00}, {0x08,0x08,0x2A,0x1C,0x08}, {0x08,0x1C,0x2A,0x08,0x08}
};

static void Delay(volatile uint32_t count) {
    while (count--) { __NOP(); }
}

static void I2C_Delay(void) {
    volatile uint8_t i;
    for (i = 0; i < 16; i++) { __NOP(); }
}

static void I2C_Start(void) {
    SDA_HIGH(); SCL_HIGH(); I2C_Delay();
    SDA_LOW();  I2C_Delay();
    SCL_LOW();  I2C_Delay();
}

static void I2C_Stop(void) {
    SDA_LOW();  I2C_Delay();
    SCL_HIGH(); I2C_Delay();
    SDA_HIGH(); I2C_Delay();
}

static void I2C_WriteByte(uint8_t byte) {
    uint8_t i;
    for (i = 0; i < 8; i++) {
        if (byte & 0x80U) { SDA_HIGH(); } else { SDA_LOW(); }
        I2C_Delay(); SCL_HIGH(); I2C_Delay(); SCL_LOW();
        byte <<= 1;
    }
    SDA_HIGH(); I2C_Delay(); SCL_HIGH(); I2C_Delay(); SCL_LOW(); I2C_Delay();
}

static void OLED_WriteCmd(uint8_t cmd) {
    I2C_Start(); I2C_WriteByte(OLED_ADDR); I2C_WriteByte(0x00U); I2C_WriteByte(cmd); I2C_Stop();
}

static void OLED_SetCursor(uint8_t page, uint8_t col) {
    OLED_WriteCmd((uint8_t)(0xB0U + (page & 0x07U)));
    OLED_WriteCmd((uint8_t)(0x00U | (col & 0x0FU)));
    OLED_WriteCmd((uint8_t)(0x10U | ((col >> 4) & 0x0FU)));
}

static void OLED_Fill(uint8_t pattern) {
    uint8_t page, col;
    for (page = 0; page < 8; page++) {
        OLED_SetCursor(page, 0);
        I2C_Start(); I2C_WriteByte(OLED_ADDR); I2C_WriteByte(0x40U);
        for (col = 0; col < 128; col++) { I2C_WriteByte(pattern); }
        I2C_Stop();
    }
}

static void OLED_SetFlip180(uint8_t flip) {
    if (flip) {
        OLED_WriteCmd(0xA1U); OLED_WriteCmd(0xC8U);
    } else {
        OLED_WriteCmd(0xA0U); OLED_WriteCmd(0xC0U);
    }
}

static void OLED_Init(void) {
    OLED_WriteCmd(0xAEU);
    OLED_WriteCmd(0xD5U); OLED_WriteCmd(0x80U);
    OLED_WriteCmd(0xA8U); OLED_WriteCmd(0x3FU);
    OLED_WriteCmd(0xD3U); OLED_WriteCmd(0x00U);
    OLED_WriteCmd(0x40U);
    OLED_WriteCmd(0x8DU); OLED_WriteCmd(0x14U);
    OLED_WriteCmd(0x20U); OLED_WriteCmd(0x02U);
    OLED_SetFlip180(g_oled_flip_state);
    OLED_WriteCmd(0xDAU); OLED_WriteCmd(0x12U);
    OLED_WriteCmd(0x81U); OLED_WriteCmd(0xCFU);
    OLED_WriteCmd(0xD9U); OLED_WriteCmd(0xF1U);
    OLED_WriteCmd(0xDBU); OLED_WriteCmd(0x40U);
    OLED_WriteCmd(0xA4U); OLED_WriteCmd(0xA6U); OLED_WriteCmd(0xAFU);
    OLED_Fill(0x00U);
}

static void OLED_PrintLine(uint8_t page, const char *str) {
    uint8_t line_buf[128];
    uint8_t x = 0, i;
    for (i = 0; i < 128; i++) line_buf[i] = 0x00;

    while (*str && (x + 6 <= 128)) {
        char c = *str++;
        uint8_t idx = ((uint8_t)c < 32 || (uint8_t)c > 126) ? 0 : (uint8_t)c - 32U;
        uint8_t b;
        for (b = 0; b < 5; b++) line_buf[x++] = Font5x7[idx][b];
        line_buf[x++] = 0x00;
    }
    OLED_SetCursor(page, 0);
    I2C_Start(); I2C_WriteByte(OLED_ADDR); I2C_WriteByte(0x40U);
    for (i = 0; i < 128; i++) I2C_WriteByte(line_buf[i]);
    I2C_Stop();
}

static void System_SoftwareReset(void) {
    __disable_irq();
    OLED_Fill(0x00U);
    OLED_PrintLine(2, "=== SYSTEM RESET ===");
    Delay(200000);
    *((volatile uint32_t *)0xE000ED0CUL) = (0x05FA0000UL | (1UL << 2));
    while (1) { __NOP(); }
}

static void Trigger_Safety_Trip(hardware_dtc_t dtc_code, const char *reason) {
    (void)reason;
    g_active_dtc = dtc_code;
    g_safety_tripped = true;
    RELAY_OFF();
    g_relay_state = 0;
}

/* ============================================================================
 * 2. THUẬT TOÁN CRC-16-CCITT (Poly 0x1021, Khớp 100% với FPGA SPI Master)
 * ============================================================================ */
static uint16_t Calculate_CRC16_CCITT(const uint8_t *data, uint32_t len) {
    uint16_t crc = 0xFFFFU;
    uint32_t i;
    uint8_t  j;
    for (i = 0; i < len; i++) {
        crc ^= ((uint16_t)data[i] << 8);
        for (j = 0; j < 8; j++) {
            if (crc & 0x8000U)
                crc = (crc << 1) ^ CRC16_POLY;
            else
                crc <<= 1;
        }
    }
    return crc;
}

/* ============================================================================
 * 3. NGOẠI VI SPI0 SLAVE VÀ DMA PING-PONG (524 BYTES)
 * ============================================================================ */
static void SPI_FIFO_Reset(void) {
    uint32_t guard = 20000U;
    SN_SPI0->CTRL0_b.FRESET = FSPI_FRESET_ALL;
    while ((SN_SPI0->CTRL0_b.FRESET == FSPI_FRESET_ALL) && (guard-- > 0U)) { }
}

static void SPI_DMA_Arm(uint8_t bank) {
    SN_DMA0->C0_DSTADDR = (uint32_t)(uintptr_t)s_spi_frame[bank];
    SN_DMA0->C0_SRCADDR = (uint32_t)(uintptr_t)&SN_SPI0->DATA;
    SN_DMA0->C0_SIZE    = SPI_FRAME_LEN;
    SN_DMA0->C0_CSR     = FDMA_CSR_RX_CFG | FDMA_CSR_CH_EN;
    SN_SPI0->DMA        = FSPI_RX_DMA_EN | (uint32_t)SPI_FRAME_LEN;
}

static void SPI_DMA_Resync(void) {
    uint32_t guard = 20000U;
    SN_SPI0->DMA = 0U;
    SN_DMA0->C0_CSR |= FDMA_CSR_ABT;
    while (((SN_DMA0->C0_CSR & FDMA_CSR_CH_EN) != 0U) && (guard-- > 0U)) { }
    SN_DMA0->INT_ABT_CLR = FDMA_INT_ABT_CH0;
    SN_DMA0->INT_TC_CLR  = FDMA_INT_TC_CH0;
    SPI_FIFO_Reset();
    SPI_DMA_Arm(s_spi_rx_bank);
}

void DMA_IRQHandler(void) {
    uint32_t tc  = SN_DMA0->INT_TC;
    uint32_t abt = SN_DMA0->INT_ABT;

    if (abt != 0U) {
        SN_DMA0->INT_ABT_CLR = abt;
    }
    if (tc & FDMA_INT_TC_CH0) {
        const volatile uint8_t *rx = s_spi_frame[s_spi_rx_bank];
        SN_DMA0->INT_TC_CLR = FDMA_INT_TC_CH0;
        /* Chấp nhận cả 2 dạng đồng bộ (0x55,0xAA hoặc 0xAA,0x55) loại trừ triệt để lỗi phân cực endian */
        if (((rx[0] == 0x55U) && (rx[1] == 0xAAU)) || ((rx[0] == 0xAAU) && (rx[1] == 0x55U))) {
            if (!s_spi_frame_ready) {
                s_spi_work_bank   = s_spi_rx_bank;
                s_spi_frame_ready = 1;
                s_spi_rx_bank    ^= 1U;
            }
            SPI_DMA_Arm(s_spi_rx_bank);
        } else {
            uint8_t i;
            for (i = 0; i < 8; i++) g_dbg_rx[i] = rx[i];
            g_dbg_isr_err++;
            g_fpga_sync_err_count++;
            SN_SPI0->DMA = 0U;
            SPI_FIFO_Reset();
            SPI_DMA_Arm(s_spi_rx_bank);
        }
    }
    tc = SN_DMA0->INT_TC;
    if (tc != 0U) { SN_DMA0->INT_TC_CLR = tc; }
}

/* Watchdog 15ms an toàn: Chỉ Reset khi DMA bị đơ giữa chừng quá lâu */
static void SPI_DMA_Watchdog_1ms(void) {
    static uint32_t s_last_rem = SPI_FRAME_LEN;
    static uint8_t  s_stall    = 0U;
    uint32_t rem;

    if ((SN_DMA0->C0_CSR & FDMA_CSR_CH_EN) == 0U) return;
    rem = SN_DMA0->C0_SIZE;
    if ((rem >= SPI_FRAME_LEN) || (rem != s_last_rem)) {
        s_last_rem = rem;
        s_stall = 0U;
        return;
    }
    if (++s_stall >= 15U) { /* 15 ms gap */
        uint8_t i;
        for (i = 0; i < 8; i++) g_dbg_rx[i] = s_spi_frame[s_spi_rx_bank][i];
        g_dbg_wd_err++;
        s_stall = 0U;
        g_fpga_sync_err_count++;
        SPI_DMA_Resync();
        s_last_rem = SPI_FRAME_LEN;
    }
}

static void SPI_FPGA_Init(void) {
    SN_SYS1->AHBCLKEN |= (1UL << 5) | FDMA_CLK_EN;
    SN_SYS1->AHBCLKEN_b.SPI0CLKEN = 1;

    /* P1.1 MISO, P1.2 MOSI, P1.0 SCK, P1.8 SEL */
    SN_PFPA->SPI0 = (2UL << 0) | (2UL << 2) | (2UL << 4) | (2UL << 6);

    SN_GPIO1->MODE_b.MODE0 = 0; SN_GPIO1->CFG_b.CFG0 = 1; /* SCK Pull-Down */
    SN_GPIO1->MODE_b.MODE8 = 0; SN_GPIO1->CFG_b.CFG8 = 0; /* SEL Pull-Up */
    SN_GPIO1->MODE_b.MODE2 = 0; SN_GPIO1->CFG_b.CFG2 = 2; /* MOSI Floating */

    SN_SPI0->CTRL0_b.SPIEN    = 0;
    SN_SPI0->CTRL0_b.DL       = FSPI_DL_8;
    SN_SPI0->CTRL0_b.MS       = 1;     /* Slave */
    SN_SPI0->CTRL0_b.SDODIS   = 1;     /* Tắt MISO */
    SN_SPI0->CTRL0_b.SELDIS   = 0;     /* Dùng P1.8 làm CS */
    SN_SPI0->CTRL1 = 0U;               /* Mode 0 (CPOL=0, CPHA=0), MSB first */
    SN_SPI0->IE    = 0U;
    SN_SPI0->DFDLY = 0U;
    SPI_FIFO_Reset();
    SN_SPI0->CTRL0_b.SPIEN    = 1;

    SN_DMA0->MCSR_b.DMACEN = 1;
    SN_DMA0->C0_CSR = 0U;
    SN_DMA0->C0_CFG = FDMA_CFG_ERR_ABT_MASK | FDMA_CFG_SRC_PERIPH | FDMA_CFG_SRC_SPI0_RX;
    SN_DMA0->INT_TC_CLR  = FDMA_INT_TC_CH0;
    SN_DMA0->INT_ABT_CLR = FDMA_INT_ABT_CH0;

    s_spi_rx_bank     = 0;
    s_spi_work_bank   = 0;
    s_spi_frame_ready = 0;

    NVIC_ClearPendingIRQ(DMA0_IRQn);
    NVIC_SetPriority(DMA0_IRQn, 0);
    NVIC_EnableIRQ(DMA0_IRQn);

    SPI_DMA_Arm(0);
}

static uint8_t Spi_FixByteOrder(uint8_t *w) {
    if (w[0] == 0x55U && w[1] == 0xAAU) {
        return 1U;
    }
    if (w[0] == 0xAAU && w[1] == 0x55U) {
        uint16_t n;
        for (n = 0; n < SPI_FRAME_LEN; n += 2U) {
            uint8_t t = w[n];
            w[n] = w[n + 1U];
            w[n + 1U] = t;
        }
        return 1U;
    }
    return 0U;
}

/* Hàm tính căn bậc 2 số nguyên tốc độ cao cho Cortex-M0 (Bit-by-Bit integer sqrt) */
static uint16_t Integer_Sqrt(uint32_t n) {
    uint32_t root = 0;
    uint32_t bit = 1UL << 30;
    while (bit > n) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (n >= root + bit) {
            n -= root + bit;
            root = (root >> 1) + bit;
        } else {
            root >>= 1;
        }
        bit >>= 2;
    }
    return (uint16_t)root;
}

/* ============================================================================
 * 4. GIẢI MÃ KHUNG TIN SPI 524 BYTES TỪ FPGA
 * ============================================================================ */
static void Process_FPGA_Frame(void) {
    uint16_t calc_crc, recv_crc;
    uint16_t max_vib = 0, max_bin = 2;
    uint16_t k, col;
    uint8_t *b;

    if (!s_spi_frame_ready) return;
    b = s_spi_frame[s_spi_work_bank];

    /* 1. Chuẩn hóa thứ tự byte về chuẩn FPGA (Little-Endian) */
    if (!Spi_FixByteOrder(b)) {
        g_fpga_sync_err_count++;
        s_spi_frame_ready = 0;
        return;
    }

    /* 2. Kiểm tra CRC-16-CCITT trên 522 bytes đầu theo thứ tự chuẩn wire của FPGA */
    calc_crc = Calculate_CRC16_CCITT((const uint8_t *)b, 522U);
    recv_crc = ((uint16_t)b[523] << 8) | b[522]; /* FPGA gửi CRC byte thấp trước */

    if (calc_crc != recv_crc) {
        uint8_t i;
        for (i = 0; i < 6; i++) g_dbg_rx[i] = b[518 + i];  /* 6 byte cuối khung */
        g_dbg_crc_calc = calc_crc;
        g_dbg_crc_recv = recv_crc;
        g_fpga_crc_err_count++;
        s_spi_frame_ready = 0;
        return;
    }

    /* 3. Đọc Frame Counter (Byte 2..3 Little-Endian) */
    g_fpga_frame_count  = ((uint16_t)b[3] << 8) | b[2];

    /* 4. Lấy kết quả chẩn đoán NPU phần cứng (Byte 518..521)
     * Trong RTL spi_master_packet.v:
     *   b[518] = {snap_ood, 5'b00000, snap_class} (Bit 7: OOD Alert, Bits 1..0: Class)
     *   b[519] = Dirichlet Vacuity (u_Q15[15:8])
     *   b[520..521] = Hardware Status Flags (Little-Endian)
     */
    g_epistemic_vacuity = (uint16_t)b[519] << 8; /* Scale sang Q15 */
    g_is_ood_alert      = ((b[518] & 0x80U) != 0U) || (g_epistemic_vacuity > 14745U);
    g_npu_class         = b[518] & 0x03U; /* 0: Normal, 1: BPFI, 2: BPFO, 3: BSF */
    g_fpga_hw_status    = ((uint16_t)b[521] << 8) | b[520];

    /* 5. Đọc đủ 257 Bins FFT (Bắt đầu từ Byte 4 đến Byte 517, Little-Endian mỗi bin)
     * Khớp 100% với RTL FPGA:
     *   k = 0 (Bin 0 DC)   : Byte 4 (LSB), Byte 5 (MSB)
     *   k = 1 (Bin 1 23.4Hz): Byte 6 (LSB), Byte 7 (MSB)
     *   ...
     *   k = 256 (Bin 256 6000Hz): Byte 516 (LSB), Byte 517 (MSB)
     */
    for (k = 0; k < NUM_FFT_BINS; k++) {
        uint16_t v = ((uint16_t)b[5 + k * 2] << 8) | b[4 + k * 2];
        s_bins[k] = v;
        if (k >= FFT_SKIP_BINS && v > max_vib) {
            max_vib = v;
            max_bin = k;
        }
    }
    s_spi_frame_ready = 0; /* Trả lại cờ cho DMA */
    g_last_good_frame_ms = g_sys_tick_ms;
    s_link_armed = true;

    g_fpga_packet_count++;
    LED_TOGGLE();

    g_peak_bin_mag  = max_vib;
    g_peak_bin_idx  = max_bin;
    g_peak_freq_x10 = (uint16_t)(((uint32_t)max_bin * 3750U + 8U) >> 4);

    /* 6. Ước lượng tuổi thọ hữu ích còn lại (Remaining Useful Life - RUL) & HopACP */
    {
        uint32_t point_rul;
        if (g_npu_class == BEARING_NORMAL) {
            point_rul = 1200U;
        } else if (g_fpga_hw_status <= 32768U && g_fpga_hw_status > 0U) {
            /* Su dung truc tiep RUL phan cung lien tuc tinh tu NPU 12-way FPGA (Byte 520..521) */
            point_rul = (uint32_t)(((uint32_t)g_fpga_hw_status * 1200U + 16384U) >> 15);
            if (point_rul < 2U)    point_rul = 2U;
            if (point_rul > 1200U) point_rul = 1200U;
        } else {
            uint32_t fault_energy = 0;
            for (k = 4; k <= 16; k++) {
                fault_energy += s_bins[k];
            }
            int32_t base_h = (g_npu_class == BEARING_INNER_RACE)  ? 350L :
                             (g_npu_class == BEARING_OUTER_RACE)  ? 180L : 80L;
            int32_t wear_loss = (int32_t)(fault_energy / 64U);
            int32_t h = base_h - wear_loss;
            if (h < 2L)    h = 2L;
            if (h > 1200L) h = 1200L;
            point_rul = (uint32_t)h;
        }
        /* Lọc EMA (Exponential Moving Average) 16-tap làm mượt dao động giữa các khung */
        g_rul_hours = (g_rul_hours * 15U + point_rul + 8U) / 16U;
        g_rul_pct   = (uint16_t)((g_rul_hours * 100U + 600U) / 1200U);
        if (g_rul_pct > 100U) g_rul_pct = 100U;

        /* Cập nhật khoảng bất định HopACP Q16.16 */
        {
            int32_t point_q16 = (int32_t)g_rul_hours << 16;
            int32_t low_q16   = point_q16 - s_hop_margin_q16;
            int32_t high_q16  = point_q16 + s_hop_margin_q16;
            if (low_q16 < 0) low_q16 = 0;

            int32_t feedback_q16 = (int32_t)point_rul << 16;
            uint8_t miscovered = (feedback_q16 < low_q16 || feedback_q16 > high_q16) ? 1U : 0U;

            int32_t delta = miscovered ? HOP_ACP_DELTA_ERR_Q16 : HOP_ACP_DELTA_OK_Q16;
            int32_t d_err = (int32_t)miscovered - (int32_t)s_hop_prev_err;
            if (d_err > 0)      delta += HOP_ACP_BETA_Q16;
            else if (d_err < 0) delta -= HOP_ACP_BETA_Q16;
            s_hop_prev_err = miscovered;

            s_hop_margin_q16 += delta;
            if (s_hop_margin_q16 < HOP_ACP_QMIN_Q16) s_hop_margin_q16 = HOP_ACP_QMIN_Q16;
            if (s_hop_margin_q16 > HOP_ACP_QMAX_Q16) s_hop_margin_q16 = HOP_ACP_QMAX_Q16;
        }
    }

    /* 7. Cập nhật 64 cột phổ rời rạc (Digital Equalizer Bars) với Auto-Gain & Sqrt Dynamic Range */
    {
        uint32_t max_disp = 1U;
        uint32_t sqrt_max;

        /* Quét tìm giá trị đỉnh thực tế của các bin hiển thị (bỏ qua DC/hạ tần < 46.9Hz) */
        for (col = 2; col < 64; col++) {
            uint16_t val = (col < NUM_FFT_BINS) ? s_bins[col] : 0;
            if (val > max_disp) {
                max_disp = val;
            }
        }

        sqrt_max = (uint32_t)Integer_Sqrt(max_disp);
        if (sqrt_max < 4U) sqrt_max = 4U; /* Ngưỡng sàn chống chia cho 0 khi không có tín hiệu */

        for (col = 0; col < 64; col++) {
            uint16_t val = (col < NUM_FFT_BINS) ? s_bins[col] : 0;
            uint32_t h;

            if (col < 2) {
                val = 0; /* Bỏ cột DC (Bin 0 & 1) */
            }

            if (val == 0) {
                h = 0;
            } else {
                /* Dùng căn bậc 2 mở rộng dải động:
                 * - Đỉnh phổ (max_disp) sẽ vươn cao tới 46 pixels (sát mép chữ trên).
                 * - Các hài và dải tần lỗi phụ không bị chìm ở đáy mà vươn cao 15-30 pixels. */
                uint32_t sqrt_v = (uint32_t)Integer_Sqrt(val);
                h = (sqrt_v * 46U) / sqrt_max;
                if (h == 0) h = 1U; /* Giữ tối thiểu 1 pixel vệt phổ */
                if (h > 46U) h = 46U;
            }

            /* Lọc IIR làm mượt cột: 37.5% cũ + 62.5% mới */
            s_col_height[col] = (uint8_t)(((uint32_t)s_col_height[col] * 3U + h * 5U + 4U) / 8U);
        }
    }

    /* 7. SIL-2 Logic Trip Bảo Vệ Động Cơ:
     * - Trip tức thì nếu rung động vượt ngưỡng vật lý (VIB_TRIP_LIMIT)
     * - Trip có lọc debounce (5 khung liên tiếp = ~213ms) nếu NPU báo Bearing Fault hoặc OOD
     */
    if (g_peak_bin_mag >= VIB_TRIP_LIMIT) {
        Trigger_Safety_Trip(DTC_CRITICAL_BEARING_TRIP, "Vibration Exceeded Limit");
    }

    if ((g_npu_class != BEARING_NORMAL) || g_is_ood_alert) {
        if (s_consecutive_faults < 255U) s_consecutive_faults++;
        if (s_consecutive_faults >= FAULT_PERSISTENCE_LIMIT) {
            Trigger_Safety_Trip(DTC_CRITICAL_BEARING_TRIP, "Bearing Fault / OOD Confirmed");
        }
    } else {
        s_consecutive_faults = 0U;
    }
}

static void Draw_FFT_Spectrum_Fast(void) {
    uint16_t col;
    uint8_t  page, top, lo, byte_val;
    uint8_t  peak_bar = (uint8_t)g_peak_bin_idx;

    for (page = 2; page < 8; page++) {
        OLED_SetCursor(page, 0);
        lo = (uint8_t)(page * 8U);
        I2C_Start(); I2C_WriteByte(OLED_ADDR); I2C_WriteByte(0x40U);
        for (col = 0; col < 128; col++) {
            uint8_t bar_idx = (uint8_t)(col >> 1);
            if ((col & 1U) && (bar_idx != peak_bar)) {
                /* Cột lẻ thông thường: Khe hở 1-pixel màu đen chống hiện tượng dính chùm */
                byte_val = 0x00U;
            } else {
                /* Cột chẵn HOẶC cột của Đỉnh phổ (Peak Bin): Cột phổ tương ứng */
                if (bar_idx < 64) {
                    top = (uint8_t)(64U - s_col_height[bar_idx]);
                    if (top <= lo) byte_val = 0xFFU;
                    else if (top >= (lo + 8U)) byte_val = 0x00U;
                    else byte_val = (uint8_t)(0xFFU << (top - lo));
                } else {
                    byte_val = 0x00U;
                }
            }
            /* Thêm đường trục hoành cơ sở (Baseline) ở đáy màn hình (Page 7, Bit 7) */
            if (page == 7) {
                byte_val |= 0x80U;
            }
            I2C_WriteByte(byte_val);
        }
        I2C_Stop();
    }
}

static int16_t MatrixKeypad_Scan_Raw(void) {
    uint8_t r, c;
    uint32_t cols;
    volatile int d;
    for (r = 0; r < 4; r++) {
        SN_GPIO1->BSET = ROW_MASK;
        SN_GPIO1->BCLR = (1U << (4 + r));
        for (d = 0; d < 40; d++) __NOP();
        cols = (SN_GPIO2->DATA >> 4) & 0x0FU;
        for (c = 0; c < 4; c++) {
            if (!(cols & (1U << c))) {
                SN_GPIO1->BSET = ROW_MASK;
                g_last_pressed_sw = (uint8_t)(r * 4 + c + 1);
                return (int16_t)KEY_MAP[r][c];
            }
        }
    }
    SN_GPIO1->BSET = ROW_MASK;
    return -1;
}

static void Keypad_Tick_5ms(void) {
    int16_t raw_key = MatrixKeypad_Scan_Raw();
    static int16_t s_debouncing_key = -1;
    static uint8_t s_debounce_count = 0;
    static int16_t s_latched_key = -1;

    if (raw_key != -1 && raw_key == s_debouncing_key) {
        if (s_debounce_count < 255U) s_debounce_count++;
        if (s_debounce_count == 3U) {
            if (raw_key != s_latched_key) {
                s_latched_key = raw_key;
                g_key_event = (uint8_t)raw_key;
                g_has_key_event = 1;
            }
        }
    } else {
        s_debouncing_key = raw_key;
        s_debounce_count = 0U;
        if (raw_key == -1) s_latched_key = -1;
    }
}

static void Handle_Keypad_Event(uint8_t key) {
    g_last_pressed_key = (int16_t)key;
    g_key_press_count++;
    SevenSeg_ShowKey(key);

    switch (key) {
        case 0x1:
            g_safety_tripped = false;
            g_active_dtc = DTC_SYSTEM_NORMAL;
            s_boot_ref_ms = g_sys_tick_ms;
            g_last_good_frame_ms = g_sys_tick_ms;
            s_consecutive_faults = 0U;
            g_relay_state = 1;
            RELAY_ON();
            break;
        case 0x2:
            g_relay_state = 0;
            RELAY_OFF();
            break;
        case 0x3:
        case 0x9:
            g_relay_state = (uint8_t)(!g_relay_state);
            if (g_relay_state) {
                g_safety_tripped = false;
                g_active_dtc = DTC_SYSTEM_NORMAL;
                s_boot_ref_ms = g_sys_tick_ms;
                g_last_good_frame_ms = g_sys_tick_ms;
                s_consecutive_faults = 0U;
                RELAY_ON();
            } else {
                RELAY_OFF();
            }
            break;
        case 0x4:
            __disable_irq();
            s_spi_frame_ready = 0;
            s_spi_rx_bank = 0;
            s_boot_ref_ms = g_sys_tick_ms;
            SPI_DMA_Resync();
            __enable_irq();
            break;
        case 0xA: g_oled_mode = (OLED_Mode_t)((g_oled_mode + 1) % OLED_MODE_MAX); OLED_Fill(0x00U); break;
        case 0xB:
        case 0x5: g_oled_mode = (OLED_Mode_t)((g_oled_mode + OLED_MODE_MAX - 1) % OLED_MODE_MAX); OLED_Fill(0x00U); break;
        case 0xC:
            __disable_irq(); g_pulse_count = 0; g_pulses_window = 0; g_rev_count = 0; g_rev_decimal = 0; g_measured_rpm = 0; __enable_irq();
            SevenSeg_SetNumber(0);
            break;
        case 0xD:
            g_active_dtc = DTC_SYSTEM_NORMAL;
            g_safety_tripped = false;
            s_boot_ref_ms = g_sys_tick_ms;
            g_last_good_frame_ms = g_sys_tick_ms;
            s_consecutive_faults = 0U;
            break;
        case 0xE:
        case 0x7: System_SoftwareReset(); break;
        case 0xF:
        case 0x6:
        case 0x8: g_oled_flip_state = (uint8_t)(!g_oled_flip_state); OLED_SetFlip180(g_oled_flip_state); break;
        default: break;
    }
}

static void Update_OLED_Display(void) {
    char buf[24];
    const char *bearing_str;

    switch (g_npu_class) {
        case BEARING_INNER_RACE:  bearing_str = "BPFI (INNER) "; break;
        case BEARING_OUTER_RACE:  bearing_str = "BPFO (OUTER) "; break;
        case BEARING_BALL_DEFECT: bearing_str = "BALL DEFECT  "; break;
        default:                  bearing_str = "HEALTHY [OK] "; break;
    }

    switch (g_oled_mode) {
        case OLED_MODE_MOTOR_PULSES:
            OLED_PrintLine(0, "=== MOTOR & ENCODER =");
            sprintf(buf, "Motor : %-4s (P2.2)", g_relay_state ? "RUN " : "STOP");
            OLED_PrintLine(2, buf);
            sprintf(buf, "Speed : %5u RPM", (unsigned)g_measured_rpm);
            OLED_PrintLine(4, buf);
            sprintf(buf, "Pulses: %-7lu (30PPR)", (unsigned long)g_pulse_count);
            OLED_PrintLine(6, buf);
            break;

        case OLED_MODE_FPGA_DIAGNOSTICS:
            if (g_fpga_packet_count == 0) {
                OLED_PrintLine(0, "=== WAITING FPGA ===");
                sprintf(buf, "Link  : SEARCHING SPI");
                OLED_PrintLine(2, buf);
                sprintf(buf, "CRCerr: %-5lu", (unsigned long)g_fpga_crc_err_count);
                OLED_PrintLine(4, buf);
                sprintf(buf, "SyncEr: %-5lu", (unsigned long)g_fpga_sync_err_count);
                OLED_PrintLine(6, buf);
            } else {
                const char *health_badge;
                int32_t margin_h = (s_hop_margin_q16 + 32768L) >> 16;
                if (g_rul_pct > 50U)      health_badge = "[NORM]";
                else if (g_rul_pct > 20U) health_badge = "[WARN]";
                uint16_t vac_pct = (uint16_t)(((uint32_t)g_epistemic_vacuity * 100U + 16384U) >> 15);
                if (margin_h < 1) margin_h = 1;

                sprintf(buf, "HEALTH:%3u%%  %-6s", (unsigned)g_rul_pct, health_badge);
                OLED_PrintLine(0, buf);

                sprintf(buf, "FAULT : %-13s", bearing_str);
                OLED_PrintLine(2, buf);

                sprintf(buf, "RUL   :%4luh (+-%ldh)", (unsigned long)g_rul_hours, (long)margin_h);
                OLED_PrintLine(4, buf);

                if (g_safety_tripped) {
                    sprintf(buf, "TRIP:%3uHz B:%-2u u:%2u%%", g_peak_freq_x10 / 10U, (unsigned)g_peak_bin_idx, (unsigned)vac_pct);
                } else {
                    sprintf(buf, "PK:%3u.%uHz B:%-2u u:%2u%%", g_peak_freq_x10 / 10U, g_peak_freq_x10 % 10U, (unsigned)g_peak_bin_idx, (unsigned)vac_pct);
                }
                OLED_PrintLine(6, buf);
            }
            break;

        case OLED_MODE_FFT_SPECTRUM:
            {
                int32_t margin_h = (s_hop_margin_q16 + 32768L) >> 16;
                uint16_t vac_pct = (uint16_t)(((uint32_t)g_epistemic_vacuity * 100U + 16384U) >> 15);
                if (margin_h < 1) margin_h = 1;

                sprintf(buf, "PK:%3u.%uHz B:%-2u u:%2u%%", g_peak_freq_x10 / 10U, g_peak_freq_x10 % 10U, (unsigned)g_peak_bin_idx, (unsigned)vac_pct);
                OLED_PrintLine(0, buf);
                if (g_fpga_packet_count > 0) {
                    const char *cls_short = (g_npu_class == BEARING_INNER_RACE)  ? "BPFI" :
                                            (g_npu_class == BEARING_OUTER_RACE)  ? "BPFO" :
                                            (g_npu_class == BEARING_BALL_DEFECT) ? "BALL" : "NORM";
                    sprintf(buf, "%-4s RUL:%-4luh +-%-2ldh", cls_short, (unsigned long)g_rul_hours, (long)margin_h);
                } else {
                    sprintf(buf, "FPGA SYNCING...     ");
                }
                OLED_PrintLine(1, buf);
                Draw_FFT_Spectrum_Fast();
            }
            break;

        case OLED_MODE_KEYPAD_SAFETY:
            OLED_PrintLine(0, "=== KEYPAD & SAFETY =");
            if (g_last_pressed_key >= 0 && g_last_pressed_sw > 0) {
                sprintf(buf, "Key   : SW%-2u (Code 0x%X)", (unsigned)g_last_pressed_sw, (unsigned)g_last_pressed_key);
            } else {
                sprintf(buf, "Key   : [ STANDBY ] ");
            }
            OLED_PrintLine(2, buf);
            sprintf(buf, "Safety: %-14s", g_safety_tripped ? "TRIPPED [HALT]" : "ARMED [NORMAL]");
            OLED_PrintLine(4, buf);
            sprintf(buf, "Relay : %-4s (P2.2=%u)", g_relay_state ? "RUN " : "STOP", g_relay_state ? 0U : 1U);
            OLED_PrintLine(6, buf);
            break;

        default: g_oled_mode = OLED_MODE_MOTOR_PULSES; break;
    }
}

static uint32_t Get_Micros(void) {
    uint32_t ms = g_sys_tick_ms;
    uint32_t elapsed_ticks = SysTick->LOAD - SysTick->VAL;
    uint32_t ticks_per_us = (SystemCoreClock > 0) ? (SystemCoreClock / 1000000UL) : 48U;
    return (ms * 1000U) + (elapsed_ticks / ticks_per_us);
}

void P2_IRQHandler(void) {
    uint32_t ris = SN_GPIO2->RIS & ENCODER_PIN_MASK;
    if (ris) {
        uint32_t now_us = Get_Micros();
        SN_GPIO2->IC = ris;
        if ((now_us - g_last_pulse_us) < 60U) return;
        g_last_pulse_us = now_us;
        g_pulse_count++;
        g_pulses_window++;
        g_rev_count   = g_pulse_count / ENCODER_PPR;
        g_rev_decimal = ((g_pulse_count % ENCODER_PPR) * 100U) / ENCODER_PPR;
    }
}

void SysTick_Handler(void) {
    static uint16_t s_speed_timer = 0;
    static uint8_t  s_oled_timer  = 0;
    uint32_t now_us;
    uint8_t seg;

    g_sys_tick_ms++;
    SPI_DMA_Watchdog_1ms();

    /* Mất FPGA khi động cơ đang chạy -> ngắt relay an toàn */
    if (g_relay_state && !g_safety_tripped) {
        if (s_link_armed) {
            if ((uint32_t)(g_sys_tick_ms - g_last_good_frame_ms) > LINK_TIMEOUT_MS) {
                Trigger_Safety_Trip(DTC_FPGA_HEARTBEAT_TIMEOUT, "FPGA Link Lost");
            }
        } else {
            if ((uint32_t)(g_sys_tick_ms - s_boot_ref_ms) > BOOT_GRACE_MS) {
                Trigger_Safety_Trip(DTC_FPGA_HEARTBEAT_TIMEOUT, "FPGA Boot Link Timeout");
            }
        }
    }

    now_us = Get_Micros();
    if (g_last_pulse_us > 0U && (uint32_t)(now_us - g_last_pulse_us) > 250000U) {
        g_measured_rpm = 0U;
    }

    /* Quét LED 7 đoạn 4 số (250 Hz) */
    SN_GPIO1->BCLR = COM_MASK;
    seg = g_7seg_patterns[g_7seg_active_digit];
    SN_GPIO0->DATA = (SN_GPIO0->DATA & ~SEG_MASK) | (seg & SEG_MASK);
    SN_GPIO1->BSET = (1U << (9 + g_7seg_active_digit));
    g_7seg_active_digit = (g_7seg_active_digit + 1U) & 0x03U;

    if (g_7seg_hold_timer > 0U) {
        g_7seg_hold_timer--;
    } else {
        SevenSeg_SetNumber(g_measured_rpm);
    }

    if ((g_sys_tick_ms % 5U) == 0U) {
        Keypad_Tick_5ms();
    }

    s_speed_timer++;
    if (s_speed_timer >= 200U) {
        uint32_t pulses = g_pulses_window;
        s_speed_timer = 0U;
        g_pulses_window = 0U;

        if (pulses == 0U) {
            g_measured_rpm = 0U;
        } else {
            uint32_t raw_rpm = (pulses * 60000UL) / (ENCODER_PPR * 200UL);
            if (raw_rpm > 15000U) raw_rpm = 15000U;
            if (pulses <= 5U) {
                g_measured_rpm = (uint16_t)raw_rpm;
            } else {
                g_measured_rpm = (uint16_t)(((uint32_t)g_measured_rpm * 3U + raw_rpm + 2U) >> 2);
            }
        }
    }

    s_oled_timer++;
    if (s_oled_timer >= 100U) {
        s_oled_timer = 0U;
        g_oled_frame_ready = 1;
    }
}

static void System_Hardware_Init(void) {
    SystemInit();
    SystemCoreClockUpdate();
    if (SystemCoreClock == 0) {
        SystemCoreClock = 48000000UL;
    }

    SN_SYS1->AHBCLKEN |= (1U << 4) | (1U << 5) | (1U << 6) | (1U << 7);

    SN_GPIO3->MODE |= (1U << LED_PIN_BIT);
    LED_OFF();

    RELAY_OFF();
    SN_GPIO2->MODE |= (1U << RELAY_PIN_BIT);
    g_relay_state = 0;

    SN_GPIO2->MODE &= ~(ENCODER_PIN_MASK | COL_MASK);
    SN_GPIO2->CFG  &= ~0x000FFFC0UL; /* Pull-up P2.3..P2.9 */

    SN_GPIO2->IS   &= ~ENCODER_PIN_MASK;
    SN_GPIO2->IBS  &= ~ENCODER_PIN_MASK;
    SN_GPIO2->IEV  &= ~ENCODER_PIN_MASK; /* Rising edge */
    SN_GPIO2->IC    =  ENCODER_PIN_MASK;
    SN_GPIO2->IE   |=  ENCODER_PIN_MASK;

    NVIC_ClearPendingIRQ(P2_IRQn);
    NVIC_SetPriority(P2_IRQn, 1);
    NVIC_EnableIRQ(P2_IRQn);

    SN_GPIO1->MODE |= ROW_MASK;
    SN_GPIO1->BSET  = ROW_MASK;

    SN_GPIO0->MODE |= SEG_MASK;
    SN_GPIO0->BCLR  = SEG_MASK;
    SN_GPIO1->MODE |= COM_MASK;
    SN_GPIO1->BCLR  = COM_MASK;

    SN_GPIO0->MODE |= (1U << 10) | (1U << 11);
    SN_GPIO0->CFG   = (SN_GPIO0->CFG & ~(0xFUL << 20)) | (0x5UL << 20);
    SCL_HIGH();
    SDA_HIGH();
    Delay(10000);

    OLED_Init();
    OLED_Fill(0x00U);
    OLED_PrintLine(0, "VIBRADISTILL-EDGE");
    OLED_PrintLine(2, "BEARING DIAGNOSTICS");
    OLED_PrintLine(4, "NPU + CONFORMAL RUL");
    OLED_PrintLine(6, "SYSTEM READY - SIL2");
    Delay(200000);
    OLED_Fill(0x00U);
    /* CRC-16 Self-Test chuẩn vector "123456789" -> 0x29B1 */
    {
        static const uint8_t crc_test_vec[9] = "123456789";
        if (Calculate_CRC16_CCITT(crc_test_vec, 9U) != 0x29B1U) {
            Trigger_Safety_Trip(DTC_SPI_CHECKSUM_FAULT, "CRC Self-Test Failed");
        }
    }
    s_boot_ref_ms        = 0U;
    s_link_armed         = false;
    s_consecutive_faults = 0U;

    SPI_FPGA_Init();

    NVIC_SetPriority(SysTick_IRQn, 0);
    SysTick_Config(SystemCoreClock / 1000UL);
}

int main(void) {
    uint8_t key;
    System_Hardware_Init();

    while (1) {
        Process_FPGA_Frame();

        if (g_has_key_event) {
            key = g_key_event;
            g_has_key_event = 0;
            Handle_Keypad_Event(key);
            Update_OLED_Display();
            g_oled_frame_ready = 0;
        }

        if (g_oled_frame_ready) {
            g_oled_frame_ready = 0;
            Update_OLED_Display();
        }
    }
}
