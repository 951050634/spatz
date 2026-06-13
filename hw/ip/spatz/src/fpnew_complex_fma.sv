// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Complex FMA Hardware Unit for Spatz VFU
// Implements: result = c + a * b (complex arithmetic)
//
// Author: Complex FMA Implementation Team

`include "common_cells/registers.svh"

module fpnew_complex_fma
  import fpnew_pkg::*;
#(
  parameter fpnew_pkg::fp_format_e   FpFormat    = fpnew_pkg::FP64,
  parameter int unsigned             NumPipeRegs = 0,
  parameter fpnew_pkg::pipe_config_t PipeConfig  = fpnew_pkg::BEFORE,
  parameter type                     TagType     = logic,

  localparam int unsigned WIDTH = fpnew_pkg::fp_width(FpFormat) // do not change
) (
  input logic                      clk_i,
  input logic                      rst_ni,

  // Complex operands (6 inputs: a, b, c with real/imag parts)
  input logic [WIDTH-1:0]          operand_a_real_i,
  input logic [WIDTH-1:0]          operand_a_imag_i,
  input logic [WIDTH-1:0]          operand_b_real_i,
  input logic [WIDTH-1:0]          operand_b_imag_i,
  input logic [WIDTH-1:0]          operand_c_real_i,
  input logic [WIDTH-1:0]          operand_c_imag_i,

  // Control signals
  input fpnew_pkg::roundmode_e     rnd_mode_i,
  input logic                      op_valid_i,
  output logic                     op_ready_o,
  input logic                      flush_i,

  // Complex results (2 outputs: real/imag)
  output logic [WIDTH-1:0]         result_real_o,
  output logic [WIDTH-1:0]         result_imag_o,
  output fpnew_pkg::status_t       status_o,
  output logic                     result_valid_o,
  input logic                      result_ready_i,

  // Side channels
  input TagType                    tag_i,
  output TagType                   tag_o,

  // Status
  output logic                     busy_o
);

  // ----------------
  // State Machine
  // ----------------
  typedef enum logic [1:0] {
    IDLE         = 2'b00,  // Waiting for new operation
    MULTIPLY_PH1 = 2'b01,  // Compute prod_rr = a.real * b.real, prod_ii = a.imag * b.imag
    MULTIPLY_PH2 = 2'b10,  // Compute prod_ri = a.real * b.imag, prod_ir = a.imag * b.real
    ADD_PHASE    = 2'b11   // Compute final results: result.real and result.imag
  } cfma_state_e;

  cfma_state_e state_q, state_d;

  // ----------------
  // State Register
  // ----------------
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q <= IDLE;
    end else begin
      state_q <= state_d;
    end
  end

  // ----------------------
  // State Transition Logic
  // ----------------------
  always_comb begin
    // Default: stay in current state
    state_d = state_q;

    unique case (state_q)
      IDLE: begin
        // Start operation when valid input arrives
        if (op_valid_i) begin
          state_d = MULTIPLY_PH1;
        end
      end

      MULTIPLY_PH1: begin
        // Automatically transition to next phase
        state_d = MULTIPLY_PH2;
      end

      MULTIPLY_PH2: begin
        // Automatically transition to add phase
        state_d = ADD_PHASE;
      end

      ADD_PHASE: begin
        // Return to IDLE when result is consumed
        if (result_ready_i) begin
          state_d = IDLE;
        end
      end

      default: begin
        state_d = IDLE;
      end
    endcase
  end

  // ----------------------
  // Control Signal Outputs
  // ----------------------

  // op_ready_o: Ready to accept new operation only in IDLE state
  assign op_ready_o = (state_q == IDLE);

  // result_valid_o: Result is valid only in ADD_PHASE state
  assign result_valid_o = (state_q == ADD_PHASE);

  // busy_o: Module is busy when not in IDLE state
  assign busy_o = (state_q != IDLE);

  // -----------------------------
  // Intermediate Result Registers
  // -----------------------------
  // Store intermediate products from multiply phases

  // prod_rr = a.real * b.real (computed in MULTIPLY_PH1)
  logic [WIDTH-1:0] prod_rr_q, prod_rr_d;

  // prod_ii = a.imag * b.imag (computed in MULTIPLY_PH1)
  logic [WIDTH-1:0] prod_ii_q, prod_ii_d;

  // prod_ri = a.real * b.imag (computed in MULTIPLY_PH2)
  logic [WIDTH-1:0] prod_ri_q, prod_ri_d;

  // prod_ir = a.imag * b.real (computed in MULTIPLY_PH2)
  logic [WIDTH-1:0] prod_ir_q, prod_ir_d;

  // Register update logic
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      prod_rr_q <= '0;
      prod_ii_q <= '0;
      prod_ri_q <= '0;
      prod_ir_q <= '0;
    end else begin
      prod_rr_q <= prod_rr_d;
      prod_ii_q <= prod_ii_d;
      prod_ri_q <= prod_ri_d;
      prod_ir_q <= prod_ir_d;
    end
  end

  // Default: hold current values
  always_comb begin
    prod_rr_d = prod_rr_q;
    prod_ii_d = prod_ii_q;
    prod_ri_d = prod_ri_q;
    prod_ir_d = prod_ir_q;

    // Update intermediate results based on state
    // (Will be connected to FMA outputs in next steps)
  end

  // TODO: FMA unit instantiation (2x)
  // TODO: Operand multiplexer
  // TODO: Result routing

  // Temporary assignments to prevent compilation errors
  assign result_real_o  = '0;
  assign result_imag_o  = '0;
  assign status_o       = '0;
  assign tag_o          = tag_i;

endmodule : fpnew_complex_fma
