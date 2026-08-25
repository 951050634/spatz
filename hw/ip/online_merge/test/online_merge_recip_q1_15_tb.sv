module online_merge_recip_q1_15_tb;
  import online_merge_fp32_helpers::*;
  logic [31:0] x;
  q1_15_t q;
  logic signed [9:0] s;
  logic v, u;
  logic [7:0] i;
  logic [14:0] f;
  q1_15_t lo, hi;
  logic [31:0] p;
  logic [15:0] step;
  online_merge_recip_approx_q1_15 dut (
    .x_i(x), .recip_q1_15_o(q), .scale_exp_o(s), .valid_o(v),
    .unsupported_o(u), .index_o(i), .frac_o(f), .lut_lo_o(lo),
    .lut_hi_o(hi), .interp_product_o(p), .interp_step_o(step)
  );

  task automatic expect_vector(
    input fp16_bits_t denominator_h,
    input q1_15_t expected_q,
    input logic signed [9:0] expected_s,
    input logic [7:0] expected_i,
    input logic [14:0] expected_f,
    input q1_15_t expected_lo,
    input q1_15_t expected_hi,
    input logic [31:0] expected_p,
    input logic [15:0] expected_step,
    input logic expected_v,
    input logic expected_u
  );
    begin
      x = fp16_to_fp32(denominator_h);
      #1;
      assert (q == expected_q)
        else $fatal(1, "q1.15 mismatch den=%h got=%h exp=%h",
                    denominator_h, q, expected_q);
      assert (s == expected_s)
        else $fatal(1, "scale mismatch den=%h got=%0d exp=%0d",
                    denominator_h, s, expected_s);
      assert (i == expected_i && f == expected_f)
        else $fatal(1, "address mismatch den=%h", denominator_h);
      assert (lo == expected_lo && hi == expected_hi)
        else $fatal(1, "endpoint mismatch den=%h", denominator_h);
      assert (p == expected_p && step == expected_step)
        else $fatal(1, "interpolation mismatch den=%h", denominator_h);
      assert (v == expected_v && u == expected_u)
        else $fatal(1, "validity mismatch den=%h", denominator_h);
    end
  endtask

  initial begin
    x = 32'h3f80_0000;
    expect_vector(16'h3c00, 16'h8000, 0, 8'd0, 15'd0,
                  16'h8000, 16'h7f80, 32'd0, 16'd0, 1'b1, 1'b0);
    expect_vector(16'h0000, 16'h0000, 0, 8'd0, 15'd0,
                  16'h0000, 16'h0000, 32'd0, 16'd0, 1'b0, 1'b1);
    expect_vector(16'h0001, 16'h8000, 24, 8'd0, 15'd0,
                  16'h8000, 16'h7f80, 32'd0, 16'd0, 1'b1, 1'b0);
    expect_vector(16'h0003, 16'h5555, 23, 8'd128, 15'd0,
                  16'h5555, 16'h551d, 32'd0, 16'd0, 1'b1, 1'b0);
    expect_vector(16'h3c00, 16'h8000, 0, 8'd0, 15'd0,
                  16'h8000, 16'h7f80, 32'd0, 16'd0, 1'b1, 1'b0);
    expect_vector(16'h4000, 16'h8000, -1, 8'd0, 15'd0,
                  16'h8000, 16'h7f80, 32'd0, 16'd0, 1'b1, 1'b0);
    expect_vector(16'h3c04, 16'h7f80, 0, 8'd1, 15'd0,
                  16'h7f80, 16'h7f02, 32'd0, 16'd0, 1'b1, 1'b0);
    expect_vector(16'h7bff, 16'h4008, -15, 8'd255, 15'd24576,
                  16'h4020, 16'h4000, 32'd786432, 16'd24, 1'b1, 1'b0);
    $display("online_merge_recip_q1_15_tb PASS (8 direct vectors)");
    $finish;
  end
endmodule
