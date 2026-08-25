// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

// LUT reciprocal approximation for positive finite normal FP32 inputs.
// The output represents recip_q1_23_o * 2**scale_exp_o.
module online_merge_recip_approx (
  input  online_merge_fp32_helpers::fp32_bits_t x_i,
  output online_merge_fp32_helpers::q1_23_t     recip_q1_23_o,
  output logic signed [9:0]                     scale_exp_o,
  output logic                                  valid_o,
  output logic                                  unsupported_o
);

  import online_merge_fp32_helpers::*;

  localparam q1_23_t RecipLut [0:256] = '{
    24'h800000, 24'h7f8080, 24'h7f01fc, 24'h7e8473,
    24'h7e07e0, 24'h7d8c43, 24'h7d1196, 24'h7c97d9,
    24'h7c1f08, 24'h7ba720, 24'h7b301f, 24'h7aba02,
    24'h7a44c7, 24'h79d06b, 24'h795ceb, 24'h78ea46,
    24'h787878, 24'h780780, 24'h77975c, 24'h772807,
    24'h76b982, 24'h764bc9, 24'h75ded9, 24'h7572b2,
    24'h750750, 24'h749cb3, 24'h7432d6, 24'h73c9b9,
    24'h73615a, 24'h72f9b6, 24'h7292cc, 24'h722c99,
    24'h71c71c, 24'h716253, 24'h70fe3c, 24'h709ad5,
    24'h70381c, 24'h6fd610, 24'h6f74ae, 24'h6f13f6,
    24'h6eb3e4, 24'h6e5479, 24'h6df5b1, 24'h6d978c,
    24'h6d3a07, 24'h6cdd21, 24'h6c80d9, 24'h6c252d,
    24'h6bca1b, 24'h6b6fa2, 24'h6b15c0, 24'h6abc75,
    24'h6a63be, 24'h6a0b99, 24'h69b407, 24'h695d04,
    24'h690690, 24'h68b0aa, 24'h685b50, 24'h680680,
    24'h67b23a, 24'h675e7c, 24'h670b45, 24'h66b894,
    24'h666666, 24'h6614bc, 24'h65c394, 24'h6572ec,
    24'h6522c4, 24'h64d31a, 24'h6483ed, 24'h64353c,
    24'h63e706, 24'h63994a, 24'h634c06, 24'h62ff3a,
    24'h62b2e4, 24'h626704, 24'h621b98, 24'h61d09f,
    24'h618618, 24'h613c03, 24'h60f25e, 24'h60a928,
    24'h606060, 24'h601806, 24'h5fd018, 24'h5f8895,
    24'h5f417d, 24'h5eface, 24'h5eb488, 24'h5e6eaa,
    24'h5e2932, 24'h5de420, 24'h5d9f74, 24'h5d5b2b,
    24'h5d1746, 24'h5cd3c3, 24'h5c90a2, 24'h5c4de2,
    24'h5c0b81, 24'h5bc980, 24'h5b87de, 24'h5b4699,
    24'h5b05b0, 24'h5ac524, 24'h5a84f3, 24'h5a451d,
    24'h5a05a0, 24'h59c67d, 24'h5987b2, 24'h59493e,
    24'h590b21, 24'h58cd5b, 24'h588fea, 24'h5852ce,
    24'h581606, 24'h57d991, 24'h579d6f, 24'h57619f,
    24'h572621, 24'h56eaf3, 24'h56b016, 24'h567588,
    24'h563b49, 24'h560158, 24'h55c7b5, 24'h558e5f,
    24'h555555, 24'h551c98, 24'h54e425, 24'h54abfd,
    24'h547420, 24'h543c8c, 24'h540540, 24'h53ce3e,
    24'h539783, 24'h53610f, 24'h532ae2, 24'h52f4fb,
    24'h52bf5b, 24'h5289ff, 24'h5254e8, 24'h522015,
    24'h51eb85, 24'h51b739, 24'h51832f, 24'h514f68,
    24'h511be2, 24'h50e89d, 24'h50b599, 24'h5082d5,
    24'h505050, 24'h501e0b, 24'h4fec05, 24'h4fba3d,
    24'h4f88b3, 24'h4f5766, 24'h4f2657, 24'h4ef583,
    24'h4ec4ec, 24'h4e9491, 24'h4e6471, 24'h4e348b,
    24'h4e04e0, 24'h4dd56f, 24'h4da638, 24'h4d7739,
    24'h4d4874, 24'h4d19e7, 24'h4ceb91, 24'h4cbd74,
    24'h4c8f8d, 24'h4c61dd, 24'h4c3464, 24'h4c0721,
    24'h4bda13, 24'h4bad3b, 24'h4b8097, 24'h4b5428,
    24'h4b27ed, 24'h4afbe6, 24'h4ad013, 24'h4aa472,
    24'h4a7905, 24'h4a4dc9, 24'h4a22c0, 24'h49f7e9,
    24'h49cd43, 24'h49a2ce, 24'h49788a, 24'h494e76,
    24'h492492, 24'h48fade, 24'h48d15a, 24'h48a805,
    24'h487ede, 24'h4855e6, 24'h482d1c, 24'h480480,
    24'h47dc12, 24'h47b3d1, 24'h478bbd, 24'h4763d6,
    24'h473c1b, 24'h47148c, 24'h46ed29, 24'h46c5f2,
    24'h469ee6, 24'h467804, 24'h46514e, 24'h462ac2,
    24'h460460, 24'h45de28, 24'h45b81a, 24'h459235,
    24'h456c79, 24'h4546e7, 24'h45217c, 24'h44fc3a,
    24'h44d720, 24'h44b22e, 24'h448d64, 24'h4468c0,
    24'h444444, 24'h441fef, 24'h43fbc0, 24'h43d7b8,
    24'h43b3d6, 24'h439019, 24'h436c83, 24'h434911,
    24'h4325c5, 24'h43029e, 24'h42df9c, 24'h42bcbe,
    24'h429a04, 24'h42776f, 24'h4254fd, 24'h4232af,
    24'h421084, 24'h41ee7d, 24'h41cc98, 24'h41aad6,
    24'h418937, 24'h4167bb, 24'h414660, 24'h412527,
    24'h410410, 24'h40e31b, 24'h40c247, 24'h40a194,
    24'h408102, 24'h406091, 24'h404040, 24'h402010,
    24'h400000
  };

  logic [8:0]  idx;
  logic [14:0] frac;
  logic [23:0] lut_lo, lut_hi;
  logic [24:0] lut_delta;
  logic [39:0] interp_product;
  logic [23:0] interp_step;

  always_comb begin
    idx = {1'b0, x_i[22:15]};
    frac = x_i[14:0];
    lut_lo = RecipLut[idx];
    lut_hi = (idx == 9'd256) ? RecipLut[256] : RecipLut[idx + 9'd1];
    lut_delta = {1'b0, lut_lo} - {1'b0, lut_hi};
    interp_product = {15'd0, lut_delta} * {25'd0, frac};
    interp_step = 24'(interp_product >> 15);
    recip_q1_23_o = Q1_23_ZERO;
    scale_exp_o = '0;
    valid_o = 1'b0;
    unsupported_o = 1'b0;

    if (!fp32_is_positive_finite_normal(x_i)) begin
      unsupported_o = 1'b1;
    end else begin
      valid_o = 1'b1;
      recip_q1_23_o = lut_lo - interp_step;
      scale_exp_o = 10'sd127 - $signed({2'b00, x_i[30:23]});
    end
  end

endmodule

// Mixed-normalization reciprocal image.  The physical ROM contains exactly
// code[0:255] in unsigned Q1.15; code[256] is the terminal value 0x4000 and is
// hardwired for the final interpolation bin.  The input is the FP32 widening
// of the already-RNE-quantized FP16 denominator.
module online_merge_recip_approx_q1_15 (
  input  online_merge_fp32_helpers::fp32_bits_t x_i,
  output online_merge_fp32_helpers::q1_15_t     recip_q1_15_o,
  output logic signed [9:0]                     scale_exp_o,
  output logic                                  valid_o,
  output logic                                  unsupported_o,
  output logic [7:0]                            index_o,
  output logic [14:0]                           frac_o,
  output online_merge_fp32_helpers::q1_15_t     lut_lo_o,
  output online_merge_fp32_helpers::q1_15_t     lut_hi_o,
  output logic [31:0]                            interp_product_o,
  output logic [15:0]                            interp_step_o
);

  import online_merge_fp32_helpers::*;

  localparam q1_15_t RecipLut [0:255] = '{
    16'h8000, 16'h7f80, 16'h7f02, 16'h7e84, 16'h7e08, 16'h7d8c, 16'h7d12, 16'h7c98,
    16'h7c1f, 16'h7ba7, 16'h7b30, 16'h7aba, 16'h7a45, 16'h79d0, 16'h795d, 16'h78ea,
    16'h7878, 16'h7808, 16'h7797, 16'h7728, 16'h76ba, 16'h764c, 16'h75df, 16'h7573,
    16'h7507, 16'h749d, 16'h7433, 16'h73ca, 16'h7361, 16'h72fa, 16'h7293, 16'h722d,
    16'h71c7, 16'h7162, 16'h70fe, 16'h709b, 16'h7038, 16'h6fd6, 16'h6f75, 16'h6f14,
    16'h6eb4, 16'h6e54, 16'h6df6, 16'h6d98, 16'h6d3a, 16'h6cdd, 16'h6c81, 16'h6c25,
    16'h6bca, 16'h6b70, 16'h6b16, 16'h6abc, 16'h6a64, 16'h6a0c, 16'h69b4, 16'h695d,
    16'h6907, 16'h68b1, 16'h685b, 16'h6807, 16'h67b2, 16'h675e, 16'h670b, 16'h66b9,
    16'h6666, 16'h6615, 16'h65c4, 16'h6573, 16'h6523, 16'h64d3, 16'h6484, 16'h6435,
    16'h63e7, 16'h6399, 16'h634c, 16'h62ff, 16'h62b3, 16'h6267, 16'h621c, 16'h61d1,
    16'h6186, 16'h613c, 16'h60f2, 16'h60a9, 16'h6060, 16'h6018, 16'h5fd0, 16'h5f89,
    16'h5f41, 16'h5efb, 16'h5eb5, 16'h5e6f, 16'h5e29, 16'h5de4, 16'h5d9f, 16'h5d5b,
    16'h5d17, 16'h5cd4, 16'h5c91, 16'h5c4e, 16'h5c0c, 16'h5bca, 16'h5b88, 16'h5b47,
    16'h5b06, 16'h5ac5, 16'h5a85, 16'h5a45, 16'h5a06, 16'h59c6, 16'h5988, 16'h5949,
    16'h590b, 16'h58cd, 16'h5890, 16'h5853, 16'h5816, 16'h57da, 16'h579d, 16'h5762,
    16'h5726, 16'h56eb, 16'h56b0, 16'h5676, 16'h563b, 16'h5601, 16'h55c8, 16'h558e,
    16'h5555, 16'h551d, 16'h54e4, 16'h54ac, 16'h5474, 16'h543d, 16'h5405, 16'h53ce,
    16'h5398, 16'h5361, 16'h532b, 16'h52f5, 16'h52bf, 16'h528a, 16'h5255, 16'h5220,
    16'h51ec, 16'h51b7, 16'h5183, 16'h514f, 16'h511c, 16'h50e9, 16'h50b6, 16'h5083,
    16'h5050, 16'h501e, 16'h4fec, 16'h4fba, 16'h4f89, 16'h4f57, 16'h4f26, 16'h4ef6,
    16'h4ec5, 16'h4e95, 16'h4e64, 16'h4e35, 16'h4e05, 16'h4dd5, 16'h4da6, 16'h4d77,
    16'h4d48, 16'h4d1a, 16'h4cec, 16'h4cbd, 16'h4c90, 16'h4c62, 16'h4c34, 16'h4c07,
    16'h4bda, 16'h4bad, 16'h4b81, 16'h4b54, 16'h4b28, 16'h4afc, 16'h4ad0, 16'h4aa4,
    16'h4a79, 16'h4a4e, 16'h4a23, 16'h49f8, 16'h49cd, 16'h49a3, 16'h4979, 16'h494e,
    16'h4925, 16'h48fb, 16'h48d1, 16'h48a8, 16'h487f, 16'h4856, 16'h482d, 16'h4805,
    16'h47dc, 16'h47b4, 16'h478c, 16'h4764, 16'h473c, 16'h4715, 16'h46ed, 16'h46c6,
    16'h469f, 16'h4678, 16'h4651, 16'h462b, 16'h4604, 16'h45de, 16'h45b8, 16'h4592,
    16'h456c, 16'h4547, 16'h4521, 16'h44fc, 16'h44d7, 16'h44b2, 16'h448d, 16'h4469,
    16'h4444, 16'h4420, 16'h43fc, 16'h43d8, 16'h43b4, 16'h4390, 16'h436d, 16'h4349,
    16'h4326, 16'h4303, 16'h42e0, 16'h42bd, 16'h429a, 16'h4277, 16'h4255, 16'h4233,
    16'h4211, 16'h41ee, 16'h41cd, 16'h41ab, 16'h4189, 16'h4168, 16'h4146, 16'h4125,
    16'h4104, 16'h40e3, 16'h40c2, 16'h40a2, 16'h4081, 16'h4061, 16'h4040, 16'h4020
  };

  logic [7:0]  idx;
  logic [14:0] frac;
  q1_15_t lut_lo, lut_hi;
  logic [16:0] lut_delta;
  logic [31:0] interp_product;
  logic [15:0] interp_step;

  always_comb begin
    idx = x_i[22:15];
    frac = x_i[14:0];
    lut_lo = RecipLut[idx];
    lut_hi = (idx == 8'd255) ? Q1_15_HALF : RecipLut[idx + 8'd1];
    lut_delta = {1'b0, lut_lo} - {1'b0, lut_hi};
    interp_product = lut_delta * frac;
    // Q1.15 interpolation deliberately truncates the low 15 product bits.
    interp_step = interp_product[30:15];
    recip_q1_15_o = Q1_15_ZERO;
    scale_exp_o = '0;
    valid_o = 1'b0;
    unsupported_o = 1'b0;
    index_o = idx;
    frac_o = frac;
    lut_lo_o = lut_lo;
    lut_hi_o = lut_hi;
    interp_product_o = interp_product;
    interp_step_o = interp_step;

    if (!fp32_is_positive_finite_normal(x_i)) begin
      index_o = '0;
      frac_o = '0;
      lut_lo_o = Q1_15_ZERO;
      lut_hi_o = Q1_15_ZERO;
      interp_product_o = '0;
      interp_step_o = '0;
      unsupported_o = 1'b1;
    end else begin
      valid_o = 1'b1;
      recip_q1_15_o = lut_lo - interp_step;
      scale_exp_o = 10'sd127 - $signed({2'b00, x_i[30:23]});
    end
  end

endmodule
