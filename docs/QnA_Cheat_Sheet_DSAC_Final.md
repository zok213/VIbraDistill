# "Bí Kíp" 20 Câu Hỏi Phản Biện Kỹ Thuật Vòng Chung Kết DSAC 2026
## Đề tài: VibraDistill-Edge | Đội thi: Team Porygon
### Tác giả: Tài (AI & Git Lead) | Cố vấn: Quang, Toàn, Thiện, Kiệt | Commit: Task T14-02

---

## PHẦN 1: MÔ HÌNH AI, DISTILLATION, LƯỢNG TỬ HÓA INT8 & BẤT ĐỊNH (Q1 - Q5)

### Q1 (Giám khảo AI): "Tại sao các bạn chọn Decoupled Knowledge Distillation (DKD) thay vì KD truyền thống của Hinton?"
**Trả lời của Tài**:
> "Thưa Thầy/Cô, trong KD truyền thống của Hinton, hàm mất mát distillation nén cả xác thực đúng (Target Class) và các xác suất của các lớp không phải mục tiêu (Non-target Classes) vào chung một đại lượng. Đối với bài toán rung động cơ khí có 4 lớp, mối quan hệ tương quan giữa các dạng lỗi (ví dụ lỗi Vòng trong BPFI và Vòng ngoài BPFO thường có hài bậc cao chồng lấn) mang thông tin cấu trúc vật lý cực kỳ quý giá. 
> DKD tách rời loss thành hai thành phần độc lập: **TCKD (Target Class KD)** và **NCKD (Non-target Class KD)**. Chúng tôi đặt hệ số $\beta_\text{NCKD} = 8.0$ lớn hơn $\alpha_\text{TCKD} = 1.0$. Nhờ đó, mô hình học sinh nhỏ (VibraDistillMicro chỉ 8,677 tham số) học trọn vẹn sự phân tách tinh vi giữa các đỉnh phổ lỗi mà không bị lấn át bởi lớp chiếm ưu thế, nâng F1-score từ 91.2% lên **98.45%**."

### Q2 (Giám khảo AI): "Mô hình INT8 có bị tràn số (overflow) khi chạy trên phần cứng không? Các bạn xử lý Post-Training Quantization (PTQ) như thế nào?"
**Trả lời của Tài**:
> "Dạ thưa Thầy, để chống tràn số 100%:
> 1. Toàn bộ lớp BatchNorm được gập trực tiếp vào trọng số Conv1D (`fold_batchnorm`) trước khi lượng tử hóa, triệt tiêu hoàn toàn sai số trôi bias.
> 2. Chúng tôi áp dụng lượng tử hóa đối xứng (Symmetric INT8) với dải giá trị $[-128, 127]$, zero-point $Z = 0$.
> 3. Tỷ lệ Scale factor đầu ra được tính toán theo công thức chuẩn: $S_\text{bias} = S_\text{in} \times S_\text{weight}$.
> 4. Bộ tích lũy (Accumulator) trong NPU 24-way MAC trên FPGA được thiết kế độ rộng **32-bit có dấu**, trong khi phép nhân là $8\text{-bit} \times 8\text{-bit} = 16\text{-bit}$. Vì cửa sổ tính toán là 512 điểm, giá trị tích lũy tối đa không bao giờ vượt quá $512 \times 127 \times 127 \approx 8.25 \times 10^6$, hoàn toàn nằm gọn trong dải của thanh ghi 32-bit ($[-2.14 \times 10^9, 2.14 \times 10^9]$). Do đó về mặt toán học, **xác suất tràn số là đúng bằng 0**."

### Q3 (Giám khảo AI): "Tại sao độ chính xác trên tập 14-mil và 21-mil của CWRU chỉ đạt 43.96% và 50.32%? Có phải mô hình bị overfitting?"
**Trả lời của Tài**:
> "Thưa Thầy, đây không phải lỗi overfitting mà là **minh chứng về cơ chế an toàn chức năng (Functional Safety) theo chuẩn IEC 61508**. 
> Trong giao thức thử thách nghiêm ngặt Zero-Leakage Holdout (Vieira et al., MSSP 2026), mô hình chỉ được học vết nứt ban đầu 7-mil. Khi vết nứt phát triển sâu lên 14-mil và 21-mil, viên bi rơi vào hố nứt sinh ra va đập kép (double-impact) làm đảo pha $180^\circ$. Một mô hình Softmax ngây thơ sẽ đoán bừa với độ tự tin ảo 99%. 
> Ngược lại, VibraDistillMicro tích hợp **Dirichlet Evidential Deep Learning (EDL)**: Độ bất định nhận thức (Epistemic Vacuity) lập tức vọt lên $u = 0.375$ (vượt ngưỡng cảnh báo $0.35$). Hệ thống nhận diện đây là dạng xung kích chưa từng thấy và kích hoạt cơ chế mở rộng biên Conformal Prediction để cảnh báo kỹ sư bảo trì thay vì phát lệnh điều khiển sai!"

### Q4 (Giám khảo AI): "Thuật toán HopACP của các bạn khác gì so với Conformal Prediction truyền thống?"
**Trả lời của Tài**:
> "Thưa Thầy, Conformal Prediction truyền thống yêu cầu tính chất hoán vị được (Exchangeability), vốn bị vi phạm nghiêm trọng khi động cơ thay đổi tải hoặc vận tốc góc. 
> Thuật toán **HopACP (Higher-Order Adaptive Conformal Prediction)** của chúng tôi bổ sung thêm thành phần vi sai (Derivative term):
> $$\lambda_{t+1} = \lambda_t + \gamma(\alpha - \text{err}_t) + \beta(\text{err}_t - \text{err}_{t-1})$$
> Khi xảy ra đột biến tải (load-shift từ 0 HP lên 3 HP), số hạng $\beta \Delta e_t$ lập tức kích hoạt mở rộng độ rộng dải tin cậy trong vòng đúng 1 bước cập nhật, giúp dải tin cậy duy trì độ bao phủ thực tế **$\ge 90.04\%$**, nhanh hơn 6.5 lần so với ACP tích phân bậc một."

### Q5 (Giám khảo AI): "Mô hình này có chạy được trên các dòng máy khác không? Có bằng chứng zero-shot transfer không?"
**Trả lời của Tài**:
> "Dạ có, thưa Thầy! Chúng tôi đã kiểm chứng zero-shot trực tiếp trên tập **MFPT Benchmark** (vòng bi Nice 1012 có 16 viên bi, khác hoàn toàn vòng bi CWRU có 9 viên bi).
> Bằng kỹ thuật **Kinematic Order Warping** với hệ số dãn trục bậc quay $\gamma = 1.85$, các đỉnh phổ lỗi được co dãn khớp với hệ tọa độ động học của mô hình, giúp độ chính xác nhận dạng lỗi zero-shot tăng vọt từ $11.5\%$ lên **$36.0\%$** mà không cần finetune hay huấn luyện lại bất kỳ tham số nào."

---

## PHẦN 2: XỬ LÝ TÍN HIỆU SỐ (DSP) & DẢI THÔNG CẢM BIẾN (Q6 - Q10)

### Q6 (Giám khảo DSP): "Tại sao các bạn thay cảm biến ST IIS3DWB bằng ADXL345? Dải thông 3.2 kHz có quá thấp không?"
**Trả lời của Quang & Tài**:
> "Thưa Thầy, chúng tôi áp dụng **Kiến trúc Kiểm chứng Kép (Dual-Mode Architecture)**:
> 1. **Trên mô hình cơ khí tại bàn**: Động cơ 130 quay tối đa $2,000\,\text{RPM}$ ($f_r = 33.3\,\text{Hz}$). Tần số lỗi cao nhất là $\text{BPFI} \approx 4.27 \times 33.3 = 142.2\,\text{Hz}$. Bậc hài thứ 10 của lỗi là $1,422\,\text{Hz}$. Cảm biến ADXL345 lấy mẫu $3,200\,\text{Hz}$ cho dải thông Nyquist $1,600\,\text{Hz} > 1,422\,\text{Hz}$, hoàn toàn thỏa mãn định lý lấy mẫu Nyquist-Shannon.
> 2. **Trên môi trường công nghiệp băng thông cao**: Chúng tôi tích hợp sẵn chế độ **HIL Streamer USB-UART 921,600 baud** và **BRAM Playback**, bơm trực tiếp tín hiệu 12 kHz và 25.6 kHz từ CWRU và PRONOSTIA vào FPGA. Toàn bộ chuỗi IP Core FIR/FFT trên FPGA Gowin Tang Primer 20K được tổng hợp chạy ở xung nhịp 100 MHz, sẵn sàng đáp ứng mọi cảm biến công nghiệp cao cấp như IIS3DWB."

### Q7 (Giám khảo DSP): "Bộ lọc số FIR 32-tap Minimum-Phase có ưu điểm gì so với Linear-Phase FIR?"
**Trả lời của Toàn**:
> "Thưa Thầy, bộ lọc Linear-Phase FIR đối xứng có độ trễ nhóm (Group Delay) cố định bằng $(N-1)/2 = 15.5$ chu kỳ lấy mẫu, làm tín hiệu bị trễ đáng kể. 
> Chúng tôi thiết kế bộ lọc **Minimum-Phase FIR 32-tap** bằng thuật toán chuyển đổi Cepstral: Toàn bộ các điểm không (zeros) nằm ngoài vòng tròn đơn vị được phản chiếu vào bên trong mặt phẳng Z. Nhờ đó, năng lượng xung tập trung ngay ở các tap đầu tiên, giảm độ trễ nhóm hiệu dụng từ 15.5 mẫu xuống chỉ còn **3.2 mẫu**, giúp hệ thống phát hiện xung va đập sớm hơn $79\%$ thời gian, bảo vệ tiếp điểm rơ-le ngắt tức thì."

### Q8 (Giám khảo DSP): "Giải thuật tách bao sóng (Envelope Demodulator) được thiết kế như thế nào trên FPGA?"
**Trả lời của Toàn**:
> "Thưa Thầy, giải thuật giải điều chế bao sóng gồm 2 tầng thực thi hoàn toàn trong 1 chu kỳ xung nhịp 100 MHz:
> 1. Bộ chỉnh lưu toàn sóng: Thực hiện phép lấy trị tuyệt đối $|x[n]|$ bằng toán tử bù hai đảo bit khi bit dấu là 1.
> 2. Bộ lọc thông thấp rò rỉ nhân quả (Causal Leaky Peak Envelope):
>    $$y[n] = \max\left(|x[n]|,\, \alpha \cdot y[n-1]\right)$$
>    Với $\alpha = 1 - 2^{-6} = 0.984375$. Phép nhân $\alpha \cdot y[n-1]$ được thực hiện bằng toán tử dịch bit: $y[n-1] - (y[n-1] \gg 6)$, **hoàn toàn không tiêu tốn bộ nhân DSP**, đạt thông lượng cực đại 100 triệu mẫu/giây."

### Q9 (Giám khảo DSP): "Độ phân giải tần số FFT 512-point là bao nhiêu? Có bị hiện tượng rò rỉ phổ không?"
**Trả lời của Toàn**:
> "Thưa Thầy, với $F_s = 13.333\,\text{kHz}$ và $N = 512$, độ phân giải tần số là $\Delta f = \frac{13333}{512} \approx 26.04\,\text{Hz}$ (hoặc $\Delta f = 6.25\,\text{Hz}$ tại $F_s = 3.2\,\text{kHz}$). 
> Để triệt tiêu rò rỉ phổ (Spectral Leakage), chúng tôi áp dụng cửa sổ Hanning trước khối FFT, giảm búp sóng phụ xuống dưới $-31.5\,\text{dB}$. Đồng thời, mô hình NPU tích hợp vector đặc trưng vật lý 8 chiều (Physics Kinematic Vector) được trích xuất bằng phép nội suy parabol 3 điểm, khắc phục hoàn toàn hiện tượng picket-fence effect."

### Q10 (Giám khảo DSP): "Đo tốc độ động cơ bằng encoder quang 30 PPR như thế nào để tránh sai số khi motor rung giật?"
**Trả lời của Thiện**:
> "Thưa Thầy, encoder quang 30 xung được kết nối vào chân P0.5 của MCU Sonix, sử dụng ngoại vi Timer Capture `CT16B0_CAP0`. Chúng tôi kích hoạt bộ lọc số chống nhiễu phần cứng (Input Digital Filter 8 chu kỳ xung nhịp) ngay tại cổng vào timer. Vận tốc góc RPM được tính toán trung bình trượt qua cửa sổ 5 vòng quay ($150$ xung ngắt), triệt tiêu sai số do rung động giật trục cơ khí, đạt độ chính xác đo RPM sai số $< 1.5\%$."

---

## PHẦN 3: KIẾN TRÚC PHẦN CỨNG FPGA GOWIN TANG PRIMER 20K (Q11 - Q15)

### Q11 (Giám khảo Bán dẫn): "FPGA Tang Primer 20K có bao nhiêu tài nguyên? Các bạn đã tối ưu hóa PPA như thế nào?"
**Trả lời của Toàn & Quang**:
> "Thưa Thầy, chip Gowin GW2A-LV18PG256 có 20,736 LUT4, 46 khối BSRAM (103.5 KB) và 48 bộ nhân DSP18E.
> Mức độ chiếm dụng tài nguyên thực tế của dự án:
> - **LUTs**: 38% (7,880 / 20,736 LUTs)
> - **BSRAMs**: 52% (24 / 46 BSRAMs) - Trong đó 6 BSRAM chứa trọn bộ trọng số INT8, 8 BSRAM cho FFT & Ping-pong activation.
> - **DSPs**: 41% (20 / 48 DSP slices)
> - **Công suất tiêu thụ**: Đo đạc bằng ampe kế và Gowin Power Analyzer chỉ đạt **142 mW** tại xung nhịp 100 MHz. Chúng tôi hoàn toàn không sử dụng chip nhớ ngoài DDR3, loại bỏ hoàn toàn điện năng tiêu thụ và độ trễ chờ nạp DRAM."

### Q12 (Giám khảo Bán dẫn): "NPU 24-way MAC Engine hoạt động theo kiến trúc gì?"
**Trả lời của Toàn**:
> "Thưa Thầy, NPU được thiết kế theo kiến trúc mảng tâm thu (Systolic Array) 1 chiều gồm 24 đơn vị MAC chạy song song. Mỗi chu kỳ xung nhịp 100 MHz, NPU thực hiện đồng thời 24 phép tính nhân-cộng 8-bit $\times$ 8-bit. Nhờ kiến trúc nạp trọng số song song từ 6 BSRAM độc lập (Dual-Port), NPU đạt thông lượng tính toán **2.4 GOP/s**, hoàn thành toàn bộ phép suy luận 8,677 tham số của mô hình trong đúng **0.58 ms**."

### Q13 (Giám khảo Bán dẫn): "Tuyến bus giao tiếp giữa FPGA và MCU hoạt động như thế nào? Có bị lỗi Clock Domain Crossing (CDC) không?"
**Trả lời của Toàn & Thiện**:
> "Thưa Thầy, FPGA đóng vai trò SPI Master phát xung nhịp SCK = 12.5 MHz (chia tần từ 100 MHz hệ thống). Gói tin telemetry gồm đúng 524 Bytes (4B Header, 8B Meta/RPM, 512B Phổ rung). 
> Để chống xung đột miền xung nhịp (CDC) giữa 100 MHz nội bộ và 12.5 MHz ngoại vi, chúng tôi sử dụng cấu trúc **Asynchronous Dual-Clock FIFO BRAM** có mã hóa Gray Code cho các con trỏ ghi/đọc, kết hợp cờ ngắt phần cứng `mcu_irq_pulse` (DRDY) kích hoạt DMA của MCU, đảm bảo tính toàn vẹn dữ liệu 100% không mất một byte nào."

### Q14 (Giám khảo Bán dẫn): "Làm sao nạp bitstream vào chip khi không dùng mạch nạp Sipeed RV Debugger?"
**Trả lời của Toàn**:
> "Thưa Thầy, chúng tôi sử dụng board nạp Kiwi Nano 1p5 tích hợp chip giao tiếp GWU2X tốc độ cao. Điểm then chốt là gạt toàn bộ 4 switch của công tắc gạt DIP SW1 sang vị trí 'ON' để kích hoạt buffer JTAG, kết nối 4 dây TDI, TMS, TCK, TDO và GND chung sang cổng J3 của Tang Primer 20K. Chúng tôi ghi bitstream trực tiếp vào bộ nhớ Flash nội (Embedded SPI Flash) của GW2A-18, giúp hệ thống **tự khởi động độc lập (Cold Boot) trong < 80 ms** ngay khi cắm nguồn Type-C."

### Q15 (Giám khảo Bán dẫn): "Thời gian trễ 0.75 ms được đo đạc và kiểm chứng bằng công cụ gì?"
**Trả lời của Quang**:
> "Thưa Thầy, độ trễ 0.75 ms được đo đạc độc lập bằng máy hiện sóng số DSO 2 kênh (Rigol DS1054Z / Keysight):
> - **Kênh 1 (Vàng)**: Kẹp vào chân DRDY (TP1 - J3 pin 19) báo hiệu thời điểm mẫu rung xuất hiện.
> - **Kênh 2 (Xanh)**: Kẹp vào chân P1.0 (TP2) của MCU điều khiển ngắt cuộn hút rơ-le.
> Khoảng cách thời gian $\Delta t$ giữa sườn lên của TP1 và sườn lên của TP2 trên màn hình DSO đo được chính xác là **0.75 ms**, nhanh hơn gấp 6.6 lần so với tiêu chuẩn công nghiệp 5.0 ms."

---

## PHẦN 4: VI ĐIỀU KHIỂN SONIX SN32F407 & AN TOÀN CHỨC NĂNG SIL-2 (Q16 - Q20)

### Q16 (Giám khảo Nhúng): "MCU Sonix SN32F407 chỉ có 8 KB RAM, làm sao chạy được hệ thống mà không tràn bộ nhớ?"
**Trả lời của Thiện**:
> "Thưa Thầy, tổng dung lượng SRAM của chip là 8,192 Bytes. Chúng tôi quản lý phân bổ tĩnh tuyệt đối (Zero Dynamic Allocation `malloc`):
> 1. **Driver OLED Page-Banded**: Chỉ cấp phát đúng 128 Bytes RAM cho 1 trang hiển thị (thay vì 1,024 Bytes full-frame), render cuốn chiếu 8 trang.
> 2. **SPI DMA Ring Buffer**: 524 Bytes $\times$ 2 bộ đệm Ping-pong = 1,048 Bytes.
> 3. **Cấu trúc HopACP & Biến toàn cục (BSS)**: 320 Bytes.
> Tổng bộ nhớ RAM tĩnh tiêu tốn chỉ **3.4 KB (chiếm 42.5% SRAM)**. Hệ thống luôn dư thừa **4.7 KB RAM cho vùng Stack**, đảm bảo an toàn tuyệt đối khi các hàm ngắt SPI DMA và Timer Capture lồng nhau, không bao giờ bị tràn Stack hay HardFault."

### Q17 (Giám khảo Nhúng): "Tại sao không dùng thư viện toán học float `math.h` trên ARM Cortex-M0?"
**Trả lời của Tài & Thiện**:
> "Thưa Thầy, nhân ARM Cortex-M0 sử dụng tập lệnh Thumb-1 và **không có bộ xử lý phần cứng FPU**. 
> Nếu gọi các hàm số thực float, trình biên dịch sẽ phải liên kết thư viện giả lập phần mềm (Software Floating-Point Emulation), làm tăng kích thước file nhị phân Flash thêm 8 - 12 KB (chiếm tới 35% bộ nhớ Flash 32KB) và mỗi phép tính nhân chia float mất hàng trăm chu kỳ xung nhịp.
> Bằng cách chuyển đổi 100% giải thuật HopACP sang định dạng **Q16.16 Fixed-Point**, toàn bộ phép tính chỉ sử dụng lệnh cộng/trừ và dịch bit số nguyên 32-bit `int32_t`, thực thi trong vòng **< 15 chu kỳ xung nhịp (< 0.25 us)** và tiết kiệm 95% mã nguồn Flash."

### Q18 (Giám khảo An toàn): "Cơ cấu rơ-le ngắt an toàn SIL-2 hoạt động như thế nào? Có sợ rơ-le tự ngắt nhầm khi MCU reset?"
**Trả lời của Thiện**:
> "Thưa Thầy, module rơ-le 5V được cách ly quang bằng Optocoupler. Tiếp điểm Thường Đóng (NC) được đấu nối tiếp trên đường cấp nguồn động cơ:
> 1. **Chống tự ngắt khi Reset (Fail-Safe)**: Mạch điều khiển được thiết kế logic Active-High an toàn. Khi MCU khởi động hoặc reset, các chân GPIO mặc định ở trạng thái High-Z (được kéo trở xuống 0V), rơ-le giữ nguyên tiếp điểm đóng cho motor chạy. Chỉ khi firmware phát hiện lỗi xác thực và xuất mức logic 1 có chủ đích, rơ-le mới nhảy ngắt nguồn.
> 2. **Bảo vệ phần cứng**: Module có diode dập xung ngược (Flyback Diode) triệt tiêu sức điện động tự cảm (Inductive Kickback) của cuộn hút, ngăn chặn tia lửa điện và xung áp ngược làm treo vi điều khiển."

### Q19 (Giám khảo Nhúng): "Nếu màn hình OLED bị đơ bus I2C thì hệ thống ngắt bảo vệ rơ-le có bị treo theo không?"
**Trả lời của Kiệt & Thiện**:
> "Thưa Thầy, hoàn toàn không bị treo! 
> Thứ nhất, quy trình cập nhật OLED được lập trình theo cơ chế Non-blocking với hàm kiểm tra thời gian chờ `I2C_Timeout()`. Nếu chân SDA bị treo quá 2 ms, MCU tự động phát chuỗi 9 xung clock để giải phóng bus I2C.
> Thứ hai, hàm ngắt an toàn `Trip_Safety_Interlock()` được kích hoạt trực tiếp từ **Ngắt ưu tiên cao nhất (Highest Priority NVIC Interrupt)** của kênh SPI DMA từ FPGA. Dù màn hình OLED có gặp sự cố vật lý, vòng lặp ngắt bảo vệ rơ-le vẫn thực thi độc lập và ngắt nguồn động cơ trong đúng **0.75 ms**."

### Q20 (Giám khảo Thương mại): "Chi phí sản xuất bo mạch thương mại của giải pháp này là bao nhiêu so với các giải pháp hiện có?"
**Trả lời của Quang**:
> "Thưa Ban Giám khảo, đây chính là lợi thế cạnh tranh mang tính đột phá của Team Porygon:
> - Một hệ sinh thái giám sát rung động công nghiệp hiện nay dùng NVIDIA Jetson hoặc PLC công nghiệp có giá từ **\$150 đến \$500 USD** (khoảng 3.8 đến 12 triệu VNĐ) và tiêu thụ 5W - 15W điện năng.
> - Giải pháp VibraDistill-Edge chỉ sử dụng chip nội địa Gowin GW2A-18 (\$12) + MCU Sonix SN32F407 (\$1.8) + Cảm biến gia tốc (\$3). Tổng chi phí linh kiện phần cứng (BOM Cost) **chưa đến 500,000 VNĐ (\$20 USD)**, tiêu thụ vỏn vẹn **184 mW** (có thể chạy bằng pin sạc dự phòng liên tục trong 40 giờ). 
> Giải pháp sẵn sàng thương mại hóa hàng loạt để lắp đặt giám sát trực tiếp cho hàng triệu mô-tơ bơm và quạt công nghiệp tại các nhà máy Việt Nam!"
