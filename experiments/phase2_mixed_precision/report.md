# Phase-2 fixed-role pruning smoke

This directory contains only the new Phase-2 smoke evidence.  The historical
`area_trials.json`/`.csv` row is retained as a diagnostic, explicitly marked
`INVALID_DIAGNOSTIC_latched_mode_not_pruned`; it is not a formal area result.

## RTL correction

`online_merge_update_engine` keeps the default `ScalarOnly=0` runtime behavior.
The C1, legacy-scalar, mixed-scalar, and dual-scalar mapped tops pass
`ScalarOnly=1`; full tops and the cluster use the default.  The STORE completion
bound and the `UPDATE_VECTOR`/`RD_O_*` logic are constant-guarded, allowing the
vector O datapath and state to be removed at elaboration.  `elab_guarded/` is the
clean evidence set: all three scalar netlists have no `elem_q`, `o_old_q`,
`o_tile_q`, or `o_new_q`, while `LEGACY_FULL` retains them.

## Corrected one-trial area smoke

The flow uses the pinned Yosys/Slang executable
`/home/wxt/yosys-sta/oss-cad-suite/bin/yosys` and
`Nangate45_typ.lib` from `/home/wxt/yosys-sta/pdk/nangate45/lib/`.

| role | status | area (um2) | mapped cells | sequential area (um2) | elapsed |
| --- | --- | ---: | ---: | ---: | ---: |
| LEGACY_SCALAR | PASS | 77,047.964 | 73,549 | 2,766.4 | 41.0 s |
| MIXED_SCALAR_ONLY | PASS (smoke) | 230,951.574 | 221,941 | 3,521.84 | 415.2 s |

Commands (run sequentially, with a 600 s outer limit):

```text
PYTHONDONTWRITEBYTECODE=1 python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage elab --trial-start 1 --trial-end 1 --timeout-s 300 --work-root /tmp/om_phase2_fixed_role_elab_guarded --result-dir experiments/phase2_mixed_precision/elab_guarded
timeout 600s env PYTHONDONTWRITEBYTECODE=1 python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage area --trial-start 1 --trial-end 1 --timeout-s 1200 --work-root /tmp/om_phase2_fixed_role_area_corrected --result-dir experiments/phase2_mixed_precision/corrected_area --role LEGACY_SCALAR
timeout 600s env PYTHONDONTWRITEBYTECODE=1 python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage area --trial-start 1 --trial-end 1 --timeout-s 1200 --work-root /tmp/om_phase2_fixed_role_area_corrected --result-dir experiments/phase2_mixed_precision/corrected_area --role MIXED_SCALAR_ONLY
```

Mixed is intentionally not expanded to dual/full or repeated trials: its
shared 35-iteration restoring binary16 divider/normalization path is the
dominant structural cost (ABC peak memory was about 1.95 GB), and this smoke is
already 3.00x the corrected legacy area.  This is a lower-bound diagnostic,
not a claim about a completed dual deployment point.

## Focused simulation

All existing focused tests passed after the correction:

* `online_merge_approx_tb` — legacy approximation checks.
* `online_merge_mixed_tb` — binary16 conversion, divider, and LUT checks.
* `online_merge_engine_mixed_tb` — mode latch and exact mode 0/1/2/3 vectors.
* `online_merge_precision_support_tb` — legal/illegal PrecisionSupport modes.

The Verilator builds used `/home/wxt/yosys-sta/oss-cad-suite/bin/verilator`
with `--binary --timing --Wno-fatal`; build directories are under
`/tmp/om_phase2_scalar_tb_*_20260823`.

No formal multi-trial area, timing, or power result is claimed in this smoke.

## Fused ordered-FP16 delta direction (single area smoke)

Sol P2 approved the ordered finite FP16 loser/winner to LUT-address fusion
direction.  The fused module first preserves the existing FP16 subtraction
RNE/address and saturation semantics, then selects the same single 256-entry
ROM; the focused miter covered 1,158,722 structured and signed-random pairs
and the frozen mixed engine vector remained bit-exact with 78
`COMPUTE_WEIGHT` cycles.  This section is a directional one-trial smoke, not
a formal three-trial characterization.

Command:

```text
timeout 600s python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage area --trial-start 1 --trial-end 1 --timeout-s 1200 --role MIXED_SCALAR_ONLY --result-dir experiments/phase2_mixed_precision/fused_delta_area --work-root /tmp/om_phase2_fused_delta_area_20260823
```

| role / comparison | status | area (um2) | mapped cells | sequential area (um2) | combinational area (um2) | elapsed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MIXED_SCALAR_ONLY, fused | PASS | 55,783.658 | 50,967 | 3,521.840 | 52,261.818 | 40.8 s |
| LEGACY_SCALAR reference (pre-final snapshot) | PASS diagnostic | 77,047.964 | 73,549 | 2,766.400 | 74,281.564 | 41.0 s |
| MIXED_SCALAR_ONLY, prior corrected | PASS diagnostic | 230,951.574 | 221,941 | 3,521.840 | 227,429.734 | 415.2 s |

The fused smoke is 0.724012x legacy area (27.599% lower), 0.241538x the
prior mixed area (75.846% lower), and has 0.692967x the legacy mapped-cell
count.  These ratios are directional because each fused row is one trial;
the prior mixed row remains a pre-fusion diagnostic and is not overwritten.

Pre-ABC/elaboration evidence is consistent with removal of the large
FP16-delta normalization cone: the prior mixed log had two 349-assignment
FP16 arithmetic processes (337 `fp16_add_sub` assignments plus 12 rounding
assignments in each), while the fused log has no `fp16_add_sub` process
occurrence.  The first post-`OPT_MERGE` mixed-top cell hash count fell from
12,090 (prior) to 8,114 (fused).  Fixed-point normalization/divider lowering
still reports the same two `$mul` wrappers (64x64 and 63x72), and mapped
sequential area is unchanged.  Thus the remaining divider/length arithmetic
is still present; this smoke does not claim that it has been optimized.  The
one ROM contract is unchanged.

No dual/full/repeated area trial, timing, or power run was started for this
direction.  Power/energy remain unavailable, and the old narrow-divider
experiment remains a negative diagnostic only.

## Dual scalar gate (single area smoke)

The staged dual gate uses the same scalar-only interface and keeps both
precision implementations available at run time.  It is the deployment-cost
point; `MIXED_SCALAR_ONLY` above is a precision-specialized lower bound.

Command:

```text
timeout 600s python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage area --trial-start 1 --trial-end 1 --timeout-s 1200 --role DUAL_SCALAR --result-dir experiments/phase2_mixed_precision/fused_dual_area --work-root /tmp/om_phase2_fused_dual_area_20260823
```

| role / comparison | status | area (um2) | mapped cells | sequential area (um2) | combinational area (um2) | elapsed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| DUAL_SCALAR | PASS | 117,007.282 | 108,141 | 4,208.120 | 112,799.162 | 68.4 s |
| LEGACY_SCALAR reference | PASS | 77,047.964 | 73,549 | 2,766.400 | 74,281.564 | 41.0 s |
| MIXED_SCALAR_ONLY reference | PASS | 55,783.658 | 50,967 | 3,521.840 | 52,261.818 | 40.8 s |

This diagnostic gate used the earlier corrected legacy reference and is not
a same-snapshot comparison.  The formal three-trial section below supersedes
its legacy-relative ratio.  Against the diagnostic references, the dual
point is 1.518629x legacy area and 2.097519x mixed-only area; it is a single
gate trial and is not a formal three-trial area characterization.

The hierarchy and pre-ABC evidence confirms that both paths survive
elaboration: the dual log retains
`gen_legacy_math.i_old_exp_approx`, `i_tile_exp_approx`, and
`i_recip_approx`, and also retains the fused
`gen_mixed_math.i_mixed_exp_loser` plus
`gen_mixed_math.i_weight_divider`.  The mapped netlist contains the divider
state (`quotient_q`, `remainder_q`, `work_q`) and the fused loser address
logic; the compatibility `online_merge_exp_mixed` module is removed as
unused, leaving the single fused loser-ROM source path rather than a second
ROM instance.

Runtime precision is not constantized in this top.  The wrapper instantiates
`PrecisionSupport=2`, `ScalarOnly=1`, and `RuntimeScalarPrecision=1`, maps
`mode_i` to `{30'd0, cfg_i.mode[1], 1'b1}`, and the mapped netlist shows the
corresponding input bit (`cfg_i[3]`) feeding the latched `use_mixed`/`mode_q`
control.  The dual Yosys FSM log lists `mode_q[1]` as a control input, so
legacy and mixed are both reachable at run time.

No further role, repeat, timing, or power run was started for this gate.

## Formal three-trial area matrix (frozen source snapshot)

The three fixed roles were rerun as deterministic area repeats under one
shared `final_area` result directory and one work root.  All nine trials
passed; each role produced identical mapped netlist/stat artifact hashes and
an identical exact signature across trials.  Only wall-clock elapsed time
varied.

Commands (run sequentially, outer timeout 600 s each):

```text
timeout 600s python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage area --trial-start 1 --trial-end 3 --timeout-s 1200 --role LEGACY_SCALAR --result-dir experiments/phase2_mixed_precision/final_area --work-root /tmp/om_phase2_final_area_20260823
timeout 600s python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage area --trial-start 1 --trial-end 3 --timeout-s 1200 --role MIXED_SCALAR_ONLY --result-dir experiments/phase2_mixed_precision/final_area --work-root /tmp/om_phase2_final_area_20260823
timeout 600s python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage area --trial-start 1 --trial-end 3 --timeout-s 1200 --role DUAL_SCALAR --result-dir experiments/phase2_mixed_precision/final_area --work-root /tmp/om_phase2_final_area_20260823
```

| role | trial elapsed (s) | status | area (um2) | mapped cells | sequential area (um2) | combinational area (um2) | exact signature |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| LEGACY_SCALAR | 33.1 / 32.6 / 39.8 | PASS / PASS / PASS | 77,171.920 | 73,622 | 2,766.400 | 74,405.520 | `8e3e87c0...e66186` |
| MIXED_SCALAR_ONLY | 35.4 / 34.2 / 33.3 | PASS / PASS / PASS | 55,783.658 | 50,967 | 3,521.840 | 52,261.818 | `cc4d1acc...baf371` |
| DUAL_SCALAR | 62.2 / 67.9 / 63.2 | PASS / PASS / PASS | 117,007.282 | 108,141 | 4,208.120 | 112,799.162 | `78d4cad6...461a25` |

All figures in this section use the same final snapshot recorded in
`final_area/area_manifest.json` (Yosys 0.66+4, Nangate45 typical Liberty,
source SHA-256 entries intact).  The full 64-character signatures and all
artifact hashes are in `final_area/area_trials.json` and `.csv`.

Using the formal repeated means (which equal every trial here), mixed-only is
0.722849x legacy area, a 27.715% reduction.  Dual is 1.516190x legacy area,
or 51.619% overhead.  The two specialized areas sum to 132,955.578 um2;
dual is 0.880048x that sum.  Equivalently, sharing avoids 15,948.296 um2,
or 11.995% of the two-specialized sum.  For clarity, mixed-only remains the
specialized lower bound while dual is the runtime deployment point.

This is a formal three-trial area result only.  No timing, power, energy, or
additional role is implied by this section.

## Formal timing proxy (one trial per role, common `-D1500` target)

Timing was run once for each fixed role against the same 1500 ps ABC delay
target.  A runner `PASS` means the mapping completed; all three
`target_met` fields are false because the reported delays exceed 1500 ps.
Each result contains five non-empty `critical_path_lines` entries, and the
Yosys logs contain the corresponding `ABC: Path` traces.

Command (roles run serially):

```text
timeout 600s python3 experiments/phase2_mixed_precision/run_fixed_role_synthesis.py --stage timing --trial-start 1 --trial-end 1 --timeout-s 1200 --role LEGACY_SCALAR --role MIXED_SCALAR_ONLY --role DUAL_SCALAR --result-dir experiments/phase2_mixed_precision/final_timing --work-root /tmp/om_phase2_final_timing_20260823
```

| role | status | elapsed | critical delay (ps) | target (ps) | target_met | timing-map area (um2) |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| LEGACY_SCALAR | PASS | 83.5 s | 13,657.7 | 1,500 | false | 67,122.972 |
| MIXED_SCALAR_ONLY | PASS | 58.6 s | 16,531.92 | 1,500 | false | 37,001.664 |
| DUAL_SCALAR | PASS | 161.8 s | 16,780.43 | 1,500 | false | 95,060.686 |

Relative to LEGACY_SCALAR, MIXED_SCALAR_ONLY has a +21.045% critical-delay
proxy (16,531.92 ps versus 13,657.7 ps).  This is only the common-target,
pre-layout ABC reg-to-reg combinational proxy described below; it is not an
Fmax or cluster timing result.

The area column above is the area of the timing-mapped netlist and must not
be mixed with the formal area matrix.  The flow is a pre-layout ABC
reg-to-reg combinational-delay proxy with no clock definition, setup/hold,
skew, IO-delay, output-load, routing, or cluster timing constraints.  It is
therefore not an Fmax claim and not a synchronous cluster-timing result.
Power and energy remain unavailable.  Full 64-character signatures,
critical-path traces, and source/tool hashes are in
`final_timing/timing_trials.json` and `timing_manifest.json`.

## Matched legacy-vs-mixed Scalar performance (three canonical cases)

This matrix compares the existing legacy Scalar path (`mode=1`) with the
mixed Scalar path (`mode=3`) using the same generated input, seed, build
configuration, memory counter profile, and one RVV update.  `kernel_cycles` is
the reported `OM_RESULT.cycles_lo`; the policy has no explicit transfer phase,
so `end_to_end_cycles` is intentionally not reported.  The FSM gate checks
both warm-up and measured invocations: `1/1` for legacy and `3/3` for mixed.
`busy` and `weight` are the measured invocation's SMU busy and
`COMPUTE_WEIGHT` cycle counts.

| case | path / mode | kernel cycles | Δ vs legacy | SMU scalar | RVV | busy / weight | max abs | scale-relative max | status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| N1/D1 (smoke) | legacy / 1 | 1,517 | — | 1,376 | 141 | 24 / 1 | 1.252e-6 | 1.252e-6 | PASS |
| N1/D1 (smoke) | mixed / 3 | 1,473 | −2.900% | 1,332 | 141 | 65 / 42 | 9.737e-4 | 2.513e-4 | PASS |
| N8/D32 | legacy / 1 | 2,625 | — | 1,481 | 1,144 | 192 / 8 | 6.032e-4 | 1.474e-4 | PASS |
| N8/D32 | mixed / 3 | 3,171 | +20.800% | 2,027 | 1,144 | 737 / 552 | 7.586e-3 | 3.796e-3 | PASS |
| N16/D64 | legacy / 1 | 5,067 | — | 1,744 | 3,323 | 384 / 16 | 2.594e-4 | 1.619e-4 | PASS |
| N16/D64 | mixed / 3 | 6,061 | +19.617% | 2,738 | 3,323 | 1,474 / 1,104 | 6.297e-3 | 6.051e-3 | PASS |

The mixed policy uses `max(abs(actual-reference))/max(abs(reference),1)` and
allows 0.015 for `A1_MIXED_SCALAR`; the worst observed scale-relative error is
0.006051 (N16/D64), and the worst raw max absolute error is 0.007586
(N8/D32).  All outputs are finite and all correctness/status gates pass.
The RVV portion is identical between paths for each case; mixed therefore
has no speedup on the meaningful N8/N16 cases, with kernel latency increases
of 20.800% and 19.617%.  The formal area matrix's mixed-only result is
27.715% below legacy (55,783.658 versus 77,171.920 um²), so that area result
comes with the measured N8/N16 latency cost.  N1/D1 is retained as a selector
and FSM smoke test, not as a performance claim.  These figures do not imply
Fmax, power, or energy conclusions.

Each case/config was run for three trials.  All trials have identical result
hashes and metrics (`reproducible=YES`), `fairness_gate=PASS`, and
`comparison_set_complete=YES`; the run has 18 records and zero failures.
The worktree was intentionally dirty to preserve the surrounding experiment
state, so the runner marks `paper_eligible=NO` with `DIRTY_WORKTREE`; this is a
directional matched-path result, not a clean-paper eligibility claim.

Successful command:

```text
python3 experiments/scripts/run_performance_matrix.py --repo-root /home/wxt/work-online-merge-supplement --case-file experiments/configs/p0_anchor_cases.json --policy experiments/phase2_mixed_precision/matched_scalar_policy.json --source-dir hw/system/spatz_cluster/sw --cfg hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson --simulator hw/system/spatz_cluster/bin/spatz_cluster.vlt --artifact-root /home/wxt/work-online-merge-phase2-matched-20260823 --build-dir /home/wxt/work-online-merge-phase2-matched-build-20260823 --suite phase2_matched_scalar --case-ids N1_D1_S1_main,N8_D32_S1_main,N16_D64_S1_main --configs A1_SMU_SCALAR,A1_MIXED_SCALAR --profiles memory --trials 3 --jobs 1 --build-timeout-seconds 900 --no-index
```

Run ID: `20260823T153454Z_4d92e822_phase2_matched_scalar`.  The frozen
machine-readable evidence is under
`/home/wxt/work-online-merge-phase2-matched-20260823/`:
`records.json`, `records.csv`, `failures.json`, `run_manifest.json`, and
`artifact_manifest.json`; generated ELFs, logs, and traces are in the same
directory.  The external build directory is
`/home/wxt/work-online-merge-phase2-matched-build-20260823/`.

Manifest identity: case-file SHA-256
`7eb15301d30441c1fc90f7f1bfbf48ad7dca2a935d505ec8e47d30270c5ba77b`, policy
SHA-256 `6adcb8d263fbd52a98ce3317102abb34c1385a8c3412f0be962894fddcf91bc8`,
cluster cfg SHA-256
`120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
simulator SHA-256
`6f227327bda826f2509d0249488df39fdde3001daa7d0ee3b2bb76f3c748c3bd`, and
runner SHA-256
`41e4b8470c7e9a0bb7cee8805afaed7fec3c7e8f98509c60415eab587274732d`.
The source commit was `4d92e82265db7f4496902a4969afe1a598f85624`, and the
verified worktree snapshot was
`e572dbdfb57fe0201b2572b92cf09f9596324b637c0a0f69398ed4de6489cdff`.
