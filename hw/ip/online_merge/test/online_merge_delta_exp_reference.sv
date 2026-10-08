// Frozen pre-optimization normalization reference; test-only.
// Source SHA256: 05ffa836746856b82949db7dfd83ac71ea1b7683dc9276e62d1448b702f411ae
// The exponential ROM is shared because its table and logic are unchanged.
module online_merge_fp16_delta_exp_reference (
  input  online_merge_fp32_helpers::fp16_bits_t loser_i,
  input  online_merge_fp32_helpers::fp16_bits_t winner_i,
  output logic [7:0]                            address_o,
  output logic [15:0]                           exp_q1_14_o,
  output logic                                  valid_o,
  output logic                                  saturated_o,
  output logic                                  unsupported_o
);

  import online_merge_fp32_helpers::*;

  logic [7:0] lut_index;
  logic lut_unity, lut_zero, lut_valid, lut_saturated, lut_unsupported;
  logic sign_loser, sign_winner;
  logic [4:0] exp_loser, exp_winner;
  logic [9:0] frac_loser, frac_winner;
  logic [10:0] sig_loser, sig_winner, sig_hi, sig_lo;
  logic signed [6:0] e_loser, e_winner, e_hi, e_lo, e_norm;
  logic [14:0] raw_hi, raw_lo, aligned_lo, magnitude;
  logic [5:0] align_shift;
  logic [15:0] rounded_sig, rounded_subnormal;
  logic [4:0] out_exp;
  logic [9:0] out_frac;
  logic [10:0] address_sig;
  logic signed [6:0] address_exp;
  logic signed [7:0] address_shift;
  logic [31:0] scaled_abs;

  function automatic logic [15:0] round_shift_15(
    input logic [14:0] value,
    input int unsigned shift
  );
    logic [15:0] base, remainder, halfway, mask;
    begin
      if (shift == 0) begin
        round_shift_15 = {1'b0, value};
      end else if (shift >= 16) begin
        round_shift_15 = 16'd0;
      end else begin
        mask = (16'd1 << shift) - 16'd1;
        base = {1'b0, value} >> shift;
        remainder = {1'b0, value} & mask;
        halfway = 16'd1 << (shift - 1);
        if ((remainder > halfway) ||
            ((remainder == halfway) && base[0])) begin
          round_shift_15 = base + 16'd1;
        end else begin
          round_shift_15 = base;
        end
      end
    end
  endfunction

  always_comb begin
    lut_index = 8'd0;
    lut_unity = 1'b0;
    lut_zero = 1'b0;
    lut_valid = 1'b0;
    lut_saturated = 1'b0;
    lut_unsupported = 1'b0;
    sign_loser = loser_i[15];
    sign_winner = winner_i[15];
    exp_loser = loser_i[14:10];
    exp_winner = winner_i[14:10];
    frac_loser = loser_i[9:0];
    frac_winner = winner_i[9:0];
    sig_loser = (exp_loser == 0) ? {1'b0, frac_loser} :
        {1'b1, frac_loser};
    sig_winner = (exp_winner == 0) ? {1'b0, frac_winner} :
        {1'b1, frac_winner};
    e_loser = (exp_loser == 0) ? -7'sd24 : $signed({1'b0, exp_loser}) -
        7'sd25;
    e_winner = (exp_winner == 0) ? -7'sd24 : $signed({1'b0, exp_winner}) -
        7'sd25;
    sig_hi = '0;
    sig_lo = '0;
    e_hi = '0;
    e_lo = '0;
    e_norm = '0;
    raw_hi = '0;
    raw_lo = '0;
    aligned_lo = '0;
    magnitude = '0;
    align_shift = '0;
    rounded_sig = '0;
    rounded_subnormal = '0;
    out_exp = '0;
    out_frac = '0;
    address_sig = '0;
    address_exp = '0;
    address_shift = '0;
    scaled_abs = '0;

    if (fp16_is_nan_or_inf(loser_i) || fp16_is_nan_or_inf(winner_i) ||
        fp16_lt(winner_i, loser_i)) begin
      // The fused interface is intentionally restricted to ordered finite
      // inputs.  This is the same unsupported result as an FP16 overflow or
      // NaN/Inf entering the existing mixed LUT.
      lut_unsupported = 1'b1;
    end else if (fp16_is_zero(loser_i) && fp16_is_zero(winner_i) ||
                 loser_i == winner_i) begin
      // Equal maxima, including +0/-0, bypass the ROM with exact unity.
      lut_valid = 1'b1;
      lut_unity = 1'b1;
    end else begin
      lut_valid = 1'b1;
      if ((e_loser > e_winner) ||
          ((e_loser == e_winner) && (sig_loser >= sig_winner))) begin
        sig_hi = sig_loser;
        sig_lo = sig_winner;
        e_hi = e_loser;
        e_lo = e_winner;
      end else begin
        sig_hi = sig_winner;
        sig_lo = sig_loser;
        e_hi = e_winner;
        e_lo = e_loser;
      end
      raw_hi = {1'b0, sig_hi, 3'b000};
      raw_lo = {1'b0, sig_lo, 3'b000};
      align_shift = 6'(e_hi - e_lo);
      if (align_shift == 0) begin
        aligned_lo = raw_lo;
      end else if (align_shift >= 15) begin
        aligned_lo = (raw_lo != 0) ? 15'd1 : 15'd0;
      end else begin
        aligned_lo = raw_lo >> align_shift;
        if ((raw_lo & ((15'd1 << align_shift) - 15'd1)) != 0) begin
          aligned_lo[0] = 1'b1;
        end
      end
      // Original same-sign operands subtract magnitudes; opposite signs
      // add them after b's sign is inverted by fp16_sub.
      if (sign_loser == sign_winner) begin
        magnitude = raw_hi - aligned_lo;
      end else begin
        magnitude = raw_hi + aligned_lo;
      end
      e_norm = e_hi;
      if (magnitude == 0) begin
        lut_unity = 1'b1;
      end else begin
        if (magnitude >= 15'd16384) begin
          magnitude = (magnitude >> 1) |
              (magnitude[0] ? 15'd1 : 15'd0);
          e_norm = e_norm + 1'b1;
        end
        for (int unsigned norm_iter = 0; norm_iter < 15; norm_iter++) begin
          if ((magnitude < 15'd8192) && (e_norm > -7'sd40)) begin
            magnitude = magnitude << 1;
            e_norm = e_norm - 1'b1;
          end
        end
        rounded_sig = round_shift_15(magnitude, 3);
        if (rounded_sig >= 16'd2048) begin
          rounded_sig = rounded_sig >> 1;
          e_norm = e_norm + 1'b1;
        end
        if (e_norm > 7'sd5) begin
          // A finite pair whose difference overflows FP16 maps to the same
          // unsupported state as online_merge_exp_mixed(-Inf).
          lut_valid = 1'b0;
          lut_unsupported = 1'b1;
        end else if (e_norm >= -7'sd24) begin
          out_exp = 5'(e_norm + 7'sd25);
          out_frac = rounded_sig[9:0];
        end else begin
          rounded_subnormal = round_shift_15(magnitude,
              3 + (-int'(e_norm) - 24));
          if (rounded_subnormal >= 16'd1024) begin
            out_exp = 5'd1;
            out_frac = 10'd0;
          end else begin
            out_exp = 5'd0;
            out_frac = rounded_subnormal[9:0];
          end
        end

        if (lut_valid && !lut_unsupported) begin
          if ((out_exp == 0) && (out_frac == 0)) begin
            // fp16_sub may produce signed zero after underflow; both signs
            // are exact winner identities in the existing LUT path.
            lut_unity = 1'b1;
          end else begin
            address_sig = (out_exp == 0) ? {1'b0, out_frac} :
                {1'b1, out_frac};
            address_exp = (out_exp == 0) ? -7'sd24 :
                $signed({1'b0, out_exp}) - 7'sd25;
            address_shift = address_exp + 7'sd5;
            if (address_shift >= 0) begin
              scaled_abs = {21'd0, address_sig} << address_shift;
            end else begin
              if (-address_shift >= 32) begin
                scaled_abs = (address_sig != 0) ? 32'd1 : 32'd0;
              end else begin
                scaled_abs = ({21'd0, address_sig} +
                    (32'd1 << (-address_shift)) - 32'd1) >>
                    (-address_shift);
              end
            end
            if (scaled_abs >= 256) begin
              lut_index = 8'd0;
            end else begin
              lut_index = 8'(256 - scaled_abs);
            end
            // -8 exactly is LUT[0]; only a rounded result strictly greater
            // than eight is saturated to zero.
            if ((out_exp > 5'd18) ||
                ((out_exp == 5'd18) && (out_frac != 0))) begin
              lut_zero = 1'b1;
              lut_saturated = 1'b1;
            end
          end
        end
      end
    end
  end

  online_merge_exp_mixed_rom i_rom (
    .index_i       (lut_index),
    .unity_i       (lut_unity),
    .zero_i        (lut_zero),
    .valid_i       (lut_valid),
    .saturated_i   (lut_saturated),
    .unsupported_i (lut_unsupported),
    .exp_q1_14_o   (exp_q1_14_o),
    .valid_o       (valid_o),
    .saturated_o   (saturated_o),
    .unsupported_o (unsupported_o)
  );
  assign address_o = lut_index;
endmodule
