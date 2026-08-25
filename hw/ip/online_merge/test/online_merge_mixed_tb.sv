// Focused unit checks for the mixed binary16 helpers and direct INT16 ROM.
module online_merge_mixed_tb;
  import online_merge_fp32_helpers::*;

  logic clk;
  logic rst_ni;
  logic divider_start;
  fp16_bits_t divider_num, divider_den, divider_result;
  logic divider_busy, divider_done;

  online_merge_fp16_divider i_divider (
    .clk_i         (clk),
    .rst_ni        (rst_ni),
    .start_i       (divider_start),
    .numerator_i   (divider_num),
    .denominator_i (divider_den),
    .busy_o        (divider_busy),
    .done_o        (divider_done),
    .result_o      (divider_result)
  );

  fp16_bits_t lut_x;
  logic [15:0] lut_y;
  logic lut_valid, lut_saturated, lut_unsupported;
  logic signed [47:0] lut_center_fixed;
  logic [15:0] previous_lut_code;
  logic [47:0] q16_midpoint;

  fp16_bits_t pair_loser, pair_winner, pair_ref_delta;
  logic [7:0] fused_address;
  logic [15:0] fused_exp_q1_14, ref_exp_q1_14;
  logic [7:0] ref_address;
  logic fused_valid, fused_saturated, fused_unsupported;
  logic ref_valid, ref_saturated, ref_unsupported;

  localparam logic signed [15:0] FROZEN_LUT [0:255] = '{
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

  online_merge_exp_mixed i_lut (
    .x_i             (lut_x),
    .exp_q1_14_o     (lut_y),
    .valid_o         (lut_valid),
    .saturated_o     (lut_saturated),
    .unsupported_o   (lut_unsupported)
  );

  assign pair_ref_delta = fp16_sub(pair_loser, pair_winner);

  function automatic logic [7:0] direct_lut_address(
    input fp16_bits_t value
  );
    logic [10:0] sig;
    logic [63:0] scaled;
    int signed value_exp;
    int signed address_shift;
    begin
      sig = (value[14:10] == 0) ? {1'b0, value[9:0]} :
          {1'b1, value[9:0]};
      value_exp = (value[14:10] == 0) ? -24 :
          int'(value[14:10]) - 25;
      address_shift = value_exp + 5;
      if (address_shift >= 0) begin
        scaled = {53'd0, sig} << address_shift;
      end else begin
        scaled = ({53'd0, sig} + (64'd1 << (-address_shift)) - 64'd1) >>
            (-address_shift);
      end
      direct_lut_address = (scaled >= 256) ? 8'd0 :
          8'(256 - scaled);
    end
  endfunction

  assign ref_address = direct_lut_address(pair_ref_delta);

  online_merge_fp16_delta_exp i_fused_delta_exp (
    .loser_i         (pair_loser),
    .winner_i        (pair_winner),
    .address_o       (fused_address),
    .exp_q1_14_o     (fused_exp_q1_14),
    .valid_o         (fused_valid),
    .saturated_o     (fused_saturated),
    .unsupported_o   (fused_unsupported)
  );

  online_merge_exp_mixed i_reference_delta_exp (
    .x_i             (pair_ref_delta),
    .exp_q1_14_o     (ref_exp_q1_14),
    .valid_o         (ref_valid),
    .saturated_o     (ref_saturated),
    .unsupported_o   (ref_unsupported)
  );

  task automatic expect_f32_to_f16(
    input fp32_bits_t value,
    input fp16_bits_t expected
  );
    fp16_bits_t got;
    begin
      got = fp32_to_fp16_rne(value);
      assert (got == expected)
        else $fatal(1, "fp32->fp16 mismatch value=%h got=%h expected=%h",
                    value, got, expected);
    end
  endtask

  task automatic expect_f16_to_f32(
    input fp16_bits_t value,
    input fp32_bits_t expected
  );
    fp32_bits_t got;
    begin
      got = fp16_to_fp32(value);
      assert (got == expected)
        else $fatal(1, "fp16->fp32 mismatch value=%h got=%h expected=%h",
                    value, got, expected);
    end
  endtask

  task automatic expect_lut(
    input fp16_bits_t value,
    input logic [15:0] expected,
    input logic expected_saturated
  );
    begin
      lut_x = value;
      #1;
      assert (lut_y == expected)
        else $fatal(1, "mixed LUT mismatch x=%h got=%h expected=%h",
                    value, lut_y, expected);
      assert (lut_valid && !lut_unsupported)
        else $fatal(1, "mixed LUT validity mismatch x=%h", value);
      assert (lut_saturated == expected_saturated)
        else $fatal(1, "mixed LUT saturation mismatch x=%h", value);
    end
  endtask

  task automatic expect_div(
    input fp16_bits_t numerator,
    input fp16_bits_t denominator,
    input fp16_bits_t expected
  );
    begin
      divider_num = numerator;
      divider_den = denominator;
      divider_start = 1'b1;
      @(posedge clk);
      #0.1;
      divider_start = 1'b0;
      for (int cycles = 0; cycles < 100; cycles++) begin
        @(posedge clk);
        #0.1;
        if (divider_done) begin
          break;
        end
        if (cycles == 99) begin
          $fatal(1, "binary16 divider timeout busy=%b", divider_busy);
        end
      end
      #1;
      assert (divider_result == expected)
        else $fatal(1, "binary16 divide mismatch %h/%h got=%h expected=%h",
                    numerator, denominator, divider_result, expected);
      @(posedge clk);
    end
  endtask

  task automatic expect_fused_pair(
    input fp16_bits_t loser,
    input fp16_bits_t winner
  );
    begin
      pair_loser = loser;
      pair_winner = winner;
      #1;
      assert (fused_exp_q1_14 == ref_exp_q1_14)
        else $fatal(1, "fused exp mismatch loser=%h winner=%h delta=%h got=%h ref=%h",
                    loser, winner, pair_ref_delta, fused_exp_q1_14,
                    ref_exp_q1_14);
      assert (fused_address == ref_address)
        else $fatal(1, "fused address mismatch loser=%h winner=%h delta=%h got=%0d ref=%0d",
                    loser, winner, pair_ref_delta, fused_address, ref_address);
      assert (fused_valid == ref_valid &&
              fused_saturated == ref_saturated &&
              fused_unsupported == ref_unsupported)
        else $fatal(1, "fused flags mismatch loser=%h winner=%h delta=%h got=%b/%b/%b ref=%b/%b/%b",
                    loser, winner, pair_ref_delta, fused_valid,
                    fused_saturated, fused_unsupported, ref_valid,
                    ref_saturated, ref_unsupported);
    end
  endtask

  initial begin
    clk = 1'b0;
    rst_ni = 1'b0;
    divider_start = 1'b0;
    divider_num = '0;
    divider_den = '0;
    fork
      forever #1 clk = ~clk;
    join_none
    repeat (2) @(posedge clk);
    rst_ni = 1'b1;

    expect_f32_to_f16(32'h3f80_0000, 16'h3c00);
    expect_f32_to_f16(32'h3fc0_0000, 16'h3e00);
    expect_f32_to_f16(32'h3f80_1000, 16'h3c00); // halfway, even result
    expect_f32_to_f16(32'h3f80_3000, 16'h3c02); // halfway, odd result increments
    expect_f32_to_f16(32'h0000_0001, 16'h0000);
    expect_f32_to_f16(32'h477f_e000, 16'h7bff);
    expect_f16_to_f32(16'h3c00, 32'h3f80_0000);
    expect_f16_to_f32(16'h3e00, 32'h3fc0_0000);
    expect_f16_to_f32(16'h3555, 32'h3eaa_a000);
    expect_f16_to_f32(16'hc800, 32'hc100_0000);
    expect_f16_to_f32(16'h0001, 32'h3380_0000);
    expect_f16_to_f32(16'h03ff, 32'h387f_c000);

    assert (fp16_sub(16'h3c00, 16'h3800) == 16'h3800)
      else $fatal(1, "binary16 subtraction 1-0.5 failed");
    assert (fp16_sub(16'h3c00, 16'h3c00) == FP16_POS_ZERO)
      else $fatal(1, "binary16 subtraction equal failed");
    assert (fp16_sub(16'h0000, 16'h0000) == FP16_POS_ZERO)
      else $fatal(1, "binary16 +0 - +0 canonicalization failed");
    assert (fp16_sub(16'h3800, 16'h3c00) == 16'hb800)
      else $fatal(1, "binary16 subtraction 0.5-1 failed");
    assert (fp16_sub(16'h0002, 16'h0001) == 16'h0001)
      else $fatal(1, "binary16 subnormal subtraction failed");
    assert (q1_14_to_q1_23(16'h4000) == 24'h800000)
      else $fatal(1, "Q1.14 to Q1.23 widening failed");
    q16_midpoint = (48'd1 << 32) + (48'd1 << 21) + 48'd1;
    assert (uq16_16_to_fp16(q16_midpoint) == 16'h3c01)
      else $fatal(1, "direct Q16.32->FP16 RNE midpoint failed: %h",
                  uq16_16_to_fp16(q16_midpoint));
    expect_lut(16'h0000, 16'h4000, 1'b0);
    expect_lut(16'h3c00, 16'h4000, 1'b1);
    expect_lut(16'hc800, 16'sd6, 1'b0);
    expect_lut(16'hc400, 16'sd305, 1'b0);
    expect_lut(16'hc840, 16'h0000, 1'b1);

    // Fused ordered-pair address miter: compare the fused path bit-for-bit
    // against fp16_sub followed by the original direct-address LUT.
    expect_fused_pair(16'h0000, 16'h0000); // +0 - +0
    expect_fused_pair(16'h8000, 16'h0000); // -0 - +0
    expect_fused_pair(16'h0000, 16'h8000); // +0 - -0
    expect_fused_pair(16'h3c00, 16'h3c00); // equal normal
    expect_fused_pair(16'h0001, 16'h0002); // positive subnormal
    expect_fused_pair(16'h8002, 16'h8001); // same-sign negative subnormal
    expect_fused_pair(16'h3c00, 16'h3c01); // same-sign cancellation
    expect_fused_pair(16'hbe00, 16'hbc00); // negative same-sign cancellation
    expect_fused_pair(16'hbc00, 16'h3c00); // cross-sign finite addition
    expect_fused_pair(16'h0000, 16'h4800); // delta == -8, LUT[0]
    expect_fused_pair(16'h0000, 16'h4801); // delta < -8, zero saturation
    expect_fused_pair(16'hfbff, 16'h7bff); // finite difference overflow
    begin
      logic [31:0] miter_state;
      fp16_bits_t miter_a, miter_b, miter_tmp;
      int unsigned structured_cases, random_cases;
      structured_cases = 0;
      random_cases = 0;

      // Every finite magnitude code against the zero endpoints.
      for (int code = 0; code <= 16'h7bff; code++) begin
        miter_a = 16'(code);
        expect_fused_pair(16'h0000, miter_a);
        miter_a = 16'h8000 | 16'(code);
        expect_fused_pair(miter_a, 16'h8000);
        structured_cases += 2;
      end

      // Every adjacent finite code pair, on both signs.  This includes all
      // subnormal/normal and exponent-field transition boundaries.
      for (int code = 0; code < 16'h7bff; code++) begin
        miter_a = 16'(code);
        miter_b = 16'(code + 1);
        expect_fused_pair(miter_a, miter_b);
        miter_a = 16'h8000 | 16'(code + 1);
        miter_b = 16'h8000 | 16'(code);
        expect_fused_pair(miter_a, miter_b);
        structured_cases += 2;
      end

      // Every finite magnitude paired with its opposite sign counterpart.
      for (int code = 0; code <= 16'h7bff; code++) begin
        miter_a = 16'h8000 | 16'(code);
        miter_b = 16'(code);
        expect_fused_pair(miter_a, miter_b);
        structured_cases++;
      end

      // Explicit RNE halfway cases (even and odd retained significand) and
      // subnormal/normal rounding boundaries.
      expect_fused_pair(16'h9000, 16'h3c00); // 1 + 2^-11, tie to even
      expect_fused_pair(16'h9000, 16'h3c01); // tie requiring increment
      expect_fused_pair(16'h8001, 16'h0400);
      expect_fused_pair(16'h83ff, 16'h0400);
      structured_cases += 4;

      // One million signed deterministic random ordered finite pairs.
      miter_state = 32'h5eed_2026;
      for (int i = 0; i < 1_000_000; i++) begin
        miter_state = miter_state * 32'd1664525 + 32'd1013904223;
        miter_a = miter_state[15:0];
        if (miter_a[14:10] == 5'h1f)
          miter_a[14:10] = 5'h1e;
        miter_state = miter_state * 32'd1664525 + 32'd1013904223;
        miter_b = miter_state[15:0];
        if (miter_b[14:10] == 5'h1f)
          miter_b[14:10] = 5'h1e;
        if (fp16_lt(miter_b, miter_a)) begin
          miter_tmp = miter_a;
          miter_a = miter_b;
          miter_b = miter_tmp;
        end
        expect_fused_pair(miter_a, miter_b);
        random_cases++;
      end
      $display("FUSED_MITER structured=%0d random=%0d total=%0d",
               structured_cases, random_cases,
               structured_cases + random_cases);
    end
    // The bin centers are exact binary16 values in this range.  Walk all
    // 256 addresses and compare every code against the frozen ROM image.
    previous_lut_code = 16'd0;
    for (int i = 0; i < 256; i++) begin
      // center = (-511 + 2*i) / 64; Q16.32 scale is 2^26.
      lut_center_fixed = (-511 + 2 * i) * 48'sd67_108_864;
      lut_x = fp32_to_fp16_rne(sq16_16_to_fp32(lut_center_fixed));
      #1;
      assert (lut_valid && !lut_unsupported && !lut_saturated)
        else $fatal(1, "mixed LUT address %0d invalid", i);
      assert ($signed(lut_y) == FROZEN_LUT[i])
        else $fatal(1, "mixed LUT code mismatch at address %0d got=%0d expected=%0d",
                    i, $signed(lut_y), FROZEN_LUT[i]);
      assert (lut_y >= previous_lut_code)
        else $fatal(1, "mixed LUT code not monotonic at address %0d", i);
      previous_lut_code = lut_y;
    end
    assert (previous_lut_code == 16'd16130)
      else $fatal(1, "mixed LUT final address mismatch");
    expect_div(16'h3c00, 16'h3c00, 16'h3c00);
    expect_div(16'h3e00, 16'h3c00, 16'h3e00);
    expect_div(16'h3c00, 16'h4200, 16'h3555); // 1/3, RNE
    expect_div(16'h4000, 16'h4200, 16'h3955); // 2/3, RNE
    expect_div(16'h0000, 16'h3c00, 16'h0000);
    expect_div(16'h0001, 16'h3c00, 16'h0001);
    expect_div(16'h0001, 16'h0003, 16'h3555);
    expect_div(16'h0003, 16'h0001, 16'h4200);
    expect_div(16'h3c00, 16'h7bff, 16'h0100);

    $display("online_merge_mixed_tb PASS");
    $finish;
  end
endmodule
