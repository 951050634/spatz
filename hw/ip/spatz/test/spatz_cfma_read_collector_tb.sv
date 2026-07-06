// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Standalone testbench for the CFMA v2 two-beat VRF read collector.

`timescale 1ns/1ps

module spatz_cfma_read_collector_tb;
  localparam int unsigned ELEN       = 64;
  localparam int unsigned AddrWidth  = 10;
  localparam int unsigned ElemWidth  = 16;

  logic clk;
  logic rst_n;

  logic                         start_valid;
  logic                         start_ready;
  logic [AddrWidth-1:0]         a_real_addr;
  logic [AddrWidth-1:0]         a_imag_addr;
  logic [AddrWidth-1:0]         b_real_addr;
  logic [AddrWidth-1:0]         b_imag_addr;
  logic [AddrWidth-1:0]         c_real_addr;
  logic [AddrWidth-1:0]         c_imag_addr;
  logic [2:0][AddrWidth-1:0]    vrf_raddr;
  logic [2:0]                   vrf_re;
  logic [2:0]                   vrf_rvalid;
  logic [2:0][ELEN-1:0]         vrf_rdata;
  logic                         bundle_valid;
  logic                         bundle_ready;
  logic [ELEN-1:0]              a_real_data;
  logic [ELEN-1:0]              a_imag_data;
  logic [ELEN-1:0]              b_real_data;
  logic [ELEN-1:0]              b_imag_data;
  logic [ELEN-1:0]              c_real_data;
  logic [ELEN-1:0]              c_imag_data;
  logic [AddrWidth-1:0]         vd_real_addr_o;
  logic [AddrWidth-1:0]         vd_imag_addr_o;
  logic [ElemWidth-1:0]         elem_idx_i;
  logic [ElemWidth-1:0]         elem_idx_o;
  logic                         last_i;
  logic                         last_o;
  logic                         busy;

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  initial begin
    rst_n = 1'b0;
    repeat (4) @(posedge clk);
    rst_n = 1'b1;
  end

  spatz_cfma_read_collector #(
    .ELEN      (ELEN),
    .AddrWidth (AddrWidth),
    .ElemWidth (ElemWidth)
  ) i_dut (
    .clk_i           (clk),
    .rst_ni          (rst_n),
    .start_valid_i   (start_valid),
    .start_ready_o   (start_ready),
    .a_real_addr_i   (a_real_addr),
    .a_imag_addr_i   (a_imag_addr),
    .b_real_addr_i   (b_real_addr),
    .b_imag_addr_i   (b_imag_addr),
    .c_real_addr_i   (c_real_addr),
    .c_imag_addr_i   (c_imag_addr),
    .elem_idx_i      (elem_idx_i),
    .last_i          (last_i),
    .vrf_raddr_o     (vrf_raddr),
    .vrf_re_o        (vrf_re),
    .vrf_rvalid_i    (vrf_rvalid),
    .vrf_rdata_i     (vrf_rdata),
    .bundle_valid_o  (bundle_valid),
    .bundle_ready_i  (bundle_ready),
    .a_real_o        (a_real_data),
    .a_imag_o        (a_imag_data),
    .b_real_o        (b_real_data),
    .b_imag_o        (b_imag_data),
    .c_real_o        (c_real_data),
    .c_imag_o        (c_imag_data),
    .vd_real_addr_o  (vd_real_addr_o),
    .vd_imag_addr_o  (vd_imag_addr_o),
    .elem_idx_o      (elem_idx_o),
    .last_o          (last_o),
    .busy_o          (busy)
  );

  task automatic expect_r0_addresses;
    begin
      if (vrf_re !== 3'b111) $fatal(1, "R0 vrf_re mismatch: %b", vrf_re);
      if (vrf_raddr[0] !== a_real_addr) $fatal(1, "R0 port0 expected a.real addr");
      if (vrf_raddr[1] !== a_imag_addr) $fatal(1, "R0 port1 expected a.imag addr");
      if (vrf_raddr[2] !== b_real_addr) $fatal(1, "R0 port2 expected b.real addr");
    end
  endtask

  task automatic expect_r1_addresses;
    begin
      if (vrf_re !== 3'b111) $fatal(1, "R1 vrf_re mismatch: %b", vrf_re);
      if (vrf_raddr[0] !== b_imag_addr) $fatal(1, "R1 port0 expected b.imag addr");
      if (vrf_raddr[1] !== c_real_addr) $fatal(1, "R1 port1 expected c.real addr");
      if (vrf_raddr[2] !== c_imag_addr) $fatal(1, "R1 port2 expected c.imag addr");
    end
  endtask

  task automatic expect_bundle;
    begin
      if (!bundle_valid) $fatal(1, "bundle_valid not asserted");
      if (a_real_data !== 64'haaaa_0000_0000_0001) $fatal(1, "a.real data mismatch");
      if (a_imag_data !== 64'haaaa_0000_0000_0002) $fatal(1, "a.imag data mismatch");
      if (b_real_data !== 64'hbbbb_0000_0000_0001) $fatal(1, "b.real data mismatch");
      if (b_imag_data !== 64'hbbbb_0000_0000_0002) $fatal(1, "b.imag data mismatch");
      if (c_real_data !== 64'hcccc_0000_0000_0001) $fatal(1, "c.real data mismatch");
      if (c_imag_data !== 64'hcccc_0000_0000_0002) $fatal(1, "c.imag data mismatch");
      if (vd_real_addr_o !== c_real_addr) $fatal(1, "vd_real_addr mismatch");
      if (vd_imag_addr_o !== c_imag_addr) $fatal(1, "vd_imag_addr mismatch");
      if (elem_idx_o !== elem_idx_i) $fatal(1, "elem_idx mismatch");
      if (last_o !== last_i) $fatal(1, "last mismatch");
    end
  endtask

  initial begin
    start_valid = 1'b0;
    bundle_ready = 1'b0;
    vrf_rvalid = '0;
    vrf_rdata = '0;
    a_real_addr = 10'h010;
    a_imag_addr = 10'h018;
    b_real_addr = 10'h020;
    b_imag_addr = 10'h028;
    c_real_addr = 10'h030;
    c_imag_addr = 10'h038;
    elem_idx_i = 16'h0042;
    last_i = 1'b1;

    wait (rst_n === 1'b1);
    @(posedge clk);
    if (!start_ready || busy) $fatal(1, "collector not idle after reset");

    start_valid = 1'b1;
    @(posedge clk);
    start_valid = 1'b0;

    expect_r0_addresses();
    if (!busy || bundle_valid) $fatal(1, "collector should be busy in R0 without bundle");

    vrf_rdata[0] = 64'haaaa_0000_0000_0001;
    vrf_rdata[1] = 64'haaaa_0000_0000_0002;
    vrf_rdata[2] = 64'hbbbb_0000_0000_0001;
    vrf_rvalid = 3'b011;
    @(posedge clk);
    expect_r0_addresses();

    vrf_rvalid = 3'b111;
    @(posedge clk);
    expect_r1_addresses();

    vrf_rdata[0] = 64'hbbbb_0000_0000_0002;
    vrf_rdata[1] = 64'hcccc_0000_0000_0001;
    vrf_rdata[2] = 64'hcccc_0000_0000_0002;
    @(posedge clk);
    vrf_rvalid = 3'b000;

    expect_bundle();
    if (start_ready) $fatal(1, "collector accepted new start while bundle pending");

    repeat (3) begin
      @(posedge clk);
      expect_bundle();
    end

    bundle_ready = 1'b1;
    @(posedge clk);
    bundle_ready = 1'b0;
    if (!start_ready || busy || bundle_valid) $fatal(1, "collector did not return idle after bundle handshake");

    $display("spatz_cfma_read_collector_tb: PASS R0/R1 mapping and backpressure");
    $finish;
  end
endmodule
