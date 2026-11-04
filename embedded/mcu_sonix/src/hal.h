/**
 * @file  hal.h
 * @brief Hardware abstraction contract for VibraDistill-Edge (Sonix SN32F407).
 *
 * Every vendor-register access lives behind this header. Application modules
 * (spi_slave_dma, tachometer, safety_trip, oled_ssd1306, main) never touch
 * peripheral registers directly. Implement these in hal_sn32f407.c.
 * All functions returning int: 0 = success, non-zero = failure/timeout.
 */
#ifndef HAL_H
#define HAL_H

#include <stdint.h>

/* ---- System ------------------------------------------------------------- */
void     hal_system_init(void);            /* 60 MHz core clock, flash wait states   */
void     hal_systick_init(void);           /* 1 ms tick feeding hal_millis()         */
uint32_t hal_millis(void);                 /* free-running ms counter (wraps ok)     */
uint32_t hal_irq_save(void);               /* returns previous PRIMASK, masks IRQs   */
void     hal_irq_restore(uint32_t state);

/* ---- Watchdog ------------------------------------------------------------ */
void     hal_wdt_init(uint32_t timeout_ms);
void     hal_wdt_feed(void);

/* ---- Relay (P1.0): level 0 = closed/run, level 1 = TRIP ------------------ */
void     hal_relay_init(void);             /* output, high drive, drives level 0     */
void     hal_relay_set(uint8_t level);     /* MUST be a single atomic register write */

/* ---- DRDY_IRQ (P2.4, rising) -> calls Spi_Slave_OnDrdyIrq() -------------- */
void     hal_drdy_init(void);

/* ---- SPI0 slave RX (Mode 0) ---------------------------------------------- */
void     hal_spi_slave_init(void);
/** Start receiving exactly len bytes into dst. Called from the DRDY ISR, so it
 *  must complete in a few register writes (< ~20 us). When all len bytes have
 *  arrived, call Spi_Slave_OnFrameEnd() once. Do NOT call it on a truncated
 *  frame (CS released early). May preload the MISO ACK flag. */
void     hal_spi_rx_arm(uint8_t *dst, uint16_t len);
void     hal_spi_rx_abort(void);

/* ---- Tachometer: CT16B0, 1 MHz tick, capture P0.5 rising edge ------------- */
/** ISR must call Tach_OnCapture(captured 16-bit counter value). */
void     hal_tach_init(void);

/* ---- I2C0 master, 400 kHz, P1.2/P1.3 -------------------------------------- */
int      hal_i2c_init(void);
/** START, addr7<<1|W, ctrl byte, len data bytes, STOP. Bounded timeouts. */
int      hal_i2c_write(uint8_t addr7, uint8_t ctrl, const uint8_t *data, uint16_t len);

#endif /* HAL_H */
