/**
 * @file  hal_sn32f407.c
 * NOTE: Tat ca chuc nang HAL, SysTick, ngat P2.3 Encoder, SPI0 Slave DMA, OLED
 * da duoc tich hop truc tiep, dong bo va toi uu trong main.c (All-in-One architecture).
 * File nay duoc tam thoi vo hieu hoa de tranh loi trung lap ky hieu (Multiply defined) trong Keil MDK.
 */

#if 0 /* VO HIEU HOA TOAN BO DE KHONG BI TRUNG LAP SYMBOL VOI MAIN.C */

#include <stdint.h>
#include <string.h>
#include "hal.h"
#include "spi_slave_dma.h"
#include "tachometer.h"
#include "SN32F400.h"
#include "SN32F400_Def.h"

#define CORE_CLK_HZ          60000000UL
#define I2C_TIMEOUT_CYCLES   8000UL     /* ~1.5 ms timeout limit at 60 MHz */

/* ============================================================================
 * PIN CONFIGURATION SELECTION
 * ============================================================================
 * SPI0 Group Options on SN32F407:
 *   0: P0.0=SCK0, P0.1=SEL0, P0.2=MISO0, P0.3=MOSI0  (RECOMMENDED: 0 conflicts)
 *   1: P2.5=SCK0, P2.4=SEL0, P2.6=MISO0, P2.7=MOSI0
 *
 * I2C0 Group Options on SN32F407:
 *   0: P0.10=SCL0, P0.11=SDA0 (Standard Sonix EVB / Devboard)
 *   1: P1.1 =SCL0, P1.2 =SDA0
 *   2: P1.4 =SCL0, P1.5 =SDA0
 * ============================================================================ */
#ifndef CONF_SPI0_PIN_GROUP
#define CONF_SPI0_PIN_GROUP  2   /* Default: P0.0..P0.3 */
#endif

#ifndef CONF_I2C0_PIN_GROUP
#define CONF_I2C0_PIN_GROUP  0   /* Default: P0.10, P0.11 */
#endif

/* ----------------------------------------------------------------------------
 * 1. GENERIC CORTEX-M0 SYSTICK & PRIMASK
 * ---------------------------------------------------------------------------- */
static volatile uint32_t s_ms = 0;

void SysTick_Handler(void) 
{ 
    s_ms++; 
}

void hal_systick_init(void)
{
    *((volatile uint32_t *)0xE000E014UL) = (CORE_CLK_HZ / 1000UL) - 1UL; /* SYST_RVR */
    *((volatile uint32_t *)0xE000E018UL) = 0UL;                          /* SYST_CVR */
    *((volatile uint32_t *)0xE000E010UL) = 7UL; /* CLKSOURCE=core, TICKINT, ENABLE */
}

uint32_t hal_millis(void) 
{ 
    return s_ms; 
}

uint32_t hal_irq_save(void)
{
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    return primask;
}

void hal_irq_restore(uint32_t state) 
{ 
    __set_PRIMASK(state); 
}

/* ----------------------------------------------------------------------------
 * 2. SYSTEM CLOCKS & PIN MULTIPLEXING (PFPA)
 * ---------------------------------------------------------------------------- */
void hal_system_init(void)
{
    /* 1. Enable AHB Clocks for Required Peripherals:
     *    Bit 2:  DMA0
     *    Bit 5:  CT16B0
     *    Bit 10: CT16B5
     *    Bit 12: SPI0
     *    Bit 21: I2C0
     */
    SN_SYS1->AHBCLKEN |= (1UL << 2)  |   /* DMA0CLKEN   */
                         (1UL << 5)  |   /* CT16B0CLKEN */
                         (1UL << 10) |   /* CT16B5CLKEN */
                         (1UL << 12) |   /* SPI0CLKEN   */
                         (1UL << 21);    /* I2C0CLKEN   */

    /* 2. Configure Pin Function Multiplexing (PFPA): */
#if (CONF_SPI0_PIN_GROUP == 0)
    /* SCK0=P0.0, SEL0=P0.1, MISO0=P0.2, MOSI0=P0.3 */
    SN_PFPA->SPI0 = 0x00;
#elif (CONF_SPI0_PIN_GROUP == 1)
    /* SCK0=P2.5, SEL0=P2.4, MISO0=P2.6, MOSI0=P2.7 */
    SN_PFPA->SPI0 = (1 << 6) | (1 << 4) | (1 << 2) | (1 << 0);
#else
    /* Header J12 DB_SPI: SCK0=P1.0, SEL0=P1.8, MISO0=P1.1, MOSI0=P1.2 */
    SN_PFPA->SPI0 = (2 << 6) | (2 << 4) | (2 << 2) | (2 << 0); /* 0xAA */
#endif

#if (CONF_I2C0_PIN_GROUP == 0)
    /* SCL0=P0.10, SDA0=P0.11 */
    SN_PFPA->I2C0 = (2 << 2) | (2 << 0);
#elif (CONF_I2C0_PIN_GROUP == 1)
    /* SCL0=P1.1, SDA0=P1.2 */
    SN_PFPA->I2C0 = (3 << 2) | (3 << 0);
#else
    /* SCL0=P1.4, SDA0=P1.5 */
    SN_PFPA->I2C0 = (1 << 2) | (1 << 0);
#endif

    /* Tachometer: P0.5 is CT16B5_CAP0 */
}

/* ----------------------------------------------------------------------------
 * 3. WATCHDOG TIMER (SN_WDT) - HARDWARE RESET MODE
 * ---------------------------------------------------------------------------- */
void hal_wdt_init(uint32_t timeout_ms)
{
    uint32_t tc_val;
    (void)timeout_ms;
    
    /* ILRC clock ~32 kHz: TC=61 gives ~250 ms timeout */
    tc_val = 61;
    
    /* Key 0x5AFA required for writes to SN_WDT registers */
    SN_WDT->CFG  = (0x5AFA << 16) | 0x0001;          /* WDTEN=1, WDTIE=0 (Reset Mode) */
    SN_WDT->TC   = (0x5AFA << 16) | (tc_val & 0xFF); /* Reload constant */
    SN_WDT->FEED = (0x5AFA << 16) | 0x55AA;          /* Initial Feed */
}

void hal_wdt_feed(void)
{
    /* Atomic feed sequence */
    SN_WDT->FEED = (0x5AFA << 16) | 0x55AA;
}

/* ----------------------------------------------------------------------------
 * 4. SIL-2 SAFETY RELAY (P1.0)
 * ---------------------------------------------------------------------------- */
void hal_relay_init(void)
{
    /* Use P3.8 (EVK on-board LED0_P38 / LED-FAIL / Trip Output) to avoid collision with P1.0 (SCK0) */
    SN_GPIO3->BCLR = (1UL << 8);
    SN_GPIO3->CFG_b.CFG8   = 0; /* Push-pull */
    SN_GPIO3->MODE_b.MODE8 = 1; /* Output */
    SN_GPIO3->BCLR = (1UL << 8);
}

void hal_relay_set(uint8_t level)
{
    if (level != 0U) {
        SN_GPIO3->BSET = (1UL << 8); /* Level 1: TRIP / LED-FAIL ON */
    } else {
        SN_GPIO3->BCLR = (1UL << 8); /* Level 0: Safe / Normal */
    }
}

/* ----------------------------------------------------------------------------
 * 5. DRDY_IRQ EXTI INTERRUPT (P2.4 RISING EDGE)
 * ---------------------------------------------------------------------------- */
void hal_drdy_init(void)
{
    /* Configure P2.4 as Digital Input */
    SN_GPIO2->MODE_b.MODE4 = 0; /* Input */
    SN_GPIO2->CFG_b.CFG4   = 1; /* Pull-up/pull-down enabled */
    
    /* Configure P2.4 Interrupt: Edge-sensitive, Single Rising Edge */
    SN_GPIO2->IS_b.IS4   = 0; /* 0 = Edge sensitive */
    SN_GPIO2->IBS_b.IBS4 = 0; /* 0 = Single edge */
    SN_GPIO2->IEV_b.IEV4 = 1; /* 1 = Rising edge trigger */
    
    /* Clear pending flag */
    SN_GPIO2->IC = (1UL << 4);
    
    /* Enable interrupt in GPIO2 block */
    SN_GPIO2->IE_b.IE4 = 1;
    
    /* Configure NVIC for P2 interrupt: Priority 0 (Highest) */
    NVIC_ClearPendingIRQ(P2_IRQn);
    NVIC_SetPriority(P2_IRQn, 0);
    NVIC_EnableIRQ(P2_IRQn);
}

void P2_IRQHandler(void)
{
    /* Check if interrupt source is P2.4 */
    if (SN_GPIO2->RIS_b.IF4 != 0U) {
        SN_GPIO2->IC = (1UL << 4); /* Clear interrupt flag */
        Spi_Slave_OnDrdyIrq();     /* Notify SPI slave state machine */
    }
}

/* ----------------------------------------------------------------------------
 * 6. SPI0 SLAVE & DMA0 RECEIVER (12.5 MHz MODE 0)
 * ---------------------------------------------------------------------------- */

void hal_spi_slave_init(void)
{
    /* 1. Reset SPI0 FSM and FIFOs */
    SN_SPI0->CTRL0_b.FRESET = 3; /* Reset TX and RX FIFOs */
    
    /* 2. Configure SPI0 as Slave Mode 0:
     *    SPIEN  = 0 (enable after config)
     *    MS     = 1 (1 = Slave mode in SN32F400!)
     *    DL     = 7 (Data length = 7 + 1 = 8-bit)
     *    SELDIS = 1 (External SEL from FPGA)
     */
    SN_SPI0->CTRL0 = (1UL << 18) | /* SELDIS: External SEL */
                     (7UL << 8)  | /* DL: 8-bit data */
                     (1UL << 3);   /* MS: Slave mode */
                     
    /* 3. Mode 0: CPOL=0, CPHA=0, MSB first */
    SN_SPI0->CTRL1 = 0;
    
    /* 4. Disable SPI core interrupts (DMA is used) */
    SN_SPI0->IE = 0;
    NVIC_DisableIRQ(SPI0_IRQn);
    
    /* 5. Enable SPI0 peripheral */
    SN_SPI0->CTRL0_b.SPIEN = 1;
    
    /* 6. Configure DMA Channel 1 for SPI0 RX */
    /* C1_CFG:
     *   INT_TC_MSK = 0 (Transfer complete interrupt enabled)
     *   SRC_HE     = 1 (Peripheral mode)
     *   SRC_RS     = 3 (Request select = SPI0 RX)
     *   DST_RS     = 0 (Memory)
     */
    SN_DMA0->C1_CFG = (3UL << 16) | (1UL << 7);
    
    /* Enable DMA0 interrupt in NVIC */
    NVIC_ClearPendingIRQ(DMA0_IRQn);
    NVIC_SetPriority(DMA0_IRQn, 1);
    NVIC_EnableIRQ(DMA0_IRQn);
}

void hal_spi_rx_arm(uint8_t *dst, uint16_t len)
{
    /* Abort any previous DMA transfer on Channel 1 */
    SN_DMA0->C1_CSR_b.CH_EN = 0;
    
    /* Flush SPI RX FIFO */
    SN_SPI0->CTRL0_b.FRESET = 2; /* Reset RX FIFO */
    
    /* Setup DMA Channel 1:
     *   Source Address:      SN_SPI0->DATA (Fixed)
     *   Destination Address: dst (Incrementing)
     *   Total Transfer Size: len (524 bytes)
     */
    SN_DMA0->C1_SRCADDR = (uint32_t)&SN_SPI0->DATA;
    SN_DMA0->C1_DSTADDR = (uint32_t)dst;
    SN_DMA0->C1_SIZE    = len;
    
    /* C1_CSR:
     *   CH_EN       = 1 (Enable)
     *   DSTAD_CTL   = 1 (Increment)
     *   SRCAD_CTL   = 0 (Fixed)
     *   MODE        = 1 (Peripheral)
     *   DST_WIDTH   = 0 (8-bit)
     *   SRC_WIDTH   = 0 (8-bit)
     *   SRC_SIZE    = 2 (Burst 4)
     *   CHPRI       = 0 (Priority Level 0)
     */
    SN_DMA0->C1_CSR = (2UL << 16) | (1UL << 7) | (1UL << 3) | (1UL << 0);
    
    /* Trigger SPI0 RX DMA */
    SN_SPI0->DMA = (1UL << 30) | len; /* RX_DMA_EN=1, DMA_SIZE=len */
}

void hal_spi_rx_abort(void)
{
    SN_DMA0->C1_CSR_b.CH_EN = 0;
    SN_SPI0->DMA            = 0;
    SN_SPI0->CTRL0_b.FRESET = 2; /* Flush RX FIFO */
}

void DMA_IRQHandler(void)
{
    /* Check Channel 1 Transfer Complete Flag */
    if (SN_DMA0->INT_TC_b.INT_TC1 != 0U) {
        SN_DMA0->INT_TC_CLR = (1UL << 1); /* Clear TC1 flag */
        
        /* Disable SPI DMA mode */
        SN_SPI0->DMA = 0;
        
        /* Notify SPI Slave driver that complete 524-byte packet has arrived */
        Spi_Slave_OnFrameEnd();
    }
    
    /* Check Abort flag */
    if (SN_DMA0->INT_ABT_b.INT_ABT1 != 0U) {
        SN_DMA0->INT_ABT_CLR = (1UL << 1); /* Clear ABT1 flag */
    }
}

void DMA0_IRQHandler(void)
{
    DMA_IRQHandler();
}

/* ----------------------------------------------------------------------------
 * 7. TACHOMETER INPUT CAPTURE (P0.5 / CT16B5_CAP0 @ 1 MHz)
 * ---------------------------------------------------------------------------- */
void hal_tach_init(void)
{
    /* 1. Configure P0.5 as Input */
    SN_GPIO0->MODE_b.MODE5 = 0;
    
    /* 2. Configure 16-bit Timer CT16B5:
     *    Timer Clock = 60 MHz.
     *    Prescaler = 59 -> Counter clock = 60 MHz / (59 + 1) = 1.0 MHz (1 us tick).
     */
    SN_CT16B5->PRE = (CORE_CLK_HZ / 1000000UL) - 1UL;
    
    /* 3. Configure Capture Control:
     *    Bit 0: CAP0RE = 1 (Capture on rising edge)
     *    Bit 2: CAP0IE = 1 (Interrupt enable)
     *    Bit 3: CAP0EN = 1 (Capture channel enable)
     */
    SN_CT16B5->CAPCTRL = (1UL << 3) | (1UL << 2) | (1UL << 0);
    
    /* 4. Enable Counter */
    SN_CT16B5->TMRCTRL = 1; /* CEN=1 */
    
    /* 5. Configure NVIC for CT16B5 */
    NVIC_ClearPendingIRQ(CT16B5_IRQn);
    NVIC_SetPriority(CT16B5_IRQn, 1);
    NVIC_EnableIRQ(CT16B5_IRQn);
}

void CT16B5_IRQHandler(void)
{
    /* Read 16-bit captured counter value */
    uint16_t cap_val = (uint16_t)SN_CT16B5->CAP0;
    
    /* Clear Capture interrupt flag (write 1 to clear) */
    SN_CT16B5->IC = 0xFF;
    
    /* Deliver raw timestamp to tachometer moving-average engine */
    Tach_OnCapture(cap_val);
}

/* ----------------------------------------------------------------------------
 * 8. I2C0 MASTER FAST-MODE (400 kHz) FOR SSD1306 OLED
 * ---------------------------------------------------------------------------- */
int hal_i2c_init(void)
{
    /* Clock: 60 MHz. Period for 400 kHz = 2.5 us = 150 cycles.
     * High time = 75 cycles, Low time = 75 cycles.
     */
    SN_I2C0->SCLHT = 74;
    SN_I2C0->SCLLT = 74;
    
    /* Enable I2C0 Interface */
    SN_I2C0->CTRL_b.I2CEN = 1;
    
    return 0;
}

static int i2c_wait_stat(uint32_t mask, uint32_t expected)
{
    uint32_t timeout = I2C_TIMEOUT_CYCLES;
    while ((SN_I2C0->STAT & mask) != expected) {
        if (--timeout == 0U) {
            return -1; /* Timeout */
        }
    }
    return 0;
}

int hal_i2c_write(uint8_t addr7, uint8_t ctrl, const uint8_t *data, uint16_t len)
{
    uint16_t i;
    
    /* 1. Generate START Condition */
    SN_I2C0->CTRL_b.STA = 1;
    if (i2c_wait_stat(0x10, 0x10) != 0) { /* START_DN = bit 4 */
        SN_I2C0->CTRL_b.STO = 1;
        return -1;
    }
    
    /* 2. Send 7-bit Slave Address + Write (0) */
    SN_I2C0->TXDATA = (uint32_t)(addr7 << 1);
    if (i2c_wait_stat(0x02, 0x02) != 0) { /* ACK_STAT = bit 1 */
        SN_I2C0->CTRL_b.STO = 1;
        return -2;
    }
    
    /* 3. Send Control Byte (0x00 for Command, 0x40 for Data) */
    SN_I2C0->TXDATA = (uint32_t)ctrl;
    if (i2c_wait_stat(0x02, 0x02) != 0) {
        SN_I2C0->CTRL_b.STO = 1;
        return -3;
    }
    
    /* 4. Stream Data Payload */
    for (i = 0; i < len; i++) {
        SN_I2C0->TXDATA = (uint32_t)data[i];
        if (i2c_wait_stat(0x02, 0x02) != 0) {
            SN_I2C0->CTRL_b.STO = 1;
            return -4;
        }
    }
    
    /* 5. Generate STOP Condition */
    SN_I2C0->CTRL_b.STO = 1;
    (void)i2c_wait_stat(0x08, 0x08); /* STOP_DN = bit 3 */
    
    return 0;
}

#endif /* #if 0 VO HIEU HOA DE TRANH LỖI TRÙNG LẶP SYMBOL */

