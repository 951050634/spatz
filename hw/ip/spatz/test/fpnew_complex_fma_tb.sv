// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Standalone directed testbench for fpnew_complex_fma.
//
// This test intentionally checks the v2 arithmetic contract against exact
// bit patterns for simple representable operands:
//   real = c.real + a.real * b.real - a.imag * b.imag
//   imag = c.imag + a.real * b.imag + a.imag * b.real
// The chosen operands are exactly representable in FP16/FP32/FP64 and produce
// exact results, so all exception flags must remain clear in RNE mode.

`timescale 1ns/1ps

module fpnew_complex_fma_tb;
  import fpnew_pkg::*;

  logic clk;
  logic rst_n;

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  initial begin
    rst_n = 1'b0;
    repeat (5) @(posedge clk);
    rst_n = 1'b1;
  end

  // -----------------
  // FP64 DUT instance
  // -----------------
  logic [63:0] fp64_ar, fp64_ai, fp64_br, fp64_bi, fp64_cr, fp64_ci;
  logic        fp64_valid, fp64_ready, fp64_flush;
  logic [63:0] fp64_real, fp64_imag;
  status_t     fp64_status;
  logic        fp64_result_valid, fp64_result_ready, fp64_busy;
  logic [7:0]  fp64_tag_i, fp64_tag_o;

  fpnew_complex_fma #(
    .FpFormat(fpnew_pkg::FP64),
    .NumPipeRegs(0),
    .PipeConfig(fpnew_pkg::BEFORE),
    .TagType(logic [7:0])
  ) i_dut_fp64 (
    .clk_i(clk),
    .rst_ni(rst_n),
    .operand_a_real_i(fp64_ar),
    .operand_a_imag_i(fp64_ai),
    .operand_b_real_i(fp64_br),
    .operand_b_imag_i(fp64_bi),
    .operand_c_real_i(fp64_cr),
    .operand_c_imag_i(fp64_ci),
    .rnd_mode_i(fpnew_pkg::RNE),
    .op_valid_i(fp64_valid),
    .op_ready_o(fp64_ready),
    .flush_i(fp64_flush),
    .result_real_o(fp64_real),
    .result_imag_o(fp64_imag),
    .status_o(fp64_status),
    .result_valid_o(fp64_result_valid),
    .result_ready_i(fp64_result_ready),
    .tag_i(fp64_tag_i),
    .tag_o(fp64_tag_o),
    .busy_o(fp64_busy)
  );

  // -----------------
  // FP32 DUT instance
  // -----------------
  logic [31:0] fp32_ar, fp32_ai, fp32_br, fp32_bi, fp32_cr, fp32_ci;
  logic        fp32_valid, fp32_ready, fp32_flush;
  logic [31:0] fp32_real, fp32_imag;
  status_t     fp32_status;
  logic        fp32_result_valid, fp32_result_ready, fp32_busy;
  logic [7:0]  fp32_tag_i, fp32_tag_o;

  fpnew_complex_fma #(
    .FpFormat(fpnew_pkg::FP32),
    .NumPipeRegs(0),
    .PipeConfig(fpnew_pkg::BEFORE),
    .TagType(logic [7:0])
  ) i_dut_fp32 (
    .clk_i(clk),
    .rst_ni(rst_n),
    .operand_a_real_i(fp32_ar),
    .operand_a_imag_i(fp32_ai),
    .operand_b_real_i(fp32_br),
    .operand_b_imag_i(fp32_bi),
    .operand_c_real_i(fp32_cr),
    .operand_c_imag_i(fp32_ci),
    .rnd_mode_i(fpnew_pkg::RNE),
    .op_valid_i(fp32_valid),
    .op_ready_o(fp32_ready),
    .flush_i(fp32_flush),
    .result_real_o(fp32_real),
    .result_imag_o(fp32_imag),
    .status_o(fp32_status),
    .result_valid_o(fp32_result_valid),
    .result_ready_i(fp32_result_ready),
    .tag_i(fp32_tag_i),
    .tag_o(fp32_tag_o),
    .busy_o(fp32_busy)
  );

  // -----------------
  // FP16 DUT instance
  // -----------------
  logic [15:0] fp16_ar, fp16_ai, fp16_br, fp16_bi, fp16_cr, fp16_ci;
  logic        fp16_valid, fp16_ready, fp16_flush;
  logic [15:0] fp16_real, fp16_imag;
  status_t     fp16_status;
  logic        fp16_result_valid, fp16_result_ready, fp16_busy;
  logic [7:0]  fp16_tag_i, fp16_tag_o;

  fpnew_complex_fma #(
    .FpFormat(fpnew_pkg::FP16),
    .NumPipeRegs(0),
    .PipeConfig(fpnew_pkg::BEFORE),
    .TagType(logic [7:0])
  ) i_dut_fp16 (
    .clk_i(clk),
    .rst_ni(rst_n),
    .operand_a_real_i(fp16_ar),
    .operand_a_imag_i(fp16_ai),
    .operand_b_real_i(fp16_br),
    .operand_b_imag_i(fp16_bi),
    .operand_c_real_i(fp16_cr),
    .operand_c_imag_i(fp16_ci),
    .rnd_mode_i(fpnew_pkg::RNE),
    .op_valid_i(fp16_valid),
    .op_ready_o(fp16_ready),
    .flush_i(fp16_flush),
    .result_real_o(fp16_real),
    .result_imag_o(fp16_imag),
    .status_o(fp16_status),
    .result_valid_o(fp16_result_valid),
    .result_ready_i(fp16_result_ready),
    .tag_i(fp16_tag_i),
    .tag_o(fp16_tag_o),
    .busy_o(fp16_busy)
  );

  function automatic logic flags_clear(status_t st);
    return !(st.NV | st.DZ | st.OF | st.UF | st.NX);
  endfunction

  task automatic run_fp64_directed;
    int cycles;
    begin
      // a=(1.5,2.0), b=(3.0,4.0), c=(5.0,6.0)
      // expected=(1.5,18.0), exact, flags=0
      fp64_ar = 64'h3ff8_0000_0000_0000;
      fp64_ai = 64'h4000_0000_0000_0000;
      fp64_br = 64'h4008_0000_0000_0000;
      fp64_bi = 64'h4010_0000_0000_0000;
      fp64_cr = 64'h4014_0000_0000_0000;
      fp64_ci = 64'h4018_0000_0000_0000;
      fp64_tag_i = 8'h64;
      fp64_result_ready = 1'b1;
      fp64_flush = 1'b0;
      fp64_valid = 1'b0;
      @(posedge clk);
      if (!fp64_ready) $fatal(1, "FP64 DUT not ready at test start");
      fp64_valid = 1'b1;
      @(posedge clk);
      fp64_valid = 1'b0;
      cycles = 0;
      while (!fp64_result_valid && cycles < 40) begin
        @(posedge clk);
        cycles++;
      end
      if (!fp64_result_valid) $fatal(1, "FP64 result did not become valid");
      if (fp64_real !== 64'h3ff8_0000_0000_0000)
        $fatal(1, "FP64 real mismatch: actual=0x%016h expected=0x3ff8000000000000", fp64_real);
      if (fp64_imag !== 64'h4032_0000_0000_0000)
        $fatal(1, "FP64 imag mismatch: actual=0x%016h expected=0x4032000000000000", fp64_imag);
      if (!flags_clear(fp64_status)) $fatal(1, "FP64 flags not clear: %b", fp64_status);
      if (fp64_tag_o !== 8'h64) $fatal(1, "FP64 tag mismatch: actual=0x%02h", fp64_tag_o);
      @(posedge clk);
    end
  endtask

  task automatic run_fp32_directed;
    int cycles;
    begin
      // a=(1.5,2.0), b=(3.0,4.0), c=(5.0,6.0)
      // expected=(1.5,18.0), exact, flags=0
      fp32_ar = 32'h3fc0_0000;
      fp32_ai = 32'h4000_0000;
      fp32_br = 32'h4040_0000;
      fp32_bi = 32'h4080_0000;
      fp32_cr = 32'h40a0_0000;
      fp32_ci = 32'h40c0_0000;
      fp32_tag_i = 8'h32;
      fp32_result_ready = 1'b1;
      fp32_flush = 1'b0;
      fp32_valid = 1'b0;
      @(posedge clk);
      if (!fp32_ready) $fatal(1, "FP32 DUT not ready at test start");
      fp32_valid = 1'b1;
      @(posedge clk);
      fp32_valid = 1'b0;
      cycles = 0;
      while (!fp32_result_valid && cycles < 40) begin
        @(posedge clk);
        cycles++;
      end
      if (!fp32_result_valid) $fatal(1, "FP32 result did not become valid");
      if (fp32_real !== 32'h3fc0_0000)
        $fatal(1, "FP32 real mismatch: actual=0x%08h expected=0x3fc00000", fp32_real);
      if (fp32_imag !== 32'h4190_0000)
        $fatal(1, "FP32 imag mismatch: actual=0x%08h expected=0x41900000", fp32_imag);
      if (!flags_clear(fp32_status)) $fatal(1, "FP32 flags not clear: %b", fp32_status);
      if (fp32_tag_o !== 8'h32) $fatal(1, "FP32 tag mismatch: actual=0x%02h", fp32_tag_o);
      @(posedge clk);
    end
  endtask

  task automatic run_fp16_directed;
    int cycles;
    begin
      // a=(1,2), b=(3,4), c=(5,6)
      // expected=(0,16), exact, flags=0
      fp16_ar = 16'h3c00;
      fp16_ai = 16'h4000;
      fp16_br = 16'h4200;
      fp16_bi = 16'h4400;
      fp16_cr = 16'h4500;
      fp16_ci = 16'h4600;
      fp16_tag_i = 8'h16;
      fp16_result_ready = 1'b1;
      fp16_flush = 1'b0;
      fp16_valid = 1'b0;
      @(posedge clk);
      if (!fp16_ready) $fatal(1, "FP16 DUT not ready at test start");
      fp16_valid = 1'b1;
      @(posedge clk);
      fp16_valid = 1'b0;
      cycles = 0;
      while (!fp16_result_valid && cycles < 40) begin
        @(posedge clk);
        cycles++;
      end
      if (!fp16_result_valid) $fatal(1, "FP16 result did not become valid");
      if (fp16_real !== 16'h0000)
        $fatal(1, "FP16 real mismatch: actual=0x%04h expected=0x0000", fp16_real);
      if (fp16_imag !== 16'h4c00)
        $fatal(1, "FP16 imag mismatch: actual=0x%04h expected=0x4c00", fp16_imag);
      if (!flags_clear(fp16_status)) $fatal(1, "FP16 flags not clear: %b", fp16_status);
      if (fp16_tag_o !== 8'h16) $fatal(1, "FP16 tag mismatch: actual=0x%02h", fp16_tag_o);
      @(posedge clk);
    end
  endtask

  initial begin
    fp64_ar = '0; fp64_ai = '0; fp64_br = '0; fp64_bi = '0; fp64_cr = '0; fp64_ci = '0;
    fp32_ar = '0; fp32_ai = '0; fp32_br = '0; fp32_bi = '0; fp32_cr = '0; fp32_ci = '0;
    fp16_ar = '0; fp16_ai = '0; fp16_br = '0; fp16_bi = '0; fp16_cr = '0; fp16_ci = '0;
    fp64_valid = 1'b0; fp32_valid = 1'b0; fp16_valid = 1'b0;
    fp64_result_ready = 1'b1; fp32_result_ready = 1'b1; fp16_result_ready = 1'b1;
    fp64_flush = 1'b0; fp32_flush = 1'b0; fp16_flush = 1'b0;
    fp64_tag_i = '0; fp32_tag_i = '0; fp16_tag_i = '0;

    wait (rst_n === 1'b1);
    @(posedge clk);
    run_fp64_directed();
    run_fp32_directed();
    run_fp16_directed();
    $display("fpnew_complex_fma_tb: PASS directed FP64/FP32/FP16 arithmetic checks");
    $finish;
  end
endmodule
