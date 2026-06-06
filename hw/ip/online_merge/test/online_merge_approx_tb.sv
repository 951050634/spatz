// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

module online_merge_approx_tb;

  import online_merge_fp32_helpers::*;

  fp32_bits_t exp_x;
  q1_23_t exp_q1_23;
  logic exp_valid;
  logic exp_saturated;
  logic exp_unsupported;

  fp32_bits_t recip_x;
  q1_23_t recip_q1_23;
  logic signed [9:0] recip_scale_exp;
  logic recip_valid;
  logic recip_unsupported;

  online_merge_exp_approx i_exp_approx (
    .x_i             (exp_x),
    .exp_q1_23_o    (exp_q1_23),
    .valid_o         (exp_valid),
    .saturated_o     (exp_saturated),
    .unsupported_o   (exp_unsupported)
  );

  online_merge_recip_approx i_recip_approx (
    .x_i             (recip_x),
    .recip_q1_23_o   (recip_q1_23),
    .scale_exp_o     (recip_scale_exp),
    .valid_o         (recip_valid),
    .unsupported_o   (recip_unsupported)
  );

  task automatic expect_exp(
    input fp32_bits_t x,
    input q1_23_t expected,
    input logic expected_valid,
    input logic expected_saturated,
    input logic expected_unsupported
  );
    begin
      exp_x = x;
      #1;
      assert (exp_q1_23 == expected)
        else $fatal(1, "exp mismatch x=%h got=%h expected=%h", x, exp_q1_23, expected);
      assert (exp_valid == expected_valid)
        else $fatal(1, "exp valid mismatch x=%h", x);
      assert (exp_saturated == expected_saturated)
        else $fatal(1, "exp saturated mismatch x=%h", x);
      assert (exp_unsupported == expected_unsupported)
        else $fatal(1, "exp unsupported mismatch x=%h", x);
    end
  endtask

  task automatic expect_recip(
    input fp32_bits_t x,
    input q1_23_t expected,
    input logic signed [9:0] expected_scale_exp,
    input logic expected_valid,
    input logic expected_unsupported
  );
    begin
      recip_x = x;
      #1;
      assert (recip_q1_23 == expected)
        else $fatal(1, "recip mismatch x=%h got=%h expected=%h", x, recip_q1_23, expected);
      assert (recip_scale_exp == expected_scale_exp)
        else $fatal(1, "recip scale mismatch x=%h got=%0d expected=%0d",
                    x, recip_scale_exp, expected_scale_exp);
      assert (recip_valid == expected_valid)
        else $fatal(1, "recip valid mismatch x=%h", x);
      assert (recip_unsupported == expected_unsupported)
        else $fatal(1, "recip unsupported mismatch x=%h", x);
    end
  endtask

  initial begin
    expect_exp(32'h0000_0000, 24'h80_0000, 1'b1, 1'b0, 1'b0);
    expect_exp(32'hbf40_0000, 24'h3c_7682, 1'b1, 1'b0, 1'b0);
    expect_exp(32'hc100_0000, 24'h00_0afe, 1'b1, 1'b0, 1'b0);
    expect_exp(32'h3f80_0000, 24'h80_0000, 1'b1, 1'b1, 1'b0);
    expect_exp(32'h7fc0_0000, 24'h00_0000, 1'b0, 1'b0, 1'b1);

    expect_recip(32'h3f80_0000, 24'h80_0000, 10'sd0, 1'b1, 1'b0);
    expect_recip(32'h3f5e_3b41, 24'h49_b99c, 10'sd1, 1'b1, 1'b0);
    expect_recip(32'h0000_0000, 24'h00_0000, 10'sd0, 1'b0, 1'b1);
    expect_recip(32'h7f80_0000, 24'h00_0000, 10'sd0, 1'b0, 1'b1);

    $display("online_merge_approx_tb PASS");
    $finish;
  end

endmodule
