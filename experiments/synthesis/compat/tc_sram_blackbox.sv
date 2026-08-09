// Synthesis-only blackbox replacement for tech_cells_generic `tc_sram`.
//
// This file is NOT part of the RTL.  It is a synthesis-only shim used by the
// cluster synthesis flow (see work-p6b/gen_cluster_bb_f.py).  The original
// `tc_sram` is a behavioral SRAM model (`data_t sram [NumWords-1:0]` +
// always_ff), which Yosys bit-blasts into ~1 M flip-flops during `proc`,
// exhausting memory.  Standard synthesis practice treats SRAM macros as leaf
// cells; this shim keeps the SRAM as an unelaborated blackbox cell so the
// TCDM/icache arrays are NOT bit-blasted.  No functional behavior is
// modified: the blackbox has no body, and its area/timing is not part of the
// mapped logic netlist (macro .lib would add it in a real flow).
//
// Parameters are declared so instance parameter lists bind; ports are
// fixed-width plain logic so RTLIL port widths are deterministic regardless
// of instance parameter order (Yosys resolves blackbox port widths from the
// first elaborated parameter set, which would otherwise truncate the widest
// icache line SRAMs).
//
// Widths chosen cover all cluster instantiations:
//   - TCDM banks:    DataWidth 64,  NumWords 1024, BeWidth 8,  AddrWidth 10
//   - icache tag:    DataWidth 23,  NumWords 64,   BeWidth 3,  AddrWidth 6
//   - icache data:   DataWidth 256, NumWords 64,   BeWidth 32, AddrWidth 6

(* blackbox *)
module tc_sram #(
  parameter int unsigned NumWords    = 32'd1024,
  parameter int unsigned DataWidth   = 32'd256,
  parameter int unsigned ByteWidth   = 32'd8,
  parameter int unsigned NumPorts    = 32'd1,
  parameter int unsigned Latency     = 32'd1,
  parameter              SimInit     = "none",
  parameter bit          PrintSimCfg = 1'b0,
  parameter              ImplKey     = "none",
  parameter int unsigned AddrWidth   = 32'd10,
  parameter int unsigned BeWidth     = 32'd32
) (
  input  logic         clk_i,
  input  logic         rst_ni,
  input  logic         req_i,
  input  logic         we_i,
  input  logic [9:0]   addr_i,
  input  logic [255:0] wdata_i,
  input  logic [31:0]  be_i,
  output logic [255:0] rdata_o
);
endmodule
