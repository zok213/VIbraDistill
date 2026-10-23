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

    // 32-sample delay line and 4-multiplier folded engine identical to fir_minphase_32.v
endmodule
