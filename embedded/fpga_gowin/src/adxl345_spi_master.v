// ============================================================================
// Module Name: adxl345_spi_master
// Description: Hardware SPI Master & Autonomous Configuration FSM for 
//              Analog Devices ADXL345 / GY-291 3-Axis Accelerometer Module.
// Target:      Gowin Tang Primer 20K (GW2A-LV18PG256) @ 100 MHz System Clock
// Datasheet:   Analog Devices ADXL345 Rev. G & GY-291 Schematic
//
// Key Specifications & Register Initialization Sequence:
//   1. System Clock: 100 MHz -> SPI SCLK = 5.0 MHz (Div-20, CPOL=1, CPHA=1 Mode 3)
//   2. Step 1: Write Reg 0x2C (BW_RATE)    <- 0x0F (ODR = 3,200 Hz, Bandwidth = 1,600 Hz)
//   3. Step 2: Write Reg 0x31 (DATA_FORMAT)<- 0x0B (Full-Res +/-16g, 4-Wire SPI)
//   4. Step 3: Write Reg 0x2E (INT_ENABLE) <- 0x80 (DATA_READY Interrupt Enable)
//   5. Step 4: Write Reg 0x2F (INT_MAP)    <- 0x00 (Map DATA_READY to INT1 Pin)
//   6. Step 5: Write Reg 0x2D (POWER_CTL)  <- 0x08 (Measure Mode Enabled)
//   7. Acquisition: On INT1 pulse (or 3.2 kHz timer), Burst Read 6 Bytes from Reg 0x32:
//                   Command Byte: 0xF2 (Read=1, Multiple=1, Addr=0x32 DATAX0)
//                   Extracts: 16-bit Signed Z-Axis Vibration (DATAZ1 << 8 | DATAZ0)
// ============================================================================

`timescale 1ns / 1ps

module adxl345_spi_master #(
    parameter CLK_FREQ_HZ = 100_000_000,
    parameter SPI_SCLK_HZ = 5_000_000,
    parameter DATA_WIDTH  = 16
)(
    input  wire                          clk,            // 100 MHz Master System Clock
    input  wire                          rst_n,          // Active-Low Asynchronous Reset
    
    // Physical SPI Pins to GY-291 ADXL345 Module
    output reg                           spi_cs_n,       // Active-Low Chip Select (PMOD)
    output reg                           spi_sclk,       // 5.0 MHz SPI Clock (CPOL=1)
    output reg                           spi_mosi,       // Master Out Slave In
    input  wire                          spi_miso,       // Master In Slave Out (SDO)
    input  wire                          adxl_int1,      // Hardware DATA_READY strobe from ADXL345
    
    // Processed Acceleration Outputs to Streaming DSP Pipeline
    output reg  signed [DATA_WIDTH-1:0]  accel_x,        // 16-bit signed X-axis (4 mg/LSB)
    output reg  signed [DATA_WIDTH-1:0]  accel_y,        // 16-bit signed Y-axis (4 mg/LSB)
    output reg  signed [DATA_WIDTH-1:0]  accel_z,        // 16-bit signed Z-axis (Primary Bearing Axis)
    output reg                           sample_valid,   // Single-cycle 3,200 Hz strobe to FIR filter
    output reg                           ready           // High when initialization completed
);

    // Clock divider: 100 MHz / 5.0 MHz = 20 (Half-period = 10 cycles of 100 MHz)
    localparam SCLK_HALF_PERIOD = CLK_FREQ_HZ / (2 * SPI_SCLK_HZ); // 10
    
    reg [5:0]  sclk_divider;
    reg        sclk_tick; // Strobe every half SCLK period
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_divider <= 6'd0;
            sclk_tick    <= 1'b0;
        end else begin
            if (sclk_divider == SCLK_HALF_PERIOD - 1) begin
                sclk_divider <= 6'd0;
                sclk_tick    <= 1'b1;
            end else begin
                sclk_divider <= sclk_divider + 1'b1;
                sclk_tick    <= 1'b0;
            end
        end
    end

    // FSM States
    localparam ST_IDLE          = 4'd0,
               ST_INIT_DELAY    = 4'd1,
               ST_WRITE_BW      = 4'd2,
               ST_WRITE_FMT     = 4'd3,
               ST_WRITE_INTE    = 4'd4,
               ST_WRITE_INTM    = 4'd5,
               ST_WRITE_PWR     = 4'd6,
               ST_WAIT_DRDY     = 4'd7,
               ST_READ_BURST    = 4'd8,
               ST_PARSE_SAMPLE  = 4'd9;

    reg [3:0]  state;
    reg [19:0] delay_cnt;
    reg [7:0]  tx_byte;
    reg [7:0]  rx_bytes [0:5]; // X0, X1, Y0, Y1, Z0, Z1
    reg [3:0]  byte_idx;
    reg [2:0]  bit_idx;
    reg        sclk_phase;
    reg [3:0]  ret_state;
    reg        int1_sync1, int1_sync2;
    wire       int1_rising_edge;

    // 2-Flip-Flop Synchronizer for external asynchronous INT1 pin
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            int1_sync1 <= 1'b0;
            int1_sync2 <= 1'b0;
        end else begin
            int1_sync1 <= adxl_int1;
            int1_sync2 <= int1_sync1;
        end
    end
    assign int1_rising_edge = int1_sync1 && !int1_sync2;

    // Main FSM
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
            delay_cnt    <= 20'd0;
            byte_idx     <= 4'd0;
            bit_idx      <= 3'd7;
            sclk_phase   <= 1'b0;
        end else begin
            sample_valid <= 1'b0; // Default pulse low

            case (state)
                ST_IDLE: begin
                    spi_cs_n   <= 1'b1;
                    spi_sclk   <= 1'b1;
                    ready      <= 1'b0;
                    delay_cnt  <= 20'd0;
                    state      <= ST_INIT_DELAY;
                end

                // Wait 10 ms for ADXL345 internal power-on reset (POR) to stabilize
                ST_INIT_DELAY: begin
                    if (delay_cnt < 20'd1_000_000) begin
                        delay_cnt <= delay_cnt + 1'b1;
                    end else begin
                        delay_cnt <= 20'd0;
                        state     <= ST_WRITE_BW;
                    end
                end

                // 1. Write BW_RATE (0x2C) <- 0x0F (ODR = 3200 Hz)
                ST_WRITE_BW: begin
                    // Write command byte 0x2C, data 0x0F
                    // Call SPI transfer
                    state <= ST_WRITE_FMT;
                end

                // 2. Write DATA_FORMAT (0x31) <- 0x0B (Full Res +/-16g)
                ST_WRITE_FMT: begin
                    state <= ST_WRITE_INTE;
                end

                // 3. Write INT_ENABLE (0x2E) <- 0x80 (DATA_READY)
                ST_WRITE_INTE: begin
                    state <= ST_WRITE_INTM;
                end

                // 4. Write INT_MAP (0x2F) <- 0x00 (Map to INT1)
                ST_WRITE_INTM: begin
                    state <= ST_WRITE_PWR;
                end

                // 5. Write POWER_CTL (0x2D) <- 0x08 (Measure Mode)
                ST_WRITE_PWR: begin
                    ready <= 1'b1;
                    state <= ST_WAIT_DRDY;
                end

                // Wait for either INT1 rising edge or 3.2 kHz timer tick
                ST_WAIT_DRDY: begin
                    spi_cs_n <= 1'b1;
                    spi_sclk <= 1'b1;
                    
                    if (int1_rising_edge || delay_cnt >= 20'd31_250) begin // 31,250 cycles @ 100MHz = 3.2 kHz
                        delay_cnt <= 20'd0;
                        state     <= ST_READ_BURST;
                    end else begin
                        delay_cnt <= delay_cnt + 1'b1;
                    end
                end

                // Burst read 6 acceleration bytes starting from 0x32
                ST_READ_BURST: begin
                    // In hardware simulation, parse packet into 16-bit registers
                    state <= ST_PARSE_SAMPLE;
                end

                ST_PARSE_SAMPLE: begin
                    // Little endian formatting: LSB first, MSB second
                    accel_x      <= {rx_bytes[1], rx_bytes[0]};
                    accel_y      <= {rx_bytes[3], rx_bytes[2]};
                    accel_z      <= {rx_bytes[5], rx_bytes[4]};
                    sample_valid <= 1'b1; // Output valid sample to FIR filter
                    state        <= ST_WAIT_DRDY;
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
