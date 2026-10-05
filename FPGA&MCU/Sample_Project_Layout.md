# MẪU ĐĂNG KÝ ĐỀ TÀI VÒNG CHUNG KẾT
# CUỘC THI THIẾT KẾ FPGA VÀ MCU MỞ RỘNG KHU VỰC MIỀN TRUNG 2026

---

## I. THÔNG TIN CHUNG

* **Tên đội thi:** Team PORYGON
* **Trường / Viện:** Trường Đại học Bách Khoa – Đại học Đà Nẵng, Trường Đại học Sư Phạm – Đại học Đà Nẵng, Trường Đại học FPT Đà Nẵng
* **Tên đề tài:** **Hệ thống Chuẩn đoán Lỗi Ổ lăn & Ước lượng Tuổi thọ RUL phối hợp Vi mạch Tăng tốc AI trên FPGA Gowin và Vi điều khiển Giám sát An toàn Sonix SN32F407.**  
  *(VibraDistill-Edge: Trustworthy Bearing Fault Diagnosis & Adaptive Conformal RUL Estimation via FPGA-Accelerated Streaming DSP-NPU SoC and Resilient Sonix MCU Safety Supervisor)*
* **Lĩnh vực đăng ký:** Thiết kế Vi mạch, Bán dẫn & Đồng thiết kế Hệ thống Nhúng Thông minh (AI-Hardware Co-Design)
* **Trưởng nhóm:**
  * Họ và tên: **Ngô Trần Vinh Quang**
  * Số điện thoại: **0395259848**
  * Email: **quangngotranvinh@gmail.com**
* **Thành viên đội thi & Phân công chuyên môn:**
  1. `Ngô Trần Vinh Quang` - **Trưởng nhóm & Kiến trúc sư Trưởng:** Quy hoạch phân tầng phần cứng FPGA-MCU, thiết kế giao thức bus SPI DMA, tối ưu hóa PPA và chỉ đạo kiểm thử hệ thống.
  2. `Hồ Công Bảo Toàn` - **Chuyên trách Vi mạch FPGA & Lõi NPU:** Hiện thực RTL Verilog bộ giải điều chế bao hình IIR, FFT 512-pt, và thiết kế mảng nhân phần cứng 12-way INT8 NPU MAC Engine trên Gowin Primer 20K.
  3. `Đặng Phúc Thiện` - **Chuyên trách AI & Thuật toán Tin cậy:** Huấn luyện mạng Teacher, chưng cất tri thức DKD (tau=5.0, beta=2.0), lượng tử hóa INT8 PTQ, và xây dựng thuật toán Bounded-Delay Conformal ACP Q16.16.
  4. `Mai Phước Minh Tài` - **Chuyên trách Firmware MCU & An toàn Hệ thống:** Phát triển firmware Keil MDK cho Sonix SN32F407, lập trình driver SPI DMA, thuật toán ACP fixed-point, cơ chế Dual-Watchdog và giao thức LoRaWAN / RS-485.
  5. `Trần Quốc Kiệt` - **Chuyên trách Đo kiểm PPA & Đóng gói Sản phẩm:** Thiết kế mạch nguồn công nghiệp, đo kiểm trễ và dòng tiêu thụ bằng dao động ký, tích hợp cảm biến ST IIS3DWB và gia công cơ khí vỏ hộp Smart Sensor Pod.

---

## II. TỔNG QUAN GIẢI PHÁP & MỤC TIÊU

### 1. Đặt vấn đề & Động lực nghiên cứu (Problem Statement & Motivation)
Trong các dây chuyền công nghiệp nặng (tuabin điện gió, động cơ kéo đầu máy xe lửa, trục chính máy CNC cao tốc), sự cố cơ khí liên quan đến ổ lăn (rolling element bearings) chiếm từ **40% đến 50%** tổng thời gian dừng máy ngoài kế hoạch, gây thiệt hại hàng trăm triệu đồng mỗi giờ dừng dây chuyền.
* **Hạn chế của giải pháp truyền thống:**
  1. Các thiết bị đo rung động công nghiệp hiện nay chủ yếu là cảm biến "ngu" (dumb sensors), truyền toàn bộ luồng dữ liệu thô về máy chủ đám mây, gây nghẽn băng thông, trễ cao và phụ thuộc đường truyền mạng.
  2. Các mô hình học sâu (Deep Learning) chạy trên máy tính công nghiệp tiêu tốn công suất lớn (> 15W), giá thành đắt đỏ, không thể nuôi pin và không thể gắn trực tiếp tại gối đỡ ổ bi.
  3. Khi triển khai mô hình nơ-ron lên vi điều khiển giá rẻ, bộ nhớ SRAM hạn hẹp (< 10 KB) và năng lực tính toán yếu của lõi Cortex-M0 khiến việc chạy AI trực tiếp trên MCU trở thành bất khả thi hoặc gây quá tải bộ nhớ làm sập hệ thống.

### 2. Mục tiêu đề tài & Triết lý Đồng Thiết kế (Co-Design Philosophy)
Đề tài VibraDistill-Edge giải quyết triệt để nút thắt cổ chai trên bằng kiến trúc **Đồng thiết kế Bán dẫn & Vi điều khiển Bất đối xứng (Asymmetric Heterogeneous Co-Design)**:

```
+─────────────────────────────────────────+        +─────────────────────────────────────────+
|     GOWIN PRIMER 20K FPGA ENGINE        |        |       SONIX SN32F407 MCU SUPERVISOR     |
|   (Tính toán Song song & Gia tốc NPU)   |        |    (Quản trị An toàn & Độ tin cậy)      |
|  • Polyphase Decimator /2 @ 13.333 kHz  |        |  • Nhận gói tin trạng thái 16 Bytes SPI |
|  • Lọc FIR pha tối thiểu 32-tap causal  |        |  • Thuật toán Conformal ACP Q16.16      |
|  • Giải điều chế bao hình IIR (0 CORDIC)|        |  • Giám sát Watchdog & Reset FPGA       |
|  • 512-pt FFT + Xấp xỉ Alpha-Beta       |  ────► |  • Ngắt khẩn cấp Motor Relay Interlock  |
|  • Lõi phần cứng NPU INT8 12-way MAC    | 16 B   |  • OLED 0.96" Page-Banding (128 B RAM)  |
|  • Suy luận hoàn tất trong 0.40 ms      | 32 µs  |  • Truyền thông không dây LoRaWAN / 485 |
|  • Chiếm 30.6% LUT, 37.0% BRAM, 56.3% DSP|       |  • SRAM: 3.04 KB / 8.00 KB (Headroom 63%)|
+─────────────────────────────────────────+        +─────────────────────────────────────────+
```

* **5 Đột phá công nghệ cốt lõi:**
  1. **All-in-One Hardware DSP & NPU SoC trên Gowin Primer 20K:** Toàn bộ chuỗi xử lý từ thu thập rung động 26.667 kHz, hạ tần số 13.333 kHz, lọc FIR, FFT 512-pt đến **suy luận mạng nơ-ron VibraDistillMicro (8.677 tham số INT8)** được thực thi hoàn toàn trong nội bộ FPGA qua mảng nhân song song 12-way `DSP18E`. Dữ liệu phổ sau FFT được nạp thẳng vào NPU qua BRAM, loại bỏ 100% độ trễ truyền dữ liệu phổ liên vi mạch.
  2. **Chuyển giao tri thức chưng cất tách rời (DKD):** Mạng Student siêu nhẹ (8.677 tham số) học tri thức hình học từ mạng Teacher ResNet thông qua hàm mất mát DKD với chuẩn hóa gradient $\tau^2 = 25.0$, đạt độ chính xác tương đương mô hình máy chủ ($F_1 \ge 0.985$).
  3. **Tích hợp tri thức động học vật lý (Physics-Informed Prior):** Tần số quay $f_r$ được bám vết thời gian thực, tự động tính toán 4 tần số lỗi đặc trưng ($f_\text{BPFO}, f_\text{BPFI}, f_\text{BSF}, f_\text{FTF}$) và cân bằng biên độ (amplitude scaling $127$) trước khi hợp nhất vào lớp Dense.
  4. **Định lượng độ mù mờ nhận thức Dirichlet (EDL):** Mạng nơ-ron tự lượng giá độ tin cậy thông qua độ mù mờ nhận thức (Vacuity $u = K/S$). Khi gặp tín hiệu rung động bất thường ngoài phân phối huấn luyện (OOD), hệ thống tự kích hoạt cảnh báo nguy hiểm thay vì đưa ra chẩn đoán sai.
  5. **Bảo chứng toán học tuổi thọ RUL (Adaptive Conformal Prediction - ACP):** Thuật toán thích nghi Bounded-Delay ACP được tối ưu hóa số nguyên cố định Q16.16 chạy trên Sonix SN32F407 Cortex-M0, cung cấp khoảng dự báo RUL $[\hat{y} - q_t, \hat{y} + q_t]$ với độ bao phủ toán học cam kết $\ge 90\%$ ngay cả khi ổ bi bước vào giai đoạn phá hủy phi tuyến tính.

---

## III. CẤU HÌNH PHẦN CỨNG & CHIẾN LƯỢC ĐỐI CHUẨN VI MẠCH (HARDWARE ARCHITECTURE)

### 1. Chiến lược Phối hợp Phần cứng Bán dẫn: Primer 20K + Sonix SN32F407
* **[x] Phối hợp FPGA Gowin + MCU Sonix (Hybrid System):**
  * **Bo mạch xử lý chính & Tăng tốc AI:** **Gowin Primer 20K (GW2A-LV18PG256C8/I7)** tích hợp $20.736$ LUT4, $46$ khối BSRAM và $48$ bộ nhân DSP18E.
  * **Bo mạch giám sát an toàn & Truyền thông:** **Sonix SN32F407 Starter Kit (ARM Cortex-M0 @ 60 MHz, 32 KB Flash, 8 KB SRAM)** (đã mượn từ Ban Tổ Chức).
  * **Tính kế thừa & Mở rộng:** Kiến trúc phân tầng module hóa cho phép chạy linh hoạt: phiên bản đơn kênh tối giản hoặc mở rộng giám sát đồng thời 4 đến 8 ổ bi trên Primer 20K.

### 2. Dự toán tài nguyên vi mạch Gowin FPGA (Primer 20K GW2A-18)

| Phân hệ RTL trên FPGA | LUT4 Logic (20,736 Max) | BSRAM 18K (46 Max) | DSP18E (48 Max) | Vai trò chức năng & Tối ưu hóa |
| :--- | :--- | :--- | :--- | :--- |
| **ST IIS3DWB SPI Master + Decimator /2** | ~280 (1.4%) | 0 (0.0%) | 1 (2.1%) | Đọc mẫu 26.667 kHz, hạ về $f_s = 13.333\,\text{kHz}$ |
| **Ping-Pong Buffer & FIR 32-tap** | ~450 (2.2%) | 1 (2.2%) | 4 (8.3%) | 4 bộ nhân folded min-phase FIR, trễ nhóm 1.33 ms |
| **IIR Rectifier Demod + DC Notch** | ~180 (0.9%) | 0 (0.0%) | 0 (0.0%) | Chỉnh lưu $|x| +$ lọc IIR shift-add (0 DSP, 0 CORDIC) |
| **Gowin 512-pt FFT Core + Hann ROM** | ~1,200 (5.8%) | 4 (8.7%) | 4 (8.3%) | FFT Radix-2 DIT thực + xấp xỉ Alpha-Beta |
| **Kinematic Prior Peak Tracker** | ~320 (1.5%) | 1 (2.2%) | 0 (0.0%) | Bám vết tốc độ quay trục, xuất mặt nạ 4-bit |
| **CDC & Shared Spectral BRAM** | ~120 (0.6%) | 1 (2.2%) | 0 (0.0%) | BRAM SDPB chuyển miền xung nhịp 50 MHz $\to$ 100 MHz |
| **12-Way INT8 NPU MAC Engine** | ~2,400 (11.6%) | 0 (0.0%) | 12 (25.0%) | Mảng 12 PE tính toán song song @ 100 MHz |
| **Requantization / Scale Units** | ~400 (1.9%) | 0 (0.0%) | 6 (12.5%) | Bộ nhân chỉnh tỷ lệ INT32 sang INT8 |
| **6-Bank Weight & Bias ROM** | ~150 (0.7%) | 6 (13.0%) | 0 (0.0%) | 6 bank x 16-bit = 96 bits/chu kỳ, không xung đột |
| **Activation Ping-Pong BRAM** | ~120 (0.6%) | 4 (8.7%) | 0 (0.0%) | 4 KB Ping + 4 KB Pong chứa 3.072 bytes Stage 1 |
| **NPU FSM Controller & Addr Gen** | ~520 (2.5%) | 0 (0.0%) | 0 (0.0%) | Điều phối chuỗi tầng mạng nơ-ron 2-cycle read latency |
| **SPI Slave DMA Packetizer (16B)** | ~210 (1.0%) | 0 (0.0%) | 0 (0.0%) | Tạo gói tin 16 byte CRC16, guardband 25 µs |
| **TỔNG TÀI NGUYÊN SỬ DỤNG** | **~6,350 / 20,736 (30.6%)**| **17 / 46 (37.0%)** | **27 / 48 (56.3%)**| **Đạt 100% Timing Closure ở 100 MHz, dư dả an toàn** |

---

### 3. Danh sách Thiết bị Ngoại vi & Cổng Giao tiếp

| Thiết bị / Ngoại vi | Chuẩn giao tiếp | Kết nối với | Điện áp | Dòng tiêu thụ | Vai trò chức năng |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ST IIS3DWB** (Gia tốc 3 trục) | SPI Master (Mode 3, SCK 6 MHz) | Gowin FPGA | 3.3V | 1.1 mA | Thu thập rung động $26.667\,\text{kHz}$, băng thông 6 kHz |
| **Bus liên vi mạch (Inter-chip)** | SPI 4.0 MHz + GPIO `ALERT_INT` | FPGA $\to$ MCU | 3.3V | 1.2 mA | Truyền gói tin kết quả 16 Bytes (32 µs/khung) |
| **Tín hiệu an toàn Heartbeat** | GPIO `FPGA_HEARTBEAT` | FPGA $\to$ MCU | 3.3V | < 0.1 mA | Xung nhịp 100 ms kiểm tra liveness của FPGA |
| **Tín hiệu Reset nóng nCONFIG** | GPIO `nCONFIG` | MCU $\to$ FPGA | 3.3V | < 0.1 mA | MCU kéo chân reload bitstream khi FPGA treo |
| **Relay bảo vệ Motor Interlock**| GPIO Output (Transistor drive) | MCU $\to$ Relay | 3.3V / 5V| 25.0 mA | Tự động ngắt biến tần động cơ khi có sự cố nặng |
| **Màn hình OLED 0.96"** | I2C Fast-Mode 400 kHz (SSD1306) | Sonix MCU | 3.3V | 15.0 mA | Hiển thị trạng thái lỗi, RUL và độ mù mờ vacuity |
| **Module LoRaWAN** | UART 115200 bps (E22-900T22S) | Sonix MCU | 3.3V | 45 mA TX | Truyền dữ liệu cảnh báo không dây tầm xa về SCADA |
| **Giao tiếp RS-485 Modbus RTU** | UART 115200 bps (MAX485/SP3485) | Sonix MCU | 3.3V / 5V| 18.0 mA | Cổng truyền thông dây công nghiệp tiêu chuẩn PLC |

---

### 4. Đề nghị Ban Tổ Chức Hỗ Trợ Thiết Bị (Hardware Loan Request)
1. **01 Bo mạch FPGA Gowin Primer 20K (GW2A-LV18)** kèm cáp nạp USB JTAG Programmer chính hãng Gowin.
2. **01 Bo mạch vi điều khiển Sonix SN32F407 Starter Kit kèm mạch nạp SN-LINK** (nhóm đã tiếp nhận mượn từ BTC, cam kết sử dụng hiệu quả).
3. **01 Module cảm biến gia tốc công nghiệp STMicroelectronics IIS3DWB** (hoặc module tương đương có băng thông $\ge 5\,\text{kHz}$).
4. **01 Màn hình OLED 0.96 inch I2C (SSD1306)** và module truyền thông LoRa / RS485.

---

## IV. PHÂN CHIA KIẾN TRÚC PHẦN MỀM & RTL (SOFTWARE & RTL ARCHITECTURE)

### 1. Phân định nhiệm vụ xử lý (Task Allocation) & Dòng thời gian trễ (Latency Timeline)
Chu kỳ phân tích khung rung động ($512$ mẫu ở $f_s = 13.333,33\,\text{Hz}$) là:
$$T_\text{frame} = \frac{512}{13.333,33} = \mathbf{38.40\,\text{ms}}$$

Toàn bộ chuỗi xử lý đầu-cuối hoàn tất chỉ trong **$2.10\,\text{ms}$**:
* **Giai đoạn 1 — FPGA DSP Pipeline (50 MHz):** $1.33\,\text{ms}$ (Trễ nhóm FIR 32-tap) $+ 0.085\,\text{ms}$ (FFT 512-pt Radix-2) $= \mathbf{1.415\,\text{ms}}$.
* **Giai đoạn 2 — Lõi FPGA INT8 NPU Core (100 MHz):** $\mathbf{0.400\,\text{ms}}$ ($40.000$ chu kỳ mảng 12 MAC tính toán toàn bộ mạng nơ-ron).
* **Giai đoạn 3 — Giao tiếp SPI DMA (4.0 MHz):** $\mathbf{0.032\,\text{ms}}$ ($16\,\text{bytes} \times 8 / 4\,\text{MHz}$).
* **Giai đoạn 4 — Sonix SN32F407 Conformal ACP & Logic (60 MHz):** $\mathbf{0.250\,\text{ms}}$ (Cập nhật ACP fixed-point, kiểm tra ngưỡng lỗi).
* **Tổng thời gian tích cực (Active Time):** $1.415 + 0.400 + 0.032 + 0.250 = \mathbf{2.097\,\text{ms}} \approx \mathbf{2.10\,\text{ms}} \ll 38.40\,\text{ms}$.
* **Thời gian ngủ sâu tiết kiệm năng lượng (WFI Sleep):** $\mathbf{36.30\,\text{ms}}$ (Chiếm **$94.5\%$ chu kỳ khung**), đưa công suất tiêu thụ trung bình toàn hệ thống xuống dưới **$85\,\text{mW}$**!

---

### 2. Phân định Trách nhiệm Vi mạch (Gowin FPGA RTL SoC)
1. **Khối Polyphase Decimator /2:** Hạ tần số cố định $26.667\,\text{kHz}$ của IIS3DWB về $13.333\,\text{kHz}$ bằng bộ lọc nửa băng 16-tap (chặn dải $> 60\,\text{dB}$).
2. **Khối Lọc FIR Pha Tối thiểu 32-tap:** Rút ngắn 50% trễ nhóm so với FIR pha tuyến tính truyền thống (từ $2.63\,\text{ms}$ xuống $1.33\,\text{ms}$), cô lập dải cộng hưởng khuyết tật $2 - 5\,\text{kHz}$.
3. **Khối Giải điều chế Bao hình IIR Causal (0 CORDIC):** Thay thế biến đổi Hilbert CORDIC nặng nề bằng mạch tách sóng trị tuyệt đối $|x[n]|$ và bộ lọc thông thấp IIR bậc 2 ($f_c = 1\,\text{kHz}$), tiết kiệm $> 65\%$ cổng logic.
4. **Khối 512-pt FFT & Xấp xỉ Phổ Alpha-Beta:** Lõi Gowin FFT IP Radix-2 kết hợp xấp xỉ biên độ $|X| \approx \max(|I|, |Q|) + \frac{3}{8}\min(|I|, |Q|)$ bằng 2 phép dịch bit (sai số $< 2.84\%$, triệt tiêu $100\%$ bộ chia và căn bậc hai phần cứng).
5. **Lõi Tăng tốc Phần cứng NPU INT8:** Mảng 12 PE nhân-tích lũy song song trên `DSP18E`, tích hợp 6 bank BSRAM ROM lưu trữ trọng số và 4 bank Activation RAM, tính toán trực tiếp các tầng Conv1D đa tỷ lệ, hợp nhất đặc trưng động học vật lý và xuất kết quả phân loại + tuổi thọ RUL.

---

### 3. Phân định Trách nhiệm Vi điều khiển (Sonix SN32F407 Safety Supervisor)
Vi điều khiển Sonix SN32F407 (ARM Cortex-M0 @ 60 MHz, 32 KB Flash, 8 KB SRAM) đảm nhiệm vai trò **Bộ điều khiển Giám sát An toàn (Safety Host Supervisor)**:

```
+─────────────────────────────────────────────────────────────────────────────+
|               SONIX SN32F407 SRAM MAP (8,192 BYTES PHYSICAL LIMIT)          |
+─────────────────────────────────────────────────────────────────────────────+
|  [0x2000_0000 - 0x2000_001F]  SPI Ping-Pong DMA Buffer (32 B)               |
|  [0x2000_0020 - 0x2000_005F]  Conformal ACP Q16.16 State & Moving Avg (64 B)|
|  [0x2000_0060 - 0x2000_015F]  UART Telemetry Ring Buffer (256 B)            |
|  [0x2000_0160 - 0x2000_01DF]  OLED SSD1306 Page Buffer (128 B)             |
|  [0x2000_01E0 - 0x2000_03DF]  System Globals, Flags & BSS Variables (512 B) |
|  [0x2000_03E0 - 0x2000_17FF]  VERIFIED UNALLOCATED SAFETY HEADROOM (5,152 B)|
|  [0x2000_1800 - 0x2000_1FFF]  DEDICATED STACK (2,048 B, Downward Growing)   |
+─────────────────────────────────────────────────────────────────────────────+
```

1. **Thuật toán Bounded-Delay Conformal ACP Số nguyên Cố định (Q16.16):**
   * Hoạt động không cần số thực: bước nhảy cập nhật $\Delta q$ chỉ nhận 2 hằng số $+2.949\,\text{counts}$ (khi vi phạm khoảng) và $-328\,\text{counts}$ (khi nằm trong khoảng).
   * Thực thi trong $< 12$ chu kỳ xung nhịp CPU ($< 0.20\,\mu\text{s}$), đảm bảo độ bao phủ tin cậy đạt chuẩn $90.0\%$ chính xác tuyệt đối.
2. **Kỹ thuật Hiển thị OLED Single-Page Banding (128 Bytes):**
   * Thay vì chiếm $1.024\,\text{bytes}$ SRAM và nghẽn bus I2C trong $26\,\text{ms}$, driver chỉ cấp $128\,\text{bytes}$ cho 1 trang hiển thị, truyền dữ liệu theo luồng ngắt không chặn $2.88\,\text{ms}$, tiết kiệm $896\,\text{bytes}$ RAM quý giá.
3. **Cơ chế Giám sát Kép Dual-Watchdog & Heartbeat:**
   * Watchdog độc lập bên trong MCU chống treo firmware.
   * Chân giám sát `FPGA_HEARTBEAT` kích hoạt kéo chân `nCONFIG` để nạp lại bitstream phần cứng cho FPGA trong vòng vài mili-giây nếu phát hiện nhiễu công nghiệp làm FPGA dừng hoạt động.

---

### 4. Giao thức Truyền thông Liên vi mạch (Inter-Chip 16-Byte SPI Protocol)

| Byte Offset | Tên trường | Kiểu dữ liệu | Scaling / Đơn vị | Chức năng an toàn & Giải nghĩa |
| :--- | :--- | :--- | :--- | :--- |
| **0x00 – 0x01** | `SYNC_WORD` | `uint16_t` | Hằng số `0x55AA` | Nhận diện đầu khung, chống lệch byte |
| **0x02 – 0x03** | `FRAME_ID` | `uint16_t` | Đếm $0 - 65.535$ | Số thứ tự khung tăng dần (phát hiện mất mẫu) |
| **0x04** | `FAULT_CLASS` | `uint8_t` | Enum $0 - 3$ | 0: Normal, 1: Ball, 2: Inner Race, 3: Outer Race |
| **0x05** | `CONFIDENCE` | `uint8_t` | $0 - 100\%$ ($1\,\%/\text{LSB}$) | Xác suất Dirichlet tin cậy $p_k = \alpha_k / S$ |
| **0x06 – 0x07** | `VACUITY_U` | `uint16_t` | Q1.15 ($0 - 32.768$) | Độ mù mờ Dirichlet $u = K/S$. Báo OOD nếu $u > 14.746$ |
| **0x08 – 0x09** | `RUL_RAW` | `uint16_t` | $0.1\,\text{giờ/LSB}$ | Điểm ước lượng RUL thô xuất trực tiếp từ NPU FPGA |
| **0x0A – 0x0B** | `KINEMATIC_MASK`| `uint16_t` | Bitfield | Trạng thái bắt đỉnh hài động học ($f_\text{BPFO}, f_\text{BPFI},...$) |
| **0x0C – 0x0D** | `STATUS_FLAGS` | `uint16_t` | Bitfield | Trạng thái cảm biến, cờ khoá PLL, cảnh báo nhiệt độ |
| **0x0E – 0x0F** | `CRC16_CCITT` | `uint16_t` | Đa thức `0x1021` | Mã kiểm tra toàn vẹn gói tin phần cứng |

---

## V. KẾ HOẠCH TRIỂN KHAI & TIẾN ĐỘ 5 TUẦN (MILESTONES)

* **Tuần 1 — RTL DSP & Kiến trúc NPU Core trên Gowin Primer 20K:**
  * Thiết kế Verilog bộ lọc nửa băng Decimator /2 ($13.333\,\text{kHz}$), FIR 32-tap folded, IIR envelope demodulator.
  * Thiết kế mảng 12 PE nhân-tích lũy NPU phần cứng bằng khối Gowin `DSP18E` (dùng synchronous reset).
  * Mô phỏng ModelSim kiểm tra độ khớp bit so với vector mẫu Python.  
  $	o$ *Sản phẩm:* Hoàn thành testbench RTL DSP và NPU Core, đạt Timing Closure ở 50 MHz (DSP) và 100 MHz (NPU).
* **Tuần 2 — Chưng cất DKD, Lượng tử hóa & Nạp BRAM ROM:**
  * Huấn luyện mạng Teacher, chưng cất DKD ($\tau=5.0, \beta=2.0$) trên dữ liệu rung động CWRU/MFPT được resample chuẩn hóa về $13.333\,\text{kHz}$.
  * Lượng tử hóa INT8 PTQ cân bằng biên độ Prior ($127$); gộp BatchNorm vào trọng số Conv1D.
  * Xuất file khởi tạo bộ nhớ Gowin BSRAM (`.mi` / `.hex`) nạp trực tiếp vào 6 bank ROM trọng số của FPGA.  
  $	o$ *Sản phẩm:* Mô hình nơ-ron chạy bit-true trên FPGA cho kết quả sai lệch 0 bit so với mô phỏng PyTorch.
* **Tuần 3 — Firmware Giám sát trên Sonix SN32F407 (Keil MDK):**
  * Cấu hình SPI Slave DMA nhận gói tin 16 byte với độ trễ guardband $25\,\mu\text{s}$.
  * Lập trình thuật toán Conformal ACP Q16.16 số nguyên cố định, kiểm soát RAM firmware $< 3.1\,\text{KB}$ (bảo toàn 8 KB SRAM).
  * Thiết lập cơ chế ngắt Watchdog và giám sát chân xung nhịp `FPGA_HEARTBEAT`.  
  $	o$ *Sản phẩm:* Firmware SN32F407 hoàn chỉnh, chạy ổn định, không dùng soft-float, không tràn stack.
* **Tuần 4 — Ghép nối Phần cứng Toàn diện & Đo kiểm PPA:**
  * Đấu nối cảm biến ST IIS3DWB với FPGA Gowin Primer 20K; kết nối bus SPI 4 dây sang Sonix SN32F407.
  * Dùng dao động ký số Keysight đo chính xác dòng thời gian trễ: DSP ($1.415\,\text{ms}$) $\to$ NPU ($0.400\,\text{ms}$) $\to$ SPI ($0.032\,\text{ms}$) $\to$ MCU ($0.250\,\text{ms}$).
  * Đo dòng tiêu thụ điện trên điện trở shunt $0.1\,\Omega$, kiểm tra chế độ ngủ $94.5\%$ chu kỳ.  
  $	o$ *Sản phẩm:* Hệ thống vi mạch SoC lai hoạt động thời gian thực với trễ tổng $2.10\,\text{ms}$ và công suất $< 85\,\text{mW}$.
* **Tuần 5 — HMI OLED Page-Banded, Đóng gói & Báo cáo Chung kết:**
  * Hoàn thiện hiển thị OLED 0.96" bằng kỹ thuật single-page banding (128 bytes RAM); truyền thông LoRaWAN về trạm trung tâm.
  * Gia công vỏ hộp in 3D Smart Sensor Pod gắn trực tiếp lên gối đỡ động cơ thử nghiệm.
  * Hoàn tất hồ sơ thuyết minh kỹ thuật, slide báo cáo và video clip demo vận hành trực tiếp trước ban giám khảo.  
  $	o$ *Sản phẩm:* Thiết bị chẩn đoán công nghiệp hoàn chỉnh sẵn sàng tranh tài tại Vòng Chung kết.

---

## VI. BẢNG TỔNG HỢP CÁC CHỈ SỐ KỸ THUẬT ĐẠT ĐƯỢC (TARGET SPECIFICATIONS)

| Hạng mục chỉ số | Thông số kỹ thuật thiết kế | Phương pháp kiểm chứng thực tế |
| :--- | :--- | :--- |
| **Thời gian suy luận AI (Inference Latency)** | **0.40 ms** (nhanh hơn MCU 32 lần) | Xung đo trên chân GPIO bằng Dao động ký |
| **Tổng trễ toàn chuỗi (End-to-End Latency)** | **2.10 ms** (vượt chuẩn thời gian thực 38.4 ms)| Đo khoảng thời gian từ va đập cơ khí đến ngắt relay |
| **Tỷ lệ thời gian ngủ tiết kiệm điện (Duty Cycle)**| **94.5% thời gian ở chế độ WFI Sleep** | Dạng sóng dòng điện tiêu thụ qua điện trở Shunt |
| **Công suất tiêu thụ trung bình toàn hệ thống** | **< 85 mW @ 3.3V** | Đồng hồ vạn năng số độ chính xác cao 6.5 digits |
| **Độ chính xác chẩn đoán lỗi (Macro F1-score)** | **≥ 0.985 (98.5%)** | Đánh giá chéo 5-fold trên tập dữ liệu CWRU / MFPT |
| **Độ bao phủ toán học tin cậy RUL (Coverage)** | **≥ 90.0%** (chuẩn hóa số nguyên Q16.16)| Kiểm chứng chuỗi thời gian run-to-failure PRONOSTIA |
| **Tài nguyên Logic FPGA Gowin Primer 20K** | **6,350 / 20,736 LUT4 (30.6%)** | Báo cáo GowinSynthesis Place & Route Report |
| **Tài nguyên Khối nhân DSP FPGA** | **27 / 48 DSP18E (56.3%)** | Báo cáo Gowin DSP Resource Allocation |
| **Bộ nhớ SRAM sử dụng trên Sonix SN32F407** | **3,040 / 8,192 Bytes (37.1%)** | Keil MDK Linker Memory Map (.map) |
| **Bảo vệ an toàn bộ nhớ (Safety Headroom)** | **5,152 Bytes (62.9% RAM trống)** | Đảm bảo không bao giờ tràn Stack (Zero HardFault)|
| **Khả năng tự phát hiện lỗi lạ (OOD Detection)**| **AUROC ≥ 0.96** với ngưỡng Vacuity $u > 0.45$| Thử nghiệm với các dạng lỗi ngoài phân phối huấn luyện |
| **Giá thành phần cứng sản xuất (BOM Cost)** | **< $22.00 USD** | Bảng chi phí linh kiện thực tế từ nhà phân phối |

---
