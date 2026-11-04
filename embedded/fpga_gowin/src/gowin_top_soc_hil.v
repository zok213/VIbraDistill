// ============================================================================
// Module Name: gowin_top_soc
// Description: Top-Level Gowin Primer 20K Edge AI SoC Architecture (Pure HIL Mode)
//              End-to-End Autonomous Hardware Pipeline:
//                1. HIL BSRAM Vector Replay Engine (12 kHz sample rate generator)
//                2. 32-Tap Causal Min-Phase FIR Bandpass (280 - 1400 Hz @ 12 kHz)
//                3. Causal Envelope Demodulator (Rectifier + Butterworth IIR LPF)
//                4. Hanning Window (512 points)
//                5. Gowin FFT 512 IP Core + 257-Bin Filter + Magnitude (mag_isqrt)
//                6. 12-Way Systolic Spectral NPU Accelerator (2.60 µs @ 100 MHz)
//                7. Hardware Telemetry & Inference SPI Master to Sonix SN32F407 MCU
// ============================================================================

`timescale 1ns / 1ps

module gowin_top_soc #(
    // 512-Sample Time-Domain Stimulus Hex File for HIL Replay Engine
    // Options in src/test_npu/roms/:
    //   stimulus_cwru_normal.hex, stimulus_cwru_ball.hex, stimulus_cwru_inner.hex, stimulus_cwru_outer.hex
    //   stimulus_pronostia_early_life.hex, stimulus_pronostia_mid_life.hex, stimulus_pronostia_end_of_life.hex
    parameter HIL_VECTOR_FILE   = "src/test_npu/roms/stimulus_cwru_normal.hex",
    parameter WEIGHT_FILE_BANK0 = "src/test_npu/roms/hil/npu_weights_bank0.hex",
    parameter WEIGHT_FILE_BANK1 = "src/test_npu/roms/hil/npu_weights_bank1.hex",
    parameter WEIGHT_FILE_BANK2 = "src/test_npu/roms/hil/npu_weights_bank2.hex",
    parameter WEIGHT_FILE_BANK3 = "src/test_npu/roms/hil/npu_weights_bank3.hex",
    parameter WEIGHT_FILE_BANK4 = "src/test_npu/roms/hil/npu_weights_bank4.hex",
    parameter WEIGHT_FILE_BANK5 = "src/test_npu/roms/hil/npu_weights_bank5.hex"
)(
    input  wire                 clk_27m,          
    input  wire                 rst_n_pin,        
    
    output wire                 mcu_spi_sck,      
    output wire                 mcu_spi_cs_n,     
    output wire                 mcu_spi_mosi,     
    output wire                 mcu_irq_pulse,    
    
    output reg                  led_alive,        
    output reg                  led_infer_busy,   
    output reg                  led_ood_alert     
);

    // =========================================================================
    // 1. Quản lý Clock & Reset
    // =========================================================================
`ifdef SIMULATION
    wire clk_100m = clk_27m;
    wire pll_lock = 1'b1;
`else
    wire clk_100m;
    wire pll_lock = 1'b1; // IP Core Gowin_rPLL không xuất chân lock, ta gán cứng 1'b1
    
    // Gọi IP Core PLL đã được tạo sẵn trong dự án
    Gowin_rPLL u_pll_100m (
        .clkout(clk_100m),
        .reset (~rst_n_pin), // Nút nhấn tích cực mức thấp -> đảo lại cho PLL
        .clkin (clk_27m)
    );
`endif

    wire sys_rst_n = rst_n_pin & pll_lock;

    reg [23:0] heartbeat_cnt;
    always @(posedge clk_100m or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            heartbeat_cnt <= 24'd0;
            led_alive     <= 1'b0;
        end else begin
            heartbeat_cnt <= heartbeat_cnt + 1'b1;
            led_alive     <= heartbeat_cnt[23]; 
        end
    end

    // =========================================================================
    // 2. Khối HIL Vector Replay Engine (12 kHz)
    // =========================================================================
    reg [13:0] sample_div_cnt;
    reg        hil_sample_strobe;
    reg [8:0]  hil_addr; 
    reg signed [15:0] hil_sample_bram [0:511];

    initial begin
        $readmemh(HIL_VECTOR_FILE, hil_sample_bram);
    end

    always @(posedge clk_100m or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            sample_div_cnt    <= 14'd0;
            hil_sample_strobe <= 1'b0;
            hil_addr          <= 9'd0;
        end else begin
            // Chuan hoa theo rPLL 100.286 MHz: 100,285,714 Hz / 12,000 Hz = 8357 chu ky (8356 + 1)
            if (sample_div_cnt >= 14'd8356) begin
                sample_div_cnt    <= 14'd0;
                hil_sample_strobe <= 1'b1;
                hil_addr          <= (hil_addr == 9'd511) ? 9'd0 : (hil_addr + 1'b1);
            end else begin
                sample_div_cnt    <= sample_div_cnt + 1'b1;
                hil_sample_strobe <= 1'b0;
            end
        end
    end

    wire signed [15:0] sample_in     = hil_sample_bram[hil_addr];
    wire               sample_strobe = hil_sample_strobe;

    // =========================================================================
    // 3. Stage 1 DSP: FIR 32-Tap
    // =========================================================================
    wire signed [15:0] fir_out;
    wire               fir_valid;

    fir_minphase_32 #(
        .DATA_WIDTH  (16),
        .COEFF_WIDTH (16),
        .TAPS        (32)
    ) u_fir_legacy (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .sample_en  (sample_strobe),
        .x_in       (sample_in),
        .y_out      (fir_out),
        .valid_out  (fir_valid)
    );

    // =========================================================================
    // 4. Stage 2 DSP: Envelope Demodulator
    // =========================================================================
    wire signed [15:0] env_out;
    wire               env_valid;

    envelope_demodulator #(
        .WIDTH        (16),
        .USE_HIL  (0) 
    ) u_envelope (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .sample_en  (fir_valid),
        .y_filtered (fir_out),
        .env_out    (env_out),
        .valid_out  (env_valid)
    );

    // =========================================================================
    // 5. Stage 2.5 DSP: Cửa sổ Hanning 512
    // =========================================================================
    wire signed [15:0] win_out;
    wire               win_valid;
    wire               win_sop;

    hann_window u_hann_window (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .in_valid   (env_valid),
        .in_data    (env_out),
        .out_valid  (win_valid),
        .out_data   (win_out),
        .out_sop    (win_sop),
        .out_eop    ()
    );

    // =========================================================================
    // 6. Stage 3 DSP: FFT Wrapper
    // =========================================================================
    wire [15:0] mag_data;
    wire [8:0]  mag_bin_idx;
    wire        mag_valid;
    wire        fft_frame_done;

    fft_wrapper u_fft_wrapper (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .in_data    (win_out),
        .in_valid   (win_valid),
        .in_sop     (win_sop),
        .mag_idx    (mag_bin_idx),
        .mag_data   (mag_data),
        .mag_valid  (mag_valid),
        .mag_sop    (),
        .mag_eop    (),
        .err_overrun(),
        .err_timeout(),
        .err_sync   ()
    );

    // Giả lập tín hiệu frame_done để kích hoạt NPU (vì wrapper cũ không xuất ra trực tiếp)
    assign fft_frame_done = mag_valid && (mag_bin_idx == 9'd256);

    // =========================================================================
    // 7. Dual-Port BRAM Lưu Phổ
    // =========================================================================
    reg [15:0] spectrum_bram [0:256];
    wire [8:0]  spi_bram_addr;
    wire [15:0] spi_bram_data;
    assign spi_bram_data = spectrum_bram[spi_bram_addr];

    always @(posedge clk_100m) begin
        if (mag_valid && (mag_bin_idx <= 9'd256)) begin
            spectrum_bram[mag_bin_idx] <= mag_data;
        end
    end

    // =========================================================================
    // 8. Stage 4 NPU: Gowin 12-Way Core
    // =========================================================================
    reg                 npu_start;
    wire                npu_ready;
    wire                npu_done;
    reg                 npu_in_valid;
    reg  [8:0]          npu_in_addr;
    reg  signed [7:0]   npu_in_data;

    wire [1:0]          npu_pred_class;
    wire signed [31:0]  npu_logits;
    wire [15:0]         npu_vacuity_q15;
    wire [15:0]         npu_rul_q15;
    wire                npu_ood_alert;

    npu_12way_core #(
        .WEIGHT_FILE_BANK0 (WEIGHT_FILE_BANK0),
        .WEIGHT_FILE_BANK1 (WEIGHT_FILE_BANK1),
        .WEIGHT_FILE_BANK2 (WEIGHT_FILE_BANK2),
        .WEIGHT_FILE_BANK3 (WEIGHT_FILE_BANK3),
        .WEIGHT_FILE_BANK4 (WEIGHT_FILE_BANK4),
        .WEIGHT_FILE_BANK5 (WEIGHT_FILE_BANK5)
    ) u_npu (
        .clk             (clk_100m),
        .rst_n           (sys_rst_n),
        .start           (npu_start),
        .ready           (npu_ready),
        .done            (npu_done),
        .in_valid        (npu_in_valid),
        .in_addr         (npu_in_addr),
        .in_data         (npu_in_data),
        .predicted_class (npu_pred_class),
        .logits_packed   (npu_logits),
        .vacuity_q15     (npu_vacuity_q15),
        .rul_q15         (npu_rul_q15),
        .ood_alert       (npu_ood_alert)
    );

    // =========================================================================
    // 9. Stage 5 SPI DMA Telemetry
    // =========================================================================
    reg         spi_start_tx;
    wire        spi_tx_busy;

    spi_master_packet #(
        .TOTAL_BYTES (524),
        .NUM_BINS    (257)
    ) u_spi_tx (
        .clk                    (clk_100m),
        .rst_n                  (sys_rst_n),
        .start_tx               (spi_start_tx),
        .npu_pred_class         (npu_pred_class),
        .dirichlet_max_evidence (npu_vacuity_q15[15:8]),
        .hardware_status_flags  (16'h0004), 
        .bram_addr              (spi_bram_addr),
        .bram_data              (spi_bram_data),
        .spi_sck                (mcu_spi_sck),
        .spi_cs_n               (mcu_spi_cs_n),
        .spi_mosi               (mcu_spi_mosi),
        .irq_pulse              (mcu_irq_pulse),
        .tx_busy                (spi_tx_busy)
    );

    // =========================================================================
    // 10. Master Control Sequencer
    // =========================================================================
   localparam SEQ_IDLE   = 3'd0;
    localparam SEQ_LOAD   = 3'd1;
    localparam SEQ_START  = 3'd2;
    localparam SEQ_WAIT   = 3'd3;
    localparam SEQ_TX     = 3'd4;
    localparam SEQ_DELAY  = 3'd5;

    reg [2:0]   seq_state;
    reg [9:0]   load_idx;        // Dùng 10-bit để đếm an toàn đến 257 không bị tràn
    reg [23:0]  timer_cnt;
    reg         new_frame_ready;

    // Các thanh ghi đệm Pipeline cho bộ nạp phổ
    reg [15:0]  load_raw_data;
    reg [8:0]   load_addr_pipe;
    reg         load_valid_pipe;

    always @(posedge clk_100m or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            new_frame_ready <= 1'b0;
        end else if (fft_frame_done) begin
            new_frame_ready <= 1'b1;
        end else if (seq_state == SEQ_LOAD) begin
            new_frame_ready <= 1'b0;
        end
    end

    always @(posedge clk_100m or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            seq_state       <= SEQ_IDLE;
            load_idx        <= 10'd0;
            timer_cnt       <= 24'd0;
            npu_start       <= 1'b0;
            npu_in_valid    <= 1'b0;
            npu_in_addr     <= 9'd0;
            npu_in_data     <= 8'sd0;
            spi_start_tx    <= 1'b0;
            led_infer_busy  <= 1'b0;
            led_ood_alert   <= 1'b0;
            load_raw_data   <= 16'd0;
            load_addr_pipe  <= 9'd0;
            load_valid_pipe <= 1'b0;
        end else begin
            led_infer_busy <= (seq_state != SEQ_IDLE && seq_state != SEQ_DELAY);
            led_ood_alert  <= npu_ood_alert;

            case (seq_state)
                SEQ_IDLE: begin
                    npu_start       <= 1'b0;
                    npu_in_valid    <= 1'b0;
                    spi_start_tx    <= 1'b0;
                    load_idx        <= 10'd0;
                    load_valid_pipe <= 1'b0;
                    timer_cnt       <= timer_cnt + 1'b1;

                    if ((new_frame_ready || timer_cnt >= 24'd10_000_000) && npu_ready && !spi_tx_busy) begin
                        timer_cnt <= 24'd0;
                        seq_state <= SEQ_LOAD;
                    end
                end

                SEQ_LOAD: begin
                    // Tầng 1: Đọc thô từ BRAM vào thanh ghi đệm (chỉ mất ~2.5 ns)
                    if (load_idx <= 10'd256) begin
                        load_raw_data   <= spectrum_bram[load_idx];
                        load_addr_pipe  <= load_idx[8:0];
                        load_valid_pipe <= 1'b1;
                        load_idx        <= load_idx + 1'b1;
                    end else begin
                        load_valid_pipe <= 1'b0;
                    end

                    // Tầng 2: Bão hòa logic từ thanh ghi đệm đưa sang NPU (chỉ mất ~3.5 ns)
                    npu_in_valid <= load_valid_pipe;
                    npu_in_addr  <= load_addr_pipe;
                    npu_in_data  <= (load_raw_data[15:8] != 8'd0) ?
                ((load_raw_data[15:8] > 8'd127) ? 8'sd127 : load_raw_data[15:8]) :
                ((load_raw_data[7:0]  > 8'd127) ? 8'sd127 : load_raw_data[7:0]);

                    // Kết thúc khi toàn bộ 257 bin đã được nạp qua cả 2 tầng
                    if (load_idx > 10'd256 && !load_valid_pipe) begin
                        load_idx  <= 10'd0;
                        seq_state <= SEQ_START;
                    end
                end

                SEQ_START: begin
                    npu_in_valid <= 1'b0;
                    npu_start    <= 1'b1;
                    seq_state    <= SEQ_WAIT;
                end

                SEQ_WAIT: begin
                    npu_start <= 1'b0;
                    if (npu_done) begin
                        if (!spi_tx_busy) begin
                            spi_start_tx <= 1'b1;
                            seq_state    <= SEQ_TX;
                        end else begin
                            seq_state    <= SEQ_DELAY;
                        end
                    end
                end

                SEQ_TX: begin
                    spi_start_tx <= 1'b0;
                    if (spi_tx_busy) begin
                        seq_state <= SEQ_DELAY;
                    end
                end

                SEQ_DELAY: begin
                    if (!spi_tx_busy) begin
                        seq_state <= SEQ_IDLE;
                    end
                end

                default: seq_state <= SEQ_IDLE;
            endcase
        end
    end
endmodule