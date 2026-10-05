// ============================================================================
// Module Name: spi_master_packet16
// Description: Ultra-Compact 16-Byte SPI Master Packetizer with Hardware CRC-16
// Target:      Gowin GW2A-LV18PG256 (Primer 20K) -> Sonix SN32F407 (Cortex-M0)
// Clock:       100 MHz Core System Clock -> 4.0 MHz SPI Clock (SCK)
// Protocol:    16-Byte Compact Frame with 25 µs WFI Wakeup Guardband
//              [0:1]   Sync Word: 0x55AA
//              [2:3]   Frame Counter: uint16_t
//              [4]     Fault Class: uint8_t (0: Normal, 1: Ball, 2: Inner, 3: Outer)
//              [5]     Confidence: uint8_t (0 - 100%)
//              [6:7]   Vacuity u: uint16_t Q1.15 (0 - 32768)
//              [8:9]   RUL Raw: uint16_t (0.1 hours/LSB)
//              [10:11] Kinematic Mask: uint16_t (BPFO, BPFI, BSF, FTF)
//              [12:13] Status Flags: uint16_t
//              [14:15] CRC-16-CCITT: Polynomial 0x1021
// ============================================================================

`timescale 1ns / 1ps

module spi_master_packet16 (
    input  wire        clk,           // 100 MHz System Clock
    input  wire        rst_n,         // Synchronous Active-Low Reset
    input  wire        start_tx,      // 1-cycle pulse when NPU inference finishes
    
    // NPU Output Signals
    input  wire [15:0] frame_id,
    input  wire [7:0]  fault_class,
    input  wire [7:0]  confidence,
    input  wire [15:0] vacuity_u,
    input  wire [15:0] rul_raw,
    input  wire [15:0] kinematic_mask,
    input  wire [15:0] status_flags,
    
    // SPI Physical Pins to Sonix SN32F407 MCU
    output reg         spi_sck,       // SPI Clock (4.0 MHz: 12 high, 13 low @ 100 MHz)
    output reg         spi_cs_n,      // Active-Low Chip Select
    output reg         spi_mosi,      // Master Out Slave In
    output reg         alert_int,     // Active-High Interrupt to MCU EXTI
    output reg         tx_busy        // High while transmitting
);

    // 4.0 MHz Clock Generation from 100 MHz (Divide by 25: 12 high, 13 low)
    reg [4:0] clk_div;
    wire sck_tick = (clk_div == 5'd11); // Half-period
    wire sck_fall = (clk_div == 5'd24); // Full-period

    // 25.0 µs Wakeup Guardband Counter (2,500 clock cycles @ 100 MHz)
    reg [11:0] guard_cnt;
    localparam GUARD_LIMIT = 12'd2500;

    // FSM States
    localparam S_IDLE      = 3'd0;
    localparam S_WAKEUP    = 3'd1;
    localparam S_LOAD_BYTE = 3'd2;
    localparam S_SHIFT_BIT = 3'd3;
    localparam S_DONE      = 3'd4;

    reg [2:0]  state;
    reg [3:0]  byte_idx; // 0 to 15 (16 bytes)
    reg [2:0]  bit_idx;  // 7 downto 0
    reg [7:0]  current_byte;
    reg [15:0] crc16_reg;

    // CRC-16-CCITT Calculation Function
    function [15:0] crc16_step(input [15:0] crc, input [7:0] data);
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
            crc16_step = c;
        end
    endfunction

    // 16-Byte Packet Multiplexer
    reg [7:0] packet_rom [0:15];

    always @(posedge clk) begin
        if (!rst_n) begin
            state        <= S_IDLE;
            spi_sck      <= 1'b0;
            spi_cs_n     <= 1'b1;
            spi_mosi     <= 1'b0;
            alert_int    <= 1'b0;
            tx_busy      <= 1'b0;
            clk_div      <= 5'd0;
            guard_cnt    <= 12'd0;
            byte_idx     <= 4'd0;
            bit_idx      <= 3'd7;
            current_byte <= 8'd0;
            crc16_reg    <= 16'hFFFF;
        end else begin
            case (state)
                S_IDLE: begin
                    spi_sck   <= 1'b0;
                    spi_cs_n  <= 1'b1;
                    spi_mosi  <= 1'b0;
                    alert_int <= 1'b0;
                    tx_busy   <= 1'b0;
                    clk_div   <= 5'd0;

                    if (start_tx) begin
                        // Assemble the 16-byte frame payload
                        packet_rom[ 0] <= 8'h55;
                        packet_rom[ 1] <= 8'hAA;
                        packet_rom[ 2] <= frame_id[15:8];
                        packet_rom[ 3] <= frame_id[7:0];
                        packet_rom[ 4] <= fault_class;
                        packet_rom[ 5] <= confidence;
                        packet_rom[ 6] <= vacuity_u[15:8];
                        packet_rom[ 7] <= vacuity_u[7:0];
                        packet_rom[ 8] <= rul_raw[15:8];
                        packet_rom[ 9] <= rul_raw[7:0];
                        packet_rom[10] <= kinematic_mask[15:8];
                        packet_rom[11] <= kinematic_mask[7:0];
                        packet_rom[12] <= status_flags[15:8];
                        packet_rom[13] <= status_flags[7:0];
                        
                        // Compute CRC-16 over bytes 0..13
                        crc16_reg <= 16'hFFFF;
                        
                        // Assert interrupt to wake Cortex-M0 from WFI sleep
                        alert_int  <= 1'b1;
                        spi_cs_n   <= 1'b0; // Pull CS low
                        tx_busy    <= 1'b1;
                        guard_cnt  <= 12'd0;
                        state      <= S_WAKEUP;
                    end
                end

                S_WAKEUP: begin
                    // Wait for 25.0 µs (2,500 clock cycles) to guarantee MCU wakeup
                    if (guard_cnt == GUARD_LIMIT) begin
                        byte_idx     <= 4'd0;
                        current_byte <= packet_rom[0];
                        bit_idx      <= 3'd7;
                        clk_div      <= 5'd0;
                        state        <= S_LOAD_BYTE;
                    end else begin
                        guard_cnt <= guard_cnt + 1'b1;
                    end
                end

                S_LOAD_BYTE: begin
                    if (byte_idx == 4'd14) begin
                        // Insert CRC high byte
                        current_byte <= crc16_reg[15:8];
                    end else if (byte_idx == 4'd15) begin
                        // Insert CRC low byte
                        current_byte <= crc16_reg[7:0];
                    end else begin
                        current_byte <= packet_rom[byte_idx];
                        crc16_reg    <= crc16_step(crc16_reg, packet_rom[byte_idx]);
                    end
                    bit_idx <= 3'd7;
                    state   <= S_SHIFT_BIT;
                end

                S_SHIFT_BIT: begin
                    clk_div <= (clk_div == 5'd24) ? 5'd0 : (clk_div + 1'b1);
                    
                    // Drive MOSI stable before SCK rising edge
                    spi_mosi <= current_byte[bit_idx];

                    if (sck_tick) begin
                        spi_sck <= 1'b1; // Rising edge for slave sampling
                    end else if (sck_fall) begin
                        spi_sck <= 1'b0; // Falling edge
                        if (bit_idx == 3'd0) begin
                            if (byte_idx == 4'd15) begin
                                state <= S_DONE;
                            end else begin
                                byte_idx <= byte_idx + 1'b1;
                                state    <= S_LOAD_BYTE;
                            end
                        end else begin
                            bit_idx <= bit_idx - 1'b1;
                        end
                    end
                end

                S_DONE: begin
                    spi_cs_n  <= 1'b1; // Release CS
                    alert_int <= 1'b0; // De-assert interrupt
                    tx_busy   <= 1'b0;
                    state     <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
