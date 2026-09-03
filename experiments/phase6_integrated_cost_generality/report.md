# Phase 6 Integrated Hardware Cost and Workload Generality

Status: **P0-2 COMPLETE / P0-1 BLOCKED_RESOURCE**

This report records a partial closure. P0-2 has a PASS formal consolidation
for four Attention shapes. P0-1 has no accepted integrated area or timing
number because both exact official matched synthesis attempts reached the host
resource boundary during techmap.

The Proposed Design remains Scalar SMU + RVV. Full SMU is an ablation mode
only. Phase 6 does not change the SMU algorithm, datapath, LUT, precision
allocation, recurrence semantics, FSM, ISA, RVV datapath, or frozen RTL.
P0-1 evaluates the frozen integrated contribution named final Mixed SMU, and
P0-2 evaluates runtime mode 3, Mixed Scalar, with the existing RVV output
update.

## 1. Scope and frozen setup

P0-1 measures the cost of integrating the frozen SMU contribution into the
real Spatz cluster hierarchy. P0-2 extends the Phase 5 native online-attention
workload from two archived anchors to two additional frozen shapes.

The P0-1 synthesis top is `spatz_cluster_wrapper`. Its cluster instance is
`i_cluster`, and the SMU instance is
`i_online_merge_update_engine`. The SRAM macro is blackboxed. The source list,
top, hierarchy policy, memory assumptions, Nangate45 typical Liberty,
Yosys/Slang tool identity, optimization passes, and ABC map settings are
matched between configurations.

P0-2 uses the same Q/K/V inputs, seed, score and scale, local state, tile
order, tile size, merge count, RVV update, output semantics, and frozen RTL
for software and SMU runs. The core variable is software recurrence versus
SMU recurrence. All SMU launches use mode 3. No row was selected by its
speedup after collection, and no cherry-picking was used. The Phase 5 anchor
records come from commit `7da83c5ad08063e110be8917733b5ebc8bdb3a61`, whereas
the Phase 6 executed runs come from commit
`117caff8109c0f6c32cf07a8322a3397307c8e14`; their complete `hw` trees both
have tree object `eea7595276eb1a4c1fba58da791b4aa0f67f5f95`, establishing the
same frozen RTL across the four selected shapes.

## 2. Gate 1 record

Sol Gate 1 initially returned **FAIL (P0=0, P1=2)**. The findings were that
P0-1 used a non-hierarchical area statistic despite retained hierarchy, and
P0-2 read a nonexistent SMU status field in `run_details`.

The recorded disposition is `PASS_AFTER_P1_RESOLUTION`. P0-1 now specifies
`stat -top spatz_cluster_wrapper -hierarchy -json` and the instance-weighted
top `num_cells.area`. P0-2 derives status from implementation and
command/done/error/timeout counters and includes a contract self-test. The
four shape rows were frozen before formal collection.

## 2.1 Gate 2 record

Sol Max performed a read-only closure review and returned **GATE2_PASS**
(P0=0, P1=0, P2=2). This remains a partial closure: the two P2 notes are
that formal `.log` files were gitignored and were force-added into the final
archive, and that the Section 4 command is a canonical invocation template;
the r3/r4 exact commands with relocation parameters are recorded in the
formal manifest.

## 3. P0-1 matched method

The two matched configurations are:

| Configuration | SMU boundary treatment |
|---|---|
| Spatz Baseline | Temporary synthesis-only overlay from `957667e^` of `spatz_cluster.sv` and the four pre-SMU peripheral sources |
| Spatz + final Mixed SMU | Current frozen cluster RTL with the final Mixed SMU contribution retained and runtime mode support retained |

The baseline overlay files are:

`hw/system/spatz_cluster/src/spatz_cluster.sv`,
`hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral.sv`,
`hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg.hjson`,
`hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg_pkg.sv`,
and
`hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg_top.sv`.

The direct pre-SMU reference is `957667e^`. The unrelated core TCDM request-ID
tieoff is restored in the temporary baseline overlay so the intended
difference is the SMU-related cluster integration. The integration history
audit records exactly `957667e`, `dc6a6a9`, and `ec2d70e`, with no generated
wrapper change.

The flow keeps hierarchy during elaboration and mapping. The earlier
full-cluster flatten attempt exited 137, so flattening is not used here. The
elaboration smoke passed for both configurations and intentionally issued no
mapping, process, ABC, or stat command. The isolated hierarchical-stat CLI
smoke also passed, but it was not cluster data collection.

## 4. P0-1 formal result

The canonical official invocation template was
`python3 experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/run_matched_synthesis.py --execute-formal`.
The r3/r4 exact commands, including their relocation parameters, are recorded
verbatim in the P0-1 formal manifest.
Both official attempts used the frozen commit
`117caff8109c0f6c32cf07a8322a3397307c8e14` and reached the same failure
boundary.

| Attempt | Resource configuration | Exact official result | mapped-hier-stat | Accepted PPA |
|---|---|---|---|---|
| r3 | 4 GiB host RAM plus 4 GiB swap | Baseline-area flow OOM at techmap | absent | no |
| r4 | 6 GiB host RAM plus 4 GiB swap | Baseline-area flow OOM at techmap | absent | no |

The P0-1 formal CSV has two rows, and every area and timing numeric field is
empty. The status for both rows is `not_available_resource_blocked`.

### Integrated area

| Configuration | Area | Incremental area | Area overhead |
|---|---:|---:|---:|
| Spatz Baseline | not available (resource blocked) | not available (resource blocked) | not available (resource blocked) |
| Spatz + final Mixed SMU | not available (resource blocked) | not available (resource blocked) | not available (resource blocked) |

### Integrated timing

| Configuration | Local ABC stime delay | Change |
|---|---:|---:|
| Spatz Baseline | not available (resource blocked) | not available (resource blocked) |
| Spatz + final Mixed SMU | not available (resource blocked) | not available (resource blocked) |

The planned timing measure is the maximum local ABC `stime` delay across
reported mapped modules after the common `-D 50000` ps mapping target. It is
not an STA result, an Fmax result, a post-layout result, or a cross-hierarchy
path result. No such timing value was emitted.

### Blocker

Problem: P0-1 requires accepted hierarchical mapped area and local timing
measurements for the matched baseline and SMU cluster configurations.

现象: Both exact official baseline-area attempts reached global OOM at
techmap before `mapped-hier-stat.json` was emitted. The r4 kernel evidence
reports `total-vm=6535660kB`, `anon-rss=4288984kB`, and
`free swap=200kB`.

影响: The comparison has no mapped hierarchical statistic, no accepted
integrated area, no incremental area, no area overhead, and no timing change.
The standalone SMU reference cannot replace the missing integrated result.

可能原因: The retained full cluster elaboration and technology mapping exceed
the available host memory and swap at the current exact flow boundary.

当前状态: **BLOCKED**

## 5. P0-2 frozen Attention shapes

The formal shape manifest contains exactly four selected rows:

| Case | N | D | Tile | Tiles | Real merges | Source |
|---|---:|---:|---:|---:|---:|---|
| N8_D32_S1 | 8 | 32 | 4 | 2 | 1 | Phase 5 formal anchor |
| N16_D64_S1 | 16 | 64 | 4 | 4 | 3 | Phase 5 formal anchor |
| N24_D64_S1 | 24 | 64 | 4 | 6 | 5 | Phase 6 formal |
| N16_D128_S1 | 16 | 128 | 4 | 4 | 3 | Phase 6 formal |

The two new shapes fit the current TCDM allocation policy. N32/D64 was
rejected before formal collection because its matched smoke did not complete
within the host/completion budget and produced no matched result. No speedup
was inspected for that rejection. N24/D64 is the recorded replacement.

## 6. P0-2 performance

The following values are copied from
`p0_2_workload_generality/formal/performance.csv`.

| Source | Case | N | D | Tile | Tiles | Merges | SW recurrence cycles | SMU recurrence cycles | Recurrence speedup | SW merge cycles | SMU merge cycles | Merge speedup | SW core cycles | SMU core cycles | Core speedup | SW status | SMU status | Commands | DONE | Errors | Timeouts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| phase5_formal | N8_D32_S1 | 8 | 32 | 4 | 2 | 1 | 12368 | 1451 | 8.523776705720193 | 13204 | 2318 | 5.6962899050905955 | 85262 | 73706 | 1.156785064987925 | pass | pass | 1 | 1 | 0 | 0 |
| phase5_formal | N16_D64_S1 | 16 | 64 | 4 | 4 | 3 | 68994 | 4926 | 14.006090133982948 | 77037 | 13060 | 5.898698315467075 | 571374 | 507918 | 1.1249335522663106 | pass | pass | 3 | 3 | 0 | 0 |
| phase6_formal | N24_D64_S1 | 24 | 64 | 4 | 6 | 5 | 165993 | 9334 | 17.78369402185558 | 186446 | 29711 | 6.275318905455892 | 1288856 | 1130764 | 1.1398098984403466 | pass | pass | 5 | 5 | 0 | 0 |
| phase6_formal | N16_D128_S1 | 16 | 128 | 4 | 4 | 3 | 67451 | 4910 | 13.737474541751528 | 82220 | 19841 | 4.143944357643264 | 1026162 | 962823 | 1.0657846769343897 | pass | pass | 3 | 3 | 0 | 0 |

Across the four measured shapes, recurrence speedup is 8.524x–17.784x,
merge speedup is 4.144x–6.275x, and core speedup is 1.066x–1.157x.
The merge window is recurrence plus RVV output update plus orchestration.
SMU recurrence is setup plus wait, with `delta=0` and `exact=1` in the
measurement contract.

## 7. P0-2 numerical result

The following values are copied from
`p0_2_workload_generality/formal/numerical_agreement.csv`.

| Source | Case | N | D | Output MAE | Stable relative error | Cosine similarity | No NaN | SMU DONE | SMU error | Timeout |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| phase5_formal | N8_D32_S1 | 8 | 32 | 0.00027930841859813427 | 0.004884280453878236 | 0.9999845409676584 | 1 | 1 | 0 | 0 |
| phase5_formal | N16_D64_S1 | 16 | 64 | 0.0004665493647806329 | 0.0070528189563345296 | 0.9999707235395717 | 1 | 1 | 0 | 0 |
| phase6_formal | N24_D64_S1 | 24 | 64 | 0.00037368802472788804 | 0.006109508981206703 | 0.999980878833838 | 1 | 5 | 0 | 0 |
| phase6_formal | N16_D128_S1 | 16 | 128 | 0.0005631592360604287 | 0.005219446185106457 | 0.9999847510886731 | 1 | 3 | 0 | 0 |

All four rows pass the numerical and execution contract. The output chunks
are contiguous and complete, outputs are finite, and every SMU invocation
uses mode 3 and reaches DONE without an error or timeout.

## 8. Explicit Q1 to Q4 answers

| Question | Answer | Evidence |
|---|---|---|
| Q1. Can the same frozen RTL cover multiple reasonable Attention shapes? | Yes | Phase 5 anchors use `7da83c5ad08063e110be8917733b5ebc8bdb3a61`; Phase 6 runs use `117caff8109c0f6c32cf07a8322a3397307c8e14`; both complete `hw` trees are `eea7595276eb1a4c1fba58da791b4aa0f67f5f95`; all use mode 3 and tile size 4 |
| Q2. Is recurrence speedup greater than 1 across every shape? | Yes | The minimum recurrence speedup is 8.524x |
| Q3. Is merge-kernel speedup greater than 1 across every shape? | Yes | The minimum merge speedup is 4.144x |
| Q4. Is Native Attention Core speedup greater than 1 across every shape? | Yes | The minimum Native Attention Core speedup is 1.066x |

Separately, all SMU launches reach DONE with zero errors and timeouts, and all
four rows satisfy the numerical output contract.

## 9. Cost-benefit conclusion

Integrated area: **not available (resource blocked)**.

Integrated timing: **not available (resource blocked)**.

P0-2 provides measured recurrence, merge-window, and native Attention core
cycles for four shapes. It does not provide an integrated area or timing
tradeoff. No integrated cost conclusion is made.

## 10. Supported claims

The evidence supports the following claims:

1. The Scalar SMU + RVV path was evaluated on four selected Attention shapes
   with tile size 4 and runtime mode 3.
2. The measured recurrence, merge-window, and native Attention core speedups
   are the four CSV-derived rows shown above, with the stated ranges.
3. The four measured rows satisfy the recorded finite-output, DONE, zero-error,
   and zero-timeout contract.
4. P0-1's exact official integrated cost collection was attempted twice and
   is blocked by resource exhaustion before an accepted mapped statistic.

The P0-2 generality claim is limited to multiple evaluated Attention shapes.
It is not a claim about a full Transformer, Multi-Head Attention, an LLM,
model generality, or end-to-end inference.

## 11. Unsupported claims

This report does not claim integrated area, incremental area, area overhead,
timing change, power, energy, post-layout delay, Fmax, or end-to-end model
acceleration. The local ABC `stime` definition is not used as STA, Fmax, or
post-layout evidence. It does not claim performance for shapes outside the
four selected rows. Full SMU is not treated as the Proposed Design.

## 12. Formal freeze and provenance

The P0-1 formal artifact and the P0-2 executed runs use freeze commit
`117caff8109c0f6c32cf07a8322a3397307c8e14`, with clean status recorded in
both formal manifests. P0-2 imports its two Phase 5 anchor rows from commit
`7da83c5ad08063e110be8917733b5ebc8bdb3a61`; the complete `hw` tree object is
`eea7595276eb1a4c1fba58da791b4aa0f67f5f95` for both commits, as recorded by
`cross_phase_rtl_identity`. The P0-1 sources are
`p0_1_integrated_cost/formal/manifest.json` and
`p0_1_integrated_cost/formal/synthesis_comparison.csv`. The latter contains
two rows with empty area and timing fields and
`not_available_resource_blocked` status.

The P0-2 collection mode is `offline-formal-consolidation`. Its formal
manifest and audit report reconciled the performance CSV, numerical CSV,
FSM values, run logs, output hashes, contiguous output chunks, the Phase 6
executed-run freeze commit, and cross-phase RTL identity. All runs use the same simulator
`/home/wxt/spatz-archive/phase4/work-phase4-recip-sim/spatz_cluster.vlt`,
whose recorded SHA256 is
`8f85b204d064f1ced29d2fc27518754f8b018db0530cf2328a3a1062687c9138`.

The host reboot interrupted the original P0-2 session. In r1, the complete
runs were N24/D64 software, N24/D64 SMU, and N16/D128 software. The
N16/D128 SMU predecessor was incomplete, with three OM-FSM invocations and no
result or output chunks, and was excluded. r2 recovered only the interrupted
N16/D128 SMU run with a runner-guarded single-run recovery. The final audit
records the three complete r1 runs, one r2 recovered run, and exclusion of the
incomplete r1 predecessor.

The exact commands, tool hashes, library hash, source overlays, log paths,
r3 and r4 OOM evidence, and all artifact hashes remain in the P0-1 and P0-2
manifests and audits. No source RTL or other file is changed by this report.
