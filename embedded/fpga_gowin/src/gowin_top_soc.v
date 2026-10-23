// ============================================================================
// Module Name: gowin_top_soc
// Description: Top-Level Gowin Primer 20K Edge AI SoC Architecture
//              End-to-End Signal Chain:
//                1. ST IIS3DWB Sensor Acceleration Ingest (13.333 kHz)
//                2. 32-Tap Causal Min-Phase FIR Bandpass (2-5 kHz)
//                3. Causal Envelope Demodulator (Rectifier + Butterworth IIR)
//                4. 12-Way Parallel NPU Systolic Accelerator (QAT INT8)
//                5. Hardware Telemetry & Inference SPI DMA Master to Sonix MCU
// Target:      Gowin GW2A-LV18PG256 (20K LUTs, 48 DSP18E, 46 BSRAMs)
// ============================================================================

`timescale 1ns / 1ps

module gowin_top_soc #(
    parameter USE_ADXL345 = 1,  // 1: Live ADXL345 SPI Mode (3.2 kHz), 0: HIL / 12kHz Mode
    parameter WEIGHT_FILE_BANK0 = USE_ADXL345 ? "roms/adxl345/npu_weights_bank0.hex" : "roms/npu_weights_bank0.hex",
    parameter WEIGHT_FILE_BANK1 = USE_ADXL345 ? "roms/adxl345/npu_weights_bank1.hex" : "roms/npu_weights_bank1.hex",
    parameter WEIGHT_FILE_BANK2 = USE_ADXL345 ? "roms/adxl345/npu_weights_bank2.hex" : "roms/npu_weights_bank2.hex",
    parameter WEIGHT_FILE_BANK3 = USE_ADXL345 ? "roms/adxl345/npu_weights_bank3.hex" : "roms/npu_weights_bank3.hex",
    parameter WEIGHT_FILE_BANK4 = USE_ADXL345 ? "roms/adxl345/npu_weights_bank4.hex" : "roms/npu_weights_bank4.hex",
    parameter WEIGHT_FILE_BANK5 = USE_ADXL345 ? "roms/adxl345/npu_weights_bank5.hex" : "roms/npu_weights_bank5.hex"
)(
    input  wire                 clk_100m,         // 100 MHz On-Board Oscillator
    input  wire                 rst_n_pin,        // Active-Low Reset Pushbutton
    
    // Physical ADXL345 / GY-291 SPI Interface (PMOD0 Header J3)
    output wire                 adxl_cs_n,        // Chip Select (Pin 1)
    output wire                 adxl_sclk,        // 5.0 MHz SPI Clock (Pin 4)
    output wire                 adxl_mosi,        // MOSI (SDA/SDI Pin 2)
    input  wire                 adxl_miso,        // MISO (SDO Pin 3)
    input  wire                 adxl_int1,        // DATA_READY Strobe (Pin 7)
    
    // Optional Fallback / External Ingest Interface (HIL Streamer / CWRU 12kHz)
    input  wire                 sensor_sample_en, // 12.0/13.333 kHz Sample Strobe
    input  wire signed [15:0]   sensor_data_in,   // 16-bit Raw Acceleration Sample
    
    // External Tachometer & Telemetry Inputs
    input  wire [15:0]          shaft_speed_fr,   // Rotational frequency fr (0.1 Hz)
    input  wire [15:0]          temperature_c,    // Bearing housing temperature (0.1 C)
    
    // High-Speed SPI DMA Interface to Sonix MCU (SN32F407 / SN34F788)
    output wire                 spi_sck,          // SPI Clock (12.5 MHz)
    output wire                 spi_cs_n,         // Active-Low SPI Chip Select
    output wire                 spi_mosi,         // Master Out Slave In
    output wire                 mcu_irq_pulse,    // Hardware IRQ Strobe to MCU GPIO
    
    // Status & Diagnostic LEDs
    output reg                  led_alive,        // Heartbeat LED
    output reg                  led_infer_busy,   // NPU active LED
    output reg                  led_ood_alert     // Dirichlet Vacuity Alert LED (u* > 0.45)
);

    // =========================================================================
    // 1. Clock & Reset Management
    // =========================================================================
    reg [23:0] heartbeat_cnt;
    always @(posedge clk_100m or negedge rst_n_pin) begin
        if (!rst_n_pin) begin
            heartbeat_cnt <= 24'd0;
            led_alive     <= 1'b0;
        end else begin
            heartbeat_cnt <= heartbeat_cnt + 1'b1;
            led_alive     <= heartbeat_cnt[23]; // ~6 Hz Blink
        end
    end

    // =========================================================================
    // 2. Stage 1 DSP: ADXL345 Master Ingest & 32-Tap Causal Min-Phase FIR
    // =========================================================================
    wire signed [15:0] adxl_x, adxl_y, adxl_z;
    wire               adxl_sample_valid;
    wire               adxl_ready;

    adxl345_spi_master #(
        .CLK_FREQ_HZ (100_000_000),
        .SPI_SCLK_HZ (5_000_000),
        .DATA_WIDTH  (16)
    ) u_adxl_master (
        .clk          (clk_100m),
        .rst_n        (rst_n_pin),
        .spi_cs_n     (adxl_cs_n),
        .spi_sclk     (adxl_sclk),
        .spi_mosi     (adxl_mosi),
        .spi_miso     (adxl_miso),
        .adxl_int1    (adxl_int1),
        .accel_x      (adxl_x),
        .accel_y      (adxl_y),
        .accel_z      (adxl_z),
        .sample_valid (adxl_sample_valid),
        .ready        (adxl_ready)
    );

    // Mux input source based on mode
    wire signed [15:0] sample_in = USE_ADXL345 ? adxl_z : sensor_data_in;
    wire               sample_strobe = USE_ADXL345 ? adxl_sample_valid : sensor_sample_en;

    wire signed [15:0] fir_out;
    wire               fir_valid;

    generate
        if (USE_ADXL345) begin: gen_adxl_fir
            fir_adxl345_32 #(
                .DATA_WIDTH  (16),
                .COEFF_WIDTH (16),
                .TAPS        (32)
            ) u_fir_adxl (
                .clk        (clk_100m),
                .rst_n      (rst_n_pin),
                .sample_en  (sample_strobe),
                .x_in       (sample_in),
                .y_out      (fir_out),
                .valid_out  (fir_valid)
            );
        end else begin: gen_legacy_fir
            fir_minphase_32 #(
                .DATA_WIDTH  (16),
                .COEFF_WIDTH (16),
                .TAPS        (32)
            ) u_fir_legacy (
                .clk        (clk_100m),
                .rst_n      (rst_n_pin),
                .sample_en  (sample_strobe),
                .x_in       (sample_in),
                .y_out      (fir_out),
                .valid_out  (fir_valid)
            );
        end
    endgenerate

    // =========================================================================
    // 3. Stage 2 DSP: Causal Envelope Demodulator (Rectifier + IIR LPF)
    // =========================================================================
    wire signed [15:0] env_out;
    wire               env_valid;

    envelope_demodulator #(
        .WIDTH        (16),
        .USE_ADXL345  (USE_ADXL345)
    ) u_envelope (
        .clk        (clk_100m),
        .rst_n      (rst_n_pin),
        .sample_en  (fir_valid),
        .y_filtered (fir_out),
        .env_out    (env_out),
        .valid_out  (env_valid)
    );

    // =========================================================================
    // 4. Stage 3 NPU: Gowin 12-Way Systolic Acceleration Core
    // =========================================================================
    reg         npu_start;
    wire        npu_ready;
    wire        npu_done;
    reg         npu_in_valid;
    reg  [8:0]  npu_in_addr;
    reg  signed [7:0] npu_in_data;

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
        .rst_n           (rst_n_pin),
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
    // 5. Stage 4 SPI DMA Telemetry: Packet Streaming to Sonix MCU
    // =========================================================================
    reg         spi_start_tx;
    wire [8:0]  spi_bram_addr;
    wire [15:0] spi_bram_data;
    wire        spi_tx_busy;

    // Dual-Port BRAM for FFT / Spectrum Transmission
    reg [15:0] spectrum_bram [0:256];
    assign spi_bram_data = spectrum_bram[spi_bram_addr];

    spi_master_packet #(
        .TOTAL_BYTES (524),
        .NUM_BINS    (257)
    ) u_spi_tx (
        .clk         (clk_100m),
        .rst_n       (rst_n_pin),
        .start_tx    (spi_start_tx),
        .shaft_speed (shaft_speed_fr),
        .temperature (temperature_c),
        .bram_addr   (spi_bram_addr),
        .bram_data   (spi_bram_data),
        .spi_sck     (spi_sck),
        .spi_cs_n    (spi_cs_n),
        .spi_mosi    (spi_mosi),
        .irq_pulse   (mcu_irq_pulse),
        .tx_busy     (spi_tx_busy)
    );

    // =========================================================================
    // 6. Master Control Sequencer & LED Indicators
    // =========================================================================
    always @(posedge clk_100m or negedge rst_n_pin) begin
        if (!rst_n_pin) begin
            npu_start      <= 1'b0;
            npu_in_valid   <= 1'b0;
            npu_in_addr    <= 9'd0;
            npu_in_data    <= 8'sd0;
            spi_start_tx   <= 1'b0;
            led_infer_busy <= 1'b0;
            led_ood_alert  <= 1'b0;
        end else begin
            led_infer_busy <= !npu_ready;
            led_ood_alert  <= npu_ood_alert;

            // Trigger SPI packet when NPU inference completes
            if (npu_done && !spi_tx_busy) begin
                spi_start_tx <= 1'b1;
            end else begin
                spi_start_tx <= 1'b0;
            end
        end
    end

endmodule
