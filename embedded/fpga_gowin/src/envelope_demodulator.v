// ============================================================================
// Module Name: envelope_demodulator
// Description: True Causal Envelope Demodulation Engine
//              Full-Wave Absolute Value Rectifier + 2nd-Order Direct-Form I IIR LPF
// Target:      Gowin GW2A-LV18PG256 (Primer 20K)
// Architecture: 3-Stage Pipelined IIR Architecture with Synchronous Reset
// Cutoff:      Profile 1: Fc = 1,200 Hz @ Fs = 12.0 kHz (Butterworth 2nd-Order)
//              Profile 2: Fc = 400 Hz   @ Fs = 3.2 kHz  (Butterworth 2nd-Order)
// ============================================================================

`timescale 1ns / 1ps

module envelope_demodulator #(
    parameter WIDTH        = 16,
    parameter USE_ADXL345  = 0,  // 1: ADXL345 (Fc=400Hz @ Fs=3.2kHz), 0: HIL (Fc=1200Hz @ Fs=12kHz)
    parameter USE_HIL      = 0   // Backwards compatibility alias for HIL SoC top-level
)(
    input  wire                          clk,        // 50 MHz / 100 MHz System Clock
    input  wire                          rst_n,      // Synchronous Active-Low Reset
    input  wire                          sample_en,  // Sample Strobe (3.2 kHz for ADXL345 or 12.0 kHz for HIL)
    input  wire signed [WIDTH-1:0]       y_filtered, // Bandpass Filtered Sample
    output reg  signed [WIDTH-1:0]       env_out,    // Demodulated Baseband Envelope
    output reg                           valid_out   // Output Valid Strobe
);

    // Step 1: Full-Wave Absolute Value Rectification with Two's Complement -32768 Clamp
    wire signed [WIDTH-1:0] v_rect = (y_filtered == 16'sh8000) ? 16'sh7FFF :
                                     (y_filtered < 0) ? -y_filtered : y_filtered;

    // Fixed-Point Butterworth 2nd-Order LPF Coefficients Scaled in Q3.15 Format
    // Dual-Mode Selection:
    //   Mode 1 (USE_ADXL345 = 1): Fc = 400 Hz  @ Fs = 3,200 Hz (ADXL345 Profile)
    //   Mode 2 (USE_ADXL345 = 0): Fc = 1200 Hz @ Fs = 12,000 Hz (Industrial CWRU / HIL Profile)
    //
    // Note on 18-bit DSP Slices:
    // For Mode 2, a1 = -1.1429805. Scaled by 32768 (Q15), A1 = -37453.
    // Because |a1| > 1.0, A1 exceeds the 16-bit signed range [-32768, 32767].
    // Gowin GW2A-18 MULT18X18 DSP blocks natively support 18-bit signed operands.
    // We use signed [17:0] coefficients to guarantee zero coefficient overflow.
    localparam signed [17:0] B0 = USE_ADXL345 ? 18'sd3199   :  18'sd2210;  // 0.097631 vs 0.067455
    localparam signed [17:0] B1 = USE_ADXL345 ? 18'sd6398   :  18'sd4421;  // 0.195262 vs 0.134911
    localparam signed [17:0] B2 = USE_ADXL345 ? 18'sd3199   :  18'sd2210;  // 0.097631 vs 0.067455
    localparam signed [17:0] A1 = USE_ADXL345 ? -18'sd30894 : -18'sd37453; // -0.942809 vs -1.142981
    localparam signed [17:0] A2 = USE_ADXL345 ?  18'sd10923 :  18'sd13527; //  0.333333 vs  0.412802

    reg signed [WIDTH-1:0] v_z1, v_z2;
    reg signed [WIDTH-1:0] e_z1, e_z2;

    // Pipeline Registers: 16-bit input * 18-bit coefficient = 34-bit product
    reg signed [33:0] prod_b0, prod_b1, prod_b2;
    reg signed [33:0] prod_a1, prod_a2;
    reg signed [35:0] accum_stage1;
    reg [1:0] pipe_valid;

    always @(posedge clk) begin
        if (!rst_n) begin
            v_z1         <= 16'sd0;
            v_z2         <= 16'sd0;
            e_z1         <= 16'sd0;
            e_z2         <= 16'sd0;
            prod_b0      <= 34'sd0;
            prod_b1      <= 34'sd0;
            prod_b2      <= 34'sd0;
            prod_a1      <= 34'sd0;
            prod_a2      <= 34'sd0;
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

            // Stage 3: Output scaling (divide by 2^15 = 32768) and recursive state update with saturation
            if (pipe_valid[1]) begin
                if (accum_stage1 > 36'sd1073709056) begin       // Positive clamp at +32767
                    env_out <= 16'sh7FFF;
                    e_z1    <= 16'sh7FFF;
                end else if (accum_stage1 < -36'sd1073741824) begin // Negative clamp at -32768
                    env_out <= 16'sh8000;
                    e_z1    <= 16'sh8000;
                end else begin
                    env_out <= accum_stage1[30:15];
                    e_z1    <= accum_stage1[30:15];
                end
                e_z2      <= e_z1;
                valid_out <= 1'b1;
            end else begin
                valid_out <= 1'b0;
            end
        end
    end

endmodule
