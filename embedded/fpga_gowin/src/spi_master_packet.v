// ============================================================================
// Module Name: spi_master_packet
// Description: High-Speed SPI Master Packetizer with Hardware CRC-16-CCITT
// Target:      Gowin GW2A-LV18PG256 (Primer 20K) -> Sonix SN32F407 SPI Slave DMA
// Clock:       100 MHz System Clock -> 12.5 MHz SPI Clock (SCK)
// Protocol:    524-Byte Exact Bit-True Alignment with MCU C Struct (main.c):
//              [0:1]     Sync Word: uint16_t (0xAA55 in Little-Endian: 0x55, 0xAA)
//              [2:3]     Frame Counter: uint16_t (Little-Endian: Low, High)
//              [4:517]   257 Bins: uint16_t * 257 (514 Bytes Little-Endian: Low, High)
//              [518]     NPU Predicted Class: uint8_t (0: Normal, 1: Inner, 2: Outer, 3: Ball)
//              [519]     Dirichlet Max Evidence / Vacuity: uint8_t
//              [520:521] Hardware Status Flags: uint16_t (Little-Endian)
//              [522:523] CRC-16-CCITT: Polynomial 0x1021 across bytes 0..521 (Little-Endian)
// ============================================================================

`timescale 1ns / 1ps

module spi_master_packet #(
    parameter TOTAL_BYTES = 524,
    parameter NUM_BINS    = 257
)(
    input  wire        clk,                     // 100 MHz System Clock
    input  wire        rst_n,                   // Active-low Reset
    input  wire        start_tx,                // Pulse to trigger packet transmission
    
    // NPU Inference Results & Status
    input  wire [1:0]  npu_pred_class,          // 0: Normal, 1: Inner, 2: Outer, 3: Ball
    input  wire [7:0]  dirichlet_max_evidence,  // Max evidence / uncertainty metric
    input  wire [15:0] hardware_status_flags,   // Status flags (bit 0: Sensor, bit 1: FIR, bit 2: CRC)
    
    // Interface to Dual-Port Block RAM storing 257 FFT bins
    output reg  [8:0]  bram_addr,               // 0 to 256
    input  wire [15:0] bram_data,               // 16-bit Q0.15 bin magnitude
    
    // SPI Physical Interface to Sonix SN32F407 MCU
    output reg         spi_sck,                 // SPI Clock (12.5 MHz)
    output reg         spi_cs_n,                // SPI Active-Low Chip Select
    output reg         spi_mosi,                // Master Out Slave In
    output reg         irq_pulse,               // Hardware interrupt pulse to MCU GPIO
    output reg         tx_busy                  // High while transmission in progress
);

    // Clock divider: 100 MHz / 8 = 12.5 MHz SPI Clock
    reg [2:0] clk_div;
    wire sck_tick = (clk_div == 3'd3);
    wire sck_fall = (clk_div == 3'd7);

    // FSM States
    localparam STATE_IDLE      = 3'd0;
    localparam STATE_LOAD_BYTE = 3'd1;
    localparam STATE_SHIFT_BIT = 3'd2;
    localparam STATE_DONE      = 3'd3;

    reg [2:0]  state;
    reg [9:0]  byte_idx;     // 0 to 523
    reg [2:0]  bit_idx;      // 7 downto 0
    reg [7:0]  current_byte;
    reg [15:0] frame_count;
    reg [15:0] crc16_reg;

    // CRC-16-CCITT update function (Polynomial: 0x1021, Init: 0xFFFF)
    function [15:0] update_crc(input [15:0] crc, input [7:0] data);
        integer j;
        reg [15:0] c;
        begin
            c = crc ^ (data << 8);
            for (j = 0; j < 8; j = j + 1) begin
                if (c[15])
                    c = (c << 1) ^ 16'h1021;
                else
                    c = c << 1;
            end
            update_crc = c;
        end
    endfunction

    // Exact Little-Endian byte-multiplexer matching Sonix SN32F407 C-struct layout
    wire [7:0] next_byte =
        (byte_idx == 10'd0)   ? 8'h55 :                    // sync_word low byte (0x55)
        (byte_idx == 10'd1)   ? 8'hAA :                    // sync_word high byte (0xAA -> 0xAA55 on ARM)
        (byte_idx == 10'd2)   ? frame_count[7:0] :         // frame_seq_id low byte
        (byte_idx == 10'd3)   ? frame_count[15:8] :        // frame_seq_id high byte
        (byte_idx <= 10'd517) ? (byte_idx[0] ? bram_data[15:8] : bram_data[7:0]) : // 257 bins (Low, High)
        (byte_idx == 10'd518) ? {6'b000000, npu_pred_class} : // npu_pred_class (0, 1, 2, 3)
        (byte_idx == 10'd519) ? dirichlet_max_evidence :   // dirichlet_max_evidence
        (byte_idx == 10'd520) ? hardware_status_flags[7:0] : // hardware_status_flags low byte
        (byte_idx == 10'd521) ? hardware_status_flags[15:8] : // hardware_status_flags high byte
        (byte_idx == 10'd522) ? crc16_reg[7:0] :           // crc16 low byte (Little-Endian in C)
                                crc16_reg[15:8];           // crc16 high byte

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_div      <= 3'd0;
            state        <= STATE_IDLE;
            byte_idx     <= 10'd0;
            bit_idx      <= 3'd7;
            current_byte <= 8'd0;
            frame_count  <= 16'd0;
            crc16_reg    <= 16'hFFFF;
            spi_sck      <= 1'b0;
            spi_cs_n     <= 1'b1;
            spi_mosi     <= 1'b0;
            irq_pulse    <= 1'b0;
            tx_busy      <= 1'b0;
            bram_addr    <= 9'd0;
        end else begin
            clk_div <= clk_div + 1'b1;

            case (state)
                STATE_IDLE: begin
                    spi_cs_n  <= 1'b1;
                    spi_sck   <= 1'b0;
                    tx_busy   <= 1'b0;
                    irq_pulse <= 1'b0;
                    bram_addr <= 9'd0;
                    if (start_tx) begin
                        state        <= STATE_LOAD_BYTE;
                        byte_idx     <= 10'd0;
                        bit_idx      <= 3'd7;
                        crc16_reg    <= 16'hFFFF;
                        tx_busy      <= 1'b1;
                        spi_cs_n     <= 1'b0;
                        bram_addr    <= 9'd0;
                        frame_count  <= frame_count + 1'b1;
                    end
                end

                STATE_LOAD_BYTE: begin
                    current_byte <= next_byte;

                    // Update CRC-16 for payload bytes 0 to 521
                    if (byte_idx <= 10'd521) begin
                        crc16_reg <= update_crc(crc16_reg, next_byte);
                    end

                    // Advance BRAM address when high byte of current bin is consumed
                    if (byte_idx >= 10'd4 && byte_idx <= 10'd517 && byte_idx[0] == 1'b1) begin
                        bram_addr <= bram_addr + 1'b1;
                    end

                    bit_idx <= 3'd7;
                    state   <= STATE_SHIFT_BIT;
                end

                STATE_SHIFT_BIT: begin
                    if (sck_fall) begin
                        spi_mosi <= current_byte[bit_idx];
                        spi_sck  <= 1'b0;
                    end else if (sck_tick) begin
                        spi_sck <= 1'b1;
                        if (bit_idx == 0) begin
                            if (byte_idx == TOTAL_BYTES - 1)
                                state <= STATE_DONE;
                            else begin
                                byte_idx <= byte_idx + 1'b1;
                                state    <= STATE_LOAD_BYTE;
                            end
                        end else begin
                            bit_idx <= bit_idx - 1'b1;
                        end
                    end
                end

                STATE_DONE: begin
                    spi_cs_n  <= 1'b1;
                    spi_sck   <= 1'b0;
                    tx_busy   <= 1'b0;
                    irq_pulse <= 1'b1; // Trigger hardware interrupt on MCU P2.4
                    state     <= STATE_IDLE;
                end
            endcase
        end
    end

endmodule
