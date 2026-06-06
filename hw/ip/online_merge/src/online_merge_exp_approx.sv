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
