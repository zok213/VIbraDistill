# BÁO CÁO TỔNG HỢP TOÀN DIỆN KỸ THUẬT THIẾT KẾ FPGA HIL-ONLY
## Hệ Thống VibraDistill-Edge (Tang Primer 20K & MCU Sonix SN32F407)
**Phiên làm việc ngày:** 01/11/2026  
**Kỹ sư thực hiện:** Toàn (Team Porygon)  
**Nền tảng mục tiêu:** Gowin GW2A-LV18PG256C8/I7 (Tang Primer 20K Dock Lite)  
**Công cụ phân tích:** Gowin EDA V1.9.12.03 (Synthesis & PnR), ModelSim SE  

---

> [!IMPORTANT]
> **MỤC ĐÍCH TÀI LIỆU:**  
> Tài liệu này được biên soạn nhằm chuyển giao toàn bộ bức tranh kiến trúc, thực trạng kỹ thuật, các đánh đổi thiết kế vi mạch (hardware trade-offs), phân tích đường trễ định thời (timing analysis chi tiết từ Gowin PnR) và danh mục cảnh báo quan trọng cho bất kỳ kỹ sư hoặc AI nào tiếp quản hệ thống mà không bị đứt gãy bối cảnh.  
> **QUY TẮC BẢO TOÀN THIẾT KẾ:** Tuyệt đối không chỉnh sửa tùy tiện các file Verilog (`.v`) khi chưa đối soát với mô hình số Bit-True và biên bản phân tích Timing Closure dưới đây.

---

## 1. BỐI CẢNH DỰ ÁN & MỤC TIÊU PHIÊN LÀM VIỆC NGÀY 01/11/2026

### 1.1. Bối Cảnh Toàn Hệ Thống (VibraDistill-Edge)
VibraDistill-Edge là giải pháp chẩn đoán lỗi vòng bi công nghiệp thời gian thực phân tầng (Heterogeneous Edge Co-Design):
1. **Tầng Vi Mạch FPGA (Gowin Tang Primer 20K @ 100 MHz):**
   * Đảm nhiệm 100% các tác vụ tính toán nặng nề: Lọc dải thông nhân quả, tách đường bao dao động va đập cơ học, biến đổi Fourier nhanh (FFT 512 điểm), trích xuất phổ biên độ, và thực thi mạng nơ-ron tích chập AI (NPU 12-way INT8 Core).
   * Đóng gói toàn bộ 257 bin phổ + nhãn chẩn đoán + độ bất định Dirichlet vào khung truyền SPI 524 bytes tốc độ 12.5 MHz gửi sang MCU.
2. **Tầng Vi Điều Khiển Giám Sát (Sonix SN32F407 ARM Cortex-M0 @ 60 MHz):**
   * Đóng vai trò System Supervisor: Hứng gói tin qua SPI DMA Circular, tính toán độ tin cậy RUL theo thuật toán HopACP Q16.16, hiển thị đồ thị phổ lên OLED SSD1306 và kích hoạt rơ-le ngắt bảo vệ SIL-2 (< 1.0 ms).

### 1.2. Mục Tiêu Cụ Thể Trong Phiên Làm Việc Hôm Nay
* Tách biệt hoàn toàn chế độ cảm biến vật lý ADXL345 (tạm hoãn để kiểm tra sau) và chuyển Top SoC sang **Chế độ thuần HIL (Hardware-in-the-Loop Replay)** sử dụng dữ liệu sóng rung chuẩn công nghiệp CWRU 12 kHz lưu trong BRAM.
* Khép kín toàn bộ chuỗi luồng dữ liệu (Dataflow):  
  $$\text{HIL Replay} \to \text{FIR 32-tap} \to \text{Envelope IIR} \to \text{Hann 512} \to \text{FFT 512 IP} \to \text{Square-Root} \to \text{NPU 12-way} \to \text{SPI Master 524B}$$
* Khắc phục triệt để các lỗi biên dịch, lỗi lệch pha truyền bit đầu tiên của SPI, chuẩn hóa hàm bão hòa phổ sang INT8.
* Thực hiện tổng hợp (Synthesis) và định vị - đi dây (Place & Route - PnR) trên Gowin EDA để lấy số liệu đo đạc tài nguyên và phân tích vi phạm định thời (STA Timing Closure).

---

## 2. KIẾN TRÚC VI MẠCH & DÒNG DỮ LIỆU ĐÃ NỐI (DATAFLOW ARCHITECTURE)

```
[HIL Replay BRAM] (512 mẫu x 16-bit, Fs = 12 kHz, phát mỗi 83.3 µs)
       │
       ▼ (sample_in, sample_strobe)
[fir_minphase_32] (32-tap Minimum-Phase FIR, 2.0 - 5.0 kHz, 4 multipliers x 8 cycles)
       │
       ▼ (fir_out, fir_valid)
[envelope_demodulator] (Full-wave Rectifier + 2nd-order Butterworth IIR LPF, USE_HIL=0)
       │
       ▼ (env_out, env_valid)
[hann_window] (Nhân cửa sổ Hann 512 điểm, tra bảng hann512_rom.vh, 2-stage pipeline)
       │
       ▼ (win_data, win_valid, win_sop)
[fft_wrapper] (Gom 512 mẫu vào fbuf -> Gowin FFT_Top IP Core 512-pt Radix-2)
       │
       ▼ (xk_re, xk_im, 257 bin dương 0..256)
[mag_isqrt] (18-stage fully pipelined: xk_re^2 + xk_im^2 -> non-restoring isqrt)
       │
       ├────────────────────────────────────────┬───────────────────────────────────────┐
       ▼ (mag_data, mag_valid, mag_idx)         ▼                                       ▼
[spectrum_bram] (257 x 16-bit)           [Monotonic Clamp INT8]                  [Master Sequencer]
(Đệm phổ cho khung SPI)                 (mag > 127 ? 127 : mag[7:0])             (Bắt mag_eop)
       │                                        │                                       │
       │                                        ▼ (npu_in_data streaming)               ▼ npu_start
       │                                 [npu_12way_core] ◄─────────────────────────────┘
       │                                 (12 kênh song song, 257 bước MAC, 2.62 µs)
       │                                        │
       │                                        ▼ npu_done (class, vacuity_q15)
       └───────────────────────────────────────►│
                                                ▼ spi_start_tx
                                         [spi_master_packet]
                                         (524 Bytes @ 12.5 MHz SCK, Mode 0)
                                                │
                                                ▼ (mcu_spi_sck, mosi, cs_n, irq_pulse)
                                         MCU Sonix SN32F407 Supervisor
```

### Thông Số Ngân Sách Thời Gian Từng Khối (Clock 100 MHz = 10 ns/chu kỳ)
| Phân Đoạn Vi Mạch | Thời Gian Xử Lý | Tần Suất Kích Hoạt | Ghi Chú Kỹ Thuật |
| :--- | :---: | :---: | :--- |
| **HIL Sample Generator** | 1 chu kỳ clock | Mỗi $83.3\,\mu\text{s}$ (12 kHz) | Bộ chia `SAMPLE_DIV = 8333` từ clock 100 MHz |
| **FIR 32-tap** | 8 chu kỳ tính + 2 chu kỳ chốt | 10 chu kỳ / mẫu | Cấu trúc gập 4 bộ nhân, trễ cố định 100 ns |
| **Envelope Demodulator** | 3 chu kỳ clock | 30 ns / mẫu | Pipeline 3 tầng, IIR Butterworth bậc 2 |
| **Hann Window** | 2 chu kỳ clock | 20 ns / mẫu | Tra ROM pROM BSRAM + nhân Q1.15 |
| **FFT 512 Buffer & IP** | ~1,000 chu kỳ clock | Mỗi khung 512 mẫu (~42.67 ms) | IP Gowin Radix-2 kéo dữ liệu từ `fbuf` |
| **Magnitude ISQRT** | 18 chu kỳ clock | Thông lượng 1 bin / chu kỳ | 2 tầng bình phương + 16 tầng căn số nguyên bit-true |
| **NPU 12-Way Inference** | **262 chu kỳ (~2.62 µs)** | 1 lần / khung FFT | 257 bước MAC + 2 nhịp xả + Argmax/Dirichlet |
| **SPI Packet Transmit** | **~335.4 µs** | 1 lần / khung FFT | 524 byte x 8 bit x 80 ns (SCK = 12.5 MHz) |
| **Chu Kỳ Khung FFT Toàn Phần** | **42.67 ms** | 23.44 Hz | Tổng thời gian tính toán < 1.5 ms $\ll$ 42.67 ms |

---

## 3. BÁO CÁO PHÂN TÍCH TIMING THỰC TẾ TRÊN GOWIN EDA (STA REPORT)

> [!WARNING]
> **KẾT LUẬN ĐỊNH THỜI: HỆ THỐNG HIỆN TẠI CHƯA ĐẠT TIMING CLOSURE Ở TẦN SỐ 100 MHZ.**  
> Báo cáo PnR Timing (`FPGA_FINAL.rpt.txt` và `FPGA_FINAL_tr_content.html`) ghi nhận tần số hoạt động cực đại thực tế là **$F_\text{max} = 83.264\,\text{MHz}$** (thiếu 17.022 MHz so với yêu cầu 100.286 MHz).  
> **Worst Setup Slack:** **$-2.038\,\text{ns}$** (Có 68 điểm cuối bị vi phạm Setup).  
> **Worst Hold Slack:** **$+0.000\,\text{ns}$** (0 vi phạm Hold - Phần mạng xung nhịp Hold đạt chuẩn tuyệt đối 100%).

### 3.1. Bảng 5 Đường Trễ Tới Hạn (Critical Paths) Vi Phạm Nặng Nhất
Dữ liệu trích xuất trực tiếp từ file `FPGA_FINAL.timing_paths` và `FPGA_FINAL_tr_content.html`:

| Hạng | Điểm Bắt Đầu (Launch Flip-Flop) | Điểm Kết Thúc (Capture Flip-Flop) | Data Delay | Required | Setup Slack | Nguyên Nhân Gốc Rễ Vi Mạch |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- |
| **1** | `u_fir/cycle_cnt_2_s8/Q` | `u_fir/acc_30_s0/D` | $18.476\,\text{ns}$ | $9.972\,\text{ns}$ | **$-2.038\,\text{ns}$** | Mux 32:1 chọn mẫu $\to$ 4 bộ nhân 16x16 $\to$ Chuỗi cộng 36-bit gom 5 toán hạng dồn trong 1 chu kỳ clock. |
| **2** | `u_fir/cycle_cnt_2_s8/Q` | `u_fir/acc_28_s0/D` | $18.233\,\text{ns}$ | $9.972\,\text{ns}$ | **$-1.796\,\text{ns}$** | Bit 28 của bộ tích lũy FIR (cùng đường trễ chuỗi cộng tích lũy). |
| **3** | `u_fir/cycle_cnt_2_s8/Q` | `u_fir/acc_29_s0/D` | $17.944\,\text{ns}$ | $9.972\,\text{ns}$ | **$-1.506\,\text{ns}$** | Bit 29 của bộ tích lũy FIR. |
| **4** | `u_fir/cycle_cnt_2_s8/Q` | `u_fir/acc_24_s0/D` | $17.839\,\text{ns}$ | $9.972\,\text{ns}$ | **$-1.401\,\text{ns}$** | Bit 24 của bộ tích lũy FIR. |
| **5** | `u_fft/.../stage_0_s1/Q` | `u_fft/.../mem_r_0_0_s/DIB[8]` | $11.302\,\text{ns}$ | $9.972\,\text{ns}$ | **$-1.365\,\text{ns}$** | Đường logic giải mã bướm (butterfly) và ghi BSRAM nội bộ của IP FFT Gowin. |
| **6** | `u_npu/score_0_6_s0/Q` | `u_npu/vacuity_q15_8_s0/CE` | $10.911\,\text{ns}$ | $9.972\,\text{ns}$ | **$-0.974\,\text{ns}$** | Trạng thái `S_DECIDE` của NPU: So sánh argmax 4 lớp + tính tổng evidence + kích hoạt chia trong 1 chu kỳ. |

---

## 4. BẢNG TỔNG HỢP TÀI NGUYÊN VI MẠCH THỰC TẾ (SILICON RESOURCE USAGE)

Dưới đây là số liệu kiểm toán tài nguyên thực tế trích xuất từ `FPGA_FINAL_syn_resource.html` và báo cáo PnR `FPGA_FINAL.rpt.txt` trên chip Gowin GW2A-18:

| Khối Chức Năng (Hierarchical Module) | DFF Registers | LUT Logic | ALU Slices | DSP Blocks | BSRAM (Cứng) | SSRAM (LUT RAM) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Top SoC & Replay Control** | 55 | 377 | 23 | 0 | 1 | 68 |
| **u_fir (fir_minphase_32)** | 591 | 390 | 0 | 2 (MULT18) | 0 | 0 |
| **u_envelope (envelope_demodulator)** | 67 | 27 | 31 | 3 (MULT9) | 0 | 0 |
| **u_hann (hann_window + ROM)** | 31 | 7 | 8 | 1 (MULT18) | 1 (pROM) | 0 |
| **u_fft (fft_wrapper logic & fbuf)** | 33 | 398 | 0 | 0 | 0 | 128 (SSRAM) |
| **├── FFT_Top (Gowin IP Core)** | 306 | 673 | 182 | 2 (MULT18) | 5 (DPB) | 0 |
| **└── u_mag (mag_isqrt 18-stage)** | 604 | 372 | 326 | 1 (MULT18) | 0 | 16 (SSRAM) |
| **u_npu (npu_12way_core)** | 1654 | 1240 | 172 | 0 | 3 (pROM) | 0 |
| **├── u_mac12 (12-way Pipelined MAC)** | 662 | 610 | 384 | 12 (MULT9) | 0 | 0 |
| **└── u_div (div_18bit Restoring)** | 56 | 46 | 34 | 0 | 0 | 0 |
| **u_spi_tx (spi_master_packet 524B)** | 101 | 473 | 15 | 0 | 0 | 0 |
| **TỔNG TIÊU THỤ TRÊN CHIP (TOTAL)** | **4,845 / 16,173** | **5,046 / 20,736** | **1,664** | **11 / 24** | **10 / 46** | **212** |
| **TỶ LỆ PHẦN TRĂM (%)** | **30% DFF** | **39% Logic** | — | **46% DSP** | **22% BSRAM** | — |

> [!NOTE]
> **ĐÍNH CHÍNH QUAN TRỌNG VỚI TÀI LIỆU CŨ:**  
> Các tài liệu sơ khởi ghi nhận hệ thống chỉ dùng `< 750 DFF` thực chất **chỉ đo lường riêng khối lõi NPU**. Khi tích hợp toàn bộ chuỗi streaming công nghiệp (bao gồm bộ đệm hàng đợi FIR 32 tap, bộ căn bậc hai 18 tầng pipeline `mag_isqrt`, IP FFT, bộ chia 18-bit và máy phát khung SPI), tổng số DFF thực tế trên chip là **4,845 DFFs (30% diện tích chip)**. Mức sử dụng này vẫn cực kỳ an toàn, dư thừa tới 70% tài nguyên logic trên chip Gowin GW2A-18.

---

## 5. NHỮNG ĐÁNH ĐỔI KỸ THUẬT (TRADE-OFFS) THỰC SỰ ĐẰNG SAU THIẾT KẾ

### 5.1. Trade-off 1: Tần Số Xung Nhịp 100 MHz vs Bản Chất Tín Hiệu 12 kHz
* **Được:** Đạt tốc độ suy luận siêu tốc $2.62\,\mu\text{s}$, đáp ứng đúng đặc tả kỹ thuật bàn giao của nhóm và tốc độ SPI 12.5 MHz truyền gói 524 bytes chỉ mất $335\,\mu\text{s}$.
* **Mất & Rủi ro:** Đẩy hệ thống vào thế kẹt định thời (STA Setup Violation -2.038 ns). Trong thực tế, chu kỳ lấy mẫu của cảm biến rung là $83.3\,\mu\text{s}$ (12 kHz) và một khung FFT dài tới $42.67\,\text{ms}$. Việc FPGA chạy 100 MHz là dư thừa năng lực xử lý gấp hàng trăm lần nhu cầu thời gian thực.
* **Phương án lùi (Fallback Plan):** Nếu không muốn can thiệp cấu trúc pipeline của FIR, có thể **hạ tần số rPLL xuống 80 MHz hoặc 75 MHz**. Tại 80 MHz, chu kỳ clock là $12.5\,\text{ns} > 12.0\,\text{ns}$ (đủ bù đắp slack -2.038 ns), vi mạch sẽ **ĐẠT TIMING CLOSURE 100% SẠCH SẼ** mà không làm ảnh hưởng đến bất kỳ tính năng chẩn đoán hay độ chính xác nào của AI!

### 5.2. Trade-off 2: Cấu Trúc FIR Gập 4 Bộ Nhân (4-Multiplier Folding Architecture)
* **Được:** Tiết kiệm tối đa tài nguyên DSP. Thay vì dùng 32 bộ nhân 16-bit tốn cạn kiệt DSP của chip, thiết kế chỉ dùng 4 bộ nhân nhân chập qua 8 chu kỳ lặp (`cycle_cnt`).
* **Mất & Rủi ro:** Tạo thành đường trễ tổ hợp dài nhất trên toàn chip: Mux chọn mẫu 32:1 $\to$ Nhân 16x16 $\to$ Bộ cộng dồn 36-bit 5 toán hạng. Đây chính là nguyên nhân tạo ra vi phạm Setup Slack số 1 (-2.038 ns).

### 5.3. Trade-off 3: Streaming Trực Tiếp FFT Sang NPU (Bỏ Bộ Đệm Trung Gian)
* **Được:** Tiết kiệm 5.1 KB bộ nhớ trung gian, loại bỏ hoàn toàn giai đoạn chờ nạp (`SEQ_LOAD`), NPU suy luận ngay khi bin 256 vừa rời khối tính căn bậc hai.
* **Mất & Rủi ro:** Mất đi tính độc lập giữa khối xử lý phổ và khối suy luận. Nếu FFT bị trễ nhịp hoặc `mag_eop` đến khi NPU đang bận, khung dữ liệu sẽ bị bỏ qua (Drop Frame).

### 5.4. Trade-off 4: Khối Trích Căn Bậc Hai `mag_isqrt.v` 18 Tầng Pipeline Đầy Đủ
* **Được:** Độ chính xác căn bậc hai số nguyên tuyệt đối 100% (Bit-True hoàn hảo với hàm `math.isqrt()` của Python). Cho thông lượng 1 bin / chu kỳ liên tục.
* **Mất & Rủi ro:** Tiêu tốn tới 604 DFFs và 326 ALUs (chiếm 12.5% tổng số flip-flop toàn chip) chỉ để phục vụ phép toán căn bậc hai.

### 5.5. Trade-off 5: Đọc Bất Đồng Bộ `fbuf` & `stim_bram` (SSRAM vs BSRAM)
* **Được:** Giao diện đơn giản, cho phép IP FFT đọc dữ liệu ngay lập tức theo địa chỉ `idx` trong cùng 1 chu kỳ clock mà không cần trễ đọc 1 nhịp.
* **Mất & Rủi ro:** Gowin EDA buộc phải suy luận mảng nhớ thành **SSRAM (LUT RAM)** tiêu tốn 212 ô RAM16 thay vì dùng khối nhớ cứng BSRAM, làm gia tăng trễ định tuyến.

---

## 6. DANH MỤC LỖI ĐÃ TÌM VÀ ĐIỀU CHỈNH TRONG PHIÊN LÀM VIỆC

| STT | Hiện Tượng / Lỗi Gặp Phải | Nguyên Nhân Gốc Rễ Vi Mạch | Giải Pháp Kỹ Thuật Đã Áp Dụng |
| :---: | :--- | :--- | :--- |
| **1** | **SPI Gói #2 Lệch Bit Đầu (Sync ra `0xAAD5` thay vì `0xAA55`)** | Bộ chia `clk_div` chạy tự do liên tục. Khi xung `start_tx` đến lệch pha, cạnh lên SCK xuất hiện *trước* cạnh rơi cập nhật MOSI. Slave đọc phải bit cũ của gói trước. | Bổ sung lệnh ép pha: `clk_div <= 3'd4;` ngay tại trạng thái `STATE_IDLE` khi nhận lệnh bắt đầu gửi. Đảm bảo sự kiện đầu tiên luôn là cạnh rơi SCK cập nhật MOSI. |
| **2** | **Lỗi Cú Pháp Parameter `.USE_ (0)` trong Top SoC** | Khi gõ sửa code bị cụt tên parameter. Tên chuẩn trong module con là `USE_HIL`. | Khôi phục đầy đủ thành `.USE_HIL(0)` (chú thích rõ cơ chế chọn hệ số bên dưới). |
| **3** | **Biến Chưa Khai Báo `$readmemh(..., memory_reg)`** | Code cũ tham chiếu biến nhớ không tồn tại trong top module. | Loại bỏ lệnh thừa; bộ đệm `spectrum_bram` được ghi động bởi FFT và reset về 0. |
| **4** | **Thiếu Nguồn Mẫu Cho Khối Lọc FIR** | Cắt bỏ ADXL345 làm đầu vào FIR bị treo hở mạch. | Kết nối khối phát mẫu HIL BRAM 12 kHz (`stim_bram`) với bộ chia 8333 chu kỳ. |
| **5** | **Đường Dẫn ROM Kích Thích Không Tồn Tại** | Gowin EDA tìm file theo đường dẫn tương đối từ thư mục dự án chứa file `.gprj`, không phải từ `src/`. | Cố định đường dẫn chuẩn: `src/test_npu/roms/hil/stimulus_cwru_normal.hex`. |
| **6** | **Nén Phổ Phi Tuyến Dạng Răng Cưa (Sawtooth Inversion Cliff)** | Logic phân nhánh byte cao `mag[15:8] != 0` làm biên độ 256 bị nén thành 1 (tín hiệu mạnh biến thành nhiễu sàn). | Thay bằng hàm bão hòa tuyến tính đơn điệu chuẩn của Tài: `(mag > 127) ? 8'sd127 : mag[7:0]`. |

---

## 7. CẢNH BÁO QUAN TRỌNG KHI VẬN HÀNH & KẾ THỪA THIẾT KẾ

> [!CAUTION]
> **CẢNH BÁO 1: NGHỊCH LÝ PARAMETER `USE_HIL` TRONG `envelope_demodulator.v`**  
> Trong file `envelope_demodulator.v`, các hệ số được gán qua toán tử ba ngôi:  
> `localparam signed [15:0] B0 = USE_HIL ? 16'sh0C7F : 16'sh08A4;`  
> Nguyên bản code này dùng tham số `USE_ADXL345` (1 là ADXL345, 0 là HIL). Khi đổi tên thành `USE_HIL`, người viết **chưa đảo lại vị trí toán tử**. Do đó:  
> * **`USE_HIL = 0`:** Mới thực sự chọn bộ hệ số `08A4, 1148, 08A4, 96E8, 34B2` (dành cho chế độ HIL công nghiệp Fc = 1000 Hz @ 13.333 kHz).  
> * **`USE_HIL = 1`:** Thực chất lại chọn bộ hệ số `0C7F` (dành cho cảm biến ADXL345 Fc = 400 Hz @ 3.2 kHz).  
> 👉 **LƯU Ý:** Trong file `gowin_top_soc_hil.v`, parameter này **BẮT BUỘC PHẢI ĐỂ LÀ `.USE_HIL(0)`**. Tuyệt đối không tự ý đổi thành 1!

> [!WARNING]
> **CẢNH BÁO 2: TÌNH TRẠNG FILE RÀNG BUỘC VẬT LÝ CST (`top_wrapper.cst`)**  
> Trong lần chạy PnR vừa qua, báo cáo chỉ ra: `<Physical Constraints File>: ---` (Chưa gán file CST thành công hoặc bị loại khỏi project). Hệ quả là **toàn bộ 9 chân I/O bị Gowin tự động phân bổ ngẫu nhiên vào các chân Bank 1.8V thay vì Bank 3.3V**.  
> Trước khi nạp bitstream lên board thật Tang Primer 20K Dock Lite, kỹ sư phụ trách phải:  
> 1. Đồng bộ lại tên cổng trong CST: Đổi `spi_sck`, `spi_cs_n`, `spi_mosi` thành `mcu_spi_sck`, `mcu_spi_cs_n`, `mcu_spi_mosi`.  
> 2. Gán chân cho `rst_n_pin` (khuyến nghị chân `T10` hoặc nút nhấn trên board).  
> 3. Đảm bảo cấu hình đúng chuẩn điện áp `IO_TYPE=LVCMOS33`.

> [!WARNING]
> **CẢNH BÁO 3: ĐỘ RỘNG XUNG NGẮT `mcu_irq_pulse`**  
> Trong `spi_master_packet.v`, tín hiệu ngắt `irq_pulse` được kích lên mức 1 tại trạng thái `STATE_DONE` và hạ xuống 0 ngay ở chu kỳ clock tiếp theo khi chuyển sang `STATE_IDLE`.  
> Độ rộng xung ngắt này chỉ kéo dài đúng **1 chu kỳ clock 100 MHz ($10\,\text{ns}$)**. Vi điều khiển Sonix SN32F407 chạy ở tần số 60 MHz có nguy cơ **bỏ lỡ ngắt GPIO** nếu cạnh lấy mẫu không bắt kịp xung quá hẹp này. Khuyến nghị cấu hình chân ngắt MCU ở chế độ ngắt cạnh (Edge-Triggered Falling/Rising) hoặc kéo dài xung lên tối thiểu $1.0\,\mu\text{s}$ trong RTL.

---

## 8. LỘ TRÌNH THỰC THI TIẾP THEO (NEXT STEPS)

1. **Khép Kín Định Thời (Timing Closure 100 MHz):**
   * *Phương án tối ưu logic (Ưu tiên 1):* Chèn 1 tầng thanh ghi đường ống (Pipeline Register) vào giữa bộ nhân 16x16 và bộ cộng tích lũy 36-bit trong `fir_minphase_32.v` để bẻ gãy critical path dài $18.476\,\text{ns}$.
   * *Phương án hạ xung (Ưu tiên 2 - Không sửa code):* Cấu hình lại `Gowin_rPLL` từ 100 MHz xuống **80 MHz**. Tần số 80 MHz hoàn toàn thỏa mãn mọi yêu cầu thời gian thực của hệ thống và giải quyết triệt để vi phạm định thời STA.
2. **Cập Nhật File Gán Chân Vật Lý (`top_wrapper.cst`):**
   * Sửa đổi tên các chân SPI theo đúng top SoC, loại bỏ các cổng ADXL345 thừa và gán điện áp 3.3V cho Bank 2/Bank 7.
3. **Kiểm Tra Thực Nghiệm Với Trọng Số & Stimulus Thật:**
   * Thay thế stimulus giả bằng file sóng rung chuẩn CWRU thật để đối soát lớp dự đoán (`npu_pred_class`) và chỉ số bất định Dirichlet (`npu_vacuity_q15`) trực tiếp trên màn hình OLED của MCU Sonix.
4. **Tích Hợp Lại Khối Cảm Biến ADXL345 (Sau Khi HIL Ổn Định):**
   * Bổ sung khối đọc SPI ADXL345 3.2 kHz và khối chuyển mạch tham số (`USE_ADXL345`) sau khi đã nghiệm thu hoàn tất chế độ HIL trên phần cứng.

---
*Tài liệu được kết xuất phục vụ công tác bàn giao và kiểm định chất lượng kỹ thuật vi mạch dự án VibraDistill-Edge.*
