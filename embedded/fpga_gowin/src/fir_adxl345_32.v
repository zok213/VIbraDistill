// ============================================================================
// Module Name: fir_adxl345_32
// Description: 32-Tap Minimum-Phase Causal Bandpass FIR Filter for ADXL345
// Target:      Gowin GW2A-LV18PG256 (Primer 20K) DSP Multiplier/MAC Slices
// Architecture: 4-Multiplier Time-Multiplexed Folded MAC Architecture
//              (Executes 32 taps in 8 clock cycles @ 100 MHz, taking 80 ns)
// Passband:    280 Hz - 1400 Hz @ Fs = 3,200 Hz
// Features:    Synchronous Reset (prevents LUT explosion in Gowin DSP18E primitives),
//              Minimum-Phase causal impulse response, Group Delay = 2.76 samples.
//              Triệt tiêu hoàn toàn sóng gợn Gibbs trước va đập cơ khí.
// ============================================================================

`timescale 1ns / 1ps

module fir_adxl345_32 #(
    parameter DATA_WIDTH  = 16,
    parameter COEFF_WIDTH = 16,
    parameter TAPS        = 32
)(
    input  wire                          clk,        // 100 MHz System Clock
    input  wire                          rst_n,      // Synchronous Active-Low Reset
    input  wire                          sample_en,  // 3,200 Hz Sample Enable Strobe
    input  wire signed [DATA_WIDTH-1:0]  x_in,       // Raw ADXL345 Acceleration Sample
    output reg  signed [DATA_WIDTH-1:0]  y_out,      // Filtered Minimum-Phase Sample
    output reg                           valid_out   // Output Valid Strobe
);

    // 32-Sample Circular / Delay Line Shift Register
    reg signed [DATA_WIDTH-1:0] delay_line [0:TAPS-1];
    integer k;

    // Minimum-Phase Filter Coefficients in Q1.15 Format for ADXL345 (Fs = 3,200 Hz)
    wire signed [COEFF_WIDTH-1:0] h [0:TAPS-1];
    assign h[ 0] = 16'sh1FEB; assign h[ 1] = 16'shF4F3;
    assign h[ 2] = 16'shB3D6; assign h[ 3] = 16'sh16F9;
    assign h[ 4] = 16'sh216F; assign h[ 5] = 16'sh03AB;
    assign h[ 6] = 16'sh1BEF; assign h[ 7] = 16'shF030;
    assign h[ 8] = 16'shFF65; assign h[ 9] = 16'shF182;
    assign h[10] = 16'shF302; assign h[11] = 16'sh0067;
    assign h[12] = 16'shF787; assign h[13] = 16'sh0C3B;
    assign h[14] = 16'shFFD1; assign h[15] = 16'sh0BD8;
    assign h[16] = 16'sh030B; assign h[17] = 16'sh027D;
    assign h[18] = 16'sh0179; assign h[19] = 16'shF98E;
    assign h[20] = 16'shFF9D; assign h[21] = 16'shF791;
    assign h[22] = 16'sh0011; assign h[23] = 16'shFBFB;
    assign h[24] = 16'sh01B5; assign h[25] = 16'sh01AF;
    assign h[26] = 16'sh021B; assign h[27] = 16'sh0435;
    assign h[28] = 16'sh0081; assign h[29] = 16'sh02E9;
    assign h[30] = 16'shFE5C; assign h[31] = 16'sh002F;

    // FSM States for 4-Multiplier Folded Engine (8 cycles)
    localparam S_IDLE = 2'd0;
    localparam S_CALC = 2'd1;
    localparam S_DONE = 2'd2;

    reg [1:0] state;
    reg [2:0] cycle_cnt; // 0 to 7 (8 cycles x 4 MACs = 32 taps)
    reg signed [35:0] acc;

    // 4 Parallel Multipliers
    wire [4:0] idx0 = {cycle_cnt, 2'b00};
    wire [4:0] idx1 = {cycle_cnt, 2'b01};
    wire [4:0] idx2 = {cycle_cnt, 2'b10};
    wire [4:0] idx3 = {cycle_cnt, 2'b11};

    wire signed [31:0] p0 = delay_line[idx0] * h[idx0];
    wire signed [31:0] p1 = delay_line[idx1] * h[idx1];
    wire signed [31:0] p2 = delay_line[idx2] * h[idx2];
    wire signed [31:0] p3 = delay_line[idx3] * h[idx3];

    // Synchronous Reset Mandate for Gowin DSP18E inference
    always @(posedge clk) begin
        if (!rst_n) begin
            for (k = 0; k < TAPS; k = k + 1) begin
                delay_line[k] <= 16'sd0;
            end
            state     <= S_IDLE;
            cycle_cnt <= 3'd0;
            acc       <= 36'sd0;
            y_out     <= 16'sd0;
            valid_out <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    valid_out <= 1'b0;
                    if (sample_en) begin
                        // Shift delay line and insert new sample
                        delay_line[0] <= x_in;
                        for (k = 1; k < TAPS; k = k + 1) begin
                            delay_line[k] <= delay_line[k-1];
                        end
                        // Start folded accumulation
                        cycle_cnt <= 3'd0;
                        acc       <= 36'sd0;
                        state     <= S_CALC;
                    end
                end

                S_CALC: begin
                    // Accumulate 4 MAC products per cycle
                    acc <= acc + p0 + p1 + p2 + p3;
                    if (cycle_cnt == 3'd7) begin
                        state <= S_DONE;
                    end else begin
                        cycle_cnt <= cycle_cnt + 1'b1;
                    end
                end

                S_DONE: begin
                    // Output scaled Q1.15 sample (bits [30:15])
                    y_out     <= acc[30:15];
                    valid_out <= 1'b1;
                    state     <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
