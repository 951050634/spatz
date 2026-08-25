// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

// Fixed-configuration, synthesis-only tops for the C0/C1/C2 SMU area
// comparison.  All configurations expose the same packed interface.  C0
// contains no update engine, C1 fixes the production engine to scalar-only
// mode, and C2 fixes it to full-update mode.  This is an SMU contribution
// scope, not a complete Spatz cluster synthesis top.
package online_merge_mapped_types_pkg;
  typedef struct packed {
    logic [16:0] src_m_old;
    logic [16:0] src_l_old;
    logic [16:0] src_o_old;
    logic [16:0] src_m_tile;
    logic [16:0] src_l_tile;
    logic [16:0] src_o_tile;
    logic [16:0] dst_m;
    logic [16:0] dst_l;
    logic [16:0] dst_o;
    logic [16:0] dst_weight_old;
    logic [16:0] dst_weight_tile;
    logic [31:0] n;
    logic [31:0] d;
    logic [31:0] stride;
    logic [31:0] mode;
    logic        start;
    logic        clear_done;
  } engine_cfg_t;

  typedef struct packed {
    logic        ready;
    logic        valid;
    logic [63:0] data;
  } tcdm_rsp_flat_t;

  typedef struct packed {
    logic        valid;
    logic [16:0] addr;
    logic        write;
    logic [3:0]  amo;
    logic [63:0] data;
    logic [7:0]  strb;
    logic [3:0]  user;
  } tcdm_req_flat_t;

  typedef struct packed {
    logic busy;
    logic done;
    logic error;
  } engine_status_t;
endpackage

module online_merge_mapped_variant #(
  parameter bit          EnginePresent = 1'b1,
  parameter logic [31:0] FixedMode = 32'd0,
  parameter bit          RuntimeScalarPrecision = 1'b0,
  parameter int unsigned PrecisionSupport = 2,
  parameter bit          ScalarOnly = 1'b0,
  parameter bit          MixedNormalizationReciprocal = 1'b0
) (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  import online_merge_resource_types_pkg::*;

  if (EnginePresent) begin : gen_engine
    tcdm_req_t tcdm_req;
    tcdm_rsp_t tcdm_rsp;

    always_comb begin
      tcdm_rsp = '0;
      tcdm_rsp.q_ready = rsp_i.ready;
      tcdm_rsp.p_valid = rsp_i.valid;
      tcdm_rsp.p.data = rsp_i.data;

      req_o = '0;
      req_o.valid = tcdm_req.q_valid;
      req_o.addr = tcdm_req.q.addr;
      req_o.write = tcdm_req.q.write;
      req_o.amo = tcdm_req.q.amo;
      req_o.data = tcdm_req.q.data;
      req_o.strb = tcdm_req.q.strb;
      req_o.user = tcdm_req.q.user;
    end

    online_merge_update_engine #(
      .AddrWidth  (AddrWidth),
      .DataWidth  (DataWidth),
      .PrecisionSupport (PrecisionSupport),
      .ScalarOnly (ScalarOnly),
      .MixedNormalizationReciprocal (MixedNormalizationReciprocal),
      .tcdm_req_t (tcdm_req_t),
      .tcdm_rsp_t (tcdm_rsp_t)
    ) i_engine (
      .clk_i,
      .rst_ni,
      .src_m_old_i         (cfg_i.src_m_old),
      .src_l_old_i         (cfg_i.src_l_old),
      .src_o_old_i         (cfg_i.src_o_old),
      .src_m_tile_i        (cfg_i.src_m_tile),
      .src_l_tile_i        (cfg_i.src_l_tile),
      .src_o_tile_i        (cfg_i.src_o_tile),
      .dst_m_i             (cfg_i.dst_m),
      .dst_l_i             (cfg_i.dst_l),
      .dst_o_i             (cfg_i.dst_o),
      .dst_weight_old_i    (cfg_i.dst_weight_old),
      .dst_weight_tile_i   (cfg_i.dst_weight_tile),
      .n_i                 (cfg_i.n),
      .d_i                 (cfg_i.d),
      .stride_i            (cfg_i.stride),
      // Dual runtime mode is scalar-only: bit 0 is forced and cfg_i.mode[1]
      // selects legacy (0) versus mixed (1) precision.
      .mode_i              (RuntimeScalarPrecision ?
                            {30'd0, cfg_i.mode[1], 1'b1} : FixedMode),
      .start_i             (cfg_i.start),
      .clear_done_i        (cfg_i.clear_done),
      .busy_o              (status_o.busy),
      .done_o              (status_o.done),
      .error_o             (status_o.error),
      .tcdm_req_o          (tcdm_req),
      .tcdm_rsp_i          (tcdm_rsp)
    );
  end else begin : gen_no_engine
    always_comb begin
      status_o = '0;
      req_o = '0;
    end
  end
endmodule

module online_merge_c0_none_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent (1'b0),
    .FixedMode     (32'd0)
  ) i_variant (.*);
endmodule

module online_merge_c1_scalar_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent    (1'b1),
    .FixedMode        (32'd1),
    .PrecisionSupport (0),
    .ScalarOnly       (1'b1)
  ) i_variant (.*);
endmodule

module online_merge_c2_full_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent    (1'b1),
    .FixedMode        (32'd0),
    .PrecisionSupport (0)
  ) i_variant (.*);
endmodule

// Phase-2 synthesis points.  They share the packed interface above and are
// intentionally outside the existing P0-6 C0/C1/C2 runner.
module online_merge_legacy_scalar_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent    (1'b1),
    .FixedMode        (32'd1),
    .PrecisionSupport (0),
    .ScalarOnly       (1'b1)
  ) i_variant (.*);
endmodule

module online_merge_mixed_scalar_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent    (1'b1),
    .FixedMode        (32'd3),
    .PrecisionSupport (1),
    .ScalarOnly       (1'b1)
  ) i_variant (.*);
endmodule

// Constantized mixed normalization comparison points.  Both are scalar-only
// and keep the Dual runtime deployment top above unchanged.
module online_merge_mixed_division_scalar_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent                 (1'b1),
    .FixedMode                     (32'd3),
    .PrecisionSupport              (1),
    .ScalarOnly                    (1'b1),
    .MixedNormalizationReciprocal (1'b0)
  ) i_variant (.*);
endmodule

module online_merge_mixed_reciprocal_scalar_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent                 (1'b1),
    .FixedMode                     (32'd3),
    .PrecisionSupport              (1),
    .ScalarOnly                    (1'b1),
    .MixedNormalizationReciprocal (1'b1)
  ) i_variant (.*);
endmodule

module online_merge_dual_scalar_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent          (1'b1),
    .FixedMode              (32'd1),
    .RuntimeScalarPrecision (1'b1),
    .PrecisionSupport       (2),
    .ScalarOnly             (1'b1)
  ) i_variant (.*);
endmodule

module online_merge_legacy_full_mapped_top (
  input  logic                                                 clk_i,
  input  logic                                                 rst_ni,
  input  online_merge_mapped_types_pkg::engine_cfg_t           cfg_i,
  input  online_merge_mapped_types_pkg::tcdm_rsp_flat_t        rsp_i,
  output online_merge_mapped_types_pkg::engine_status_t        status_o,
  output online_merge_mapped_types_pkg::tcdm_req_flat_t        req_o
);
  online_merge_mapped_variant #(
    .EnginePresent    (1'b1),
    .FixedMode        (32'd0),
    .PrecisionSupport (0)
  ) i_variant (.*);
endmodule
