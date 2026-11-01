# DANH MỤC 28 TỆP SÓNG RUNG KIỂM THỬ CÔNG NGHIỆP TRÊN FPGA
## (COMPREHENSIVE INDUSTRIAL STIMULUS SUITE CATALOG)

> Thư mục lưu trữ: `embedded/fpga_gowin/roms/stimulus_suite/`  
> Toàn bộ 28 tệp đều có định dạng: **512 mẫu sóng rung thời gian, 16-bit signed hex, tần số trích xuất 12,000 Hz**.

| STT | Tên Tệp `.hex` | Lớp Chuẩn (True Class) | Điều Kiện Tải / Tốc Độ | Mô Tả Kỹ Thuật | Phản Ứng Dự Kiến Của FPGA |
| :---: | :--- | :---: | :--- | :--- | :--- |
| 01 | `01_cwru_normal_0hp.hex` | **Normal** | 0 HP / 1797 RPM | Chuẩn vòng bi lành lặn 0 HP | Bình thường (Relay đóng) |
| 02 | `02_cwru_inner_7mil_0hp.hex` | **Inner** | 0 HP / 1797 RPM | Lỗi vòng trong 7-mil (BPFI ~162Hz) | Trip Rơ-le SIL-2 (< 1.0ms) |
| 03 | `03_cwru_outer_7mil_0hp.hex` | **Outer** | 0 HP / 1797 RPM | Lỗi vòng ngoài 7-mil (BPFO ~107Hz) | Trip Rơ-le SIL-2 (< 1.0ms) |
| 04 | `04_cwru_ball_7mil_0hp.hex` | **Ball** | 0 HP / 1797 RPM | Lỗi viên bi 7-mil (BSF ~71Hz) | Trip Rơ-le SIL-2 (< 1.0ms) |
| 05 | `05_cwru_normal_1hp.hex` | **Normal** | 1 HP / 1772 RPM | Chuẩn vòng bi lành lặn 1 HP | Bình thường (Relay đóng) |
| 06 | `06_cwru_inner_7mil_1hp.hex` | **Inner** | 1 HP / 1772 RPM | Lỗi vòng trong 7-mil tải 1 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 07 | `07_cwru_outer_7mil_1hp.hex` | **Outer** | 1 HP / 1772 RPM | Lỗi vòng ngoài 7-mil tải 1 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 08 | `08_cwru_ball_7mil_1hp.hex` | **Ball** | 1 HP / 1772 RPM | Lỗi viên bi 7-mil tải 1 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 09 | `09_cwru_normal_2hp.hex` | **Normal** | 2 HP / 1750 RPM | Chuẩn vòng bi lành lặn 2 HP | Bình thường (Relay đóng) |
| 10 | `10_cwru_inner_7mil_2hp.hex` | **Inner** | 2 HP / 1750 RPM | Lỗi vòng trong 7-mil tải 2 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 11 | `11_cwru_outer_7mil_2hp.hex` | **Outer** | 2 HP / 1750 RPM | Lỗi vòng ngoài 7-mil tải 2 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 12 | `12_cwru_ball_7mil_2hp.hex` | **Ball** | 2 HP / 1750 RPM | Lỗi viên bi 7-mil tải 2 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 13 | `13_cwru_normal_3hp.hex` | **Normal** | 3 HP / 1730 RPM | Chuẩn vòng bi lành lặn 3 HP | Bình thường (Relay đóng) |
| 14 | `14_cwru_inner_7mil_3hp.hex` | **Inner** | 3 HP / 1730 RPM | Lỗi vòng trong 7-mil tải 3 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 15 | `15_cwru_outer_7mil_3hp.hex` | **Outer** | 3 HP / 1730 RPM | Lỗi vòng ngoài 7-mil tải 3 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 16 | `16_cwru_ball_7mil_3hp.hex` | **Ball** | 3 HP / 1730 RPM | Lỗi viên bi 7-mil tải 3 HP | Trip Rơ-le SIL-2 (< 1.0ms) |
| 17 | `17_cwru_inner_14mil_1hp.hex` | **Inner** | 1 HP / 14-mil | Lỗi vòng trong vết nứt 14-mil | Trip Rơ-le SIL-2 (< 1.0ms) |
| 18 | `18_cwru_outer_14mil_1hp.hex` | **Outer** | 1 HP / 14-mil | Lỗi vòng ngoài vết nứt 14-mil | Trip Rơ-le SIL-2 (< 1.0ms) |
| 19 | `19_cwru_ball_14mil_1hp.hex` | **Ball** | 1 HP / 14-mil | Lỗi viên bi vết nứt 14-mil | Trip Rơ-le SIL-2 (< 1.0ms) |
| 20 | `20_cwru_inner_21mil_1hp.hex` | **Inner** | 1 HP / 21-mil | Lỗi vòng trong phá hủy nặng 21-mil | Trip Rơ-le SIL-2 (< 1.0ms) |
| 21 | `21_cwru_outer_21mil_1hp.hex` | **Outer** | 1 HP / 21-mil | Lỗi vòng ngoài phá hủy nặng 21-mil | Trip Rơ-le SIL-2 (< 1.0ms) |
| 22 | `22_cwru_ball_21mil_1hp.hex` | **Ball** | 1 HP / 21-mil | Lỗi viên bi phá hủy nặng 21-mil | Trip Rơ-le SIL-2 (< 1.0ms) |
| 23 | `23_cwru_inner_7mil_win2.hex` | **Inner** | 0 HP / Window 2 | Cửa sổ thời gian số 2 (Offset 4096) | Trip Rơ-le SIL-2 (< 1.0ms) |
| 24 | `24_cwru_inner_7mil_win3.hex` | **Inner** | 0 HP / Window 3 | Cửa sổ thời gian số 3 (Offset 8192) | Trip Rơ-le SIL-2 (< 1.0ms) |
| 25 | `25_cwru_outer_7mil_win2.hex` | **Outer** | 0 HP / Window 2 | Cửa sổ thời gian số 2 (Offset 4096) | Trip Rơ-le SIL-2 (< 1.0ms) |
| 26 | `26_cwru_outer_7mil_win3.hex` | **Outer** | 0 HP / Window 3 | Cửa sổ thời gian số 3 (Offset 8192) | Trip Rơ-le SIL-2 (< 1.0ms) |
| 27 | `27_ood_high_noise.hex` | **OOD Anomaly** | Gaussian Noise | Nhiễu trắng biên độ cao (Test đèn OOD Vacuity) | Bật LED OOD Alert (u > 0.45) |
| 28 | `28_ood_synthetic_multitone.hex` | **OOD Anomaly** | Synthetic Multitone | Tín hiệu cộng hưởng lạ 450Hz & 850Hz | Bật LED OOD Alert (u > 0.45) |
