@echo off
echo ======================================================================
echo  RUNNING GOWIN NPU VERILOG CO-SIMULATION (ICARUS VERILOG)
echo ======================================================================
cd ..
iverilog -g2012 -o sim/tb_npu_cosim.vvp src/npu_mac12_unit.v src/npu_12way_core.v src/tb_npu_cosim.v
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Verilog compilation failed!
    exit /b 1
)
cd sim
vvp tb_npu_cosim.vvp
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Simulation failed!
    exit /b 1
)
echo [SUCCESS] Hardware co-simulation passed!
