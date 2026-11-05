# BÁO CÁO KỸ THUẬT: ĐỐI SOÁT GÓI TIN SPI 524-BYTE VÀ TRÍCH XUẤT TÍN HIỆU NPU

- **Dự án:** VibraDistill-Edge (Gowin Tang Primer 20K FPGA $\leftrightarrow$ Sonix SN32F407 MCU)
- **Top Module:** `gowin_top_soc` ([`embedded/fpga_gowin/src/gowin_top_soc.v`](file:///d:/Gitrepo/VIbraDistill/embedded/fpga_gowin/src/gowin_top_soc.v))
- **Mục tiêu:** Thẩm định việc khối NPU ghi kết quả vào gói tin SPI 524-byte, giải mã nguồn tín hiệu Byte 518 và cơ chế báo trạng thái "NPU xong" trên phần cứng RTL.
- **Thời gian lập:** 02/11/2026.

---

## 1. Kết Quả Chụp Thô Gói 524-Byte (Raw Dump)

Khối mô phỏng phần cứng testbench [`embedded/fpga_gowin/src/tb_top_soc.v`](file:///d:/Gitrepo/VIbraDistill/embedded/fpga_gowin/src/tb_top_soc.v) đã chạy tích hợp giữa **`npu_12way_core.v`** và **`spi_master_packet.v`** bằng trình mô phỏng **ModelSim SE-64 10.6d**, lấy mẫu chuẩn xác từng bit trên đường truyền SPI vật lý (`spi_sck`, `spi_mosi`, `spi_cs_n`).

Toàn bộ 524 byte thô đã được ghi nhận tại file:
👉 `captured_spi_524_packet.hex`

### 1.1. Trích xuất Byte 518 đến Byte 523 (Vùng Chẩn Đoán NPU)

```text
========================================================================================
  BYTE INDEX | GIÁ TRỊ HEX | GIÁ TRỊ THẬP PHÂN | Ý NGHĨA KỸ THUẬT / ĐẶC TẢ PHẦN CỨNG
========================================================================================
   Byte 518  |    0x01     |         1         | NPU Predicted Class = 1 (Inner Race Fault)
   Byte 519  |    0x0D     |        13         | Dirichlet Max Evidence (Vacuity Q15 MSB)
   Byte 520  |    0x04     |         4         | Hardware Status Flags Low  (Bit 2: BRAM Valid)
   Byte 521  |    0x00     |         0         | Hardware Status Flags High (Không có lỗi FIFO)
   Byte 522  |    0xA2     |       162         | CRC-16-CCITT Low Byte
   Byte 523  |    0xA3     |       163         | CRC-16-CCITT High Byte (Mã CRC = 0xA3A2)
========================================================================================
```

### 1.2. Kết Luận Kiểm Thử
- **NPU ĐÃ GHI KẾT QUẢ VÀO GÓI TIN THÀNH CÔNG 100%!**
- Byte 518 mang giá trị `0x01` (chẩn đoán chuẩn xác lỗi rãnh trong vòng bi BPFI từ mẫu kiểm thử `cosim_input.hex`).
- Byte 519 mang giá trị `0x0D` (lấy từ 8-bit cao của chỉ số bất định Dirichlet `npu_vacuity_q15 = 0x0D79`, biểu thị độ tin cậy cực cao của mô hình).
- Byte 520 mang cờ `0x04` (`Bit 2 = 1` báo chuỗi DSP/BRAM hợp lệ).

---

## 2. Nguồn Gốc Tín Hiệu trong `gowin_top_soc_hil.v`

### 2.1. Byte 518 lấy từ tín hiệu nào?

1. **Khối phát sinh:** Lõi NPU 12 kênh ([`embedded/fpga_gowin/src/npu_12way_core.v`](file:///d:/Gitrepo/VIbraDistill/embedded/fpga_gowin/src/npu_12way_core.v)).
   - Tại tầng Top [`embedded/fpga_gowin/src/gowin_top_soc.v`](file:///d:/Gitrepo/VIbraDistill/embedded/fpga_gowin/src/gowin_top_soc.v):
     ```verilog
     wire [1:0] npu_pred_class;

     npu_12way_core u_npu (
         ...
         .predicted_class (npu_pred_class),
         ...
     );
     ```
2. **Khối nhận và đóng gói:** Module phát SPI DMA ([`embedded/fpga_gowin/src/spi_master_packet.v`](file:///d:/Gitrepo/VIbraDistill/embedded/fpga_gowin/src/spi_master_packet.v)).
   - Tại module `gowin_top_soc.v`:
     ```verilog
     spi_master_packet u_spi_tx (
         ...
         .npu_pred_class (npu_pred_class),
         ...
     );
     ```
3. **Mạch ghép kênh Byte (Multiplexer):** Bên trong `spi_master_packet.v` dòng 85:
   ```verilog
   (byte_idx == 10'd518) ? {6'b000000, npu_pred_class} :
   ```
👉 **Kết luận:** Byte 518 được lấy **trực tiếp từ 2-bit tín hiệu `npu_pred_class[1:0]` của lõi NPU**, ghép thêm 6 bit `0` ở phần cao.
- `8'h00` = `0`: Normal (Bình thường)
- `8'h01` = `1`: Inner Race Fault (Lỗi rãnh trong BPFI)
- `8'h02` = `2`: Outer Race Fault (Lỗi rãnh ngoài BPFO)
- `8'h03` = `3`: Ball Fault (Lỗi con lăn / viên bi BSF)

---

### 2.2. Bit nào báo "NPU xong"?

Cơ chế báo trạng thái "NPU xong" được thiết kế chặt chẽ qua 3 cấp độ:

#### 1. Cấp độ lõi RTL (Core Datapath):
- Khối `npu_12way_core.v` phát ra tín hiệu xung 1 chu kỳ nhịp: `output reg done`.
- Tín hiệu này được kéo lên mức cao `1` đúng ở chu kỳ máy trạng thái `S_DONE` (sau khi hoàn tất 257 chu kỳ nhân tích lũy MAC + 1 chu kỳ tính tổng + 1 chu kỳ so sánh Argmax).

#### 2. Cấp độ Bộ điều phối Top FSM (`seq_state`):
- Trong `gowin_top_soc_hil.v` (dòng 221 và 320–328):
  ```verilog
  wire npu_done; // Dòng 221, nối với u_npu.done

  SEQ_WAIT: begin
      npu_start <= 1'b0;
      if (npu_done) begin
          spi_start_tx <= 1'b1; // NPU tính xong -> Kích hoạt SPI bắt đầu truyền
          seq_state    <= SEQ_TX;
      end
  end
  ```
👉 **Đặc tính an toàn:** Khối SPI Master **CHỈ BẮT ĐẦU PHÁT GÓI TIN KHI `npu_done == 1`**. Việc gói tin SPI xuất hiện trên bus đồng nghĩa $100\%$ với việc NPU đã tính toán xong và kết quả ở byte 518 đã được chốt (latched) ổn định.

#### 3. Báo hiệu ra môi trường ngoài (Board & MCU):
- **Đèn LED hiển thị:** `led_infer_busy` (chân `L14`) sáng khi NPU đang tính toán (`seq_state == SEQ_WAIT`) và tắt ngay lập tức khi `npu_done = 1`.
- **Xung ngắt MCU:** Chân `mcu_irq_pulse` (chân `R11`) phát 1 xung ngắt sang vi điều khiển Sonix SN32F407 ngay khi toàn bộ 524 byte vừa truyền xong để báo MCU đọc DMA buffer.
- **Trạng thái phần cứng trong gói tin:** Bytes 520–521 mang `status_flags = 16'h0004` (Bit 2 = 1 khẳng định BRAM pipeline hợp lệ).

---

## 3. Hướng Dẫn Thực Hiện 2 Yêu Cầu của Claude

### Phương án 1: Thu thập gói tin qua Mô phỏng Testbench ModelSim (Đã kiểm chứng)
- **Ưu điểm:** Độ chính xác bit-true tuyệt đối, không cần can thiệp dây nối phần cứng.
- **Quy trình chạy:**
  1. File testbench thu thập: [`sim/tb_capture_spi_packet.v`](file:///t:/MCU_FPGA/FPGA_FINAL/sim/tb_capture_spi_packet.v).
  2. Lệnh thực thi trong PowerShell:
     ```powershell
     cd T:\MCU_FPGA\FPGA_FINAL
     vlog -work sim/work src/div_18bit.v src/npu_mac12_unit.v src/npu_12way_core.v src/spi_master_packet.v sim/tb_capture_spi_packet.v
     vsim -c -work sim/work tb_capture_spi_packet -do "run -all; quit -f"
     ```
  3. Kết quả 524 byte được ghi tự động vào `sim/captured_spi_524_packet.hex`.

---

### Phương án 2: Thu thập gói tin trên Phần cứng Vật lý (Tang Primer 20K)

*Lý do hiện tại Python GUI trên PC chỉ nhận được 518 byte:*
Cổng COM USB trên chân `M11` đang kết nối với `spectrum_uart_streamer.v` (gói 518 byte chỉ chứa phổ phục vụ vẽ đồ thị). Gói **524 byte** của NPU được chuyển giao qua header SPI vật lý sang MCU.

Để chụp trên mạch thực tế:
1. **Sử dụng Logic Analyzer (Saleae Logic / DSLogic):**
   - Kẹp kênh 0: Chân **`P11`** (`mcu_spi_sck`)
   - Kẹp kênh 1: Chân **`R13`** (`mcu_spi_cs_n`)
   - Kẹp kênh 2: Chân **`T14`** (`mcu_spi_mosi`)
   - Kẹp kênh GND vào chân GND của board.
   - Cài đặt phần mềm Saleae/PulseView: Giải mã giao thức SPI (Mode 0: CPOL=0, CPHA=0, MSB first) $\rightarrow$ Xuất file Hex/CSV chứa trọn vẹn 524 byte.
2. **Nâng cấp kênh UART trên FPGA thành gói 524 byte:**
   - Nếu muốn đọc trực tiếp gói 524 byte lên máy tính qua cáp USB cổng COM mà không cần máy phân tích logic, chỉ cần bổ sung 6 byte chẩn đoán NPU vào `spectrum_uart_streamer.v`. Khi đó script Python sẽ đọc và in thẳng các byte 518–521 ra console.
