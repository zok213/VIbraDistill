// ============================================================================
// File Name: primer20k_timing.sdc
// Target Board: Sipeed Tang Primer 20K (GW2A-LV18PG256)
// Description: Synopsys Timing Constraints for 100 MHz System & 5 MHz SPI Clock
// ============================================================================

// 1. Primary Crystal Oscillator: 27 MHz (Period = 37.037 ns)
create_clock -name clk_27m -period 37.037 -waveform {0 18.518} [get_ports {clk_27m}]

// 2. PLL Generated System Clock: 100 MHz (Period = 10.000 ns)
create_clock -name clk_100m -period 10.000 -waveform {0 5.000} [get_nets {clk_100m}]

// 3. ADXL345 SPI Clock: 5.0 MHz (Period = 200.000 ns)
create_clock -name adxl_sclk -period 200.000 -waveform {0 100.000} [get_nets {adxl_sclk}]

// 4. False Paths across asynchronous reset
set_false_path -from [get_ports {rst_n_pin}]
set_false_path -from [get_ports {adxl_int1}]
