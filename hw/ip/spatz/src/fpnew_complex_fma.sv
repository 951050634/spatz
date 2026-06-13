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

  // -----------------------
  // FMA Unit Instantiation
  // -----------------------
  // Two FMA units for time-multiplexed complex arithmetic

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

  // FMA Unit 0
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
    .extension_bit_o (                 ), // unused
    .tag_o           (                 ), // unused
    .mask_o          (                 ), // unused
    .aux_o           (                 ), // unused
    .out_valid_o     ( fma0_out_valid  ),
    .out_ready_i     ( fma0_out_ready  ),
    .busy_o          ( fma0_busy       )
  );

  // FMA Unit 1
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
    .extension_bit_o (                 ), // unused
    .tag_o           (                 ), // unused
    .mask_o          (                 ), // unused
    .aux_o           (                 ), // unused
    .out_valid_o     ( fma1_out_valid  ),
    .out_ready_i     ( fma1_out_ready  ),
    .busy_o          ( fma1_busy       )
  );

  // --------------------------
  // Operand Multiplexer (FMA0)
  // --------------------------
  // Select operands for FMA0 based on current state
  always_comb begin
    // Default assignments
    fma0_operands  = '0;
    fma0_is_boxed  = '1;
    fma0_op        = fpnew_pkg::FMADD;
    fma0_op_mod    = 1'b0;
    fma0_in_valid  = 1'b0;
    fma0_out_ready = 1'b1;

    unique case (state_q)
      IDLE, MULTIPLY_PH1: begin
        // Compute prod_rr = a.real * b.real
        fma0_operands[0] = operand_a_real_i;
        fma0_operands[1] = operand_b_real_i;
        fma0_operands[2] = '0;
        fma0_in_valid    = (state_q == MULTIPLY_PH1);
      end

      MULTIPLY_PH2: begin
        // Compute prod_ri = a.real * b.imag
        fma0_operands[0] = operand_a_real_i;
        fma0_operands[1] = operand_b_imag_i;
        fma0_operands[2] = '0;
        fma0_in_valid    = 1'b1;
      end

      ADD_PHASE: begin
        // Compute result.real = c.real + prod_rr - prod_ii
        fma0_operands[0] = prod_rr_q;
        fma0_operands[1] = prod_ii_q;
        fma0_operands[2] = operand_c_real_i;
        fma0_op          = fpnew_pkg::FNMSUB;
        fma0_in_valid    = 1'b1;
      end

      default: ;
    endcase
  end

  // --------------------------
  // Operand Multiplexer (FMA1)
  // --------------------------
  always_comb begin
    fma1_operands  = '0;
    fma1_is_boxed  = '1;
    fma1_op        = fpnew_pkg::FMADD;
    fma1_op_mod    = 1'b0;
    fma1_in_valid  = 1'b0;
    fma1_out_ready = 1'b1;

    unique case (state_q)
      IDLE, MULTIPLY_PH1: begin
        // Compute prod_ii = a.imag * b.imag
        fma1_operands[0] = operand_a_imag_i;
        fma1_operands[1] = operand_b_imag_i;
        fma1_operands[2] = '0;
        fma1_in_valid    = (state_q == MULTIPLY_PH1);
      end

      MULTIPLY_PH2: begin
        // Compute prod_ir = a.imag * b.real
        fma1_operands[0] = operand_a_imag_i;
        fma1_operands[1] = operand_b_real_i;
        fma1_operands[2] = '0;
        fma1_in_valid    = 1'b1;
      end

      ADD_PHASE: begin
        // Compute result.imag = c.imag + prod_ri + prod_ir
        // Note: FMA can only do a*b+c, not a+b+c
        // Use: prod_ri + (prod_ir * 1.0 + c.imag)
        // Workaround: Set operand[1] to 1.0, but this is tricky
        // Better: use ADD operation separately or multi-cycle
        // For now: simplified as prod_ri*1 + prod_ir (missing c.imag)
        fma1_operands[0] = prod_ri_q;
        fma1_operands[1] = prod_ir_q;
        fma1_operands[2] = operand_c_imag_i;
        fma1_op          = fpnew_pkg::FMADD;
        fma1_in_valid    = 1'b1;
      end

      default: ;
    endcase
  end

  // TODO: Result routing

  // Temporary assignments to prevent compilation errors
  assign result_real_o  = '0;
  assign result_imag_o  = '0;
  assign status_o       = '0;
  assign tag_o          = tag_i;

endmodule : fpnew_complex_fma
