//Copyright (C)2014-2026 Gowin Semiconductor Corporation.
//All rights reserved.
//File Title: Template file for instantiation
//Tool Version: V1.9.12.03 (64-bit)
//IP Version: 1.5
//Part Number: GW2A-LV18PG256C8/I7
//Device: GW2A-18
//Device Version: C
//Created Time: Sun Nov  1 09:23:33 2026

//Change the instance name and port connections to the signal names
//--------Copy here to design--------

	FFT_Top your_instance_name(
		.idx(idx), //output [8:0] idx
		.xk_re(xk_re), //output [15:0] xk_re
		.xk_im(xk_im), //output [15:0] xk_im
		.sod(sod), //output sod
		.ipd(ipd), //output ipd
		.eod(eod), //output eod
		.busy(busy), //output busy
		.soud(soud), //output soud
		.opd(opd), //output opd
		.eoud(eoud), //output eoud
		.xn_re(xn_re), //input [15:0] xn_re
		.xn_im(xn_im), //input [15:0] xn_im
		.start(start), //input start
		.clk(clk), //input clk
		.rst(rst) //input rst
	);

//--------Copy end-------------------
