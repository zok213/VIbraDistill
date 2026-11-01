// Module chia số nguyên 18-bit nhiều chu kỳ (18 chu kỳ clock)
module div_18bit (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [17:0] dividend, // Số bị chia (tử số)
    input  wire [17:0] divisor,  // Số chia (mẫu số)
    output reg  [17:0] quotient, // Thương số
    output reg         done
);
    reg [4:0]  count;
    reg [35:0] qr;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 0;
            qr <= 0;
            quotient <= 0;
            done <= 0;
        end else if (start) begin
            count <= 18;
            qr <= {18'd0, dividend};
            done <= 0;
        end else if (count > 0) begin
            // Thuật toán dịch bit - trừ (Restoring Division)
            if (qr[34:17] >= divisor) begin
                qr <= {qr[33:17] - divisor[16:0], qr[16:0], 1'b1};
            end else begin
                qr <= {qr[33:0], 1'b0};
            end
            count <= count - 5'd1;
        end else if (count == 0 && !done) begin
            quotient <= qr[17:0];
            done <= 1;
        end else begin
            done <= 0;
        end
    end
endmodule