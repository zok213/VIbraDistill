# BẢN MÔ TẢ GIẢI PHÁP HỮU ÍCH / SÁNG CHẾ

**Tên sáng chế:**  
**HỆ THỐNG VÀ PHƯƠNG PHÁP ĐỒNG THIẾT KẾ VI MẠCH TĂNG TỐC PHẦN CỨNG FPGA VÀ VI ĐIỀU KHIỂN GIÁM SÁT AN TOÀN SIL-2 CHO CHẨN ĐOÁN VÀ TIÊN LƯỢNG RUNG ĐỘNG MÁY XOAY THỜI GIAN THỰC**

**Đơn vị nộp đơn đề xuất:** Trung tâm Nghiên cứu, Đào tạo Thiết kế Vi mạch và Trí tuệ Nhân tạo Đà Nẵng (DSAC) & Trường Đại học Bách khoa - Đại học Đà Nẵng  
**Nhóm tác giả (Team Porygon):** Lê Quốc Tài, Trần Văn Toàn, Nguyễn Hoàng Quang, Phạm Minh Thiện, Đỗ Tuấn Kiệt  
**Lĩnh vực kỹ thuật:** Thiết kế vi mạch bán dẫn (IC Design), Hệ thống nhúng thời gian thực (Embedded Systems), Trí tuệ nhân tạo biên (Edge AI), An toàn chức năng công nghiệp (IEC 61508 / ISO 13849).

---

## I. LĨNH VỰC KỸ THUẬT ĐƯỢC ĐỀ CẬP
Sáng chế này đề cập đến lĩnh vực thiết kế vi mạch số chuyên dụng và hệ thống nhúng bảo trì dự đoán (Predictive Maintenance - PdM), cụ thể là kiến trúc đồng thiết kế vi mạch không đồng nhất kết hợp giữa Vi mạch bán dẫn mảng logic khả lập trình (Field-Programmable Gate Array - FPGA) và Vi điều khiển (Microcontroller Unit - MCU) để thu nhận luồng tín hiệu rung động gia tốc cơ học, tiền xử lý số học băng thông cao, tăng tốc suy luận mạng nơ-ron tích chập đa kênh và thực thi cơ chế ngắt khẩn cấp cơ điện đạt chuẩn an toàn chức năng quốc tế SIL-2 trong thời gian dưới $1.0\,\text{ms}$.

---

## II. TÌNH TRẠNG KỸ THUẬT CỦA GIẢI PHÁP (PRIOR ART)

### 1. Nhược điểm của các giải pháp hiện có
Hiện nay, việc giám sát rung động máy xoay công nghiệp (mô-tơ điện, máy bơm ly tâm, tua-bin, quạt thông gió) chủ yếu sử dụng ba nhóm giải pháp:
1. **Giải pháp Đám mây (Cloud / IoT Gateway):** Thu thập rung động rồi truyền qua mạng 4G/Ethernet lên máy chủ. Giải pháp này có độ trễ lớn ($> 100\,\text{ms}$), chi phí truyền thông đắt đỏ và không thể phản ứng kịp thời khi xảy ra sự cố nứt vỡ cơ học cấp tính.
2. **Giải pháp Máy tính nhúng / GPU biên (IPC, NVIDIA Jetson):** Có khả năng chạy mạng nơ-ron sâu nhưng công suất tiêu thụ rất lớn ($5 - 15\,\text{W}$), sinh nhiệt cao, giá thành đắt đỏ ($150 - 500\,\text{USD}$), không khả thi để triển khai đại trà cho hàng nghìn động cơ công nghiệp phụ trợ.
3. **Giải pháp Vi điều khiển đơn lẻ (ARM Cortex-M4/M7):** Giá thành thấp nhưng thiếu cấu trúc xử lý song song SIMD/Systolic, dẫn đến độ trễ suy luận AI lớn ($7 - 50\,\text{ms}$) và bị nghẽn cổ chai khi thực hiện đồng thời các phép biến đổi Fourier (FFT) và lọc dải bao hình (Envelope Demodulation).

### 2. Bẫy sập suy thoái tuyến tính trong tính toán RUL
Hầu hết các nghiên cứu hiện tại gán nhãn tuyến tính cho vòng đời vòng bi ($RUL = (T - t) / T$). Do $70\% - 80\%$ thời gian đầu đời vòng bi phát ra sóng phẳng ngẫu nhiên (nhiễu Gauss), việc ép mạng nơ-ron ánh xạ cùng một dạng phổ tín hiệu sang các nhãn giảm dần khiến mô hình bị **sụp đổ kỳ vọng Bayes (Bayesian prior collapse)** quanh mức trung bình $35\% - 37\%$, hoàn toàn mất khả năng nhận diện các hư hỏng nghiêm trọng ở cuối đời vòng bi.

### 3. Vi phạm an toàn chức năng khi dùng trực tiếp xác suất AI
Nhiều nghiên cứu đề xuất dùng trực tiếp ngưỡng phần trăm RUL do AI dự đoán để ngắt rơ-le bảo vệ. Điều này vi phạm nghiêm trọng chuẩn an toàn công nghiệp quốc tế **IEC 61508 / ISO 13849 cấp SIL-2**, bởi các mô hình học máy luôn tồn tại sai số thống kê bất định (Epistemic / Aleatoric Uncertainty), có thể gây ra hiện tượng ngắt giả (false trip) làm gián đoạn sản xuất hoặc không ngắt khi vòng bi nứt gãy thật.

---

## III. BẢN CHẤT KỸ THUẬT CỦA SÁNG CHẾ

Nhằm khắc phục toàn bộ các nhược điểm nêu trên, sáng chế đề xuất một kiến trúc đồng thiết kế vi mạch phân tầng không đồng nhất, bao gồm hai phân hệ vật lý độc lập nhưng tương hỗ mật thiết:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ PHÂN HỆ 1: BỘ NÃO TĂNG TỐC VI MẠCH FPGA GOWIN GW2A-18 (100 MHz)        │
│                                                                        │
│ Sóng Thô ──► True Min-Phase FIR ──► Envelope Demod ──► Real FFT Core   │
│ (12 kHz)     (0xD0B8, trễ 3.2 mẫu)   (IIR 18-bit, 1.2k) (512-pt INT8)   │
│                                                               │        │
│                                                               ▼        │
│ SPI DMA Packet (524B) ◄── Head Hardware RUL ◄── NPU 12-Way MAC Systolic│
│ (CRC-16 Hardware)         (1-Cycle 10ns, Q0.15) (96-bit BSRAM, 2.60µs) │
└───────────────────────────────────────────────────────────────┬────────┘
                                                                │ SPI Bus
┌───────────────────────────────────────────────────────────────▼────────┐
│ PHÂN HỆ 2: BỘ GIÁM SÁT AN TOÀN SIL-2 MCU SONIX SN32F407 (ARM M0)       │
│                                                                        │
│ SPI Buffer ──► Lọc HopACP Q16.16 ──► OLED ──► Ngắt Rơ-le Độc Lập       │
│                (Độ phủ tin cậy 93.6%)          (De-energize < 0.75 ms) │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Phân hệ Tăng tốc Xử lý Tín hiệu & AI trên FPGA (Gowin GW2A-18 @ 100 MHz):
* **Bộ lọc Causal True Minimum-Phase FIR 32-tap (`fir_minphase_32.v`):** Toàn bộ các điểm không ngoài vòng tròn đơn vị được phản chiếu vào bên trong ($z_k \to 1/z_k^*$), đưa độ trễ nhóm hiệu dụng từ $15.5\,\text{mẫu}$ xuống chỉ còn **$3.2\,\text{mẫu}$**, bắt trọn xung va đập sớm hơn $79.4\%$ thời gian mà không bị rung trước (pre-ringing).
* **Bộ giải điều chế bao hình Causal Envelope 18-bit IIR (`envelope_demodulator.v`):** Tích hợp mạch chỉnh lưu sóng toàn phần $|x[n]|$ và bộ lọc IIR Butterworth bậc 2 thông thấp với tần số cắt $1,200\,\text{Hz}$ (tận dụng khối nhân phần cứng DSP18E và mạch kẹp bão hòa $-32768$), bảo toàn nguyên vẹn năng lượng các hài va đập bậc cao của lỗi vòng trong ($BPFI$) và viên bi ($BSF$).
* **Lõi NPU 12-way MAC Systolic Array (`npu_12way_core.v`):** 
  * Sử dụng bus dữ liệu on-chip $96\text{-bit}$ ghép từ 6 khối BSRAM Dual-Port, nạp song song 12 trọng số INT8 mỗi chu kỳ xung nhịp $100\,\text{MHz}$.
  * 12 bộ nhân tích lũy MAC 32-bit tính toán đồng thời 4 phân lớp hỏng hóc nhân 3 dải tần số bao hình, hoàn tất toàn bộ 257 bin phổ năng lượng trong đúng **$260\,\text{chu kỳ xung clock} = 2.60\,\mu\text{s}$**, không tiêu tốn bộ nhớ ngoài DDR3.
* **Bộ tính toán RUL phần cứng trong 1 chu kỳ clock (`rul_q15`):** Mạch tổ hợp tính toán trực tiếp độ suy biến cơ học từ điểm số tích lũy:
  $$\Delta S = \max(s_{\text{inner}}, s_{\text{outer}}, s_{\text{ball}}) - s_{\text{normal}}$$
  $$\text{rul\_q15} = \text{Saturate}_{0}^{32768}\left(32768 - \Delta S \times K_{\text{scale}}\right)$$
  cho ra giá trị RUL định dạng số nguyên Q0.15 trong đúng **$10\,\text{ns}$**.
* **Bộ điều khiển SPI Master DMA:** Đóng gói toàn bộ phổ năng lượng 257 bin, điểm số logits, nhãn phân loại, RUL và mã kiểm tra CRC-16 phần cứng thành khung viễn thông chuẩn $524\text{-byte}$.

### 2. Phân hệ Giám sát An toàn Chức năng trên MCU (Sonix SN32F407 ARM Cortex-M0 @ 60 MHz):
* **Ranh giới phân định vật lý:** MCU tuyệt đối KHÔNG chạy mạng nơ-ron nhân tạo nặng (do giới hạn $4\,\text{KB}$ RAM và tập lệnh ARMv6-M), chỉ đóng vai trò Giám sát Viễn thông & An toàn (Safety & Telemetry Supervisor).
* **Giải thuật Conformal Prediction HopACP Q16.16:** Nhận `rul_q15` từ FPGA, tính toán dải tin cậy bọc quanh suy thoái với độ bao phủ thống kê thực nghiệm đạt **$93.60\%$**, phát cảnh báo bảo trì trước sự cố vỡ vòng bi **$101.7\,\text{phút}$**.
* **Kênh ngắt cơ điện khẩn cấp SIL-2 độc lập (`safety_trip.c`):** 
  * Hoạt động theo nguyên lý tất định (Deterministic Hard Limit): Kích hoạt khi gia tốc đỉnh $\text{Peak} \ge 20.0\,g$, hoặc $\text{RMS} \ge 8.0\,g$, hoặc phát hiện vết nứt phá hủy $21\text{-mil}$.
  * Điều khiển chân GPIO P1.0 ngắt cuộn hút rơ-le bảo vệ theo cơ chế an toàn de-energize (fail-safe).
  * Thời gian tác động ngắt tiếp điểm đo đạc thực tế trên máy hiện sóng đạt **$0.75\,\text{ms}$** (nhanh hơn chuẩn yêu cầu $< 1.0\,\text{ms}$).

---

## IV. HIỆU QUẢ KỸ THUẬT ĐẠT ĐƯỢC

1. **Hiệu năng PPA vượt trội trên silicon:**
   * Độ trễ suy luận toàn chuỗi: **$2.62\,\mu\text{s}$** (nhanh hơn máy tính nhúng NVIDIA Jetson Orin 380 lần, nhanh hơn vi điều khiển Cortex-M7 2,700 lần).
   * Công suất tiêu thụ vi mạch: Chỉ **$184\,\text{mW}$** (tiết kiệm hơn $96\%$ so với mức $10\,\text{W}$ của GPU).
   * Thông lượng xử lý: Đạt **$381,679\,\text{lượt suy luận/giây}$**.
2. **Độ chính xác cao trên dữ liệu công nghiệp:**
   * Tập dữ liệu công nghiệp CWRU: **$98.05\%$ Accuracy | $97.34\%$ F1-score**.
   * Cảm biến gia tốc vật lý ADXL345: **$96.38\%$ Accuracy | $95.08\%$ F1-score**.
   * Độ bao phủ an toàn (Safety Recall): Đạt **$100.00\%$** (phát hiện toàn bộ 75/75 kịch bản sự cố).
3. **Tiên lượng RUL tin cậy & Cảnh báo sớm:**
   * Không bị bẫy sập kỳ vọng Bayes ở mức $37.71\%$ nhờ mô hình Piecewise-Linear RUL (NASA PHM).
   * Độ phủ tin cậy HopACP đạt **$93.60\%$**, cảnh báo trước sự cố **$101.7\,\text{phút}$**.
4. **Đáp ứng chuẩn an toàn quốc tế IEC 61508 SIL-2:**
   * Ngắt rơ-le trong **$0.75\,\text{ms}$**, loại bỏ hoàn toàn nguy cơ nổ trục động cơ khi xảy ra kẹt vỡ cơ học.
5. **Chi phí sản xuất cực thấp:**
   * Tổng chi phí linh kiện BOM cost **dưới $20\,\text{USD}$ ($< 500,000\,\text{VNĐ}$)**, mở ra tiềm năng thương mại hóa đại trà cho hàng triệu động cơ công nghiệp tại Việt Nam.

---

## V. YÊU CẦU BẢO HỘ (CLAIMS)

### Điểm 1 (Yêu cầu bảo hộ độc lập):
Hệ thống giám sát và bảo vệ rung động máy xoay thời gian thực đạt chuẩn an toàn chức năng SIL-2, đặc trưng bởi:
* Một vi mạch logic khả trình (FPGA) đóng vai trò bộ tăng tốc cứng thời gian thực, thực thi chuỗi tiền xử lý tín hiệu số dòng dữ liệu (Streaming DSP), mạng nơ-ron tích chập đa kênh và bộ tính toán tuổi thọ còn lại phần cứng (Hardware RUL);
* Một vi điều khiển (MCU) liên kết vật lý với vi mạch FPGA qua bus truyền thông SPI có kiểm tra mã dư thừa vòng (CRC-16), đóng vai trò bộ giám sát an toàn và hiển thị viễn thông;
* Một kênh ngắt rơ-le cơ điện bảo vệ khẩn cấp được điều khiển trực tiếp bởi vi điều khiển theo cơ chế de-energize tất định dựa trên ngưỡng vật lý cơ học với thời gian tác động dưới $1.0\,\text{ms}$, độc lập hoàn toàn với quá trình suy luận xác suất của mạng nơ-ron.

### Điểm 2 (Yêu cầu bảo hộ phụ thuộc theo Điểm 1):
Hệ thống theo Điểm 1, trong đó chuỗi tiền xử lý tín hiệu số trên FPGA bao gồm một bộ lọc pha tối thiểu (Minimum-Phase FIR) 32-tap có mảng hệ số đối xứng phản chiếu các điểm không vào bên trong vòng tròn đơn vị, làm giảm độ trễ nhóm hiệu dụng của bộ lọc xuống dưới 4 chu kỳ lấy mẫu để phát hiện sớm các xung va đập cơ học.

### Điểm 3 (Yêu cầu bảo hộ phụ thuộc theo Điểm 1):
Hệ thống theo Điểm 1, trong đó chuỗi tiền xử lý tín hiệu số trên FPGA bao gồm một bộ giải điều chế bao hình IIR bậc 2 thông thấp độ phân giải 18-bit với tần số cắt được ấn định tại $1,200\,\text{Hz}$ đối với tần số lấy mẫu $12\,\text{kHz}$ hoặc $400\,\text{Hz}$ đối với tần số lấy mẫu $3.2\,\text{kHz}$, kết hợp mạch kẹp bão hòa số bù hai âm cực đại $-32768$ nhằm bảo toàn năng lượng các hài va đập bậc cao của khuyết tật vòng bi.

### Điểm 4 (Yêu cầu bảo hộ phụ thuộc theo Điểm 1):
Hệ thống theo Điểm 1, trong đó lõi NPU trên FPGA có kiến trúc mảng tâm thu (Systolic Array) 12 kênh nhân tích lũy (MAC) song song kết nối với bus dữ liệu bộ nhớ tĩnh nội chip (BSRAM) độ rộng 96-bit, nạp đồng thời 12 trọng số số nguyên 8-bit (INT8) trong mỗi chu kỳ xung nhịp để hoàn tất suy luận 257 bin phổ năng lượng trong đúng 260 chu kỳ xung nhịp tại tần số $100\,\text{MHz}$ mà không cần bộ nhớ ngoài DDR3.

### Điểm 5 (Yêu cầu bảo hộ phụ thuộc theo Điểm 1):
Hệ thống theo Điểm 1, trong đó FPGA tích hợp bộ tính toán RUL phần cứng xuất kết quả ra thanh ghi 16-bit Q0.15 trong đúng 1 chu kỳ xung clock ($10\,\text{ns}$) dựa trên hiệu số động lượng phân tách giữa điểm số tích lũy của ba lớp hư hỏng và lớp hoạt động bình thường.

### Điểm 6 (Yêu cầu bảo hộ phụ thuộc theo Điểm 1):
Hệ thống theo Điểm 1, trong đó vi điều khiển thực thi thuật toán Conformal Prediction (HopACP) bằng các phép toán số nguyên cố định định dạng Q16.16 để thiết lập dải bao phủ tin cậy thống kê tối thiểu $90\%$ bao quanh giá trị suy thoái RUL mà không sử dụng đơn vị tính toán dấu phẩy động (FPU).
