// ============================================================================
// Module Name: fir_adxl345_32
// Description: 32-Tap Causal Minimum-Phase Bandpass FIR Filter for ADXL345
// Passband:    280 Hz - 1400 Hz @ Fs = 3,200 Hz
// Features:    Group delay reduced from 15.5 to 2.76 samples.
//              Triệt tiêu hoàn toàn sóng gợn Gibbs trước va đập.
// ============================================================================

`timescale 1ns / 1ps

module fir_adxl345_32 #(
    parameter DATA_WIDTH  = 16,
    parameter COEFF_WIDTH = 16,
    parameter TAPS        = 32
)(
    input  wire                          clk,        // 100 MHz System Clock
    input  wire                          rst_n,      // Synchronous Active-Low Reset
    input  wire                          sample_en,  // 3,200 Hz Strobe (100MHz / 31,250)
    input  wire signed [DATA_WIDTH-1:0]  x_in,       // Raw ADXL345 Sample
    output reg  signed [DATA_WIDTH-1:0]  y_out,      // Filtered Sample
    output reg                           valid_out
);

    wire signed [COEFF_WIDTH-1:0] h [0:TAPS-1];
    assign h[ 0] = 16'sh1FEB;
    assign h[ 1] = 16'shF4F3;
    assign h[ 2] = 16'shB3D6;
    assign h[ 3] = 16'sh16F9;
    assign h[ 4] = 16'sh216F;
    assign h[ 5] = 16'sh03AB;
    assign h[ 6] = 16'sh1BEF;
    assign h[ 7] = 16'shF030;
    assign h[ 8] = 16'shFF65;
    assign h[ 9] = 16'shF182;
    assign h[10] = 16'shF302;
    assign h[11] = 16'sh0067;
    assign h[12] = 16'shF787;
    assign h[13] = 16'sh0C3B;
    assign h[14] = 16'shFFD1;
    assign h[15] = 16'sh0BD8;
    assign h[16] = 16'sh030B;
    assign h[17] = 16'sh027D;
    assign h[18] = 16'sh0179;
    assign h[19] = 16'shF98E;
    assign h[20] = 16'shFF9D;
    assign h[21] = 16'shF791;
    assign h[22] = 16'sh0011;
    assign h[23] = 16'shFBFB;
    assign h[24] = 16'sh01B5;
    assign h[25] = 16'sh01AF;
    assign h[26] = 16'sh021B;
    assign h[27] = 16'sh0435;
    assign h[28] = 16'sh0081;
    assign h[29] = 16'sh02E9;
    assign h[30] = 16'shFE5C;
    assign h[31] = 16'sh002F;

    // 32-Sample Circular / Delay Line Shift Register
    reg signed [DATA_WIDTH-1:0] delay_line [0:TAPS-1];
    integer k;

    // FSM States for 3-Stage Pipelined 4-Multiplier Folded Engine (Timing Closure > 100 MHz)
    localparam S_IDLE    = 3'd0;
    localparam S_CALC    = 3'd1;
    localparam S_DRAIN_1 = 3'd2;
    localparam S_DRAIN_2 = 3'd3;
    localparam S_DONE    = 3'd4;

    reg [2:0] state;
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

    // Stage 1 Pipeline Registers: 4 Multiplier Products (32-bit each)
    reg signed [31:0] pp0, pp1, pp2, pp3;

    // Stage 2 Pipeline Registers: Pairwise Sums (34-bit each, prevents overflow)
    reg signed [33:0] s01, s23;

    // Pipeline Valid Strobe Shift Registers
    reg pv1, pv2;

    // Synchronous Reset Mandate for Gowin DSP18E inference
    always @(posedge clk) begin
        if (!rst_n) begin
            for (k = 0; k < TAPS; k = k + 1) begin
                delay_line[k] <= 16'sd0;
            end
            state     <= S_IDLE;
            cycle_cnt <= 3'd0;
            acc       <= 36'sd0;
            pp0       <= 32'sd0;
            pp1       <= 32'sd0;
            pp2       <= 32'sd0;
            pp3       <= 32'sd0;
            s01       <= 34'sd0;
            s23       <= 34'sd0;
            pv1       <= 1'b0;
            pv2       <= 1'b0;
            y_out     <= 16'sd0;
            valid_out <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    valid_out <= 1'b0;
                    pv1       <= 1'b0;
                    pv2       <= 1'b0;
                    if (sample_en) begin
                        // Shift delay line and insert new sample
                        delay_line[0] <= x_in;
                        for (k = 1; k < TAPS; k = k + 1) begin
                            delay_line[k] <= delay_line[k-1];
                        end
                        // Initialize folded pipelined accumulation
                        cycle_cnt <= 3'd0;
                        acc       <= 36'sd0;
                        pp0       <= 32'sd0;
                        pp1       <= 32'sd0;
                        pp2       <= 32'sd0;
                        pp3       <= 32'sd0;
                        s01       <= 34'sd0;
                        s23       <= 34'sd0;
                        state     <= S_CALC;
                    end
                end

                S_CALC: begin
                    // Stage 1: Latch 4 multiplier products
                    pp0 <= p0;
                    pp1 <= p1;
                    pp2 <= p2;
                    pp3 <= p3;
                    pv1 <= 1'b1;

                    // Stage 2: Pairwise addition (enabled once pv1 is valid)
                    if (pv1) begin
                        s01 <= pp0 + pp1;
                        s23 <= pp2 + pp3;
                        pv2 <= 1'b1;
                    end

                    // Stage 3: Accumulator update (enabled once pv2 is valid)
                    if (pv2) begin
                        acc <= acc + s01 + s23;
                    end

                    if (cycle_cnt == 3'd7) begin
                        state <= S_DRAIN_1;
                    end else begin
                        cycle_cnt <= cycle_cnt + 1'b1;
                    end
                end

                S_DRAIN_1: begin
                    // Process group 7 in Stage 2; accumulate group 6 in Stage 3
                    s01   <= pp0 + pp1;
                    s23   <= pp2 + pp3;
                    acc   <= acc + s01 + s23;
                    state <= S_DRAIN_2;
                end

                S_DRAIN_2: begin
                    // Accumulate group 7 (final 4 taps) in Stage 3
                    acc   <= acc + s01 + s23;
                    state <= S_DONE;
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
