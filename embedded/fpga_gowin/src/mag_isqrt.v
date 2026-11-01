// =============================================================================
// mag_isqrt.v - Do lon pho  mag = floor( sqrt(re^2 + im^2) ),  pipeline day du, 1 mau/chu ky.
//   re, im : so co dau 16 bit.  re^2+im^2 <= 2^31  =>  mag <= 46341 (vua trong 16 bit KHONG DAU)
//   Tre co dinh = 2 + 16 = 18 chu ky. KHONG co back-pressure (valid di kem du lieu).
//   Can bac hai tung chu so (restoring): chinh xac tuyet doi, khop math.isqrt() cua Python.
// =============================================================================
module mag_isqrt (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               in_valid,
    input  wire        [8:0]  in_idx,
    input  wire signed [15:0] in_re,
    input  wire signed [15:0] in_im,
    output wire               out_valid,
    output wire        [8:0]  out_idx,
    output wire        [15:0] out_mag
);
    // ---- tang 1: binh phuong (2 bo nhan 16x16, ket qua >= 0) ----
    wire signed [31:0] pr = in_re * in_re;
    wire signed [31:0] pi = in_im * in_im;
    reg         v1;  reg [8:0] i1;  reg [31:0] re2, im2;
    // ---- tang 2: cong ----
    reg         v2;  reg [8:0] i2;  reg [31:0] sum;

    always @(posedge clk) begin
        if (!rst_n) begin v1 <= 1'b0; v2 <= 1'b0; end
        else begin v1 <= in_valid; v2 <= v1; end
        i1 <= in_idx;  re2 <= pr[31:0];  im2 <= pi[31:0];
        i2 <= i1;      sum <= re2 + im2;
    end

    // ---- 16 tang lap can bac hai ----
    reg         vs [0:16];
    reg  [8:0]  ix [0:16];
    reg  [31:0] xs [0:16];
    reg  [19:0] rs [0:16];
    reg  [15:0] qs [0:16];

    always @(posedge clk) begin
        if (!rst_n) vs[0] <= 1'b0; else vs[0] <= v2;
        ix[0] <= i2;  xs[0] <= sum;  rs[0] <= 20'd0;  qs[0] <= 16'd0;
    end

    genvar g;
    generate for (g = 0; g < 16; g = g + 1) begin : it
        wire [19:0] rem_n = {rs[g][17:0], xs[g][31:30]};
        wire [19:0] trial = {2'b00, qs[g], 2'b01};
        wire        take  = (rem_n >= trial);
        always @(posedge clk) begin
            if (!rst_n) vs[g+1] <= 1'b0; else vs[g+1] <= vs[g];
            ix[g+1] <= ix[g];
            xs[g+1] <= {xs[g][29:0], 2'b00};
            rs[g+1] <= take ? (rem_n - trial) : rem_n;
            qs[g+1] <= {qs[g][14:0], take};
        end
    end endgenerate

    assign out_valid = vs[16];
    assign out_idx   = ix[16];
    assign out_mag   = qs[16];
endmodule
