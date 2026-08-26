# Phase 5: Native Online Attention Merge

Status: **Gate 1 re-review; formal data not started**.

This directory is independent of the archived Phase 1--4 result directories.
The target benchmark is registered as two ELF variants:

```text
native-online-attention-software
native-online-attention-smu
```

Both variants use the same generated FP32 Q/K/V tensors, score kernel, local
tile-state kernel, RVV output update, tile order, allocator, compiler flags and
simulator. The compile-time selector changes only the online merge recurrence:

```text
Software: existing LUT-backed B2-R scalar recurrence -> existing RVV update
SMU:      existing Mixed Scalar mode 3             -> existing RVV update
```

## Dataflow

The fixed anchor tile has four keys. For each query and tile, the target
computes the scaled `Q * K_tile^T`, reduces the local scores to
`(m_tile, l_tile, O_tile)`, and carries only the running `(m, l, O)` state:

```text
Q/K/V resident
    -> score tile (N x 4 temporary)
    -> local (m_tile, l_tile, O_tile)
    -> online merge with running (m, l, O)
    -> same RVV O update
    -> next tile
    -> final normalized O
```

`O_tile` and `O` are normalized weighted-value states. For a local tile,
`l_tile = sum(exp(score - m_tile))` and
`O_tile = sum(exp(score - m_tile) * V) / l_tile`. The existing merge
recurrence then computes `w_old`, `w_tile`, `l_new`, and
`O_new = w_old * O_old + w_tile * O_tile`. Consequently no final division is
needed; the final state is already the attention output. `No Materialized P`
applies to this target timed dataflow: the host case generator may use the
Phase 4 host reference (including a host-side `P_ref`) outside the target and
outside timing. The target itself never allocates or materializes an `N x N`
P buffer.

The two required anchors use `PHASE5_TILE_KEYS=4`:

| anchor | tiles | real merges |
|---|---:|---:|
| N8/D32 | 2 | 1 |
| N16/D64 | 4 | 3 |

Q/K/V are the deterministic FP32 projection outputs from the Phase 4 host
case generator. They are copied before the native-core timer; QKV linear work
and allocation are outside the timed region.

## Reused implementation

* `online_merge_b2_r_scalar` is a small API exposure of the existing
  `online_merge_rtl_row_weights`/B2-R LUT recurrence. It writes only
  `m_new`, `l_new`, `old_weight`, and `tile_weight`.
* `online_merge_rvv_update` is used unchanged by both target variants.
* SMU launch/status handling uses the existing cluster peripheral registers;
  mode is explicitly `ONLINE_MERGE_MODE_MIXED_SCALAR` (`3`).
* The local-state exp and reciprocal wrappers call the existing legacy B2-R
  Q1.23 exp and reciprocal LUT semantics; they are not a mode-3 local-state
  datapath. No LUT, precision allocation, RTL datapath or FSM was changed.
* RTL changes: none. The only C/CMake changes are integration, generated
  input, measurement and the scalar-only API exposure described above.

The FP32 software recurrence and Mixed SMU recurrence have the same
mathematical recurrence but can differ in internal precision, as allowed by
the Phase 5 protocol. The target emits output error metrics against the
generated FP32 reference, plus a 32-bit output digest. Full final-O dumping is
disabled by default because diagnostic output dominates this small simulator
run; `PHASE5_DUMP_OUTPUT=1` emits one compact `PHASE5_OUTPUT` JSON record via a
single host write. The record contains every final-O FP32 encoding as a uint32
bit pattern for the formal collector to archive. This diagnostic write is
outside the timed core window.

## Measurement contract

`total` starts after Q/K/V have been loaded and includes score computation,
local state, non-first-tile merge windows, core residual work and final output
copy. It excludes allocation, input generation and post-timer diagnostics.
For every non-first tile, an outer window starts immediately before recurrence
and ends after the same RVV update and running-state swap:

```text
merge_window = recurrence + rvv_output_update + merge_orchestration
```

The cycle fields are:

```text
score_compute
tile_local_state
software_recurrence or smu_recurrence
rvv_output_update
merge_window
merge_orchestration
core_residual
output_copy
merge_total = merge_window
total
```

`clear_tile_output` is included in `tile_local_state`. First-tile state
initialization, timer gaps and other non-merge work are represented by the
independent `core_residual`, rather than being charged to `merge_total`.

For SMU, the recurrence window includes register programming, clear/start, and
BUSY/DONE polling. `smu_setup` starts at the same cycle sample as the
recurrence window, and `smu_wait` ends at its final sample, so the target
reports and checks `smu_recurrence == smu_setup + smu_wait` and emits the
corresponding sum/delta/exact fields. `OM_FSM` (the simulation-only observer
already present in RTL) supplies `compute_weight_cycles` and the other FSM
buckets. The target also reports SMU command/done/error/timeout counts, and
`mode=3` is visible in each `OM_FSM` record.

## Gate 1 smoke evidence (non-formal)

Using `/home/wxt/work-phase4-recip-sim/spatz_cluster.vlt`, N8/D32 and seed 1,
both ELF variants built successfully and completed with `status=pass`:

```text
Software: total=84451, recurrence=12377, RVV=797,
          merge_window=13213, merge_orchestration=39,
          core_residual=2161, output_copy=1549,
          output_nonfinite=0, output cosine diagnostic=0.9999992
SMU:      total=72221,  recurrence=1498,  RVV=792,
          merge_window=2339, merge_orchestration=49,
          core_residual=2212, output_copy=1551,
          output_nonfinite=0, output cosine diagnostic=0.9999858,
          commands=1, done=1, errors=0, timeouts=0, mode=3,
          setup=1220, wait=278, setup+wait=recurrence
```

These are post-fix implementation smoke values only and are not frozen Phase 5
results. A dump-enabled N8 diagnostic emitted all 256 final FP32 bits per
path in the compact output record; the collector accepts simulator text
appended after a JSON record. The actual one-write SW N8 smoke log is archived
at `smoke/sw_n8_onewrite.log`; `collect_formal.parse_output_bits()` accepted
`n=8`, `d=32`, and exactly 256 bits after the simulator's `[SUCCESS]` text.
The N16/D64 target and generated case also build successfully. A
long N16/D64 software simulator smoke was started but stopped without a result
because the Verilator throughput is low; it is deferred to the formal run and
is not a correctness failure.

## Formal commands after Gate 1

Run each anchor and each implementation from a clean approved snapshot using
the same simulator and flags. The target names are:

```text
test-spatzBenchmarks-native-online-attention-software
test-spatzBenchmarks-native-online-attention-smu
```

The planned collector is `collect_formal.py`. With no arguments it is
plan-only and executes no command:

```text
python3 experiments/phase5_native_online_attention/collect_formal.py
```

After a clean approved snapshot, execute the four-run matrix with the explicit
gate:

```text
python3 experiments/phase5_native_online_attention/collect_formal.py \
  --execute-formal --output experiments/phase5_native_online_attention/formal
```

The collector refuses a dirty worktree, stale N8/N16 build directory or
non-empty output directory; both build directories are preflighted once before
any formal output is created or command is run. It configures/builds both
targets for each anchor with `PHASE5_DUMP_OUTPUT=1`, runs fresh simulator
processes, archives raw logs and all final FP32 output bits, checks the
call/command/`OM_FSM` contracts, and computes direct SW-to-SMU MAE, stable
relative error and cosine in host float64. It writes `manifest.json`,
`native_merge_performance.csv`,
`native_merge_summary.csv`, `native_attention_performance.csv`,
`numerical_agreement.csv`, and `om_fsm_breakdown.csv`.

The manifest records the clean-before-run audit (including any Phase 4 dirty
entries), commit, simulator/config/compiler/flags, complete build/run
commands, separate configure/build logs, actual C/C++/GCC compiler executable
paths, `--version` text and SHA256, ELF/header hashes, raw-log hashes and
external simulator SHA256. The collector's startup self-test injects
`0x7fc00000` and requires NaN rejection.
No formal run or freeze is claimed by this Gate 1 package.

## Known issues / deferred

* UART output and Verilator throughput make even a ~100k-cycle target run take
  roughly 1--2 minutes. Default output is therefore a compact digest and
  reference metrics; this does not affect the timed core window.
* Direct pairwise MAE between the two final output arrays is implemented in
  `collect_formal.py` using archived output bits and host float64; it remains
  uncollected until the clean formal run.
* N16/D64 non-formal execution was deferred after the successful build; both
  N16/D64 implementations remain required in the formal fresh-run matrix.
