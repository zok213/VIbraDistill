# Makefile for Gowin 12-Way NPU Verilog Co-Simulation
IV = iverilog
VVP = vvp
VFLAGS = -g2012 -Wall

SRCS = ../src/npu_mac12_unit.v ../src/npu_12way_core.v ../src/tb_npu_cosim.v

all: simulate

compile:
	$(IV) $(VFLAGS) -o tb_npu_cosim.vvp $(SRCS)

simulate: compile
	$(VVP) tb_npu_cosim.vvp

clean:
	rm -f tb_npu_cosim.vvp test_vectors/cosim_rtl_output.hex
