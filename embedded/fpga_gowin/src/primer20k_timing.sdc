# ============================================================================
# File Name: primer20k_timing.sdc
# Target Board: Sipeed Tang Primer 20K (GW2A-LV18PG256)
# Description: Pure HIL Mode Timing Constraints
# ============================================================================

# 1. Primary Crystal Oscillator: 27 MHz (Period = 37.037 ns)
# ============================================================================
# File Name: primer20k_timing.sdc
# ============================================================================

# Khống chế xung clock 27 MHz đầu vào (Không dùng get_ports nữa)
create_clock -name clk_27m -period 37.037 -waveform {0 18.518} [get_ports {clk_27m}]

# LUY Y: KHONG dung lệnh create_clock cho clk_100m. 
# Gowin EDA se tu dong noi suy tan so 100 MHz tu bo rPLL.

# 2. False Paths across asynchronous reset
set_false_path -from [get_ports {rst_n_pin}]