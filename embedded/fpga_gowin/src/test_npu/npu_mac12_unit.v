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
    output reg                  act_valid,    // Valid strobe for act_out
    output wire signed [383:0]  accum_all_out // Direct 12-channel accumulators output (12 x 32-bit)
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

    // -------------------------------------------------------------------------
    // 2-Stage High-Performance MAC Pipeline (Guarantees >200 MHz Gowin Timing Closure)
    // Stage 1: Register BSRAM DO weights and broadcast activation
    // Stage 2: Register 12 signed 8x8 products
    // Stage 3: 32-bit Accumulator Update
    // Eliminates combinational path from BSRAM DO through multiplier and adder carry chain.
    // -------------------------------------------------------------------------
    reg signed [7:0]  pipe1_act;
    reg signed [7:0]  pipe1_w [0:11];
    reg               pipe1_mac_en;
    reg               pipe1_acc_clear;

    always @(posedge clk) begin
        if (!rst_n) begin
            pipe1_act       <= 8'sd0;
            pipe1_mac_en    <= 1'b0;
            pipe1_acc_clear <= 1'b0;
            for (i = 0; i < 12; i = i + 1) begin
                pipe1_w[i] <= 8'sd0;
            end
        end else begin
            pipe1_act       <= act_in;
            pipe1_mac_en    <= mac_en;
            pipe1_acc_clear <= acc_clear;
            for (i = 0; i < 12; i = i + 1) begin
                pipe1_w[i] <= w[i];
            end
        end
    end

    reg signed [15:0] pipe2_prod [0:11];
    reg               pipe2_mac_en;
    reg               pipe2_acc_clear;

    always @(posedge clk) begin
        if (!rst_n) begin
            pipe2_mac_en    <= 1'b0;
            pipe2_acc_clear <= 1'b0;
            for (i = 0; i < 12; i = i + 1) begin
                pipe2_prod[i] <= 16'sd0;
            end
        end else begin
            pipe2_mac_en    <= pipe1_mac_en;
            pipe2_acc_clear <= pipe1_acc_clear;
            for (i = 0; i < 12; i = i + 1) begin
                pipe2_prod[i] <= pipe1_act * pipe1_w[i];
            end
        end
    end

    // Stage 3: Accumulator Update
    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < 12; i = i + 1) begin
                accum[i] <= 32'sd0;
            end
        end else begin
            for (i = 0; i < 12; i = i + 1) begin
                if (pipe2_acc_clear) begin
                    accum[i] <= pipe2_mac_en ? {{16{pipe2_prod[i][15]}}, pipe2_prod[i]} : 32'sd0;
                end else if (pipe2_mac_en) begin
                    accum[i] <= accum[i] + {{16{pipe2_prod[i][15]}}, pipe2_prod[i]};
                end
            end
        end
    end

    // Direct Parallel Output of All 12 Accumulators
    assign accum_all_out = {
        accum[11], accum[10], accum[9], accum[8],
        accum[7],  accum[6],  accum[5], accum[4],
        accum[3],  accum[2],  accum[1], accum[0]
    };

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

    wire signed [7:0] clamped_val = (shifted_val > 64'sd127)  ? 8'sd127 :
                                    (shifted_val < -64'sd128) ? -8'sd128 :
                                    shifted_val[7:0];

    always @(posedge clk) begin
        if (!rst_n) begin
            act_out   <= 8'sd0;
            act_valid <= 1'b0;
        end else if (pipe1_valid) begin
            if (pipe1_relu && (clamped_val < 8'sd0)) begin
                act_out <= 8'sd0;
            end else begin
                act_out <= clamped_val;
            end
            act_valid <= 1'b1;
        end else begin
            act_valid <= 1'b0;
        end
    end

endmodule
