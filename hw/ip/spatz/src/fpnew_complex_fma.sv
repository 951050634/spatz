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

  // TODO: State machine (4 states)
  // TODO: Intermediate registers (4x 64-bit)
  // TODO: FMA unit instantiation (2x)
  // TODO: Control logic

  // Temporary implementation to prevent compilation errors
  assign op_ready_o     = 1'b0;
  assign result_real_o  = '0;
  assign result_imag_o  = '0;
  assign status_o       = '0;
  assign result_valid_o = 1'b0;
  assign tag_o          = tag_i;
  assign busy_o         = 1'b0;

endmodule : fpnew_complex_fma
