// PrecisionSupport elaboration/acceptance checks.  This test keeps the
// interface identical while checking the legal and illegal mode sets of the
// legacy-only and mixed-only engine variants.
module online_merge_precision_support_tb;
  import online_merge_resource_types_pkg::*;

  logic clk, rst_ni;
  logic [16:0] src_m_old0, src_l_old0, src_o_old0;
  logic [16:0] src_m_tile0, src_l_tile0, src_o_tile0;
  logic [16:0] dst_m0, dst_l0, dst_o0, dst_weight_old0, dst_weight_tile0;
  logic [31:0] n0, d0, stride0, mode0;
  logic start0, clear0, busy0, done0, error0;
  tcdm_req_t req0;
  tcdm_rsp_t rsp0;
  logic [31:0] memory0 [0:63];
  logic rsp_valid0;
  logic [63:0] rsp_data0;

  logic [16:0] src_m_old1, src_l_old1, src_o_old1;
  logic [16:0] src_m_tile1, src_l_tile1, src_o_tile1;
  logic [16:0] dst_m1, dst_l1, dst_o1, dst_weight_old1, dst_weight_tile1;
  logic [31:0] n1, d1, stride1, mode1;
  logic start1, clear1, busy1, done1, error1;
  tcdm_req_t req1;
  tcdm_rsp_t rsp1;
  logic [31:0] memory1 [0:63];
  logic rsp_valid1;
  logic [63:0] rsp_data1;

  online_merge_update_engine #(
    .PrecisionSupport (0),
    .AddrWidth       (17),
    .DataWidth       (64),
    .tcdm_req_t      (tcdm_req_t),
    .tcdm_rsp_t      (tcdm_rsp_t)
  ) i_legacy_only (
    .clk_i (clk), .rst_ni (rst_ni),
    .src_m_old_i (src_m_old0), .src_l_old_i (src_l_old0),
    .src_o_old_i (src_o_old0), .src_m_tile_i (src_m_tile0),
    .src_l_tile_i (src_l_tile0), .src_o_tile_i (src_o_tile0),
    .dst_m_i (dst_m0), .dst_l_i (dst_l0), .dst_o_i (dst_o0),
    .dst_weight_old_i (dst_weight_old0),
    .dst_weight_tile_i (dst_weight_tile0), .n_i (n0), .d_i (d0),
    .stride_i (stride0), .mode_i (mode0), .start_i (start0),
    .clear_done_i (clear0), .busy_o (busy0), .done_o (done0),
    .error_o (error0), .tcdm_req_o (req0), .tcdm_rsp_i (rsp0)
  );

  online_merge_update_engine #(
    .PrecisionSupport (1),
    .AddrWidth       (17),
    .DataWidth       (64),
    .tcdm_req_t      (tcdm_req_t),
    .tcdm_rsp_t      (tcdm_rsp_t)
  ) i_mixed_only (
    .clk_i (clk), .rst_ni (rst_ni),
    .src_m_old_i (src_m_old1), .src_l_old_i (src_l_old1),
    .src_o_old_i (src_o_old1), .src_m_tile_i (src_m_tile1),
    .src_l_tile_i (src_l_tile1), .src_o_tile_i (src_o_tile1),
    .dst_m_i (dst_m1), .dst_l_i (dst_l1), .dst_o_i (dst_o1),
    .dst_weight_old_i (dst_weight_old1),
    .dst_weight_tile_i (dst_weight_tile1), .n_i (n1), .d_i (d1),
    .stride_i (stride1), .mode_i (mode1), .start_i (start1),
    .clear_done_i (clear1), .busy_o (busy1), .done_o (done1),
    .error_o (error1), .tcdm_req_o (req1), .tcdm_rsp_i (rsp1)
  );

  always_comb begin
    rsp0 = '0;
    rsp0.q_ready = 1'b1;
    rsp0.p_valid = rsp_valid0;
    rsp0.p.data = rsp_data0;
    rsp1 = '0;
    rsp1.q_ready = 1'b1;
    rsp1.p_valid = rsp_valid1;
    rsp1.p.data = rsp_data1;
  end

  always_ff @(posedge clk) begin
    rsp_valid0 <= 1'b0;
    if (req0.q_valid && !req0.q.write) begin
      rsp_valid0 <= 1'b1;
      rsp_data0 <= req0.q.addr[2] ?
          {memory0[req0.q.addr[7:2]], 32'd0} :
          {32'd0, memory0[req0.q.addr[7:2]]};
    end else if (req0.q_valid && req0.q.write) begin
      if (req0.q.strb[3:0] != 0)
        memory0[req0.q.addr[7:2]] <= req0.q.data[31:0];
      if (req0.q.strb[7:4] != 0)
        memory0[req0.q.addr[7:2]] <= req0.q.data[63:32];
    end
    rsp_valid1 <= 1'b0;
    if (req1.q_valid && !req1.q.write) begin
      rsp_valid1 <= 1'b1;
      rsp_data1 <= req1.q.addr[2] ?
          {memory1[req1.q.addr[7:2]], 32'd0} :
          {32'd0, memory1[req1.q.addr[7:2]]};
    end else if (req1.q_valid && req1.q.write) begin
      if (req1.q.strb[3:0] != 0)
        memory1[req1.q.addr[7:2]] <= req1.q.data[31:0];
      if (req1.q.strb[7:4] != 0)
        memory1[req1.q.addr[7:2]] <= req1.q.data[63:32];
    end
  end

  task automatic init_cases;
    begin
      for (int i = 0; i < 64; i++) begin
        memory0[i] = 32'd0;
        memory1[i] = 32'd0;
      end
      memory0[0] = 32'h3f80_0000;
      memory0[1] = 32'h3f80_0000;
      memory0[2] = 32'h0000_0000;
      memory0[3] = 32'h3f80_0000;
      memory1 = memory0;
      src_m_old0 = 17'd0; src_l_old0 = 17'd4; src_o_old0 = 17'd32;
      src_m_tile0 = 17'd8; src_l_tile0 = 17'd12; src_o_tile0 = 17'd36;
      dst_m0 = 17'd16; dst_l0 = 17'd20; dst_o0 = 17'd40;
      dst_weight_old0 = 17'd24; dst_weight_tile0 = 17'd28;
      src_m_old1 = src_m_old0; src_l_old1 = src_l_old0;
      src_o_old1 = src_o_old0; src_m_tile1 = src_m_tile0;
      src_l_tile1 = src_l_tile0; src_o_tile1 = src_o_tile0;
      dst_m1 = dst_m0; dst_l1 = dst_l0; dst_o1 = dst_o0;
      dst_weight_old1 = dst_weight_old0; dst_weight_tile1 = dst_weight_tile0;
      n0 = 32'd1; d0 = 32'd1; stride0 = 32'd0;
      n1 = n0; d1 = d0; stride1 = stride0;
      start0 = 1'b0; clear0 = 1'b0; mode0 = 32'd0;
      start1 = 1'b0; clear1 = 1'b0; mode1 = 32'd0;
    end
  endtask

  task automatic expect_error0(input logic [31:0] requested_mode);
    begin
      mode0 = requested_mode;
      start0 = 1'b1;
      @(posedge clk);
      #0.1;
      start0 = 1'b0;
      @(posedge clk);
      #0.1;
      assert (error0 && !busy0)
        else $fatal(1, "legacy-only accepted mode %0d", requested_mode);
      clear0 = 1'b1;
      @(posedge clk);
      #0.1;
      clear0 = 1'b0;
    end
  endtask

  task automatic expect_error1(input logic [31:0] requested_mode);
    begin
      mode1 = requested_mode;
      start1 = 1'b1;
      @(posedge clk);
      #0.1;
      start1 = 1'b0;
      @(posedge clk);
      #0.1;
      assert (error1 && !busy1)
        else $fatal(1, "mixed-only accepted mode %0d", requested_mode);
      clear1 = 1'b1;
      @(posedge clk);
      #0.1;
      clear1 = 1'b0;
    end
  endtask

  task automatic expect_done0;
    begin
      mode0 = 32'd1;
      start0 = 1'b1;
      @(posedge clk);
      #0.1;
      start0 = 1'b0;
      for (int cycles = 0; cycles < 1000; cycles++) begin
        @(posedge clk);
        #0.1;
        if (done0 || error0) break;
      end
      assert (done0 && !error0) else $fatal(1, "legacy-only mode1 failed");
    end
  endtask

  task automatic expect_done1;
    begin
      mode1 = 32'd3;
      start1 = 1'b1;
      @(posedge clk);
      #0.1;
      start1 = 1'b0;
      for (int cycles = 0; cycles < 1000; cycles++) begin
        @(posedge clk);
        #0.1;
        if (done1 || error1) break;
      end
      assert (done1 && !error1) else $fatal(1, "mixed-only mode3 failed");
    end
  endtask

  initial begin
    clk = 1'b0;
    rst_ni = 1'b0;
    init_cases();
    fork
      forever #1 clk = ~clk;
    join_none
    repeat (2) @(posedge clk);
    #0.1;
    rst_ni = 1'b1;

    expect_error0(32'd2);
    expect_error0(32'd3);
    expect_error1(32'd0);
    expect_error1(32'd1);
    expect_done0();
    clear0 = 1'b1;
    @(posedge clk);
    #0.1;
    clear0 = 1'b0;
    init_cases();
    expect_done1();

    $display("online_merge_precision_support_tb PASS");
    $finish;
  end
endmodule
