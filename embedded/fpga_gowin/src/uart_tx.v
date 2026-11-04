`timescale 1ns / 1ps
// =============================================================================
// Module: uart_tx (UART Transmitter 8N1)
// Ho tro toc do truyen cao: 115200, 460800, 921600, 1000000 baud
// =============================================================================
module uart_tx #(
    parameter CLK_HZ = 100_000_000,
    parameter BAUD   = 921600
) (
    input  wire       clk, 
    input  wire       rst_n,
    input  wire [7:0] data,
    input  wire       valid,
    output wire       ready,
    output reg        txd
);
    localparam integer DIV = (CLK_HZ + BAUD/2) / BAUD;

    reg [15:0] cnt;
    reg [3:0]  bitn;
    reg [9:0]  sh;
    reg        busy;

    assign ready = ~busy;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin 
            txd  <= 1'b1; 
            busy <= 1'b0; 
            cnt  <= 16'd0; 
            bitn <= 4'd0; 
            sh   <= 10'h3FF; 
        end else if (!busy) begin
            if (valid) begin 
                sh   <= {1'b1, data, 1'b0}; 
                busy <= 1'b1; 
                cnt  <= 16'd0; 
                bitn <= 4'd0; 
                txd  <= 1'b0; // Start bit
            end
        end else begin
            if (cnt == DIV - 1) begin
                cnt <= 16'd0;
                if (bitn == 4'd9) begin 
                    busy <= 1'b0; 
                    txd  <= 1'b1; // Stop bit done
                end else begin 
                    bitn <= bitn + 1'b1; 
                    txd  <= sh[bitn + 1'b1]; 
                end
            end else begin
                cnt <= cnt + 1'b1;
            end
        end
    end
endmodule
