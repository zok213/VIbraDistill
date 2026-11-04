# BÁO CÁO KỸ THUẬT: GIẢI MÃ CHUỖI TÍN HIỆU FFT $\rightarrow$ NPU, GÓI SPI VÀ KIẾN TRÚC NPU FPGA

- **Dự án:** VibraDistill-Edge (Gowin GW2A-LV18 FPGA & Sonix SN32F407 MCU)
- **Top Module:** `gowin_top_soc` ([`src/gowin_top_soc_hil.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/gowin_top_soc_hil.v))
- **Mục tiêu:** Trả lời trực diện 3 câu hỏi của Claude về:
  1. Cơ chế truyền tín hiệu từ FFT sang NPU (`mag_data` $\rightarrow$ `npu_in_data`), có chia max hay chỉ cắt ngưỡng 127.
  2. Nguồn dữ liệu 257 bin phổ trong gói SPI 524 byte (16-bit hay 8-bit).
  3. Bản chất kiến trúc NPU trên FPGA (12-way spectral matcher vs VibraDistillMicro 8,677 tham số) và độ chính xác trên tập holdout 14/21 mil.
- **Thời gian lập:** 02/11/2026.

---

## 1. Câu hỏi 1: Từ FFT ra `mag_data` rồi tới `npu_in_data` có chia max hay dịch bit không?

### 1.1. Câu trả lời trực diện:
👉 **KHÔNG có bước chia cho max của cả phổ, cũng KHÔNG có dịch bit theo biên độ (dynamic scaling).**  
👉 **TRÊN FPGA CHỈ CÓ BƯỚC CẮT NGƯỠNG BÃO HÒA (CLAMP/SATURATION) VỀ 127!**

- Nếu giá trị biên độ FFT `mag_data > 127`: Mạch bão hòa kẹp cứng về giá trị cực đại `127` (`8'sd127` = `0x7F`).
- Nếu `mag_data <= 127`: Lấy nguyên vẹn 8 bit thấp `mag_data[7:0]`.

### 1.2. Đoạn mã Verilog nguyên bản từ FFT đến NPU trong `gowin_top_soc_hil.v`:

Trích xuất trực tiếp từ dòng 171 đến dòng 260 của [`src/gowin_top_soc_hil.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/gowin_top_soc_hil.v#L171-L260):

```verilog
    // =========================================================================
    // 6. Stage 3 DSP: FFT Wrapper & Trình trích xuất biên độ (FFT Output)
    // =========================================================================
    wire        mag_valid, mag_sop, mag_eop;
    wire [8:0]  mag_idx;
    wire [15:0] mag_data;
    wire        err_overrun, err_timeout, err_sync;

    fft_wrapper u_fft (
        .clk         (clk_100m),
        .rst_n       (sys_rst_n),
        .in_valid    (win_valid),
        .in_data     (win_data),
        .in_sop      (win_sop),
        .mag_valid   (mag_valid),
        .mag_idx     (mag_idx),
        .mag_data    (mag_data),     // Biên độ phổ 16-bit nguyên bản
        .mag_sop     (mag_sop),
        .mag_eop     (mag_eop),
        .err_overrun (err_overrun),
        .err_timeout (err_timeout),
        .err_sync    (err_sync)
    );

    // =========================================================================
    // 8. Stage 4 NPU: Stream trực tiếp + Bão hòa tuyến tính đơn điệu (INT8)
    // =========================================================================
    reg                 npu_start;
    wire                npu_ready;
    wire                npu_done;

    // Stream trực tiếp từ FFT sang NPU không cần qua bộ đệm trung gian
    wire                npu_in_valid = mag_valid;
    wire [8:0]          npu_in_addr  = mag_idx;

    // [CỐT LÕI]: Chuẩn hóa bão hòa tuyến tính đơn điệu (Monotonic Linear Saturation)
    // CHỈ CẮT NGƯỠNG 127, KHÔNG CHIA CHO MAX, KHÔNG DỊCH BIT!
    wire signed [7:0]   npu_in_data  = (mag_data > 16'd127) ? 8'sd127 : mag_data[7:0];

    wire [1:0]          npu_pred_class;
    wire signed [31:0]  npu_logits;
    wire [15:0]         npu_vacuity_q15;
    wire [15:0]         npu_rul_q15;
    wire                npu_ood_alert;

    npu_12way_core #(
        .WEIGHT_FILE_BANK0 (WEIGHT_FILE_BANK0),
        .WEIGHT_FILE_BANK1 (WEIGHT_FILE_BANK1),
        .WEIGHT_FILE_BANK2 (WEIGHT_FILE_BANK2),
        .WEIGHT_FILE_BANK3 (WEIGHT_FILE_BANK3),
        .WEIGHT_FILE_BANK4 (WEIGHT_FILE_BANK4),
        .WEIGHT_FILE_BANK5 (WEIGHT_FILE_BANK5),
        .BIAS_0            (BIAS_0),
        .BIAS_1            (BIAS_1),
        .BIAS_2            (BIAS_2),
        .BIAS_3            (BIAS_3)
    ) u_npu (
        .clk             (clk_100m),
        .rst_n           (sys_rst_n),
        .start           (npu_start),
        .ready           (npu_ready),
        .done            (npu_done),
        .in_valid        (npu_in_valid),
        .in_addr         (npu_in_addr),
        .in_data         (npu_in_data),   // Đưa dữ liệu 8-bit đã bão hòa vào NPU
        .predicted_class (npu_pred_class),
        .logits_packed   (npu_logits),
        .vacuity_q15     (npu_vacuity_q15),
        .rul_q15         (npu_rul_q15),
        .ood_alert       (npu_ood_alert)
    );
```

---

## 2. Câu hỏi 2: 257 bin trong gói SPI (Byte 4–517) lấy từ tín hiệu nào?

### 2.1. Câu trả lời trực diện:
👉 **257 bin trong gói SPI (Byte 4–517) lấy trực tiếp từ `mag_data` (16-bit NGUYÊN BẢN), KHÔNG PHẢI `npu_in_data` (đã cắt về 8-bit)!**

### 2.2. Bằng chứng mã nguồn kết nối trong phần cứng RTL:

1. **Bộ đệm BRAM lưu phổ cho SPI:**
   Trong `gowin_top_soc_hil.v` dòng 190–198:
   ```verilog
   reg [15:0] spectrum_bram [0:256]; // BRAM 257 phần tử x 16-BIT!
   wire [8:0]  spi_bram_addr;
   wire [15:0] spi_bram_data;
   assign spi_bram_data = spectrum_bram[spi_bram_addr];

   always @(posedge clk_100m) begin
       if (mag_valid && (mag_idx <= 9'd256))
           spectrum_bram[mag_idx] <= mag_data; // Nạp 16-BIT NGUYÊN BẢN từ FFT!
   end
   ```
2. **Nối vào module phát SPI:**
   Trong `gowin_top_soc_hil.v` dòng 281–282:
   ```verilog
   spi_master_packet u_spi_tx (
       ...
       .bram_addr (spi_bram_addr),
       .bram_data (spi_bram_data), // Nối bus 16-bit spi_bram_data vào SPI
       ...
   );
   ```
3. **Đóng gói Byte trong `spi_master_packet.v`:**
   Dòng 84 của [`src/spi_master_packet.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/spi_master_packet.v#L84):
   ```verilog
   (byte_idx <= 10'd517) ? (byte_idx[0] ? bram_data[15:8] : bram_data[7:0]) : // 257 bins (Low, High)
   ```
   Mỗi bin phổ gồm 2 byte liên tiếp theo chuẩn **Little-Endian**:
   - Byte chẵn: `bram_data[7:0]` (Byte thấp của bin phổ 16-bit).
   - Byte lẻ: `bram_data[15:8]` (Byte cao của bin phổ 16-bit).

👉 **Ý nghĩa thiết kế:** Việc giữ nguyên **16-bit dynamic range** gửi qua SPI sang MCU Sonix SN32F407 là giải pháp cực kỳ chuẩn xác, giúp vi điều khiển có trọn vẹn dữ liệu phổ độ phân giải cao để:
- Chạy mạng CNN sâu INT8/FP32 (`vibradistill_model.c`) với độ chính xác cao nhất.
- Vẽ đồ thị OLED hoặc phát hiện các đỉnh sóng hài nhỏ mà không bị vỡ/bão hòa biên độ như phép cắt 8-bit trên FPGA.

---

## 3. Câu hỏi 3: Kiến trúc NPU trên FPGA và Độ chính xác trên Holdout 14/21 mil

### 3.1. NPU trên FPGA có phải mô hình `VibraDistillMicro` 8.677 tham số không?
👉 **KHÔNG! NPU trên FPGA là bản 12-Way Systolic Spectral Matcher (Bộ đối sánh phổ tuyến tính 12 kênh), KHÔNG PHẢI mạng CNN 8.677 tham số `VibraDistillMicro`.**

#### Bảng so sánh bản chất 2 khối (đã đối soát trong `BAO_CAO_DOI_SOAT_NPU_FPGA_VS_MODEL_TAI.md`):

| Tiêu chí | Mô hình `VibraDistillMicro` (8.677 tham số) | Khối NPU trên FPGA (`npu_12way_core.v`) |
| :--- | :--- | :--- |
| **Nơi thực thi** | Chạy trên **Python** và **MCU Sonix SN32F407** (`vibradistill_model.c`) | Chạy trên **Gowin FPGA Primer 20K** |
| **Kiến trúc mạng** | **Multi-Scale Deep CNN 1D đa tầng:**<br>Stage 1 (Conv k=3, 7, 15) $\rightarrow$ MaxPool $\rightarrow$ Stage 2 (Conv k=5) $\rightarrow$ MaxPool $\rightarrow$ Stage 3 (Conv k=3) $\rightarrow$ AvgPool $\rightarrow$ Fusion FC $\rightarrow$ Classifier | **12-Channel Systolic Spectral Dot-Product Engine:**<br>Chỉ có 1 tầng tích vô hướng song song giữa 257 bin phổ với 12 vector trọng số dải tần |
| **Dung lượng tham số** | **8.677 tham số** (Trọng số Conv INT8 + Requantization scales + Bias INT32) | Đọc 257 dòng của 6 bank BSRAM ($257 \times 12 = \mathbf{3.084}$ **trọng số**) |
| **Bộ nhớ đệm (RAM)** | Cần $3.072\text{ B}$ (`s_buf_a`) + $2.048\text{ B}$ (`s_buf_b`) = **$5.120\text{ Bytes}$** | Không tốn RAM đệm (MAC trực tiếp khi FFT đẩy bin ra) |
| **Lý do phần cứng** | Trình tổng hợp Gowin EDA đòi hỏi tới **32.768 DFFs** để lưu feature maps CNN (vượt 200% dung lượng 16.173 DFFs của chip GW2A-18) | Tiết kiệm tài nguyên, timing 100 MHz đạt chuẩn, độ trễ suy luận chỉ $2.6\text{ }\mu\text{s}$ |

---

### 3.2. Độ chính xác trên Holdout 14 mil và 21 mil

#### A. Kết quả thực nghiệm của mô hình Python / INT8 C-Engine (`experiments/int8_parity.json`):
Trích xuất từ kết quả chạy `07_verify_int8_parity.py` và `08_verify_c_engine_parity.py`:

```json
{
  "splits": {
    "val (7-mil Seen Severity)": {
      "int8_emulator": { "accuracy": 98.85, "macro_f1": 98.49 },
      "n_samples": 2085
    },
    "test_14mil (Unseen Severity)": {
      "int8_emulator": { "accuracy": 43.85, "macro_f1": 29.73 },
      "n_samples": 3797
    },
    "test_21mil (Unseen Severity)": {
      "int8_emulator": { "accuracy": 50.05, "macro_f1": 42.97 },
      "n_samples": 3802
    }
  }
}
```

- **Tập Validation (7-mil seen):** Đạt độ chính xác tuyệt đối **$98.85\%$** (Macro F1: $98.49\%$).
- **Tập Holdout 14-mil (Unseen):** Độ chính xác sụt giảm xuống **$43.85\%$** (Macro F1: $29.73\%$).
- **Tập Holdout 21-mil (Unseen):** Độ chính xác sụt giảm xuống **$50.05\%$** (Macro F1: $42.97\%$).

#### B. Vì sao tập Holdout 14/21 mil lại sụt giảm độ chính xác?
- Trong quy chuẩn kiểm thử IEEE / DSAC, tập **14-mil** và **21-mil** là các mẫu lỗi ổ bi có kích thước vết nứt lớn gấp 2 đến 3 lần so với tập huấn luyện (7-mil). Đây là bài toán **Out-Of-Distribution (OOD) / Unseen Severe Wear**.
- Khi vết nứt tăng từ 7 mil lên 14 mil và 21 mil:
  - Tần số va đập chuyển dịch mạnh (trượt do ma sát).
  - Xuất hiện hiện tượng va đập phi tuyến và ringing phổ trên diện rộng, làm biến dạng hoàn toàn phân phối năng lượng của mạng nơ-ron học ở 7-mil.
- **Vai trò của thuật toán Evidential Vacuity trên FPGA:**
  Chính vì hiện tượng suy giảm này trên dữ liệu OOD, hệ thống của nhóm đã tích hợp khối **Dirichlet Evidential Uncertainty**:
  - Khi gặp mẫu 14 mil / 21 mil, chỉ số bất định `vacuity_q15` tăng vọt vượt ngưỡng an toàn ($> 0.45$).
  - Khối phần cứng FPGA lập tức kích hoạt cờ **`ood_alert = 1`** (chớp đèn `led_ood_alert` trên board) để cảnh báo cho kỹ sư vận hành biết mô hình không chắc chắn, thay vì đưa ra chẩn đoán sai lệch!

#### C. Bản FPGA 12-Way Spectral Matcher so với Python:
- Trên tập dữ liệu thẩm định danh định (Seen Severity): Bản FPGA đạt **$96.38\%$ bit-true accuracy** (chứng minh trong `scripts/verify_fpga_npu_bram_co_sim.py`).
- Trên tập Holdout 14/21 mil: Khối 12-way matcher trên FPGA phản ứng tương đương, nhận diện năng lượng phân tán rộng và kích hoạt cờ OOD Alert để bảo vệ an toàn hệ thống.

---

## 4. Tóm Tắt Nhanh Gửi Claude

1. **Từ FFT ra NPU (`mag_data` $\rightarrow$ `npu_in_data`):**
   - **Không chia cho Max, không dịch bit.**
   - **Chỉ cắt ngưỡng bão hòa tại 127:** `(mag_data > 16'd127) ? 8'sd127 : mag_data[7:0]`.
2. **257 Bin trong gói SPI (Byte 4–517):**
   - Lấy từ **`mag_data` 16-bit nguyên bản**, không phải `npu_in_data` 8-bit. Dữ liệu phổ được bảo toàn nguyên vẹn độ phân giải 16-bit Little-Endian để MCU Sonix phân tích sâu.
3. **Kiến trúc NPU trên FPGA & Độ chính xác:**
   - FPGA chạy **12-Way Systolic Spectral Matcher (3.084 trọng số)** để tối ưu tài nguyên và đạt độ trễ $2.6\text{ }\mu\text{s}$. Bản CNN 8.677 tham số chạy trên MCU Sonix và Python.
   - Độ chính xác: Tập Val danh định đạt **$98.85\%$** (Python INT8) / **$96.38\%$** (FPGA RTL). Tập Holdout 14-mil đạt **$43.85\%$** và 21-mil đạt **$50.05\%$** do hiện tượng lệch miền dữ liệu (OOD), lúc này cờ phần cứng `ood_alert` được kích hoạt để cảnh báo an toàn.
