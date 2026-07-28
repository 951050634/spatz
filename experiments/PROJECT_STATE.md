# Project State

Recorded before implementation of the P0 paper-experiment facade on
2026-07-28.  Every run manifest records its own state again; this file is not a
substitute for per-run provenance.

| Item | Observed value |
| --- | --- |
| Repository HEAD | `9c74078cc8d67ecf709fffddf31a03de2ec6d2f2` |
| Branch | `exp/online-softmax-supplement` |
| Worktree at inspection | clean |
| Local Spatz base commit | `948985eaa4c88132f7786bbd9ce019a800e744d8` |
| First SMU commit | `957667edb213cc748252d486554ff54b3b41fefe` |
| Latest functional SMU commit at inspection | `dc6a6a963dfb2a27b9d3b54b4d24a87512724741` |
| Config | `hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson` |
| Config SHA256 | `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775` |
| Cluster top | `spatz_cluster` |
| SMU top | `online_merge_update_engine` |
| Benchmark sources | `sw/spatzBenchmarks/online-softmax-merge/` |
| Legacy benchmark target | `test-spatzBenchmarks-online-softmax-merge` |
| Legacy binary | `hw/system/spatz_cluster/sw/build/spatzBenchmarks/test-spatzBenchmarks-online-softmax-merge` |
| LLVM compiler | Clang 14.0.6, PULP LLVM commit `b494f2d8` |
| RISC-V GCC support toolchain | GCC 7.1.1 20170509 |
| Verilator | 5.034, 2025-02-24 |
| Yosys | 0.66+4, git `8125af88d` |
| OpenROAD / ORFS | not found in the current environment |

## Provenance qualification

The configured Git remote is a project fork and no official PULP upstream
remote is configured.  Consequently, `948985e` is recorded as the local base
commit preceding the first SMU change; it is not asserted to be a verified
official Spatz release commit.

No toolchain, submodule, PDK, or standard-cell library was updated during this
inspection.  Formal runs must keep tool identities fixed and record executable
hashes in their manifests.

At the P0-1--P0-3 implementation handoff the worktree is intentionally dirty
with the experiment-framework changes described in this directory; no commit
was created on the user's behalf.  All smoke results from this state are
therefore diagnostic and carry `paper_eligible=NO`.  The runner additionally
hashes every modified and untracked source file so distinct dirty snapshots
cannot be confused merely because they share the same HEAD commit.

## Hardware granularity

| Symbol | Current value | Source and interpretation |
| --- | --- | --- |
| `T` | `NA` | The merge benchmark exposes no tile-size parameter |
| `V` | 8 FP32 elements | `ONLINE_MERGE_RVV_AVL_CAP` in `rvv_update.c` |
| `A_interface` | 4 bytes | SMU validates FP32 address alignment |
| `A_allocation` | 256 bytes | Benchmark TCDM allocation rounding |
| `M` | 131072 bytes | Default CFG TCDM size |
| Runtime TCDM reservation | 16512 bytes | 2 × (8 KiB stack + 8 B bank skew) + 112 B root team |
| Formal total-footprint limit | 104857 bytes | 80% of default TCDM, including aligned buffers and runtime reservation |
| Formal aligned-buffer budget | 88345 bytes | Total-footprint limit minus runtime reservation |
