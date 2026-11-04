// ============================================================================
// Module Name: fir_minphase_32
// Description: 32-Tap Minimum-Phase Causal Bandpass FIR Filter
// Target:      Gowin GW2A-LV18PG256 (Primer 20K) DSP Multiplier/MAC Slices
// Architecture: 4-Multiplier Time-Multiplexed Folded MAC Architecture
//              (Executes 32 taps in 8 clock cycles @ 100 MHz, taking 80 ns)
// Passband:    Actual Peaking Band ~720 Hz (400 - 1100 Hz, +15.0 dB Peak Gain @ Fs = 12.0 kHz HIL CWRU / PRONOSTIA)
// Note:        Coefficients are matched bit-true to AI model training (use_rtl_coeffs=True).
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
    input  wire                          sample_en,  // Sample Enable Strobe (12.0 kHz for HIL or 3.2 kHz for ADXL345)
    input  wire signed [DATA_WIDTH-1:0]  x_in,       // Raw Input Acceleration Sample
    output reg  signed [DATA_WIDTH-1:0]  y_out,      // Filtered Minimum-Phase Sample
    output reg                           valid_out   // Output Valid Strobe
);

    // 32-Sample Circular / Delay Line Shift Register
    reg signed [DATA_WIDTH-1:0] delay_line [0:TAPS-1];
    integer k;

    // Minimum-Phase Filter Coefficients in Q1.15 Format (Roots strictly inside unit circle, |z| < 1)
    // Energy concentrated at earliest taps (h[0..3] large) for minimal latency and fastest shock response
    wire signed [COEFF_WIDTH-1:0] h [0:TAPS-1];
    assign h[ 0] = 16'shD0B8; assign h[ 1] = 16'shC6AE;
    assign h[ 2] = 16'shC514; assign h[ 3] = 16'shCCC2;
    assign h[ 4] = 16'shDBA2; assign h[ 5] = 16'shEF2A;
    assign h[ 6] = 16'sh04DE; assign h[ 7] = 16'sh18CE;
    assign h[ 8] = 16'sh27B8; assign h[ 9] = 16'sh2EEA;
    assign h[10] = 16'sh2DCA; assign h[11] = 16'sh2431;
    assign h[12] = 16'sh1476; assign h[13] = 16'sh015E;
    assign h[14] = 16'shEE1C; assign h[15] = 16'shDDDE;
    assign h[16] = 16'shD2DE; assign h[17] = 16'shCEEE;
    assign h[18] = 16'shD21E; assign h[19] = 16'shDA62;
    assign h[20] = 16'shE689; assign h[21] = 16'shF4BE;
    assign h[22] = 16'sh02EE; assign h[23] = 16'sh0EE4;
    assign h[24] = 16'sh17B3; assign h[25] = 16'sh1C2A;
    assign h[26] = 16'sh1C76; assign h[27] = 16'sh198D;
    assign h[28] = 16'sh14C2; assign h[29] = 16'sh0F3A;
    assign h[30] = 16'sh0AB1; assign h[31] = 16'sh0824;

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
