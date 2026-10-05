// ============================================================================
// Module Name: envelope_demodulator
// Description: True Causal Envelope Demodulation Engine
//              Full-Wave Absolute Value Rectifier + 2nd-Order Direct-Form I IIR LPF
// Target:      Gowin GW2A-LV18PG256 (Primer 20K)
// Architecture: 3-Stage Pipelined IIR Architecture with Synchronous Reset
// Cutoff:      1000 Hz @ Fs = 13.333 kHz (Butterworth 2nd-Order Response)
// ============================================================================

`timescale 1ns / 1ps

module envelope_demodulator #(
    parameter WIDTH = 16
)(
    input  wire                          clk,        // 50 MHz / 100 MHz System Clock
    input  wire                          rst_n,      // Synchronous Active-Low Reset
    input  wire                          sample_en,  // 13.333 kHz Sample Strobe
    input  wire signed [WIDTH-1:0]       y_filtered, // Bandpass Filtered Sample
    output reg  signed [WIDTH-1:0]       env_out,    // Demodulated Baseband Envelope
    output reg                           valid_out   // Output Valid Strobe
);

    // Step 1: Full-Wave Absolute Value Rectification
    wire signed [WIDTH-1:0] v_rect = (y_filtered < 0) ? -y_filtered : y_filtered;

    // Fixed-Point Butterworth 2nd-Order LPF Coefficients (Fc = 1000 Hz @ Fs = 13.333 kHz)
    // Scaled in Q1.15 Format
    localparam signed [15:0] B0 = 16'sh08A4; // ~0.067455
    localparam signed [15:0] B1 = 16'sh1148; // ~0.134911
    localparam signed [15:0] B2 = 16'sh08A4; // ~0.067455
    localparam signed [15:0] A1 = 16'sh96E8; // -1.142981
    localparam signed [15:0] A2 = 16'sh34B2; //  0.412802

    reg signed [WIDTH-1:0] v_z1, v_z2;
    reg signed [WIDTH-1:0] e_z1, e_z2;

    // Pipeline Registers
    reg signed [31:0] prod_b0, prod_b1, prod_b2;
    reg signed [31:0] prod_a1, prod_a2;
    reg signed [35:0] accum_stage1;
    reg [1:0] pipe_valid;

    always @(posedge clk) begin
        if (!rst_n) begin
            v_z1         <= 16'sd0;
            v_z2         <= 16'sd0;
            e_z1         <= 16'sd0;
            e_z2         <= 16'sd0;
            prod_b0      <= 32'sd0;
            prod_b1      <= 32'sd0;
            prod_b2      <= 32'sd0;
            prod_a1      <= 32'sd0;
            prod_a2      <= 32'sd0;
            accum_stage1 <= 36'sd0;
            env_out      <= 16'sd0;
            valid_out    <= 1'b0;
            pipe_valid   <= 2'b00;
        end else begin
            // Stage 1: Register multiplier products on sample strobe
            if (sample_en) begin
                v_z1    <= v_rect;
                v_z2    <= v_z1;
                prod_b0 <= v_rect * B0;
                prod_b1 <= v_z1 * B1;
                prod_b2 <= v_z2 * B2;
                prod_a1 <= e_z1 * A1;
                prod_a2 <= e_z2 * A2;
                pipe_valid[0] <= 1'b1;
            end else begin
                pipe_valid[0] <= 1'b0;
            end

            // Stage 2: Parallel Accumulation
            if (pipe_valid[0]) begin
                accum_stage1 <= (prod_b0 + prod_b1 + prod_b2) - (prod_a1 + prod_a2);
                pipe_valid[1] <= 1'b1;
            end else begin
                pipe_valid[1] <= 1'b0;
            end

            // Stage 3: Output scaling and recursive state update
            if (pipe_valid[1]) begin
                env_out   <= accum_stage1[30:15];
                e_z1      <= accum_stage1[30:15];
                e_z2      <= e_z1;
                valid_out <= 1'b1;
            end else begin
                valid_out <= 1'b0;
            end
        end
    end

endmodule
