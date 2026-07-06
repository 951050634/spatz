// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Complex FMA Hardware Unit for Spatz VFU
// Implements: result = c + a * b (complex arithmetic)
//
//   real = c.real + a.real * b.real - a.imag * b.imag
//   imag = c.imag + a.imag * b.real + a.real * b.imag
//
// The block deliberately follows the v1 architectural accumulation order with
// two fpnew_fma instances and two arithmetic rounds.  This makes the dedicated
// block a standalone, handshaked unit while preserving the verified v1 phase
// order as the initial v2 correctness contract:
//   phase 1: real_acc = FMADD (a.real, b.real, c.real)
//            imag_acc = FMADD (a.imag, b.real, c.imag)
//   phase 2: real     = FNMSUB(a.imag, b.imag, real_acc)
//            imag     = FMADD (a.real, b.imag, imag_acc)

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

  typedef enum logic [2:0] {
    IDLE,
    PHASE1_ISSUE,
    PHASE1_WAIT,
    PHASE2_ISSUE,
    PHASE2_WAIT,
    RESULT
  } cfma_state_e;

  cfma_state_e state_q, state_d;

  logic accept_input;
  logic phase1_result_valid;
  logic phase2_result_valid;
  logic fma_pair_ready;

  logic [WIDTH-1:0] a_real_q, a_imag_q;
  logic [WIDTH-1:0] b_real_q, b_imag_q;
  logic [WIDTH-1:0] c_real_q, c_imag_q;
  logic [WIDTH-1:0] real_acc_q, real_acc_d;
  logic [WIDTH-1:0] imag_acc_q, imag_acc_d;
  logic [WIDTH-1:0] result_real_q, result_real_d;
  logic [WIDTH-1:0] result_imag_q, result_imag_d;
  fpnew_pkg::status_t status_q, status_d;
  TagType tag_q, tag_d;

  // FMA0 signals
  logic [2:0][WIDTH-1:0] fma0_operands;
  logic [2:0]            fma0_is_boxed;
  fpnew_pkg::operation_e fma0_op;
  logic                  fma0_op_mod;
  logic                  fma0_in_valid;
  logic                  fma0_in_ready;
  logic [WIDTH-1:0]      fma0_result;
  fpnew_pkg::status_t    fma0_status;
  logic                  fma0_out_valid;
  logic                  fma0_out_ready;
  logic                  fma0_busy;

  // FMA1 signals
  logic [2:0][WIDTH-1:0] fma1_operands;
  logic [2:0]            fma1_is_boxed;
  fpnew_pkg::operation_e fma1_op;
  logic                  fma1_op_mod;
  logic                  fma1_in_valid;
  logic                  fma1_in_ready;
  logic [WIDTH-1:0]      fma1_result;
  fpnew_pkg::status_t    fma1_status;
  logic                  fma1_out_valid;
  logic                  fma1_out_ready;
  logic                  fma1_busy;

  function automatic fpnew_pkg::status_t merge_status(
    input fpnew_pkg::status_t lhs,
    input fpnew_pkg::status_t rhs0,
    input fpnew_pkg::status_t rhs1
  );
    fpnew_pkg::status_t merged;
    begin
      merged.NV = lhs.NV | rhs0.NV | rhs1.NV;
      merged.DZ = lhs.DZ | rhs0.DZ | rhs1.DZ;
      merged.OF = lhs.OF | rhs0.OF | rhs1.OF;
      merged.UF = lhs.UF | rhs0.UF | rhs1.UF;
      merged.NX = lhs.NX | rhs0.NX | rhs1.NX;
      return merged;
    end
  endfunction

  assign accept_input        = op_valid_i && op_ready_o;
  assign phase1_result_valid = fma0_out_valid && fma1_out_valid &&
                               ((state_q == PHASE1_ISSUE) || (state_q == PHASE1_WAIT));
  assign phase2_result_valid = fma0_out_valid && fma1_out_valid &&
                               ((state_q == PHASE2_ISSUE) || (state_q == PHASE2_WAIT));
  assign fma_pair_ready      = fma0_in_ready && fma1_in_ready;

  always_comb begin
    state_d = state_q;

    unique case (state_q)
      IDLE: begin
        if (op_valid_i)
          state_d = PHASE1_ISSUE;
      end
      PHASE1_ISSUE: begin
        if (phase1_result_valid)
          state_d = PHASE2_ISSUE;
        else if (fma_pair_ready)
          state_d = PHASE1_WAIT;
      end
      PHASE1_WAIT: begin
        if (phase1_result_valid)
          state_d = PHASE2_ISSUE;
      end
      PHASE2_ISSUE: begin
        if (phase2_result_valid)
          state_d = RESULT;
        else if (fma_pair_ready)
          state_d = PHASE2_WAIT;
      end
      PHASE2_WAIT: begin
        if (phase2_result_valid)
          state_d = RESULT;
      end
      RESULT: begin
        if (result_ready_i)
          state_d = IDLE;
      end
      default: state_d = IDLE;
    endcase

    if (flush_i)
      state_d = IDLE;
  end

  always_comb begin
    real_acc_d    = real_acc_q;
    imag_acc_d    = imag_acc_q;
    result_real_d = result_real_q;
    result_imag_d = result_imag_q;
    status_d      = status_q;
    tag_d         = tag_q;

    if (accept_input) begin
      status_d = '0;
      tag_d    = tag_i;
    end

    if (phase1_result_valid) begin
      real_acc_d = fma0_result;
      imag_acc_d = fma1_result;
      status_d   = merge_status(status_d, fma0_status, fma1_status);
    end

    if (phase2_result_valid) begin
      result_real_d = fma0_result;
      result_imag_d = fma1_result;
      status_d      = merge_status(status_d, fma0_status, fma1_status);
    end

    if (flush_i) begin
      real_acc_d    = '0;
      imag_acc_d    = '0;
      result_real_d = '0;
      result_imag_d = '0;
      status_d      = '0;
      tag_d         = '0;
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q       <= IDLE;
      a_real_q      <= '0;
      a_imag_q      <= '0;
      b_real_q      <= '0;
      b_imag_q      <= '0;
      c_real_q      <= '0;
      c_imag_q      <= '0;
      real_acc_q    <= '0;
      imag_acc_q    <= '0;
      result_real_q <= '0;
      result_imag_q <= '0;
      status_q      <= '0;
      tag_q         <= '0;
    end else begin
      state_q       <= state_d;
      real_acc_q    <= real_acc_d;
      imag_acc_q    <= imag_acc_d;
      result_real_q <= result_real_d;
      result_imag_q <= result_imag_d;
      status_q      <= status_d;
      tag_q         <= tag_d;

      if (accept_input) begin
        a_real_q <= operand_a_real_i;
        a_imag_q <= operand_a_imag_i;
        b_real_q <= operand_b_real_i;
        b_imag_q <= operand_b_imag_i;
        c_real_q <= operand_c_real_i;
        c_imag_q <= operand_c_imag_i;
      end

      if (flush_i) begin
        a_real_q <= '0;
        a_imag_q <= '0;
        b_real_q <= '0;
        b_imag_q <= '0;
        c_real_q <= '0;
        c_imag_q <= '0;
      end
    end
  end

  fpnew_fma #(
    .FpFormat    ( FpFormat    ),
    .NumPipeRegs ( NumPipeRegs ),
    .PipeConfig  ( PipeConfig  ),
    .TagType     ( logic       ),
    .AuxType     ( logic       )
  ) i_fma0 (
    .clk_i           ( clk_i           ),
    .rst_ni          ( rst_ni          ),
    .operands_i      ( fma0_operands   ),
    .is_boxed_i      ( fma0_is_boxed   ),
    .rnd_mode_i      ( rnd_mode_i      ),
    .op_i            ( fma0_op         ),
    .op_mod_i        ( fma0_op_mod     ),
    .tag_i           ( 1'b0            ),
    .mask_i          ( 1'b0            ),
    .aux_i           ( 1'b0            ),
    .in_valid_i      ( fma0_in_valid   ),
    .in_ready_o      ( fma0_in_ready   ),
    .flush_i         ( flush_i         ),
    .result_o        ( fma0_result     ),
    .status_o        ( fma0_status     ),
    .extension_bit_o (                 ),
    .tag_o           (                 ),
    .mask_o          (                 ),
    .aux_o           (                 ),
    .out_valid_o     ( fma0_out_valid  ),
    .out_ready_i     ( fma0_out_ready  ),
    .busy_o          ( fma0_busy       )
  );

  fpnew_fma #(
    .FpFormat    ( FpFormat    ),
    .NumPipeRegs ( NumPipeRegs ),
    .PipeConfig  ( PipeConfig  ),
    .TagType     ( logic       ),
    .AuxType     ( logic       )
  ) i_fma1 (
    .clk_i           ( clk_i           ),
    .rst_ni          ( rst_ni          ),
    .operands_i      ( fma1_operands   ),
    .is_boxed_i      ( fma1_is_boxed   ),
    .rnd_mode_i      ( rnd_mode_i      ),
    .op_i            ( fma1_op         ),
    .op_mod_i        ( fma1_op_mod     ),
    .tag_i           ( 1'b0            ),
    .mask_i          ( 1'b0            ),
    .aux_i           ( 1'b0            ),
    .in_valid_i      ( fma1_in_valid   ),
    .in_ready_o      ( fma1_in_ready   ),
    .flush_i         ( flush_i         ),
    .result_o        ( fma1_result     ),
    .status_o        ( fma1_status     ),
    .extension_bit_o (                 ),
    .tag_o           (                 ),
    .mask_o          (                 ),
    .aux_o           (                 ),
    .out_valid_o     ( fma1_out_valid  ),
    .out_ready_i     ( fma1_out_ready  ),
    .busy_o          ( fma1_busy       )
  );

  always_comb begin
    fma0_operands  = '0;
    fma0_is_boxed  = '1;
    fma0_op        = fpnew_pkg::FMADD;
    fma0_op_mod    = 1'b0;
    fma0_in_valid  = 1'b0;
    fma0_out_ready = 1'b1;

    unique case (state_q)
      PHASE1_ISSUE: begin
        // real_acc = c.real + a.real * b.real
        fma0_operands[0] = a_real_q;
        fma0_operands[1] = b_real_q;
        fma0_operands[2] = c_real_q;
        fma0_op          = fpnew_pkg::FMADD;
        fma0_in_valid    = 1'b1;
      end
      PHASE2_ISSUE: begin
        // real = real_acc - a.imag * b.imag
        fma0_operands[0] = a_imag_q;
        fma0_operands[1] = b_imag_q;
        fma0_operands[2] = real_acc_q;
        fma0_op          = fpnew_pkg::FNMSUB;
        fma0_in_valid    = 1'b1;
      end
      default: ;
    endcase
  end

  always_comb begin
    fma1_operands  = '0;
    fma1_is_boxed  = '1;
    fma1_op        = fpnew_pkg::FMADD;
    fma1_op_mod    = 1'b0;
    fma1_in_valid  = 1'b0;
    fma1_out_ready = 1'b1;

    unique case (state_q)
      PHASE1_ISSUE: begin
        // imag_acc = c.imag + a.imag * b.real
        fma1_operands[0] = a_imag_q;
        fma1_operands[1] = b_real_q;
        fma1_operands[2] = c_imag_q;
        fma1_op          = fpnew_pkg::FMADD;
        fma1_in_valid    = 1'b1;
      end
      PHASE2_ISSUE: begin
        // imag = imag_acc + a.real * b.imag
        fma1_operands[0] = a_real_q;
        fma1_operands[1] = b_imag_q;
        fma1_operands[2] = imag_acc_q;
        fma1_op          = fpnew_pkg::FMADD;
        fma1_in_valid    = 1'b1;
      end
      default: ;
    endcase
  end

  assign op_ready_o     = (state_q == IDLE);
  assign result_valid_o = (state_q == RESULT);
  assign busy_o         = (state_q != IDLE) | fma0_busy | fma1_busy;

  assign result_real_o  = result_real_q;
  assign result_imag_o  = result_imag_q;
  assign status_o       = status_q;
  assign tag_o          = tag_q;

endmodule : fpnew_complex_fma
