// =============================================================================
// hann_window.v - Nhan tung mau voi cua so Hanning 512 diem (he so Q1.15).
//   out[n] = ( in[n] * w[idx] ) >>> 15,    idx = 0..511 quay vong (khung 512 mau KHONG chong lan)
// Pipeline 2 tang (de de dat timing 100 MHz):
//   tang 1: tra ROM he so + chot mau;   tang 2: nhan va dich.
// out_sop = mau dau khung (idx=0), out_eop = mau cuoi khung (idx=511) - de noi voi IP FFT.
// ROM he so nam trong hann512_rom.vh (tu sinh bang python/golden_env_win.py).
// =============================================================================
module hann_window (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               in_valid,
    input  wire signed [15:0] in_data,
    output reg                out_valid,
    output reg  signed [15:0] out_data,
    output reg                out_sop,
    output reg                out_eop
);
    `include "hann512_rom.vh"

    reg [8:0]          idx;
    reg                v1, sop1, eop1;
    reg signed [15:0]  d_reg, w_reg;

    wire signed [31:0] prod = d_reg * w_reg;     // w_reg >= 0 (MSB=0), nen dinh |prod| < 2^30

    always @(posedge clk) begin
        if (!rst_n) begin
            idx <= 9'd0; v1 <= 1'b0; sop1 <= 1'b0; eop1 <= 1'b0;
            d_reg <= 16'sd0; w_reg <= 16'sd0;
            out_valid <= 1'b0; out_data <= 16'sd0; out_sop <= 1'b0; out_eop <= 1'b0;
        end else begin
            // ---- tang 1 ----
            v1 <= in_valid;
            if (in_valid) begin
                d_reg <= in_data;
                w_reg <= hann_w(idx);
                sop1  <= (idx == 9'd0);
                eop1  <= (idx == 9'd511);
                idx   <= idx + 9'd1;             // 9 bit: 511 -> 0 tu dong
            end
            // ---- tang 2 ----
            out_valid <= v1;
            out_sop   <= v1 & sop1;
            out_eop   <= v1 & eop1;
            if (v1) out_data <= prod[30:15];
        end
    end
endmodule
