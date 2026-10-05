#!/usr/bin/env bash
set -e
echo "======================================================================"
echo " RUNNING GOWIN NPU VERILOG CO-SIMULATION (ICARUS VERILOG)"
echo "======================================================================"
cd ..
iverilog -g2012 -o sim/tb_npu_cosim.vvp src/npu_mac12_unit.v src/npu_12way_core.v src/tb_npu_cosim.v
cd sim
vvp tb_npu_cosim.vvp
echo "[SUCCESS] Hardware co-simulation passed!"
