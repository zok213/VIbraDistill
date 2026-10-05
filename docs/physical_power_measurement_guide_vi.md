# Hướng Dẫn Đo Đạc Công Suất Động & Năng Lượng Thực Nghiệm (Physical Power & Energy Profiling Guide)

> **Mục tiêu**: Hướng dẫn kỹ thuật đo đạc khách quan, chính xác công suất tiêu thụ động ($P_{\text{dynamic}}$ tính bằng $\text{mW}$) và năng lượng trên mỗi lượt suy luận ($E_{\text{inference}}$ tính bằng $\mu\text{J}$) cho hệ thống VibraDistill-Edge (FPGA Gowin Primer 20K & MCU Sonix SN32F407).
> 
> Hỗ trợ **2 phương pháp đo đạc thực tế tại phòng lab**:
> - **Phương pháp A (Sẵn có, chi phí thấp)**: Dao động ký số (Digital Storage Oscilloscope - DSO) + Điện trở Shunt ($1\,\Omega$ hoặc $0.1\,\Omega$).
> - **Phương pháp B (Độ chính xác cao, chuyên dụng)**: Nordic Power Profiler Kit II (PPK2) hoặc Monsoon High-Voltage Power Monitor.

---

## 1. Phương Pháp A: Đo Bằng Dao Động Ký Số (DSO) & Điện Trở Shunt

### 1.1. Sơ Đồ Nguyên Lý Mắc Mạch Điện Tử

```
        Nguồn Cấp 3.3V (Lab Power Supply)
                     |
                     v
           +--------------------+
           |  ĐIỆN TRỞ SHUNT   |  R_shunt = 1.0 Ohm 1% (Cho MCU)
           |      R_shunt       |  R_shunt = 0.1 Ohm 1% (Cho FPGA)
           +--------------------+
             |                |
   CH1 (+) --+                +-- CH2 (+)  (Que đo vi sai hoặc 2 kênh CH1, CH2)
             |                |
             v                v
          Node A           Node B (V_in thiết bị)
                              |
                              +--------------------+
                              |  Thiết Bị Cần Đo   |
                              |  (FPGA hoặc MCU)   |
                              +--------------------+
                              |                  |
   CH3 (+) -------------------| MCU_BENCH_PIN    | (Xung mức cao trong thời gian tính)
                              | (P1.1)           |
                              +------------------+
                                        |
                                       GND (Nối mass chung que đo DSO)
```

### 1.2. Chọn Lựa Trị Số Điện Trở Shunt Để Tránh Sụt Áp Reset (Brown-Out)

> [!CAUTION]
> **Cảnh Báo Sụt Áp**:
> - Đối với **Sonix SN32F407 (Cortex-M0)**: Dòng điện tiêu thụ trung bình $I \approx 8 - 12\,\text{mA}$.
>   Sụt áp trên điện trở $R_{\text{shunt}} = 1.0\,\Omega$ là $\Delta V = 10\,\text{mA} \times 1\,\Omega = 10\,\text{mV}$ (Điện áp tại MCU là $3.29\,\text{V}$, hoàn toàn an toàn).
> - Đối với **Gowin Tang Primer 20K FPGA**: Dòng điện tĩnh là $\sim 25\,\text{mA}$, dòng động khi chạy 12-way NPU là $\sim 45\,\text{mA}$, nhưng dòng khởi động nạp bitstream (Inrush Current) có thể đạt $\sim 150 - 200\,\text{mA}$.
>   Nếu dùng shunt $1\,\Omega$, sụt áp khởi động sẽ là $200\,\text{mV} \implies V_{\text{dd}}$ tụt xuống $3.1\,\text{V}$, gây kích hoạt mạch Reset Brown-Out (BOR)!
>   **Quy tắc bắt buộc**: 
>   - Dùng **$R_{\text{shunt}} = 1.0\,\Omega \ (1\%)$** khi đo riêng Sonix MCU.
>   - Dùng **$R_{\text{shunt}} = 0.1\,\Omega \ (100\,\text{m}\Omega \ 1\%)$** khi đo Tang Primer 20K FPGA.

---

### 1.3. Cấu Hình Kênh Đo & Kênh Toán Học Trên Dao Động Ký (DSO Setup)

1. **Cắm Que Đo**:
   - **Kênh 1 (CH1)**: Cắm vào Node A (Điện áp nguồn trước Shunt $V_{\text{in}} \approx 3.30\,\text{V}$). Đặt Coupling: `DC`, $1\text{ V/div}$.
   - **Kênh 2 (CH2)**: Cắm vào Node B (Điện áp sau Shunt $V_{\text{dev}}$). Đặt Coupling: `DC`, $1\text{ V/div}$ (hoặc dùng que đo vi sai đo trực tiếp $\Delta V_{\text{shunt}} = V_A - V_B$ ở thang $10\text{ mV/div}$).
   - **Kênh 3 (CH3)**: Cắm vào chân `BENCH_PIN` (P1.1 của MCU). Đặt Coupling: `DC`, $1\text{ V/div}$.
   - **GND của cả 3 que đo**: Kẹp chung vào chân Ground của bo mạch.
2. **Thiết Lập Trigger (Kích Hoạt)**:
   - Source: `CH3 (BENCH_PIN)`.
   - Slope: `Rising Edge` (Sườn lên).
   - Sweep Mode: `Normal` hoặc `Single`.
3. **Cấu Hình Kênh Toán Học (Math Channel)**:
   - Nếu đo vi sai bằng 2 kênh CH1, CH2:
     $$\Delta V_{\text{shunt}}(t) = \text{CH1} - \text{CH2}$$
     $$I(t) = \frac{\Delta V_{\text{shunt}}(t)}{R_{\text{shunt}}} = \frac{\text{CH1} - \text{CH2}}{R_{\text{shunt}}}$$
     $$\text{Công suất tức thời: } P(t) = \text{CH2} \times I(t) = \text{CH2} \times \frac{\text{CH1} - \text{CH2}}{R_{\text{shunt}}}$$
   - Cài đặt trên máy Rigol/Siglent: Chọn hàm `Math` $\to$ `Operator: Advanced` $\to$ Nhập biểu thức:
     $$\mathtt{Math = CH2 * (CH1 - CH2) / 1.0} \quad (\text{Đơn vị: Watt})$$
4. **Đo Năng Lượng Tích Phân**:
   - Dùng tính năng đo tự động `Measure` $\to$ `Area` (Tích phân diện tích dưới đường cong Math) trong khoảng thời gian con trỏ (Gated by Cursors giữa sườn lên và sườn xuống của CH3):
     $$E_{\text{inference}} = \int_{t_{\text{start}}}^{t_{\text{end}}} P(t) \, dt \quad (\text{Joule hoặc } \mu\text{J})$$

---

## 2. Phương Pháp B: Đo Bằng Nordic Power Profiler Kit II (PPK2)

Mạch đo **Nordic PPK2** là thiết bị chuẩn công nghiệp tốt nhất cho TinyML vì có dải đo từ $200\,\text{nA}$ đến $1\,\text{A}$, tự động đổi thang đo (auto-ranging) và tốc độ lấy mẫu $100\,\text{kSps}$.

### 2.1. Sơ Đồ Cắm Dây Nordic PPK2

```
      Nordic PPK2                              Bo Mạch Cần Đo (Sonix MCU / Tang 20K)
   +----------------+                         +-----------------------------------+
   |                |   Dây Đỏ (3.3V)         |                                   |
   |  VOUT (Power)  |------------------------>| Chân VDD / 3.3V Pin               |
   |                |                         |                                   |
   |  GND           |------------------------>| Chân GND Pin                      |
   |                |   Dây Vàng (Digital In) |                                   |
   |  LOGIC IN 0    |<------------------------| Chân BENCH_PIN (P1.1)             |
   +----------------+                         +-----------------------------------+
          |
       Cáp USB
          v
      Máy Tính (Phần Mềm nRF Connect / Python Script)
```

### 2.2. Quy Trình Vận Hành Với Phần Mềm nRF Connect Power Profiler

1. Mở phần mềm **nRF Connect for Desktop** $\to$ Mở ứng dụng **Power Profiler**.
2. Chọn thiết bị PPK2 kết nối qua USB.
3. Trong mục **Select Mode**: Chọn `Source Meter` (PPK2 tự cấp nguồn 3.3V cho thiết bị).
4. Đặt điện áp: `3300 mV`.
5. Bật tùy chọn `Enable Power Output`.
6. Trong mục **Digital Inputs**: Tích chọn `D0` (nối với chân `BENCH_PIN`).
7. Nhấn **Start** để bắt đầu ghi:
   - Dòng điện nền (Baseline Sleep Current) khi MCU nhàn rỗi: $\sim 1.2\,\text{mA}$.
   - Dòng điện hoạt động (Active Inference Current) khi `D0` lên mức cao: $\sim 8.5\,\text{mA}$.
8. Dùng chuột quét chọn vùng thời gian khi `D0 = HIGH`:
   - Màn hình sẽ tự động hiển thị:
     - **Thời gian (Duration)**: $1.85\,\text{ms}$ (Cortex-M4F) hoặc $3.45\,\text{ms}$ (Cortex-M0).
     - **Dòng điện trung bình (Average Current)**: $8.42\,\text{mA}$.
     - **Công suất trung bình (Average Power)**: $3.3\,\text{V} \times 8.42\,\text{mA} = 27.78\,\text{mW}$.
     - **Tổng năng lượng (Total Energy)**: $E = P \times \Delta t = 27.78\,\text{mW} \times 1.85\,\text{ms} = \mathbf{51.4\,\mu\text{J}}$.

---

## 3. Bảng Đối Soát Số Liệu Thực Tế Dự Kiến (Benchmark Expectation Table)

| Thành Phần Phần Cứng | Chế Độ Hoạt Động | Điện Áp ($V_{\text{dd}}$) | Dòng Trung Bình ($I_{\text{avg}}$) | Công Suất Động ($P$) | Độ Trễ Suy Luận ($t$) | Năng Lượng / Lượt ($E$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Gowin Tang Primer 20K** | 12-Way NPU + Streaming DSP | 3.30 V | 35.8 mA | **118.1 mW** | **0.40 ms** | **47.2 uJ** |
| **Sonix SN34F788** | Cortex-M4F @ 192 MHz (__SMLAD) | 3.30 V | 9.8 mA | **32.3 mW** | **1.85 ms** | **59.8 uJ** |
| **Sonix SN32F407** | Cortex-M0 @ 60 MHz (Scalar C) | 3.30 V | 7.6 mA | **25.1 mW** | **3.45 ms** | **86.6 uJ** |
| **Toàn Hệ Thống (FPGA+MCU)**| Hoạt động đồng thời | 3.30 V | 45.6 mA | **150.4 mW** | **0.40 ms (Pipeline)**| **107.0 uJ** |
| *So sánh: Jetson Orin NX* | TensorRT FP16 (Baseline cũ) | 12.00 V | 1,250.0 mA | **15,000.0 mW** | **0.85 ms** | **12,750.0 uJ** ($119\times$ cao hơn!) |
