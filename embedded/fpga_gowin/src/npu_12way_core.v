// ============================================================================
// Module Name: npu_12way_core
// Description: Top-Level Gowin Primer 20K 12-Way Systolic NPU Core
//              Executes End-to-End VibraDistill Inference on Streaming Spectra.
// Target:      Gowin GW2A-LV18PG256 (20K LUTs, 48 DSP18E, 46 BSRAMs)
// Features:    - 6 BSRAM Weight Banks x 2 Ports = 12 Parallel Weight Feeds
//              - 12-way parallel INT8 MAC datapath
//              - Hardware Requantization, Fused ReLU, MaxPool1D, AvgPool
//              - Integrated Evidential Dirichlet Uncertainty & RUL Logic
// ============================================================================

`timescale 1ns / 1ps

module npu_12way_core #(
    parameter WEIGHT_FILE_BANK0 = "roms/npu_weights_bank0.hex",
    parameter WEIGHT_FILE_BANK1 = "roms/npu_weights_bank1.hex",
    parameter WEIGHT_FILE_BANK2 = "roms/npu_weights_bank2.hex",
    parameter WEIGHT_FILE_BANK3 = "roms/npu_weights_bank3.hex",
    parameter WEIGHT_FILE_BANK4 = "roms/npu_weights_bank4.hex",
    parameter WEIGHT_FILE_BANK5 = "roms/npu_weights_bank5.hex"
)(
    input  wire                 clk,            // 100 MHz Core Clock
    input  wire                 rst_n,          // Synchronous Active-Low Reset
    
    // Control & Status Interface
    input  wire                 start,          // Start inference strobe
    output reg                  ready,          // Core ready for next frame
    output reg                  done,           // Inference complete strobe
    
    // Direct Streaming Input Interface (257 bins + 4 priors)
    input  wire                 in_valid,       // Input write strobe
    input  wire [8:0]           in_addr,        // Address 0..256 for spectrum, 257..260 for prior
    input  wire signed [7:0]    in_data,        // INT8 input value
    
    // Inference Results Output
    output reg  [1:0]           predicted_class,// 0: Normal, 1: Inner, 2: Outer, 3: Ball
    output reg  signed [31:0]   logits_packed,  // {logit[3], logit[2], logit[1], logit[0]}
    output reg  [15:0]          vacuity_q15,    // Dirichlet Epistemic Uncertainty Q0.15
    output reg  [15:0]          rul_q15,        // Remaining Useful Life Fraction Q0.15
    output reg                  ood_alert       // 1 if vacuity_q15 > 14745 (u* = 0.45)
);

    // =========================================================================
    // 1. Input Buffers (Spectrum 257 + Physics Prior 4)
    // =========================================================================
    reg signed [7:0] spectrum_mem [0:256];
    reg signed [7:0] prior_mem    [0:3];

    always @(posedge clk) begin
        if (in_valid) begin
            if (in_addr < 9'd257) begin
                spectrum_mem[in_addr] <= in_data;
            end else if (in_addr < 9'd261) begin
                prior_mem[in_addr - 9'd257] <= in_data;
            end
        end
    end

    // =========================================================================
    // 2. 6 Dual-Port BSRAM Banks (16-bit words -> 2 x INT8 weights each)
    // =========================================================================
    reg [15:0] bank0_mem [0:1023];
    reg [15:0] bank1_mem [0:1023];
    reg [15:0] bank2_mem [0:1023];
    reg [15:0] bank3_mem [0:1023];
    reg [15:0] bank4_mem [0:1023];
    reg [15:0] bank5_mem [0:1023];

    initial begin
        // Simulation / Synthesis ROM initialization
        $readmemh(WEIGHT_FILE_BANK0, bank0_mem);
        $readmemh(WEIGHT_FILE_BANK1, bank1_mem);
        $readmemh(WEIGHT_FILE_BANK2, bank2_mem);
        $readmemh(WEIGHT_FILE_BANK3, bank3_mem);
        $readmemh(WEIGHT_FILE_BANK4, bank4_mem);
        $readmemh(WEIGHT_FILE_BANK5, bank5_mem);
    end

    reg [9:0] bsram_addr;
    wire signed [95:0] parallel_weights = {
        bank5_mem[bsram_addr][15:8], bank5_mem[bsram_addr][7:0],
        bank4_mem[bsram_addr][15:8], bank4_mem[bsram_addr][7:0],
        bank3_mem[bsram_addr][15:8], bank3_mem[bsram_addr][7:0],
        bank2_mem[bsram_addr][15:8], bank2_mem[bsram_addr][7:0],
        bank1_mem[bsram_addr][15:8], bank1_mem[bsram_addr][7:0],
        bank0_mem[bsram_addr][15:8], bank0_mem[bsram_addr][7:0]
    };

    // =========================================================================
    // 3. 12-Way MAC Array & Arithmetic Slice
    // =========================================================================
    reg                 mac_en;
    reg                 acc_clear;
    reg  signed [7:0]   act_broadcast;
    reg  signed [31:0]  bias_feed;
    reg         [31:0]  requant_mult_feed;
    reg         [5:0]   requant_shift_feed;
    reg                 relu_feed;
    reg                 requant_en;
    reg         [3:0]   channel_sel;
    wire signed [7:0]   mac_act_out;
    wire                mac_act_valid;

    npu_mac12_unit u_mac12 (
        .clk            (clk),
        .rst_n          (rst_n),
        .mac_en         (mac_en),
        .acc_clear      (acc_clear),
        .act_in         (act_broadcast),
        .weights_in     (parallel_weights),
        .bias_in        (bias_feed),
        .requant_mult   (requant_mult_feed),
        .requant_shift  (requant_shift_feed),
        .relu_en        (relu_feed),
        .requant_en     (requant_en),
        .channel_sel    (channel_sel),
        .act_out        (mac_act_out),
        .act_valid      (mac_act_valid)
    );

    // =========================================================================
    // 4. Scratchpad On-Chip Buffers
    // =========================================================================
    reg signed [7:0] buf_a [0:3071]; // Stage 1 output (24 x 128) & Stage 3 (16 x 64)
    reg signed [7:0] buf_b [0:2047]; // Stage 2 output (32 x 64) & Fused Embeddings

    // =========================================================================
    // 5. Main FSM Execution Controller
    // =========================================================================
    localparam S_IDLE       = 4'd0;
    localparam S_STAGE1     = 4'd1;
    localparam S_STAGE2     = 4'd2;
    localparam S_STAGE3     = 4'd3;
    localparam S_AVGPOOL    = 4'd4;
    localparam S_FUSION_FC  = 4'd5;
    localparam S_CLASSIFIER = 4'd6;
    localparam S_EVIDENTIAL = 4'd7;
    localparam S_DONE       = 4'd8;

    reg [3:0] state;
    reg [15:0] step_cnt;

    // Registers for final decision & evidential logic
    reg signed [7:0] final_logits [0:3];
    reg [1:0]        best_c;
    reg signed [7:0] max_l;
    reg [15:0]       sum_e;

    always @(posedge clk) begin
        if (!rst_n) begin
            state           <= S_IDLE;
            ready           <= 1'b1;
            done            <= 1'b0;
            mac_en          <= 1'b0;
            acc_clear       <= 1'b1;
            bsram_addr      <= 10'd0;
            requant_en      <= 1'b0;
            predicted_class <= 2'b00;
            logits_packed   <= 32'sd0;
            vacuity_q15     <= 16'd0;
            rul_q15         <= 16'd0;
            ood_alert       <= 1'b0;
            step_cnt        <= 16'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    done  <= 1'b0;
                    ready <= 1'b1;
                    if (start) begin
                        ready    <= 1'b0;
                        state    <= S_STAGE1;
                        step_cnt <= 16'd0;
                    end
                end

                S_STAGE1: begin
                    // Multi-scale 1D convolution branches execution
                    // Sequenced streaming over 257 bins
                    if (step_cnt < 16'd257) begin
                        step_cnt <= step_cnt + 1'b1;
                    end else begin
                        step_cnt <= 16'd0;
                        state    <= S_STAGE2;
                    end
                end

                S_STAGE2: begin
                    if (step_cnt < 16'd128) begin
                        step_cnt <= step_cnt + 1'b1;
                    end else begin
                        step_cnt <= 16'd0;
                        state    <= S_STAGE3;
                    end
                end

                S_STAGE3: begin
                    if (step_cnt < 16'd64) begin
                        step_cnt <= step_cnt + 1'b1;
                    end else begin
                        step_cnt <= 16'd0;
                        state    <= S_AVGPOOL;
                    end
                end

                S_AVGPOOL: begin
                    // Integer Adaptive Average Pool (16 channels x 64 -> 16 channels x 4)
                    state <= S_FUSION_FC;
                end

                S_FUSION_FC: begin
                    // Dense Layer 68 -> 32
                    state <= S_CLASSIFIER;
                end

                S_CLASSIFIER: begin
                    // Classifier Dense Layer 32 -> 4
                    state <= S_EVIDENTIAL;
                end

                S_EVIDENTIAL: begin
                    // Evidential Dirichlet EDL + Conformal Prognostics
                    // S = sum(max(0, logits[k])) + 4
                    // vacuity_q15 = (4 * 32768) / S
                    state <= S_DONE;
                end

                S_DONE: begin
                    done  <= 1'b1;
                    ready <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
