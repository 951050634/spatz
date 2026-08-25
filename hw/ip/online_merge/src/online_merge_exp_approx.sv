// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

// LUT approximation of exp(x) for the online merge datapath.
// The supported design range is -8.0 <= x <= 0.0. Inputs above 0.0
// saturate to 1.0, inputs below -8.0 saturate to 0.0. The output is a
// linearly interpolated Q1.23 value.
module online_merge_exp_approx (
  input  online_merge_fp32_helpers::fp32_bits_t x_i,
  output online_merge_fp32_helpers::q1_23_t     exp_q1_23_o,
  output logic                                  valid_o,
  output logic                                  saturated_o,
  output logic                                  unsupported_o
);

  import online_merge_fp32_helpers::*;

  localparam q1_23_t ExpLut [0:256] = '{
    24'h800000, 24'h7c0fd6, 24'h783eb0, 24'h748b9b,
    24'h70f5a9, 24'h6d7bf5, 24'h6a1da0, 24'h66d9d4,
    24'h63afbe, 24'h609e96, 24'h5da595, 24'h5ac3fe,
    24'h57f918, 24'h554432, 24'h52a49c, 24'h5019b1,
    24'h4da2cc, 24'h4b3f50, 24'h48eea5, 24'h46b035,
    24'h448372, 24'h4267d0, 24'h405cc9, 24'h3e61d9,
    24'h3c7682, 24'h3a9a49, 24'h38ccb6, 24'h370d57,
    24'h355bbc, 24'h33b778, 24'h322022, 24'h309554,
    24'h2f16ac, 24'h2da3ca, 24'h2c3c51, 24'h2adfe8,
    24'h298e36, 24'h2846e9, 24'h2709ad, 24'h25d634,
    24'h24ac30, 24'h238b58, 24'h227363, 24'h21640b,
    24'h205d0c, 24'h1f5e25, 24'h1e6715, 24'h1d779f,
    24'h1c8f87, 24'h1bae94, 24'h1ad48c, 24'h1a0139,
    24'h193467, 24'h186de2, 24'h17ad78, 24'h16f2fb,
    24'h163e39, 24'h158f08, 24'h14e53b, 24'h1440a7,
    24'h13a123, 24'h130687, 24'h1270ae, 24'h11df70,
    24'h1152ab, 24'h10ca3a, 24'h1045fc, 24'h0fc5cf,
    24'h0f4994, 24'h0ed12c, 24'h0e5c78, 24'h0deb5b,
    24'h0d7db9, 24'h0d1376, 24'h0cac79, 24'h0c48a6,
    24'h0be7e6, 24'h0b8a20, 24'h0b2f3c, 24'h0ad725,
    24'h0a81c3, 24'h0a2f02, 24'h09decc, 24'h09910e,
    24'h0945b5, 24'h08fcad, 24'h08b5e4, 24'h087149,
    24'h082eca, 24'h07ee57, 24'h07afdf, 24'h077354,
    24'h0738a5, 24'h06ffc4, 24'h06c8a4, 24'h069336,
    24'h065f6c, 24'h062d3b, 24'h05fc94, 24'h05cd6d,
    24'h059fba, 24'h05736e, 24'h05487f, 24'h051ee3,
    24'h04f68e, 24'h04cf76, 24'h04a993, 24'h0484da,
    24'h046142, 24'h043ec3, 24'h041d53, 24'h03fceb,
    24'h03dd82, 24'h03bf10, 24'h03a18e, 24'h0384f5,
    24'h03693d, 24'h034e5f, 24'h033455, 24'h031b18,
    24'h0302a1, 24'h02eaeb, 24'h02d3f0, 24'h02bdab,
    24'h02a814, 24'h029328, 24'h027ee0, 24'h026b38,
    24'h02582b, 24'h0245b4, 24'h0233ce, 24'h022275,
    24'h0211a5, 24'h02015a, 24'h01f18e, 24'h01e23f,
    24'h01d369, 24'h01c508, 24'h01b717, 24'h01a995,
    24'h019c7d, 24'h018fcc, 24'h01837f, 24'h017793,
    24'h016c05, 24'h0160d2, 24'h0155f7, 24'h014b72,
    24'h01413f, 24'h01375d, 24'h012dc8, 24'h01247f,
    24'h011b80, 24'h0112c7, 24'h010a53, 24'h010221,
    24'h00fa30, 24'h00f27d, 24'h00eb07, 24'h00e3cc,
    24'h00dcca, 24'h00d5ff, 24'h00cf6a, 24'h00c908,
    24'h00c2d8, 24'h00bcda, 24'h00b70a, 24'h00b169,
    24'h00abf3, 24'h00a6a9, 24'h00a188, 24'h009c90,
    24'h0097bf, 24'h009314, 24'h008e8d, 24'h008a2b,
    24'h0085ea, 24'h0081cc, 24'h007dcd, 24'h0079ee,
    24'h00762e, 24'h00728b, 24'h006f05, 24'h006b9b,
    24'h00684b, 24'h006516, 24'h0061f9, 24'h005ef6,
    24'h005c0a, 24'h005935, 24'h005676, 24'h0053cd,
    24'h005139, 24'h004eba, 24'h004c4d, 24'h0049f4,
    24'h0047ae, 24'h004579, 24'h004356, 24'h004144,
    24'h003f42, 24'h003d50, 24'h003b6d, 24'h003999,
    24'h0037d3, 24'h00361b, 24'h003471, 24'h0032d4,
    24'h003144, 24'h002fc0, 24'h002e48, 24'h002cdb,
    24'h002b7a, 24'h002a23, 24'h0028d8, 24'h002796,
    24'h00265e, 24'h002530, 24'h00240b, 24'h0022ef,
    24'h0021dc, 24'h0020d1, 24'h001fcf, 24'h001ed4,
    24'h001de1, 24'h001cf6, 24'h001c12, 24'h001b35,
    24'h001a5f, 24'h00198f, 24'h0018c6, 24'h001802,
    24'h001745, 24'h00168e, 24'h0015dc, 24'h001530,
    24'h001489, 24'h0013e8, 24'h00134b, 24'h0012b3,
    24'h001220, 24'h001191, 24'h001107, 24'h001080,
    24'h000ffe, 24'h000f80, 24'h000f06, 24'h000e90,
    24'h000e1d, 24'h000dae, 24'h000d42, 24'h000cda,
    24'h000c75, 24'h000c13, 24'h000bb4, 24'h000b57,
    24'h000afe
  };

  fp32_bits_t abs_x;
  logic [16:0] pos_q8;
  logic [8:0]  idx;
  logic [7:0]  frac;
  logic [23:0] lut_lo, lut_hi;
  logic [24:0] lut_delta;
  logic [32:0] interp_product;
  logic [23:0] interp_step;

  always_comb begin
    abs_x = {1'b0, x_i[30:0]};
    pos_q8 = fp32_abs_to_exp_pos_q8(x_i);
    idx = pos_q8[16:8];
    frac = pos_q8[7:0];
    lut_lo = ExpLut[idx];
    lut_hi = (idx == 9'd256) ? ExpLut[256] : ExpLut[idx + 9'd1];
    lut_delta = {1'b0, lut_lo} - {1'b0, lut_hi};
    interp_product = {8'd0, lut_delta} * {25'd0, frac};
    interp_step = 24'(interp_product >> 8);
    exp_q1_23_o = Q1_23_ZERO;
    valid_o = 1'b0;
    saturated_o = 1'b0;
    unsupported_o = 1'b0;

    if (fp32_is_nan_or_inf(x_i)) begin
      unsupported_o = 1'b1;
    end else begin
      valid_o = 1'b1;
      if (fp32_is_zero(x_i)) begin
        exp_q1_23_o = Q1_23_ONE;
      end else if (!x_i[31]) begin
        exp_q1_23_o = Q1_23_ONE;
        saturated_o = 1'b1;
      end else if (abs_x > 32'h4100_0000) begin
        exp_q1_23_o = Q1_23_ZERO;
        saturated_o = 1'b1;
      end else begin
        exp_q1_23_o = lut_lo - interp_step;
      end
    end
  end

endmodule

// Direct-address mixed-precision exponential ROM.  The table is the frozen
// Phase-1 256-entry signed-INT16 Q1.14 image (raw little-endian hash
// 3ea4629839c7341f1d40b388b444d1d4ae8adf4fefccd2d36e5876f6eb49df30).
// Addressing is floor((delta + 8) * 32), with bin-center codes and no
// interpolation.  A zero/positive delta is the exact winner identity.
module online_merge_exp_mixed_rom (
  input  logic [7:0]  index_i,
  input  logic        unity_i,
  input  logic        zero_i,
  input  logic        valid_i,
  input  logic        saturated_i,
  input  logic        unsupported_i,
  output logic [15:0] exp_q1_14_o,
  output logic        valid_o,
  output logic        saturated_o,
  output logic        unsupported_o
);

  import online_merge_fp32_helpers::*;

  localparam logic signed [15:0] MixedExpLut [0:255] = '{
    16'sd6, 16'sd6, 16'sd6, 16'sd6, 16'sd6, 16'sd7, 16'sd7, 16'sd7,
    16'sd7, 16'sd7, 16'sd8, 16'sd8, 16'sd8, 16'sd8, 16'sd9, 16'sd9,
    16'sd9, 16'sd9, 16'sd10, 16'sd10, 16'sd10, 16'sd11, 16'sd11, 16'sd11,
    16'sd12, 16'sd12, 16'sd13, 16'sd13, 16'sd13, 16'sd14, 16'sd14, 16'sd15,
    16'sd15, 16'sd16, 16'sd16, 16'sd17, 16'sd17, 16'sd18, 16'sd18, 16'sd19,
    16'sd19, 16'sd20, 16'sd21, 16'sd21, 16'sd22, 16'sd23, 16'sd24, 16'sd24,
    16'sd25, 16'sd26, 16'sd27, 16'sd27, 16'sd28, 16'sd29, 16'sd30, 16'sd31,
    16'sd32, 16'sd33, 16'sd34, 16'sd35, 16'sd36, 16'sd38, 16'sd39, 16'sd40,
    16'sd41, 16'sd43, 16'sd44, 16'sd45, 16'sd47, 16'sd48, 16'sd50, 16'sd51,
    16'sd53, 16'sd55, 16'sd56, 16'sd58, 16'sd60, 16'sd62, 16'sd64, 16'sd66,
    16'sd68, 16'sd70, 16'sd72, 16'sd75, 16'sd77, 16'sd80, 16'sd82, 16'sd85,
    16'sd87, 16'sd90, 16'sd93, 16'sd96, 16'sd99, 16'sd102, 16'sd105, 16'sd109,
    16'sd112, 16'sd116, 16'sd119, 16'sd123, 16'sd127, 16'sd131, 16'sd135, 16'sd140,
    16'sd144, 16'sd149, 16'sd153, 16'sd158, 16'sd163, 16'sd168, 16'sd174, 16'sd179,
    16'sd185, 16'sd191, 16'sd197, 16'sd203, 16'sd209, 16'sd216, 16'sd223, 16'sd230,
    16'sd237, 16'sd245, 16'sd253, 16'sd261, 16'sd269, 16'sd278, 16'sd286, 16'sd295,
    16'sd305, 16'sd314, 16'sd324, 16'sd335, 16'sd345, 16'sd356, 16'sd368, 16'sd379,
    16'sd391, 16'sd404, 16'sd417, 16'sd430, 16'sd443, 16'sd458, 16'sd472, 16'sd487,
    16'sd503, 16'sd518, 16'sd535, 16'sd552, 16'sd569, 16'sd588, 16'sd606, 16'sd625,
    16'sd645, 16'sd666, 16'sd687, 16'sd709, 16'sd731, 16'sd754, 16'sd778, 16'sd803,
    16'sd829, 16'sd855, 16'sd882, 16'sd910, 16'sd939, 16'sd969, 16'sd999, 16'sd1031,
    16'sd1064, 16'sd1098, 16'sd1133, 16'sd1168, 16'sd1206, 16'sd1244, 16'sd1283, 16'sd1324,
    16'sd1366, 16'sd1409, 16'sd1454, 16'sd1500, 16'sd1548, 16'sd1597, 16'sd1648, 16'sd1700,
    16'sd1754, 16'sd1810, 16'sd1867, 16'sd1926, 16'sd1988, 16'sd2051, 16'sd2116, 16'sd2183,
    16'sd2252, 16'sd2324, 16'sd2398, 16'sd2474, 16'sd2552, 16'sd2633, 16'sd2717, 16'sd2803,
    16'sd2892, 16'sd2984, 16'sd3078, 16'sd3176, 16'sd3277, 16'sd3381, 16'sd3488, 16'sd3599,
    16'sd3713, 16'sd3831, 16'sd3953, 16'sd4078, 16'sd4208, 16'sd4341, 16'sd4479, 16'sd4621,
    16'sd4768, 16'sd4919, 16'sd5076, 16'sd5237, 16'sd5403, 16'sd5574, 16'sd5751, 16'sd5934,
    16'sd6122, 16'sd6317, 16'sd6517, 16'sd6724, 16'sd6937, 16'sd7158, 16'sd7385, 16'sd7619,
    16'sd7861, 16'sd8111, 16'sd8368, 16'sd8634, 16'sd8908, 16'sd9191, 16'sd9482, 16'sd9783,
    16'sd10094, 16'sd10414, 16'sd10745, 16'sd11086, 16'sd11438, 16'sd11801, 16'sd12176, 16'sd12562,
    16'sd12961, 16'sd13372, 16'sd13797, 16'sd14235, 16'sd14687, 16'sd15153, 16'sd15634, 16'sd16130
  };

  always_comb begin
    exp_q1_14_o = 16'h0000;
    valid_o = valid_i;
    saturated_o = saturated_i;
    unsupported_o = unsupported_i;
    if (unsupported_i || !valid_i) begin
      exp_q1_14_o = 16'h0000;
    end else if (unity_i) begin
      exp_q1_14_o = 16'h4000;
    end else if (zero_i) begin
      exp_q1_14_o = 16'h0000;
    end else begin
      exp_q1_14_o = MixedExpLut[index_i];
    end
  end

endmodule

// Compatibility wrapper for direct FP16 delta users and the existing unit
// test.  The engine uses the fused ordered-pair module below, so this wrapper
// is not present in its mixed datapath.
module online_merge_exp_mixed (
  input  online_merge_fp32_helpers::fp16_bits_t x_i,
  output logic [15:0]                           exp_q1_14_o,
  output logic                                  valid_o,
  output logic                                  saturated_o,
  output logic                                  unsupported_o
);

  import online_merge_fp32_helpers::*;

  logic [7:0] index;
  logic [10:0] significand;
  int signed value_exp;
  logic [63:0] scaled_abs;
  logic [63:0] abs_value_x32;
  int signed shift;
  logic unity, zero, valid, saturated, unsupported;

  always_comb begin
    index = '0;
    significand = (x_i[14:10] == 0) ? {1'b0, x_i[9:0]} :
        {1'b1, x_i[9:0]};
    value_exp = (x_i[14:10] == 0) ? -24 : int'(x_i[14:10]) - 25;
    abs_value_x32 = '0;
    shift = int'(value_exp) + 5;
    if (shift >= 0) begin
      abs_value_x32 = {53'd0, significand} << shift;
    end else if (-shift >= 64) begin
      abs_value_x32 = (significand != 0) ? 64'd1 : 64'd0;
    end else begin
      // ceil(|x|*32) turns floor((x+8)*32) into 256-ceil(|x|*32).
      abs_value_x32 = ({53'd0, significand} + (64'd1 << (-shift)) - 1) >>
          (-shift);
    end
    if (abs_value_x32 >= 256) begin
      index = 8'd0;
    end else begin
      index = 8'(256 - abs_value_x32);
    end

    valid = 1'b0;
    unity = 1'b0;
    zero = 1'b0;
    saturated = 1'b0;
    unsupported = 1'b0;
    if (fp16_is_nan_or_inf(x_i)) begin
      unsupported = 1'b1;
    end else begin
      valid = 1'b1;
      if (!x_i[15] || fp16_is_zero(x_i)) begin
        unity = 1'b1;
        saturated = !fp16_is_zero(x_i);
      end else if (fp16_lt(x_i, FP16_NEG_EIGHT)) begin
        zero = 1'b1;
        saturated = 1'b1;
      end
    end
  end

  online_merge_exp_mixed_rom i_rom (
    .index_i       (index),
    .unity_i       (unity),
    .zero_i        (zero),
    .valid_i       (valid),
    .saturated_i   (saturated),
    .unsupported_i (unsupported),
    .exp_q1_14_o   (exp_q1_14_o),
    .valid_o       (valid_o),
    .saturated_o   (saturated_o),
    .unsupported_o (unsupported_o)
  );
endmodule

// Fused ordered finite FP16 loser/winner -> direct LUT address.  It mirrors
// fp16_sub's three guard bits, sticky alignment and RNE result, but retains
// only the 15-bit aligned magnitude needed to form ceil(|delta|*32).  The ROM
// itself remains single-copy in online_merge_exp_mixed_rom.
module online_merge_fp16_delta_exp (
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
