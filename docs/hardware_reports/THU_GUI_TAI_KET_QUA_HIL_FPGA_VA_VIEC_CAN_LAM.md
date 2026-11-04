# GỬI TÀI: KẾT QUẢ KIỂM TRA CHUỖI HIL FPGA VÀ NHỮNG VIỆC CẦN TÀI LÀM

**Người gửi:** Đội ngũ Kỹ thuật Phần cứng FPGA / MCU  
**Người nhận:** Tài (Porygon Team - Phụ trách AI & Mô hình Hóa)  
**Thời gian lập:** 02/11/2026  
**Dự án:** VibraDistill-Edge (Gowin Tang Primer 20K FPGA & Sonix SN32F407 MCU)  

---

## 1. Mình đang làm gì

Mình đang làm lại và xác thực độc lập toàn bộ phần FPGA theo repository của Tài (`nhánh tai`). 

Cụ thể, mình nạp 3 file kích thích phần cứng:
* `stimulus_cwru_normal.hex` (512 mẫu INT16)
* `stimulus_cwru_inner.hex` (512 mẫu INT16)
* `stimulus_cwru_outer.hex` (512 mẫu INT16)

vào top module [`gowin_top_soc_hil.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/gowin_top_soc_hil.v). 

Chuỗi xử lý thực tế trên board chạy nối tiếp qua các khối:
$$\text{FIR 32 tap} \longrightarrow \text{Envelope IIR} \longrightarrow \text{Cửa sổ Hann} \longrightarrow \text{FFT 512 điểm} \longrightarrow \text{mag\_data (16-bit)} \longrightarrow \text{Cắt ngưỡng 127} \longrightarrow \text{NPU 12 kênh} \longrightarrow \text{SPI 524 byte} \longrightarrow \text{MCU} \longrightarrow \text{OLED}$$

Mục tiêu là kiểm tra xem khối FPGA chạy có khớp chính xác với thuật toán mô phỏng không, đồng thời nhờ các trợ lý AI chuyên gia (Antigravity, Claude) cùng rà soát độc lập. Dưới đây là bảng tổng hợp kết quả chi tiết, phân loại rõ ràng phần chắc chắn và phần còn nghi vấn.

---

## 2. Phần đã kiểm tra: FPGA làm đúng theo Verilog

Mình đã mô phỏng bit-true chính xác các hệ số trong [`fir_minphase_32.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/fir_minphase_32.v) và [`envelope_demodulator.v`](file:///t:/MCU_FPGA/FPGA_FINAL/src/envelope_demodulator.v), sau đó đối chiếu trực tiếp với phổ tần số do FPGA xuất ra:
* **Bộ Outer và Inner:** Phổ đo đạc trên FPGA khớp rất sát với mô phỏng chuẩn trong dung sai $\sim 1 - 2\%$ (tỉ lệ quy đổi: $\text{FPGA} \approx \text{giá trị} / 512$).
* **Bộ Normal:** Phổ xuất ra giữ đúng hình dạng phân bố đặc trưng, nhưng biên độ tổng thể chỉ đạt khoảng $0.68$ lần so với mức dự kiến, đồng thời vùng tần số thấp (từ bin 2 đến bin 8) xuất hiện sai lệch. Hiện tượng này chưa rõ nguyên nhân cụ thể (nghi ngờ do hiện tượng bão hòa tín hiệu đầu vào hoặc tỉ lệ co giãn scale của tầng FFT), phần này mình sẽ tự tra cứu và khoanh vùng thêm.

---

## 3. Những chỗ lệch giữa FPGA và phía huấn luyện của Tài

Dưới đây là bảng đối chiếu chi tiết 6 điểm bất đối xứng kỹ thuật giữa phần cứng RTL FPGA và mã nguồn huấn luyện AI của Tài:

| # | Vấn đề kỹ thuật | Bằng chứng thực tế trong mã nguồn | Mức độ |
| :-: | :--- | :--- | :-: |
| **A** | **Trọng số 12 kênh trong ROM HIL là bản của cảm biến ADXL345 (3.2 kHz):**<br>Script xuất trọng số (`export_fpga_tier1_spectral_weights.py`) đọc cache `cwru_*_adxl345_w512.pt`. Antigravity so khớp nhị phân file `npu_weights_bank0.hex` trong `src/test_npu/roms/hil/` thì trùng khớp 100% với thư mục `adxl345`. Do đó, trục tần số bị lệch tới **3.75 lần** (ví dụ: đỉnh BPFI ở ADXL là bin 26, nhưng ở HIL 12 kHz lại nằm tại bin 7). | Tên file cache huấn luyện; So khớp nhị phân file ROM (`Compare-Object` rỗng). | **Nặng** |
| **B** | **Chuẩn hóa đầu vào NPU không đồng nhất:**<br>• *Phía huấn luyện:* Phổ được chia cho giá trị lớn nhất (Max) của cả 257 bin rồi nhân 127 (đảm bảo bin cực đại luôn đạt 127).<br>• *Phía FPGA:* Hiện chỉ cắt bão hòa cứng đơn giản: `(mag_data > 127) ? 127 : mag_data[7:0]`.<br>Hậu quả: Với bộ Inner, 8 bin đầu tiên đều bị xén phẳng về mức 127, trong khi vector chuẩn huấn luyện là `[127, 65, 25, 36, 22, 9, 12, 12]`. | RTL `gowin_top_soc_hil.v` dòng ~227 so với `StreamingDSPPipeline` trong `pipeline.py`. | **Nặng** |
| **C** | **Tần số cắt bộ lọc bao (Envelope Cutoff):**<br>`pipeline.py` đang mặc định $f_c = 1000\text{ Hz}$ (hàm đang thực thi), trong khi RTL cấu hình $f_c = 1200\text{ Hz}$ (`USE_HIL=1`). Mình đo đạc thực tế: Mức lệch tối đa chỉ khoảng 3–4 bậc INT8 ở dải cao, hoàn toàn không gây ảnh hưởng đến dải tần chẩn đoán chính từ bin 0 đến bin 20. | So khớp hệ số phân số IIR. | **Nhẹ** |
| **D** | **Hệ số bộ lọc FIR:**<br>32 hệ số trong RTL không phải là bộ lọc thông dải 2–5 kHz như ghi chú trong file header. Đáp ứng thực tế đo được: Độ lợi $1.06$ ở DC, đạt $2.9$ ở $500\text{ Hz}$, tạo đỉnh $5.6$ tại $\sim 720\text{ Hz}$, và không có đặc tính pha cực tiểu (minimum phase). Tuy nhiên, phía huấn luyện Python đã dùng cờ `use_rtl_coeffs=True` nên hai bên vẫn đang nhất quán với nhau về mặt dữ liệu. | Đường cong đáp ứng tần số `freqz` trong Python. | **Tài liệu** |
| **E** | **4 giá trị Prior vật lý:**<br>Trên FPGA hiện tại đang gán cố định mức 0 (`in_data <= 8'sd0`), trong khi `pipeline.py` có hàm tính toán các đỉnh prior động từ phổ cơ học. | Báo cáo tích hợp `npu_12way_core.v`. | **Cần xác nhận** |
| **F** | **Số liệu độ chính xác 12 kênh trên Holdout chưa có số đo thực nghiệm:**<br>Các con số "38.2–42.5%", "44.0–48.7%" và tỉ lệ bật cờ `ood_alert` 78.4% / 85.6% là do Antigravity ước tính giải tích (Analytical Projection), không phải log chạy thực. Thực tế repo chỉ mới lưu: Val ADXL = 96.38% (553 mẫu), CNN INT8 trên CWRU 12 kHz (14-mil: 43.85%, 21-mil: 50.05%). | Đối chiếu `experiments/int8_parity.json` và `adxl345_training_report.json`. | **Thiếu số liệu** |

---

## 4. Những việc mình nhờ Tài làm (Theo thứ tự ưu tiên)

1. **Ưu tiên 1 — Xuất lại bộ trọng số 12 kênh cho profile HIL 12 kHz:**  
   * Cần build lại cache dữ liệu CWRU với $f_s = 12000\text{ Hz}$ (áp dụng đúng bộ lọc bao $1200\text{ Hz}$ và bộ hệ số FIR RTL).
   * Chạy lại script [`scripts/export_fpga_tier1_spectral_weights.py`](file:///C:/Users/Admin/Downloads/porygon-tai/porygon-tai/scripts/export_fpga_tier1_spectral_weights.py) để xuất ra 6 file ROM hex (`npu_weights_bank0..5.hex`) và 4 giá trị Bias mới tương ứng.  
   *(Do trên máy mình không có sẵn tập dữ liệu thô CWRU gốc `.mat` nên mình không thể tự chạy bước này được).*

2. **Ưu tiên 2 — Thống nhất và chốt giải pháp chuẩn hóa đầu vào NPU:**  
   * Mình nghiêng về phương án bổ sung khối mạch chia cho Max trên FPGA (để đồng nhất hoàn toàn với mô hình huấn luyện và giúp thuật toán không bị trôi theo biên độ cảm biến). Mình sẽ trực tiếp viết khối RTL này trên phần cứng.
   * **Tuy nhiên, cần Tài cung cấp định nghĩa toán học chính xác:**
     * Tìm giá trị cực đại (Max) trên toàn bộ 257 bin (bao gồm cả bin 0 DC) hay bỏ qua bin 0?
     * Quy tắc làm tròn $\text{round}(x \times 127 / \text{Max})$ dùng chuẩn nào: làm tròn đến số chẵn gần nhất (`half-even` của `np.round`) hay làm tròn lên nửa đơn vị (`half-up`)?
   * *Trường hợp Tài muốn đi theo hướng ngược lại (giữ nguyên FPGA cắt bão hòa 127 và huấn luyện lại AI trên phổ thô bị xén), xin hãy báo sớm để mình thống nhất luồng xử lý.*

3. **Ưu tiên 3 — Cung cấp file kiểm chuẩn mẫu (Golden Vector toàn chuỗi) từ dữ liệu thô:**  
   * Ứng với từng file kích thích thô `stimulus_cwru_normal.hex`, `stimulus_cwru_inner.hex`, `stimulus_cwru_outer.hex`: Tài xuất giúp mình mảng phổ INT8 mong đợi (đủ 257 bin), giá trị 4 Logits và Lớp dự đoán chuẩn.
   * File `cosim_golden.hex` hiện tại trong repo chỉ dùng để kiểm tra riêng khối NPU độc lập (với một mẫu Inner lấy từ tập dataset), không dùng để kiểm chứng toàn chuỗi HIL từ đầu vào sóng rung được.

4. **Ưu tiên 4 — Đo đạc thực tế và gửi log thực nghiệm:**  
   * Chạy đo đạc thực tế và xuất log kiểm chuẩn: Độ chính xác của bộ đối sánh 12 kênh (chuẩn HIL 12 kHz) trên tập Validation và hai tập Holdout nứt nặng 14-mil / 21-mil, kèm theo tỉ lệ kích hoạt cờ `ood_alert` thực tế trên các tập này.

---

## 5. Câu hỏi kỹ thuật cần Tài làm rõ

1. **Cửa sổ Hann:** Trong thư viện Python, cửa sổ Hann mặc định là đối xứng (chia cho $N - 1 = 511$). Trong file ROM phần cứng RTL, cửa sổ Hann đang dùng là loại đối xứng (`periodic=False`) hay tuần hoàn (`periodic=True`, chia cho $N = 512$)?
2. **Quy chuẩn thang đo biên độ INT16:** Ba file kích thích `stimulus_cwru_*.hex` hiện tại có đỉnh cực đại đạt tới mức $\approx 26000$ LSB. Dữ liệu huấn luyện ban đầu được scale về INT16 theo hệ số tỉ lệ nào? Vì bộ lọc FIR thực tế có độ lợi lên tới $5.6$ tại $720\text{ Hz}$, nếu tín hiệu rung vào quá lớn sẽ gây tràn dải bão hòa (ví dụ: mẫu Normal của mình đang bị xén đỉnh khoảng 49 mẫu).
3. **Bộ lọc FIR 32 hệ số đang dùng:** Đáp ứng tần số hiện tại (đỉnh tại $720\text{ Hz}$, có độ lợi ở tần số thấp) là do chủ đích thiết kế riêng để bắt các hài cơ bản, hay là thiết kế nhầm so với mục tiêu thông dải 2–5 kHz ban đầu?
4. **Tần số cắt Envelope:** Giá trị $f_c = 1000\text{ Hz}$ trong `pipeline.py` có phải là di tích còn sót lại từ profile cảm biến IIS3DWB ($13.333\text{ kHz}$) không? Chuẩn phần cứng cuối cùng áp dụng cho toàn hệ thống có phải là $1200\text{ Hz}$?
5. **Đặc trưng vật lý Prior:** Bộ suy luận 12 kênh triển khai trên FPGA có thực sự không sử dụng đến 4 giá trị Prior (được huấn luyện độc lập hoàn toàn với phổ 257 bin và gán 0 trong phần cứng) hay có cấu hình nào cần kích hoạt không?

---
> [!NOTE]
> Mọi phát hiện trên đều đã được kiểm chứng chéo qua mô phỏng bit-true phần cứng ModelSim SE-64 và đối chiếu mã nguồn thực tế tại repository. Rất mong nhận được phản hồi và bộ trọng số cập nhật từ Tài để hoàn thiện toàn diện chuỗi HIL trên board!
