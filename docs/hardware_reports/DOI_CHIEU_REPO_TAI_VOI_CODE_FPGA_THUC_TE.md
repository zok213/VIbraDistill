# BẢN ĐỐI CHIẾU KỸ THUẬT: TÀI LIỆU REPO CỦA TÀI (BRANCH TAI) VS MÃ NGUỒN FPGA THỰC TẾ
## Dự án: VibraDistill-Edge (Tang Primer 20K & MCU Sonix SN32F407)
**Thời điểm thực hiện:** 01/11/2026  
**Mục đích:** Chỉ rõ toàn bộ các điểm **MÂU THUẪN, SAI LỆCH KHÁI NIỆM, VÀ ĐIỂM KHÁC BIỆT** giữa tài liệu README/báo cáo của Tài (`zok213/porygon at tai`) với mã nguồn Verilog RTL thực tế đang chạy trong thư mục `t:\MCU_FPGA\FPGA_FINAL\`.  
**Nguyên tắc:** Độc bản kiểm toán kỹ thuật — TUYỆT ĐỐI KHÔNG CHỈNH SỬA CODE RTL.

---

> [!IMPORTANT]
> **THÔNG ĐIỆP CỐT LÕI CHO KỸ SƯ / HỘI ĐỒNG PHẢN BIỆN:**  
> Tài liệu README của Tài có nhiều điểm **lý tưởng hóa, gom số liệu một phần gán cho toàn bộ hệ thống, và tồn tại những mâu thuẫn vật lý rõ rệt** so với bản chất vi mạch đang chạy trên FPGA.  
> Bản đối chiếu này giúp bạn nắm được bản chất kỹ thuật thật sự đằng sau để trả lời phản biện tự tin, chính xác, không bị rơi vào "bẫy số liệu" của README.

---

## BẢNG MA TRẬN ĐỐI CHIẾU TRỰC DIỆN (DIRECT COMPARISON MATRIX)

| Hạng Mục Kỹ Thuật | Tuyên Bố Trong README Của Tài | Thực Tế Trong Code RTL & Gowin PnR Của Toàn | Đánh Giá Bản Chất Kỹ Thuật |
| :--- | :--- | :--- | :--- |
| **1. Khối Vector Động Học 8 Chiều (④ DSP_KIN)** | Sơ đồ Mermaid và mục III khẳng định có khối `DSP_KIN` trích xuất 8 đặc trưng hài ($BPFO_{1x,2x}, BPFI_{1x,2x}, BSF, FTF$) đưa vào NPU. | **HOÀN TOÀN KHÔNG CÓ.** Tín hiệu từ FFT/ISQRT đi thẳng 100% vào NPU. 4 ô nhớ `prior_mem` trong NPU không bao giờ được đọc (Dead Code). | **README sai sự thật.** Hệ thống phân loại thuần túy dựa trên 257 bin phổ FFT, không hề có trích xuất đặc trưng động học 8 chiều nào trên FPGA. |
| **2. Độ trễ toàn hệ thống (End-to-End Latency)** | Ghi: **`0.75 ms`** (đo trên DSO Rigol DS1054Z từ TP1 đến TP2), "nhanh gấp 6.6 lần chuẩn SIL-2 $\le 5.0\,\text{ms}$". | Thời gian gom 512 mẫu ở $F_s = 12\,\text{kHz}$ là **$42.67\,\text{ms}$** (với ADXL345 $3.2\,\text{kHz}$ là **$160\,\text{ms}$**). | **Ngụy biện khái niệm.** $0.75\,\text{ms}$ thực chất chỉ là trễ suy luận + truyền SPI sau khi đã có sẵn khung FFT. Tổng trễ vật lý từ khi rung đến khi ngắt phải là **$> 43.4\,\text{ms}$**. |
| **3. Tài nguyên Flip-Flop (DFF)** | "Tài nguyên Flip-Flop tiêu thụ chỉ **< 750 DFFs (< 4.5% dung lượng chip)**". | Báo cáo Gowin PnR: **4,900 / 15,552 DFFs (31.5%)**. | **Gom số bộ phận gán cho toàn thể.** Con số $< 750$ DFF thực chất chỉ đo riêng lõi `npu_12way_core.v`. Toàn bộ SoC (FIR, Hann, FFT, ISQRT, SPI) tốn gần 5,000 DFFs. |
| **4. Tài nguyên DSP Blocks** | Mục 1 ghi: "12 DSP18E slices (25.0%)". Nhưng bảng VI lại ghi: "41% DSPs". | Báo cáo Gowin PnR: **11 / 24 slices (45.8%)** (chứa 12 MULT9x9, 6 MULT18x18, 5 MULTADDALU). | README của Tài tự mâu thuẫn giữa mục 1 và bảng VI. Số thực tế là 11 slices (45.8%). |
| **5. Bộ lọc FIR: Tần số cắt & Pha cực tiểu** | Ghi: "Passband $2000 - 5000\,\text{Hz}$, Group delay $3.2$ mẫu, Minimum-Phase causal, zero pre-cursor ringing". | Đỉnh khuếch đại nằm ở **$720 - 800\,\text{Hz}$ (+15 dB)**. Trong dải 2–5 kHz bị suy hao $-7$ đến $-17\,\text{dB}$. Có **29/31 nghiệm zero nằm ngoài vòng tròn đơn vị** ($|z|>1$). | **Sai lệch lý thuyết DSP.** Bộ lọc thực tế là Non-Minimum Phase (trễ nhóm $\approx 20$ mẫu). Không chặn DC. Cắt bit $y[30:15]$ không bão hòa gây nguy cơ wrap-around nếu biên độ đỉnh $> 26,000$. |
| **6. Envelope Demodulator** | Tuyên bố: "Causal Leaky Demodulator $y = \max(\|x\|, y - (y \gg 6))$" và "Cutoff 1000 Hz @ 13.333 kHz". | Code là **IIR Butterworth bậc 2**. Hệ số $A_1 = -1.142981$ không biểu diễn được trong Q1.15, mã hex `0x96E8` ra $-0.821$, độ lợi DC chỉ $0.457$, cắt ở $\approx 2437\,\text{Hz}$. | README mô tả một đằng, RTL làm một nẻo. Hệ số nhánh HIL bị méo toán học do ép kiểu Q1.15. |
| **7. Tham số `USE_HIL`** | README không đề cập đến việc đảo ngược tham số. | Code top SoC bắt buộc phải gán: `.USE_HIL(0)` thì mới ăn vào nhánh hệ số HIL công nghiệp! | Do người viết copy từ code cũ dùng `USE_ADXL345` nhưng không đảo vế toán tử ba ngôi `? :`. |
| **8. Ràng buộc chân vật lý CST (`.cst`)** | Ghi rõ ràng các chân PMOD và GPIO cho Tang Primer 20K. | File `top_wrapper.cst` trong project bị lệch tên cổng (`spi_*` thay vì `mcu_spi_*`), thiếu `rst_n_pin`. Gowin PnR bỏ qua CST, gán vào chân 1.8V ngẫu nhiên! | **Lỗi chưa hoàn thiện cấu hình.** Nếu nạp bitstream hiện tại xuống board thật sẽ không chạy được giao tiếp ngoại vi. |
| **9. Tín hiệu ngắt `mcu_irq_pulse`** | Ghi: "Kích ngắt SPI DMA sang MCU". | Xung ngắt trong RTL chỉ kéo dài đúng **1 chu kỳ clock 100 MHz (10 ns)**. | **Rủi ro MCU bỏ lỡ ngắt.** Cortex-M0 @ 60 MHz (chu kỳ 16.7 ns) không thể bắt chắc chắn xung 10 ns nếu MCU không cấu hình ngắt cạnh đặc biệt. |
| **10. Định dạng Trọng số NPU** | Liệt kê cả file `.mem` 7,880 B, 8.47 KB và 6 file `.hex`. | RTL `npu_12way_core.v` chỉ nhận duy nhất **6 file `npu_weights_bank0..5.hex`** (mỗi file 257 dòng x 16-bit). | Không dùng được các file `.mem` thống nhất nếu không sửa lại kiến trúc đọc 6 bank BSRAM trong Verilog. |

---

## PHÂN TÍCH CHI TIẾT TỪNG MÂU THUẪN TRỌNG YẾU

---

### 1. ẢO TƯỞNG VỀ "END-TO-END LATENCY 0.75 MS"
* **Tài viết:** Đo trễ từ TP1 (DRDY) đến TP2 (P1.0 Trip) là $0.75\,\text{ms}$, thỏa mãn IEC 61508 SIL-2 $(< 1.0\,\text{ms})$.
* **Thực tế kỹ thuật:**
  * Khối biến đổi Fourier bắt buộc phải gom đủ một cửa sổ $N = 512$ mẫu thời gian thì mới thực hiện biến đổi sang miền tần số được.
  * Với tốc độ lấy mẫu chuẩn công nghiệp $F_s = 12\,\text{kHz}$:
    $$T_\text{window} = \frac{512}{12,000\,\text{Hz}} = 42.667\,\text{ms}$$
  * Với cảm biến thực tế ADXL345 chạy ở $F_s = 3,200\,\text{Hz}$:
    $$T_\text{window} = \frac{512}{3,200\,\text{Hz}} = 160.0\,\text{ms}$$
  * **Kết luận:** Con số $0.75\,\text{ms}$ mà Tài công bố **chỉ là thời gian phản ứng cục bộ (Processing & Transmission Latency)** tính từ khi mẫu thứ 512 vừa vào chip cho tới khi MCU nhận xong gói SPI. Tổng thời gian trễ thực sự từ lúc hiện tượng rung xuất hiện đến khi rơ-le ngắt nguồn phải là:
    $$T_\text{total} = 42.67\,\text{ms} + 0.75\,\text{ms} \approx \mathbf{43.42\,\text{ms}}$$
  * *Lời khuyên khi phản biện:* Hãy giải thích rõ ràng với Giám khảo rằng: **"0.75 ms là Hardware Processing Latency của lõi FPGA + SPI DMA, còn Physical Sampling Latency là 42.7 ms do giới hạn vật lý của cửa sổ 512 mẫu ở 12 kHz."** Điều này thể hiện sự am hiểu sâu sắc về mặt bản chất kỹ thuật.

---

### 2. SỰ THẬT VỀ KHỐI "VECTOR ĐỘNG HỌC 8 CHIỀU" (DSP_KIN)
* **Tài viết:** Có khối ④ tính toán 8 đặc trưng động học ($BPFO, BPFI, BSF, FTF$) kết hợp cùng phổ FFT để nạp vào NPU.
* **Thực tế trong code Verilog:**
  * File top [`gowin_top_soc_hil.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/gowin_top_soc_hil.v) nối trực tiếp đầu ra biên độ `mag_isqrt` sang NPU:
    ```verilog
    wire npu_in_valid = mag_valid;
    wire [8:0] npu_in_addr = mag_idx;
    wire signed [7:0] npu_in_data = (mag_data > 16'd127) ? 8'sd127 : mag_data[7:0];
    ```
  * Không có bất kỳ bộ tính toán tần số động học nào tồn tại giữa FFT và NPU.
  * Trong [`npu_12way_core.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/npu_12way_core.v), mảng `prior_mem[0:3]` chỉ được ghi dữ liệu vào nếu `in_addr >= 257`, nhưng FSM của NPU chỉ quét qua `bsram_addr` từ $0 \dots 256$ để nhân với `spectrum_mem`. Các giá trị trong `prior_mem` hoàn toàn không tham gia vào phép tính tích lũy `accum` hay phân loại lớp!
  * *Kết luận:* Mô hình AI đang chạy thực tế trên FPGA là **mạng NPU tích chập phổ 1 chiều (1D Spectral CNN/MLP) trên 257 bin tần số**, KHÔNG PHẢI mô hình lai ghép tri thức động học (Physics-Informed Neural Network) như README quảng bá.

---

### 3. NGHỊCH LÝ ĐÁP ỨNG TẦN SỐ CỦA BỘ LỌC FIR HIL (`fir_minphase_32.v`)
* **Tài viết:** Bộ lọc thông dải $2000 - 5000\,\text{Hz}$, pha cực tiểu (Minimum-Phase).
* **Thực tế toán học:**
  * Bảng 32 hệ số trong RTL cho thấy đây là một bộ lọc có hình dạng kỳ lạ:
    * Thay vì suy hao dải thấp, nó có **độ lợi đỉnh $+15\,\text{dB}$ tại dải $720 - 800\,\text{Hz}$** (khuếch đại tín hiệu vùng này lên gấp $5.7$ lần).
    * Tại dải $2000 - 5000\,\text{Hz}$ (dải mà README bảo là passband), độ lợi thực tế lại bị suy hao từ $-7\,\text{dB}$ đến $-17\,\text{dB}$!
    * Có 29 trên tổng số 31 nghiệm zero nằm ngoài vòng tròn đơn vị.
  * *Hệ quả:* Bộ lọc này hoạt động như một bộ lọc thông thấp tăng cường dải dưới $1\,\text{kHz}$ hơn là bộ lọc thông dải 2–5 kHz.
  * **Tại sao AI vẫn đạt độ chính xác cao?** Vì mạng NPU của Tài đã được huấn luyện (train) trực tiếp trên tập dữ liệu đã chạy qua chính bộ lọc kỳ dị này! Nói cách khác, AI đã học thuộc lòng các đặc trưng méo dạng tạo ra bởi bộ lọc này, nên khi chạy trên phần cứng nó vẫn nhận dạng đúng, nhưng bản chất vật lý của bộ lọc thì hoàn toàn sai lệch so với mô tả trong README.

---

### 4. BỘ ĐỆM PHỔ VÀ TRUY XUẤT BRAM (SSRAM VS BSRAM)
* **Tài viết:** "Toàn bộ mảng đệm trung gian 5.1 KB đã được chuyển thành streaming trực tiếp; ZERO DFF Buffer Overflow, 6 BSRAM blocks".
* **Thực tế Gowin PnR:**
  * Gowin tổng hợp sử dụng **10 BSRAM blocks** (chứ không phải 6).
  * Bộ đệm khung FFT `fbuf [0:511]` trong `fft_wrapper.v` và mảng phát mẫu `stim_bram [0:511]` do được viết theo dạng đọc tổ hợp bất đồng bộ (`assign xn_re = fbuf[fft_idx]`), nên Gowin Synthesis đã suy luận chúng thành **212 ô SSRAM (LUT-RAM)** thay vì BSRAM cứng!
  * Điều này làm tiêu tốn thêm tài nguyên logic LUT, nhưng đổi lại giúp thỏa mãn giao thức bắt tay của IP Gowin FFT mà không bị trượt 1 chu kỳ đọc.

---

## TỔNG KẾT BÀN GIAO: BẠN CẦN LÀM GÌ TIẾP THEO?

1. **Về mặt Logic & Timing:**  
   Code hiện tại trong thư mục của bạn (`FPGA_FINAL`) **ĐÃ TỐT HƠN BẢN TRONG README CỦA TÀI**. Code của bạn đã vá được lỗi lệch pha bit đầu SPI (`clk_div <= 3'd4`), vá lỗi răng cưa biên độ (`mag > 127`), và đặc biệt là **đã đóng timing thành công ở 100.368 MHz** với 0 lỗi Setup/Hold.
2. **Về mặt Nạp Phần Cứng Thật:**  
   Đừng tin vào file CST trong README của Tài. Hãy sửa file [`top_wrapper.cst`](file:///t:/MCU_FPGA/FPGA_FINAL/src/top_wrapper.cst) của chính bạn:
   * Sửa tên 3 chân SPI thành `mcu_spi_sck`, `mcu_spi_cs_n`, `mcu_spi_mosi`.
   * Gán chân cho `rst_n_pin` (ví dụ chân T10 trên board).
   * Xóa bỏ các chân thừa không có trong top module HIL (`adxl_*`, `uart_txd`).
3. **Về mặt Hồ Sơ Báo Cáo & Phản Biện:**  
   Sử dụng các số liệu thực tế được kiểm toán trong file này (100.368 MHz, 4,900 DFFs, 10 BSRAMs, trễ tính toán 0.75 ms + trễ lấy mẫu 42.7 ms) để giải trình. Sự trung thực và chính xác về mặt kỹ thuật vi mạch này sẽ ghi điểm tuyệt đối trước Ban giám khảo chuyên môn FPGA/ASIC.

---
*Bản đối chiếu kỹ thuật được lập ngày 01/11/2026 bởi hệ thống kiểm định vi mạch Antigravity.*
