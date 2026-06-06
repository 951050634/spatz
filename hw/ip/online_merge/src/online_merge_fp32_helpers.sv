// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

package online_merge_fp32_helpers;

  typedef logic [31:0] fp32_bits_t;
  typedef logic [23:0] q1_23_t;
  typedef logic [47:0] uq16_16_t;
  typedef logic signed [47:0] sq16_16_t;

  localparam int unsigned UQ_FRAC_BITS = 32;

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

  function automatic logic fp32_is_finite_normal_or_zero(input fp32_bits_t value);
    fp32_is_finite_normal_or_zero =
        fp32_is_zero(value) || ((value[30:23] != 8'd0) && (value[30:23] != 8'hff));
  endfunction

  function automatic logic fp32_is_nonnegative_finite_normal_or_zero(input fp32_bits_t value);
    fp32_is_nonnegative_finite_normal_or_zero =
        !value[31] && fp32_is_finite_normal_or_zero(value);
  endfunction

  function automatic uq16_16_t fp32_abs_to_uq16_16(input fp32_bits_t value);
    logic [23:0] significand;
    logic [79:0] wide;
    int signed shift;
    begin
      if (fp32_is_zero(value)) begin
        fp32_abs_to_uq16_16 = '0;
      end else begin
        significand = {1'b1, value[22:0]};
        shift = int'(value[30:23]) + int'(UQ_FRAC_BITS) - 150;
        wide = {56'd0, significand};
        if (shift >= 0) begin
          fp32_abs_to_uq16_16 = uq16_16_t'(wide << shift);
        end else begin
          fp32_abs_to_uq16_16 = uq16_16_t'(wide >> -shift);
        end
      end
    end
  endfunction

  function automatic sq16_16_t fp32_to_sq16_16(input fp32_bits_t value);
    uq16_16_t abs_value;
    begin
      abs_value = fp32_abs_to_uq16_16(value);
      fp32_to_sq16_16 = value[31] ? -sq16_16_t'(abs_value) : sq16_16_t'(abs_value);
    end
  endfunction

  function automatic fp32_bits_t uq16_16_to_fp32(input uq16_16_t value);
    int msb;
    logic [47:0] mag;
    logic [47:0] norm;
    logic [7:0] exponent_bits;
    begin
      if (value == '0) begin
        uq16_16_to_fp32 = FP32_POS_ZERO;
      end else begin
        mag = value;
        msb = 0;
        for (int i = 0; i < 48; i++) begin
          if (mag[i]) begin
            msb = i;
          end
        end
        exponent_bits = 8'(msb - int'(UQ_FRAC_BITS) + 127);
        if (msb >= 23) begin
          norm = mag >> (msb - 23);
        end else begin
          norm = mag << (23 - msb);
        end
        uq16_16_to_fp32 = {1'b0, exponent_bits, norm[22:0]};
      end
    end
  endfunction

  function automatic fp32_bits_t sq16_16_to_fp32(input sq16_16_t value);
    uq16_16_t mag;
    fp32_bits_t abs_bits;
    begin
      if (value < 0) begin
        mag = uq16_16_t'(-value);
        abs_bits = uq16_16_to_fp32(mag);
        sq16_16_to_fp32 = {1'b1, abs_bits[30:0]};
      end else begin
        sq16_16_to_fp32 = uq16_16_to_fp32(uq16_16_t'(value));
      end
    end
  endfunction

  function automatic uq16_16_t q1_23_mul_uq16_16(
    input uq16_16_t lhs,
    input q1_23_t rhs
  );
    logic [71:0] product;
    begin
      product = {24'd0, lhs} * {48'd0, rhs};
      q1_23_mul_uq16_16 = uq16_16_t'(product >> 23);
    end
  endfunction

  function automatic uq16_16_t q1_23_scaled_mul_uq16_16(
    input uq16_16_t lhs,
    input q1_23_t rhs,
    input logic signed [9:0] scale_exp
  );
    logic [71:0] product;
    uq16_16_t scaled;
    begin
      product = {24'd0, lhs} * {48'd0, rhs};
      scaled = uq16_16_t'(product >> 23);
      if (scale_exp > 0) begin
        q1_23_scaled_mul_uq16_16 = scaled << scale_exp;
      end else begin
        q1_23_scaled_mul_uq16_16 = scaled >> -scale_exp;
      end
    end
  endfunction

  function automatic sq16_16_t sq16_16_mul_weight(
    input sq16_16_t value,
    input uq16_16_t weight
  );
    logic sign;
    uq16_16_t abs_value;
    logic [95:0] product;
    uq16_16_t scaled_abs;
    begin
      sign = value < 0;
      abs_value = sign ? uq16_16_t'(-value) : uq16_16_t'(value);
      product = {48'd0, abs_value} * {48'd0, weight};
      scaled_abs = uq16_16_t'(product >> UQ_FRAC_BITS);
      sq16_16_mul_weight = sign ? -sq16_16_t'(scaled_abs) : sq16_16_t'(scaled_abs);
    end
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
