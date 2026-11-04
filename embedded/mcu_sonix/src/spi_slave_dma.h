#ifndef SPI_SLAVE_DMA_H
#define SPI_SLAVE_DMA_H

#include <stdint.h>

#define SPI_FRAME_LEN         524U
#define SPI_FRAME_BINS        257U
#define SPI_FRAME_BIN_OFFSET  8U
#define SPI_FRAME_CRC_OFFSET  522U
#define SPI_FRAME_SYNC0       0xAAU
#define SPI_FRAME_SYNC1       0x55U

#ifndef SPI_FRAME_TIMEOUT_MS
#define SPI_FRAME_TIMEOUT_MS  10U   /* frame lasts ~0.34 ms at 12.5 MHz */
#endif

#if defined(__GNUC__) || defined(__ARMCC_VERSION)
#define SPI_ALIGN4 __attribute__((aligned(4)))
#else
#define SPI_ALIGN4
#endif

typedef enum {
    SPI_POLL_NONE = 0,      /* no frame pending                         */
    SPI_POLL_OK,            /* valid frame; caller MUST call Release()  */
    SPI_POLL_BAD_HEADER,    /* dropped (auto-released)                  */
    SPI_POLL_BAD_CRC        /* dropped (auto-released)                  */
} spi_poll_t;

typedef struct {
    uint16_t ok;
    uint16_t crc_err;
    uint16_t hdr_err;
    uint16_t overrun;       /* DRDY arrived while previous frame busy   */
    uint16_t timeout;       /* DMA armed but frame never completed      */
} spi_stats_t;

void        Spi_Slave_Init(void);
void        Spi_Slave_Task(void);                 /* supervises armed-timeout */
void        Spi_Slave_OnDrdyIrq(void);            /* call from P2.4 ISR       */
void        Spi_Slave_OnFrameEnd(void);           /* call on 524-byte done    */
spi_poll_t  Spi_Slave_Poll(const uint8_t **frame);
void        Spi_Slave_Release(void);
const spi_stats_t *Spi_Slave_GetStats(void);

uint16_t    Spi_Crc16Ccitt(const uint8_t *data, uint16_t len);

/* Big-endian field accessors (frame is the 524-byte buffer) */
uint16_t    Spi_Frame_GetBin(const uint8_t *frame, uint16_t index);
uint16_t    Spi_Frame_ShaftSpeed(const uint8_t *frame);   /* 0.1 Hz units */

#endif
