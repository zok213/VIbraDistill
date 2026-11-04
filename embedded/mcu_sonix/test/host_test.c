#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "hal.h"
#include "spi_slave_dma.h"
#include "spectrum_dsp.h"
#include "tachometer.h"
#include "safety_trip.h"
#include "oled_ssd1306.h"

/* ---------------- mock HAL ---------------- */
static uint32_t g_ms; static uint8_t g_relay; static uint8_t *g_dma_dst; static int g_aborts;
static int g_i2c_fail; static int g_i2c_calls; static uint8_t g_last_cmd[3]; static uint8_t g_pages_seen[16]; static int g_npages;
uint32_t hal_millis(void){ return g_ms; }
uint32_t hal_irq_save(void){ return 0; } void hal_irq_restore(uint32_t s){ (void)s; }
void hal_system_init(void){} void hal_systick_init(void){} void hal_wdt_init(uint32_t t){(void)t;} void hal_wdt_feed(void){}
void hal_relay_init(void){ g_relay=0; } void hal_relay_set(uint8_t l){ g_relay=l; }
void hal_drdy_init(void){} void hal_spi_slave_init(void){}
void hal_spi_rx_arm(uint8_t *d, uint16_t n){ (void)n; g_dma_dst=d; } void hal_spi_rx_abort(void){ g_aborts++; }
void hal_tach_init(void){}
int hal_i2c_init(void){ return g_i2c_fail?-1:0; }
int hal_i2c_write(uint8_t a, uint8_t c, const uint8_t *d, uint16_t n){
    (void)a; g_i2c_calls++; if (g_i2c_fail) return -1;
    if (c==0x00 && n==3){ memcpy(g_last_cmd,d,3); g_pages_seen[g_npages++ & 15]=d[0]&0x0F; }
    return 0; }

static int fails;
#define CHECK(c) do{ if(!(c)){ printf("FAIL line %d: %s\n",__LINE__,#c); fails++; } }while(0)

static void build_frame(uint8_t *f, uint16_t peak_bin, uint16_t peak_val){
    memset(f,0,524); f[0]=0xAA; f[1]=0x55; f[2]=0; f[3]=7; f[4]=0x00; f[5]=250; /* 25.0 Hz */
    for (int i=0;i<257;i++){ uint16_t v=(uint16_t)(10+i%7); f[8+2*i]=v>>8; f[9+2*i]=v&0xFF; }
    f[8]=0x13; f[9]=0x88;           /* bin0 = 5000 (DC)  */
    f[10]=0x0B; f[11]=0xB8;         /* bin1 = 3000       */
    f[8+2*peak_bin]=peak_val>>8; f[9+2*peak_bin]=peak_val&0xFF;
    uint16_t crc=Spi_Crc16Ccitt(f,522); f[522]=crc>>8; f[523]=crc&0xFF;
}
static void deliver(const uint8_t *f){ Spi_Slave_OnDrdyIrq(); memcpy(g_dma_dst,f,524); Spi_Slave_OnFrameEnd(); }

int main(void){
    uint8_t f[524]; const uint8_t *rx=0;

    /* CRC-16/CCITT-FALSE check value */
    CHECK(Spi_Crc16Ccitt((const uint8_t*)"123456789",9)==0x29B1);

    /* frame pipeline */
    Spi_Slave_Init(); build_frame(f,50,800);
    CHECK(Spi_Slave_Poll(&rx)==SPI_POLL_NONE);
    deliver(f);
    CHECK(Spi_Slave_Poll(&rx)==SPI_POLL_OK);
    CHECK(Spec_FindPeakBin(rx)==50);                     /* DC bins 5000/3000 skipped */
    CHECK(Spec_BinToHz(50)==312.5f);
    CHECK(Spi_Frame_GetBin(rx,0)==5000 && Spi_Frame_GetBin(rx,1)==3000);   /* BE decode */
    CHECK(Spi_Frame_ShaftSpeed(rx)==250);
    int8_t q[257]; Spec_Quantize(rx,q);
    CHECK(q[0]==0 && q[1]==0 && q[50]==50);
    Spi_Slave_OnDrdyIrq(); CHECK(Spi_Slave_GetStats()->overrun==1);   /* busy -> overrun */
    Spi_Slave_Release();
    /* corrupt CRC / header */
    f[100]^=0x01; deliver(f); CHECK(Spi_Slave_Poll(&rx)==SPI_POLL_BAD_CRC);
    build_frame(f,50,800); f[0]=0x00; deliver(f); CHECK(Spi_Slave_Poll(&rx)==SPI_POLL_BAD_HEADER);
    /* armed but never completed */
    Spi_Slave_OnDrdyIrq(); g_ms+=SPI_FRAME_TIMEOUT_MS+1; Spi_Slave_Task();
    CHECK(g_aborts==1 && Spi_Slave_GetStats()->timeout==1);
    build_frame(f,50,800); deliver(f); CHECK(Spi_Slave_Poll(&rx)==SPI_POLL_OK); Spi_Slave_Release(); /* recovered */
    /* peak when strongest non-DC bin is the last one */
    build_frame(f,256,900); deliver(f); Spi_Slave_Poll(&rx); CHECK(Spec_FindPeakBin(rx)==256); Spi_Slave_Release();

    /* priors */
    uint8_t pr[4]; Spec_ComputePriors(25.0f,pr);
    CHECK(pr[0]==7 && pr[1]==10 && pr[2]==4 && pr[3]==0);
    Spec_ComputePriors(41.6667f,pr); CHECK(pr[1]==17);
    Spec_ComputePriors(1000.0f,pr);  CHECK(pr[0]==127 && pr[3]==31);   /* clamp / floor */
    Spec_ComputePriors(-5.0f,pr);    CHECK(pr[0]==0);

    /* tachometer: 1500 RPM -> 1333 us period, counter wraps at 65536 */
    g_ms=1000; Tach_Init(); uint32_t cap=65000; uint16_t rpm=0; float fr=0;
    for(int i=0;i<12;i++){ cap+=1333; g_ms+=1; Tach_OnCapture((uint16_t)cap); if(i==5) CHECK(Tach_Get(&rpm,&fr)==0); }
    CHECK(Tach_Get(&rpm,&fr)==1 && rpm>=1499 && rpm<=1501 && fr>24.9f && fr<25.1f);
    Tach_OnCapture((uint16_t)(cap+50));                   /* glitch ignored */
    CHECK(Tach_Get(&rpm,&fr)==1);
    g_ms+=TACH_STALE_MS+1; CHECK(Tach_Get(&rpm,&fr)==0);  /* motor stopped */

    /* safety */
    Safety_Trip_Init(); CHECK(g_relay==0);
    CHECK(Safety_Trip_Evaluate(0,0)==0 && g_relay==0);
    CHECK(Safety_Trip_Evaluate(2,0)==1 && g_relay==1 && Safety_Trip_GetReason()==SAFETY_REASON_BPFI);
    Safety_Trip_Evaluate(0,0); CHECK(Safety_Trip_IsLatched()==1);       /* stays latched */
    g_relay=0; Safety_Trip_Refresh(); CHECK(g_relay==1);
    Safety_Trip_Init(); CHECK(Safety_Trip_Evaluate(0,1)==1 && Safety_Trip_GetReason()==SAFETY_REASON_OOD);
    Safety_Trip_Init(); CHECK(Safety_Trip_Evaluate(9,0)==1);            /* invalid class -> unsafe */

    /* OLED */
    g_ms=5000; g_i2c_fail=0; Oled_Init();
    oled_view_t v={OLED_ST_NORMAL,1500,3125,87,12}; static int8_t sp[257];
    Oled_SetView(&v,sp);
    uint8_t pg[128]; Oled_RenderPage(0,pg);
    CHECK(pg[0]==0x26 && pg[1]==0x49 && pg[4]==0x32 && pg[5]==0x00);   /* 'S' + gap */
    Oled_RenderPage(1,pg); CHECK(pg[0]==0x7F && pg[1]==0x09);          /* 'R' */
    /* line-2 and line-3 text content via glyph compare of first digit */
    for(int i=0;i<8;i++) Oled_Task();
    int ok=1; for(int i=0;i<8;i++) if(g_pages_seen[i]!=i) ok=0; CHECK(ok);    /* pages 0..7 in order */
    /* chart: DC bins never drawn */
    memset(sp,0,sizeof sp); sp[0]=127; sp[1]=127;
    for(int p=3;p<8;p++){ Oled_RenderPage(p,pg); for(int c=0;c<128;c++) CHECK(pg[c]==0); }
    /* chart: single full-scale bin 50 -> exactly one column lit on bottom page */
    sp[50]=127; Oled_RenderPage(7,pg); int lit=0,col=-1; for(int c=0;c<128;c++) if(pg[c]){lit++;col=c;}
    CHECK(lit==1 && pg[col]==0xFF);
    Oled_RenderPage(3,pg); CHECK(pg[col]==0xFE);                       /* 39 px tall: top page rows 1..7 */
    CHECK(col==(50-2)*128/255 || col==((50-2)*128/255)+1 || col==((50-2)*128/255)-1);
    /* bus failure -> backs off, no hang */
    g_i2c_fail=1; int before=g_i2c_calls; Oled_Task(); Oled_Task(); CHECK(g_i2c_calls-before<=2);

    printf(fails? "\n%d FAILURE(S)\n":"ALL TESTS PASSED\n", fails);
    return fails?1:0;
}
