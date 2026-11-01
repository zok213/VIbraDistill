// =============================================================================
// fft_wrapper.v - hann_window -> [dem 512 mau] -> FFT_Top (Gowin IP, 512 diem, thuan, thu tu tu nhien)
//                 -> loc 257 bin duong (idx <= 256) -> do lon pho 16 bit khong dau -> NPU
//
// GIAO THUC IP (Gowin IPUG503-1.4E): IP "KEO" du lieu, khong nhan day:
//   - xung `start` (>= 1 chu ky, chi lay mau khi IP ranh) -> vai chu ky sau `sod`=1 (1 chu ky), `ipd`=1 suot pha nhap
//   - trong pha nhap `idx` = chi so mau se duoc nap o suon clk TIEP THEO  => xn phai la ham to hop cua idx
//   - tinh toan (`busy`), roi pha xa: `soud`=1 o bin dau, `opd`=1 suot pha xa, `eoud`=1 o bin cuoi,
//     `idx` = chi so bin hien tai (tu nhien 0..511), xk_re/xk_im di cung chu ky voi opd
//   => can bo dem 512x16 de gom khung tu hann_window roi cho IP doc theo idx.
//
// CAC GIA DINH CAN KIEM VOI IP THAT (xem PROGRESS.md muc Giai doan 3):
//   G1. FFT_Top co them cong sod, ipd, eod, busy (bang 4-1 cua IPUG503); wrapper dung ipd.
//   G2. xn_re duoc IP lay mau o suon clk ma idx=k dang hien (xn_re = bo_dem[idx], doc to hop/khong dem).
//   G3. RS111 voi 512 diem => xk = X[k] / 512 (9 tang radix-2, moi tang dich phai 1 bit), lam tron.
//   Khong ai trong G1-G3 duoc chung minh trong sandbox: tb_fft_wrapper chay duoc voi IP that (doi file trong danh sach vlog),
//   va python/golden_fft_mag.py --check do sai lech xk thuc so voi FFT ly tuong de xac nhan G2, G3.
//
// Do lon pho: mag = floor(sqrt(xk_re^2 + xk_im^2)) cua DAU RA IP (tuc |X[k]|/512 neu G3 dung), 16 bit khong dau.
// =============================================================================
module fft_wrapper #(
    parameter TIMEOUT = 16'd60000          // so chu ky toi da cho IP phan hoi (ipd len / ipd xuong)
)(
    input  wire               clk,
    input  wire               rst_n,       // dong bo, tich cuc thap (IP can rst tich cuc cao -> dao ben trong)
    // ---- tu hann_window (out_valid, out_data, out_sop) ----
    input  wire               in_valid,
    input  wire signed [15:0] in_data,
    input  wire               in_sop,
    // ---- sang NPU: 257 bin duong, 1 bin/chu ky ----
    output wire               mag_valid,
    output wire        [8:0]  mag_idx,     // 0..256
    output wire        [15:0] mag_data,    // so khong dau
    output wire               mag_sop,     // bin 0
    output wire               mag_eop,     // bin 256
    // ---- trang thai loi (dinh den khi reset) ----
    output reg                err_overrun, // nhan mau khi IP con dang doc bo dem
    output reg                err_timeout, // IP khong phan hoi sau start (hoac ipd khong ha)
    output reg                err_sync     // sop/so mau khong dung khung 512
);
    localparam N = 512;

    // ------------------------------------------------------------------ bo dem khung
    reg [15:0] fbuf [0:N-1];
    reg [8:0]  wr_ptr;
    reg        collecting, frame_full;
    reg [1:0]  st;
    localparam S_IDLE = 2'd0, S_WAIT = 2'd1, S_LOAD = 2'd2;

    wire [8:0] wr_addr = in_sop ? 9'd0 : wr_ptr;
    wire       wr_ok   = in_valid && (st == S_IDLE) && (in_sop || collecting);

    always @(posedge clk) if (wr_ok) fbuf[wr_addr] <= in_data;

    always @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= 9'd0; collecting <= 1'b0; frame_full <= 1'b0;
            err_overrun <= 1'b0; err_sync <= 1'b0;
        end else begin
            frame_full <= 1'b0;
            if (in_valid) begin
                if (st != S_IDLE) begin
                    err_overrun <= 1'b1;                       // mau bi bo (bo dem dang duoc IP doc)
                end else if (in_sop || collecting) begin
                    if (in_sop && collecting) err_sync <= 1'b1; // sop giua khung: khung truoc thieu mau
                    if (wr_addr == N-1) begin
                        collecting <= 1'b0; wr_ptr <= 9'd0; frame_full <= 1'b1;
                    end else begin
                        collecting <= 1'b1; wr_ptr <= wr_addr + 9'd1;
                    end
                end else begin
                    err_sync <= 1'b1;                          // mau ngoai khung (chua co sop)
                end
            end
        end
    end

    // ------------------------------------------------------------------ dieu khien start -> IP
    wire        fft_ipd, fft_opd, fft_soud, fft_eoud;
    wire [8:0]  fft_idx;
    wire [15:0] xk_re, xk_im;
    reg         fft_start;
    reg  [15:0] tmo;

    always @(posedge clk) begin
        if (!rst_n) begin
            st <= S_IDLE; fft_start <= 1'b0; tmo <= 16'd0; err_timeout <= 1'b0;
        end else begin
            fft_start <= 1'b0;
            case (st)
                S_IDLE: if (frame_full) begin fft_start <= 1'b1; st <= S_WAIT; tmo <= 16'd0; end
                S_WAIT: begin                                  // cho IP bat dau pha nhap
                    tmo <= tmo + 16'd1;
                    if (fft_ipd) begin st <= S_LOAD; tmo <= 16'd0; end
                    else if (tmo == TIMEOUT) begin err_timeout <= 1'b1; st <= S_IDLE; end
                end
                S_LOAD: begin                                  // IP dang doc bo dem theo idx
                    tmo <= tmo + 16'd1;
                    if (!fft_ipd) st <= S_IDLE;                // ipd ha = nap xong, bo dem duoc giai phong
                    else if (tmo == TIMEOUT) begin err_timeout <= 1'b1; st <= S_IDLE; end
                end
                default: st <= S_IDLE;
            endcase
        end
    end

    // ------------------------------------------------------------------ IP FFT
    wire [15:0] xn_re = fbuf[fft_idx];                         // G2: doc to hop theo idx (xem ghi chu timing trong PROGRESS)

    FFT_Top u_fft (
        .clk   (clk),
        .rst   (~rst_n),
        .start (fft_start),
        .xn_re (xn_re),
        .xn_im (16'h0000),
        .idx   (fft_idx),
        .sod   (),
        .ipd   (fft_ipd),
        .eod   (),
        .busy  (),
        .soud  (fft_soud),
        .opd   (fft_opd),
        .eoud  (fft_eoud),
        .xk_re (xk_re),
        .xk_im (xk_im)
    );

    // ------------------------------------------------------------------ loc 257 bin duong + do lon
    wire keep = fft_opd && (fft_idx <= 9'd256);

    mag_isqrt u_mag (
        .clk(clk), .rst_n(rst_n),
        .in_valid(keep), .in_idx(fft_idx), .in_re(xk_re), .in_im(xk_im),
        .out_valid(mag_valid), .out_idx(mag_idx), .out_mag(mag_data)
    );

    assign mag_sop = mag_valid && (mag_idx == 9'd0);
    assign mag_eop = mag_valid && (mag_idx == 9'd256);
endmodule
