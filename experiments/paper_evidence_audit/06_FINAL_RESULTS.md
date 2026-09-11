# Final Paper-Eligible Results

All ratios below are derived directly from the cited formal CSV values. Cycle
speedup is baseline/design; reduction is `(baseline-design)/baseline`. Keep result
families separate.

## A. B2R versus final Mixed Scalar SMU + RVV

### Primary anchors

| Shape | Window | B2R cycles | SMU cycles | Speedup | Cycle reduction |
|---|---|---:|---:|---:|---:|
| N8/D32 | recurrence | 12,368 | 1,451 | 8.5238× | 88.268% |
| N8/D32 | merge | 13,204 | 2,318 | 5.6963× | 82.445% |
| N8/D32 | Native Core | 85,262 | 73,706 | 1.1568× | 13.554% |
| N16/D64 | recurrence | 68,994 | 4,926 | 14.0061× | 92.860% |
| N16/D64 | merge | 77,037 | 13,060 | 5.8987× | 83.047% |
| N16/D64 | Native Core | 571,374 | 507,918 | 1.1249× | 11.106% |

The Phase 5 SMU recurrence decomposes into setup+wait `1187+264=1451` cycles
at N8 and `3468+1458=4926` at N16. This is inclusive of control and SMU busy.

### Additional Phase 6 shapes

| Shape | Recurrence (SW/SMU, speedup) | Merge (SW/SMU, speedup) | Native Core (SW/SMU, speedup) |
|---|---|---|---|
| N24/D64 | 165,993 / 9,334, 17.7837× | 186,446 / 29,711, 6.2753× | 1,288,856 / 1,130,764, 1.1398× |
| N16/D128 | 67,451 / 4,910, 13.7375× | 82,220 / 19,841, 4.1439× | 1,026,162 / 962,823, 1.0658× |

Across these four measured shapes: recurrence `8.524–17.784×`, merge
`4.144–6.275×`, Native Core `1.066–1.157×`.

**Claim boundary:** recurrence speedup is not whole-attention speedup. Native Core
also excludes Q/K/V loading/linear projection and diagnostics, so it is not a full
Transformer end-to-end measurement.

Sources: `experiments/phase5_native_online_attention/formal/native_merge_performance.csv`,
`experiments/phase5_native_online_attention/formal/native_attention_performance.csv`, and
`experiments/phase6_integrated_cost_generality/p0_2_workload_generality/formal/performance.csv`.

## B. A1-MMIO versus A1-ISA / OMERGE

| Shape | Path | Setup | Recurrence/control | Engine busy | RVV | Merge | Native Core | Setup-inclusive |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| N8/D32 | A1-MMIO | 0* | 2,069 | 808 | 808 | 2,926 | 74,392 | 74,392 |
| N8/D32 | A1-ISA | 869 | 848 | 808 | 800 | 1,706 | 72,897 | 73,766 |
| N16/D64 | A1-MMIO | 0* | 8,429 | 4,852 | 7,942 | 16,548 | 510,991 | 510,991 |
| N16/D64 | A1-ISA | 907 | 4,929 | 4,848 | 7,813 | 12,915 | 507,795 | 508,702 |

`*` Phase 7 MMIO has zero separate workload-setup bucket because its programming is
inside every recurring control window; it does not mean zero MMIO cost.

| Shape | Control reduction / speedup | Merge reduction | Native Core reduction | Setup-inclusive reduction | Residual control above engine busy (MMIO→ISA) |
|---|---|---|---|---|---|
| N8/D32 | 59.014% / 2.440× | 41.695% | 2.010% | 0.841% | 1,261→40 cycles |
| N16/D64 | 41.523% / 1.710× | 21.954% | 0.625% | 0.448% | 3,577→81 cycles |

The residual is `recurrence/control − engine_busy`, not a separately instrumented
pipeline event. The OMERGE path emitted one command/toggle for N8 and three for
N16, sequences `0→1` and `0→1→0→1`, with matching start/done counts, zero errors,
and zero timeouts.

Final-O equivalence:

| Shape | MMIO hash | ISA hash | Exact words | Pairwise MAE / stable rel / cosine |
|---|---|---|---|---|
| N8/D32 | `0x9c7cdedc` | `0x9c7cdedc` | yes | 0 / 0 / 1 |
| N16/D64 | `0xfd0d2cff` | `0xfd0d2cff` | yes | 0 / 0 / 1 |

**Interpretation:** A1-MMIO → A1-ISA isolates recurring invocation/control benefit
around the same SMU arithmetic and RVV update. It does not isolate SMU computation
because both windows include the engine busy interval.

Sources: `experiments/phase7_omerge_instruction/formal/performance.csv`,
`experiments/phase7_omerge_instruction/formal/numerical_agreement.csv`,
`experiments/phase7_omerge_instruction/formal/selector_audit.csv`, and the four
exact raw paths listed in `11_PROVENANCE.md`.

## C. MMIO-config versus OMCFG-config

| Shape | Config path | Setup | Native Core | Setup+Core | RVV | Merge | OMERGE/start/done/toggle | Config commands |
|---|---|---:|---:|---:|---:|---:|---|---|
| N8/D32 | MMIO | 991 | 72,636 | 73,627 | 808 | 1,694 | 1/1/1/1 | 9 writes + 1 INIT |
| N8/D32 | OMCFG | 659 | 72,636 | 73,295 | 808 | 1,694 | 1/1/1/1 | 10 OMCFG incl. INIT |
| N16/D64 | MMIO | 986 | 507,464 | 508,450 | 7,905 | 13,013 | 3/3/3/3 | 9 writes + 1 INIT |
| N16/D64 | OMCFG | 632 | 507,476 | 508,108 | 7,875 | 12,983 | 3/3/3/3 | 10 OMCFG incl. INIT |

Setup reductions are `332` cycles / `33.50%` at N8 and `354` cycles /
`35.90%` at N16. N8 Native Core is exactly equal; N16 differs by +12 cycles
(+0.0024%) for OMCFG. No steady-state performance benefit is claimed.

Both shapes have exact configuration-state equality (`cfg_valid=1`, selector 0
after INIT, all nine fields) and exact final-O equality:

| Shape | Config-state SHA-256 | Output words | Output hash | Pairwise correctness |
|---|---|---:|---|---|
| N8/D32 | `31a112541234a811901899f55413724b33811aac8b09921b7082a0bb3762a89a` | 256 | `0x9c7cdedc` | MAE 0, stable rel 0, cosine 1, nonfinite 0 |
| N16/D64 | `9d07df611b831de36d6e0811b9a78c218923fe2e5f46205992d1f71feadcfd24` | 1,024 | `0xfd0d2cff` | same |

The matched MMIO/OMCFG binaries have byte-identical `.text` within each shape and
accept different runtime addresses/N values without rebuilding the RTL or simulator.
This supports runtime configurability for the nine-field v1 namespace only.

Sources: `experiments/phase8c_omcfg_runtime/matched_results.csv`,
`experiments/phase8c_omcfg_runtime/correctness.md`,
`experiments/phase8c_omcfg_runtime/setup_overhead.md`,
`experiments/phase8c_omcfg_runtime/runtime_configurability.md`,
`experiments/phase8c_omcfg_runtime/manifest.json`, and the four exact raw paths
listed in `11_PROVENANCE.md`.

## D. Mixed-precision numerical results

| Evidence | Metric | Final value |
|---|---|---:|
| Native, N8/D32 | MAE / stable rel / cosine | 2.793084e-4 / 4.884280e-3 / 0.999984541 |
| Native, N16/D64 | MAE / stable rel / cosine | 4.665494e-4 / 7.052819e-3 / 0.999970724 |
| Native, N24/D64 | MAE / stable rel / cosine | 3.736880e-4 / 6.109509e-3 / 0.999980879 |
| Native, N16/D128 | MAE / stable rel / cosine | 5.631592e-4 / 5.219446e-3 / 0.999984751 |
| reciprocal exhaustive FP16 domain | max relative error | 6.696582e-5 |
| reciprocal 257-point probe | max relative error | 7.297017e-5 |
| extended optimized-vs-FP32 stress | minimum cosine | **0.999873853** |

No native result has a nonfinite output. The stress minimum prevents a global
`cosine > 0.9999` claim. Phase 3 attributes the dominant candidate error to the
existing Mixed EXP/FP16-max path, not the reciprocal approximation in isolation.

## E. Standalone SMU PPA

### Area mapping (three identical trials)

| Design | Mapped cells | Mapped area | Reduction vs Legacy |
|---|---:|---:|---:|
| Legacy scalar | 69,012 | 72,399.082 | — |
| Mixed + Division | 47,141 | 52,000.074 | 28.176% |
| Mixed + Reciprocal | 48,418 | 52,407.586 | 27.613% |

Mixed+Reciprocal is 0.784% larger than Mixed+Division in this area flow.

### Timing proxy (separate timing mapping; three identical values)

| Design | reg-to-reg proxy | Change vs Legacy | Status |
|---|---:|---:|---|
| Legacy scalar | 12,517.79 ps | — | pre-layout proxy |
| Mixed + Division | 14,619.73 ps | +16.792% | target not met |
| Mixed + Reciprocal | 15,539.55 ps | +24.140% | target not met |

Mixed+Reciprocal is 6.292% longer than Mixed+Division in this proxy. These values
are **not Fmax**, are not post-layout timing, and are not cluster timing. Do not use
the mapped areas from the separate timing run as the area table.

Sources: `experiments/phase3_reciprocal_hardware/area/area_trials.csv`,
`experiments/phase3_reciprocal_hardware/timing/timing_trials.csv`, and
`experiments/phase3_reciprocal_hardware/report.md`.

## Separate historical final evidence (not the current main table)

The M2/TCAS-II final workload file reports:

| Workload | N/D | B2R | legacy A1 | Full SMU/A2 | B2R/A1 | B2R/A2 |
|---|---|---:|---:|---:|---:|---:|
| BERT | 12/64 | 19,856 | 4,128 | 7,704 | 4.8101× | 2.5774× |
| Mistral | 32/128 | 56,296 | 12,866 | 34,728 | 4.3756× | 1.6211× |
| Qwen14B | 40/128 | 69,348 | 15,733 | 43,206 | 4.4078× | 1.6051× |
| geometric mean | — | — | — | — | 4.526920× | 1.885766× |

Its standalone A1/A2 area is `77,103.292`/`114,713.298` units. These values
remain frozen for that evidence epoch but predate the final Mixed OMERGE/OMCFG
architecture and are excluded from the primary result claims above.
