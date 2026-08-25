// Minimal TCDM behavioral check for mode latch and mixed Scalar SMU.
module online_merge_engine_mixed_tb;
  import online_merge_resource_types_pkg::*;

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

  online_merge_update_engine #(
    .AddrWidth  (17),
    .DataWidth  (64),
    .tcdm_req_t (tcdm_req_t),
    .tcdm_rsp_t (tcdm_rsp_t)
  ) i_engine (
    .clk_i (clk),
    .rst_ni,
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
    .dst_weight_tile_i(dst_weight_tile),
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

  task automatic init_case;
    begin
      for (int i = 0; i < 64; i++) memory[i] = 32'd0;
      memory[0] = 32'h3f80_0000; // m_old = 1
      memory[1] = 32'h3f80_0000; // l_old = 1
      memory[2] = 32'h0000_0000; // m_tile = 0
      memory[3] = 32'h3f80_0000; // l_tile = 1
      memory[8] = 32'h3f80_0000; // O_old = 1
      memory[9] = 32'h4040_0000; // O_tile = 3
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
      clear_done = 1'b0;
      start = 1'b0;
    end
  endtask

  task automatic launch_and_wait(input logic [31:0] launch_mode);
    begin
      mode = launch_mode;
      start = 1'b1;
      @(posedge clk);
      #0.1;
      // Deliberately change the live register after acceptance.  The engine
      // must continue using the latched mode_q for every FSM branch.
      mode = 32'd0;
      start = 1'b0;
      for (int cycles = 0; cycles < 1000; cycles++) begin
        @(posedge clk);
        #0.1;
        if (done || error) begin
          assert (done && !error)
            else $fatal(1, "engine returned error for mode=%0d", launch_mode);
          break;
        end
        if (cycles == 999)
          $fatal(1, "engine timeout for mode=%0d", launch_mode);
      end
    end
  endtask

  task automatic expect_invalid(input logic [31:0] invalid_mode);
    begin
      mode = invalid_mode;
      start = 1'b1;
      @(posedge clk);
      #0.1;
      start = 1'b0;
      for (int cycles = 0; cycles < 4; cycles++) begin
        @(posedge clk);
        #0.1;
        if (error) break;
      end
      assert (error && !busy)
        else $fatal(1, "invalid mode %0d was accepted", invalid_mode);
      clear_done = 1'b1;
      @(posedge clk);
      #0.1;
      clear_done = 1'b0;
    end
  endtask

  task automatic expect_mixed_data_error(
    input logic [31:0] m_old_bits,
    input logic [31:0] l_old_bits,
    input logic [31:0] l_tile_bits
  );
    begin
      init_case();
      memory[0] = m_old_bits;
      memory[1] = l_old_bits;
      memory[3] = l_tile_bits;
      mode = 32'd3;
      start = 1'b1;
      @(posedge clk);
      #0.1;
      start = 1'b0;
      for (int cycles = 0; cycles < 1000; cycles++) begin
        @(posedge clk);
        #0.1;
        if (error) break;
        if (done)
          $fatal(1, "invalid mixed data was accepted");
        if (cycles == 999)
          $fatal(1, "invalid mixed data did not reach ERROR");
      end
      assert (error && !busy)
        else $fatal(1, "invalid mixed data did not assert ERROR");
      clear_done = 1'b1;
      @(posedge clk);
      #0.1;
      clear_done = 1'b0;
    end
  endtask

  initial begin
    clk = 1'b0;
    rst_ni = 1'b0;
    init_case();
    fork
      forever #1 clk = ~clk;
    join_none
    repeat (2) @(posedge clk);
    #0.1;
    rst_ni = 1'b1;

    // Proposed mixed Scalar mode.  A mode change immediately after start
    // must not turn this into legacy Full or legacy Scalar behavior.
    launch_and_wait(32'd3);
    $display("MODE3 m=%h l=%h w_old=%h w_tile=%h", memory[4], memory[5],
             memory[6], memory[7]);
    assert (memory[4] == 32'h3f80_0000 && memory[5] == 32'h3faf_d400 &&
            memory[6] == 32'h3f3a_6000 && memory[7] == 32'h3e8b_4000)
      else $fatal(1, "mixed Scalar exact scalar result mismatch");
    assert (i_engine.sim_compute_weight_cycles_q == 64'd78)
      else $fatal(1, "mixed Scalar COMPUTE_WEIGHT cycles changed: %0d",
                  i_engine.sim_compute_weight_cycles_q);
    assert (memory[6] != 32'd0 && memory[7] != 32'd0)
      else $fatal(1, "mixed scalar weights were not written");
    assert ((memory[6][31] == 1'b0) && (memory[7][31] == 1'b0))
      else $fatal(1, "mixed weights are not positive FP32 values");
    assert (memory[6] < 32'h3f80_0000 && memory[7] < 32'h3f80_0000)
      else $fatal(1, "mixed weights outside (0,1)");

    // Mixed Full is retained as an explicit ablation; it widens the FP16
    // weights into the existing fixed-point vector expression.
    clear_done = 1'b1;
    @(posedge clk);
    #0.1;
    clear_done = 1'b0;
    init_case();
    launch_and_wait(32'd2);
    $display("MODE2 m=%h l=%h o=%h", memory[4], memory[5], memory[10]);
    assert (memory[4] == 32'h3f80_0000 && memory[5] == 32'h3faf_d400 &&
            memory[10] == 32'h3fc5_a000)
      else $fatal(1, "mixed Full exact scalar/vector result mismatch");
    assert (i_engine.sim_compute_weight_cycles_q == 64'd78)
      else $fatal(1, "mixed Full COMPUTE_WEIGHT cycles changed: %0d",
                  i_engine.sim_compute_weight_cycles_q);

    // Legacy Scalar remains accepted and uses the old reciprocal path.
    clear_done = 1'b1;
    @(posedge clk);
    #0.1;
    clear_done = 1'b0;
    init_case();
    launch_and_wait(32'd1);
    $display("MODE1 m=%h l=%h w_old=%h w_tile=%h", memory[4], memory[5],
             memory[6], memory[7]);
    assert (i_engine.sim_compute_weight_cycles_q == 64'd1)
      else $fatal(1, "legacy Scalar COMPUTE_WEIGHT cycles changed: %0d",
                  i_engine.sim_compute_weight_cycles_q);
    assert (memory[4] == 32'h3f80_0000 && memory[5] == 32'h3faf_16ac &&
            memory[6] == 32'h3f3b_26b8 && memory[7] == 32'h3e89_b2bb)
      else $fatal(1, "legacy Scalar exact result mismatch");
    clear_done = 1'b1;
    @(posedge clk);
    #0.1;
    clear_done = 1'b0;
    init_case();
    launch_and_wait(32'd0);
    $display("MODE0 m=%h l=%h o=%h", memory[4], memory[5], memory[10]);
    assert (memory[4] == 32'h3f80_0000 && memory[5] == 32'h3faf_16ac &&
            memory[10] == 32'h3fc4_d968)
      else $fatal(1, "legacy Full exact scalar/vector result mismatch");
    init_case();
    expect_invalid(32'd4);
    expect_mixed_data_error(32'h4780_0000, 32'h3f80_0000, 32'h3f80_0000);
    expect_mixed_data_error(32'h3f80_0000, 32'h4780_0000, 32'h3f80_0000);
    expect_mixed_data_error(32'h3f80_0000, 32'h0000_0000, 32'h0000_0000);

    $display("online_merge_engine_mixed_tb PASS");
    $finish;
  end
endmodule
