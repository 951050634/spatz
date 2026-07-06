// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// CFMA v2 two-beat VRF read collector.
//
// This standalone helper freezes the stage-3 R0/R1 operand mapping for a
// future VFU integration.  It does not write architectural state and it has no
// dependency on the v1 four-phase fallback path.

module spatz_cfma_read_collector #(
  parameter int unsigned ELEN      = 64,
  parameter int unsigned AddrWidth = 10,
  parameter int unsigned ElemWidth = 16
) (
  input  logic                         clk_i,
  input  logic                         rst_ni,

  input  logic                         start_valid_i,
  output logic                         start_ready_o,

  input  logic [AddrWidth-1:0]         a_real_addr_i,
  input  logic [AddrWidth-1:0]         a_imag_addr_i,
  input  logic [AddrWidth-1:0]         b_real_addr_i,
  input  logic [AddrWidth-1:0]         b_imag_addr_i,
  input  logic [AddrWidth-1:0]         c_real_addr_i,
  input  logic [AddrWidth-1:0]         c_imag_addr_i,
  input  logic [ElemWidth-1:0]         elem_idx_i,
  input  logic                         last_i,

  output logic [2:0][AddrWidth-1:0]    vrf_raddr_o,
  output logic [2:0]                   vrf_re_o,
  input  logic [2:0]                   vrf_rvalid_i,
  input  logic [2:0][ELEN-1:0]         vrf_rdata_i,

  output logic                         bundle_valid_o,
  input  logic                         bundle_ready_i,

  output logic [ELEN-1:0]              a_real_o,
  output logic [ELEN-1:0]              a_imag_o,
  output logic [ELEN-1:0]              b_real_o,
  output logic [ELEN-1:0]              b_imag_o,
  output logic [ELEN-1:0]              c_real_o,
  output logic [ELEN-1:0]              c_imag_o,
  output logic [AddrWidth-1:0]         vd_real_addr_o,
  output logic [AddrWidth-1:0]         vd_imag_addr_o,
  output logic [ElemWidth-1:0]         elem_idx_o,
  output logic                         last_o,
  output logic                         busy_o
);

  typedef enum logic [1:0] {
    CfmaReadIdle,
    CfmaReadR0,
    CfmaReadR1,
    CfmaReadReady
  } cfma_read_state_e;

  cfma_read_state_e state_q, state_d;

  logic [AddrWidth-1:0] a_real_addr_q, a_real_addr_d;
  logic [AddrWidth-1:0] a_imag_addr_q, a_imag_addr_d;
  logic [AddrWidth-1:0] b_real_addr_q, b_real_addr_d;
  logic [AddrWidth-1:0] b_imag_addr_q, b_imag_addr_d;
  logic [AddrWidth-1:0] c_real_addr_q, c_real_addr_d;
  logic [AddrWidth-1:0] c_imag_addr_q, c_imag_addr_d;
  logic [ElemWidth-1:0] elem_idx_q, elem_idx_d;
  logic                 last_q, last_d;

  logic [ELEN-1:0] a_real_q, a_real_d;
  logic [ELEN-1:0] a_imag_q, a_imag_d;
  logic [ELEN-1:0] b_real_q, b_real_d;
  logic [ELEN-1:0] b_imag_q, b_imag_d;
  logic [ELEN-1:0] c_real_q, c_real_d;
  logic [ELEN-1:0] c_imag_q, c_imag_d;

  logic start_fire;
  logic r0_fire;
  logic r1_fire;
  logic bundle_fire;

  assign start_fire  = start_valid_i && start_ready_o;
  assign r0_fire     = (state_q == CfmaReadR0) && (&vrf_rvalid_i);
  assign r1_fire     = (state_q == CfmaReadR1) && (&vrf_rvalid_i);
  assign bundle_fire = bundle_valid_o && bundle_ready_i;

  always_comb begin
    state_d = state_q;
    unique case (state_q)
      CfmaReadIdle:  if (start_fire)  state_d = CfmaReadR0;
      CfmaReadR0:    if (r0_fire)     state_d = CfmaReadR1;
      CfmaReadR1:    if (r1_fire)     state_d = CfmaReadReady;
      CfmaReadReady: if (bundle_fire) state_d = CfmaReadIdle;
      default: state_d = CfmaReadIdle;
    endcase
  end

  always_comb begin
    a_real_addr_d = a_real_addr_q;
    a_imag_addr_d = a_imag_addr_q;
    b_real_addr_d = b_real_addr_q;
    b_imag_addr_d = b_imag_addr_q;
    c_real_addr_d = c_real_addr_q;
    c_imag_addr_d = c_imag_addr_q;
    elem_idx_d    = elem_idx_q;
    last_d        = last_q;

    a_real_d = a_real_q;
    a_imag_d = a_imag_q;
    b_real_d = b_real_q;
    b_imag_d = b_imag_q;
    c_real_d = c_real_q;
    c_imag_d = c_imag_q;

    if (start_fire) begin
      a_real_addr_d = a_real_addr_i;
      a_imag_addr_d = a_imag_addr_i;
      b_real_addr_d = b_real_addr_i;
      b_imag_addr_d = b_imag_addr_i;
      c_real_addr_d = c_real_addr_i;
      c_imag_addr_d = c_imag_addr_i;
      elem_idx_d    = elem_idx_i;
      last_d        = last_i;
    end

    if (r0_fire) begin
      a_real_d = vrf_rdata_i[0];
      a_imag_d = vrf_rdata_i[1];
      b_real_d = vrf_rdata_i[2];
    end

    if (r1_fire) begin
      b_imag_d = vrf_rdata_i[0];
      c_real_d = vrf_rdata_i[1];
      c_imag_d = vrf_rdata_i[2];
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q       <= CfmaReadIdle;
      a_real_addr_q <= '0;
      a_imag_addr_q <= '0;
      b_real_addr_q <= '0;
      b_imag_addr_q <= '0;
      c_real_addr_q <= '0;
      c_imag_addr_q <= '0;
      elem_idx_q    <= '0;
      last_q        <= 1'b0;
      a_real_q      <= '0;
      a_imag_q      <= '0;
      b_real_q      <= '0;
      b_imag_q      <= '0;
      c_real_q      <= '0;
      c_imag_q      <= '0;
    end else begin
      state_q       <= state_d;
      a_real_addr_q <= a_real_addr_d;
      a_imag_addr_q <= a_imag_addr_d;
      b_real_addr_q <= b_real_addr_d;
      b_imag_addr_q <= b_imag_addr_d;
      c_real_addr_q <= c_real_addr_d;
      c_imag_addr_q <= c_imag_addr_d;
      elem_idx_q    <= elem_idx_d;
      last_q        <= last_d;
      a_real_q      <= a_real_d;
      a_imag_q      <= a_imag_d;
      b_real_q      <= b_real_d;
      b_imag_q      <= b_imag_d;
      c_real_q      <= c_real_d;
      c_imag_q      <= c_imag_d;
    end
  end

  always_comb begin
    vrf_raddr_o = '0;
    vrf_re_o    = 3'b000;

    unique case (state_q)
      CfmaReadR0: begin
        vrf_re_o       = 3'b111;
        vrf_raddr_o[0] = a_real_addr_q;
        vrf_raddr_o[1] = a_imag_addr_q;
        vrf_raddr_o[2] = b_real_addr_q;
      end
      CfmaReadR1: begin
        vrf_re_o       = 3'b111;
        vrf_raddr_o[0] = b_imag_addr_q;
        vrf_raddr_o[1] = c_real_addr_q;
        vrf_raddr_o[2] = c_imag_addr_q;
      end
      default: ;
    endcase
  end

  assign start_ready_o  = state_q == CfmaReadIdle;
  assign bundle_valid_o = state_q == CfmaReadReady;
  assign busy_o         = state_q != CfmaReadIdle;

  assign a_real_o       = a_real_q;
  assign a_imag_o       = a_imag_q;
  assign b_real_o       = b_real_q;
  assign b_imag_o       = b_imag_q;
  assign c_real_o       = c_real_q;
  assign c_imag_o       = c_imag_q;
  assign vd_real_addr_o = c_real_addr_q;
  assign vd_imag_addr_o = c_imag_addr_q;
  assign elem_idx_o     = elem_idx_q;
  assign last_o         = last_q;

endmodule : spatz_cfma_read_collector
