// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Standalone directed/reference-style testbench for fpnew_complex_fma.
//
// The matrix checks the v2 arithmetic contract against explicit bit-level
// expectations for exact finite cases, signed zero, infinities, quiet NaNs,
// invalid-operation flags, rounding-mode effects, tag propagation, and result
// backpressure:
//   real = c.real + a.real * b.real - a.imag * b.imag
//   imag = c.imag + a.imag * b.real + a.real * b.imag

`timescale 1ns/1ps

module fpnew_complex_fma_tb;
  import fpnew_pkg::*;

  typedef enum logic [1:0] {
    EXPECT_BITS,
    EXPECT_NAN,
    EXPECT_ANY
  } value_expect_e;

  typedef enum logic [1:0] {
    EXPECT_STATUS_CLEAR,
    EXPECT_STATUS_NX_ONLY,
    EXPECT_STATUS_NV_ONLY,
    EXPECT_STATUS_ANY
  } status_expect_e;

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
  logic [63:0]            fp64_ar, fp64_ai, fp64_br, fp64_bi, fp64_cr, fp64_ci;
  logic                   fp64_valid, fp64_ready, fp64_flush;
  logic [63:0]            fp64_real, fp64_imag;
  status_t                fp64_status;
  logic                   fp64_result_valid, fp64_result_ready, fp64_busy;
  logic [7:0]             fp64_tag_i, fp64_tag_o;
  fpnew_pkg::roundmode_e  fp64_rnd;

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
    .rnd_mode_i(fp64_rnd),
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
  logic [31:0]            fp32_ar, fp32_ai, fp32_br, fp32_bi, fp32_cr, fp32_ci;
  logic                   fp32_valid, fp32_ready, fp32_flush;
  logic [31:0]            fp32_real, fp32_imag;
  status_t                fp32_status;
  logic                   fp32_result_valid, fp32_result_ready, fp32_busy;
  logic [7:0]             fp32_tag_i, fp32_tag_o;
  fpnew_pkg::roundmode_e  fp32_rnd;

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
    .rnd_mode_i(fp32_rnd),
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
  logic [15:0]            fp16_ar, fp16_ai, fp16_br, fp16_bi, fp16_cr, fp16_ci;
  logic                   fp16_valid, fp16_ready, fp16_flush;
  logic [15:0]            fp16_real, fp16_imag;
  status_t                fp16_status;
  logic                   fp16_result_valid, fp16_result_ready, fp16_busy;
  logic [7:0]             fp16_tag_i, fp16_tag_o;
  fpnew_pkg::roundmode_e  fp16_rnd;

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
    .rnd_mode_i(fp16_rnd),
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

  function automatic logic status_clear(status_t st);
    return !(st.NV | st.DZ | st.OF | st.UF | st.NX);
  endfunction

  function automatic logic status_nx_only(status_t st);
    return st.NX && !(st.NV | st.DZ | st.OF | st.UF);
  endfunction

  function automatic logic status_nv_only(status_t st);
    return st.NV && !(st.DZ | st.OF | st.UF | st.NX);
  endfunction

  function automatic logic is_nan64(logic [63:0] value);
    return (&value[62:52]) && (|value[51:0]);
  endfunction

  function automatic logic is_nan32(logic [31:0] value);
    return (&value[30:23]) && (|value[22:0]);
  endfunction

  function automatic logic is_nan16(logic [15:0] value);
    return (&value[14:10]) && (|value[9:0]);
  endfunction

  task automatic check_status(input string name, input status_t actual,
                              input status_expect_e expected_status_mode);
    begin
      unique case (expected_status_mode)
        EXPECT_STATUS_CLEAR:
          if (!status_clear(actual))
            $fatal(1, "%s status mismatch: actual=%b expected=CLEAR", name, actual);
        EXPECT_STATUS_NX_ONLY:
          if (!status_nx_only(actual))
            $fatal(1, "%s status mismatch: actual=%b expected=NX_ONLY", name, actual);
        EXPECT_STATUS_NV_ONLY:
          if (!status_nv_only(actual))
            $fatal(1, "%s status mismatch: actual=%b expected=NV_ONLY", name, actual);
        default: ;
      endcase
    end
  endtask

  task automatic check_value64(input string name, input string part, input logic [63:0] actual,
                               input value_expect_e mode, input logic [63:0] expected);
    begin
      unique case (mode)
        EXPECT_BITS:
          if (actual !== expected)
            $fatal(1, "%s FP64 %s mismatch: actual=0x%016h expected=0x%016h",
                   name, part, actual, expected);
        EXPECT_NAN:
          if (!is_nan64(actual))
            $fatal(1, "%s FP64 %s mismatch: actual=0x%016h expected=NaN", name, part, actual);
        default: ;
      endcase
    end
  endtask

  task automatic check_value32(input string name, input string part, input logic [31:0] actual,
                               input value_expect_e mode, input logic [31:0] expected);
    begin
      unique case (mode)
        EXPECT_BITS:
          if (actual !== expected)
            $fatal(1, "%s FP32 %s mismatch: actual=0x%08h expected=0x%08h",
                   name, part, actual, expected);
        EXPECT_NAN:
          if (!is_nan32(actual))
            $fatal(1, "%s FP32 %s mismatch: actual=0x%08h expected=NaN", name, part, actual);
        default: ;
      endcase
    end
  endtask

  task automatic check_value16(input string name, input string part, input logic [15:0] actual,
                               input value_expect_e mode, input logic [15:0] expected);
    begin
      unique case (mode)
        EXPECT_BITS:
          if (actual !== expected)
            $fatal(1, "%s FP16 %s mismatch: actual=0x%04h expected=0x%04h",
                   name, part, actual, expected);
        EXPECT_NAN:
          if (!is_nan16(actual))
            $fatal(1, "%s FP16 %s mismatch: actual=0x%04h expected=NaN", name, part, actual);
        default: ;
      endcase
    end
  endtask

  task automatic run_fp64_case(
    input string name,
    input fpnew_pkg::roundmode_e rnd,
    input logic [63:0] ar, input logic [63:0] ai,
    input logic [63:0] br, input logic [63:0] bi,
    input logic [63:0] cr, input logic [63:0] ci,
    input value_expect_e real_mode, input logic [63:0] expected_real,
    input value_expect_e imag_mode, input logic [63:0] expected_imag,
    input status_expect_e expected_status,
    input int unsigned hold_result_cycles = 0
  );
    int cycles;
    logic [63:0] held_real, held_imag;
    status_t held_status;
    begin
      fp64_ar = ar; fp64_ai = ai; fp64_br = br; fp64_bi = bi; fp64_cr = cr; fp64_ci = ci;
      fp64_rnd = rnd;
      fp64_tag_i = 8'h64;
      fp64_flush = 1'b0;
      fp64_result_ready = (hold_result_cycles == 0);
      fp64_valid = 1'b0;
      @(posedge clk);
      if (!fp64_ready) $fatal(1, "%s FP64 DUT not ready at test start", name);
      fp64_valid = 1'b1;
      @(posedge clk);
      fp64_valid = 1'b0;
      cycles = 0;
      while (!fp64_result_valid && cycles < 40) begin
        @(posedge clk);
        cycles++;
      end
      if (!fp64_result_valid) $fatal(1, "%s FP64 result did not become valid", name);
      held_real = fp64_real;
      held_imag = fp64_imag;
      held_status = fp64_status;
      repeat (hold_result_cycles) begin
        @(posedge clk);
        if (!fp64_result_valid) $fatal(1, "%s FP64 result_valid dropped under backpressure", name);
        if (fp64_real !== held_real || fp64_imag !== held_imag || fp64_status !== held_status)
          $fatal(1, "%s FP64 result changed under backpressure", name);
      end
      check_value64(name, "real", fp64_real, real_mode, expected_real);
      check_value64(name, "imag", fp64_imag, imag_mode, expected_imag);
      check_status(name, fp64_status, expected_status);
      if (fp64_tag_o !== 8'h64) $fatal(1, "%s FP64 tag mismatch: actual=0x%02h", name, fp64_tag_o);
      fp64_result_ready = 1'b1;
      @(posedge clk);
      $display("CASE PASS FP64 %-34s rnd=%0d real=0x%016h imag=0x%016h status=%b",
               name, rnd, fp64_real, fp64_imag, fp64_status);
    end
  endtask

  task automatic run_fp32_case(
    input string name,
    input fpnew_pkg::roundmode_e rnd,
    input logic [31:0] ar, input logic [31:0] ai,
    input logic [31:0] br, input logic [31:0] bi,
    input logic [31:0] cr, input logic [31:0] ci,
    input value_expect_e real_mode, input logic [31:0] expected_real,
    input value_expect_e imag_mode, input logic [31:0] expected_imag,
    input status_expect_e expected_status
  );
    int cycles;
    begin
      fp32_ar = ar; fp32_ai = ai; fp32_br = br; fp32_bi = bi; fp32_cr = cr; fp32_ci = ci;
      fp32_rnd = rnd;
      fp32_tag_i = 8'h32;
      fp32_flush = 1'b0;
      fp32_result_ready = 1'b1;
      fp32_valid = 1'b0;
      @(posedge clk);
      if (!fp32_ready) $fatal(1, "%s FP32 DUT not ready at test start", name);
      fp32_valid = 1'b1;
      @(posedge clk);
      fp32_valid = 1'b0;
      cycles = 0;
      while (!fp32_result_valid && cycles < 40) begin
        @(posedge clk);
        cycles++;
      end
      if (!fp32_result_valid) $fatal(1, "%s FP32 result did not become valid", name);
      check_value32(name, "real", fp32_real, real_mode, expected_real);
      check_value32(name, "imag", fp32_imag, imag_mode, expected_imag);
      check_status(name, fp32_status, expected_status);
      if (fp32_tag_o !== 8'h32) $fatal(1, "%s FP32 tag mismatch: actual=0x%02h", name, fp32_tag_o);
      @(posedge clk);
      $display("CASE PASS FP32 %-34s rnd=%0d real=0x%08h imag=0x%08h status=%b",
               name, rnd, fp32_real, fp32_imag, fp32_status);
    end
  endtask

  task automatic run_fp16_case(
    input string name,
    input fpnew_pkg::roundmode_e rnd,
    input logic [15:0] ar, input logic [15:0] ai,
    input logic [15:0] br, input logic [15:0] bi,
    input logic [15:0] cr, input logic [15:0] ci,
    input value_expect_e real_mode, input logic [15:0] expected_real,
    input value_expect_e imag_mode, input logic [15:0] expected_imag,
    input status_expect_e expected_status
  );
    int cycles;
    begin
      fp16_ar = ar; fp16_ai = ai; fp16_br = br; fp16_bi = bi; fp16_cr = cr; fp16_ci = ci;
      fp16_rnd = rnd;
      fp16_tag_i = 8'h16;
      fp16_flush = 1'b0;
      fp16_result_ready = 1'b1;
      fp16_valid = 1'b0;
      @(posedge clk);
      if (!fp16_ready) $fatal(1, "%s FP16 DUT not ready at test start", name);
      fp16_valid = 1'b1;
      @(posedge clk);
      fp16_valid = 1'b0;
      cycles = 0;
      while (!fp16_result_valid && cycles < 40) begin
        @(posedge clk);
        cycles++;
      end
      if (!fp16_result_valid) $fatal(1, "%s FP16 result did not become valid", name);
      check_value16(name, "real", fp16_real, real_mode, expected_real);
      check_value16(name, "imag", fp16_imag, imag_mode, expected_imag);
      check_status(name, fp16_status, expected_status);
      if (fp16_tag_o !== 8'h16) $fatal(1, "%s FP16 tag mismatch: actual=0x%02h", name, fp16_tag_o);
      @(posedge clk);
      $display("CASE PASS FP16 %-34s rnd=%0d real=0x%04h imag=0x%04h status=%b",
               name, rnd, fp16_real, fp16_imag, fp16_status);
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
    fp64_rnd = fpnew_pkg::RNE; fp32_rnd = fpnew_pkg::RNE; fp16_rnd = fpnew_pkg::RNE;

    wait (rst_n === 1'b1);
    @(posedge clk);

    // Original exact finite smoke tests: a=(1.5,2), b=(3,4), c=(5,6)
    run_fp64_case("exact_finite", fpnew_pkg::RNE,
                  64'h3ff8_0000_0000_0000, 64'h4000_0000_0000_0000,
                  64'h4008_0000_0000_0000, 64'h4010_0000_0000_0000,
                  64'h4014_0000_0000_0000, 64'h4018_0000_0000_0000,
                  EXPECT_BITS, 64'h3ff8_0000_0000_0000,
                  EXPECT_BITS, 64'h4032_0000_0000_0000,
                  EXPECT_STATUS_CLEAR, 0);
    run_fp32_case("exact_finite", fpnew_pkg::RNE,
                  32'h3fc0_0000, 32'h4000_0000, 32'h4040_0000, 32'h4080_0000,
                  32'h40a0_0000, 32'h40c0_0000,
                  EXPECT_BITS, 32'h3fc0_0000,
                  EXPECT_BITS, 32'h4190_0000,
                  EXPECT_STATUS_CLEAR);
    run_fp16_case("exact_finite", fpnew_pkg::RNE,
                  16'h3c00, 16'h4000, 16'h4200, 16'h4400, 16'h4500, 16'h4600,
                  EXPECT_BITS, 16'h0000,
                  EXPECT_BITS, 16'h4c00,
                  EXPECT_STATUS_CLEAR);

    // Signed-zero cases with independently determined real=-0 and imag=+0.
    run_fp64_case("signed_zero", fpnew_pkg::RNE,
                  64'h8000_0000_0000_0000, 64'h0000_0000_0000_0000,
                  64'h3ff0_0000_0000_0000, 64'h3ff0_0000_0000_0000,
                  64'h8000_0000_0000_0000, 64'h8000_0000_0000_0000,
                  EXPECT_BITS, 64'h8000_0000_0000_0000,
                  EXPECT_BITS, 64'h0000_0000_0000_0000,
                  EXPECT_STATUS_CLEAR, 0);
    run_fp32_case("signed_zero", fpnew_pkg::RNE,
                  32'h8000_0000, 32'h0000_0000, 32'h3f80_0000, 32'h3f80_0000,
                  32'h8000_0000, 32'h8000_0000,
                  EXPECT_BITS, 32'h8000_0000,
                  EXPECT_BITS, 32'h0000_0000,
                  EXPECT_STATUS_CLEAR);
    run_fp16_case("signed_zero", fpnew_pkg::RNE,
                  16'h8000, 16'h0000, 16'h3c00, 16'h3c00, 16'h8000, 16'h8000,
                  EXPECT_BITS, 16'h8000,
                  EXPECT_BITS, 16'h0000,
                  EXPECT_STATUS_CLEAR);

    // Inf propagation without invalid operation.
    run_fp64_case("inf_propagation", fpnew_pkg::RNE,
                  64'h7ff0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  64'h4000_0000_0000_0000, 64'h4008_0000_0000_0000,
                  64'h3ff0_0000_0000_0000, 64'h4010_0000_0000_0000,
                  EXPECT_BITS, 64'h7ff0_0000_0000_0000,
                  EXPECT_BITS, 64'h7ff0_0000_0000_0000,
                  EXPECT_STATUS_CLEAR, 0);
    run_fp32_case("inf_propagation", fpnew_pkg::RNE,
                  32'h7f80_0000, 32'h0000_0000, 32'h4000_0000, 32'h4040_0000,
                  32'h3f80_0000, 32'h4080_0000,
                  EXPECT_BITS, 32'h7f80_0000,
                  EXPECT_BITS, 32'h7f80_0000,
                  EXPECT_STATUS_CLEAR);
    run_fp16_case("inf_propagation", fpnew_pkg::RNE,
                  16'h7c00, 16'h0000, 16'h4000, 16'h4200, 16'h3c00, 16'h4400,
                  EXPECT_BITS, 16'h7c00,
                  EXPECT_BITS, 16'h7c00,
                  EXPECT_STATUS_CLEAR);

    // Quiet NaN propagation: payload is implementation-defined, so only assert NaN class.
    run_fp64_case("quiet_nan", fpnew_pkg::RNE,
                  64'h7ff8_0000_0000_1234, 64'h0000_0000_0000_0000,
                  64'h3ff0_0000_0000_0000, 64'h3ff0_0000_0000_0000,
                  64'h0000_0000_0000_0000, 64'h0000_0000_0000_0000,
                  EXPECT_NAN, '0,
                  EXPECT_NAN, '0,
                  EXPECT_STATUS_CLEAR, 0);
    run_fp32_case("quiet_nan", fpnew_pkg::RNE,
                  32'h7fc0_1234, 32'h0000_0000, 32'h3f80_0000, 32'h3f80_0000,
                  32'h0000_0000, 32'h0000_0000,
                  EXPECT_NAN, '0,
                  EXPECT_NAN, '0,
                  EXPECT_STATUS_CLEAR);
    run_fp16_case("quiet_nan", fpnew_pkg::RNE,
                  16'h7e01, 16'h0000, 16'h3c00, 16'h3c00, 16'h0000, 16'h0000,
                  EXPECT_NAN, '0,
                  EXPECT_NAN, '0,
                  EXPECT_STATUS_CLEAR);

    // Invalid operation: +Inf * +0 in the real path must raise NV and produce NaN real.
    run_fp64_case("invalid_inf_times_zero", fpnew_pkg::RNE,
                  64'h7ff0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  64'h0000_0000_0000_0000, 64'h3ff0_0000_0000_0000,
                  64'h0000_0000_0000_0000, 64'h0000_0000_0000_0000,
                  EXPECT_NAN, '0,
                  EXPECT_BITS, 64'h7ff0_0000_0000_0000,
                  EXPECT_STATUS_NV_ONLY, 0);
    run_fp32_case("invalid_inf_times_zero", fpnew_pkg::RNE,
                  32'h7f80_0000, 32'h0000_0000, 32'h0000_0000, 32'h3f80_0000,
                  32'h0000_0000, 32'h0000_0000,
                  EXPECT_NAN, '0,
                  EXPECT_BITS, 32'h7f80_0000,
                  EXPECT_STATUS_NV_ONLY);
    run_fp16_case("invalid_inf_times_zero", fpnew_pkg::RNE,
                  16'h7c00, 16'h0000, 16'h0000, 16'h3c00, 16'h0000, 16'h0000,
                  EXPECT_NAN, '0,
                  EXPECT_BITS, 16'h7c00,
                  EXPECT_STATUS_NV_ONLY);

    // Rounding tie: 1.0 + 2^-(precision) is exactly half an ulp above 1.0.
    run_fp64_case("round_tie_rne", fpnew_pkg::RNE,
                  64'h3ff0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  64'h3ca0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  64'h3ff0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  EXPECT_BITS, 64'h3ff0_0000_0000_0000,
                  EXPECT_BITS, 64'h0000_0000_0000_0000,
                  EXPECT_STATUS_NX_ONLY, 0);
    run_fp64_case("round_tie_rup_backpressure", fpnew_pkg::RUP,
                  64'h3ff0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  64'h3ca0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  64'h3ff0_0000_0000_0000, 64'h0000_0000_0000_0000,
                  EXPECT_BITS, 64'h3ff0_0000_0000_0001,
                  EXPECT_BITS, 64'h0000_0000_0000_0000,
                  EXPECT_STATUS_NX_ONLY, 3);
    run_fp32_case("round_tie_rne", fpnew_pkg::RNE,
                  32'h3f80_0000, 32'h0000_0000, 32'h3380_0000, 32'h0000_0000,
                  32'h3f80_0000, 32'h0000_0000,
                  EXPECT_BITS, 32'h3f80_0000,
                  EXPECT_BITS, 32'h0000_0000,
                  EXPECT_STATUS_NX_ONLY);
    run_fp32_case("round_tie_rup", fpnew_pkg::RUP,
                  32'h3f80_0000, 32'h0000_0000, 32'h3380_0000, 32'h0000_0000,
                  32'h3f80_0000, 32'h0000_0000,
                  EXPECT_BITS, 32'h3f80_0001,
                  EXPECT_BITS, 32'h0000_0000,
                  EXPECT_STATUS_NX_ONLY);
    run_fp16_case("round_tie_rne", fpnew_pkg::RNE,
                  16'h3c00, 16'h0000, 16'h1000, 16'h0000, 16'h3c00, 16'h0000,
                  EXPECT_BITS, 16'h3c00,
                  EXPECT_BITS, 16'h0000,
                  EXPECT_STATUS_NX_ONLY);
    run_fp16_case("round_tie_rup", fpnew_pkg::RUP,
                  16'h3c00, 16'h0000, 16'h1000, 16'h0000, 16'h3c00, 16'h0000,
                  EXPECT_BITS, 16'h3c01,
                  EXPECT_BITS, 16'h0000,
                  EXPECT_STATUS_NX_ONLY);

    $display("fpnew_complex_fma_tb: PASS extended FP64/FP32/FP16 directed matrix");
    $finish;
  end
endmodule
