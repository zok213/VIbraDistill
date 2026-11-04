`timescale 1ns / 1ps
// =============================================================================
// Module: spectrum_uart_streamer
// Chup 257 bin tu FFT Magnitude va gui len PC qua UART khi co xung frame_done.
//
// Dinh dang goi tin (518 byte):
//   Byte 0..1:   0xAA, 0x55 (Sync Word)
//   Byte 2:      SEQ (So thu tu khung, tang dan tu 0..255)
//   Byte 3..516: 257 bin x 2 byte (Little-Endian: Low Byte truoc, High Byte sau)
//   Byte 517:    CKSUM (XOR cua SEQ va 514 byte du lieu tu Byte 2 den Byte 516)
//
// Toc do truyen:
//   Mac dinh BAUD = 921600 (Truyen 518 byte chi mat 5.6 ms, hoan toan khong
//   bi nghen dong thoi gian thuc so voi chu ky FFT 42.7 ms @ 12 kHz).
// =============================================================================
module spectrum_uart_streamer #(
    parameter CLK_HZ = 100_000_000,
    parameter BAUD   = 921600
) (
    input  wire        clk, 
    input  wire        rst_n,
    input  wire        bram_we,
    input  wire [8:0]  bram_addr,
    input  wire [15:0] bram_data,
    input  wire        frame_done,
    output wire        uart_txd
);
    // Bo dem 257 bin FFT (0..256)
    reg [15:0] mem [0:256];

    localparam S_IDLE  = 3'd0;
    localparam S_FETCH = 3'd1;
    localparam S_LOAD  = 3'd2;
    localparam S_SEND  = 3'd3;
    localparam S_W1    = 3'd4;
    localparam S_W2    = 3'd5;

    reg [2:0]  st;
    reg [9:0]  bi;            // Chi so byte truyen (0..517)
    reg [7:0]  seq, ck;
    reg [8:0]  rd_addr;
    reg [15:0] mem_q;
    wire [9:0] p = bi - 10'd3; // Chi so trong phan payload 514 byte

    // Chong ghi de mem khi UART dang trong qua trinh truyen goi de bao toan Checksum
    always @(posedge clk) begin
        if (bram_we && (bram_addr <= 9'd256) && (st == S_IDLE || st == S_FETCH)) begin
            mem[bram_addr] <= bram_data;
        end
    end

    reg  [7:0] tx_data; 
    reg        tx_valid; 
    wire       tx_ready;

    uart_tx #(
        .CLK_HZ (CLK_HZ), 
        .BAUD   (BAUD)
    ) u_tx (
        .clk    (clk), 
        .rst_n  (rst_n), 
        .data   (tx_data), 
        .valid  (tx_valid), 
        .ready  (tx_ready), 
        .txd    (uart_txd)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st       <= S_IDLE; 
            bi       <= 10'd0; 
            seq      <= 8'd0; 
            ck       <= 8'd0; 
            tx_valid <= 1'b0; 
            tx_data  <= 8'd0; 
            rd_addr  <= 9'd0; 
            mem_q    <= 16'd0;
        end else begin
            tx_valid <= 1'b0;
            case (st)
                S_IDLE: begin
                    if (frame_done) begin 
                        bi <= 10'd0; 
                        ck <= 8'd0; 
                        st <= S_FETCH; 
                    end
                end

                S_FETCH: begin 
                    rd_addr <= (bi >= 10'd3 && bi <= 10'd516) ? p[9:1] : 9'd0; 
                    st      <= S_LOAD; 
                end

                S_LOAD: begin 
                    mem_q <= mem[rd_addr]; 
                    st    <= S_SEND; 
                end

                S_SEND: begin
                    if (tx_ready) begin
                        tx_valid <= 1'b1;
                        if (bi == 10'd0) begin
                            tx_data <= 8'hAA;
                        end else if (bi == 10'd1) begin
                            tx_data <= 8'h55;
                        end else if (bi == 10'd2) begin
                            tx_data <= seq; 
                            ck      <= ck ^ seq;
                        end else if (bi == 10'd517) begin
                            tx_data <= ck; // Byte checksum cuoi cung
                        end else begin
                            tx_data <= p[0] ? mem_q[15:8] : mem_q[7:0];
                            ck      <= ck ^ (p[0] ? mem_q[15:8] : mem_q[7:0]);
                        end
                        st <= S_W1;
                    end
                end

                S_W1: begin
                    st <= S_W2;
                end

                S_W2: begin
                    if (tx_ready) begin
                        if (bi == 10'd517) begin 
                            seq <= seq + 1'b1; 
                            st  <= S_IDLE; 
                        end else begin 
                            bi <= bi + 10'd1; 
                            st <= S_FETCH; 
                        end
                    end
                end

                default: st <= S_IDLE;
            endcase
        end
    end
endmodule
