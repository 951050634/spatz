// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

package online_merge_fp32_helpers;

  typedef logic [31:0] fp32_bits_t;
  typedef logic [23:0] q1_23_t;

  localparam fp32_bits_t FP32_POS_ZERO = 32'h0000_0000;
  localparam fp32_bits_t FP32_ONE      = 32'h3f80_0000;
  localparam fp32_bits_t FP32_MAX_FIN  = 32'h7f7f_ffff;
  localparam q1_23_t     Q1_23_ONE     = 24'h80_0000;
  localparam q1_23_t     Q1_23_ZERO    = 24'h00_0000;

  function automatic logic fp32_is_nan_or_inf(input fp32_bits_t value);
    fp32_is_nan_or_inf = (value[30:23] == 8'hff);
  endfunction

  function automatic logic fp32_is_zero(input fp32_bits_t value);
    fp32_is_zero = (value[30:0] == 31'd0);
  endfunction

  function automatic logic fp32_is_finite(input fp32_bits_t value);
    fp32_is_finite = !fp32_is_nan_or_inf(value);
  endfunction

  function automatic logic fp32_is_positive_finite_normal(input fp32_bits_t value);
    fp32_is_positive_finite_normal =
        !value[31] && (value[30:23] != 8'd0) && (value[30:23] != 8'hff);
  endfunction

  function automatic logic fp32_is_negative_finite(input fp32_bits_t value);
    fp32_is_negative_finite = value[31] && fp32_is_finite(value);
  endfunction

  function automatic logic fp32_is_positive_finite(input fp32_bits_t value);
    fp32_is_positive_finite = !value[31] && fp32_is_finite(value) && !fp32_is_zero(value);
  endfunction

  function automatic logic [16:0] fp32_abs_to_exp_pos_q8(input fp32_bits_t value);
    logic [23:0] significand;
    int signed shift;
    logic [55:0] wide;
    begin
      if (value[30:23] == 8'd0) begin
        fp32_abs_to_exp_pos_q8 = 17'd0;
      end else begin
        significand = {1'b1, value[22:0]};
        shift = int'(value[30:23]) - 127 + 13;
        if (shift < 0) begin
          fp32_abs_to_exp_pos_q8 = 17'd0;
        end else if (shift >= 17) begin
          fp32_abs_to_exp_pos_q8 = 17'd65536;
        end else begin
          wide = {32'd0, significand};
          fp32_abs_to_exp_pos_q8 = 17'((wide << shift) >> 23);
        end
      end
    end
  endfunction

  function automatic fp32_bits_t q1_23_scaled_to_fp32(
    input q1_23_t value,
    input logic [7:0] exponent_bits
  );
    logic [24:0] norm;
    begin
      if (value == Q1_23_ZERO) begin
        q1_23_scaled_to_fp32 = FP32_POS_ZERO;
      end else if (value == Q1_23_ONE) begin
        q1_23_scaled_to_fp32 = {1'b0, exponent_bits, 23'd0};
      end else begin
        norm = {value, 1'b0};
        q1_23_scaled_to_fp32 = {1'b0, exponent_bits - 8'd1, norm[22:0]};
      end
    end
  endfunction

endpackage
