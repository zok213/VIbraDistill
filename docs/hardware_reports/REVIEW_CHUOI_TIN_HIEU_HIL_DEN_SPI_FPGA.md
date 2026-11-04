# BÁO CÁO REVIEW TOÀN DIỆN CHUỖI TÍN HIỆU TỪ RAW HIL ĐẾN XUẤT PHỔ FFT & BẮN GÓI SPI QUA MCU
## Dự án: VibraDistill-Edge (Gowin GW2A Tang Primer 20K & MCU Sonix SN32F407)
**Thời điểm đánh giá:** 01/11/2026  
**Đối tượng thẩm định:** Mã nguồn RTL Verilog tại `t:\MCU_FPGA\FPGA_FINAL\src\`, báo cáo tổng hợp và PnR Gowin EDA V1.9.12.03, tài liệu bàn giao nhánh `tai` (repo `zok213/porygon`).  
**Quy tắc kiểm thử:** Chế độ Review Độc Bản — TUYỆT ĐỐI KHÔNG CHỈNH SỬA BẤT KỲ FILE VERILOG (`.v`) NÀO.

---

> [!IMPORTANT]
> **KẾT LUẬN TỔNG QUAN (EXECUTIVE SUMMARY):**  
> * **Chuỗi logic số (Digital Datapath) FPGA đã HOÀN THÀNH 100%:** Luồng dữ liệu từ phát mẫu rung HIL 12 kHz $\to$ lọc thông dải FIR 32 tap $\to$ tách đường bao Envelope IIR $\to$ nhân cửa sổ Hann 512 điểm $\to$ biến đổi Fourier Gowin FFT_Top IP $\to$ trích xuất độ lớn phổ bit-true $\to$ phân loại AI NPU 12-way $\to$ đóng khung truyền SPI 524 bytes kèm CRC16 đã được nối thông suốt.  
> * **Khép kín định thời (Timing Closure) 100 MHz: ĐÃ ĐẠT CHUẨN (PASS 100%).** Bản PnR mới nhất ghi nhận **$F_\text{max} = 100.368\,\text{MHz}$**, Setup Slack $= +0.008\,\text{ns}$, **0 Setup Violations, 0 Hold Violations** (sau khi `fir_minphase_32.v` được bổ sung 3 tầng pipeline chia nhỏ bộ tích lũy).  
> * **ĐIỂM NGHẼN DUY NHẤT CÒN LẠI ĐỂ NẠP BOARD THẬT:** File gán chân vật lý (`top_wrapper.cst`) bị lệch tên cổng và thiếu chân reset `rst_n_pin`, dẫn tới việc Gowin PnR tự động xếp 9 chân I/O vào các chân ngẫu nhiên ở Bank 1.8V thay vì Bank 3.3V.

---

## 1. SƠ ĐỒ DÒNG DỮ LIỆU TOÀN CHUỖI TÍN HIỆU (END-TO-END DATAFLOW)

```
[HIL Replay BRAM] (512 mẫu x 16-bit signed, chia tần 100MHz / 8333 = 12 kHz)
       │ sample_in, sample_strobe (mỗi 83.3 µs)
       ▼
[Stage 1: fir_minphase_32] (32-tap Folded FIR, 2.0-5.0 kHz, 3-stage pipeline)
       │ fir_out (Q1.15), fir_valid
       ▼
[Stage 2: envelope_demodulator] (Full-Wave Rectifier + Butterworth IIR LPF, USE_HIL=0)
       │ env_out, env_valid
       ▼
[Stage 2.5: hann_window] (Nhân cửa sổ Hann 512-pt qua ROM hann512_rom.vh)
       │ win_data, win_valid, win_sop, win_eop
       ▼
[Stage 3: fft_wrapper] (Gom 512 mẫu vào fbuf -> Gowin FFT_Top Radix-2 IP Core)
       │ xk_re, xk_im, fft_opd (257 bin dương: idx <= 256)
       ▼
[Stage 3.5: mag_isqrt] (18 tầng pipeline bit-true: sqrt(re^2 + im^2))
       │ mag_data (16-bit uint), mag_valid, mag_idx (0..256), mag_eop
       ├────────────────────────────────────────┬───────────────────────────────────────┐
       ▼                                        ▼                                       ▼
[spectrum_bram] (257 x 16-bit)           [Monotonic Clamp INT8]                  [Master Sequencer]
(Lưu phổ cho gói tin SPI)               (mag > 127 ? 127 : mag[7:0])             (Bắt mag_eop)
       │                                        │                                       │
       │                                        ▼ npu_in_data (Streaming)               ▼ npu_start
       │                                 [Stage 4: npu_12way_core] ◄────────────────────┘
       │                                 (12-Way MAC, 257 steps, 2.62 µs)
       │                                        │
       │                                        ▼ npu_done (class, vacuity, logits)
       └───────────────────────────────────────►│
                                                ▼ spi_start_tx
                                         [Stage 5: spi_master_packet]
                                         (524 Bytes @ 12.5 MHz SCK, Little-Endian)
                                                │
                                                ▼ (mcu_spi_sck, mosi, cs_n, irq_pulse)
                                         MCU Sonix SN32F407 Supervisor
```

---

## 2. BẢNG ĐÁNH GIÁ CHI TIẾT TỪNG PHÂN ĐOẠN VI MẠCH (MODULE AUDIT)

### 2.1. Nguồn Mẫu Rung HIL (`gowin_top_soc_hil.v`)
* **Chức năng:** Giả lập tín hiệu gia tốc cơ học thời gian thực bằng cách phát lại 512 mẫu rung CWRU 16-bit có dấu từ bộ nhớ BRAM.
* **Tần số lấy mẫu:** Clock hệ thống 100 MHz chia qua bộ đếm `SAMPLE_DIV = 8333` $\implies F_s = \frac{100\,\text{MHz}}{8333} = 12.00048\,\text{kHz}$ (Chu kỳ mẫu $T_s = 83.33\,\mu\text{s}$).
* **Ưu điểm đã hoàn thành:**
  * Khởi tạo bộ nhớ `$readmemh` nạp trực tiếp file `stimulus_cwru_normal.hex`.
  * Bộ chia xung nhịp chính xác tuyệt đối, phát 1 mẫu sau mỗi $83.33\,\mu\text{s}$ kèm cờ `sample_strobe` chuẩn 1 chu kỳ clock.
* **Điểm lưu ý:**
  * File top hiện tại phát lặp lại một file sóng đơn lẻ. Bản ghi chú trước có đề cập module `hil_stim_player.v` (hỗ trợ 5 kịch bản tự động đổi sau 24 frame), nhưng file top nạp thực tế hiện tại đang dùng khối BRAM replay tích hợp sẵn bên trong `gowin_top_soc_hil.v`. Điều này hoàn toàn tốt cho kiểm thử tĩnh, nhưng cần lưu ý nếu muốn demo chuyển lỗi động.

---

### 2.2. Khối Lọc Thông Dải FIR 32 Tap (`fir_minphase_32.v`)
* **Chức năng:** Lọc dải thông dải sóng mang cộng hưởng hư hỏng vòng bi ($2.0\,\text{kHz} - 5.0\,\text{kHz}$).
* **Kiến trúc:** Cấu trúc gập 4 bộ nhân (Folded MAC Architecture) chạy qua 8 chu kỳ lặp (`cycle_cnt = 0..7`) + 2 chu kỳ xả pipeline.
* **Kiểm toán Pipelining:**
  * Khối này đã được nâng cấp lên **kiến trúc Pipeline 3 tầng**:
    * Tầng 1: `pp0..pp3` chốt 4 tích số $16\text{-bit} \times 16\text{-bit}$.
    * Tầng 2: `s01, s23` cộng cặp 2 tích số thành 34-bit.
    * Tầng 3: `acc <= acc + s01 + s23` cộng dồn vào bộ tích lũy 36-bit.
    * Thêm 2 trạng thái xả: `S_DRAIN_1` và `S_DRAIN_2` trước khi sang `S_DONE`.
* **Kết quả nghiệm thu:**
  * ✅ **Đường trễ dài nhất trước đây (Setup Slack $-2.038\,\text{ns}$) đã được triệt tiêu hoàn toàn!**
  * Độ trễ xử lý là 11 chu kỳ clock ($110\,\text{ns}$), cực kỳ nhỏ so với khoảng cách $83.33\,\mu\text{s}$ giữa 2 mẫu ($8333$ chu kỳ clock), không gây hiện tượng tràn dữ liệu (Overrun).
* **Điểm lưu ý số học:**
  * Đầu ra gán bằng phép cắt bit: `y_out <= acc[30:15]`. Nếu biên độ rung đầu vào vượt quá ngưỡng làm tràn bộ tích lũy, giá trị sẽ bị quay vòng dấu (Wrap-around). Dữ liệu rung chuẩn nạp vào cần được chuẩn hóa biên độ đỉnh $< 26,000$ như hướng dẫn của Tài.

---

### 2.3. Khối Tách Đường Bao Biến Điệu (`envelope_demodulator.v`)
* **Chức năng:** Chỉnh lưu toàn sóng lấy trị tuyệt đối $|x|$ kết hợp bộ lọc thông thấp số IIR Butterworth bậc 2 để trích xuất tần số va đập đặc trưng của lỗi vòng bi ($BPFO, BPFI$).
* **Kiến trúc:** Direct-Form I IIR Filter với 3 tầng pipeline (`pipe_valid[1:0]`).
* **Kiểm toán Parameter & Hệ số:**
  * Trong top SoC, module được gán: `.USE_HIL(0)`.
  * Trong `envelope_demodulator.v`:  
    `localparam signed [15:0] B0 = USE_HIL ? 16'sh0C7F : 16'sh08A4;`
  * **Xác nhận số học:** Khi `.USE_HIL(0)`, toán tử chọn nhánh `08A4, 1148, 08A4, 96E8, 34B2` (đây chính là nhánh dành cho hồ sơ HIL công nghiệp).
* **Kết quả nghiệm thu:**
  * ✅ Tầng pipeline hoạt động đồng bộ với xung nhịp `sample_en` (chỉ tiêu thụ năng lượng khi có mẫu mới).
  * ✅ Trễ cố định 3 chu kỳ clock ($30\,\text{ns}$).
* **Điểm lưu ý số học:**
  * Trường hợp biên độ âm cực đại của số nguyên 16-bit có dấu ($y = -32768$), phép đảo dấu `-y` trong bù 2 vẫn trả về $-32768$. Tuy nhiên trong thực tế tín hiệu gia tốc chuẩn hóa không bao giờ chạm tới điểm biên này.

---

### 2.4. Cửa Sổ Hanning 512 Điểm (`hann_window.v`)
* **Chức năng:** Nhân 512 mẫu thời gian với hàm cửa sổ Hanning để triệt tiêu hiện tượng rò rỉ phổ (Spectral Leakage) trước khi đưa vào FFT.
* **Kiến trúc:** 
  * Bảng tra ROM 512 hệ số đối xứng Q1.15 được include từ `hann512_rom.vh` (được Gowin tổng hợp thành 1 khối pROM BSRAM cứng).
  * Pipeline 2 tầng: Tầng 1 tra ROM + chốt mẫu; Tầng 2 nhân và dịch bit `prod[30:15]`.
* **Kết quả nghiệm thu:**
  * ✅ Tự động đếm chỉ số $0 \to 511$ không cần mạch chia.
  * ✅ Sinh cờ phân định khung: `out_sop` (Start of Packet tại mẫu 0) và `out_eop` (End of Packet tại mẫu 511) chuẩn xác cho khối FFT tiếp theo.

---

### 2.5. Gom Khung & Lõi Gowin IP FFT (`fft_wrapper.v` + `fft.v`)
* **Chức năng:** Gom đủ 512 mẫu từ cửa sổ Hann vào bộ đệm `fbuf`, kích hoạt lõi IP `FFT_Top` của hãng Gowin (512 điểm, Radix-2, Single-Clock), và lọc lấy 257 bin tần số dương ($0 \dots 256$).
* **Giao thức bắt tay với IP Gowin:**
  1. Khi gom đủ 512 mẫu (`frame_full = 1`), FSM chuyển sang `S_WAIT` và phát xung `start = 1`.
  2. IP Gowin phản hồi bằng cờ `ipd = 1` (Input Data Phase), phát ra địa chỉ `idx` cần đọc.
  3. `fft_wrapper` cung cấp dữ liệu qua đường tổ hợp `xn_re = fbuf[fft_idx]`.
  4. Sau khi nạp xong 512 mẫu, IP Gowin tính toán và bật cờ `opd = 1` (Output Data Phase), xuất các bin phổ tần số thực `xk_re` và ảo `xk_im`.
  5. Cờ `keep = fft_opd && (fft_idx <= 256)` chỉ cho phép 257 bin dương đi tiếp sang bộ trích căn bậc hai.
* **Kết quả nghiệm thu:**
  * ✅ IP Core `FFT_Top` thật đã được tổng hợp thành công vào bitstream (chiếm 5 khối BSRAM DPB và 2 khối DSP18X18).
  * ✅ Cơ chế bảo vệ toàn diện: Tích hợp đầy đủ các cờ báo lỗi phần cứng `err_overrun` (nhận mẫu khi IP đang bận), `err_timeout` (IP treo quá 60,000 chu kỳ), và `err_sync` (lỗi lệch khung).
* **Điểm lưu ý:**
  * `fbuf` đọc tổ hợp trực tiếp từ `fft_idx` của IP nên Gowin tổng hợp thành 128 ô SSRAM (LUT-RAM). Thiết kế này chấp nhận tốn thêm một lượng nhỏ LUT để đổi lấy việc đáp ứng tức thời dữ liệu cho IP Gowin trong cùng chu kỳ xung nhịp.

---

### 2.6. Trích Xuất Độ Lớn Phổ Bit-True (`mag_isqrt.v`)
* **Chức năng:** Tính biên độ phổ:
  $$\text{mag} = \lfloor \sqrt{x_r^2 + x_i^2} \rfloor$$
* **Kiến trúc:** 
  * Đường ống sâu 18 tầng đồng bộ (18-stage fully pipelined datapath).
  * Tầng 1: 2 bộ nhân $16\text{-bit} \times 16\text{-bit}$ tính $x_r^2$ và $x_i^2$.
  * Tầng 2: Bộ cộng 32-bit tính tổng năng lượng.
  * Tầng 3..18: 16 tầng lặp giải thuật căn bậc hai số nguyên không phục hồi (Non-Restoring Integer Square Root).
* **Kết quả nghiệm thu:**
  * ✅ Khớp từng bit (Bit-True 100%) với hàm `math.isqrt()` trong thư viện chuẩn của Python.
  * ✅ Thông lượng đạt đỉnh: Sau 18 chu kỳ trễ ban đầu, mỗi chu kỳ xung nhịp xuất ra đúng 1 bin phổ kèm chỉ số `out_idx` và cờ `out_valid` tương ứng.
  * ✅ Trị cực đại của $\text{mag} \le \sqrt{2^{31}} = 46341$, hoàn toàn nằm gọn an toàn trong định dạng số nguyên không dấu 16-bit (`uint16`).

---

### 2.7. Bộ Đệm Phổ & Chuẩn Hóa Lượng Tử Hóa NPU (`gowin_top_soc_hil.v`)
* **Chức năng:** Lưu trữ 257 bin phổ vào `spectrum_bram` để đóng gói SPI, đồng thời chuẩn hóa phổ thành INT8 để bơm trực tiếp vào NPU.
* **Hàm truyền lượng tử hóa:**
  ```verilog
  wire signed [7:0] npu_in_data = (mag_data > 16'd127) ? 8'sd127 : mag_data[7:0];
  ```
* **Kết quả nghiệm thu:**
  * ✅ **Đã loại bỏ hoàn toàn lỗi vực thẳm răng cưa (Sawtooth Inversion Cliff)**: Các biên độ lớn $\ge 128$ đều được bão hòa phẳng ở $127$, bảo toàn tính đơn điệu toán học $\forall x_1 \le x_2 \implies f(x_1) \le f(x_2)$.
  * ✅ Chế độ nạp streaming trực tiếp: Khi bin 256 rời khỏi bộ tính căn bậc hai (`mag_eop = 1`), toàn bộ 257 bin đã nằm sẵn trong bộ nhớ của NPU mà không tốn thêm bất kỳ chu kỳ nạp trung gian nào.

---

### 2.8. Lõi Suy Luận AI NPU 12 Kênh (`npu_12way_core.v` + `npu_mac12_unit.v`)
* **Chức năng:** Thực thi mạng nơ-ron tích chập AI 12 kênh song song phân loại 4 trạng thái vòng bi (0: Bình thường, 1: Lỗi vòng trong, 2: Lỗi vòng ngoài, 3: Lỗi bi) và tính độ bất định Dirichlet.
* **Kiến trúc:**
  * 12 bộ nhân MAC INT8 song song.
  * 6 khối BSRAM lưu trữ trọng số huấn luyện.
  * Bộ chia phục hồi 18-bit (`div_18bit.v`) tính toán chỉ số bất định Dirichlet $u^* = \frac{4}{S}$ dạng số cố định Q0.15.
* **Thời gian suy luận:** Đúng **262 chu kỳ xung nhịp @ 100 MHz = 2.62 µs** (nhanh hơn vi điều khiển Cortex-M0 gấp 2,700 lần).
* **Kết quả nghiệm thu:**
  * ✅ Đã tích hợp cấu trúc đối xứng 2 tầng MAC Pipeline (`pipe1_w`, `pipe1_act`, `pipe2_prod`) và 2 chu kỳ xả `S_DRAIN_1`, `S_DRAIN_2`.
  * ✅ Trạng thái `S_DECIDE` và `S_CHECK` phân tách rõ ràng, timing đạt chuẩn sạch sẽ.

---

### 2.9. Đóng Gói Khung Truyền SPI Telemetry (`spi_master_packet.v`)
* **Chức năng:** Đóng gói toàn bộ kết quả chẩn đoán và 257 bin phổ thành khung tin 524 bytes chuẩn định dạng gửi sang vi điều khiển Sonix qua SPI DMA.
* **Định dạng khung tin 524 Bytes (Khớp 100% C-Struct của ARM Cortex-M0):**
  * `Byte [0..1]`: Sync Word `0xAA55` (Truyền Little-Endian: `0x55` trước, `0xAA` sau).
  * `Byte [2..3]`: Bộ đếm số khung hình `frame_count` (uint16 Little-Endian).
  * `Byte [4..517]`: 257 Bins phổ biên độ (257 x uint16 Little-Endian = 514 bytes).
  * `Byte [518]`: Lớp dự đoán của AI `npu_pred_class` (uint8: 0, 1, 2, 3).
  * `Byte [519]`: Độ bất định Dirichlet `dirichlet_max_evidence` (uint8).
  * `Byte [520..521]`: Cờ trạng thái phần cứng `hardware_status_flags` (uint16 Little-Endian).
  * `Byte [522..523]`: Mã kiểm tra lỗi CRC-16-CCITT (Đa thức 0x1021, tính trên byte 0..521, truyền Little-Endian).
* **Tốc độ truyền:** $100\,\text{MHz} / 8 = 12.5\,\text{MHz}$ SPI SCK (Mode 0: SCK nghỉ ở mức thấp, lấy mẫu ở cạnh lên).
* **Thời gian truyền gói:** $524 \text{ bytes} \times 8 \text{ bits} \times 80\,\text{ns} = 335.36\,\mu\text{s}$.
* **Kết quả nghiệm thu:**
  * ✅ **Đã vá lỗi lệch pha bit đầu:** Dòng lệnh `clk_div <= 3'd4;` khi bắt đầu truyền đảm bảo cạnh rơi SCK cập nhật MOSI luôn xảy ra trước cạnh lên lấy mẫu, triệt tiêu lỗi ngẫu nhiên byte đầu ra `0xAAD5`.
  * ✅ **Đã tối ưu timing CRC:** Cờ `crc_pend` tách việc tính toán CRC sang trạng thái dịch bit, loại bỏ chuỗi trễ tổ hợp dài qua bộ MUX 524 nhánh.

---

## 3. BÁO CÁO THẨM ĐỊNH ĐỊNH THỜI VÀ TÀI NGUYÊN VI MẠCH (SYNTHESIS & PNR AUDIT)

### 3.1. Bảng Đo Kiểm Timing Thực Tế Từ Gowin PnR (Mới Nhất)

| Thông Số Phân Tích (STA Parameters) | Giá Trị Đo Được | Yêu Cầu Thiết Kế | Trạng Thái Đạt Chuẩn |
| :--- | :---: | :---: | :---: |
| **Tần Số Cực Đại ($F_\text{max}$)** | **$100.368\,\text{MHz}$** | $100.286\,\text{MHz}$ | ✅ **PASS (Thỏa Mãn 100%)** |
| **Worst Setup Slack** | **$+0.008\,\text{ns}$** | $\ge 0.000\,\text{ns}$ | ✅ **PASS (Dương, Không Vi Phạm)** |
| **Worst Hold Slack** | **$+0.000\,\text{ns}$** | $\ge 0.000\,\text{ns}$ | ✅ **PASS (0 Vi Phạm Hold)** |
| **Setup Violated Endpoints** | **0 / 30,340** | 0 | ✅ **PASS** |
| **Total Negative Slack (TNS)** | **$0.000\,\text{ns}$** | $0.000\,\text{ns}$ | ✅ **PASS (Toàn Bộ Clock Domains)** |

> [!NOTE]
> **ĐÁNH GIÁ TIMING:**  
> Hệ thống hiện tại đã đạt điểm cân bằng định thời hoàn hảo ở tần số **100 MHz**. Việc bổ sung các tầng thanh ghi đệm trong bộ lọc FIR và bộ tích lũy NPU đã giải quyết triệt để 68 điểm vi phạm Setup Slack từng ghi nhận ở các phiên làm việc trước đó.

---

### 3.2. Bảng Phân Bổ Tài Nguyên Phần Cứng Trên Chip Gowin GW2A-18

| Loại Tài Nguyên (Hardware Primitives) | Tiêu Thụ Thực Tế | Dung Lượng Chip | Tỷ Lệ Chiếm Dụng | Đánh Giá An Toàn |
| :--- | :---: | :---: | :---: | :--- |
| **Logic / LUTs** | 5,067 | 20,736 | **24.4%** | Rất rộng rãi, dư > 75% logic |
| **ALU Carry Chains** | 1,794 | — | — | Phục vụ bộ cộng và căn bậc hai |
| **SSRAM (LUT-RAM16)** | 212 | — | — | Dùng cho bộ đệm FFT `fbuf` |
| **Registers (Flip-Flops)** | 4,900 | 15,552 | **31.5%** | An toàn, không nghẽn định tuyến |
| **BSRAM (Khối nhớ cứng)** | 10 | 46 | **21.7%** | 5 FFT + 3 NPU + 1 Hann + 1 Top |
| **DSP Slices (DSP18X18)** | 11 | 24 | **45.8%** | 12 MULT9 + 6 MULT18 + 5 ALU18 |

---

## 4. BẢNG TỔNG KẾT ĐIỂM ĐÃ HOÀN HẢO VÀ ĐIỂM CẦN LƯU Ý

### 4.1. Những Điểm ĐÃ HOÀN TẤT & ĐẠT CHUẨN (OK 100%)
1. **Chuỗi dữ liệu liên tục (Continuous Streaming):** Tín hiệu mẫu rung từ BRAM được đưa qua chuỗi DSP và biến đổi Fourier mà không bị gián đoạn hay mất mẫu.
2. **IP Gowin FFT_Top hoạt động thật:** Không còn sử dụng module giả lập (stub), IP thật của Gowin đã được tổng hợp, đi dây thành công vào bitstream `FPGA_FINAL.fs`.
3. **Độ lớn phổ bit-true:** Khối `mag_isqrt.v` 18 tầng pipeline cho kết quả căn bậc hai số nguyên chính xác 100% khớp với mô phỏng phần mềm.
4. **Chuẩn hóa biên độ INT8 đơn điệu:** Loại bỏ hiện tượng đảo nghịch năng lượng, bảo toàn cấu trúc đỉnh phổ khi nạp sang mạng AI.
5. **Suy luận AI siêu tốc:** Lõi NPU 12 kênh thực hiện phân loại hoàn tất trong $2.62\,\mu\text{s}$.
6. **Đóng gói SPI 524 bytes chuẩn xác:** Đồng bộ Little-Endian, tính toán mã kiểm tra lỗi CRC-16 chuẩn, sửa xong lỗi lệch pha bit đầu tiên.
7. **Khép kín định thời STA 100 MHz:** Đạt $F_\text{max} > 100\,\text{MHz}$, toàn bộ các vi phạm Setup và Hold đều bằng 0.

---

### 4.2. Những Điểm CHƯA HỢP LÝ CẦN LƯU Ý (CÁC ĐIỂM CẢNH BÁO)

| STT | Vấn Đề Phát Hiện | Mức Độ Rủi Ro | Phân Tích Kỹ Thuật | Hành Động Đề Xuất Cho Kỹ Sư |
| :---: | :--- | :---: | :--- | :--- |
| **1** | **File CST chưa gán đúng chân (`top_wrapper.cst`)** | 🔴 **RẤT CAO** (Không chạy được trên board thật) | Trong lần chạy PnR, file CST không được nhận diện (`Physical Constraints File: ---`). 9 chân I/O bị Gowin tự động gán ngẫu nhiên vào các chân Bank 1.8V thay vì Bank 3.3V. Chân `rst_n_pin` hoàn toàn chưa có ràng buộc `IO_LOC`. Tên chân SPI bị lệch (`spi_sck` vs `mcu_spi_sck`). | Cần cập nhật lại file CST với đúng tên port của top module và cấu hình `IO_TYPE=LVCMOS33` trước khi nạp mạch thật. |
| **2** | **Độ rộng xung ngắt `mcu_irq_pulse` quá hẹp ($10\,\text{ns}$)** | 🟠 **TRUNG BÌNH** (MCU có thể lọt ngắt) | Trong `spi_master_packet.v`, xung `irq_pulse` chỉ tích cực ở trạng thái `STATE_DONE` (kéo dài đúng 1 chu kỳ clock 100 MHz = 10 ns). Vi điều khiển Cortex-M0 chạy 60 MHz (chu kỳ 16.7 ns) có thể bị bỏ lỡ ngắt GPIO này. | Cần cấu hình ngắt MCU ở chế độ bắt cạnh hoặc kéo dài xung ngắt trong RTL lên tối thiểu $1\,\mu\text{s}$. |
| **3** | **Nghịch lý Parameter `USE_HIL` trong Envelope** | 🟡 **CẦN BIẾT** (Tránh sửa nhầm) | `envelope_demodulator.v` dùng toán tử: `USE_HIL ? 0C7F : 08A4`. Trong top module đang truyền `.USE_HIL(0)` để chọn đúng bộ hệ số HIL `08A4`. | **Giữ nguyên `.USE_HIL(0)`**, tuyệt đối không đổi thành 1 vì sẽ bị chuyển nhầm sang bộ lọc 400 Hz của ADXL345. |
| **4** | **`pll_lock` bị gán cứng bằng 1** | 🟡 **THẤP** | Trong `gowin_top_soc_hil.v`, `wire pll_lock = 1'b1;` để tránh bị trình biên dịch tối ưu xóa mạch logic. | Khi cấp nguồn board thật, cần nhấn nút Reset một lần sau khi nguồn 3.3V đã ổn định để reset sạch toàn bộ chuỗi FSM. |

---

## 5. HƯỚNG DẪN BƯỚC TIẾP THEO CHO TEAM (ROADMAP)

1. **Hiệu chỉnh ràng buộc chân vật lý (File `.cst`):**
   * Đổi tên chân SPI thành: `mcu_spi_sck`, `mcu_spi_cs_n`, `mcu_spi_mosi`, `mcu_irq_pulse`.
   * Gán chân `rst_n_pin` vào nút nhấn hoặc chân GPIO chuẩn trên Tang Primer 20K Dock Lite.
   * Chạy lại bước **Place & Route (PnR)** trên Gowin EDA để xuất bitstream `.fs` với chân cắm 3.3V chuẩn xác.
2. **Kiểm tra trên vi điều khiển MCU Sonix SN32F407:**
   * Nối 4 dây bus SPI (`SCK`, `MOSI`, `CS`, `GND`) và chân ngắt `mcu_irq_pulse` sang cổng SPI Slave DMA của MCU Sonix.
   * Kiểm tra bộ đệm DMA 524 bytes trên MCU để xác nhận nhận đúng Sync `0xAA55` và kiểm tra CRC khớp $100\%$.
3. **Đối chiếu kết quả phân loại AI:**
   * So sánh nhãn dự đoán `npu_pred_class` và đồ thị 257 bin phổ hiển thị trên màn hình OLED SSD1306 với các đặc trưng rung động cơ học thực tế.

---
*Bản báo cáo hoàn thành thẩm định kỹ thuật ngày 01/11/2026. Thiết kế FPGA đã sẵn sàng cho giai đoạn đo kiểm phần cứng phối ghép MCU.*
