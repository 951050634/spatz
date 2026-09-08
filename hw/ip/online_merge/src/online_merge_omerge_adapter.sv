// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

// Scalar-side OMCFG/OMERGE control adapter.  Arithmetic remains entirely in
// online_merge_update_engine.  This block tracks configuration validity,
// selects the A/B state buffers, and translates accelerator handshakes.
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

  // Canonical configuration values are the existing MMIO registers.  OMCFG
  // writes their hardware-update side through omcfg_*_o below.
  input  logic [AddrWidth-1:0] state_a_m_i,
  input  logic [AddrWidth-1:0] state_a_l_i,
  input  logic [AddrWidth-1:0] state_b_m_i,
  input  logic [AddrWidth-1:0] state_b_l_i,
  input  logic [AddrWidth-1:0] tile_m_i,
  input  logic [AddrWidth-1:0] tile_l_i,
  input  logic [AddrWidth-1:0] dst_weight_old_i,
  input  logic [AddrWidth-1:0] dst_weight_tile_i,
  input  logic [31:0]          n_i,
  input  logic [8:0]           mmio_cfg_write_i,
  input  logic                 mmio_init_i,

  output logic                 omcfg_write_o,
  output logic [11:0]          omcfg_id_o,
  output logic [31:0]          omcfg_value_o,

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
  output logic                 cfg_valid_o,
  output logic [8:0]           cfg_written_mask_o,
  output logic                 selector_o
);

  localparam logic [31:0] OMCFG_MASK  = 32'h0000_7fff;
  localparam logic [31:0] OMCFG_MATCH = 32'h0000_105b;
  localparam logic [31:0] OMERGE_MASK  = 32'hffff_f07f;
  localparam logic [31:0] OMERGE_MATCH = 32'h0600_005b;

  localparam logic [11:0] CFG_CTRL = 12'h009;
  localparam logic [8:0] REQUIRED_MASK = 9'h1ff;

  typedef enum logic [1:0] {
    IDLE,
    START,
    WAIT,
    RESP
  } state_e;

  state_e state_q;
  logic selector_q, selector_d;
  logic cfg_valid_q, cfg_valid_d;
  logic [8:0] cfg_written_mask_q, cfg_written_mask_d;
  logic [5:0] response_id_q;
  logic response_error_q;

  logic req_is_omcfg, req_is_omerge, req_accept;
  logic [11:0] req_cfg_id;
  logic [31:0] req_cfg_value;
  logic [8:0] req_cfg_field_mask;

  assign req_is_omcfg = (req_i.data_op & OMCFG_MASK) == OMCFG_MATCH;
  assign req_is_omerge = (req_i.data_op & OMERGE_MASK) == OMERGE_MATCH;
  assign req_cfg_id = req_i.data_op[31:20];
  assign req_cfg_value = req_i.data_arga[31:0];

  always_comb begin
    req_cfg_field_mask = '0;
    if (req_cfg_id < CFG_CTRL) begin
      req_cfg_field_mask[req_cfg_id[3:0]] = 1'b1;
    end
  end

  // Both commands share the existing one-entry accelerator path.  OMCFG is
  // consequently back-pressured for the complete active OMERGE interval.
  assign req_ready_o = (state_q == IDLE) && !engine_busy_i &&
      !(|mmio_cfg_write_i) && !mmio_init_i &&
      (req_is_omcfg || req_is_omerge);
  assign req_accept = req_valid_i && req_ready_o;
  assign rsp_valid_o = (state_q == RESP);
  assign config_active_o = (state_q != IDLE);
  assign cfg_valid_o = cfg_valid_q;
  assign cfg_written_mask_o = cfg_written_mask_q;
  assign selector_o = selector_q;

  // A normal OMCFG write updates the hardware side of the existing generated
  // MMIO register.  CTRL and reserved IDs never assert this write strobe.
  assign omcfg_write_o = req_accept && req_is_omcfg && (req_cfg_id < CFG_CTRL);
  assign omcfg_id_o = req_cfg_id;
  assign omcfg_value_o = req_cfg_value;

  always_comb begin
    rsp_o = '0;
    rsp_o.id = response_id_q;
    rsp_o.error = response_error_q;
    rsp_o.data = '0;
    rsp_o.data[0] = response_error_q;
  end

  // OMERGE is fixed to mode 3 (Mixed Scalar).  The O-vector addresses are
  // not consumed in this mode.  D and stride likewise have no scalar
  // recurrence dependency, so legal constants satisfy the unchanged generic
  // engine configuration check without expanding OMCFG v1.
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
    d_o = 32'd1;
    stride_o = 32'd0;
    mode_o = 32'd3;
    start_o = (state_q == START);

    // Clear a prior engine terminal state before a valid launch, before an
    // adapter-generated invalid-config response, or on OMCFG INIT.
    clear_done_o = req_accept &&
        (req_is_omerge ||
         (req_is_omcfg && (req_cfg_id == CFG_CTRL) && req_cfg_value[0]));
  end

  // MMIO and OMCFG writes share validity tracking.  A normal write dirties
  // the context; INIT commits only a complete required mask.
  always_comb begin
    cfg_written_mask_d = cfg_written_mask_q;
    cfg_valid_d = cfg_valid_q;
    selector_d = selector_q;

    if (|mmio_cfg_write_i) begin
      cfg_written_mask_d = cfg_written_mask_q | mmio_cfg_write_i;
      cfg_valid_d = 1'b0;
    end

    if (mmio_init_i) begin
      if ((cfg_written_mask_d & REQUIRED_MASK) == REQUIRED_MASK) begin
        cfg_valid_d = 1'b1;
        selector_d = 1'b0;
      end else begin
        cfg_valid_d = 1'b0;
      end
    end

    if (req_accept && req_is_omcfg) begin
      if (req_cfg_id < CFG_CTRL) begin
        cfg_written_mask_d = cfg_written_mask_d | req_cfg_field_mask;
        cfg_valid_d = 1'b0;
      end else if ((req_cfg_id == CFG_CTRL) && req_cfg_value[0]) begin
        if ((cfg_written_mask_d & REQUIRED_MASK) == REQUIRED_MASK) begin
          cfg_valid_d = 1'b1;
          selector_d = 1'b0;
        end else begin
          cfg_valid_d = 1'b0;
        end
      end else if (req_cfg_id != CFG_CTRL) begin
        // Reserved IDs modify no value register and deterministically make a
        // later OMERGE require another successful INIT.
        cfg_valid_d = 1'b0;
      end
    end

    if (rsp_valid_o && rsp_ready_i && !response_error_q) begin
      // Commit the A/B transition only when the successful OMERGE response is
      // accepted by the Snitch response path.
      selector_d = ~selector_q;
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      cfg_written_mask_q <= '0;
      cfg_valid_q <= 1'b0;
      selector_q <= 1'b0;
    end else begin
      cfg_written_mask_q <= cfg_written_mask_d;
      cfg_valid_q <= cfg_valid_d;
      selector_q <= selector_d;
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q <= IDLE;
      response_id_q <= '0;
      response_error_q <= 1'b0;
    end else begin
      unique case (state_q)
        IDLE: begin
          if (req_accept && req_is_omerge) begin
            response_id_q <= req_i.id;
            response_error_q <= !cfg_valid_q;
            state_q <= cfg_valid_q ? START : RESP;
          end
        end

        // The one-cycle START state guarantees exactly one engine start even
        // if the accelerator response is back-pressured.
        START: begin
          state_q <= WAIT;
        end

        WAIT: begin
          if (engine_done_i || engine_error_i) begin
            response_error_q <= engine_error_i;
            state_q <= RESP;
          end
        end

        RESP: begin
          if (rsp_valid_o && rsp_ready_i) begin
            state_q <= IDLE;
          end
        end

        default: state_q <= IDLE;
      endcase
    end
  end

  // Structured directed-test evidence.  These observers do not affect RTL.
  // pragma translate_off
  always_ff @(posedge clk_i) begin
    if (rst_ni && req_accept && req_is_omcfg) begin
      if (req_cfg_id < CFG_CTRL) begin
        $display("OMCFG_ADAPTER_WRITE cfg_id=%0d rs1=x%0d value=0x%08x mask_before=0x%03x mask_after=0x%03x",
                 req_cfg_id, req_i.data_op[19:15], req_cfg_value,
                 cfg_written_mask_q, cfg_written_mask_d);
      end else if (req_cfg_id == CFG_CTRL) begin
        $display("OMCFG_ADAPTER_INIT value=0x%08x mask=0x%03x complete=%0d cfg_valid_after=%0d selector_after=%0d",
                 req_cfg_value, cfg_written_mask_q,
                 (cfg_written_mask_q == REQUIRED_MASK), cfg_valid_d,
                 selector_d);
      end else begin
        $display("OMCFG_ADAPTER_RESERVED cfg_id=%0d rs1=x%0d value=0x%08x cfg_valid_after=%0d",
                 req_cfg_id, req_i.data_op[19:15], req_cfg_value,
                 cfg_valid_d);
      end
    end
    if (rst_ni && (|mmio_cfg_write_i)) begin
      $display("OMCFG_ADAPTER_MMIO_WRITE fields=0x%03x mask_before=0x%03x mask_after=0x%03x",
               mmio_cfg_write_i, cfg_written_mask_q, cfg_written_mask_d);
    end
    if (rst_ni && mmio_init_i) begin
      $display("OMCFG_ADAPTER_MMIO_INIT mask=0x%03x cfg_valid_after=%0d selector_after=%0d",
               cfg_written_mask_d, cfg_valid_d, selector_d);
    end
    if (rst_ni && req_accept && req_is_omerge) begin
      $display("OMERGE_ADAPTER_ACCEPT id=%0d cfg_valid=%0d selector=%0d",
               req_i.id, cfg_valid_q, selector_q);
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
               response_error_q, selector_q,
               response_error_q ? selector_q : ~selector_q);
    end
  end
  // pragma translate_on

endmodule
