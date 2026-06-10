# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Avoid Reading These Files and Directories

The following files/directories contain large amounts of generated content or are unrelated to code logic. Claude Code should avoid reading them directly:

### Toolchains (Most Important - Very Large)
- `sw/toolchain/`
- `install/`

### Python Environment
- `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `*.pyo`

### Build Outputs
- `build/`, `dist/`, `out/`, `target/`, `generated/`, `gen/`, `obj/`, `obj_dir/`

### Hardware Simulation Waveforms (Can Be Very Large)
- `*.vcd`, `*.fst`, `*.wlf`, `*.fsdb`, `*.vpd`

### Compilation Artifacts
- `*.o`, `*.a`, `*.so`, `*.dylib`, `*.dll`, `*.elf`, `*.bin`, `*.hex`, `*.map`

### Temporary/Cache
- `.cache/`, `tmp/`, `*.tmp`, `*.log`

### Git Internals
- `.git/`

### IDE and Dependencies
- `.vscode/`, `.idea/`, `node_modules/`

### CMake
- `CMakeFiles/`, `CMakeCache.txt`

### Benchmark Outputs
- `benchmark_results/`, `perf_logs/`

### Large Datasets
- `datasets/`, `checkpoints/`

### RTL Generation Directories
- `hw/**/generated/`, `hw/**/build/`, `hw/**/sim/`

### Verilator
- `verilator/`

## Memory and Context Management

- Do not save the contents of the above directories to memory/
- When encountering large files, use limit/offset parameters for segmented reading
- Prefer using grep over directly reading large files
- Code structure and known directory layout information should not be repeatedly saved to memory

## Project Overview

Spatz is a compact RISC-V Vector (RVV) coprocessor designed to work with the Snitch scalar core. It implements a subset of RVV instructions optimized for embedded vector processing. The project follows a three-tier architecture: hardware RTL (`hw/`), software runtime and tests (`sw/`), and build utilities (`util/`).

## Build and Development Commands

### Initial Setup
```bash
# Download and build all dependencies (LLVM, GCC, Spike, Verilator)
make all

# For ETH Zurich users with pre-installed tools
source util/iis-env.sh
make init
```

### Cluster Simulation Workflow
All simulation commands run from `hw/system/spatz_cluster/`:

```bash
# Generate RTL from configuration
make generate

# Build Verilator simulation binary
make bin/spatz_cluster.vlt

# Compile software and run tests
make sw.vlt              # Build software for Verilator
make sw.test.vlt         # Build software with tests

# Run a specific binary
bin/spatz_cluster.vlt path/to/riscv/binary

# Post-processing: build annotated traces
make traces
make annotate
```

### Software Testing
Tests are organized through CMake/CTest:

```bash
cd hw/system/spatz_cluster/sw/build
ctest -R <test_name>          # Run specific test
ctest -R vadd                 # Example: run vadd test
```

### Configuration
Cluster behavior is controlled by HJSON configuration files in `cfg/`:

```bash
# Use a specific configuration
make bin/spatz_cluster.vlt CFG=cfg/spatz_cluster.doublebw.dram.hjson

# Or set environment variable
export CFG=cfg/spatz_cluster.doublebw.dram.hjson
make bin/spatz_cluster.vlt
```

Key configuration parameters include number of cores, FPU count, TCDM size, and memory maps.

## Architecture

### Hardware Hierarchy
- `hw/ip/spatz/`: Core vector processor with VRF, VLSU (load/store), VSLDU (slide), VAU (arithmetic), and IPU (integer)
- `hw/ip/spatz_cc/`: Core Complex combining Snitch scalar core + Spatz vector coprocessor + DMA
- `hw/system/spatz_cluster/`: Full system with multiple core complexes, shared TCDM (L1 scratchpad), and AXI external memory interface

### Software Stack
- `sw/snRuntime/`: Bare-metal runtime with multi-core primitives, DMA transfers, L1 allocation
- `sw/riscvTests/`: Functional verification tests for vector instructions
- `sw/spatzBenchmarks/`: Performance benchmarks

### Data Flow
Typical benchmark execution:
1. Input data resides in DRAM
2. DMA core transfers data to TCDM via `snrt_dma_start_1d()`
3. Compute cores execute scalar/vector operations on TCDM data
4. Results optionally DMA'd back to DRAM

### Memory Map (Default DRAM Config)
- Boot: `0x00001000`
- TCDM (L1): `0x00100000`, 128 KiB
- DRAM: `0x80000000`, 2 GiB

### Important Constraints
- Spatz VLSU can only access local TCDM, not external L2/DRAM directly
- Use `snrt_l1alloc()` and DMA functions for data movement
- Spatz does not support vector masking or fixed-point operations
- Data shuffling must be done via indexed memory operations (no `vrgather`)

## Simulator-Specific Notes

### Verilator
- Fastest for regression testing
- Generates `bin/spatz_cluster.vlt`
- Supports VCD waveform output

### QuestaSim/VCS
- Better for waveform debugging
- Use `.vsim.gui` target for interactive debugging
- Waveform TCL scripts in `script/vsim/wave.tcl`

## Code Generation

The cluster system uses template-based generation:
- `util/clustergen.py` generates RTL wrappers from HJSON configs
- `util/generate_bootrom.py` creates boot ROM initialization
- Generated files go to `hw/system/spatz_cluster/src/generated/`

## CI/CD

The project uses GitLab CI (mirrored from GitHub). Local linting:
- License headers: `make lint-license`
- SystemVerilog: Verible linter via GitHub Actions

Tests run on GitLab infrastructure with QuestaSim and VCS.

## Citation

This file's content is derived from `.codexignore`, converted to a format suitable for Claude Code.
