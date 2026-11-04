# BÁO CÁO KỸ THUẬT: ĐỐI SOÁT VECTOR KIỂM THỬ COSIM_GOLDEN VÀ ĐỊNH DẠNG GÓI TIN SPI 524-BYTE

- **Dự án:** VibraDistill-Edge (Thiết bị chẩn đoán rung động vòng bi thời gian thực)
- **Đối tượng:** Khối NPU Gowin FPGA (`npu_12way_core.v`), Testbench Co-simulation (`tb_npu_cosim.v`), và Khối truyền thông SPI Master DMA (`spi_master_packet.v`).
- **Thời gian lập:** 02/11/2026.

---

## 1. File và Script sinh ra `cosim_golden.hex`

### 1.1. Đường dẫn file nguồn
File script Python thực tế dùng để tính toán bit-exact và ghi ra bộ vector kiểm thử nằm trong nhánh `tai` của kho lưu trữ Team Porygon:
- **Đường dẫn trong kho lưu trữ nhánh `tai`:**
  `C:\Users\Admin\Downloads\porygon-tai\porygon-tai\scripts\verify_fpga_npu_bram_co_sim.py`
- **Script runner tự động hóa co-simulation (Icarus Verilog + C-Engine):**
  `C:\Users\Admin\Downloads\porygon-tai\porygon-tai\scripts\09_run_verilog_cosim.py`

### 1.2. Lệnh thực thi
```powershell
# Chạy thẩm định chu kỳ phần cứng RTL và xuất vector cosim:
cd C:\Users\Admin\Downloads\porygon-tai\porygon-tai
python scripts/verify_fpga_npu_bram_co_sim.py

# Hoặc chạy kiểm thử tự động top-level qua Icarus Verilog:
python scripts/09_run_verilog_cosim.py
```

### 1.3. Đoạn mã Python trực tiếp sinh ra file (Dòng 180–204)
```python
# Chọn mẫu kiểm thử chuẩn số 0 (Inner Race Fault)
sample_idx = 0
test_input = X_int8[sample_idx]

# 1. Ghi cosim_input.hex (257 bins phổ INT8 + 4 dummy priors)
with open("test_vectors/cosim_input.hex", "w") as f:
    for val in test_input:
        f.write(f"{int(val) & 0xFF:02X}\n")
    for _ in range(4):
        f.write("00\n")

# 2. Ghi cosim_golden.hex (đúng 8 dòng 32-bit hex)
with open("test_vectors/cosim_golden.hex", "w") as f:
    f.write(f"{rtl_preds[sample_idx]:08X}\n")     # Dòng 0: Lớp dự đoán (Argmax)
    l = rtl_logits[sample_idx]
    packed_l = ((l[3] & 0xFF) << 24) | ((l[2] & 0xFF) << 16) | ((l[1] & 0xFF) << 8) | (l[0] & 0xFF)
    f.write(f"{packed_l:08X}\n")                  # Dòng 1: 4 Logits INT8 đóng gói
    f.write("00000000\n")                         # Dòng 2: Reserved
    f.write("00000000\n")                         # Dòng 3: Reserved
    f.write("00000000\n")                         # Dòng 4: Reserved
    f.write(f"{rtl_vacuities[sample_idx]:08X}\n") # Dòng 5: Vacuity Q15
    f.write(f"{rtl_ruls[sample_idx]:08X}\n")      # Dòng 6: RUL Q15
    f.write(f"{rtl_alerts[sample_idx]:08X}\n")    # Dòng 7: OOD Alert
```

---

## 2. Giải mã chi tiết 8 dòng của `cosim_golden.hex`

Dữ liệu thực tế gồm 8 từ 32-bit hex:
```text
Dòng 0: 00000001
Dòng 1: 11082DF7
Dòng 2: 00000000
Dòng 3: 00000000
Dòng 4: 00000000
Dòng 5: 00000D79
Dòng 6: 00003999
Dòng 7: 00000000
```

### Bảng đối soát chi tiết:

| Dòng | Giá trị Hex | Tên biến RTL | Ý nghĩa kỹ thuật & Công thức toán học |
| :---: | :---: | :--- | :--- |
| **0** | `00000001` | `predicted_class` | **Lớp hư hỏng dự đoán** qua hàm Argmax.<br>• Giá trị = **`1`** tương ứng **Inner Race Fault** (Lỗi rãnh trong vòng bi - BPFI).<br>**Quy ước nhãn lớp (4 lớp):**<br>• `0`: Normal (Bình thường / Baseline)<br>• `1`: Inner Race Fault (Hỏng rãnh trong - BPFI)<br>• `2`: Outer Race Fault (Hỏng rãnh ngoài - BPFO)<br>• `3`: Ball Fault (Hỏng con lăn/viên bi - BSF) |
| **1** | `11082DF7` | `logits_packed` | **4 giá trị Logit signed INT8** gói vào 1 từ 32-bit theo chuẩn **Little-Endian**:<br>$\text{packed} = \{\text{Logit}_3, \text{Logit}_2, \text{Logit}_1, \text{Logit}_0\}$<br>• **Bits [7:0]** = `0xF7` = **`-9`** $\rightarrow$ Logit lớp **0 (Normal)**<br>• **Bits [15:8]** = `0x2D` = **`+45`** $\rightarrow$ Logit lớp **1 (Inner Race)** *(Điểm số cao nhất $\rightarrow$ Winner)*<br>• **Bits [23:16]** = `0x08` = **`+8`** $\rightarrow$ Logit lớp **2 (Outer Race)**<br>• **Bits [31:24]** = `0x11` = **`+17`** $\rightarrow$ Logit lớp **3 (Ball)** |
| **2** | `00000000` | `reserved_0` | Vùng đệm dự phòng 32-bit (Padding / Metadata). |
| **3** | `00000000` | `reserved_1` | Vùng đệm dự phòng 32-bit. |
| **4** | `00000000` | `reserved_2` | Vùng đệm dự phòng 32-bit. |
| **5** | `00000D79` | `vacuity_q15` | **Độ bất định nhận thức (Epistemic Vacuity)** theo lý thuyết Dirichlet dạng fixed-point Q15.<br>• Giá trị Hex: `0x0D79` = Thập phân **`3449`**.<br>• Công thức: $u_{Q15} = \lfloor \frac{131072}{S} \rfloor$ với $S = \sum \max(0, s_k \gg 6) + 4 = 38 \implies \lfloor \frac{131072}{38} \rfloor = 3449$.<br>• Giá trị thực: $u = \frac{3449}{32768} \approx \mathbf{0.1052}$ (Độ bất định chỉ $\approx 10.5\%$, tức mô hình rất tự tin vào kết luận). |
| **6** | `00003999` | `rul_q15` | **Thời gian sử dụng hữu ích còn lại (Remaining Useful Life)** dạng fixed-point Q15.<br>• Giá trị Hex: `0x3999` = Thập phân **`14745`**.<br>• Giá trị thực: $\frac{14745}{32768} = \mathbf{45.0\%}$ tuổi thọ còn lại (Khớp theo bảng tra trạng thái khi xuất hiện nứt rãnh trong Class 1). |
| **7** | `00000000` | `ood_alert` | **Cờ cảnh báo dữ liệu ngoại lai (Out-of-Distribution Alert)**.<br>• Giá trị = **`0`** (False / An toàn, do $u_{Q15} = 3449 \le 14745 \approx 0.45$). |

> Trong testbench [`src/test_npu/tb_npu_cosim.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/test_npu/tb_npu_cosim.v#L115-L139), các thanh ghi phần cứng được đối chiếu trực tiếp với `golden_mem[0]`, `golden_mem[1]`, `golden_mem[5]`, `golden_mem[6]`, `golden_mem[7]` và đạt tỷ lệ khớp $100\%$ bit-exact.

---

## 3. Nguồn gốc dữ liệu mẫu và file đầu vào

### 3.1. Bộ mẫu kích thích
File `cosim_golden.hex` được tạo ra từ mẫu dữ liệu **Inner Race Fault (Hư hỏng rãnh trong - cỡ nứt 7 mil)** thuộc tập dữ liệu vòng bi CWRU (Case Western Reserve University):
- Mẫu gốc: File MATLAB `105.mat` (Tải motor 0 HP, tốc độ 1797 RPM, tần số quay trục $f_r = 29.95\text{ Hz}$, tần số lỗi rãnh trong $\text{BPFI} = 162.3\text{ Hz}$).

### 3.2. Đường dẫn file đầu vào tương ứng
1. **File vector phổ INT8 đầu vào cho NPU:**
   - Trong repo nhánh `tai`: `porygon-tai/test_vectors/cosim_input.hex`
   - Trong thư mục FPGA: [`src/test_npu/test_vectors/cosim_input.hex`](file:///t:/MCU_FPGA/FPGA_FINAL/src/test_npu/test_vectors/cosim_input.hex)
   - **Quy cách:** File gồm đúng **261 dòng** (mỗi dòng 1 byte hex 8-bit):
     - **Dòng 0 đến 256 (257 bytes):** 257 bin phổ phong bì FFT (INT8 $[0, 127]$) chứa năng lượng đỉnh BPFI.
     - **Dòng 257 đến 260 (4 bytes):** 4 đặc trưng động học tiên nghiệm (BPFO, BPFI, BSF, FTF; được gán `00` dummy trong bài kiểm tra NPU thuần túy).
2. **File kích thích dữ liệu thời gian thô (16-bit signed INT16, 512 mẫu):**
   - [`src/test_npu/roms/hil/stimulus_cwru_inner.hex`](file:///t:/MCU_FPGA/FPGA_FINAL/src/test_npu/roms/hil/stimulus_cwru_inner.hex)

---

## 4. Đặc tả cấu trúc gói tin SPI 524-Byte

Khối SPI Master DMA trên FPGA ([`src/spi_master_packet.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/spi_master_packet.v#L78-L91)) đóng gói toàn bộ phổ và kết quả chẩn đoán gửi sang MCU Sonix SN32F407 ([`embedded/mcu_sonix/app/main.c`](file:///C:/Users/Admin/Downloads/porygon-tai/porygon-tai/embedded/mcu_sonix/app/main.c#L69-L77)).

### 4.1. Cấu trúc C Struct tương thích bộ nhớ trên MCU
```c
typedef struct __attribute__((packed)) {
    uint16_t sync_word;               /* Byte 0..1   : Fixed 0xAA55 alignment token */
    uint16_t frame_seq_id;            /* Byte 2..3   : Monotonically increasing sequence ID */
    uint16_t envelope_spectrum[257];  /* Byte 4..517 : 257 positive frequency bins (0 - Nyquist) */
    uint8_t  npu_pred_class;          /* Byte 518    : 0: Normal, 1: Inner, 2: Outer, 3: Ball */
    uint8_t  dirichlet_max_evidence;  /* Byte 519    : Maximum evidence / vacuity indicator */
    uint16_t hardware_status_flags;   /* Byte 520..521: Bit 0: Sensor OK, Bit 1: Clip, Bit 2: Valid */
    uint16_t crc16_checksum;          /* Byte 522..523: Hardware CRC-16-CCITT across bytes 0..521 */
} fpga_telemetry_frame_t;             /* Tổng cộng: 524 Bytes */
```

### 4.2. Bảng phân bổ Byte (Memory Map 524 Bytes)

| Dải Byte | Số Byte | Tên trường dữ liệu | Kiểu dữ liệu | Chi tiết & Thứ tự truyền |
| :---: | :---: | :--- | :---: | :--- |
| **0 – 1** | 2 | `sync_word` | `uint16_t` | Từ đồng bộ cố định `0xAA55` (Little-endian: Byte 0 = `0x55`, Byte 1 = `0xAA`). |
| **2 – 3** | 2 | `frame_seq_id` | `uint16_t` | Số thứ tự khung tăng dần (Byte 2 = Low, Byte 3 = High). |
| **4 – 517** | **514** | **`envelope_spectrum`** | **`uint16_t[257]`** | **DỮ LIỆU PHỔ PHONG BÌ TẦN SỐ**:<br>Gồm đúng **257 bins** $\times$ **2 bytes/bin** = **514 bytes**.<br>Mỗi bin lưu dạng số nguyên 16-bit Little-endian (Byte chẵn = Low, Byte lẻ = High):<br>• Byte 4–5: Bin 0 (DC / 0 Hz)<br>• Byte 6–7: Bin 1 ($f_0$)<br>• ...<br>• Byte 516–517: Bin 256 (Tần số giới hạn Nyquist) |
| **518** | **1** | **`npu_pred_class`** | **`uint8_t`** | **LỚP DỰ ĐOÁN TỪ NPU**:<br>• `0`: Normal<br>• `1`: Inner Race Fault<br>• `2`: Outer Race Fault<br>• `3`: Ball Fault |
| **519** | **1** | **`dirichlet_max_evidence`** | **`uint8_t`** | **BẰNG CHỨNG CỰC ĐẠI / VACUITY**:<br>Chỉ số độ tin cậy suy luận để MCU thẩm định trước khi trip rơ-le an toàn. |
| **520 – 521** | 2 | `hardware_status_flags` | `uint16_t` | Cờ trạng thái phần cứng (Little-endian):<br>• Bit 0: Sensor Ready<br>• Bit 1: FIR Overflow/Clip Alert<br>• Bit 2: BRAM Valid |
| **522 – 523** | 2 | `crc16_checksum` | `uint16_t` | Mã kiểm tra CRC-16-CCITT (Đa thức $x^{16} + x^{12} + x^5 + 1 = \text{0x1021}$, Init `0xFFFF`).<br>Tính toán phần cứng trên toàn bộ 522 bytes đầu (Bytes 0 đến 521). Byte 522 = Low, Byte 523 = High. |

$$\text{Tổng số byte} = 2 + 2 + 514 + 1 + 1 + 2 + 2 = 524\text{ Bytes}$$
