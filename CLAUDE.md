# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spatz is a compact RISC-V vector processor based on RVV v1.0, designed as a coprocessor to Snitch (a 64-bit scalar core). This is a hardware design and simulation project developed as part of the PULP platform at ETH Zurich and University of Bologna.

**Important**: Spatz is NOT fully RVV-compliant. It implements a subset of vector instructions optimized for embedded vector processing. For full RVV compliance, see the Ara processor.

## Initial Setup

First-time setup (downloads and compiles LLVM, GCC, Spike, Verilator):
```bash
make all
```

ETH users with existing toolchains:
```bash
source util/iis-env.sh
make init
```

## Primary Work Directory

Most development happens in `hw/system/spatz_cluster/`. Change to this directory for simulation work:
```bash
cd hw/system/spatz_cluster
```

## Building and Running Simulations

### Build Software and Simulator

Verilator (fastest):
```bash
make sw.vlt
```

QuestaSim:
```bash
make sw.vsim
```

VCS:
```bash
make sw.vcs
```

### Run a Binary

```bash
# Verilator
bin/spatz_cluster.vlt path/to/riscv/binary

# QuestaSim (headless)
bin/spatz_cluster.vsim path/to/riscv/binary

# QuestaSim (GUI)
bin/spatz_cluster.vsim.gui path/to/riscv/binary

# VCS
bin/spatz_cluster.vcs path/to/riscv/binary
```

### Trace Analysis

Build disassembled traces:
```bash
make traces
```

Annotate traces with source code:
```bash
make annotate
```

Traces are written to `.logs/trace_hart_X.txt` and `.logs/trace_hart_X.s`.

## Configuration System

Cluster configuration uses HJSON files in `hw/system/spatz_cluster/cfg/`:
- `spatz_cluster.default.dram.hjson` - Default configuration
- `spatz_cluster.doublebw.dram.hjson` - Double memory bandwidth
- `spatz_cluster.smallvrf.dram.hjson` - Smaller vector register file
- Others for specific use cases (32-bit, Carfield, MemPool)

Override configuration:
```bash
make bin/spatz_cluster.vlt CFG=cfg/spatz_cluster.default.hjson
```

Or set the `CFG` environment variable for persistent override.

## Architecture

### Spatz Cluster

The default cluster has:
- 2 Snitch-Spatz core complexes (CCs)
- Each CC: 2 KiB latch-based Vector Register File (VRF)
- Each CC: 4 trans-precision FPUs with SDOTP extensions
- Shared 128 KiB L1 scratchpad (16 SRAM banks)

### Spatz Core Functional Units

1. **Vector Arithmetic Unit (VAU)**: `F` trans-precision FPUs + integer unit
   - Supports fp8, fp16, fp32, fp64
   - Supports 8/16/32/64-bit integer computation
   - 64 bit/cycle throughput regardless of element width
   - Integer and floating-point reductions

2. **Vector Load/Store Unit (VLSU)**: Memory operations
   - Unit-strided, constant-strided, and indexed accesses
   - Multiple 64-bit memory interfaces (default: matches FPU count)
   - **CRITICAL**: VLSU cannot access cluster L2 memory, only L1
   - Use `snrt_l1alloc` and `snrt_dma_start_1d` for L1 initialization

3. **Vector Slide Unit (VSLDU)**: Permutations
   - Vector slide up/down
   - Vector moves
   - Does NOT support `vrgather` (use indexed memory operations instead)

### Software Structure

- `sw/snRuntime/` - Snitch runtime library
- `sw/spatzBenchmarks/` - Vector benchmarks (matmul, dotp, fft, etc.)
  - Complex number benchmarks: `dp-caxpy`, `dp-cdotp`, `sp-cmatmul`, etc.
  - Real number benchmarks: `dp-faxpy`, `dp-fdotp`, `dp-fmatmul`, etc.
- `sw/riscvTests/` - RISC-V test suite
  - `CMakeLists.txt` contains most up-to-date list of supported instructions

## Unsupported Features

Spatz does NOT support:
- Vector masking (work in progress)
- Fixed-point computation
- Most shuffling/permutation instructions (`vrgather`, etc.)
- Full RVV compliance

## Opcode Updates

When modifying custom opcodes in `sw/toolchain-patches/riscv-opcodes/*.patch`:
```bash
make update_opcodes
```

This regenerates `hw/ip/snitch/src/riscv_instr.sv`.

## Branch Information

Current branch: `feature/cfma-instruction-extension`
Main branch: `main`

Recent work focuses on complex FMA (CFMA) instruction extensions with diagnostics for `dp-cdotp` benchmark testing.

## File Access Restrictions

Do NOT read or index these paths (see `.codexignore`):
- `sw/toolchain/`, `install/` - Toolchain binaries
- Build outputs: `build/`, `obj/`, `obj_dir/`, `hw/**/generated/`, `hw/**/build/`, `hw/**/sim/`
- Simulation artifacts: `*.vcd`, `*.fst`, `*.wlf`, `*.fsdb`, `*.vpd`
- Binaries: `*.elf`, `*.bin`, `*.hex`, `*.o`, `*.a`, `*.so`
- Benchmark results: `benchmark_results/`, `perf_logs/`
- Large data: `datasets/`, `checkpoints/`

**Temporarily allowed for Node 6 benchmark debugging**:
- `*.log` - Log files including CTest output and trace logs
- `hw/system/spatz_cluster/work-vlt/` - Verilator work directory with trace files

When debugging `dp-cdotp` benchmark timeout issues, check:
- `logs/` or `spatzBenchmarks/logs/` for trace files
- `hw/system/spatz_cluster/sw/build/Testing/Temporary/` for CTest logs
