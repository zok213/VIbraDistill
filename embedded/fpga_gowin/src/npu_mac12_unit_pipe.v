// ============================================================================
// npu_mac12_unit_pipe - BAN SUA TIMING cua npu_mac12_unit.v (Tai). Cung cong, KHAC DO TRE.
//
// Van de (bao cao timing, duong tre nhat, slack ~ -5 ns, Fmax 66.7 MHz):
//   BSRAM.DO (clk->out 2.26ns) -> net (2.56ns, fanout 18) -> DSP nhan (3.64ns, KHONG thanh ghi)
//   -> net (2.86ns) -> bo cong 32 bit (chuoi carry) -> accum.D      ==> ~15 ns trong 1 chu ky 10 ns
//
// Cach sua: chia thanh 3 tang, moi chu ky chi lam 1 viec.
//   Tang A: chot (act_in, weights_in, mac_en, acc_clear)        -> cat phan BSRAM+dây
//   Tang B: prod[i] <= act_q * w_q[i]    (tich 8x8 -> 16 bit)    -> phep nhan co thanh ghi ngo ra
//   Tang C: accum[i] <= accum[i] + prod[i]                       -> chi con bo cong
// HE QUA QUAN TRONG: ket qua accum tre them 2 CHU KY so voi ban goc.
//   Ban goc : mac_en cuoi cung o chu ky k  -> accum dung sau canh clock k
//   Ban nay : mac_en cuoi cung o chu ky k  -> accum dung sau canh clock k+2
//   => bo dieu khien (npu_12way_core) phai cho them 2 chu ky truoc requant_en / doc accum_all_out.
// Phan requantizer (tu "selected_acc" tro xuong) giu NGUYEN VAN cua Tai.
// Du lieu (act_q, w_q, prod) co y KHONG reset: giup suy luan DSP/thanh ghi va giam fanout reset.
// ============================================================================
`timescale 1ns / 1ps

module npu_mac12_unit_pipe (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 mac_en,
    input  wire                 acc_clear,
    input  wire signed [7:0]    act_in,
    input  wire signed [95:0]   weights_in,
    input  wire signed [31:0]   bias_in,
    input  wire [31:0]          requant_mult,
    input  wire [5:0]           requant_shift,
    input  wire                 relu_en,
    input  wire                 requant_en,
    input  wire [3:0]           channel_sel,
    output reg  signed [7:0]    act_out,
    output reg                  act_valid,
    output wire signed [383:0]  accum_all_out
);
    // ---------------- Tang A: chot dau vao ----------------
    reg signed [7:0]  act_q;
    reg signed [95:0] w_q;
    reg               mac_en_q, acc_clear_q;

    always @(posedge clk) begin
        act_q <= act_in;
        w_q   <= weights_in;
        if (!rst_n) begin
            mac_en_q <= 1'b0; acc_clear_q <= 1'b0;
        end else begin
            mac_en_q <= mac_en; acc_clear_q <= acc_clear;
        end
    end

    wire signed [7:0] w [0:11];
    genvar g;
    generate
        for (g = 0; g < 12; g = g + 1) begin : GEN_WEIGHTS
            assign w[g] = w_q[(g*8) +: 8];
        end
    endgenerate

    // ---------------- Tang B: nhan ----------------
    reg signed [15:0] prod [0:11];
    reg               mac_en_qq, acc_clear_qq;
    integer j;

    always @(posedge clk) begin
        for (j = 0; j < 12; j = j + 1)
            prod[j] <= act_q * w[j];
        if (!rst_n) begin
            mac_en_qq <= 1'b0; acc_clear_qq <= 1'b0;
        end else begin
            mac_en_qq <= mac_en_q; acc_clear_qq <= acc_clear_q;
        end
    end

    // ---------------- Tang C: cong don ----------------
    reg signed [31:0] accum [0:11];
    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < 12; i = i + 1) accum[i] <= 32'sd0;
        end else begin
            for (i = 0; i < 12; i = i + 1) begin
                if (acc_clear_qq) begin
                    accum[i] <= (mac_en_qq) ? prod[i] : 32'sd0;
                end else if (mac_en_qq) begin
                    accum[i] <= accum[i] + prod[i];
                end
            end
        end
    end

    assign accum_all_out = {
        accum[11], accum[10], accum[9], accum[8],
        accum[7],  accum[6],  accum[5], accum[4],
        accum[3],  accum[2],  accum[1], accum[0]
    };

    // =====================================================================
    // Tu day tro xuong: GIU NGUYEN cua Tai (requantizer 2 tang)
    // =====================================================================
    wire signed [31:0] selected_acc = accum[channel_sel] + bias_in;

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

    wire signed [63:0] round_offset = (pipe1_shift > 0) ? (64'sd1 <<< (pipe1_shift - 1)) : 64'sd0;
    wire signed [63:0] rounded_val  = pipe1_scaled_prod + round_offset;
    wire signed [63:0] shifted_val  = rounded_val >>> pipe1_shift;

    always @(posedge clk) begin
        if (!rst_n) begin
            act_out   <= 8'sd0;
            act_valid <= 1'b0;
        end else if (pipe1_valid) begin : CLAMP_LOGIC
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
