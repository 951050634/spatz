// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

// Synthesis-only fixed-type tops for generic-resource proxy experiments.
// These ports and types match the default 128 KiB, 64-bit Spatz TCDM
// integration.  They are not functional cluster wrappers and must not be used
// to infer physical area, frequency, timing, power, or energy.
package reqrsp_pkg;
  typedef enum logic [3:0] {
    AMONone = 4'h0,
    AMOSwap = 4'h1,
    AMOAdd  = 4'h2,
    AMOAnd  = 4'h3,
    AMOOr   = 4'h4,
    AMOXor  = 4'h5,
    AMOMax  = 4'h6,
    AMOMaxu = 4'h7,
    AMOMin  = 4'h8,
    AMOMinu = 4'h9,
    AMOLR   = 4'ha,
    AMOSC   = 4'hb
  } amo_op_e;
endpackage

package online_merge_resource_types_pkg;
  localparam int unsigned AddrWidth = 17;
  localparam int unsigned DataWidth = 64;
  localparam int unsigned StrbWidth = DataWidth / 8;

  typedef logic [AddrWidth-1:0] addr_t;
  typedef logic [DataWidth-1:0] data_t;
  typedef logic [StrbWidth-1:0] strb_t;

  // Default cluster: two cores, one is_core bit, and four outstanding Spatz
  // loads.  This is the exact four-bit packed TCDM user payload shape.
  typedef struct packed {
    logic       core_id;
    logic       is_core;
    logic [1:0] req_id;
  } user_t;

  typedef struct packed {
    addr_t               addr;
    logic                write;
    reqrsp_pkg::amo_op_e amo;
    data_t               data;
    strb_t               strb;
    user_t               user;
  } tcdm_req_chan_t;

  typedef struct packed {
    data_t data;
  } tcdm_rsp_chan_t;

  typedef struct packed {
    tcdm_req_chan_t q;
    logic           q_valid;
  } tcdm_req_t;

  typedef struct packed {
    tcdm_rsp_chan_t p;
    logic           p_valid;
    logic           q_ready;
  } tcdm_rsp_t;
endpackage

module online_merge_exp_resource_top (
  input  logic [31:0] x_i,
  output logic [23:0] exp_q1_23_o,
  output logic        valid_o,
  output logic        saturated_o,
  output logic        unsupported_o
);
  online_merge_exp_approx i_exp_approx (.*);
endmodule

module online_merge_reciprocal_resource_top (
  input  logic [31:0]     x_i,
  output logic [23:0]     recip_q1_23_o,
  output logic signed [9:0] scale_exp_o,
  output logic            valid_o,
  output logic            unsupported_o
);
  online_merge_recip_approx i_reciprocal_approx (.*);
endmodule

// Standalone copy of the exact vector expression in compute_vector_merge().
// Independent synthesis can optimize this scope differently from the full SMU,
// so its total is a non-additive structural decomposition aid only.
module online_merge_vector_resource_top (
  input  logic [31:0] o_old_i,
  input  logic [31:0] o_tile_i,
  input  logic [47:0] old_weight_i,
  input  logic [47:0] tile_weight_i,
  output logic [31:0] o_new_o
);
  import online_merge_fp32_helpers::*;

  sq16_16_t old_term;
  sq16_16_t tile_term;
  sq16_16_t sum;

  always_comb begin
    old_term = sq16_16_mul_weight(fp32_to_sq16_16(o_old_i), old_weight_i);
    tile_term = sq16_16_mul_weight(fp32_to_sq16_16(o_tile_i), tile_weight_i);
    sum = old_term + tile_term;
    o_new_o = sq16_16_to_fp32(sum);
  end
endmodule

module online_merge_full_resource_top (
  input  logic        clk_i,
  input  logic        rst_ni,
  input  logic [16:0] src_m_old_i,
  input  logic [16:0] src_l_old_i,
  input  logic [16:0] src_o_old_i,
  input  logic [16:0] src_m_tile_i,
  input  logic [16:0] src_l_tile_i,
  input  logic [16:0] src_o_tile_i,
  input  logic [16:0] dst_m_i,
  input  logic [16:0] dst_l_i,
  input  logic [16:0] dst_o_i,
  input  logic [31:0] n_i,
  input  logic [31:0] d_i,
  input  logic [31:0] stride_i,
  input  logic        start_i,
  input  logic        clear_done_i,
  output logic        busy_o,
  output logic        done_o,
  output logic        error_o,
  output logic        req_valid_o,
  output logic [16:0] req_addr_o,
  output logic        req_write_o,
  output logic [3:0]  req_amo_o,
  output logic [63:0] req_data_o,
  output logic [7:0]  req_strb_o,
  output logic [3:0]  req_user_o,
  input  logic        rsp_ready_i,
  input  logic        rsp_valid_i,
  input  logic [63:0] rsp_data_i
);
  import online_merge_resource_types_pkg::*;

  tcdm_req_t tcdm_req;
  tcdm_rsp_t tcdm_rsp;

  always_comb begin
    tcdm_rsp = '0;
    tcdm_rsp.q_ready = rsp_ready_i;
    tcdm_rsp.p_valid = rsp_valid_i;
    tcdm_rsp.p.data = rsp_data_i;

    req_valid_o = tcdm_req.q_valid;
    req_addr_o = tcdm_req.q.addr;
    req_write_o = tcdm_req.q.write;
    req_amo_o = tcdm_req.q.amo;
    req_data_o = tcdm_req.q.data;
    req_strb_o = tcdm_req.q.strb;
    req_user_o = tcdm_req.q.user;
  end

  online_merge_update_engine #(
    .AddrWidth  (AddrWidth),
    .DataWidth  (DataWidth),
    .tcdm_req_t (tcdm_req_t),
    .tcdm_rsp_t (tcdm_rsp_t)
  ) i_engine (
    .clk_i,
    .rst_ni,
    .src_m_old_i,
    .src_l_old_i,
    .src_o_old_i,
    .src_m_tile_i,
    .src_l_tile_i,
    .src_o_tile_i,
    .dst_m_i,
    .dst_l_i,
    .dst_o_i,
    .n_i,
    .d_i,
    .stride_i,
    .start_i,
    .clear_done_i,
    .busy_o,
    .done_o,
    .error_o,
    .tcdm_req_o (tcdm_req),
    .tcdm_rsp_i (tcdm_rsp)
  );
endmodule
