// ============================================================================
// Module Name: npu_mac12_unit
// Description: 12-Way Parallel INT8 Signed MAC Array with Pipelined Requantizer
// Target:      Gowin Primer 20K (GW2A-LV18PG256) DSP18E Multiplier Slices
// Features:    - 12 parallel signed 8-bit x 8-bit multipliers
//              - 32-bit accumulators with synchronous clear/load
//              - 2-Stage Pipelined Requantization (enables >150 MHz timing closure):
//                  Stage 1: Signed 32x32 Multiply with per-channel requant_mult
//                  Stage 2: 64-bit Rounding, Barrel Shifter, Saturation & ReLU
// ============================================================================

`timescale 1ns / 1ps

module npu_mac12_unit (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 mac_en,       // MAC enable strobe
    input  wire                 acc_clear,    // Clear accumulators (start of new output point)
    input  wire signed [7:0]    act_in,       // Broadcast activation sample (8-bit signed)
    input  wire signed [95:0]   weights_in,   // 12 parallel weights (12 x 8-bit = 96-bit)
    input  wire signed [31:0]   bias_in,      // Bias for requantization channel
    input  wire [31:0]          requant_mult, // Requantization multiplier (unsigned)
    input  wire [5:0]           requant_shift,// Requantization shift amount
    input  wire                 relu_en,      // 1: apply ReLU (clamp negative to 0)
    input  wire                 requant_en,   // Strobe to trigger requantization of acc[channel_sel]
    input  wire [3:0]           channel_sel,  // 0 to 11 to select accumulator for output
    output reg  signed [7:0]    act_out,      // Requantized 8-bit signed activation output
    output reg                  act_valid     // Valid strobe for act_out
);

    // 12 parallel 32-bit accumulators
    reg signed [31:0] accum [0:11];
    integer i;

    // Unpack 12 weights
    wire signed [7:0] w [0:11];
    genvar g;
    generate
        for (g = 0; g < 12; g = g + 1) begin : GEN_WEIGHTS
            assign w[g] = weights_in[(g*8) +: 8];
        end
    endgenerate

    // 12-Way Multiply-Accumulate Datapath
    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < 12; i = i + 1) begin
                accum[i] <= 32'sd0;
            end
        end else begin
            for (i = 0; i < 12; i = i + 1) begin
                if (acc_clear) begin
                    accum[i] <= (mac_en) ? (act_in * w[i]) : 32'sd0;
                end else if (mac_en) begin
                    accum[i] <= accum[i] + (act_in * w[i]);
                end
            end
        end
    end

    // Selected Accumulator + Bias for Requantization
    wire signed [31:0] selected_acc = accum[channel_sel] + bias_in;

    // -------------------------------------------------------------------------
    // PIPELINE STAGE 1: DSP Multiplication (acc * mult)
    // -------------------------------------------------------------------------
    reg signed [63:0] pipe1_scaled_prod;
    reg        [5:0]  pipe1_shift;
    reg               pipe1_relu;
    reg               pipe1_valid;

    always @(posedge clk) begin
        if (!rst_n) begin
            pipe1_scaled_prod <= 64'sd0;
            pipe1_shift       <= 6'd0;
            pipe1_relu        <= 1'b0;
            pipe1_valid       <= 1'b0;
        end else if (requant_en) begin
            pipe1_scaled_prod <= selected_acc * $signed({1'b0, requant_mult});
            pipe1_shift       <= requant_shift;
            pipe1_relu        <= relu_en;
            pipe1_valid       <= 1'b1;
        end else begin
            pipe1_valid       <= 1'b0;
        end
    end

    // -------------------------------------------------------------------------
    // PIPELINE STAGE 2: Rounding, Barrel Shifter, Saturation, ReLU
    // -------------------------------------------------------------------------
    wire signed [63:0] round_offset = (pipe1_shift > 0) ? (64'sd1 <<< (pipe1_shift - 1)) : 64'sd0;
    wire signed [63:0] rounded_val  = pipe1_scaled_prod + round_offset;
    wire signed [63:0] shifted_val  = rounded_val >>> pipe1_shift;

    always @(posedge clk) begin
        if (!rst_n) begin
            act_out   <= 8'sd0;
            act_valid <= 1'b0;
        end else if (pipe1_valid) begin
            reg signed [7:0] clamped;
            if (shifted_val > 64'sd127) begin
                clamped = 8'sd127;
            end else if (shifted_val < -64'sd128) begin
                clamped = -8'sd128;
            end else begin
                clamped = shifted_val[7:0];
            end

            if (pipe1_relu && (clamped < 8'sd0)) begin
                act_out <= 8'sd0;
            end else begin
                act_out <= clamped;
            end
            act_valid <= 1'b1;
        end else begin
            act_valid <= 1'b0;
        end
    end

endmodule
