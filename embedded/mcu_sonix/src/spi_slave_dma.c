#include "spi_slave_dma.h"
#include "hal.h"

#define ST_IDLE   0U
#define ST_ARMED  1U
#define ST_READY  2U
#define ST_BUSY   3U

static uint8_t s_rx_frame[SPI_FRAME_LEN] SPI_ALIGN4;   /* 524 B */
static volatile uint8_t  s_state;
static volatile uint32_t s_armed_ms;
static spi_stats_t       s_stats;

void Spi_Slave_Init(void)
{
    s_stats.ok = 0U; s_stats.crc_err = 0U; s_stats.hdr_err = 0U;
    s_stats.overrun = 0U; s_stats.timeout = 0U;
    hal_spi_slave_init();
    hal_drdy_init();
    
    /* Always-Ready DMA: Arm immediately so MCU does NOT require DRDY pin! */
    s_state    = ST_ARMED;
    s_armed_ms = hal_millis();
    hal_spi_rx_arm(s_rx_frame, (uint16_t)SPI_FRAME_LEN);
}

/* P2.4 ISR: keep as short as possible (DMA must be armed within 50 us). */
void Spi_Slave_OnDrdyIrq(void)
{
    if (s_state == ST_IDLE) {
        s_state    = ST_ARMED;
        s_armed_ms = hal_millis();
        hal_spi_rx_arm(s_rx_frame, (uint16_t)SPI_FRAME_LEN);
    } else {
        s_stats.overrun++;
    }
}

void Spi_Slave_OnFrameEnd(void)
{
    if (s_state == ST_ARMED) {
        s_state = ST_READY;
    }
}

void Spi_Slave_Task(void)
{
    /* If DMA was armed but got stalled/interrupted, re-arm cleanly */
    if ((s_state == ST_ARMED) &&
        ((uint32_t)(hal_millis() - s_armed_ms) > SPI_FRAME_TIMEOUT_MS)) {
        uint32_t primask = hal_irq_save();
        if (s_state == ST_ARMED) {
            hal_spi_rx_abort();
            s_stats.timeout++;
            s_armed_ms = hal_millis();
            hal_spi_rx_arm(s_rx_frame, (uint16_t)SPI_FRAME_LEN);
        }
        hal_irq_restore(primask);
    }
}

uint16_t Spi_Crc16Ccitt(const uint8_t *data, uint16_t len)
{
    uint16_t crc = 0xFFFFU;
    uint16_t i;
    uint8_t  b;

    for (i = 0U; i < len; i++) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (b = 0U; b < 8U; b++) {
            if ((crc & 0x8000U) != 0U) {
                crc = (uint16_t)((uint16_t)(crc << 1) ^ 0x1021U);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

uint16_t Spi_Frame_GetBin(const uint8_t *frame, uint16_t index)
{
    uint16_t off = (uint16_t)(SPI_FRAME_BIN_OFFSET + (index * 2U));
    return (uint16_t)(((uint16_t)frame[off] << 8) | (uint16_t)frame[off + 1U]);
}

uint16_t Spi_Frame_ShaftSpeed(const uint8_t *frame)
{
    return (uint16_t)(((uint16_t)frame[4] << 8) | (uint16_t)frame[5]);
}

spi_poll_t Spi_Slave_Poll(const uint8_t **frame)
{
    uint16_t rx_crc;

    if (s_state != ST_READY) {
        return SPI_POLL_NONE;
    }
    if ((s_rx_frame[0] != SPI_FRAME_SYNC0) || (s_rx_frame[1] != SPI_FRAME_SYNC1)) {
        s_stats.hdr_err++;
        s_state    = ST_ARMED;
        s_armed_ms = hal_millis();
        hal_spi_rx_arm(s_rx_frame, (uint16_t)SPI_FRAME_LEN);
        return SPI_POLL_BAD_HEADER;
    }
    rx_crc = (uint16_t)(((uint16_t)s_rx_frame[SPI_FRAME_CRC_OFFSET] << 8) |
                        (uint16_t)s_rx_frame[SPI_FRAME_CRC_OFFSET + 1U]);
    if (Spi_Crc16Ccitt(s_rx_frame, (uint16_t)SPI_FRAME_CRC_OFFSET) != rx_crc) {
        s_stats.crc_err++;
        s_state    = ST_ARMED;
        s_armed_ms = hal_millis();
        hal_spi_rx_arm(s_rx_frame, (uint16_t)SPI_FRAME_LEN);
        return SPI_POLL_BAD_CRC;
    }
    s_stats.ok++;
    s_state = ST_BUSY;                        /* hold buffer until Release() */
    *frame  = s_rx_frame;
    return SPI_POLL_OK;
}

void Spi_Slave_Release(void)
{
    uint32_t primask = hal_irq_save();
    /* Immediately re-arm DMA for next incoming packet (No DRDY required) */
    s_state    = ST_ARMED;
    s_armed_ms = hal_millis();
    hal_spi_rx_arm(s_rx_frame, (uint16_t)SPI_FRAME_LEN);
    hal_irq_restore(primask);
}

const spi_stats_t *Spi_Slave_GetStats(void)
{
    return &s_stats;
}

