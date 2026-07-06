// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Directed Stage-4 test: the VFU dedicated complex FMA must consume the
// two-beat CFMA read-collector bundle when CfmaDedicatedReadCollectorEn=1.

`timescale 1ns/1ps

module spatz_vfu_cfma_compute_bundle_tb;
  import spatz_pkg::*;
  import rvv_pkg::*;
  import fpnew_pkg::*;

  logic clk;
  logic rst_n;

  spatz_req_t spatz_req;
  logic       spatz_req_valid;
  logic       spatz_req_ready;
  logic       vfu_rsp_valid;
  logic       vfu_rsp_ready;
  vfu_rsp_t   vfu_rsp;
  vrf_addr_t  vrf_waddr;
  vrf_data_t  vrf_wdata;
  logic       vrf_we;
  vrf_be_t    vrf_wbe;
  logic       vrf_wvalid;
  spatz_id_t [3:0] vrf_id;
  vrf_addr_t [2:0] vrf_raddr;
  logic      [2:0] vrf_re;
  vrf_data_t [2:0] vrf_rdata;
  logic      [2:0] vrf_rvalid;
  status_t         fpu_status;

  localparam vreg_t Vs1 = vreg_t'(5);
  localparam vreg_t Vs2 = vreg_t'(9);
  localparam vreg_t Vd  = vreg_t'(13);

  // FP64: a=(1+2i), b=(3+4i), c=(5+6i) => result=(0+16i), fflags=0.
  localparam logic [63:0] A_REAL = 64'h3ff0_0000_0000_0000;
  localparam logic [63:0] A_IMAG = 64'h4000_0000_0000_0000;
  localparam logic [63:0] B_REAL = 64'h4008_0000_0000_0000;
  localparam logic [63:0] B_IMAG = 64'h4010_0000_0000_0000;
  localparam logic [63:0] C_REAL = 64'h4014_0000_0000_0000;
  localparam logic [63:0] C_IMAG = 64'h4018_0000_0000_0000;
  localparam logic [63:0] R_REAL = 64'h0000_0000_0000_0000;
  localparam logic [63:0] R_IMAG = 64'h4030_0000_0000_0000;

  function automatic vrf_addr_t word_addr(input vreg_t reg_idx);
    return vrf_addr_t'(reg_idx << $clog2(NrWordsPerVector));
  endfunction

  function automatic vrf_data_t fp_at_addr(input vrf_addr_t addr);
    unique case (addr)
      word_addr(Vs1)              : return vrf_data_t'(A_REAL);
      word_addr(vreg_t'(Vs1 + 1)) : return vrf_data_t'(A_IMAG);
      word_addr(Vs2)              : return vrf_data_t'(B_REAL);
      word_addr(vreg_t'(Vs2 + 1)) : return vrf_data_t'(B_IMAG);
      word_addr(Vd)               : return vrf_data_t'(C_REAL);
      word_addr(vreg_t'(Vd + 1))  : return vrf_data_t'(C_IMAG);
      default                     : return '0;
    endcase
  endfunction

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  spatz_vfu #(
    .FPUImplementation(fpnew_pkg::DEFAULT_NOREGS),
    .CfmaDedicatedReadCollectorEn(1'b1),
    .CfmaDedicatedWritebackEn(1'b0)
  ) i_dut (
    .clk_i             (clk),
    .rst_ni            (rst_n),
    .hart_id_i         (32'h0),
    .spatz_req_i       (spatz_req),
    .spatz_req_valid_i (spatz_req_valid),
    .spatz_req_ready_o (spatz_req_ready),
    .vfu_rsp_valid_o   (vfu_rsp_valid),
    .vfu_rsp_ready_i   (vfu_rsp_ready),
    .vfu_rsp_o         (vfu_rsp),
    .vrf_waddr_o       (vrf_waddr),
    .vrf_wdata_o       (vrf_wdata),
    .vrf_we_o          (vrf_we),
    .vrf_wbe_o         (vrf_wbe),
    .vrf_wvalid_i      (vrf_wvalid),
    .vrf_id_o          (vrf_id),
    .vrf_raddr_o       (vrf_raddr),
    .vrf_re_o          (vrf_re),
    .vrf_rdata_i       (vrf_rdata),
    .vrf_rvalid_i      (vrf_rvalid),
    .fpu_status_o      (fpu_status)
  );

  always_comb begin
    for (int unsigned port = 0; port < 3; port++) begin
      vrf_rdata[port] = fp_at_addr(vrf_raddr[port]);
    end
  end

  task automatic init_req;
    begin
      spatz_req = '0;
      spatz_req.id              = '0;
      spatz_req.vs1             = Vs1;
      spatz_req.use_vs1         = 1'b1;
      spatz_req.vs2             = Vs2;
      spatz_req.use_vs2         = 1'b1;
      spatz_req.vd              = Vd;
      spatz_req.use_vd          = 1'b1;
      spatz_req.vd_is_src       = 1'b1;
      spatz_req.op              = VFCMADD;
      spatz_req.ex_unit         = VFU;
      spatz_req.op_arith.vm     = 1'b1;
      spatz_req.rm              = fpnew_pkg::RNE;
      spatz_req.vtype.vsew      = EW_64;
      spatz_req.vtype.vlmul     = LMUL_1;
      spatz_req.vl              = vlen_t'(1);
      spatz_req.vstart          = '0;
    end
  endtask

  initial begin
    rst_n           = 1'b0;
    spatz_req_valid = 1'b0;
    vfu_rsp_ready   = 1'b1;
    vrf_wvalid      = 1'b1;
    vrf_rvalid      = 3'b111;
    init_req();

    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    repeat (2) @(posedge clk);

    spatz_req_valid = 1'b1;

    for (int cycle = 0; cycle < 40; cycle++) begin
      @(posedge clk);
      #1;
      if (i_dut.gen_fpu.cfma_result_valid) begin
        if (i_dut.gen_fpu.cfma_result_real !== R_REAL)
          $fatal(1, "CFMA real result mismatch: expected 0x%0h got 0x%0h", R_REAL, i_dut.gen_fpu.cfma_result_real);
        if (i_dut.gen_fpu.cfma_result_imag !== R_IMAG)
          $fatal(1, "CFMA imag result mismatch: expected 0x%0h got 0x%0h", R_IMAG, i_dut.gen_fpu.cfma_result_imag);
        if (i_dut.gen_fpu.cfma_status !== status_t'(0))
          $fatal(1, "CFMA fflags mismatch");
        $display("SPATZ_VFU_CFMA_COMPUTE_BUNDLE_TB_PASS result.real=0x%0h result.imag=0x%0h", i_dut.gen_fpu.cfma_result_real, i_dut.gen_fpu.cfma_result_imag);
        $finish;
      end
    end

    $fatal(1, "Timed out waiting for dedicated CFMA result_valid");
  end
endmodule
