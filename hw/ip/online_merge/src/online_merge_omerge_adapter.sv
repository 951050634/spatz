// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

// Minimal control adapter for the scalar-side OMERGE instruction.  The
// arithmetic remains entirely in online_merge_update_engine; this block only
// supplies persistent configuration, selects the A/B state buffers, and
// translates the accelerator issue/response handshake.
module online_merge_omerge_adapter #(
  parameter int unsigned AddrWidth = 32,
  parameter type acc_issue_req_t = logic,
  parameter type acc_rsp_t = logic
) (
  input  logic                 clk_i,
  input  logic                 rst_ni,

  input  acc_issue_req_t       req_i,
  input  logic                 req_valid_i,
  output logic                 req_ready_o,

  output acc_rsp_t             rsp_o,
  output logic                 rsp_valid_o,
  input  logic                 rsp_ready_i,

  input  logic [AddrWidth-1:0] state_a_m_i,
  input  logic [AddrWidth-1:0] state_a_l_i,
  input  logic [AddrWidth-1:0] state_b_m_i,
  input  logic [AddrWidth-1:0] state_b_l_i,
  input  logic [AddrWidth-1:0] tile_m_i,
  input  logic [AddrWidth-1:0] tile_l_i,
  input  logic [AddrWidth-1:0] dst_weight_old_i,
  input  logic [AddrWidth-1:0] dst_weight_tile_i,
  input  logic [31:0]          n_i,
  input  logic [31:0]          d_i,
  input  logic [31:0]          stride_i,
  input  logic                 config_reset_i,

  input  logic                 engine_busy_i,
  input  logic                 engine_done_i,
  input  logic                 engine_error_i,

  output logic [AddrWidth-1:0] src_m_old_o,
  output logic [AddrWidth-1:0] src_l_old_o,
  output logic [AddrWidth-1:0] src_o_old_o,
  output logic [AddrWidth-1:0] src_m_tile_o,
  output logic [AddrWidth-1:0] src_l_tile_o,
  output logic [AddrWidth-1:0] src_o_tile_o,
  output logic [AddrWidth-1:0] dst_m_o,
  output logic [AddrWidth-1:0] dst_l_o,
  output logic [AddrWidth-1:0] dst_o_o,
  output logic [AddrWidth-1:0] dst_weight_old_o,
  output logic [AddrWidth-1:0] dst_weight_tile_o,
  output logic [31:0]          n_o,
  output logic [31:0]          d_o,
  output logic [31:0]          stride_o,
  output logic [31:0]          mode_o,
  output logic                 start_o,
  output logic                 clear_done_o,
  output logic                 config_active_o,
  output logic                 selector_o
);

  typedef enum logic [1:0] {
    IDLE,
    START,
    WAIT,
    RESP
  } state_e;

  state_e state_q;
  logic selector_q;
  logic [5:0] response_id_q;

  assign req_ready_o = (state_q == IDLE) && !engine_busy_i;
  assign rsp_valid_o = (state_q == RESP);
  assign config_active_o = (state_q != IDLE);
  assign selector_o = selector_q;

  always_comb begin
    rsp_o = '0;
    rsp_o.id = response_id_q;
    rsp_o.error = engine_error_i;
    rsp_o.data = '0;
    rsp_o.data[0] = engine_error_i;
  end

  // OMERGE is fixed to mode 3 (Mixed Scalar).  The O-vector addresses are
  // not consumed in this mode, but zero is a legal aligned value required by
  // the existing engine configuration checks.
  always_comb begin
    src_m_old_o = selector_q ? state_b_m_i : state_a_m_i;
    src_l_old_o = selector_q ? state_b_l_i : state_a_l_i;
    dst_m_o = selector_q ? state_a_m_i : state_b_m_i;
    dst_l_o = selector_q ? state_a_l_i : state_b_l_i;
    src_o_old_o = '0;
    src_o_tile_o = '0;
    dst_o_o = '0;
    src_m_tile_o = tile_m_i;
    src_l_tile_o = tile_l_i;
    dst_weight_old_o = dst_weight_old_i;
    dst_weight_tile_o = dst_weight_tile_i;
    n_o = n_i;
    d_o = d_i;
    stride_o = stride_i;
    mode_o = 32'd3;
    start_o = (state_q == START);
    // Clear a prior DONE/ERROR result on the request-accept cycle.  The
    // engine handles clear_done_i before its state case, so START must be
    // delayed by one cycle; asserting both together would clear a terminal
    // engine state and then miss the start event.
    clear_done_o = (state_q == IDLE) && req_valid_i && req_ready_o;
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q <= IDLE;
      selector_q <= 1'b0;
      response_id_q <= '0;
    end else begin
      if (config_reset_i && (state_q == IDLE)) begin
        selector_q <= 1'b0;
      end

      unique case (state_q)
        IDLE: begin
          if (req_valid_i && req_ready_o) begin
            response_id_q <= req_i.id;
            state_q <= START;
          end
        end

        // The one-cycle START state guarantees exactly one engine start even
        // if the accelerator response is back-pressured.
        START: begin
          state_q <= WAIT;
        end

        WAIT: begin
          if (engine_done_i || engine_error_i) begin
            state_q <= RESP;
          end
        end

        RESP: begin
          if (rsp_valid_o && rsp_ready_i) begin
            if (!engine_error_i) begin
              // Commit the A/B transition only when the accelerator response
              // itself has been accepted by the Snitch response path.
              selector_q <= ~selector_q;
            end
            state_q <= IDLE;
          end
        end

        default: state_q <= IDLE;
      endcase
    end
  end

  // Structured simulation evidence for the Gate 1 handshake/selector audit.
  // This observer is omitted by synthesis and does not affect functionality.
  // pragma translate_off
  always_ff @(posedge clk_i) begin
    if (rst_ni && req_valid_i && req_ready_o) begin
      $display("OMERGE_ADAPTER_ACCEPT id=%0d selector=%0d", req_i.id,
               selector_q);
    end
    if (rst_ni && start_o) begin
      $display("OMERGE_ADAPTER_START selector=%0d", selector_q);
    end
    if (rst_ni && (engine_done_i || engine_error_i) && (state_q == WAIT)) begin
      $display("OMERGE_ADAPTER_DONE error=%0d selector=%0d",
               engine_error_i, selector_q);
    end
    if (rst_ni && rsp_valid_o && rsp_ready_i) begin
      $display("OMERGE_ADAPTER_RESPONSE error=%0d selector_before=%0d selector_after=%0d",
               engine_error_i, selector_q,
               engine_error_i ? selector_q : ~selector_q);
    end
  end
  // pragma translate_on

endmodule
