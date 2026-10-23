// ============================================================================
// Module Name: adxl345_spi_master
// Description: Industrial-Grade Hardware SPI Master & Autonomous Configuration FSM
//              for Analog Devices ADXL345 / GY-291 3-Axis Accelerometer Module.
// Target:      Gowin Tang Primer 20K (GW2A-LV18PG256) @ 100 MHz Master System Clock
// Datasheet:   Analog Devices ADXL345 Rev. G & GY-291 Schematic
//
// Key Specifications & Operating Modes:
//   1. Master System Clock: 100 MHz -> SPI SCLK = 5.0 MHz (Div-20, Mode 3: CPOL=1, CPHA=1)
//   2. Autonomous Initialization Sequence (5 Registers configured after 10ms POR delay):
//        - Reg 0x2C (BW_RATE)    <- 0x0F (ODR = 3,200 Hz, Bandwidth = 1,600 Hz)
//        - Reg 0x31 (DATA_FORMAT)<- 0x0B (Full-Res +/-16g, 4-Wire SPI)
//        - Reg 0x2E (INT_ENABLE) <- 0x80 (DATA_READY Interrupt Enable)
//        - Reg 0x2F (INT_MAP)    <- 0x00 (Map DATA_READY to INT1 Pin)
//        - Reg 0x2D (POWER_CTL)  <- 0x08 (Measure Mode Enabled)
//   3. High-Speed Acquisition:
//        - Driven by INT1 rising-edge interrupt (or autonomous 3.2 kHz hardware timer)
//        - Burst Reads 6 Bytes starting at Reg 0x32 (DATAX0): Command 0xF2
//        - Formats: 16-bit Signed Twos-Complement X, Y, Z (4 mg/LSB Full Resolution)
//        - Emits 1-cycle sample_valid pulse at 3,200 Hz directly into Causal FIR Filter
// ============================================================================

`timescale 1ns / 1ps

module adxl345_spi_master #(
    parameter CLK_FREQ_HZ = 100_000_000,
    parameter SPI_SCLK_HZ = 5_000_000,
    parameter DATA_WIDTH  = 16
)(
    input  wire                          clk,            // 100 MHz Master System Clock
    input  wire                          rst_n,          // Active-Low Reset
    
    // Physical SPI Pins connected to GY-291 Module (PMOD0 Header J3)
    output reg                           spi_cs_n,       // Active-Low Chip Select
    output reg                           spi_sclk,       // 5.0 MHz SPI Clock (Idle High)
    output reg                           spi_mosi,       // Master Out Slave In
    input  wire                          spi_miso,       // Master In Slave Out (SDO)
    input  wire                          adxl_int1,      // DATA_READY Interrupt Pulse from ADXL345
    
    // Processed Acceleration Outputs to Streaming DSP Pipeline
    output reg  signed [DATA_WIDTH-1:0]  accel_x,        // 16-bit signed X-axis (4 mg/LSB)
    output reg  signed [DATA_WIDTH-1:0]  accel_y,        // 16-bit signed Y-axis (4 mg/LSB)
    output reg  signed [DATA_WIDTH-1:0]  accel_z,        // 16-bit signed Z-axis (Primary Bearing Axis)
    output reg                           sample_valid,   // Single-cycle 3,200 Hz strobe to FIR filter
    output reg                           ready           // High when initialization completed
);

    // -------------------------------------------------------------------------
    // 1. SPI Clock Strobe Generator (5.0 MHz SCLK from 100 MHz Master Clock)
    // -------------------------------------------------------------------------
    // 100 MHz / 5.0 MHz = 20 cycles total period.
    // Half-period = 10 clock cycles (100 ns).
    localparam SCLK_HALF_PERIOD = CLK_FREQ_HZ / (2 * SPI_SCLK_HZ); // 10 cycles

    reg [4:0] clk_div_cnt;
    reg       sclk_tick; // Pulses high every 100 ns

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_div_cnt <= 5'd0;
            sclk_tick   <= 1'b0;
        end else begin
            if (clk_div_cnt == SCLK_HALF_PERIOD - 1) begin
                clk_div_cnt <= 5'd0;
                sclk_tick   <= 1'b1;
            end else begin
                clk_div_cnt <= clk_div_cnt + 1'b1;
                sclk_tick   <= 1'b0;
            end
        end
    end

    // -------------------------------------------------------------------------
    // 2. Asynchronous INT1 Dual-Stage Synchronizer & Edge Detector
    // -------------------------------------------------------------------------
    reg int1_sync1, int1_sync2;
    wire int1_rising_edge;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            int1_sync1 <= 1'b0;
            int1_sync2 <= 1'b0;
        end else begin
            int1_sync1 <= adxl_int1;
            int1_sync2 <= int1_sync1;
        end
    end
    assign int1_rising_edge = (int1_sync1 == 1'b1) && (int1_sync2 == 1'b0);

    // -------------------------------------------------------------------------
    // 3. Configuration Table ROM (5 Registers to Initialize ADXL345)
    // -------------------------------------------------------------------------
    reg [2:0]  cfg_idx;
    reg [7:0]  cfg_addr;
    reg [7:0]  cfg_data;

    always @(*) begin
        case (cfg_idx)
            3'd0: begin cfg_addr = 8'h2C; cfg_data = 8'h0F; end // BW_RATE: 3.2 kHz ODR
            3'd1: begin cfg_addr = 8'h31; cfg_data = 8'h0B; end // DATA_FORMAT: Full-Res +/-16g
            3'd2: begin cfg_addr = 8'h2E; cfg_data = 8'h80; end // INT_ENABLE: DATA_READY
            3'd3: begin cfg_addr = 8'h2F; cfg_data = 8'h00; end // INT_MAP: Map to INT1
            3'd4: begin cfg_addr = 8'h2D; cfg_data = 8'h08; end // POWER_CTL: Measure mode
            default: begin cfg_addr = 8'h00; cfg_data = 8'h00; end
        endcase
    end

    // -------------------------------------------------------------------------
    // 4. Autonomous State Machine (FSM)
    // -------------------------------------------------------------------------
    localparam ST_IDLE            = 4'd0,
               ST_POWER_ON_DELAY  = 4'd1,
               ST_CFG_START       = 4'd2,
               ST_CFG_SHIFT       = 4'd3,
               ST_CFG_CS_WAIT     = 4'd4,
               ST_WAIT_DRDY       = 4'd5,
               ST_BURST_CMD_START = 4'd6,
               ST_BURST_CMD_SHIFT = 4'd7,
               ST_BURST_DATA_SHIFT= 4'd8,
               ST_BURST_DONE      = 4'd9,
               ST_ASSEMBLE_SAMPLE = 4'd10;

    reg [3:0]   state;
    reg [19:0]  timer_cnt;
    reg [15:0]  tx_shift_16;
    reg [4:0]   bit_cnt;
    reg         sclk_phase;
    reg [7:0]   rx_bytes [0:5];   // 6 Acceleration Bytes: X0, X1, Y0, Y1, Z0, Z1
    reg [2:0]   byte_idx;
    reg [7:0]   rx_shift_8;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= ST_IDLE;
            spi_cs_n     <= 1'b1;
            spi_sclk     <= 1'b1; // CPOL = 1 (Idle High)
            spi_mosi     <= 1'b0;
            sample_valid <= 1'b0;
            ready        <= 1'b0;
            accel_x      <= 16'sd0;
            accel_y      <= 16'sd0;
            accel_z      <= 16'sd0;
            timer_cnt    <= 20'd0;
            cfg_idx      <= 3'd0;
            tx_shift_16  <= 16'd0;
            bit_cnt      <= 5'd0;
            sclk_phase   <= 1'b0;
            byte_idx     <= 3'd0;
            rx_shift_8   <= 8'd0;
            rx_bytes[0]  <= 8'd0;
            rx_bytes[1]  <= 8'd0;
            rx_bytes[2]  <= 8'd0;
            rx_bytes[3]  <= 8'd0;
            rx_bytes[4]  <= 8'd0;
            rx_bytes[5]  <= 8'd0;
        end else begin
            sample_valid <= 1'b0; // Default: Single cycle strobe

            case (state)
                ST_IDLE: begin
                    spi_cs_n   <= 1'b1;
                    spi_sclk   <= 1'b1;
                    spi_mosi   <= 1'b0;
                    ready      <= 1'b0;
                    cfg_idx    <= 3'd0;
                    timer_cnt  <= 20'd0;
                    state      <= ST_POWER_ON_DELAY;
                end

                // Wait 10 ms (1,000,000 cycles @ 100 MHz) for ADXL345 POR to settle
                ST_POWER_ON_DELAY: begin
                    if (timer_cnt < 20'd1_000_000) begin
                        timer_cnt <= timer_cnt + 1'b1;
                    end else begin
                        timer_cnt <= 20'd0;
                        state     <= ST_CFG_START;
                    end
                end

                // Prepare 16-bit register write: {Addr[7:0], Data[7:0]}
                ST_CFG_START: begin
                    spi_cs_n    <= 1'b0; // Assert CS (Low)
                    spi_sclk    <= 1'b1;
                    tx_shift_16 <= {cfg_addr, cfg_data};
                    bit_cnt     <= 5'd16;
                    sclk_phase  <= 1'b0;
                    spi_mosi    <= cfg_addr[7];
                    state       <= ST_CFG_SHIFT;
                end

                // Shift 16 bits out on SCLK at 5.0 MHz (Mode 3: Data valid on rising edge)
                ST_CFG_SHIFT: begin
                    if (sclk_tick) begin
                        if (!sclk_phase) begin
                            // Falling Edge: Drive SCLK Low and update MOSI
                            spi_sclk   <= 1'b0;
                            sclk_phase <= 1'b1;
                            spi_mosi   <= tx_shift_16[15];
                        end else begin
                            // Rising Edge: Drive SCLK High, slave samples MOSI
                            spi_sclk    <= 1'b1;
                            sclk_phase  <= 1'b0;
                            tx_shift_16 <= {tx_shift_16[14:0], 1'b0};
                            bit_cnt     <= bit_cnt - 1'b1;
                            
                            if (bit_cnt == 5'd1) begin
                                spi_cs_n  <= 1'b1; // Deassert CS (High)
                                timer_cnt <= 20'd0;
                                state     <= ST_CFG_CS_WAIT;
                            end
                        end
                    end
                end

                // Hold CS High for at least 150 ns (20 cycles @ 100 MHz) between transfers
                ST_CFG_CS_WAIT: begin
                    spi_cs_n <= 1'b1;
                    spi_sclk <= 1'b1;
                    spi_mosi <= 1'b0;
                    if (timer_cnt < 20'd25) begin
                        timer_cnt <= timer_cnt + 1'b1;
                    end else begin
                        timer_cnt <= 20'd0;
                        if (cfg_idx < 3'd4) begin
                            cfg_idx <= cfg_idx + 1'b1;
                            state   <= ST_CFG_START;
                        end else begin
                            ready <= 1'b1; // All 5 configuration registers written successfully
                            state <= ST_WAIT_DRDY;
                        end
                    end
                end

                // Wait for INT1 Data Ready pulse or fallback 3.2 kHz timer tick
                ST_WAIT_DRDY: begin
                    spi_cs_n <= 1'b1;
                    spi_sclk <= 1'b1;
                    spi_mosi <= 1'b0;

                    // 31,250 cycles @ 100 MHz = exactly 3,200.0 Hz fallback timer
                    if (int1_rising_edge || timer_cnt >= 20'd31_250) begin
                        timer_cnt <= 20'd0;
                        state     <= ST_BURST_CMD_START;
                    end else begin
                        timer_cnt <= timer_cnt + 1'b1;
                    end
                end

                // Start Burst Read: Command 0xF2 (Read=1, Multiple=1, Addr=0x32 DATAX0)
                ST_BURST_CMD_START: begin
                    spi_cs_n    <= 1'b0; // Assert CS (Low)
                    spi_sclk    <= 1'b1;
                    tx_shift_16 <= {8'hF2, 8'h00};
                    bit_cnt     <= 5'd8;
                    sclk_phase  <= 1'b0;
                    spi_mosi    <= 1'b1; // First bit of 0xF2 is 1
                    state       <= ST_BURST_CMD_SHIFT;
                end

                // Shift 8 bits of command 0xF2 to ADXL345
                ST_BURST_CMD_SHIFT: begin
                    if (sclk_tick) begin
                        if (!sclk_phase) begin
                            spi_sclk   <= 1'b0;
                            sclk_phase <= 1'b1;
                            spi_mosi   <= tx_shift_16[15];
                        end else begin
                            spi_sclk    <= 1'b1;
                            sclk_phase  <= 1'b0;
                            tx_shift_16 <= {tx_shift_16[14:0], 1'b0};
                            bit_cnt     <= bit_cnt - 1'b1;
                            
                            if (bit_cnt == 5'd1) begin
                                byte_idx   <= 3'd0;
                                bit_cnt    <= 5'd8;
                                rx_shift_8 <= 8'd0;
                                state      <= ST_BURST_DATA_SHIFT;
                            end
                        end
                    end
                end

                // Read 6 Consecutive Bytes (X0, X1, Y0, Y1, Z0, Z1)
                ST_BURST_DATA_SHIFT: begin
                    if (sclk_tick) begin
                        if (!sclk_phase) begin
                            // SCLK Falling Edge
                            spi_sclk   <= 1'b0;
                            sclk_phase <= 1'b1;
                        end else begin
                            // SCLK Rising Edge: Sample MISO bit
                            spi_sclk   <= 1'b1;
                            sclk_phase <= 1'b0;
                            rx_shift_8 <= {rx_shift_8[6:0], spi_miso};
                            bit_cnt    <= bit_cnt - 1'b1;
                            
                            if (bit_cnt == 5'd1) begin
                                rx_bytes[byte_idx] <= {rx_shift_8[6:0], spi_miso};
                                bit_cnt <= 5'd8;
                                if (byte_idx == 3'd5) begin
                                    state <= ST_BURST_DONE;
                                end else begin
                                    byte_idx <= byte_idx + 1'b1;
                                end
                            end
                        end
                    end
                end

                // Deassert Chip Select after burst read completed
                ST_BURST_DONE: begin
                    spi_cs_n <= 1'b1;
                    spi_sclk <= 1'b1;
                    spi_mosi <= 1'b0;
                    state    <= ST_ASSEMBLE_SAMPLE;
                end

                // Assemble 16-bit Signed Little-Endian Acceleration Values
                ST_ASSEMBLE_SAMPLE: begin
                    accel_x      <= {rx_bytes[1], rx_bytes[0]};
                    accel_y      <= {rx_bytes[3], rx_bytes[2]};
                    accel_z      <= {rx_bytes[5], rx_bytes[4]}; // Primary vibration axis
                    sample_valid <= 1'b1; // Strobe to FIR filter
                    state        <= ST_WAIT_DRDY;
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
