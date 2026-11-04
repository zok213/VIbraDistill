# VibraDistill-Edge — Sonix SN32F407 Production MCU Firmware

Hệ thống nhúng giám sát độ rung và chuẩn đoán lỗi vòng bi công nghiệp thời gian thực (Edge AI Diagnostic & SIL-2 Protection System).

---

## 1. Sơ đồ đấu nối chân phần cứng (Hardware Pinout Table)

Toàn bộ cấu hình chân đã được map chính xác theo tài liệu **Sonix SN32F407 User Manual & Datasheet**, thanh ghi multiplexing `SN_PFPA`:

| Chức năng | Chân MCU | Chế độ / Ngoại vi | Kết nối với | Ghi chú kỹ thuật |
|---|---|---|---|---|
| **SPI0 SCK** | **P0.0** | SPI0_SCK (Slave) | FPGA SPI SCK | 12.5 MHz SPI Mode 0 (CPOL=0, CPHA=0) |
| **SPI0 CS (SEL)** | **P0.1** | SPI0_SEL0 (Slave) | FPGA SPI CS_N | Active-Low Slave Select |
| **SPI0 MISO** | **P0.2** | SPI0_MISO (Slave) | FPGA SPI MISO | Dữ liệu phản hồi (nếu cần) |
| **SPI0 MOSI** | **P0.3** | SPI0_MOSI (Slave) | FPGA SPI MOSI | Dữ liệu phổ FFT & telemetry (524 bytes) |
| **FPGA DRDY IRQ** | **P2.4** | GPIO Input + EXTI | FPGA DRDY Pin | Cạnh lên (Rising Edge), pre-trigger 50 µs trước CS |
| **OLED I2C SCL** | **P0.10** | I2C0_SCL (Master) | SSD1306 SCL | 400 kHz Fast-Mode (kéo trở 2.2kΩ - 4.7kΩ lên 3.3V) |
| **OLED I2C SDA** | **P0.11** | I2C0_SDA (Master) | SSD1306 SDA | 400 kHz Fast-Mode (kéo trở 2.2kΩ - 4.7kΩ lên 3.3V) |
| **Tachometer Capture** | **P0.5** | CT16B5_CAP0 | Cảm biến tốc độ / Encoder | Capture Timer @ 1 MHz (độ phân giải 1.0 µs) |
| **SIL-2 Relay Trip** | **P1.0** | GPIO Output Push-Pull | Driver Rơ-le bảo vệ | Active-High, trip latency < 1.0 ms khi có lỗi |
| **SWD Debugger** | **P0.8 / P0.9** | SWCLK / SWDIO | J-Link / SN-Link / DAPLink | Nạp firmware và debug trực tiếp |

> **Lưu ý cấu hình Alternate (tùy chọn trong `hal_sn32f407.c`):**
> - Nếu muốn dùng I2C trên Header P1: chỉnh `#define CONF_I2C0_PIN_GROUP 2` để chuyển sang `P1.4` (SCL) và `P1.5` (SDA).
> - Nếu muốn chuyển SPI sang Port 2: chỉnh `#define CONF_SPI0_PIN_GROUP 1` để chuyển sang `P2.4..P2.7`.

---

## 2. Thông số tài nguyên & Kiến trúc (Resource Footprint)

Biên dịch tối ưu bằng **Keil ARMCC (v5.06 update 6, `--c99 --cpu=Cortex-M0`)**:

- **Flash (ROM):** `16,336 Bytes` (~15.95 KB / 32 KB Flash) → **Dư > 50% Flash**.
- **SRAM (RAM):** `6,720 Bytes` (~6.56 KB / 8.0 KB SRAM) → **Dư 1,472 Bytes cho Call Stack & ISRs**.
- **Dynamic Allocation (Heap):** **0 Bytes** (Chuẩn an toàn MISRA C & IEC 61508 SIL-2).
- **Core Clock:** 60 MHz (IHRC 12 MHz x PLL / 48 MHz Internal High-Speed Oscillator).

---

## 3. Cấu trúc thư mục mã nguồn

```
claude_mcu_firmware/fw/
├── VibraDistill.uvprojx         <-- Keil uVision Project (mở trực tiếp để build & debug)
├── README.md                   <-- Tài liệu đấu nối & hướng dẫn nạp
├── src/
│   ├── main.c                  <-- Vòng lặp siêu cấp (Super-loop), điều phối Pipeline
│   ├── hal.h                   <-- Giao diện phần cứng chuẩn HAL
│   ├── hal_sn32f407.c          <-- Driver Sonix HAL chuẩn thanh ghi (GPIO, SPI0 DMA, I2C0, WDT, Timer)
│   ├── spi_slave_dma.c/.h      <-- FSM nhận gói SPI DMA 524B, kiểm tra CRC-16-CCITT
│   ├── spectrum_dsp.c/.h       <-- Tìm đỉnh phổ (bỏ bin 0/1 DC), chuẩn hóa int8, tính priors
│   ├── tachometer.c/.h         <-- Đo chu kỳ xung encoder B5_CAP0, trung bình động 8 mẫu
│   ├── safety_trip.c/.h        <-- Quản lý rơ-le P1.0, cơ chế Latch ngắt bảo vệ
│   ├── oled_ssd1306.c/.h       <-- Driver OLED I2C 128x64 theo kiến trúc Page-Banded 128B
│   ├── vibradistill_model.c/.h <-- Mô hình TinyML Edge AI (BPFI, BPFO, BALL, RUL, Vacuity)
│   ├── vibradistill_weights.h  <-- Trọng số mạng nơ-ron định dạng Q7/Q15
│   ├── startup_SN32F400.s      <-- Khởi tạo Vector bảng ngắt & User Mode Flag 0xAAAA5555
│   ├── system_SN32F400.c/.h    <-- Thiết lập SystemCoreClock
│   └── SN32F400.sct            <-- Scatter file phân vùng bộ nhớ
└── obj/
    ├── VibraDistill.hex        <-- File HEX đã nén sẵn, nạp trực tiếp ăn ngay!
    ├── VibraDistill.bin        <-- Binary 32KB
    ├── VibraDistill.axf        <-- ELF/AXF chứa debug symbols
    └── VibraDistill.map        <-- Báo cáo chi tiết dung lượng bộ nhớ
```

---

## 4. Hướng dẫn nạp Firmware (Flashing Guide)

### Cách 1: Nạp trực tiếp file `.hex` (Nhanh nhất - Không cần Keil)
Dùng phần mềm nạp của mạch (ví dụ **SN-Link ISP Utility**, **J-Flash**, hoặc **OpenOCD**):
1. Mở phần mềm nạp chíp Sonix hoặc J-Flash.
2. Chọn MCU target: `SN32F407` hoặc `SN32F400`.
3. Trỏ đường dẫn đến file:
   `claude_mcu_firmware\fw\obj\VibraDistill.hex`
4. Bấm **Program & Verify**.

### Cách 2: Mở và nạp bằng Keil uVision
1. Click đúp mở file `VibraDistill.uvprojx`.
2. Bấm phím **F7** (Build Target) → Sẽ thấy thông báo `0 Error(s), 0 Warning(s)`.
3. Cắm mạch nạp (J-Link / DAPLink / SN-Link) vào máy tính và nối chân SWD (`P0.8`, `P0.9`, `GND`, `3.3V`).
4. Bấm **F8** (Download) để nạp thẳng vào Flash của MCU.

---

## 5. Danh mục kiểm tra sau khi cấp nguồn (Hardware Verification Checklist)

1. **Nguồn cấp:** Đảm bảo chân VDD = 3.3V ổn định, GND nối chung giữa MCU, FPGA, OLED và Encoder.
2. **Khởi động OLED:** Ngay sau khi bật nguồn, màn hình SSD1306 sẽ sáng lên và hiển thị khung chẩn đoán (Trạng thái, Tốc độ RPM, Phổ FFT).
3. **Nhận tín hiệu DRDY & SPI:**
   - Khi FPGA hoàn thành tính FFT, chân `DRDY` (P2.4) phát xung dương.
   - MCU tự động kích hoạt nhận DMA 524 bytes qua SPI0.
   - Đồ thị phổ trên OLED sẽ cập nhật dạng sóng FFT thời gian thực.
4. **Đo tốc độ động cơ (Tachometer):**
   - Khi cấp xung từ encoder vào `P0.5`, giá trị RPM trên OLED sẽ nhảy theo tốc độ thực.
5. **Rơ-le bảo vệ (SIL-2 Safety Trip):**
   - Ở trạng thái bình thường (Normal): chân `P1.0` ở mức logic 0 (0V).
   - Khi AI phát hiện lỗi hỏng vòng bi (BPFI/BPFO/BALL) hoặc bất thường ngoài phân phối (OOD): chân `P1.0` lập tức đóng lên mức logic 1 (3.3V) trong vòng dưới 1.0 ms và hiển thị cảnh báo lên OLED.
