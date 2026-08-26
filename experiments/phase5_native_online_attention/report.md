# Phase 5: Native Online Attention Merge

Status: **formal collection complete; Sol Gate 2 PASS; archived**.

This report covers only the two prescribed anchors and the four fresh runs
collected by `collect_formal.py`. The formal snapshot is
`7da83c5ad08063e110be8917733b5ebc8bdb3a61`; the Phase 4 archive is the
preceding independent commit `4760567`. Formal results are archived in
`a8f2747526c0f9b6c11c6360101a78cd836604fe`.

## 27.1 Motivation

Phase 4 validated a materialized-probability attention path. That path is
useful for end-to-end integration, but it constructs a complete probability
matrix and therefore is not the natural workload for the Online Softmax Merge
Unit (SMU). The SMU is intended to merge online softmax state as score tiles
arrive.

This experiment places the existing recurrence implementations in that native
dataflow and changes only the recurrence backend:

```text
Software recurrence  ->  SMU recurrence
```

The question is whether the recurrence-level hardware benefit transfers to the
native online-attention core.

## 27.2 Native Online Attention Dataflow

For each query, keys and values are processed in fixed four-key tiles:

```text
Q/K/V
  -> scaled Q*K_tile^T
  -> local (m_tile, l_tile, O_tile)
  -> merge with running (m, l, O)
  -> same RVV O update
  -> next tile
  -> final O
```

The local state is

```text
l_tile = sum(exp(score - m_tile))
O_tile = sum(exp(score - m_tile) * V) / l_tile
```

The running state stores the normalized weighted-value state. The existing
merge recurrence computes the new maximum, normalization state, and
`w_old`/`w_tile`; the common RVV update computes
`O_new = w_old * O_old + w_tile * O_tile`. Therefore the final state is
already the attention output and there is no final normalization phase.

`No Materialized P` is a property of the target timed dataflow: the target
uses an `N x 4` score tile and online state, never an `N x N` probability
buffer. The host case generator may construct a golden `P_ref` for reference
checking outside the target and outside the timed region.

The formal tile and merge counts were:

| Case | N | D | Tile keys | Tiles | Real merges |
|---|---:|---:|---:|---:|---:|
| N8/D32 | 8 | 32 | 4 | 2 | 1 |
| N16/D64 | 16 | 64 | 4 | 4 | 3 |

## 27.3 Matched Baselines

The two binaries use the same deterministic seed (`1`), Q/K/V tensors, score
kernel, attention scaling, tile order, tile width, local-state code, memory
layout, allocator, RVV output-update routine, simulator, and compiler flags.
QKV generation/linear work and allocation are completed before the native-core
timer.

The only intended difference is:

| Component | Software | SMU |
|---|---|---|
| Non-first-tile recurrence | Existing B2-R scalar LUT recurrence | Existing Mixed Scalar SMU, mode 3 |
| RVV output update | Same `online_merge_rvv_update` | Same `online_merge_rvv_update` |
| Tile/local state | Same | Same |
| Final output | Same running `O` | Same running `O` |

The software path makes one scalar recurrence call per real merge. The SMU
path launches one mode-3 command per real merge and uses no SMU vector update.

## 27.4 Implementation

The implementation reuses the existing online-merge software and hardware
paths:

* `online_merge_b2_r_scalar` exposes the existing B2-R row-weight recurrence
  without updating `O`.
* `online_merge_rvv_update` is unchanged and is called by both binaries.
* SMU launch/status handling uses the existing cluster peripheral registers,
  with `ONLINE_MERGE_MODE_MIXED_SCALAR` (`mode=3`).
* Local-state exponential and reciprocal operations use the legacy B2-R Q1.23
  LUT wrappers. They are not a new mode-3 local-state datapath.
* No RTL datapath, FSM, LUT, precision allocation, ISA extension, or linear
  accelerator was added or modified.

The timed window begins after Q/K/V are ready and covers score computation,
local state, non-first-tile merge windows, residual core work, and final
`output_copy`. It excludes allocation, input generation, and diagnostics.
For each non-first tile:

```text
merge_window = recurrence + rvv_output_update + merge_orchestration
merge_total  = merge_window
```

The independent residual is reported as `core_residual`; the final field is
`output_copy`, not a normalization operation.

## 27.5 Numerical Correctness

The collector archived all final `O` values as uint32 FP32 bit patterns and
computed direct Software-to-SMU metrics in host float64. No target output was
non-finite, and all SMU commands completed without error or timeout.

| Case | Output MAE | Stable relative error | Cosine similarity |
|---|---:|---:|---:|
| N8/D32 | 2.793084e-4 | 4.884280e-3 | 0.9999845410 |
| N16/D64 | 4.665494e-4 | 7.052819e-3 | 0.9999707235 |

The small difference is expected because the software B2-R recurrence and the
Mixed Scalar SMU use different internal precision paths while preserving the
same mathematical recurrence. The collector rejects out-of-range uint32
encodings, decoded NaN/Inf values, and non-finite aggregate metrics.

## 27.6 Recurrence Performance

| Case | SW recurrence | SMU recurrence | Recurrence speedup |
|---|---:|---:|---:|
| N8/D32 | 12,368 | 1,451 | 8.524x |
| N16/D64 | 68,994 | 4,926 | 14.006x |

The SMU timing is additive. For N8/D32, `1451 = 1187 setup + 264 wait`.
For N16/D64, `4926 = 3468 setup + 1458 wait`.
The reported deltas are zero and the exactness flags are set.

## 27.7 Merge Kernel Performance

The merge kernel is the measured outer per-merge window containing recurrence,
the common RVV output update, and required orchestration:

| Case | SW merge total | SMU merge total | Merge speedup |
|---|---:|---:|---:|
| N8/D32 | 13,204 | 2,318 | 5.696x |
| N16/D64 | 77,037 | 13,060 | 5.899x |

The software and SMU paths have the same RVV update contract. The reduction is
therefore primarily the replacement of the software recurrence, with small
setup/orchestration differences exposed rather than hidden.

## 27.8 Native Attention Performance

| Case | Software native attention | SMU native attention | Speedup |
|---|---:|---:|---:|
| N8/D32 | 85,262 | 73,706 | 1.157x |
| N16/D64 | 571,374 | 507,918 | 1.125x |

Both prescribed anchors show a lower native online-attention core time with
SMU recurrence. The system-level benefit is smaller than the recurrence
benefit because score computation and local-state construction dominate the
core window.

## 27.9 Cycle Breakdown

All values are cycles from the formal CSV. `merge_total` equals the outer
`merge_window`; `core_residual` is independent of the merge kernel.

For plotting compatibility, `formal/timeline_breakdown.csv` also exposes the
requested compact schema; its `final_cycles` column is exactly the existing
`output_copy` value. The source cycle values are unchanged.

| Case | Impl. | Score | Local state | Recurrence | RVV update | Orchestration | Merge window | Residual | Output copy | Total |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N8/D32 | SW | 16,885 | 51,446 | 12,368 | 797 | 39 | 13,204 | 2,178 | 1,549 | 85,262 |
| N8/D32 | SMU | 16,906 | 50,689 | 1,451 | 812 | 55 | 2,318 | 2,242 | 1,551 | 73,706 |
| N16/D64 | SW | 135,686 | 344,198 | 68,994 | 7,908 | 135 | 77,037 | 8,292 | 6,161 | 571,374 |
| N16/D64 | SMU | 135,666 | 344,585 | 4,926 | 7,974 | 160 | 13,060 | 8,447 | 6,160 | 507,918 |

The SMU FSM observer recorded exactly the required mode-3 invocations:

| Case | Invocations | Per-invocation load | Scalar compute | Compute weight | Scalar store | Vector update | Busy |
|---|---:|---:|---:|---:|---:|---:|---:|
| N8/D32 | 1 | 104 | 8 | 24 | 72 | 0 | 208 |
| N16/D64 | 3 | 208 | 16 | 48 | 145 | 0 | 417 |

The N16 aggregate `compute_weight` count is 144 cycles (48 × 3). Every
invocation is `0..2`, `mode=3`, `DONE`, with `update_vector_cycles=0`.

## 27.10 Relationship to Previous B2R/A1

The earlier B2R/A1 experiment is microkernel evidence: it isolates a matched
online-merge workload and compares software recurrence with SMU recurrence.

This Phase 5 experiment is the integration evidence layer. It adds real tile
score computation, local online state, running state, the common RVV weighted
output update, and final attention output without materializing target-side
`P`. The formal result shows that the microkernel reduction transfers to the
native attention core, although score and local-state work limit the total
speedup.

## 27.11 Paper-Supported Claims

The formal data supports the following bounded claims:

* The existing Mixed Scalar SMU reduces the measured online merge recurrence
  cycles for both anchors (8.524x and 14.006x).
* With the same RVV output update and matched tile dataflow, it reduces the
  native online-attention core time for N8/D32 and N16/D64 (1.157x and
  1.125x).
* The two implementations produce numerically close final outputs under the
  reported MAE, stable relative error, and cosine metrics.

The experiment does **not** support a claim about end-to-end Transformer
Attention, QKV-linear-inclusive latency, multi-head attention, full-model
latency, energy, power, area, or performance across arbitrary sequence/head
dimensions. Recurrence speedup must not be presented as end-to-end Transformer
speedup.

## 27.12 Blocked / Deferred Issues

No P0/P1 correctness issue remains after formal collection and Sol Gate 2
review. The only deferred items are scope limitations:

* Only the two required anchors were measured; no shape sweep was performed.
* No model benchmark was performed.

The formal artifact directory contains the raw logs, output-bit archives,
cycle CSVs, numerical CSV, FSM breakdown, manifest, and separate configure /
build logs. The manifest records the clean commit, simulator SHA256, compiler
paths/version text/SHA256, ELF/header SHA256, separate configure/build-log
SHA256, and raw-log SHA256. The derived CSVs, output-bit archives, and this
report are sealed by the Git result commit below.

Observed wall time for the serial collector invocation was approximately
20 minutes 14 seconds, based on the configure/raw-log timestamps: about
2 minutes 15 seconds (N8 SW), 2 minutes 13 seconds (N8 SMU), 8 minutes
3 seconds (N16 SW), and 7 minutes 41 seconds (N16 SMU). These are simulator
wall times, not the cycle-count results reported above.
