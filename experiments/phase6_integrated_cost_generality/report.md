# Phase 6 Integrated Hardware Cost and Workload Generality

Status: **Gate 1 P1 findings resolved; formal data collection is approved but has not started.**

This directory is independent of the frozen Phase 1--5 result directories.
Phase 6 adds only the two requested system-level supplements:

1. cluster-level cost of integrating the final Mixed SMU into Spatz; and
2. a minimal two-shape extension of the Phase 5 native online-attention
   workload.

No SMU algorithm, datapath, LUT, precision allocation, recurrence semantics,
FSM, ISA, or RVV datapath is changed in this phase.  The selected D128
workload adds the benchmark's existing `1/sqrt(128)` attention scale.  The
out-of-timing exact-bit archive uses 256-word `PHASE5_OUTPUT_CHUNK` records so
larger outputs do not rely on one oversized host syscall.  This is a benchmark
archive-transport fix, not a hardware or timed dataflow change.

## 1. Scope

The two P0 tasks are independent.  P0-1 uses the real generated
`spatz_cluster_wrapper` top and the current cluster integration hierarchy.
P0-2 reuses the Phase 5 target names, generated Q/K/V method, tile-based
native dataflow, and matched software/SMU measurement contract.

Formal synthesis and performance collection are approved after resolving the
Gate 1 P1 findings, but have not started in this handoff.

## 2. Frozen Design

The final cluster integration is:

```text
spatz_cluster_wrapper
  -> spatz_cluster (i_cluster)
       -> i_online_merge_update_engine
```

The cluster instance uses the existing `online_merge_update_engine` defaults
(`PrecisionSupport=2`, `ScalarOnly=0`).  The final Mixed reciprocal arithmetic
is enabled by `ONLINE_MERGE_MIXED_RECIPROCAL`; software selects runtime mode 3
(`Mixed Scalar`) as in Phase 5.  The P0-1 integrated configuration retains
this runtime-mode support rather than compiling away other legal modes.

The Phase 5 formal anchors remain N8/D32 and N16/D64.  Their formal CSVs are
read-only sources and are not copied into or modified in their original
directories.

## 3. P0-1 Methodology

P0-1 compares two matched cluster configurations:

| Configuration | SMU boundary treatment |
|---|---|
| Spatz Baseline | Temporary synthesis-only overlay of `spatz_cluster.sv` and the four pre-SMU peripheral sources from `957667e^`; this removes the engine, merge TCDM master, and SMU CSR glue without editing the current worktree. |
| Spatz + final Mixed SMU | Same cluster RTL and all common configuration; final reciprocal Mixed SMU contribution is retained with runtime mode support. |

Both configurations use the same generated Bender source list, top,
hierarchy policy, SRAM blackbox assumption, Nangate45 typical Liberty,
Yosys/Slang tool identity, optimization passes, and ABC map settings.  The
planned flow is implemented in
`p0_1_integrated_cost/run_matched_synthesis.py`; without
`--execute-formal`, it is plan-only.

The baseline reference is the direct parent of the first SMU integration
commit (`957667e^`).  The only overlaid files are the cluster and the four
peripheral sources changed by the SMU integration history; the generated
wrapper and every other source remain at the current snapshot.  This gives a
pre-SMU cluster boundary without changing frozen RTL in the working tree.
The one unrelated core-TCDM request-ID tieoff carried in the first integration
commit is restored to its current value in the temporary baseline overlay;
this carry-forward is recorded explicitly in the P0-1 manifest.

The read-only history audit found exactly three commits touching this
cluster/peripheral boundary after `957667e^`: `957667e`, `dc6a6a9`, and
`ec2d70e`; no generated-wrapper change is present in that history.  The exact
file list and command are recorded in the P0-1 manifest.

The prior full-cluster attempt demonstrated that flattening the elaborated
cluster exceeded the available resource budget and exited 137.  The Phase 6
flow therefore keeps hierarchy during elaboration and mapping.  This is a
flow boundary inherited from the existing cluster evidence, not a design
change.

Before Gate 1, `run_elaboration_smoke.py` reads each generated flist with the
same explicit hashed Slang plugin and runs `hierarchy -check -top
spatz_cluster_wrapper`.  The baseline uses the historical overlay flist and
the SMU case uses the current flist.  This smoke intentionally issues no
process, ABC, mapping, or `stat` command; its command, return code, and
timestamps are archived under `p0_1_integrated_cost/logs/`.

After Gate 1 review, an isolated two-level Yosys fixture confirmed that
`stat -top <top> -hierarchy -json -liberty <liberty>` is accepted and emits
the expected `modules[\\<top>].num_cells.area` schema.  This check was
non-mapping and did not collect cluster data; its return code and schema
summary are in `logs/stat_hierarchy_smoke.log`.

## 4. Matched Spatz Configurations

The exact provisional comparison and all provenance fields are in
`p0_1_integrated_cost/manifest.json`.  The synthesis top is
`spatz_cluster_wrapper`; its cluster instance is `i_cluster`, and the SMU
instance is `i_online_merge_update_engine`.  CPU count, vector/TCDM
configuration, memory assumptions, technology, library, and synthesis tool
are shared.  No formal area or timing number is available yet.

## 5. Cluster-Level Area Cost

**Pending formal synthesis.**  The final table will be written only
from `p0_1_integrated_cost/formal/synthesis_comparison.csv`:

| Configuration | Area (um^2) | Incremental Area (um^2) | Area Overhead |
|---|---:|---:|---:|
| Spatz Baseline | pending | -- | -- |
| Spatz + Mixed SMU | pending | pending | pending |

The definitions are:

\[
A_{\mathrm{incremental}}=A_{\mathrm{Spatz+SMU}}-A_{\mathrm{Spatz}}
\]

\[
A_{\mathrm{overhead}}=100\times
\frac{A_{\mathrm{Spatz+SMU}}-A_{\mathrm{Spatz}}}{A_{\mathrm{Spatz}}}.
\]

The existing standalone reciprocal Mixed SMU mapped area, 52407.586 Liberty
cell-area units (um^2), is retained only as a sanity-check reference.  The
integrated area is the instance-weighted hierarchical-top `num_cells.area`
reported by `stat -top spatz_cluster_wrapper -hierarchy -json`, using mapped
Nangate45 standard-cell area in um^2.  Retained hierarchy is not flattened;
the SRAM macro is blackboxed and its macro area is excluded.  It is not a
substitute for the integrated measurement.

## 6. Cluster-Level Timing Impact

**Pending formal synthesis.**  The existing synthesis methodology
has no SDC `create_clock` or I/O delay constraint.  Accordingly, Phase 6 will
report an **ABC synthesis timing proxy**: the maximum local post-map `stime`
delay among all reported mapped modules from the same `-D 50000 ps` target and
common Liberty map.  The runner archives all delay samples, rather than
assuming that the last log line is the cluster worst case.  This is not a
cross-hierarchy STA path and will not be called post-layout delay, timing
closure, or post-layout Fmax.

The final comparison will use:

\[
\Delta T=100\times
\frac{T_{\mathrm{Spatz+SMU}}-T_{\mathrm{Spatz}}}{T_{\mathrm{Spatz}}}.
\]

## 7. Standalone vs Integrated SMU Area

The standalone reference is the Phase 3 reciprocal Mixed result.  The
integrated incremental area can differ because hierarchy is preserved,
constant/dead logic is optimized in context, interconnect glue is included,
and the cluster contains shared logic.  The consistency check is descriptive
only and will not be used to replace either formal result.

## 8. P0-2 Methodology

P0-2 directly reuses the Phase 5 native online-attention benchmark.  The
target never materializes a full N x N probability matrix.  For each four-key
tile it computes scores and local `(m,l,O)`, performs the real online merge,
applies the same RVV output update, and carries only the running state.

The software and SMU targets use the same Q/K/V input, seed, score and scale,
local state, tile order, tile size, merge count, RVV update, and output
semantics.  The only core variable is the software recurrence versus the SMU
recurrence.  SMU launches remain runtime mode 3 and require DONE with zero
error and timeout.

## 9. Frozen Attention Shapes

The provisional manifest prepared before Phase 6 formal collection is
`p0_2_workload_generality/shape_manifest.csv`.  It retains the two archived
Phase 5 anchors and selects exactly two new shapes before Phase 6 formal
collection:

| Case | N | D | Tile | Tiles | Real merges | Status |
|---|---:|---:|---:|---:|---:|---|
| N8/D32 | 8 | 32 | 4 | 2 | 1 | archived Phase 5 anchor |
| N16/D64 | 16 | 64 | 4 | 4 | 3 | archived Phase 5 anchor |
| N24/D64 | 24 | 64 | 4 | 6 | 5 | frozen new shape |
| N16/D128 | 16 | 128 | 4 | 4 | 3 | frozen new shape |

Both candidates fit the current 128 KiB TCDM allocation policy.  The
estimated data formula is `28*N*D + 48*N`, allocation is aligned to 256
bytes, and the Phase 5 runtime reservation is 16512 bytes.  Estimated
footprints are 60800 bytes (N24/D64) and 74624 bytes (N16/D128), below the
80%-of-TCDM limit of 104857 bytes.  Both selected cases have real online
merges.

N32/D64 was the initial pre-result candidate.  Its software smoke exceeded
the 900 s host wall budget without a `PHASE5_RESULT`; the interrupted SMU
smoke emitted only OM_FSM invocations 0..2 and no result/output.  No speedup
was inspected.  It is retained as a structured rejected candidate in
the P0-2 manifest and this report (the formal shape manifest remains exactly
four rows), and N24/D64 is the single pre-formal replacement.

The ignored local `sw/toolchain/riscv-opcodes` checkout link was repaired for
the host-only smoke/build environment to resolve to the pinned
`/home/wxt/spatz-archive/toolchain-src/riscv-opcodes`; this is recorded in the
P0-2 manifest and does not alter the timed target or tracked RTL.

The two new shapes are now frozen.  The replacement was selected under the
pre-declared host-completion criterion before formal collection, while N32
had no matched result and no shape sweep or speedup-based selection was
performed.  Both selected shapes must be retained even if a later speedup is
non-positive.

## 10. Numerical Correctness

**Smoke evidence before formal collection.**  N16/D128 software and SMU
smokes now complete with `PHASE5_RESULT status=pass`, eight contiguous
256-word output chunks covering exactly 2048 bits, no non-finite outputs, and
SMU mode-3 3/3 DONE with zero errors/timeouts.  N24/D64 replacement smoke is
also complete: both paths report pass, six contiguous chunks cover exactly
1536 bits, and the SMU path has 5/5 mode-3 DONE with zero errors/timeouts.
Its smoke-only software/SMU output comparison is MAE=3.7368802472788804e-4,
stable relative error=6.109508981206703e-3, and cosine=0.999980878833838.
These smoke values are not formal performance rows.  The final table will
combine the archived
Phase 5 numerical CSV and the new Phase 6 rows without altering the old
source.  Each new row must have finite output, `SMU DONE`, zero SMU error,
zero timeout, output MAE, stable relative error, and cosine similarity.

## 11. Recurrence Performance

**Pending formal collection.**  The final table will report matched software
and SMU recurrence cycles and `SW/SMU` speedup for all four shapes.

## 12. Merge-Kernel Performance

**Pending formal collection.**  The final table will report the same real
merge-window definition used in Phase 5 and its `SW/SMU` speedup for all four
shapes.

## 13. Native Attention Core Performance

**Pending formal collection.**  The final table will report matched native
core cycles and `SW/SMU` speedup.  No claim about full Transformer or
end-to-end model inference is in scope.

## 14. Workload Generality

The strongest supported conclusion, if the four formal rows pass the
correctness contract, is that the same frozen SMU RTL and the same tile-4
Native Online Attention dataflow were evaluated on multiple reasonable
Attention shapes.  This is workload-shape evidence only; it is not a model,
LLM, Multi-Head Attention, or scalability claim.

## 15. Cost-Benefit Summary

**Pending formal data.**  The final report will place cluster-level area and
timing proxy beside recurrence, merge, and Native Attention Core results.
No positive cost or speedup conclusion is prewritten.

## 16. Relationship to Phase 5

Phase 5 formal numbers remain frozen and are imported from its formal
artifacts.  Phase 6 does not overwrite those CSVs, manifests, logs, or
reports.  The Phase 6 collector will run only the two new shapes after the
implementation commit is clean; the four-shape output table will identify
which rows are archived Phase 5 data and which are fresh Phase 6 data.

## 17. Supported Paper Claims

Pending measured data, the report may support only cluster-level mapped area
overhead, the stated ABC timing proxy change, matched recurrence/merge/core
cycle results, and multiple-shape support for the exact evaluated cases.

## 18. Unsupported Claims

This phase does not measure post-layout Fmax or latency, power, energy,
full-Transformer speedup, Multi-Head Attention, FFN/LayerNorm/GELU, model or
LLM generality, or end-to-end inference acceleration.

## 19. Blocked / Deferred Issues

* Formal P0-1 synthesis is approved after the Gate 1 P1 resolution; no formal
  synthesis has started in this handoff.
* Formal P0-2 simulation is approved after the Gate 1 P1 resolution; no formal
  simulation has started in this handoff.
* N32/D64 was rejected before any performance result because both smoke
  paths failed to complete within the host/completion budget; this is not a
  speedup-based selection.  N24/D64 is the recorded replacement.
* The prior full-cluster flatten attempt exited 137; the Phase 6 flow keeps
  hierarchy and preserves that limitation as provenance.

## 20. Provenance

Provisional machine-readable manifests are under each P0 directory.  The
planned P0-1 flow records top, Bender source-list command, SRAM assumption,
tool/library hashes, synthesis passes, map targets, and log paths.  The P0-2
manifest records shapes, memory calculations, simulator identity, matched
variables, and gate state.  Formal manifests and CSVs will be created only by
the explicit collectors from a clean approved commit.

## 21. Gate 1 Review Record

Sol Gate 1 returned **FAIL (P0=0, P1=2)**.  The findings were: (1) P0-1
used the non-hierarchical `design.area` despite retained hierarchy, and (2)
P0-2 `run_details` read a nonexistent SMU status field and could label a
completed SMU run `not-launched`.

The P1 fixes are applied and recorded in both manifests.  P0-1 now uses
`stat -top spatz_cluster_wrapper -hierarchy -json` and parses the
instance-weighted top `num_cells.area`; P0-2 derives status from the
implementation and command/done/error/timeout counters and includes a pure
contract self-test.  The four shape rows are frozen.  Gate 1 disposition is
`PASS_AFTER_P1_RESOLUTION`: formal collection is approved, no formal command
has run, and the worktree remains uncommitted for the formal collection
workflow.
