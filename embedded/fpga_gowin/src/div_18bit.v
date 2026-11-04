// Module chia số nguyên 18-bit nhiều chu kỳ (18 chu kỳ clock)
// Đã sửa:
// 1. Thêm cờ busy: cờ done chỉ kích hoạt đúng 1 chu kỳ khi hoàn tất, triệt tiêu hiện tượng dao động 0/1 khi rảnh.
// 2. Sửa phép trừ đủ 18 bit (qr[35:17] - divisor), tránh cắt xén dữ liệu khi số chia >= 2^17.
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
    reg        busy;

    wire [18:0] sub_diff_19 = qr[35:17] - {1'b0, divisor};
    wire [17:0] sub_diff    = sub_diff_19[17:0];
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count    <= 5'd0;
            busy     <= 1'b0;
            qr       <= 36'd0;
            quotient <= 18'd0;
            done     <= 1'b0;
        end else if (start) begin
            count    <= 5'd18;
            busy     <= 1'b1;
            qr       <= {18'd0, dividend};
            done     <= 1'b0;
        end else if (busy) begin
            if (count > 0) begin
                // Thuật toán dịch bit - trừ (Restoring Division)
                if (qr[35:17] >= divisor) begin
                    qr <= {sub_diff, qr[16:0], 1'b1};
                end else begin
                    qr <= {qr[34:0], 1'b0};
                end
                count <= count - 5'd1;
            end else begin
                // Đã hoàn thành đủ 18 chu kỳ dịch trừ
                quotient <= qr[17:0];
                done     <= 1'b1;
                busy     <= 1'b0;
            end
        end else begin
            done <= 1'b0;
        end
    end
endmodule