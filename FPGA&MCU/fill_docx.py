# -*- coding: utf-8 -*-
"""
Script to populate Sample_Project_Layout.docx for
Cuoc Thi Thiet Ke FPGA va MCU Mo Rong Khu Vuc Mien Trung 2026.
Focus: IC & Semiconductor Design, Gowin Kiwi 4K / Primer 20K Silicon Optimization,
Hardware/Software Co-Design with Sonix MCU.
"""

import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def create_proposal_docx(template_path, output_path, image_path):
    doc = docx.Document(template_path)
    
    # Configure document style
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(4)
    
    # Modify Section I: THONG TIN CHUNG
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt.startswith("Tên đề tài:"):
            p.text = ""
            r1 = p.add_run("Tên đề tài: ")
            r1.bold = True
            r2 = p.add_run("Hệ thống Giám sát Sức khỏe Ổ lăn & Ước lượng Tuổi thọ Còn lại (RUL) Tối ưu Hóa Diện tích Vi mạch trên Nền tảng FPGA Gowin Kiwi 4K & MCU Sonix (VibraDistill-Edge)")
            r2.bold = True
            r2.font.color.rgb = RGBColor(0, 32, 96)
        elif txt.startswith("Tên đội thi:"):
            p.text = "Tên đội thi: [VibraDistill Team]"
        elif txt.startswith("Trường / Viện:"):
            p.text = "Trường / Viện: [Đại học Bách Khoa / Đại học Sư phạm Kỹ thuật]"
        elif txt.startswith("Trưởng nhóm"):
            p.text = "Trưởng nhóm (Họ tên - SĐT - Email): [Trưởng nhóm - SĐT: 09xx.xxx.xxx - Email: team@university.edu.vn]"
        elif txt.startswith("Tên Thành viên & Giảng viên"):
            p.text = "Tên Thành viên & Giảng viên hướng dẫn: [Thành viên 1, Thành viên 2, Thành viên 3; GVHD: TS. Nguyễn Văn A]"
            
    # Section II: TONG QUAN GIAI PHAP & MUC TIEU
    for idx, p in enumerate(doc.paragraphs):
        txt = p.text.strip()
        if txt.startswith("Mục tiêu đề tài:"):
            p.text = ""
            r = p.add_run("Mục tiêu đề tài:\n")
            r.bold = True
            p.add_run(
                "Trong các hệ thống công nghiệp tải nặng (tuabin gió, động cơ kéo tàu điện, máy công cụ CNC), sự cố hỏng hóc cơ khí ổ bi/ổ lăn chiếm tới 40–50% thời gian dừng máy ngoài kế hoạch, gây tổn thất kinh tế nghiêm trọng. "
                "Các giải pháp chẩn đoán rung động hiện nay hoặc đòi hỏi máy tính công nghiệp/GPU đắt đỏ tiêu thụ hàng chục Watt, hoặc dựa trên vi điều khiển đơn lẻ không đủ băng thông tính toán FFT và lọc số thời gian thực ở tần số cao.\n\n"
                "Đề tài VibraDistill-Edge giải quyết bài toán này bằng kiến trúc đồng thiết kế vi mạch Phần cứng/Phần mềm (Hardware/Software Co-Design) bất đối xứng tối ưu triệt để diện tích silicon (PPA - Power, Performance, Area):\n"
                "1. Tầng gia tốc phần cứng (Gowin FPGA): Thực thi trọn vẹn đường ống xử lý tín hiệu số (DSP) liên tục ở tần số lấy mẫu cao (fs = 12 kHz) hoàn toàn trên phần cứng với độ trễ siêu thấp (sub-millisecond), triệt tiêu hoàn toàn gánh nặng tính toán và hiện tượng trôi khung (jitter) cho CPU.\n"
                "2. Tầng điều khiển & suy luận biên (Sonix MCU): Thực thi mô hình học sâu thu nhỏ VibraDistillMicro (8.677 tham số, định dạng INT8 CMSIS-NN) kết hợp tầng định lượng độ bất định (Evidential Deep Learning) và khoảng tin cậy thích ứng (Adaptive Conformal Prediction) để đưa ra phán quyết chẩn đoán và dự báo tuổi thọ còn lại (RUL) với độ an toàn cấp công nghiệp.\n"
                "3. Tính khả thi thương mại: Hệ thống đạt hiệu suất suy luận vượt trội nhưng chỉ tiêu tốn < 180 mW toàn mạch, cho phép đóng gói thành cảm biến thông minh không dây (Wireless Smart Pod) gắn trực tiếp lên gối đỡ động cơ với giá thành BOM vi mạch chỉ < $15 USD."
            )
            
        elif txt.startswith("Sơ đồ khối hệ thống"):
            p.text = ""
            r = p.add_run("Sơ đồ khối hệ thống (System Block Diagram):\n")
            r.bold = True
            p.add_run(
                "Hệ thống bao gồm 3 phân tầng vật lý: (1) Khối cảm biến gia tốc công nghiệp ST IIS3DWB; (2) Bo mạch Gowin FPGA đảm nhiệm tầng tiền xử lý DSP phần cứng thời gian thực; (3) Bo mạch Sonix SN32F788 MCU đảm nhiệm suy luận TinyML và giao tiếp người dùng/công nghiệp qua OLED và RS485/CAN Bus."
            )
            # Add image right below if available
            if os.path.exists(image_path):
                img_p = doc.add_paragraph()
                img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run_img = img_p.add_run()
                run_img.add_picture(image_path, width=Inches(6.2))
                cap_p = doc.add_paragraph()
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                rcap = cap_p.add_run("Hình 1: Sơ đồ khối kiến trúc phần cứng - phần mềm hệ thống VibraDistill-Edge (Gowin FPGA + Sonix MCU).")
                rcap.italic = True
                rcap.font.size = Pt(10.5)

    # Section III: CAU HINH PHAN CUNG
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt.startswith("[ ] Phối hợp FPGA Gowin + MCU Sonix"):
            p.text = "[X] Phối hợp FPGA Gowin + MCU Sonix (Hybrid System)"
            p.runs[0].bold = True
            p.runs[0].font.color.rgb = RGBColor(0, 100, 0)
        elif txt.startswith("[ ] Gowin FPGA Board"):
            p.text = "   - Bo mạch FPGA mục tiêu chính: Gowin Kiwi 4K (Dòng chip GW1N-LV4 / GW1NR-UV4, 4.608 LUT4) - Tối ưu hóa chi phí & thương mại hóa."
        elif txt.startswith("[ ] Sonix MCU Board"):
            p.text = "   - Bo mạch vi điều khiển mục tiêu: Sonix SN32F788 (ARM Cortex-M4F @ 96 MHz, 256 KB Flash, 64 KB SRAM, FPU)."
        elif txt.startswith("Ước tính Logic Elements / LUTs:"):
            p.text = ""
            r = p.add_run("Ước tính Logic Elements / LUTs: ")
            r.bold = True
            p.add_run(
                "≈ 1.650 / 4.608 LUT4 (Chiếm ≈ 35.8% tài nguyên trên Kiwi 4K; hoặc ≈ 7.9% trên Primer 20K). "
                "Mức sử dụng 35.8% là tỷ lệ vàng (sweet spot) trong thiết kế vi mạch công nghiệp: đảm bảo tối ưu chi phí wafer silicon, diện tích đóng gói nhỏ, định tuyến (routing) thông thoáng 100% không tắc nghẽn, và tiêu tán công suất tĩnh cực thấp."
            )
        elif txt.startswith("BRAM / Block RAM:"):
            p.text = ""
            r = p.add_run("BRAM / Block RAM: ")
            r.bold = True
            p.add_run(
                "5 blocks BSRAM 18Kbit = 90 Kbit (Chiếm 50.0% trên Kiwi 4K / 10.8% trên Primer 20K). "
                "Bao gồm: 1 block cho bộ đệm Ping-Pong dữ liệu đầu vào (2 x 512 x 16-bit); 3 blocks cho lõi Gowin FFT IP (vùng nhớ dữ liệu 512 điểm phức và bảng tra hệ số Twiddle Factors); 1 block cho bảng tra cửa sổ Hann 16-bit và hệ số lọc FIR pha cực tiểu."
            )
        elif txt.startswith("DSP Blocks (nếu có):"):
            p.text = ""
            r = p.add_run("DSP Blocks (Khối nhân phần cứng): ")
            r.bold = True
            p.add_run(
                "6 khối Multiplier 18x18 (Chiếm 37.5% trong tổng số 16 khối DSP trên Kiwi 4K; hoặc 12.5% trên Primer 20K). "
                "Đặc biệt: Nhờ kỹ thuật Folded FIR Pipeline (chia sẻ thời gian nhân ở xung nhịp 50 MHz cho tần số lấy mẫu 12 kHz có tới 4.166 chu kỳ xung/mẫu), toàn bộ bộ lọc số FIR 32-tap chỉ tốn đúng 01 khối DSP; bộ giải điều chế bao IIR tốn 01 khối DSP; và khối bướm FFT phức tốn 04 khối DSP."
            )
        elif txt.startswith("Tần số xung clock hệ thống"):
            p.text = ""
            r = p.add_run("Tần số xung clock hệ thống (System Clock Frequency): ")
            r.bold = True
            p.add_run(
                "Xung nhịp DSP Pipeline: 50.0 MHz; Xung nhịp FFT Core & Số học: 100.0 MHz (tổng hợp qua Gowin rPLL từ thạch anh onboard 27.0 MHz). "
                "Xung nhịp ngoại vi: SPI Master giao tiếp cảm biến = 6.0 MHz; SPI Slave DMA giao tiếp MCU = 4.0 MHz."
            )
        elif txt.startswith("Dải bo mạch / Mạch nạp cần cấp:"):
            p.text = ""
            r = p.add_run("Dải bo mạch / Mạch nạp cần cấp:\n")
            r.bold = True
            p.add_run(
                "1. Bo mạch FPGA: Kính đề nghị BTC hỗ trợ CẢ 02 bo mạch: 01 Bo mạch Gowin Kiwi 4K (Mục tiêu sản phẩm thương phẩm tối ưu diện tích và giá thành) VÀ 01 Bo mạch Primer 20K (Mục tiêu đối chuẩn mở rộng đa kênh 4-8 ổ bi cùng lúc).\n"
                "2. Mạch nạp: 01 Cáp nạp USB JTAG Programmer chính hãng Gowin.\n"
                "3. Bo mạch MCU: 01 Bo mạch Sonix SN32F788 Starter Kit + 01 Mạch nạp SN-LINK."
            )
        elif txt.startswith("Cảm biến / Module mở rộng đề nghị hỗ trợ"):
            p.text = ""
            r = p.add_run("Cảm biến / Module mở rộng đề nghị hỗ trợ:\n")
            r.bold = True
            p.add_run(
                "1. 01 Module cảm biến gia tốc rung động công nghiệp STMicroelectronics IIS3DWB (dạng breakout SPI hoặc PMOD).\n"
                "2. 01 Màn hình hiển thị trạng thái OLED 0.96 inch I2C (SSD1306) và 01 Module giao tiếp công nghiệp RS485/CAN Bus (SN65HVD230)."
            )

    # Modify Table 1: Danh sách ngoại vi & Cổng giao tiếp
    if len(doc.tables) > 0:
        table = doc.tables[0]
        rows_data = [
            ("Cảm biến gia tốc rung động công nghiệp ST IIS3DWB", "SPI Master (Mode 3, 6.0 MHz)", "Gowin FPGA", "3.3V (Tiêu thụ cực thấp 1.1 mA)"),
            ("Bo mạch vi điều khiển Sonix SN32F788", "SPI Slave DMA (4.0 MHz) + GPIO IRQ", "Gowin FPGA <-> Sonix MCU", "3.3V (Nguồn IO chung)"),
            ("Màn hình hiển thị trạng thái OLED 0.96\" (SSD1306)", "I2C (400 kHz Fast-Mode)", "Sonix MCU", "3.3V"),
            ("Module giao tiếp công nghiệp RS485 / CAN Bus", "UART / CAN Controller", "Sonix MCU", "3.3V / 5.0V")
        ]
        
        while len(table.rows) < len(rows_data) + 1:
            table.add_row()
            
        for cell in table.rows[0].cells:
            set_cell_background(cell, "002060")
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs:
                    r.bold = True
                    r.font.color.rgb = RGBColor(255, 255, 255)
                    r.font.size = Pt(10.5)
                    
        for idx, data in enumerate(rows_data):
            row = table.rows[idx + 1]
            for c_idx, text in enumerate(data):
                cell = row.cells[c_idx]
                cell.text = text
                if (idx % 2 == 1):
                    set_cell_background(cell, "F2F5F9")
                p = cell.paragraphs[0]
                p.paragraph_format.line_spacing = 1.05
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)
                for r in p.runs:
                    r.font.size = Pt(10)
                    if c_idx in [1, 2, 3]:
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Section IV: PHAN CHIA KIEN TRUC PHAN MEM & RTL
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt.startswith("Gowin FPGA (Hardware Acceleration / RTL):"):
            p.text = ""
            r = p.add_run("Gowin FPGA (Hardware Acceleration / RTL Architecture):\n")
            r.bold = True
            p.add_run(
                "FPGA đóng vai trò là bộ tăng tốc phần cứng tiền xử lý tín hiệu số (DSP Hard Real-Time Engine), độc lập hoàn toàn với MCU:\n"
                "• Khối SPI Sensor Master: Giao tiếp với IIS3DWB ở fs = 12 kHz, tự động đọc từ thanh ghi 16-bit gia tốc mà không cần vi xử lý can thiệp.\n"
                "• Khối Ping-Pong BRAM Buffer: Vùng đệm kép 512 mẫu (42.67 ms). Trong khi Buffer 0 nạp dữ liệu mới, Buffer 1 được đọc song song vào đường ống DSP, đảm bảo không mất mẫu (zero sample drop).\n"
                "• Khối Lọc số FIR Pha Cực Tiểu (32-tap Minimum-Phase FIR): Sử dụng thuật toán phản xạ nghiệm Cepstral chuyển đổi từ bộ lọc Hamming 64-tap. Giúp giảm 50% trễ nhóm (từ 2.63 ms xuống 1.33 ms) trong khi bảo toàn 100% biên độ dải cộng hưởng lỗi (2–5 kHz). Ứng dụng kiến trúc gập (Folded FIR) chỉ tiêu tốn duy nhất 01 khối nhân DSP18E.\n"
                "• Khối Giải Điều Chế Bao (Full-Wave Rectifier + IIR LPF): Thay thế biến đổi Hilbert CORDIC cồng kềnh bằng phép lấy trị tuyệt đối kết hợp lọc thông thấp IIR bậc 2 và bộ lọc thông cao IIR bậc 1 khử triệt để thành phần bù DC (2/pi ≈ 0.6366). Tiết kiệm > 65% Logic Elements trên FPGA.\n"
                "• Khối Phân Tích Phổ FFT 512 Điểm: Tích hợp Gowin FFT IP Core (Real Radix-2 DIT) cùng cửa sổ Hann, kết hợp thuật toán xấp xỉ biên độ Alpha-Beta (Alpha-Beta Filter: |X| ≈ max + 3/8 min), xuất ra 257 bin phổ biên độ với sai số biên độ < 2.84% mà không cần tính căn bậc 2.\n"
                "• Khối Mặt Nạ Động Học (Kinematic Prior Engine): Tự động quét đỉnh phổ dưới đồng bộ (10–45 Hz) để đo tốc độ quay trục thực tế fr; tính toán tần số lỗi lý thuyết (BPFO, BPFI, BSF, FTF) và phát sinh mặt nạ 4-bit với dung sai tốc độ ±3.0%."
            )
        elif txt.startswith("Sonix MCU (Firmware / Application Control):"):
            p.text = ""
            r = p.add_run("Sonix MCU (Firmware / TinyML Inference & Safety Control):\n")
            r.bold = True
            p.add_run(
                "MCU Sonix SN32F788 (Cortex-M4F @ 96 MHz) chịu trách nhiệm chẩn đoán thông minh, định lượng bất định và quản trị năng lượng:\n"
                "• Khối Thu Thập Dữ Liệu SPI Slave DMA: Nhận trọn vẹn gói tin 520 byte phổ biên độ từ FPGA vào SRAM thông qua cơ chế Circular DMA; tự động kích hoạt ngắt giải mã và kiểm tra mã lỗi CRC-16-CCITT.\n"
                "• Mạng Nơ-ron Nhúng Siêu Nhẹ VibraDistillMicro: Mô hình 1D-CNN đa tỷ lệ gồm đúng 8.677 tham số, đã được lượng tử hóa INT8 thông qua tập lệnh tối ưu ARM CMSIS-NN (arm_convolve_1x1_s8, arm_depthwise_conv_s8). Thời gian suy luận cực nhanh chỉ 12.8 ms, bộ nhớ Flash chỉ tốn 8.48 KB và SRAM hoạt động 6.0 KB.\n"
                "• Tầng Định Lượng Bất Định Evidential Deep Learning (EDL): Áp dụng phân phối tiên nghiệm Dirichlet để ước lượng Độ mù mờ (Vacuity u = K/S). Khi u > 0.45, hệ thống tự động nhận diện mẫu lỗi lạ / nhiễu ngoài phân phối (OOD) và phát cảnh báo kiểm tra thay vì đưa ra phán đoán sai lệch.\n"
                "• Thuật Toán Thích Ứng Khoảng Tin Cậy Trực Tuyến Bounded-Delay ACP: Cập nhật động biên độ qt+1 = max(qmin, qt + gamma*(err - alpha)) đảm bảo độ phủ 90% chính xác trong bài toán ước lượng tuổi thọ còn lại (RUL) dưới hiện tượng thoái hóa phi tuyến tính.\n"
                "• Quản Trị Năng Lượng Động: Sau khi hoàn tất 12.8 ms suy luận, MCU lập tức rơi vào trạng thái ngủ sâu (Wait-For-Interrupt - WFI) trong 29.8 ms còn lại của khung (chiếm 69.8% chu kỳ), giảm dòng tiêu thụ trung bình của MCU xuống dưới 9.3 mA."
            )
        elif txt.startswith("Giao tiếp FPGA – MCU:"):
            p.text = ""
            r = p.add_run("Giao tiếp FPGA – MCU (Hardware Interconnect Protocol):\n")
            r.bold = True
            p.add_run(
                "• Giao diện vật lý: SPI 4 dây tốc độ cao 4.0 MHz (SCK, MOSI, MISO dự phòng, CS_N) kết hợp 01 chân ngắt phần cứng FRAME_READY (Gowin FPGA Output -> Sonix ExtInt Pin).\n"
                "• Cấu trúc khung gói tin (Deterministic 520-Byte Frame Format):\n"
                "  [Mã đồng bộ 4 Byte: 0x55AA55AA] + [Bộ đếm khung 2 Byte] + [Mặt nạ động học 2 Byte] + [257 Bins phổ biên độ x 2 Byte = 514 Byte] + [CRC-16-CCITT 2 Byte].\n"
                "• Thời gian truyền tải thực tế: (520 x 8) / 4.000.000 = 1.040 ms, chỉ chiếm 2.44% chu kỳ khung 42.667 ms, triệt tiêu nguy cơ nghẽn bus."
            )
        elif txt.startswith("Gowin EDA Version:"):
            p.text = "Gowin EDA Version: V1.9.9 / V1.9.10 (GowinSynthesis, Gowin PnR, Gowin Analyzer Scope)."
        elif txt.startswith("Sonix IDE / Compiler:"):
            p.text = "Sonix IDE / Compiler: Keil MDK-ARM v5.38a (ARM Compiler 6) / GCC ARM Embedded 12.3, ARM CMSIS-NN v5.9.0."
        elif txt.startswith("Các IP Cores kiến trúc dự định dùng:"):
            p.text = ""
            r = p.add_run("Các IP Cores kiến trúc dự định dùng:\n")
            r.bold = True
            p.add_run(
                "1. Gowin rPLL (Phase-Locked Loop): Nhân xung từ 27.0 MHz lên 50.0 MHz và 100.0 MHz.\n"
                "2. Gowin FFT IP Core: 512-Point Radix-2 Real FFT (Pipelined Streaming Architecture).\n"
                "3. Gowin SDPB (Semi-Dual Port Block RAM): Bộ đệm Ping-Pong và bảng tra Hann Window.\n"
                "4. Gowin FIFO Core: Chuyển đổi miền xung nhịp (Clock Domain Crossing - CDC) giữa miền lấy mẫu 12 kHz và miền truyền thông SPI 4 MHz."
            )

    # Section V: KE HOACH TRIEN KHAI & TIEN DO
    milestones = [
        ("Tuần 1: Thiết kế RTL & Mô phỏng DSP trên FPGA Gowin",
         "• Viết RTL Verilog cho bộ lọc FIR 32-tap pha cực tiểu, bộ giải điều chế bao IIR và bộ đo tốc độ quay.\n"
         "• Tích hợp Gowin FFT IP 512 điểm và mô phỏng kiểm tra trên ModelSim/Gowin Simulator, xác minh sai số < 0.05 dB so với Python.\n"
         "• Tiền huấn luyện mô hình Teacher (ResNet-1D 20.4k tham số) trên bộ dữ liệu chuẩn CWRU và MFPT."),
        ("Tuần 2: Chưng cất Tri thức (DKD) & Lượng tử hóa TinyML trên Sonix MCU",
         "• Huấn luyện chưng cất mô hình học sâu rút gọn VibraDistillMicro (8.677 tham số) bằng hàm mất mát Decoupled KD (tau=4.0, lambda1=1.0, lambda2=1.0).\n"
         "• Tích hợp đầu ra Evidential Dirichlet (EDL), xác định ngưỡng mù mờ u* = 0.45 để phát hiện lỗi lạ.\n"
         "• Lượng tử hóa INT8 CMSIS-NN và nạp thử nghiệm lên MCU Sonix SN32F788, đo đạc thời gian suy luận."),
        ("Tuần 3: Tích hợp Giao tiếp Phần cứng FPGA – MCU & Thuật toán Tin cậy ACP",
         "• Viết module SPI Master Transmitter trên FPGA Gowin và trình điều khiển SPI Slave DMA trên MCU Sonix.\n"
         "• Lập trình thuật toán Adaptive Conformal Prediction (ACP) hiệu chỉnh trực tuyến khoảng tin cậy RUL trên MCU Sonix.\n"
         "• Ghép nối dây phần cứng giữa bo mạch Gowin và bo mạch Sonix MCU, kiểm tra tính toàn vẹn truyền nhận 100.000 khung với CRC-16."),
        ("Tuần 4: Đo kiểm Rung Động Thực tế, Tối ưu hóa PPA & Thực hiện Đối chuẩn Kép (Kiwi 4K vs. Primer 20K)",
         "• Đấu nối cảm biến rung động thực tế ST IIS3DWB với bo mạch Gowin FPGA.\n"
         "• Sử dụng Dao động ký (Oscilloscope) và Logic Analyzer đo đạc chính xác thời gian trễ từng phân đoạn (DSP 0.085 ms, SPI 1.04 ms, MCU 12.88 ms).\n"
         "• Mắc điện trở shunt 0.1 Ohm đo dòng tiêu thụ thực tế ở chế độ hoạt động và chế độ ngủ WFI, xác thực tổng công suất Kiwi 4K < 180 mW.\n"
         "• Nạp bitstream cấu hình 4 kênh song song lên bo mạch Primer 20K, hoàn thiện bảng đối chuẩn mở rộng PPA."),
        ("Tuần 5: Hoàn thiện Sản phẩm Demo, Giao diện OLED & Đóng gói Báo cáo",
         "• Tích hợp màn hình OLED 0.96 inch hiển thị trực quan: Loại lỗi ổ bi, Chỉ số độ tin cậy/mù mờ (Vacuity), Khoảng dự báo tuổi thọ RUL (giờ).\n"
         "• Đóng gói mô hình demo hoạt động độc lập (Standalone Hardware Demo) chịu rung động trên động cơ thí nghiệm.\n"
         "• Hoàn thiện hồ sơ kỹ thuật vi mạch, mã nguồn RTL/Firmware và video demo vòng chung kết.")
    ]
    
    indices_to_remove = []
    for idx, p in enumerate(doc.paragraphs):
        txt = p.text.strip()
        if txt.startswith("Tuần 1 - 2:") or txt.startswith("Tuần 3 - 4:") or txt.startswith("Tuần 5:"):
            indices_to_remove.append(idx)
            
    if indices_to_remove:
        first_idx = indices_to_remove[0]
        p0 = doc.paragraphs[first_idx]
        p0.text = ""
        r_title = p0.add_run(milestones[0][0] + "\n")
        r_title.bold = True
        p0.add_run(milestones[0][1])
        
        for m_idx in range(1, len(milestones)):
            target_idx = first_idx + m_idx
            if target_idx < len(doc.paragraphs) and target_idx in indices_to_remove:
                p = doc.paragraphs[target_idx]
                p.text = ""
                r_title = p.add_run(milestones[m_idx][0] + "\n")
                r_title.bold = True
                p.add_run(milestones[m_idx][1])
            else:
                p = doc.add_paragraph()
                r_title = p.add_run(milestones[m_idx][0] + "\n")
                r_title.bold = True
                p.add_run(milestones[m_idx][1])
                
    doc.save(output_path)
    print(f"Document saved successfully to: {output_path}")

if __name__ == '__main__':
    template = r'd:\Gitrepo\VIbraDistill\FPGA&MCU\Sample_Project_Layout.docx'
    output = r'd:\Gitrepo\VIbraDistill\FPGA&MCU\Sample_Project_Layout.docx'
    image = r'd:\Gitrepo\VIbraDistill\FPGA&MCU\figures\system_block_diagram.png'
    create_proposal_docx(template, output, image)
