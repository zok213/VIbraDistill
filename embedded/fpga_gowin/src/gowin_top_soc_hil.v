
`timescale 1ns / 1ps

module gowin_top_soc #(
    // File song rung tho 16-bit (stimulus_cwru_normal, inner, outer, ball)
    parameter STIMULUS_FILE     = "src/test_npu/roms/hil/stimulus_pronostia_early_life.hex",
    parameter SAMPLE_DIV        = 8357,   // 100 MHz / 12 kHz
    // 6 Bank trong so NPU cho che do HIL 12 kHz
    parameter WEIGHT_FILE_BANK0 = "src/test_npu/roms/hil/npu_weights_bank0.hex",
    parameter WEIGHT_FILE_BANK1 = "src/test_npu/roms/hil/npu_weights_bank1.hex",
    parameter WEIGHT_FILE_BANK2 = "src/test_npu/roms/hil/npu_weights_bank2.hex",
    parameter WEIGHT_FILE_BANK3 = "src/test_npu/roms/hil/npu_weights_bank3.hex",
    parameter WEIGHT_FILE_BANK4 = "src/test_npu/roms/hil/npu_weights_bank4.hex",
    parameter WEIGHT_FILE_BANK5 = "src/test_npu/roms/hil/npu_weights_bank5.hex",
    // 4 Bias chuan cua mang NPU o che do HIL
    parameter signed [31:0] BIAS_0 = -32'sd5,
    parameter signed [31:0] BIAS_1 = -32'sd3,
    parameter signed [31:0] BIAS_2 =  32'sd14,
    parameter signed [31:0] BIAS_3 = -32'sd6
)(
    input  wire                 clk_27m,          
    input  wire                 rst_n_pin,        
    
    // Giao tiep SPI Telemetry sang Sonix SN32F407
    output wire                 mcu_spi_sck,      
    output wire                 mcu_spi_cs_n,     
    output wire                 mcu_spi_mosi,     
    output wire                 mcu_irq_pulse,    
    
    // Xuat pho truc tiep len PC qua UART (Tang Primer 20K pin M11)
    output wire                 uart_txd,
    
    // Den bao trang thai
    output reg                  led_alive,        
    output reg                  led_infer_busy,   
    output reg                  led_ood_alert     
);

    // =========================================================================
    // 1. Quan ly Clock & Reset (27 MHz -> 100 MHz)
    // =========================================================================
`ifdef SIMULATION
    wire clk_100m = clk_27m;
    wire pll_lock = 1'b1;
`else
    wire clk_100m;
    wire pll_lock;
    
    Gowin_rPLL u_pll_100m (
        .clkout (clk_100m),
        .lock   (pll_lock),
        .reset  (~rst_n_pin),
        .clkin  (clk_27m)
    );
`endif

    // Reset dong bo hoa theo xung nhip 100MHz (Async assert, Sync deassert)
    reg [1:0] rst_sync;
    always @(posedge clk_100m or negedge pll_lock or negedge rst_n_pin) begin
        if (!rst_n_pin || !pll_lock)
            rst_sync <= 2'b00;
        else
            rst_sync <= {rst_sync[0], 1'b1};
    end
    wire sys_rst_n = rst_sync[1];

    // Mach dem tao xung nhip tim led_alive (~3 Hz)
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
    // 2. Khoi HIL Vector Replay Engine (12 kHz)
    // =========================================================================
    reg signed [15:0] stim_bram [0:511];
    initial $readmemh(STIMULUS_FILE, stim_bram);

    reg [13:0]        stim_div_cnt;
    reg [8:0]         stim_addr; 
    reg signed [15:0] sample_in;
    reg               sample_strobe;

    always @(posedge clk_100m or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            stim_div_cnt  <= 14'd0;
            stim_addr     <= 9'd0;
            sample_in     <= 16'sd0;
            sample_strobe <= 1'b0;
        end else begin
            sample_strobe <= 1'b0;
            if (stim_div_cnt >= (SAMPLE_DIV - 1)) begin
                stim_div_cnt  <= 14'd0;
                sample_in     <= stim_bram[stim_addr];
                stim_addr     <= (stim_addr == 9'd511) ? 9'd0 : (stim_addr + 1'b1);
                sample_strobe <= 1'b1;
            end else begin
                stim_div_cnt <= stim_div_cnt + 1'b1;
            end
        end
    end

    // =========================================================================
    // 3. Stage 1 DSP: 32-Tap Causal Min-Phase FIR
    // =========================================================================
    wire signed [15:0] fir_out;
    wire               fir_valid;

    fir_minphase_32 #(
        .DATA_WIDTH  (16),
        .COEFF_WIDTH (16),
        .TAPS        (32)
    ) u_fir (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .sample_en  (sample_strobe),
        .x_in       (sample_in),
        .y_out      (fir_out),
        .valid_out  (fir_valid)
    );

    // =========================================================================
    // 4. Stage 2 DSP: Causal Envelope Demodulator (USE_HIL = 1 cho Fc = 1200 Hz)
    // =========================================================================
    wire signed [15:0] env_out;
    wire               env_valid;

    envelope_demodulator #(
        .WIDTH   (16),
        .USE_HIL (1) // USE_HIL = 1 cho HIL Profile (Fc = 1200 Hz, DC Gain = 1.0)
    ) u_envelope (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .sample_en  (fir_valid),
        .y_filtered (fir_out),
        .env_out    (env_out),
        .valid_out  (env_valid)
    );

    // =========================================================================
    // 5. Stage 2.5 DSP: Cua so Hanning 512 diem
    // =========================================================================
    wire signed [15:0] win_data;
    wire               win_valid, win_sop, win_eop;

    hann_window u_hann (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .in_valid   (env_valid),
        .in_data    (env_out),
        .out_valid  (win_valid),
        .out_data   (win_data),
        .out_sop    (win_sop),
        .out_eop    (win_eop)
    );

    // =========================================================================
    // 6. Stage 3 DSP: FFT Wrapper & Trinh trich xuat bien do
    // =========================================================================
    wire        mag_valid, mag_sop, mag_eop;
    wire [8:0]  mag_idx;
    wire [15:0] mag_data;
    wire        err_overrun, err_timeout, err_sync;

    fft_wrapper u_fft (
        .clk         (clk_100m),
        .rst_n       (sys_rst_n),
        .in_valid    (win_valid),
        .in_data     (win_data),
        .in_sop      (win_sop),
        .mag_valid   (mag_valid),
        .mag_idx     (mag_idx),
        .mag_data    (mag_data),
        .mag_sop     (mag_sop),
        .mag_eop     (mag_eop),
        .err_overrun (err_overrun),
        .err_timeout (err_timeout),
        .err_sync    (err_sync)
    );

    // =========================================================================
    // 7. Spectrum BRAM (257 x 16-bit) phuc vu truyen tin SPI & Normalizer
    // =========================================================================
    reg [15:0] spectrum_bram [0:256];
    wire [8:0]  spi_bram_addr;
    wire [15:0] spi_bram_data;
    assign spi_bram_data = spectrum_bram[spi_bram_addr];

    wire [8:0]  norm_bram_rd_addr;
    reg  [15:0] norm_bram_rd_data;

    always @(posedge clk_100m) begin
        if (mag_valid && (mag_idx <= 9'd256))
            spectrum_bram[mag_idx] <= mag_data;
        norm_bram_rd_data <= spectrum_bram[norm_bram_rd_addr];
    end

    // =========================================================================
    // 7.1 UART Direct Spectrum Streamer (Baudrate 921600 len PC)
    // =========================================================================
    spectrum_uart_streamer #(
        .CLK_HZ (100_285_714),
        .BAUD   (921600)
    ) u_spectrum_uart (
        .clk        (clk_100m),
        .rst_n      (sys_rst_n),
        .bram_we    (mag_valid),
        .bram_addr  (mag_idx),
        .bram_data  (mag_data),
        .frame_done (mag_eop),
        .uart_txd   (uart_txd)
    );

    // =========================================================================
    // 7.2 Stage 3.5: Chuan hoa pho dinh cao (Peak Spectrum Normalizer)
    // =========================================================================
    wire                norm_npu_valid;
    wire [8:0]          norm_npu_addr;
    wire signed [7:0]   norm_npu_data;
    wire                norm_npu_start_pulse;
    wire                norm_busy;

    spec_normalizer #(
        .RD_LAT    (1),
        .WR_SETTLE (2)
    ) u_normalizer (
        .clk             (clk_100m),
        .rst_n           (sys_rst_n),
        .fft_valid       (mag_valid),
        .fft_sop         (mag_sop),
        .fft_eop         (mag_eop),
        .fft_mag         (mag_data),
        .bram_rd_addr    (norm_bram_rd_addr),
        .bram_rd_data    (norm_bram_rd_data),
        .npu_valid       (norm_npu_valid),
        .npu_addr        (norm_npu_addr),
        .npu_data        (norm_npu_data),
        .npu_start_pulse (norm_npu_start_pulse),
        .busy            (norm_busy)
    );

    // =========================================================================
    // 8. Stage 4 NPU: Nhan vector chuan hoa [0..127] tu spec_normalizer
    // =========================================================================
    wire                npu_ready;
    wire                npu_done;

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
        .WEIGHT_FILE_BANK5 (WEIGHT_FILE_BANK5),
        .BIAS_0            (BIAS_0),
        .BIAS_1            (BIAS_1),
        .BIAS_2            (BIAS_2),
        .BIAS_3            (BIAS_3)
    ) u_npu (
        .clk             (clk_100m),
        .rst_n           (sys_rst_n),
        .start           (norm_npu_start_pulse),
        .ready           (npu_ready),
        .done            (npu_done),
        .in_valid        (norm_npu_valid),
        .in_addr         (norm_npu_addr),
        .in_data         (norm_npu_data),
        .predicted_class (npu_pred_class),
        .logits_packed   (npu_logits),
        .vacuity_q15     (npu_vacuity_q15),
        .rul_q15         (npu_rul_q15),
        .ood_alert       (npu_ood_alert)
    );

    // =========================================================================
    // 9. Stage 5 SPI DMA Telemetry sang MCU
    // =========================================================================
    reg         spi_start_tx;
    wire        spi_tx_busy;

    // Thu thap co loi phan cung dua vao byte trang thai goi tin SPI (bit 11: npu_ood_alert)
    wire [15:0] status_flags = {4'd0, npu_ood_alert, err_sync, err_timeout, err_overrun, 5'd0, 1'b1, 2'b00};

    spi_master_packet #(
        .TOTAL_BYTES (524),
        .NUM_BINS    (257)
    ) u_spi_tx (
        .clk                    (clk_100m),
        .rst_n                  (sys_rst_n),
        .start_tx               (spi_start_tx),
        .npu_pred_class         (npu_pred_class),
        .dirichlet_max_evidence (npu_vacuity_q15[15:8]),
        .hardware_status_flags  (status_flags),
        .bram_addr              (spi_bram_addr),
        .bram_data              (spi_bram_data),
        .spi_sck                (mcu_spi_sck),
        .spi_cs_n               (mcu_spi_cs_n),
        .spi_mosi               (mcu_spi_mosi),
        .irq_pulse              (mcu_irq_pulse),
        .tx_busy                (spi_tx_busy)
    );

    // =========================================================================
    // 10. Master Control Sequencer (Kich hoat suy luan & Ban goi tin)
    // =========================================================================
    localparam SEQ_IDLE  = 2'd0;
    localparam SEQ_WAIT  = 2'd1;
    localparam SEQ_TX    = 2'd2;
    localparam SEQ_DELAY = 2'd3;

    reg [1:0] seq_state;

    always @(posedge clk_100m or negedge sys_rst_n) begin
        if (!sys_rst_n) begin
            seq_state      <= SEQ_IDLE;
            spi_start_tx   <= 1'b0;
            led_infer_busy <= 1'b0;
            led_ood_alert  <= 1'b0;
        end else begin
            led_infer_busy <= (seq_state == SEQ_WAIT) || norm_busy;
            led_ood_alert  <= npu_ood_alert;

            case (seq_state)
                SEQ_IDLE: begin
                    spi_start_tx <= 1'b0;
                    // Kich hoat cho NPU khi bin FFT cuoi cung vua nap xong
                    if (mag_eop && npu_ready && !spi_tx_busy) begin
                        seq_state <= SEQ_WAIT;
                    end
                end

                SEQ_WAIT: begin
                    if (npu_done) begin
                        spi_start_tx <= 1'b1;
                        seq_state    <= SEQ_TX;
                    end
                end

                SEQ_TX: begin
                    spi_start_tx <= 1'b0;
                    if (spi_tx_busy) seq_state <= SEQ_DELAY;
                end

                SEQ_DELAY: begin
                    if (!spi_tx_busy) seq_state <= SEQ_IDLE;
                end
            endcase
        end
    end

endmodule