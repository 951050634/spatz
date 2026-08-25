// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

package online_merge_fp32_helpers;

  typedef logic [31:0] fp32_bits_t;
  typedef logic [15:0] fp16_bits_t;
  typedef logic [15:0] q1_15_t;
  typedef logic [23:0] q1_23_t;
  typedef logic [47:0] uq16_16_t;
  typedef logic signed [47:0] sq16_16_t;

  localparam int unsigned UQ_FRAC_BITS = 32;

  localparam fp32_bits_t FP32_POS_ZERO = 32'h0000_0000;
  localparam fp32_bits_t FP32_ONE      = 32'h3f80_0000;
  localparam fp32_bits_t FP32_MAX_FIN  = 32'h7f7f_ffff;
  localparam fp16_bits_t FP16_POS_ZERO = 16'h0000;
  localparam fp16_bits_t FP16_ONE      = 16'h3c00;
  localparam fp16_bits_t FP16_NEG_EIGHT = 16'hc800;
  localparam fp16_bits_t FP16_POS_INF  = 16'h7c00;
  localparam fp16_bits_t FP16_NEG_INF  = 16'hfc00;
  localparam q1_23_t     Q1_23_ONE     = 24'h80_0000;
  localparam q1_23_t     Q1_23_ZERO    = 24'h00_0000;
  localparam q1_15_t     Q1_15_ONE     = 16'h8000;
  localparam q1_15_t     Q1_15_HALF    = 16'h4000;
  localparam q1_15_t     Q1_15_ZERO    = 16'h0000;

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

  function automatic logic fp32_fits_uq16_16(input fp32_bits_t value);
    // A non-negative FP32 normal with unbiased exponent <= 15 is representable
    // in the 16-integer-bit Q16.32 carrier.  Zero is included explicitly.
    fp32_fits_uq16_16 = fp32_is_nonnegative_finite_normal_or_zero(value) &&
        ((value[30:23] == 8'd0) || (value[30:23] <= 8'd142));
  endfunction

  // Binary16 helpers used only by the mixed-precision datapath.  The legacy
  // fixed-point/FP32 functions above are intentionally left untouched.  All
  // conversions below use round-to-nearest, ties-to-even (RNE).
  function automatic logic fp16_is_nan_or_inf(input fp16_bits_t value);
    fp16_is_nan_or_inf = (value[14:10] == 5'h1f);
  endfunction

  function automatic logic fp16_is_zero(input fp16_bits_t value);
    fp16_is_zero = (value[14:0] == 15'd0);
  endfunction

  function automatic logic fp16_is_finite(input fp16_bits_t value);
    fp16_is_finite = !fp16_is_nan_or_inf(value);
  endfunction

  function automatic logic [63:0] round_shift_u64(
    input logic [63:0] value,
    input int unsigned shift
  );
    logic [63:0] base;
    logic [63:0] remainder;
    logic [63:0] halfway;
    logic [63:0] mask;
    begin
      if (shift == 0) begin
        round_shift_u64 = value;
      end else if (shift >= 64) begin
        // The input is finite and the discarded field is wider than the
        // source.  This branch is useful for FP32 subnormal -> FP16.
        // No finite 64-bit source can reach the halfway point when the
        // discarded shift is at least 64 bits.
        round_shift_u64 = 64'd0;
      end else begin
        mask = (64'h1 << shift) - 64'd1;
        base = value >> shift;
        remainder = value & mask;
        halfway = 64'h1 << (shift - 1);
        if ((remainder > halfway) ||
            ((remainder == halfway) && base[0])) begin
          round_shift_u64 = base + 64'd1;
        end else begin
          round_shift_u64 = base;
        end
      end
    end
  endfunction

  function automatic fp16_bits_t fp32_to_fp16_rne(input fp32_bits_t value);
    logic sign;
    logic [7:0] exp32;
    logic [22:0] frac32;
    logic [63:0] significand;
    logic [63:0] rounded;
    int signed unbiased;
    int unsigned shift;
    logic [5:0] exp16;
    begin
      sign = value[31];
      exp32 = value[30:23];
      frac32 = value[22:0];
      if (exp32 == 8'hff) begin
        if (frac32 == 23'd0) begin
          fp32_to_fp16_rne = {sign, 5'h1f, 10'd0};
        end else begin
          fp32_to_fp16_rne = {sign, 5'h1f, 10'h200};
        end
      end else if (exp32 == 8'd0) begin
        // The smallest FP32 subnormal is far below a binary16 subnormal.
        fp32_to_fp16_rne = {sign, 15'd0};
      end else begin
        unbiased = int'(exp32) - 127;
        significand = {40'd0, 1'b1, frac32};
        if (unbiased > 15) begin
          fp32_to_fp16_rne = {sign, 5'h1f, 10'd0};
        end else if (unbiased >= -14) begin
          rounded = round_shift_u64(significand, 13);
          exp16 = 6'(unbiased + 15);
          if (rounded >= 64'd2048) begin
            rounded = rounded >> 1;
            exp16 = exp16 + 1'b1;
          end
          if (exp16 >= 6'h1f) begin
            fp32_to_fp16_rne = {sign, 5'h1f, 10'd0};
          end else begin
            fp32_to_fp16_rne = {sign, exp16[4:0], rounded[9:0]};
          end
        end else begin
          // Half subnormals are integer multiples of 2^-24.  For an FP32
          // normal value, significand * 2^(unbiased+1) is that integer.
          shift = -(unbiased + 1);
          rounded = round_shift_u64(significand, shift);
          if (rounded >= 64'd1024) begin
            fp32_to_fp16_rne = {sign, 5'd1, 10'd0};
          end else begin
            fp32_to_fp16_rne = {sign, 5'd0, rounded[9:0]};
          end
        end
      end
    end
  endfunction

  function automatic fp32_bits_t fp16_to_fp32(input fp16_bits_t value);
    logic sign;
    logic [4:0] exp16;
    logic [9:0] frac16;
    logic [9:0] subnormal;
    logic [23:0] normalized;
    int msb;
    int signed unbiased;
    begin
      sign = value[15];
      exp16 = value[14:10];
      frac16 = value[9:0];
      if (exp16 == 5'h1f) begin
        // Preserve the binary16 payload in the high ten bits of the FP32
        // fraction.  The low thirteen bits are the newly appended zeros.
        fp16_to_fp32 = {sign, 8'hff, frac16, 13'd0};
      end else if ((exp16 == 5'd0) && (frac16 == 10'd0)) begin
        fp16_to_fp32 = {sign, 31'd0};
      end else if (exp16 == 5'd0) begin
        subnormal = frac16;
        msb = 0;
        for (int i = 0; i < 10; i++) begin
          if (subnormal[i]) begin
            msb = i;
          end
        end
        unbiased = msb - 24;
        normalized = {14'd0, subnormal} << (23 - msb);
        fp16_to_fp32 = {sign, 8'(unbiased + 127), normalized[22:0]};
      end else begin
        unbiased = int'(exp16) - 15;
        fp16_to_fp32 = {sign, 8'(unbiased + 127), frac16, 13'd0};
      end
    end
  endfunction

  function automatic logic fp16_lt(input fp16_bits_t lhs, input fp16_bits_t rhs);
    logic lhs_sign, rhs_sign;
    begin
      lhs_sign = lhs[15];
      rhs_sign = rhs[15];
      if (lhs == rhs) begin
        fp16_lt = 1'b0;
      end else if (fp16_is_zero(lhs) && fp16_is_zero(rhs)) begin
        fp16_lt = 1'b0;
      end else if (lhs_sign != rhs_sign) begin
        fp16_lt = lhs_sign;
      end else if (lhs_sign) begin
        fp16_lt = lhs > rhs;
      end else begin
        fp16_lt = lhs < rhs;
      end
    end
  endfunction

  function automatic fp16_bits_t fp16_add_sub(
    input fp16_bits_t a,
    input fp16_bits_t b,
    input logic subtract_b
  );
    logic sign_a, sign_b;
    logic [4:0] exp_a, exp_b;
    logic [9:0] frac_a, frac_b;
    logic [10:0] sig_a, sig_b;
    logic [10:0] sig_hi, sig_lo;
    logic sign_hi, sign_lo;
    int signed e_a, e_b, e_hi, e_lo;
    logic signed [64:0] signed_sum_ext;
    logic signed [63:0] signed_sum;
    logic [63:0] magnitude;
    logic [63:0] aligned_lo;
    logic [63:0] rounded;
    logic result_sign;
    logic [4:0] exp_out;
    int unsigned shift;
    int signed e_out;
    begin
      sign_a = a[15];
      sign_b = b[15] ^ subtract_b;
      exp_a = a[14:10];
      exp_b = b[14:10];
      frac_a = a[9:0];
      frac_b = b[9:0];
      sig_a = (exp_a == 0) ? {1'b0, frac_a} : {1'b1, frac_a};
      sig_b = (exp_b == 0) ? {1'b0, frac_b} : {1'b1, frac_b};
      e_a = (exp_a == 0) ? -24 : int'(exp_a) - 25;
      e_b = (exp_b == 0) ? -24 : int'(exp_b) - 25;
      // Zero is handled before normalization; retaining its sign here does
      // not affect the positive mixed datapath.
      if ((sig_a == 0) && (sig_b == 0)) begin
        // Canonicalize every zero-minus-zero result to +0.  In particular,
        // +0 - +0 must not inherit a sign from the second operand.
        fp16_add_sub = FP16_POS_ZERO;
      end else if (sig_a == 0) begin
        fp16_add_sub = {sign_b, b[14:0]};
      end else if (sig_b == 0) begin
        fp16_add_sub = {sign_a, a[14:0]};
      end else begin
        // Put the larger exponent first and align with three guard bits.
        if ((e_a > e_b) || ((e_a == e_b) && (sig_a >= sig_b))) begin
          sig_hi = sig_a;
          sig_lo = sig_b;
          e_hi = e_a;
          e_lo = e_b;
          sign_hi = sign_a;
          sign_lo = sign_b;
        end else begin
          sig_hi = sig_b;
          sig_lo = sig_a;
          e_hi = e_b;
          e_lo = e_a;
          sign_hi = sign_b;
          sign_lo = sign_a;
        end
        aligned_lo = {50'd0, sig_lo, 3'b000};
        shift = (e_hi > e_lo) ? (e_hi - e_lo) : 0;
        if (shift != 0) begin
          if (shift >= 64) begin
            aligned_lo = (aligned_lo != 0) ? 64'd1 : 64'd0;
          end else if ((aligned_lo & ((64'h1 << shift) - 1)) != 0) begin
            aligned_lo = (aligned_lo >> shift) | 64'd1;
          end else begin
            aligned_lo = aligned_lo >> shift;
          end
        end
        if (sign_a == sign_b) begin
          signed_sum_ext = $signed({1'b0, {50'd0, sig_hi, 3'b000}}) +
              $signed({1'b0, aligned_lo});
          result_sign = sign_a;
        end else if ({50'd0, sig_hi, 3'b000} >= aligned_lo) begin
          signed_sum_ext = $signed({1'b0, {50'd0, sig_hi, 3'b000}}) -
              $signed({1'b0, aligned_lo});
          result_sign = sign_hi;
        end else begin
          signed_sum_ext = $signed({1'b0, aligned_lo}) -
              $signed({1'b0, {50'd0, sig_hi, 3'b000}});
          result_sign = sign_lo;
        end
        signed_sum = signed_sum_ext[63:0];
        if (signed_sum == 0) begin
          fp16_add_sub = FP16_POS_ZERO;
        end else begin
          if (signed_sum < 0) begin
            magnitude = -signed_sum;
          end else begin
            magnitude = signed_sum;
          end
          e_out = e_hi;
          // Use statically bounded loops here.  The arithmetic bounds require
          // at most 40 iterations, and a fixed trip count also keeps synthesis
          // frontends from attempting an unbounded procedural-loop expansion.
          for (int unsigned norm_iter = 0; norm_iter < 64; norm_iter++) begin
            if ((magnitude >= (64'd2048 << 3)) && (e_out < 32)) begin
              magnitude = (magnitude >> 1) | (magnitude[0] ? 64'd1 : 64'd0);
              e_out = e_out + 1;
            end
          end
          for (int unsigned norm_iter = 0; norm_iter < 64; norm_iter++) begin
            if ((magnitude < (64'd1024 << 3)) && (e_out > -40)) begin
              magnitude = magnitude << 1;
              e_out = e_out - 1;
            end
          end
          // e_out is the exponent of the integer significand (value is
          // significand * 2^(e_out-10)); binary16 encodes it as e_out+25.
          if (e_out > 5) begin
            fp16_add_sub = {result_sign, 5'h1f, 10'd0};
          end else if (e_out >= -24) begin
            rounded = round_shift_u64(magnitude, 3);
            if (rounded >= 2048) begin
              rounded = rounded >> 1;
              e_out = e_out + 1;
            end
            exp_out = 5'(e_out + 25);
            fp16_add_sub = {result_sign, exp_out, rounded[9:0]};
          end else begin
            shift = 3 + int'(-24 - e_out);
            rounded = round_shift_u64(magnitude, shift);
            if (rounded >= 1024) begin
              fp16_add_sub = {result_sign, 5'd1, 10'd0};
            end else begin
              fp16_add_sub = {result_sign, 5'd0, rounded[9:0]};
            end
          end
        end
      end
    end
  endfunction

  function automatic fp16_bits_t fp16_sub(
    input fp16_bits_t lhs,
    input fp16_bits_t rhs
  );
    fp16_sub = fp16_add_sub(lhs, rhs, 1'b1);
  endfunction

  function automatic q1_23_t q1_14_to_q1_23(input logic [15:0] value);
    logic [23:0] widened;
    begin
      widened = {8'd0, value};
      q1_14_to_q1_23 = q1_23_t'(widened << 9);
    end
  endfunction

  function automatic uq16_16_t fp16_to_uq16_16(input fp16_bits_t value);
    fp16_to_uq16_16 = fp32_abs_to_uq16_16(fp16_to_fp32(value));
  endfunction

  function automatic fp16_bits_t uq16_16_to_fp16(input uq16_16_t value);
    logic [63:0] wide_value;
    logic [63:0] rounded;
    int msb;
    int signed exponent;
    int unsigned shift;
    begin
      wide_value = {16'd0, value};
      if (value == '0) begin
        uq16_16_to_fp16 = FP16_POS_ZERO;
      end else begin
        msb = 0;
        for (int i = 0; i < 48; i++) begin
          if (value[i]) begin
            msb = i;
          end
        end
        exponent = msb - int'(UQ_FRAC_BITS);
        if (exponent >= -14) begin
          // Keep the eleven-bit significand, rounding the discarded Q16.32
          // carrier bits directly.  This avoids an intermediate FP32
          // conversion that can lose the Q16.32 midpoint bit.
          shift = (msb > 10) ? (msb - 10) : 0;
          rounded = round_shift_u64(wide_value, shift);
          if (rounded >= 64'd2048) begin
            rounded = rounded >> 1;
            exponent = exponent + 1;
          end
          if (exponent > 15) begin
            uq16_16_to_fp16 = FP16_POS_INF;
          end else begin
            uq16_16_to_fp16 = {1'b0, 5'(exponent + 15), rounded[9:0]};
          end
        end else begin
          // Binary16 subnormals have a Q16.32 code spacing of 2^8.
          rounded = round_shift_u64(wide_value, 8);
          if (rounded >= 64'd1024) begin
            uq16_16_to_fp16 = 16'h0400;
          end else begin
            uq16_16_to_fp16 = {6'd0, rounded[9:0]};
          end
        end
      end
    end
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
