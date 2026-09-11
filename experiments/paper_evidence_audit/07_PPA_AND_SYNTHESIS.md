# PPA and Synthesis Audit

## A. Standalone mixed-SMU PPA — available

Frozen source: `experiments/phase3_reciprocal_hardware/`. All three designs use
matched standalone scope, Nangate45 typical Liberty, Yosys/ABC, and three trials.
Each design's three area signatures and values are identical.

### Formal area flow

| Design | Top | Cells | Sequential area | Combinational area | Total mapped area | vs Legacy |
|---|---|---:|---:|---:|---:|---:|
| Legacy scalar | `online_merge_legacy_scalar_mapped_top` | 69,012 | 2,761.080 | 69,638.002 | 72,399.082 | — |
| Mixed + Division | `online_merge_mixed_division_scalar_mapped_top` | 47,141 | 3,521.840 | 48,478.234 | 52,000.074 | −28.176% |
| Mixed + Reciprocal | `online_merge_mixed_reciprocal_scalar_mapped_top` | 48,418 | 2,824.920 | 49,582.666 | 52,407.586 | −27.613% |

The reciprocal variant is `407.512` area units (`0.784%`) larger than the
division variant in this area flow, but has lower sequential area.

### Formal timing-proxy flow

The timing experiment uses a separate constrained mapping. Its mapped cell/area
columns differ from the area flow and must not be used as the area result.

| Design | Longest reg-to-reg proxy | vs Legacy | vs Division | 1.5 ns target |
|---|---:|---:|---:|---|
| Legacy scalar | 12,517.79 ps | — | — | not met |
| Mixed + Division | 14,619.73 ps | +16.792% | — | not met |
| Mixed + Reciprocal | 15,539.55 ps | +24.140% | +6.292% | not met |

Paper-safe name: **pre-layout Nangate45/ABC reg-to-reg combinational-delay
proxy**. It is not Fmax, STA, post-layout timing, or cluster timing. Inverting the
delay and labeling it MHz is forbidden.

Primary files:

- `experiments/phase3_reciprocal_hardware/area/area_trials.csv`
- `experiments/phase3_reciprocal_hardware/area/area_manifest.json`
- `experiments/phase3_reciprocal_hardware/timing/timing_trials.csv`
- `experiments/phase3_reciprocal_hardware/timing/timing_manifest.json`
- `experiments/phase3_reciprocal_hardware/report.md`

## B. Historical A1 versus Full SMU standalone ablation — separate epoch

The M2/TCAS-II freeze reports:

| Design | Cells | Liberty area | Relative to A1 | Timing proxy |
|---|---:|---:|---:|---:|
| A1 Scalar SMU + RVV | 73,505 | 77,103.292 | 1.000× | 12.34285 ns |
| A2 Full SMU | 107,372 | 114,713.298 | 1.4878× | 13.20260 ns |

A2 is `48.779%` larger than A1 in that standalone flow. This supports only the
historical ablation that moving the dimension-dependent update into the SMU costs
more standalone area. It is a different mapped-top/evidence epoch from the Phase 3
three-design mixed arithmetic table; do not merge their absolute areas.

Sources: `experiments/parsed/final_area.csv`,
`experiments/parsed/final_timing.csv`,
`experiments/parsed/final_hardware_results.csv`, under
`experiments/reports/FINAL_EVIDENCE_FREEZE.md`.

## C. Cluster-level matched synthesis — unavailable

### Intended comparison

| Configuration | Definition |
|---|---|
| Spatz Baseline | synthesis-only pre-SMU overlay from `957667e^`, retaining the unrelated TCDM request-ID tieoff |
| Spatz + final Mixed SMU | current frozen cluster integration with runtime-mode support |

Both used top `spatz_cluster_wrapper`, black-box SRAMs, hierarchy-preserving
elaboration/mapping, common Nangate45/Yosys/Slang inputs, and the frozen commit
`117caff8109c0f6c32cf07a8322a3397307c8e14`.

### Formal attempts and resource boundary

| Attempt | Memory/swap | Failure stage | `mapped-hier-stat` | Accepted PPA |
|---|---|---|---|---|
| r3 | 4 GiB RAM + 4 GiB swap | baseline area flow OOM at techmap | absent | none |
| r4 | 6 GiB RAM + 4 GiB swap | baseline area flow OOM at techmap | absent | none |

The r4 kernel excerpt records total VM `6,535,660 kB`, anonymous RSS
`4,288,984 kB`, and only `200 kB` free swap. The formal CSV contains two rows
whose area/timing numeric cells are empty and whose status is
`not_available_resource_blocked`.

Audit-normalized status: **BLOCKED_RESOURCE**.

### What is not available

| Metric | Status | Reason |
|---|---|---|
| cluster baseline mapped area | `BLOCKED_RESOURCE` | no mapped hierarchy statistic |
| cluster + SMU mapped area | `BLOCKED_RESOURCE` | baseline did not pass techmap |
| incremental/percentage area overhead | `BLOCKED_RESOURCE` | neither matched area exists |
| cluster timing proxy/change | `BLOCKED_RESOURCE` | mapping did not complete |
| cluster Fmax | `UNSUPPORTED` | no Fmax methodology/result |
| cluster power/energy | `NOT MEASURED` | no power flow/data |

Standalone SMU area must not be divided by, added to, or substituted for a missing
cluster mapped area. No cluster-level PPA claim is paper-safe.

Primary files:

- `experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/formal/synthesis_comparison.csv`
- `experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/formal/manifest.json`
- `experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/logs/formal_recovery/r3_manifest.json`
- `experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/logs/formal_recovery/r4_manifest.json`
- `experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/logs/formal_recovery/r3_kernel_oom_excerpt.txt`
- `experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/logs/formal_recovery/r4_kernel_oom_excerpt.txt`
- `experiments/phase6_integrated_cost_generality/report.md`

### Earlier failed synthesis provenance

`experiments/synthesis/p6-stop/` is an earlier full-cluster diagnostic. It passed
front-end elaboration and progressed through process/optimization/memory collection
before a flatten-stage process exited 137. Its generic pre-mapped counts are not
matched cluster PPA. The final official r3/r4 blocker is techmap OOM; these stages
refer to distinct attempts and must not be conflated.
