# 📋 VIBRADISTILL-EDGE: BẢN TÓM TẮT ĐỂ BÀN DEMO THI ĐẤU (ONE-PAGE BOOTH CHEAT SHEET)
## CUỘC THI THIẾT KẾ VI MẠCH VÀ HỆ THỐNG NHÚNG — DSAC 2026
### Đội thi: Team Porygon | Đơn vị: Đại học Bách Khoa - ĐH Đà Nẵng / DSAC Center

---

## ⚡ 1. CHỈ TIÊU KỸ THUẬT CỐT LÕI (PPA AT-A-GLANCE)

| Tiêu Chí Kỹ Thuật | Giá Trị Thực Chứng | Đối Chuẩn Công Nghiệp & Ý Nghĩa |
| :--- | :---: | :--- |
| **Thời Gian Suy Luận AI (Latency)** | **`2.62 µs`** (262 chu kỳ @ 100 MHz) | Nhanh hơn MCU Cortex-M7 **2,700 lần**, nhanh hơn Jetson **380 lần** |
| **Thời Gian Ngắt An Toàn (SIL-2 Trip)** | **`0.75 ms`** (Đo thực tế trên DSO) | Đạt chuẩn an toàn quốc tế **IEC 61508 SIL-2** ($< 1.0\,\text{ms}$) |
| **Tổng Công Suất Tiêu Thụ (Power)** | **`184 mW`** (FPGA 142mW + MCU 42mW) | Tiết kiệm **> 96%** điện năng so với máy tính công nghiệp / Jetson (10W) |
| **Tần Số Cực Đại Toàn SoC ($F_\text{max}$)** | **`102.597 MHz`** (Slack $+0.225\,\text{ns}$) | Khép kín thời gian (Timing Closure) $100\%$, Zero STA Violation |
| **Độ Chính Xác Cảm Biến Thật (ADXL345)**| **`96.38% Acc` \| `95.08% F1`** | Kiểm chứng trên 553 mẫu rung động thực tế động cơ 130 |
| **Độ Chính Xác Công Nghiệp (CWRU 12k)** | **`98.05% Acc` \| `97.34% F1`** | Kiểm chứng trực tiếp từ 2,767 cửa sổ dữ liệu `.mat` thô |
| **Độ Bao Phủ An Toàn (Safety Recall)** | **`100.00%`** (75/75 ca sự cố) | Zero False Negatives trên các dạng hư hỏng vòng bi |
| **Độ Bao Phủ Tin Cậy RUL (HopACP)** | **`93.60% Coverage`** (Target $\ge 90\%$) | Cảnh báo trước sự cố **101.7 phút** trên benchmark PRONOSTIA |
| **Chi Phí Linh Kiện (BOM Cost)** | **`< 500,000 VNĐ (~$20 USD)`** | Gowin GW2A (\$12) + Sonix MCU (\$1.8) + Cảm biến (\$3) |

---

## 🎮 2. THỰC ĐƠN THỬ NGHIỆM TRỰC TIẾP CHO BAN GIÁM KHẢO (INTERACTIVE DEMO MENU)

> *Kính mời Ban Giám khảo chọn một số thứ tự bất kỳ, kỹ thuật viên gõ lệnh trên terminal để kiểm chứng phản ứng thời gian thực của hệ thống:*

```bash
# Cú pháp chạy nhanh trên Terminal của Toàn:
python switch_cosim_vector.py <STT>
```

| STT | Tên Kịch Bản Cơ Khí | Tải / Tình Trạng | Lớp Nhận Dạng | RUL Phần Cứng | Phản Ứng Phần Cứng & Rơ-le |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **`1`** | **Normal Baseline (Vòng bi lành)** | 0 HP (1797 RPM) | **Lớp 0 (Normal)** | **`100.0%`** | Tiếp điểm rơ-le đóng, motor quay êm, LED xanh. |
| **`6`** | **Inner Race Fault (Nứt vòng trong)** | 1 HP (Vết nứt 7-mil) | **Lớp 1 (Inner)** | **`76.2%`** | Phát hiện tần số BPFI, cảnh báo mòn sớm. |
| **`7`** | **Outer Race Fault (Nứt vòng ngoài)** | 1 HP (Vết nứt 7-mil) | **Lớp 2 (Outer)** | **`65.0%`** | Phát hiện tần số BPFO, cảnh báo bảo trì. |
| **`8`** | **Ball Defect (Lỗi con lăn bi)** | 1 HP (Vết nứt 7-mil) | **Lớp 3 (Ball)** | **`70.2%`** | Phát hiện tần số BSF, hiển thị dải điều chế. |
| **`17`** | **Inner Race Severe (Nứt sâu)** | 1 HP (Vết nứt 14-mil) | **Lớp 3 (Ball/Inner)**| **`49.9%`** | Khấu hao 50%, rung động mạnh, còi cảnh báo. |
| **`20`** | **Catastrophic Spall (Phá hủy nặng)** | 1 HP (Vết nứt 21-mil) | **Lớp 3 (Phá hủy)** | **`65.1%`** | **RƠ-LE NHẢ TỨC THÌ (< 1.0 ms)!** Ngắt điện motor. |
| **`27`** | **OOD High Sensor Noise (Nhiễu lạ)** | Mất tiếp xúc cảm biến | **OOD Alert** | **`95.4%`** | **Độ bất định $u^* > 0.45$**, từ chối đoán mò. |
| **`p1`** | **PRONOSTIA Early Life (Đầu đời)** | t = 5% Vòng đời | **Lớp 0 (Normal)** | **`100.0%`** | Chạy êm, dự báo tuổi thọ dồi dào. |
| **`p2`** | **PRONOSTIA Mid Life (Điểm gãy FDP)** | t = 74% Vòng đời | **Lớp 3 (Incipient)** | **`95.8%`** | Điểm bắt đầu suy biến cơ học (Knee-point). |
| **`p3`** | **PRONOSTIA Terminal (Cuối đời)** | t = 98% Vòng đời | **Lớp 3 (Terminal)** | **`83.8%`** | **Xung va đập 28.7g $\implies$ SIL-2 Emergency Trip!** |

---

## 🔌 3. SƠ ĐỒ ĐẤU NỐI DÂY & CHÂN VẬT LÝ (PINOUT & WIRING MAPPING)

```
┌─────────────────────────┐          ┌─────────────────────────┐          ┌─────────────────────────┐
│   CẢM BIẾN ADXL345      │          │  FPGA TANG PRIMER 20K   │          │   MCU SONIX SN32F407    │
│  GY-291 SPI @ 5.0 MHz   │          │     GW2A-LV18PG256      │          │   ARM Cortex-M0 @ 60MHz │
├─────────────────────────┤          ├─────────────────────────┤          ├─────────────────────────┤
│ CS    ──► Header J3 Pin1│ (A15)    │ Header J4 Pin1 ──► P2.0 │ (E15)    │ P1.2/P1.3 ──► OLED I2C  │
│ SDA   ──► Header J3 Pin2│ (B15)    │ Header J4 Pin2 ──► P2.1 │ (D14)    │ P2.5      ──► SIL-2 Trip│
│ SDO   ──► Header J3 Pin3│ (C15)    │ Header J4 Pin3 ──► P2.3 │ (A14)    │ P3.0      ──► Còi Buzzer│
│ SCL   ──► Header J3 Pin4│ (J14)    │ Header J4 Pin4 ──► P2.4 │ (N16)    │ P0.1/P0.2 ──► UART SCADA│
│ INT1  ──► Header J3 Pin7│ (J16)    │ Common GND     ──► GND  │          │ Common GND──► GND       │
└─────────────────────────┘          └─────────────────────────┘          └─────────────────────────┘
```

> **QUY TẮC AN TOÀN:** Toàn bộ tín hiệu dùng chuẩn **3.3V LVCMOS**. **BẮT BUỘC NỐI CHUNG GND** giữa 3 bo mạch!

---

## 💡 4. ĐIỂM SÁNG CÔNG NGHỆ BẢN DẪN ĐỘC ĐÁO (KEY INNOVATIONS)

1. **Chuỗi DSP Pha Tối Thiểu (Minimum-Phase FIR 32-tap):**
   - Mảng hệ số `0xD0B8` phản chiếu toàn bộ zeros vào trong vòng tròn đơn vị, giảm độ trễ nhóm hiệu dụng từ 15.5 mẫu xuống **3.2 mẫu**, bắt trọn xung va đập sớm hơn $79\%$ thời gian.
2. **Bộ Tách Bao Sóng Phong Bì 18-Bit DSP18E (Causal Envelope Demodulator):**
   - Khai thác khối nhân 18-bit của Gowin để nhân hệ số phản hồi $A_1 = -37453$ ($|A_1| > 1.0$), triệt tiêu $100\%$ lỗi tràn số, cho tần số cắt chính xác $1,200\,\text{Hz}$ / $400\,\text{Hz}$.
3. **Lõi NPU 12-Way Systolic Array với Bus Bộ Nhớ 96-Bit:**
   - 6 khối BSRAM Dual-Port nạp đồng thời 12 trọng số INT8 mỗi chu kỳ clock, hoàn thành suy luận trong đúng **260 chu kỳ xung nhịp ($2.60\,\mu\text{s}$)**.
4. **Định Lượng Độ Bất Định Dirichlet (Evidential Deep Learning):**
   - Tính toán trực tiếp độ bất định nhận thức (Vacuity $u^*$). Khi cảm biến tuột dây hoặc gặp nhiễu lạ, hệ thống phát cảnh báo OOD Alert thay vì đoán mò giả tạo.
5. **Tiên Lượng Tuổi Thọ RUL Chuẩn NASA PHM & Conformal Prediction HopACP:**
   - Tránh bẫy suy biến tuyến tính ngây thơ (vốn làm mô hình bị kẹt ở 35-37%), kết hợp giải thuật HopACP Q16.16 bọc dải tin cậy $90\%$, cảnh báo sớm trước **101.7 phút**.
6. **Kênh Ngắt An Toàn Độc Lập SIL-2 (< 1.0 ms):**
   - Đạt độ trễ thực tế **0.75 ms** đo đạc trên máy hiện sóng DSO, bảo vệ động cơ theo chuẩn quốc tế IEC 61508.

---
*Mã nguồn mở, báo cáo khoa học và tài liệu đối soát toàn bộ tại:* **[`github.com/zok213/porygon at tai`](https://github.com/zok213/porygon/tree/tai)**
