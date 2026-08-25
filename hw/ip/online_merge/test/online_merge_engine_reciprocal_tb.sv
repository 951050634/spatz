// Reciprocal-normalization bit-level miter for the Q1.15 LUT and Scalar SMU.
// Direct fields are frozen against the software reciprocal_vectors artifact;
// the engine case checks the reciprocal datapath's final FP16 widening and
// three-cycle shared-multiplier schedule.  The division engine has its own TB.
module online_merge_engine_reciprocal_tb;
  import online_merge_resource_types_pkg::*;
  import online_merge_fp32_helpers::*;

  logic clk;
  logic rst_ni;
  logic [16:0] src_m_old, src_l_old, src_o_old;
  logic [16:0] src_m_tile, src_l_tile, src_o_tile;
  logic [16:0] dst_m, dst_l, dst_o;
  logic [16:0] dst_weight_old, dst_weight_tile;
  logic [31:0] n, d, stride, mode;
  logic start, clear_done;
  logic busy, done, error;
  tcdm_req_t req;
  tcdm_rsp_t rsp;

  logic [31:0] memory [0:63];
  logic rsp_valid_q;
  logic [63:0] rsp_data_q;

  // Frozen software reciprocal_vectors golden data.  Case order is:
  // mode3, equal-max, random_0..random_3, then the four full-path boundary
  // cases (0001/0001, 0001/4000, 0000/3c00, 7bff/7bff).
  localparam logic [7:0] GOLD_INDEX [0:9] =
      '{8'd95, 8'd0, 8'd191, 8'd7, 8'd47, 8'd87, 8'd0, 8'd0, 8'd0, 8'd255};
  localparam logic [14:0] GOLD_FRAC [0:9] =
      '{15'd24576, 15'd0, 15'd8192, 15'd16384, 15'd16384,
        15'd16384, 15'd0, 15'd0, 15'd0, 15'd24576};
  localparam logic [15:0] GOLD_LO [0:9] =
      '{16'd23899, 16'd32768, 16'd18766, 16'd31896, 16'd27685,
        16'd24457, 16'd32768, 16'd32768, 16'd32768, 16'd16416};
  localparam logic [15:0] GOLD_HI [0:9] =
      '{16'd23831, 16'd32640, 16'd18725, 16'd31775, 16'd27594,
        16'd24385, 16'd32640, 16'd32640, 16'd32640, 16'd16384};
  localparam logic [15:0] GOLD_Q [0:9] =
      '{16'd23848, 16'd32768, 16'd18756, 16'd31836, 16'd27640,
        16'd24421, 16'd32768, 16'd32768, 16'd32768, 16'd16392};
  localparam logic signed [9:0] GOLD_S [0:9] =
      '{10'sd0, -10'sd2, 10'sd1, 10'sd0, 10'sd0,
        10'sd0, 10'sd24, -10'sd1, 10'sd0, -10'sd15};
  localparam logic [31:0] GOLD_INTERP_PRODUCT [0:9] =
      '{32'd1671168, 32'd0, 32'd335872, 32'd1982464, 32'd1490944,
        32'd1179648, 32'd0, 32'd0, 32'd0, 32'd786432};
  localparam logic [15:0] GOLD_INTERP_STEP [0:9] =
      '{16'd51, 16'd0, 16'd10, 16'd60, 16'd45, 16'd36, 16'd0, 16'd0,
        16'd0, 16'd24};
  localparam logic [63:0] GOLD_PRODUCT [0:9][0:1] = '{
      '{64'd102426380075008, 64'd38259853885440},
      '{64'd140737488355328, 64'd422212465065984},
      '{64'd40278203301888, 64'd30090649927680},
      '{64'd76913200594944, 64'd63860656570368},
      '{64'd74195560038400, 64'd66544142909440},
      '{64'd72110084980736, 64'd68576281100288},
      '{64'd8388608, 64'd0},
      '{64'd8388608, 64'd281474976710656},
      '{64'd0, 64'd140737488355328},
      '{64'd4611684918915760128, 64'd0}
    };
  localparam logic signed [10:0] GOLD_NET_SHIFT [0:9] =
      '{11'sd15, 11'sd17, 11'sd14, 11'sd15, 11'sd15,
        11'sd15, -11'sd9, 11'sd16, 11'sd15, 11'sd30};
  localparam logic [63:0] GOLD_SHIFTED [0:9][0:1] = '{
      '{64'd3125805056, 64'd1167598080},
      '{64'd1073741824, 64'd3221225472},
      '{64'd2458386432, 64'd1836587520},
      '{64'd2347204608, 64'd1948872576},
      '{64'd2264268800, 64'd2030766080},
      '{64'd2200625152, 64'd2092782016},
      '{64'd4294967296, 64'd0},
      '{64'd128, 64'd4294967296},
      '{64'd0, 64'd4294967296},
      '{64'd4294966272, 64'd0}
    };
  localparam logic [15:0] GOLD_FINAL_HALF [0:9][0:1] = '{
      '{16'h39d2, 16'h345a},
      '{16'h3400, 16'h3a00},
      '{16'h3894, 16'h36d8},
      '{16'h385f, 16'h3743},
      '{16'h3838, 16'h3791},
      '{16'h3819, 16'h37cc},
      '{16'h3c00, 16'h0000},
      '{16'h0000, 16'h3c00},
      '{16'h0000, 16'h3c00},
      '{16'h3c00, 16'h0000}
    };
  localparam logic [31:0] GOLD_M [0:9] =
      '{32'h3f800000, 32'h3f800000, 32'h3f800000, 32'h3f800000,
        32'h3f800000, 32'h3f800000, 32'h3f800000, 32'h3f800000,
        32'h3f800000, 32'h477fe000};
  localparam logic [31:0] GOLD_L [0:9] =
      '{32'h3fafd400, 32'h40800000, 32'h3f5fa800, 32'h3f83c900,
        32'h3f97be00, 32'h3fabb300, 32'h33800000, 32'h40000000,
        32'h3f800000, 32'h477fe000};
  localparam logic [31:0] GOLD_WEIGHT_OLD [0:9] =
      '{32'h3f3a4000, 32'h3e800000, 32'h3f128000, 32'h3f0be000,
        32'h3f070000, 32'h3f032000, 32'h3f800000, 32'h00000000,
        32'h00000000, 32'h3f800000};
  localparam logic [31:0] GOLD_WEIGHT_TILE [0:9] =
      '{32'h3e8b4000, 32'h3f400000, 32'h3edb0000, 32'h3ee86000,
        32'h3ef22000, 32'h3ef98000, 32'h00000000, 32'h3f800000,
        32'h3f800000, 32'h00000000};

  online_merge_update_engine #(
    .AddrWidth                  (17),
    .DataWidth                  (64),
    .PrecisionSupport           (1),
    .MixedNormalizationReciprocal (1'b1),
    .ScalarOnly                 (1'b1),
    .tcdm_req_t                 (tcdm_req_t),
    .tcdm_rsp_t                 (tcdm_rsp_t)
  ) i_engine (
    .clk_i (clk),
    .rst_ni (rst_ni),
    .src_m_old_i (src_m_old),
    .src_l_old_i (src_l_old),
    .src_o_old_i (src_o_old),
    .src_m_tile_i (src_m_tile),
    .src_l_tile_i (src_l_tile),
    .src_o_tile_i (src_o_tile),
    .dst_m_i (dst_m),
    .dst_l_i (dst_l),
    .dst_o_i (dst_o),
    .dst_weight_old_i (dst_weight_old),
    .dst_weight_tile_i (dst_weight_tile),
    .n_i (n),
    .d_i (d),
    .stride_i (stride),
    .mode_i (mode),
    .start_i (start),
    .clear_done_i (clear_done),
    .busy_o (busy),
    .done_o (done),
    .error_o (error),
    .tcdm_req_o (req),
    .tcdm_rsp_i (rsp)
  );

  always_comb begin
    rsp = '0;
    rsp.q_ready = 1'b1;
    rsp.p_valid = rsp_valid_q;
    rsp.p.data = rsp_data_q;
  end

  always_ff @(posedge clk) begin
    rsp_valid_q <= 1'b0;
    if (req.q_valid && !req.q.write) begin
      rsp_valid_q <= 1'b1;
      rsp_data_q <= req.q.addr[2] ?
          {memory[req.q.addr[7:2]], 32'd0} :
          {32'd0, memory[req.q.addr[7:2]]};
    end else if (req.q_valid && req.q.write) begin
      if (req.q.strb[3:0] != 0)
        memory[req.q.addr[7:2]] <= req.q.data[31:0];
      if (req.q.strb[7:4] != 0)
        memory[req.q.addr[7:2]] <= req.q.data[63:32];
    end
  end

  task automatic init_engine_case(
    input logic [31:0] m_old_bits,
    input logic [31:0] l_old_bits,
    input logic [31:0] m_tile_bits,
    input logic [31:0] l_tile_bits
  );
    begin
      for (int i = 0; i < 64; i++) memory[i] = 32'd0;
      memory[0] = m_old_bits;
      memory[1] = l_old_bits;
      memory[2] = m_tile_bits;
      memory[3] = l_tile_bits;
      src_m_old = 17'd0;
      src_l_old = 17'd4;
      src_m_tile = 17'd8;
      src_l_tile = 17'd12;
      src_o_old = 17'd32;
      src_o_tile = 17'd36;
      dst_m = 17'd16;
      dst_l = 17'd20;
      dst_o = 17'd40;
      dst_weight_old = 17'd24;
      dst_weight_tile = 17'd28;
      n = 32'd1;
      d = 32'd1;
      stride = 32'd0;
      mode = 32'd3;
      clear_done = 1'b0;
      start = 1'b0;
    end
  endtask

  task automatic restart_engine;
    begin
      clear_done = 1'b1;
      @(posedge clk);
      #0.1;
      clear_done = 1'b0;
      @(posedge clk);
      #0.1;
    end
  endtask

  // Each case is a full scalar engine run.  The reciprocal fields and both
  // old/tile products are compared against the software-frozen vectors above;
  // this deliberately covers the shared multiply, one-shot shift, FP16 RNE,
  // and writeback rather than only checking nonzero outputs.
  task automatic launch_engine(input int unsigned case_id);
    logic saw_old_product;
    logic saw_tile_product;
    begin
      saw_old_product = 1'b0;
      saw_tile_product = 1'b0;
      // Assert start away from the active edge so a repeated DONE->IDLE
      // launch cannot race the engine's sequential block.
      @(negedge clk);
      start = 1'b1;
      @(posedge clk);
      @(negedge clk);
      start = 1'b0;
      for (int cycles = 0; cycles < 500; cycles++) begin
        @(posedge clk);
        #0.1;
        if (i_engine.state_q == 3'd3 &&
            i_engine.weight_phase_q == 3'd1) begin
          saw_old_product = 1'b1;
          assert (i_engine.mixed_recip_index_d == GOLD_INDEX[case_id] &&
                  i_engine.mixed_recip_frac_d == GOLD_FRAC[case_id] &&
                  i_engine.mixed_recip_lut_lo_d == GOLD_LO[case_id] &&
                  i_engine.mixed_recip_lut_hi_d == GOLD_HI[case_id] &&
                  i_engine.mixed_recip_q1_15_q == GOLD_Q[case_id] &&
                  i_engine.mixed_recip_scale_exp_q == GOLD_S[case_id] &&
                  i_engine.mixed_recip_interp_product_d ==
                      GOLD_INTERP_PRODUCT[case_id] &&
                  i_engine.mixed_recip_interp_step_d ==
                      GOLD_INTERP_STEP[case_id] &&
                  i_engine.mixed_recip_product_d == GOLD_PRODUCT[case_id][0] &&
                  i_engine.mixed_recip_net_shift_d == GOLD_NET_SHIFT[case_id] &&
                  i_engine.mixed_recip_shifted_d == GOLD_SHIFTED[case_id][0] &&
                  i_engine.mixed_recip_weight_h_d == GOLD_FINAL_HALF[case_id][0] &&
                  !i_engine.mixed_recip_overflow_d)
            else $fatal(1, "old reciprocal trace mismatch case=%0d idx=%0d frac=%0d q=%0d s=%0d product=%0d net=%0d shifted=%0d half=%h",
                        case_id, i_engine.mixed_recip_index_d,
                        i_engine.mixed_recip_frac_d, i_engine.mixed_recip_q1_15_q,
                        i_engine.mixed_recip_scale_exp_q,
                        i_engine.mixed_recip_product_d,
                        i_engine.mixed_recip_net_shift_d,
                        i_engine.mixed_recip_shifted_d,
                        i_engine.mixed_recip_weight_h_d);
        end
        if (i_engine.state_q == 3'd3 &&
            i_engine.weight_phase_q == 3'd2) begin
          saw_tile_product = 1'b1;
          assert (i_engine.mixed_recip_index_d == GOLD_INDEX[case_id] &&
                  i_engine.mixed_recip_frac_d == GOLD_FRAC[case_id] &&
                  i_engine.mixed_recip_lut_lo_d == GOLD_LO[case_id] &&
                  i_engine.mixed_recip_lut_hi_d == GOLD_HI[case_id] &&
                  i_engine.mixed_recip_q1_15_q == GOLD_Q[case_id] &&
                  i_engine.mixed_recip_scale_exp_q == GOLD_S[case_id] &&
                  i_engine.mixed_recip_interp_product_d ==
                      GOLD_INTERP_PRODUCT[case_id] &&
                  i_engine.mixed_recip_interp_step_d ==
                      GOLD_INTERP_STEP[case_id] &&
                  i_engine.mixed_recip_product_d == GOLD_PRODUCT[case_id][1] &&
                  i_engine.mixed_recip_net_shift_d == GOLD_NET_SHIFT[case_id] &&
                  i_engine.mixed_recip_shifted_d == GOLD_SHIFTED[case_id][1] &&
                  i_engine.mixed_recip_weight_h_d == GOLD_FINAL_HALF[case_id][1] &&
                  !i_engine.mixed_recip_overflow_d)
            else $fatal(1, "tile reciprocal trace mismatch case=%0d product=%0d net=%0d shifted=%0d half=%h overflow=%b",
                        case_id, i_engine.mixed_recip_product_d,
                        i_engine.mixed_recip_net_shift_d,
                        i_engine.mixed_recip_shifted_d,
                        i_engine.mixed_recip_weight_h_d,
                        i_engine.mixed_recip_overflow_d);
        end
        if (done || error) begin
          assert (done && !error)
            else $fatal(1, "reciprocal engine returned ERROR");
          break;
        end
        if (cycles == 499)
          $fatal(1, "reciprocal engine timeout");
      end
      assert (saw_old_product)
        else $fatal(1, "case=%0d old reciprocal product phase was not observed", case_id);
      assert (saw_tile_product)
        else $fatal(1, "case=%0d tile reciprocal product phase was not observed", case_id);
      assert (memory[4] == GOLD_M[case_id] && memory[5] == GOLD_L[case_id] &&
              memory[6] == GOLD_WEIGHT_OLD[case_id] &&
              memory[7] == GOLD_WEIGHT_TILE[case_id])
        else $fatal(1, "case=%0d reciprocal final bits mismatch m=%h l=%h old=%h tile=%h",
                    case_id, memory[4], memory[5], memory[6], memory[7]);
      assert (i_engine.sim_compute_weight_cycles_q == 64'd3)
        else $fatal(1, "reciprocal COMPUTE_WEIGHT cycles mismatch: %0d",
                    i_engine.sim_compute_weight_cycles_q);
    end
  endtask

  initial begin
    clk = 1'b0;
    rst_ni = 1'b0;
    init_engine_case(32'h3f80_0000, 32'h3f80_0000,
                     32'h0000_0000, 32'h3f80_0000);
    fork
      forever #1 clk = ~clk;
    join_none
    repeat (2) @(posedge clk);
    #0.1;
    rst_ni = 1'b1;

    init_engine_case(32'h3f80_0000, 32'h3f80_0000,
                     32'h0000_0000, 32'h3f80_0000);
    launch_engine(0);

    restart_engine();
    init_engine_case(32'h3f80_0000, 32'h3f80_0000,
                     32'h3f80_0000, 32'h4040_0000);
    launch_engine(1);

    // A few deterministic legal num<=den workload points exercise the shared
    // multiplier beyond the frozen engine vector.
    for (int unsigned r = 0; r < 4; r++) begin
      restart_engine();
      init_engine_case(32'h3f80_0000,
          (32'h3f00_0000 + (r << 20)),
          32'h0000_0000,
          (32'h3f80_0000 + (r << 21)));
      launch_engine(2 + r);
    end

    // Full-path boundary coverage.  0000/0000 is intentionally left to the
    // direct reciprocal unit test because the engine's unsupported contract
    // rejects a zero denominator.
    restart_engine();
    init_engine_case(32'h3f80_0000, 32'h3380_0000,
                     32'h0000_0000, 32'h0000_0000);
    launch_engine(6); // 0001/0001, negative net shift

    restart_engine();
    init_engine_case(32'h3f80_0000, 32'h3380_0000,
                     32'h3f80_0000, 32'h4000_0000);
    launch_engine(7); // 0001/4000, RNE tie to zero

    restart_engine();
    init_engine_case(32'h3f80_0000, 32'h0000_0000,
                     32'h3f80_0000, 32'h3f80_0000);
    launch_engine(8); // 0000/positive

    restart_engine();
    init_engine_case(32'h477f_e000, 32'h477f_e000,
                     32'h0000_0000, 32'h477f_e000);
    launch_engine(9); // 7bff/7bff, index 255 plus terminal endpoint

    $display("online_merge_engine_reciprocal_tb PASS");
    $finish;
  end
endmodule
