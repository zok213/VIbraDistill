"""
Generate publication-quality system architecture block diagram for VibraDistill-Edge.
Accurately reflects:
  Sensor (ST IIS3DWB @ 12 kHz)
  -> Gowin Kiwi 4K FPGA (GW1N-4 Streaming DSP: Ping-Pong, Folded FIR, IIR Demod, Alpha-Beta FFT, Kinematic Engine)
  -> SPI DMA Interconnect (4 MHz, 520 Bytes, 1.04 ms, FRAME_READY IRQ)
  -> Sonix SN32F788 MCU (ARM Cortex-M4F @ 96 MHz: CMSIS-NN 8,677 INT8, Dirichlet EDL, Bounded-Delay ACP, WFI Sleep)
  -> 0.96" OLED Display (SSD1306) & Industrial LoRaWAN / RS485 Telemetry.
Produces:
- figures/system_block_diagram.pdf (Vector Graphic)
- figures/system_block_diagram.png (300 DPI High-Res)
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def create_system_diagram():
    out_dir = r"d:\Gitrepo\VIbraDistill\FPGA&MCU\figures"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, "system_block_diagram.pdf")
    png_path = os.path.join(out_dir, "system_block_diagram.png")

    fig, ax = plt.subplots(figsize=(13.5, 7.8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Color Palette - Professional Engineering Theme
    c_sensor_bg = '#FFF3E0'
    c_sensor_border = '#E65100'
    c_sensor_text = '#BF360C'

    c_fpga_bg = '#E8F1F9'
    c_fpga_border = '#0D47A1'
    c_fpga_box = '#D0E3F5'
    c_fpga_text = '#0A2540'
    
    c_mcu_bg = '#F2F9F3'
    c_mcu_border = '#1B5E20'
    c_mcu_box = '#DCEDC8'
    c_mcu_text = '#1E4620'

    c_bus_bg = '#FFFDE7'
    c_bus_border = '#F57F17'

    c_out_bg = '#F3E5F5'
    c_out_border = '#4A148C'
    c_out_box = '#E1BEE7'

    # --- 0. SENSOR NODE (Left) ---
    sensor_rect = patches.FancyBboxPatch((1.5, 54), 11.5, 41, boxstyle="round,pad=0.8",
                                         linewidth=1.8, edgecolor=c_sensor_border, facecolor=c_sensor_bg)
    ax.add_patch(sensor_rect)
    ax.text(7.25, 90.5, "VIBRATION\nSENSOR", fontsize=9.5, fontweight='bold', ha='center', va='center', color=c_sensor_border)
    ax.text(7.25, 77, "ST IIS3DWB\nIndustrial\nAccelerometer\n\n• ODR: 26.67 kHz\n• Decimate /2\n  -> 13.33 / 12 kHz\n• 3-Axis 16-bit\n• 75 ug/√Hz Noise\n• SPI @ 6.0 MHz",
            fontsize=7.4, ha='center', va='center', fontweight='medium', color=c_sensor_text)

    # --- 1. GOWIN FPGA PIPELINE CONTAINER (Top Center) ---
    fpga_rect = patches.FancyBboxPatch((15.5, 52), 65, 43, boxstyle="round,pad=1.2",
                                       linewidth=2.2, edgecolor=c_fpga_border, facecolor=c_fpga_bg)
    ax.add_patch(fpga_rect)
    ax.text(17.5, 91.5, "GOWIN KIWI 4K FPGA (PRIMARY TARGET: GW1NSR-LV4C) / PRIMER 20K (SCALABILITY)", 
            fontsize=10.5, fontweight='bold', color=c_fpga_border)
    ax.text(79, 91.5, "[RTL Verilog Streaming DSP Engine | 50.0 MHz Core Clock]", 
            fontsize=7.8, fontweight='semibold', ha='right', color='#1565C0')

    # FPGA Inner Blocks
    fpga_blocks = [
        (17.5, 68, 11, 20, "Sensor Interface\n& Decimator\n\nPolyphase FIR /2\n26.67 -> 13.33 kHz\nSPI Master 6 MHz"),
        (30.0, 68, 11, 20, "Ping-Pong\nBRAM Buffer\n\n2 x 512 x 16-bit\nZero Sample Drop\nDouble Buffering"),
        (42.5, 78.5, 12, 9.5, "Folded FIR Filter\n32-tap Min-Phase\n1 Multiplier @ 50MHz\nGroup Delay: 1.33 ms"),
        (42.5, 68, 12, 9.5, "IIR Demodulator\nFull-Wave Rectifier\nDC Notch Filter\n0 CORDIC (Shift-Add)"),
        (56.0, 78.5, 11, 9.5, "512-pt Radix-2 FFT\nGowin FFT IP Core\nAlpha-Beta Mag Engine\n257 Spectral Bins"),
        (56.0, 68, 11, 9.5, "Kinematic Prior\nfr Peak Detector\n(10 - 45 Hz Scan)\n4-bit Mask Vector"),
        (68.5, 68, 10.5, 20, "Deterministic\nFrame Assembler\n\nCDC Async FIFO\n520B Frame + CRC16\nAssert FRAME_READY"),
    ]

    for (bx, by, bw, bh, btext) in fpga_blocks:
        rect = patches.FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0.5",
                                     linewidth=1.2, edgecolor=c_fpga_border, facecolor=c_fpga_box)
        ax.add_patch(rect)
        ax.text(bx + bw/2, by + bh/2, btext, fontsize=6.8, ha='center', va='center',
                fontweight='semibold', color=c_fpga_text)

    # Connecting arrows inside FPGA
    arrow_f = dict(arrowstyle="->", lw=1.4, color=c_fpga_border)
    ax.annotate("", xy=(30.0, 78), xytext=(28.5, 78), arrowprops=arrow_f)
    ax.annotate("", xy=(42.5, 83), xytext=(41.0, 78), arrowprops=arrow_f)
    ax.annotate("", xy=(42.5, 72.5), xytext=(41.0, 78), arrowprops=arrow_f)
    ax.annotate("", xy=(56.0, 83), xytext=(54.5, 83), arrowprops=arrow_f)
    ax.annotate("", xy=(56.0, 72.5), xytext=(54.5, 72.5), arrowprops=arrow_f)
    ax.annotate("", xy=(68.5, 78), xytext=(67.0, 83), arrowprops=arrow_f)
    ax.annotate("", xy=(68.5, 78), xytext=(67.0, 72.5), arrowprops=arrow_f)

    # Sensor to FPGA arrow
    ax.annotate("", xy=(15.5, 78), xytext=(13.0, 78), 
                arrowprops=dict(arrowstyle="->", lw=1.8, color=c_sensor_border))

    ax.text(25, 53.5, "Kiwi 4K Budget: 1,650/4,608 LUT4 (35.8%)  |  5/10 BSRAM (50%)  |  6/16 DSP (37.5%)  |  Power: ~38 mW",
            fontsize=7.2, fontweight='bold', color='#0D47A1')

    # --- 2. HIGH-SPEED SPI INTERCONNECT BUS ---
    bus_rect = patches.FancyBboxPatch((38, 44), 36, 5.5, boxstyle="round,pad=0.4",
                                     linewidth=1.4, edgecolor=c_bus_border, facecolor=c_bus_bg)
    ax.add_patch(bus_rect)
    ax.text(56, 46.75, "INTER-CHIP SPI SLAVE DMA BUS (4.0 MHz) + FRAME_READY IRQ\nDeterministic 520-Byte Frame: Sync (4B) | Cnt (2B) | Mask (2B) | 257 Bins (514B) | CRC16 (2B) [1.04 ms]", 
            fontsize=7.2, ha='center', va='center', fontweight='bold', color='#E65100')

    # Interconnect arrows between FPGA and MCU
    ax.annotate("", xy=(56, 44), xytext=(56, 52), 
                arrowprops=dict(arrowstyle="<->", lw=1.8, color=c_bus_border))
    ax.annotate("", xy=(56, 41), xytext=(56, 44), 
                arrowprops=dict(arrowstyle="->", lw=1.8, color=c_bus_border))

    # --- 3. SONIX MCU EMBEDDED AI BRAIN CONTAINER (Bottom) ---
    mcu_rect = patches.FancyBboxPatch((15.5, 2), 65, 39, boxstyle="round,pad=1.2",
                                      linewidth=2.2, edgecolor=c_mcu_border, facecolor=c_mcu_bg)
    ax.add_patch(mcu_rect)
    ax.text(17.5, 38.2, "SONIX SN32F788 MCU (ARM CORTEX-M4F @ 96 MHz, FPU, 256KB Flash, 32KB SRAM)", 
            fontsize=10.0, fontweight='bold', color=c_mcu_border)
    ax.text(79, 38.2, "[TinyML Inference: 12.88 ms | WFI Sleep Ratio: 67.4% | I_avg < 9.3 mA]", 
            fontsize=7.6, fontweight='semibold', ha='right', color='#2E7D32')

    # MCU Inner Pipeline Blocks
    mcu_blocks = [
        (17.5, 14, 11, 20, "Circular DMA\nRing Buffer\n\nDirect to SRAM\nHardware CRC-16\nIntegrity Validated"),
        (30.5, 23.5, 12.5, 10.5, "Physics-Feature\nFusion Layer\n\nKinematic Prior ⊗\nMulti-Scale Features"),
        (30.5, 11.5, 12.5, 10.5, "VibraDistillMicro\n1D-CNN (INT8)\n\n8,677 Params (8.5KB)\nk=3,7,15 Depthwise\nCMSIS-NN: 12.88 ms"),
        (45.0, 23.5, 16.5, 10.5, "Evidential Dirichlet (EDL)\nClassifier Head\n\nDirichlet α = e + 1\nVacuity u = K/S (OOD Alert)"),
        (45.0, 11.5, 16.5, 10.5, "Bounded-Delay ACP Engine\nAdaptive Conformal RUL\n\n[RUL_min, RUL_max]\nCertified 90% Coverage"),
        (63.5, 14, 15.5, 20, "Dynamic Power Manager\n& Telemetry Pack\n\n13.9 ms Active / 28.8 ms Sleep\nWFI Deep Sleep (67.4%)\nAvg Current: 9.3 mA\nBOM < $15 USD"),
    ]

    for (bx, by, bw, bh, btext) in mcu_blocks:
        rect = patches.FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0.5",
                                     linewidth=1.2, edgecolor=c_mcu_border, facecolor=c_mcu_box)
        ax.add_patch(rect)
        ax.text(bx + bw/2, by + bh/2, btext, fontsize=6.8, ha='center', va='center',
                fontweight='semibold', color=c_mcu_text)

    # Connecting arrows inside MCU
    arrow_m = dict(arrowstyle="->", lw=1.4, color=c_mcu_border)
    ax.annotate("", xy=(30.5, 28.5), xytext=(28.5, 24), arrowprops=arrow_m)
    ax.annotate("", xy=(30.5, 16.5), xytext=(28.5, 24), arrowprops=arrow_m)
    ax.annotate("", xy=(45.0, 28.5), xytext=(43.0, 28.5), arrowprops=arrow_m)
    ax.annotate("", xy=(45.0, 16.5), xytext=(43.0, 16.5), arrowprops=arrow_m)
    ax.annotate("", xy=(63.5, 24), xytext=(61.5, 28.5), arrowprops=arrow_m)
    ax.annotate("", xy=(63.5, 24), xytext=(61.5, 16.5), arrowprops=arrow_m)

    ax.text(48, 5.0, "Decoupled Knowledge Distillation (DKD): ResNet Teacher (20.4k) -> VibraDistillMicro Student (8,677) [τ=4.0, λ1=1.0, λ2=1.0]",
            fontsize=7.2, ha='center', style='italic', color='#1B5E20')

    # --- 4. OUTPUT PERIPHERALS & TELEMETRY (Right) ---
    out_rect = patches.FancyBboxPatch((83, 14), 15.5, 60, boxstyle="round,pad=0.8",
                                     linewidth=1.8, edgecolor=c_out_border, facecolor=c_out_bg)
    ax.add_patch(out_rect)
    ax.text(90.75, 70, "FIELD TELEMETRY\n& INDUSTRIAL HMI", fontsize=9.2, fontweight='bold', ha='center', va='center', color=c_out_border)

    hmi_blocks = [
        (84.5, 47, 12.5, 19, "0.96\" I2C OLED\n(SSD1306)\n\n• Fault: BPFO/BPFI\n• Vacuity u: 0.12 (OK)\n• RUL: [142, 168] h\n• Speed: fr = 29.8 Hz"),
        (84.5, 20, 12.5, 23, "Wireless / Fieldbus\nTelemetry\n\n• LoRaWAN (868/915)\n  Long-range Smart Pod\n• RS485 Modbus RTU\n• CAN Bus 2.0B\n  Industrial SCADA / PLC"),
    ]
    for (bx, by, bw, bh, btext) in hmi_blocks:
        rect = patches.FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0.4",
                                     linewidth=1.0, edgecolor=c_out_border, facecolor=c_out_box)
        ax.add_patch(rect)
        ax.text(bx + bw/2, by + bh/2, btext, fontsize=6.8, ha='center', va='center',
                fontweight='semibold', color='#311B92')

    # Connecting arrows from MCU to Output Peripherals
    ax.annotate("", xy=(84.5, 56.5), xytext=(79.0, 28), 
                arrowprops=dict(arrowstyle="->", lw=1.6, color=c_out_border, connectionstyle="arc3,rad=-0.25"))
    ax.text(80.5, 45, "I2C\n400kHz", fontsize=6.8, fontweight='bold', color=c_out_border)

    ax.annotate("", xy=(84.5, 31.5), xytext=(79.0, 24), 
                arrowprops=dict(arrowstyle="->", lw=1.6, color=c_out_border, connectionstyle="arc3,rad=0.15"))
    ax.text(80.5, 23, "UART/CAN", fontsize=6.8, fontweight='bold', color=c_out_border)

    plt.tight_layout()
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    plt.close()
    print(f"Flawless diagram generated at:\n  - {png_path}\n  - {pdf_path}")

if __name__ == '__main__':
    create_system_diagram()
