// ============================================================================
// Module : spec_normalizer
// Purpose: Peak-normalise a 257-bin, 16-bit FFT magnitude spectrum to INT8
//          range [0..127], bit-true to the agreed golden formula:
//
//              out[k] = min(127, (mag[k]*127 + (Max>>1)) / Max)
//              Max    = max(mag[0..256])        (bin 0 / DC included)
//
// Method : * Max is tracked on the fly while the FFT streams into BRAM.
//          * Each bin is divided with an EXACT 7-iteration shift-subtract
//            divider. Because mag[k] <= Max, the quotient is always <= 127,
//            so 7 quotient bits are sufficient -> no reciprocal, no Q-format
//            truncation, no DSP block, result identical to integer division.
//          * x*127 is computed as (x<<7) - x  (no multiplier).
//
// Timing : 11 clocks / bin  -> 257*11 + ~6  ~= 2.83k clocks (~28 us @100 MHz)
//          (WR_SETTLE and RD_LAT add a few clocks.)
//
// Notes  : * Rounding is round-half-up. numpy.round() is round-half-to-even,
//            so they differ only on exact .5 ties (possible only for even Max).
//          * Max == 0 (dead sensor) -> divisor forced to 1, all outputs 0.
//          * Max < 127 is NOT clamped: output is amplified exactly like the
//            Python reference (mag*127/Max).
//          * Synchronous active-low reset, no latches, no multiplier.
// ============================================================================
`timescale 1ns / 1ps

module spec_normalizer #(
    parameter integer RD_LAT    = 1,   // BRAM read latency in clocks (1 = sync read,
                                       // 2 = sync read + output register enabled)
    parameter integer WR_SETTLE = 2    // clocks to wait after fft_eop so that the last
                                       // bin is guaranteed to be written to the BRAM
)(
    input  wire              clk,
    input  wire              rst_n,          // synchronous, active low

    // ---- Live FFT magnitude stream (monitored for Max) --------------------
    input  wire              fft_valid,      // bin strobe
    input  wire              fft_sop,        // first bin of frame (bin 0)
    input  wire              fft_eop,        // last bin of frame (bin 256), with fft_valid
    input  wire [15:0]       fft_mag,        // unsigned magnitude

    // ---- Spectrum BRAM read port ------------------------------------------
    output reg  [8:0]        bram_rd_addr,   // 0..256
    input  wire [15:0]       bram_rd_data,   // valid RD_LAT clocks after addr is presented

    // ---- Normalised stream to NPU -----------------------------------------
    output reg               npu_valid,
    output reg  [8:0]        npu_addr,
    output reg  signed [7:0] npu_data,       // 0..127
    output reg               npu_start_pulse,// 1 clock, one clock after the last bin
    output wire              busy
);

    // ------------------------------------------------------------------------
    // 1. On-the-fly peak tracking (bin 0 included)
    // ------------------------------------------------------------------------
    reg [15:0] max_reg;

    always @(posedge clk) begin
        if (!rst_n) begin
            max_reg <= 16'd0;
        end else if (fft_valid) begin
            if (fft_sop)
                max_reg <= fft_mag;
            else if (fft_mag > max_reg)
                max_reg <= fft_mag;
        end
    end

    // ------------------------------------------------------------------------
    // 2. FSM: read bin -> exact 7-step divide -> emit
    // ------------------------------------------------------------------------
    localparam [3:0] S_IDLE   = 4'd0,
                     S_SETTLE = 4'd1,
                     S_LATCH  = 4'd2,
                     S_ADDR   = 4'd3,
                     S_WAIT   = 4'd4,
                     S_LOAD   = 4'd5,
                     S_DIV    = 4'd6,
                     S_OUT    = 4'd7,
                     S_TRIG   = 4'd8;

    localparam [3:0] WS = WR_SETTLE;
    localparam [3:0] RL = RD_LAT;

    reg  [3:0]  state;
    reg  [3:0]  wcnt;          // settle / BRAM-latency counter
    reg  [8:0]  idx;           // current bin
    reg  [15:0] divisor;       // Max latched for this frame (>=1)
    reg  [22:0] rem;           // running remainder (numerator < 128*divisor < 2^23)
    reg  [22:0] dsh;           // divisor << step
    reg  [6:0]  quo;           // quotient bits
    reg  [2:0]  step;          // 6..0
    reg         ovf;           // numerator >= 128*divisor (cannot happen if x<=Max)

    assign busy = (state != S_IDLE);

    // numerator = x*127 + (Max>>1),  x*127 = (x<<7) - x
    wire [22:0] x127   = {bram_rd_data, 7'd0} - {7'd0, bram_rd_data};
    wire [22:0] numer  = x127 + {7'd0, divisor[15:1]};
    wire [22:0] dmax   = {divisor, 7'd0};            // 128 * divisor

    always @(posedge clk) begin
        if (!rst_n) begin
            state           <= S_IDLE;
            wcnt            <= 4'd0;
            idx             <= 9'd0;
            divisor         <= 16'd1;
            rem             <= 23'd0;
            dsh             <= 23'd0;
            quo             <= 7'd0;
            step            <= 3'd0;
            ovf             <= 1'b0;
            bram_rd_addr    <= 9'd0;
            npu_valid       <= 1'b0;
            npu_addr        <= 9'd0;
            npu_data        <= 8'sd0;
            npu_start_pulse <= 1'b0;
        end else begin
            // defaults (strobes)
            npu_valid       <= 1'b0;
            npu_start_pulse <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (fft_valid && fft_eop) begin
                        wcnt  <= 4'd0;
                        state <= S_SETTLE;
                    end
                end

                // wait so BRAM holds the final bin; max_reg already includes bin 256
                S_SETTLE: begin
                    if (wcnt >= WS) state <= S_LATCH;
                    else                        wcnt  <= wcnt + 4'd1;
                end

                S_LATCH: begin
                    divisor <= (max_reg == 16'd0) ? 16'd1 : max_reg;
                    idx     <= 9'd0;
                    state   <= S_ADDR;
                end

                S_ADDR: begin
                    bram_rd_addr <= idx;
                    wcnt         <= 4'd1;
                    state        <= S_WAIT;
                end

                S_WAIT: begin
                    if (wcnt >= RL) state <= S_LOAD;
                    else                     wcnt  <= wcnt + 4'd1;
                end

                S_LOAD: begin
                    rem   <= numer;
                    ovf   <= (numer >= dmax);
                    dsh   <= {1'b0, divisor, 6'd0};   // divisor << 6
                    quo   <= 7'd0;
                    step  <= 3'd6;
                    state <= S_DIV;
                end

                S_DIV: begin
                    if (rem >= dsh) begin
                        rem       <= rem - dsh;
                        quo[step] <= 1'b1;
                    end
                    dsh <= {1'b0, dsh[22:1]};
                    if (step == 3'd0) state <= S_OUT;
                    else              step  <= step - 3'd1;
                end

                S_OUT: begin
                    npu_valid <= 1'b1;
                    npu_addr  <= idx;
                    npu_data  <= ovf ? 8'sd127 : {1'b0, quo};
                    if (idx == 9'd256) begin
                        state <= S_TRIG;
                    end else begin
                        idx   <= idx + 9'd1;
                        state <= S_ADDR;
                    end
                end

                S_TRIG: begin
                    npu_start_pulse <= 1'b1;
                    state           <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
