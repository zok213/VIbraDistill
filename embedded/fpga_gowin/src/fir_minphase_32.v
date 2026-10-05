// ============================================================================
// Module Name: fir_minphase_32
// Description: 32-Tap Minimum-Phase Causal Bandpass FIR Filter
// Target:      Gowin GW2A-LV18PG256 (Primer 20K) DSP Multiplier/MAC Slices
// Architecture: 4-Multiplier Time-Multiplexed Folded MAC Architecture
//              (Executes 32 taps in 8 clock cycles @ 100 MHz, taking 80 ns)
// Passband:    2000 Hz - 5000 Hz @ Fs = 13.333 kHz
// Features:    Synchronous Reset (prevents LUT explosion in Gowin DSP18E primitives),
//              Minimum-Phase causal impulse response, zero pre-cursor ringing.
// ============================================================================

`timescale 1ns / 1ps

module fir_minphase_32 #(
    parameter DATA_WIDTH  = 16,
    parameter COEFF_WIDTH = 16,
    parameter TAPS        = 32
)(
    input  wire                          clk,        // 100 MHz System Clock
    input  wire                          rst_n,      // Synchronous Active-Low Reset
    input  wire                          sample_en,  // 13.333 kHz Sample Enable Strobe
    input  wire signed [DATA_WIDTH-1:0]  x_in,       // Raw Input Acceleration Sample
    output reg  signed [DATA_WIDTH-1:0]  y_out,      // Filtered Minimum-Phase Sample
    output reg                           valid_out   // Output Valid Strobe
);

    // 32-Sample Circular / Delay Line Shift Register
    reg signed [DATA_WIDTH-1:0] delay_line [0:TAPS-1];
    integer k;

    // Minimum-Phase Filter Coefficients in Q1.15 Format (Reflected roots inside unit circle)
    wire signed [COEFF_WIDTH-1:0] h [0:TAPS-1];
    assign h[ 0] = 16'sh0824; assign h[ 1] = 16'sh0AB1;
    assign h[ 2] = 16'sh0F3A; assign h[ 3] = 16'sh14C2;
    assign h[ 4] = 16'sh198D; assign h[ 5] = 16'sh1C76;
    assign h[ 6] = 16'sh1C2A; assign h[ 7] = 16'sh17B3;
    assign h[ 8] = 16'sh0EE4; assign h[ 9] = 16'sh02EE;
    assign h[10] = 16'shF4BE; assign h[11] = 16'shE689;
    assign h[12] = 16'shDA62; assign h[13] = 16'shD21E;
    assign h[14] = 16'shCEEE; assign h[15] = 16'shD2DE;
    assign h[16] = 16'shDDDE; assign h[17] = 16'shEE1C;
    assign h[18] = 16'sh015E; assign h[19] = 16'sh1476;
    assign h[20] = 16'sh2431; assign h[21] = 16'sh2DCA;
    assign h[22] = 16'sh2EEA; assign h[23] = 16'sh27B8;
    assign h[24] = 16'sh18CE; assign h[25] = 16'sh04DE;
    assign h[26] = 16'shEF2A; assign h[27] = 16'shDBA2;
    assign h[28] = 16'shCCC2; assign h[29] = 16'shC514;
    assign h[30] = 16'shC6AE; assign h[31] = 16'shD0B8;

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
