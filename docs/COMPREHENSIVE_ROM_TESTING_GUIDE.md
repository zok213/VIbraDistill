# CẨM NANG HƯỚNG DẪN KIỂM THỬ TOÀN DIỆN TẤT CẢ CÁC BỘ ROM VI MẠCH
## (VIBRADISTILL-EDGE: COMPREHENSIVE HARDWARE ROM TESTING & VERIFICATION GUIDE)

> **Tài liệu chính thức cho Đội ngũ AI, Firmware & Phần cứng HIL FPGA.**  
> **Nền tảng kiểm chứng:** Vi mạch Gowin GW2A-LV18PG256C8/I7 (Tang Primer 20K) + Vi điều khiển ARM Cortex-M0 SIL-2 Co-Processor.  
> **Script kiểm tra toàn bộ 1 click:** `python scripts/test_all_roms_suites.py` *(Thời gian thực thi: ~7.6 giây, 10/10 bộ kiểm thử đều PASS 100%)*.

---

## 🗺️ I. MA TRẬN QUYẾT ĐỊNH: "CẦN TEST BỘ NÀO VÀ KHI NÀO?"

Khi làm việc với dự án, bạn sẽ gặp nhiều bộ ROM và kích thích khác nhau. Bảng dưới đây chỉ rõ **bộ nào phục vụ mục đích nào** để bạn chọn đúng bài test:

```
                                      BẠN MUỐN KIỂM TRA ĐIỀU GÌ?
                                                  │
         ┌───────────────────────┬────────────────┼───────────────────────┬────────────────────────┐
         │                       │                │                       │                        │
[1. BÀN DEMO THỰC TẾ]   [2. HIL CÔNG NGHIỆP CWRU] [3. MÁY NẶNG 16 BI]    [4. TIÊN LƯỢNG RUL]     [5. HỘP SỐ NGOẠI BIÊN]
(Động cơ 130 + ADXL345) (Động cơ SKF 6205, 9 bi)  (Tải nặng Nice 1012)   (PRONOSTIA Chạy hỏng)    (Bánh răng SEU/PHM2009)
         │                       │                │                       │                        │
 -> Chọn Suite 5 & ADXL  -> Chọn Suite 1 & 6      -> Chọn Suite 2         -> Chọn Suite 4 & 7      -> Chọn Suite 3
 Profile: `adxl345_native` Profile: `prf01_cwru`   Profile: `prf02_mfpt`   Profile: `prf03_rul`     Profile: `prf04_gearbox`
 Tần số: 3,200 Hz        Tần số: 12,000 Hz        Tần số: 12,000 Hz       Tần số: 25,600 / 12,000   Tần số: 12,000 Hz
 Metric: 96.38% Acc      Metric: 98.05% Acc .mat  Metric: 100% Detect     Metric: HopACP >= 90%    Metric: OOD u >= 0.85
```

### Bảng Phân Bổ Chi Tiết 10 Bộ Kiểm Thử (Suites Inventory)

| Suite ID | Tên Bộ Kiểm Thử | Vị Trí Lưu Trữ ROM / Stimulus | Tần Số ($F_s$) | Số Mẫu | Mục Đích Kỹ Thuật | Chỉ Số Đạt Chuẩn (DoD) |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| **Suite 1** | **CWRU In-Domain Motor** | `roms/stimuli/cwru/` + `profiles/prf01_cwru_motor_9ball/` | $12.0\,\text{kHz}$ | 5 vector | Kiểm tra 4 lớp lỗi vòng bi động cơ chuẩn quốc tế | **100% Correct ($u < 0.15$)** |
| **Suite 2** | **MFPT Cross-Domain Heavy** | `roms/stimuli/mfpt_crossdomain/` + `profiles/prf02_mfpt_heavy_16ball/` | $12.0\,\text{kHz}$ | 3 vector | Kiểm tra chuyển giao chẩn đoán vòng bi 16 bi tải nặng | **100% Correct ($u < 0.05$)** |
| **Suite 3** | **Gearbox OOD Rejection** | `roms/stimuli/ood_gearbox/` + `profiles/prf04_gearbox_drivetrain/` | $12.0\,\text{kHz}$ | 3 vector | Triệt tiêu báo động giả khi gặp rung động ăn khớp bánh răng | **OOD Flagged ($u \ge 0.85$)** |
| **Suite 4** | **PRONOSTIA RUL Snapshots** | `roms/stimuli/pronostia_degradation/` + `profiles/prf03_pronostia_rul/` | $12.0\,\text{kHz}$ | 3 vector | Theo dõi 3 mốc vòng đời: Đầu đời $\to$ Giữa đời $\to$ Sắp vỡ | **Tracked ($100\% \to 12.5\%$)** |
| **Suite 5** | **ADXL345 Silicon Validation** | `roms/adxl345/` (6 BSRAM Banks) | $3.2\,\text{kHz}$ | 553 mẫu | Đối chuẩn trực tiếp dữ liệu cảm biến MEMS thực tế | **$\ge 96.0\%$ Acc (Đạt 96.38%)** |
| **Suite 6** | **Live Raw CWRU .mat Audit** | `data/CWRU_Dataset/` (15 file `.mat` thô, Zero-Cache) | $12.0 \to 3.2\text{k}$ | 2,767 cửa sổ | Đọc trực tiếp từ đĩa cứng, không dùng dữ liệu đệm | **$\ge 97.0\%$ Acc (Đạt 98.05%)** |
| **Suite 7** | **PRONOSTIA .mat Benchmark** | `data/rul_mat_benchmarks/bearing_lifecycle_1_3.mat` | $25.6\,\text{kHz}$ | 2,375 snaps | Tiên lượng suy thoái liên tục và ngắt rơ-le SIL-2 | **HopACP $\ge 90\%$, Trip $>15\text{m}$** |
| **Suite 8** | **100-Vector Industrial Suite** | `roms/stimulus_suite_100/` | $3.2\,\text{kHz}$ | 100 vector | Đánh giá độ phủ an toàn (Safety Fault Recall) | **100% Safety Fault Recall** |
| **Suite 9** | **28-Vector Functional Regression**| `roms/stimulus_suite/` | $12.0\,\text{kHz}$ | 28 vector | Hồi quy chức năng RTL (lệch pha, lệch tải, nhiễu OOD) | **28/28 Vectors Bit-True** |
| **Suite 10**| **HopACP MCU Q16.16 Parity** | `scripts/test_hop_acp_parity.py` | N/A (Logic) | 1,000 bước | Kiểm chứng sai số số học dấu phẩy tĩnh ARM Cortex-M0 | **Sai số $\approx 0.00000\%$** |

---

## ⚡ II. CÁCH KIỂM THỬ: 1-CLICK TẤT CẢ HOẶC TỪNG BỘ RIÊNG LẺ

### Cách 1: Chạy toàn bộ 10 bộ cùng lúc (Khuyên dùng khi nghiệm thu)
Chỉ cần mở PowerShell hoặc Terminal và chạy:

```powershell
python scripts/test_all_roms_suites.py
```

**Bảng kết quả mẫu xuất ra màn hình (Chạy trong 7.6 giây):**
```
======================================================================================
 MASTER ROMS & DATASETS HARDWARE VERIFICATION SUMMARY TABLE
======================================================================================
SUITE ID & NAME                  | SAMPLES    | PERFORMANCE / METRIC           | STATUS 
--------------------------------------------------------------------------------------
SUITE1_CWRU                      | 5/5        | 100% BIT-TRUE                  | PASSED 
SUITE2_MFPT                      | 3/3        | 100% BIT-TRUE                  | PASSED 
SUITE3_GEARBOX_OOD               | 3/3        | 100% BIT-TRUE                  | PASSED 
SUITE4_PRONOSTIA_RUL             | 3/3        | 100% BIT-TRUE                  | PASSED 
SUITE 5 (ADXL345 VALIDATION)     | 533/553    | 96.38% Accuracy (533/553)      | PASSED 
SUITE 6 (15 RAW .MAT FILES)      | 2713/2767  | 98.05% Acc, 97.34% F1          | PASSED 
SUITE 7 (MAT RUL BENCHMARK)      | 2375/2375  | HopACP Coverage 91.41%, SIL-2 Trip 101.7 min margin | PASSED 
SUITE 8 (100-VECTOR SUITE)       | 75/75      | 76/100 Correct, Safety Recall 100.0% | PASSED 
SUITE 9 (28-VECTOR REGRESSION)   | 28/28      | 28/28 Vectors Verified Bit-True | PASSED 
SUITE 10 (HOPACP MCU PARITY)     | 1000/1000  | Max Diff: 0.00000%, 0 Div Zero | PASSED 
======================================================================================
 TOTAL EXECUTION TIME: 7.60 seconds
 OVERALL HARDWARE AUDIT VERDICT: ALL SUITES 100% PASSED
======================================================================================
```

---

### Cách 2: Chạy kiểm thử từng bộ độc lập (Step-by-Step)

#### Bước 1: Test 4 Suite Đa Tập Dữ Liệu (Suites 1, 2, 3, 4)
```powershell
python scripts/verify_multi_dataset_fpga.py
```
* **Mục đích:** Kiểm tra lõi NPU 12 kênh Gowin chuyển đổi giữa 4 Profile ROM (`prf01` đến `prf04`).
* **Kỳ vọng:** $100\%$ Bit-True Parity, độ trễ $2.62\,\mu\text{s}$ (262 chu kỳ @ 100 MHz).

#### Bước 2: Test Bộ Dữ Liệu Cảm Biến Thật ADXL345 (Suite 5)
```powershell
python scripts/verify_fpga_npu_bram_co_sim.py
```
* **Mục đích:** Nạp 6 file hex BSRAM của ADXL345 và kiểm chứng trên 553 mẫu rung động thật.
* **Kỳ vọng:** **96.38% Accuracy**, Macro F1 **95.08%**. Đồng bộ hóa `cosim_input.hex` và `cosim_golden.hex` cho Verilog testbench.

#### Bước 3: Test Trực Tiếp 15 File `.mat` CWRU Thô (Suite 6)
```powershell
python scripts/verify_raw_mat_to_fpga_pipeline.py
```
* **Mục đích:** Chứng minh AI chạy trực tiếp trên file gốc tải từ Đại học Case Western Reserve, không qua cache hay can thiệp trước.
* **Kỳ vọng:** **98.05% Accuracy**, **97.34% F1** trên toàn bộ 2,767 cửa sổ đo.

#### Bước 4: Test Tiên Lượng RUL Từ File MATLAB `.mat` Chuẩn (Suite 7)
```powershell
python scripts/verify_mat_rul_prognostics.py
```
* **Mục đích:** Nạp `data/rul_mat_benchmarks/bearing_lifecycle_1_3.mat` (2,375 snapshot, 6.6 giờ chạy hỏng), chạy thuật toán HopACP Conformal và kiểm tra rơ-le ngắt an toàn SIL-2.
* **Kỳ vọng:** 
  * HopACP Conformal Coverage: **91.41%** ($\ge 90\%$).
  * MAE: **0.224 giờ** ($\le 1.85\,\text{h}$).
  * SIL-2 Trip kích hoạt lúc $t = 4.90\,\text{h}$, báo trước sự cố **101.7 phút**.
  * Xuất biểu đồ tại: [`docs/figures/mat_rul_benchmark.png`](file:///d:/Gitrepo/VIbraDistill/docs/figures/mat_rul_benchmark.png).

#### Bước 5: Test Kho 100 Vector Kích Thích Công Nghiệp (Suite 8)
```powershell
python scripts/verify_100_stimulus_suite.py
```
* **Mục đích:** Kiểm tra rơ-le an toàn SIL-2 trên 100 vector đại diện cho 4 mức tải và 3 độ sâu vết nứt.
* **Kỳ vọng:** **100% Safety Fault Recall** (75/75 ca hỏng hóc đều kích hoạt rơ-le ngắt nguồn, không bỏ sót lỗi nguy hiểm).

#### Bước 6: Test Hồi Quy 28 Vector Chức Năng RTL (Suite 9)
```powershell
python scripts/verify_all_stimulus_files.py
```
* **Mục đích:** Kiểm tra khả năng chịu lỗi pha và nhiễu sóng nhân tạo trong `tb_gowin_top.v`.
* **Kỳ vọng:** Đạt chuẩn Bit-True trên cả 28 vector.

#### Bước 7: Test Số Học Dấu Phẩy Tĩnh HopACP Q16.16 Trên ARM Cortex-M0 (Suite 10)
```powershell
python scripts/test_hop_acp_parity.py
```
* **Mục đích:** So sánh từng phép toán số nguyên của vi điều khiển Cortex-M0 với tham chiếu float64 qua 10,000 bước.
* **Kỳ vọng:** Sai số tối đa $< 0.0001\%$, độ trễ $< 12$ chu kỳ clock, 0 lỗi chia cho 0.

---

## 🎛️ III. HƯỚNG DẪN CẤU HÌNH PHẦN CỨNG GOWIN TANG PRIMER 20K

Khi nạp bitstream lên bo mạch thật Gowin Tang Primer 20K, cấu hình các chân gạt Switch (`SW1`, `SW2`) để chọn Profile ROM:

```
+-------------------------------------------------------------------------------+
|                    BẢNG CẤU HÌNH GẠT SWITCH CHỌN PROFILE NPU                  |
+-------------+-------------+---------------------------+-----------------------+
| Switch SW1  | Switch SW2  | Hồ Sơ ROM Kích Hoạt       | Ứng Dụng Thực Tế      |
+-------------+-------------+---------------------------+-----------------------+
|     OFF     |     OFF     | `prf01_cwru_motor_9ball`  | Động cơ CWRU (12 kHz) |
|     OFF     |     ON      | `prf02_mfpt_heavy_16ball` | Vòng bi nặng (12 kHz) |
|     ON      |     OFF     | `prf03_pronostia_rul`     | Tiên lượng RUL FEMTO  |
|     ON      |     ON      | `adxl345_native`          | Bàn demo ADXL (3.2k)  |
+-------------+-------------+---------------------------+-----------------------+
```

### Thông Số Giao Tiếp Ngoại Vi
* **Cảm biến ADXL345:** Giao tiếp qua SPI Hardware Master ở tốc độ $5.0\,\text{MHz}$, tần số ra dữ liệu (ODR) $3,200\,\text{Hz}$, dải đo $\pm 16\text{g}$.
* **Cổng UART HIL Streamer:** Chân TX/RX kết nối máy tính ở tốc độ **`921,600 baud`**, định dạng khung truyền 512 mẫu signed 16-bit kèm mã kiểm tra CRC-16.
* **Rơ-le An Toàn SIL-2:** Chân đầu ra GPIO `relay_trip_out` kết nối cuộn hút Contactor ngắt nguồn. Ở trạng thái bình thường: `Logic 1` (Giữ rơ-le đóng). Khi phát hiện lỗi hỏng: `Logic 0` (Ngắt nhả tức thì trong $< 1.0\,\text{ms}$).
