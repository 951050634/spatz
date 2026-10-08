// Bit-exact combinational miter against the frozen pre-optimization module.
`timescale 1ns/1ps
module online_merge_delta_exp_timing_tb;
  import online_merge_fp32_helpers::*;

  fp16_bits_t loser, winner;
  logic [7:0] address, ref_address;
  logic [15:0] factor, ref_factor;
  logic valid, saturated, unsupported;
  logic ref_valid, ref_saturated, ref_unsupported;
  int unsigned cases, unsupported_cases, saturated_cases, unity_cases;
  int unsigned subnormal_cases, equal_cases;
  logic [31:0] rng;

  // Include signed zeros, smallest/largest subnormal, minimum normal,
  // +/-1, the saturation boundary +/-8, finite extrema, Inf and NaNs.
  localparam fp16_bits_t Anchors [0:14] = '{
    16'h0000, 16'h8000, 16'h0001, 16'h03ff, 16'h0400,
    16'h3c00, 16'hbc00, 16'h4800, 16'hc800, 16'h7bff,
    16'hfbff, 16'h7c00, 16'hfc00, 16'h7e00, 16'hffff
  };

  online_merge_fp16_delta_exp i_dut (
    .loser_i(loser), .winner_i(winner), .address_o(address),
    .exp_q1_14_o(factor), .valid_o(valid), .saturated_o(saturated),
    .unsupported_o(unsupported)
  );
  online_merge_fp16_delta_exp_reference i_reference (
    .loser_i(loser), .winner_i(winner), .address_o(ref_address),
    .exp_q1_14_o(ref_factor), .valid_o(ref_valid),
    .saturated_o(ref_saturated), .unsupported_o(ref_unsupported)
  );

  task automatic check_pair(input fp16_bits_t a, input fp16_bits_t b);
    loser = a;
    winner = b;
    #1;
    assert ({address, factor, valid, saturated, unsupported} ===
        {ref_address, ref_factor, ref_valid, ref_saturated, ref_unsupported})
      else $fatal(1, "MISMATCH case=%0d loser=%h winner=%h dut=%h ref=%h",
          cases, loser, winner, {address, factor, valid, saturated, unsupported},
          {ref_address, ref_factor, ref_valid, ref_saturated, ref_unsupported});
    // Also compare intermediate rounding results.  ROM bins or saturation
    // can otherwise mask a normalization mismatch in the output factor.
    assert ({i_dut.magnitude, i_dut.e_norm, i_dut.rounded_sig,
        i_dut.rounded_subnormal} === {i_reference.magnitude,
        i_reference.e_norm, i_reference.rounded_sig,
        i_reference.rounded_subnormal})
      else $fatal(1, "NORMALIZATION MISMATCH loser=%h winner=%h", loser, winner);
    cases++;
    if (unsupported) unsupported_cases++;
    if (saturated) saturated_cases++;
    if (valid && factor == 16'h4000) unity_cases++;
    if (a == b) equal_cases++;
    if ((a[14:10] == 0 && a[9:0] != 0) ||
        (b[14:10] == 0 && b[9:0] != 0)) subnormal_cases++;
  endtask

  task automatic check_both_orders(input fp16_bits_t a, input fp16_bits_t b);
    if (fp16_lt(b, a)) begin
      check_pair(b, a);
      check_pair(a, b);
    end else begin
      check_pair(a, b);
      check_pair(b, a);
    end
  endtask

  function automatic logic [31:0] next_random(input logic [31:0] state);
    logic [31:0] x;
    x = state ^ (state << 13);
    x = x ^ (x >> 17);
    return x ^ (x << 5);
  endfunction

  initial begin
    cases = 0;
    unsupported_cases = 0;
    saturated_cases = 0;
    unity_cases = 0;
    subnormal_cases = 0;
    equal_cases = 0;
    rng = 32'h8e51c4a7;
    // Every binary16 bit pattern: representative winners in both orders,
    // equality, adjacent encodings (cancellation) and opposite signs.
    for (int unsigned raw = 0; raw < 65536; raw++) begin
      foreach (Anchors[k]) check_both_orders(16'(raw), Anchors[k]);
      check_pair(16'(raw), 16'(raw));
      check_both_orders(16'(raw), 16'(raw + 1));
      check_both_orders(16'(raw), 16'(raw) ^ 16'h8000);
    end
    // Exponent/fraction combinations not limited to the anchor set.
    for (int unsigned sample = 0; sample < 200000; sample++) begin
      rng = next_random(rng);
      check_both_orders(rng[15:0], rng[31:16]);
    end
    assert (unsupported_cases > 0 && saturated_cases > 0 && unity_cases > 0 &&
        subnormal_cases > 0 && equal_cases > 0)
      else $fatal(1, "Missing required input/output category");
    $display("online_merge_delta_exp_timing_tb PASS cases=%0d", cases);
    $display("unsupported=%0d saturated=%0d unity=%0d subnormal=%0d equal=%0d",
        unsupported_cases, saturated_cases, unity_cases, subnormal_cases, equal_cases);
    $finish;
  end
endmodule
