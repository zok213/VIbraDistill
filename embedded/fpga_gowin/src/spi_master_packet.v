// ============================================================================
// Module Name: spi_master_packet
// Description: High-Speed SPI Master Packetizer with Hardware CRC-16-CCITT
// Target:      Gowin GW2A-LV18PG256 (Primer 20K) -> Sonix SN34F788 SPI Slave DMA
// Clock:       100 MHz System Clock -> 12.0 MHz SPI Clock (SCK)
// Packet:      524 Bytes total
//              [0:1]   Sync Header: 0xAA55
//              [2:3]   Frame Counter: uint16_t
//              [4:5]   Shaft Speed fr: uint16_t (0.1 Hz units)
//              [6:7]   Temperature: int16_t (0.1 C units)
//              [8:521] 257 Bins: uint16_t * 257 (Q0.15 normalized)
//              [522:523] CRC-16-CCITT: Polynomial 0x1021
// ============================================================================

module spi_master_packet #(
    parameter TOTAL_BYTES = 524,
    parameter NUM_BINS = 257
)(
    input  wire        clk,           // 100 MHz System Clock
    input  wire        rst_n,         // Active-low Reset
    input  wire        start_tx,      // Pulse to trigger packet transmission
    input  wire [15:0] shaft_speed,   // Shaft Speed fr from tachometer or IAS
    input  wire [15:0] temperature,   // Temperature from bearing housing
    
    // Interface to Dual-Port Block RAM storing 257 FFT bins
    output reg  [8:0]  bram_addr,     // 0 to 256
    input  wire [15:0] bram_data,     // 16-bit Q0.15 bin magnitude
    
    // SPI Physical Interface to Sonix MCU
    output reg         spi_sck,       // SPI Clock (12.0 MHz)
    output reg         spi_cs_n,      // SPI Active-Low Chip Select
    output reg         spi_mosi,      // Master Out Slave In
    output reg         irq_pulse,     // Hardware interrupt pulse to MCU GPIO
    output reg         tx_busy        // High while transmission in progress
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

    // CRC-16-CCITT update function (Polynomial: 0x1021)
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

    // Combinational next-byte multiplexer for strict bit-true CRC calculation
    wire [7:0] next_byte = (byte_idx == 10'd0)   ? 8'hAA :
                           (byte_idx == 10'd1)   ? 8'h55 :
                           (byte_idx == 10'd2)   ? frame_count[15:8] :
                           (byte_idx == 10'd3)   ? frame_count[7:0] :
                           (byte_idx == 10'd4)   ? shaft_speed[15:8] :
                           (byte_idx == 10'd5)   ? shaft_speed[7:0] :
                           (byte_idx == 10'd6)   ? temperature[15:8] :
                           (byte_idx == 10'd7)   ? temperature[7:0] :
                           (byte_idx <= 10'd521) ? (byte_idx[0] ? bram_data[7:0] : bram_data[15:8]) :
                           (byte_idx == 10'd522) ? crc16_reg[15:8] : crc16_reg[7:0];

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

                    // Update CRC for data bytes (0 to 521) using incoming next_byte
                    if (byte_idx <= 10'd521) begin
                        crc16_reg <= update_crc(crc16_reg, next_byte);
                    end

                    // Advance BRAM address when LSB byte is consumed
                    if (byte_idx >= 10'd8 && byte_idx <= 10'd521 && byte_idx[0] == 1'b1) begin
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
                    irq_pulse <= 1'b1; // Signal Sonix MCU that frame DMA is complete
                    state     <= STATE_IDLE;
                end
            endcase
        end
    end

endmodule
