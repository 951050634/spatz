# Phase 4 quantized-attention system report

This report records the seed-1 N8/D32 and N16/D64 system anchors.  Host
numerical-model metrics are kept separate from target integration witnesses.
The target cosine fields are diagnostics only, and no speedup or throughput
claim is made from the simulator cycle counts.

## 1. Final Data Path

The exercised path is:

```text
FP32 X -> INT8 X quantization -> three INT8 Q/K/V linear kernels
      -> propagated scale + INT8 requantization -> key-major INT8 QK
      -> score rescale -> explicit one-hot P tiles
      -> Frozen Mixed scalar SMU mode 3 -> independent P update
      -> independent P x V accumulation -> output rescale
```

For each key, P is explicitly materialized as an N x N probability tile.  The
SMU returns the old/tile merge weights, and the probability update then writes
the next P tile.  The P x V loop consumes this materialized P separately; its
cycles are reported in the `pv` field and are not hidden in `smu_total`.

No RTL file was modified for this path.  The existing Scalar SMU interface is
used with the reciprocal low-perturbation simulator configuration.

## 2. Quantization Scheme and Table 1

The symmetric INT8 convention is `[-127, 127]`, with round-to-nearest-even
and a max-absolute scale.  The software and target use the following staged
representation; scale products are propagated rather than recomputed from
FP32 tensors.

**Table 1 — quantization and scale convention.**

| stage | representation | scale / operation | real-domain interpretation |
|---|---|---|---|
| X | `xq : int8` | `sX = max(abs(X))/127`; `xq = RNE(X/sX)` | `X ~= sX*xq` |
| weights | `wq : int8` | `sW = max(abs(W))/127`; `wq = RNE(W/sW)` | `W ~= sW*wq` |
| Q/K/V accumulator | `a : int32` | `a = xq @ wq` | `XW ~= (sX*sW)*a` |
| Q/K/V requant | `q : int8` | `b=sX*sW`; `sQ=b*max(abs(a))/127`; `q=RNE(127*a/max(abs(a)))` | `XW ~= sQ*q` |
| score | `score : FP32` | `sScore=sQ*sK/sqrt(D)`; `score=sScore*(q@k^T)` | scaled attention score |
| P and O | FP32 buffers | Frozen Mixed recurrence, then `P@V` and `*sV` | explicit P and output |

Zero accumulators preserve the base scale and produce zero INT8 output.
The target's reciprocal helper implements the required divisions without
emitting `fdiv.s` or `fdiv.d`.

## 3. Cross-Layer Scale Fusion

For each projection `i in {Q,K,V}`:

```text
b_i    = sX * sWi
a_i    = int32(xq @ wqi)
s_i    = b_i * max(abs(a_i)) / 127
qi     = RNE(127 * a_i / max(abs(a_i)))
sScore = sQ * sK / sqrt(D)
```

The fused score path evaluates `int32(q@k^T) * sScore`.  The staged
checkpoint evaluates `(q*sQ) @ (k*sK)^T / sqrt(D)`.  This is a host FP32
checkpoint, not a target cosine claim.

| anchor | fused-vs-staged MAE | stable-relative error | cosine |
|---|---:|---:|---:|
| N8/D32 | 6.14818e-9 | 1.14923e-7 | 0.999999999999993 |
| N16/D64 | 1.42222e-8 | 1.56978e-7 | 0.999999999999983 |

The external SMU carrier is FP32 TCDM: `m_old`, `l_old`, `O_old`, `m_tile`,
`l_tile`, and `O_tile` are FP32 pointers, with FP32 output pointers and row
stride.  No software FP16 buffer is inserted at this boundary.  At the mode-3
entry, the existing engine applies its Frozen FP16-input semantics internally;
the scalar merge and weight writeback then use the Mixed FP16/internal
fixed-point representation.  Old/tile weights are formed through the
reciprocal path, widened to FP32 for the TCDM destinations, and consumed by
software.  This is the existing external interface carrying the FP16-input
semantic, not a strict-FP32-softmax claim.

**Table 3 — propagated scales (decoded from the target records).**

| anchor | sX | sWQ | sWK | sWV | sQ | sK | sV | sScore |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| N8/D32 | 3.936512e-3 | 1.967943e-3 | 1.963737e-3 | 1.967509e-3 | 5.218987e-3 | 6.560995e-3 | 5.062687e-3 | 6.053144e-6 |
| N16/D64 | 3.936512e-3 | 1.968340e-3 | 1.968388e-3 | 1.968480e-3 | 9.366893e-3 | 9.065356e-3 | 1.195473e-2 | 1.061428e-5 |

## 4. Software / RISC-V Implementation

The Phase 4 C benchmark intentionally keeps the INT8 linear kernels and the
P x V accumulation as explicit target-side loops.  `probability_update` calls
the existing `online_merge_rvv_update` function, whose disassembly contains
the VLA `vsetvli`, vector loads, FP32 vector multiply/FMA, and vector store.
The P x V loop itself is a scalar FP32 accumulation on the RISC-V target; it
is not mislabeled as an RVV kernel.

The software writes mode 3 before every launch, clears DONE, starts the
existing peripheral, polls BUSY/DONE, and reads FP32 old/tile weights.  The
one-hot P tiles and key-major score layout make the explicit P boundary
visible.  `PRINTF_DISABLE_SUPPORT_FLOAT` is used, and all reported target
floating-point values are IEEE-754 bit fields decoded by the runner.

## 5. Numerical Results and Error Ledger

### Host paper metrics (Table 2)

These are the complete REF/B-Q/P-QM rows from
[`numerical.csv`](results/numerical.csv).  P is the softmax probability matrix
and all values compare the host path with the host FP32 reference.  Output
MAE is in the real output domain.

**Table 2 — host numerical results.**

| anchor | baseline | score cosine | softmax/P cosine | output cosine | output MAE |
|---|---|---:|---:|---:|---:|
| N8/D32 | REF | 1.000000000 | 1.000000000 | 1.000000000 | 0 |
| N8/D32 | B-Q | 0.999943487 | 0.999999755 | 0.999941232 | 6.302641e-4 |
| N8/D32 | P-QM | 0.999943487 | 0.999959389 | 0.999880377 | 8.859690e-4 |
| N16/D64 | REF | 1.000000000 | 1.000000000 | 1.000000000 | 0 |
| N16/D64 | B-Q | 0.999904443 | 0.999998886 | 0.999910746 | 8.015677e-4 |
| N16/D64 | P-QM | 0.999904443 | 0.999954645 | 0.999861672 | 1.023347e-3 |

For context, P-QM stable-relative errors for score/P/output are respectively
1.094303%/0.730764%/1.549283% at N8 and
1.366164%/0.779591%/1.546999% at N16.  These are the formal host paper
metrics; target approximate cosine values are not used in their place.

### Host Q/K/V linear quality

**Table 2a — host dequantized Q/K/V linear metrics.**

| anchor | tensor | MAE | cosine | INT8 saturation |
|---|---|---:|---:|---:|
| N8/D32 | Q | 1.557391e-3 | 0.999970068 | 1/256 (0.390625%) |
| N8/D32 | K | 1.852605e-3 | 0.999960156 | 1/256 (0.390625%) |
| N8/D32 | V | 1.573655e-3 | 0.999962201 | 1/256 (0.390625%) |
| N16/D64 | Q | 2.695191e-3 | 0.999956296 | 1/1024 (0.097656%) |
| N16/D64 | K | 2.697348e-3 | 0.999952602 | 1/1024 (0.097656%) |
| N16/D64 | V | 3.247156e-3 | 0.999933127 | 1/1024 (0.097656%) |

### Device integration / transport witness (not Error C)

The target compares its materialized P and O against host Mixed bit arrays.
The actual `main.c` integration gate requires target cosine `>=0.999` and
stable-relative error `<0.01` for both P and O.  MAE is reported for context
only; it is not a gate predicate.  The target cosine field is therefore a
gate diagnostic, while the host paper cosine remains the formal numerical
metric.

| anchor | P target MAE | P stable-rel. | O target MAE | O stable-rel. | P4 status |
|---|---:|---:|---:|---:|---|
| N8/D32 | 0.0 | 0.0 | 6.01665e-9 | 1.04861e-7 | PASS |
| N16/D64 | 0.0 | 0.0 | 6.65934e-9 | 1.00718e-7 | PASS |

### Error A / Error B / Error C

- **Error A — B-Q versus REF.**  This is the low-precision Q/K/V linear
  quantization and reference-softmax error: INT8 rounding, accumulator
  requantization, and B-Q softmax are compared directly with host FP32 REF.
  The complete B-Q values are in Table 2; this is not the device transport
  witness.
- **Error B — FP32-input Mixed versus FP32.**  This is the Frozen Mixed
  normalization approximation measured in the Phase 3 single-head QK^T V
  study: softmax stable-relative error `1.198e-2` with cosine `0.999935136`,
  and attention stable-relative error `1.047e-2` with cosine `0.999946578`.
  The Phase 3 report is the source; Phase 4 does not rerun this experiment.
  Within that Phase 3 study, the reciprocal-vs-divider incremental attention
  error was `2.540e-4`, which must not be confused with the full
  Mixed-vs-FP32 error.  See
  [`Phase 3 single-head reciprocal model report`](../phase1_online_softmax/results/phase3_reciprocal_model/report.md).
- **Error C — P-QM versus REF final combined output.**  This is the final
  quantized-plus-Frozen-Mixed host result: output stable-relative error is
  `1.549283%` (cosine `0.999880377`) at N8 and `1.546999%` (cosine
  `0.999861672`) at N16.  The device-vs-host-Mixed values above are a separate
  integration/transport witness and are not Error C.

## 6. Cycle Breakdown and Table 4

All entries are target cycle-counter deltas.  `total` starts immediately after
`load_input()` and therefore denotes the input-resident compute interval; it
excludes allocation and the initial X transfer.  `smu_total` is shown as
`scalar-window / probability-update / setup-orchestration` and the three
subfields sum to it.  `dynamic_quant_overhead` is exactly
`quantize_x + qkv_requant`.

**Table 4 — end-to-end cycle accounting and requested dynamic fields.**

| anchor | X maxabs/scale cycles | x quant | Q requant | K requant | V requant | quantize_x | QKV linear | QKV requant | QKᵀ | score rescale | SMU (S/U/setup) | P x V | output rescale | total | dynamic overhead |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N8/D32 | 3,129 | 17,198 | 23,081 | 23,046 | 22,845 | 20,327 | 757,328 | 68,972 | 31,757 | 1,436 | 14,629 (9,693/2,446/2,490) | 36,272 | 3,383 | 934,272 | 89,299 (9.558%) |
| N16/D64 | 11,309 | 68,290 | 90,847 | 90,813 | 90,859 | 79,599 | 6,129,157 | 272,519 | 281,354 | 5,432 | 48,493 (24,193/14,127/10,173) | 303,911 | 14,393 | 7,135,023 | 352,118 (4.935%) |

The complete machine-readable version is
[`cycles.csv`](results/cycles.csv).  The largest component is QKV linear:
81.061% of total at N8 and 85.902% at N16.  Dynamic quantization overhead is
9.558% and 4.935%; SMU is 1.566% and 0.680%.  These are bottleneck shares,
not speedup measurements.

The reciprocal FSM witness is:

| anchor | SMU commands | mode / presented N,D | compute_weight per invocation | terminal states |
|---|---:|---|---:|---|
| N8/D32 | 7/7 done | mode 3, 8/8 | 24 | 7 x DONE |
| N16/D64 | 15/15 done | mode 3, 16/16 | 48 | 15 x DONE |

Both logs report `profile=low_perturbation`, `dasm_trace_enabled=false`,
`fsm_observer_enabled=true`, zero errors, and zero timeouts.  The 24/48
compute-weight values scale as 3N and are reciprocal-path evidence rather
than division-path values.

## 7. Main Findings: five questions answered

1. **Q1 — Can low-precision linear feed Frozen Mixed directly?**  Yes for
   these anchors: INT8 Q/K/V plus propagated scales feed key-major scores and
   the existing FP32 TCDM SMU carrier; the mode-3 P/O integration witness is
   below `1.1e-7` stable-relative error against host Mixed.
2. **Q2 — Does scale fusion preserve the staged score?**  Yes: fused-vs-
   staged stable-relative errors are `1.14923e-7` and `1.56978e-7`.
3. **Q3 — Is dynamic per-tensor quantization sufficient?**  It is sufficient
   for the bounded two-anchor integration gate and keeps host cosines high,
   but it does not remove the final host output error; P-QM output
   stable-relative error remains about 1.55%.
4. **Q4 — Is the combined output acceptable?**  Cosines exceed `0.999`
   (`0.999880377`/`0.999861672`), but stable-relative error is slightly above
   the 1.5% preference (`1.549283%`/`1.546999%`).  This is acceptable as an
   explicitly bounded exploratory result, not as a claim of exact FP32
   softmax.
5. **Q5 — Is the complete RISC-V scheduling path exercised?**  Yes: mode-3
   peripheral launches, reciprocal FSM waits, RVV probability updates,
   scalar FP32 P x V accumulation, explicit P materialization, separate cycle
   fields, and no-fdiv objdump gates all ran at both anchors.  This does not
   imply a speedup claim.

## 8. Current Bottleneck

The measured bottleneck is the scalar INT8 QKV implementation, not the Scalar
SMU: QKV consumes 81.061%/85.902%, while SMU consumes 1.566%/0.680% for
N8/N16.  P x V is 3.882%/4.259%.  The next optimization question is therefore
QKV/P x V implementation and memory traffic, not claiming a larger SMU
speedup from these measurements.  Phase 3 also reports that the reciprocal
Mixed implementation's post-synthesis timing proxy was 6.29% worse than its
division counterpart; Phase 4 does not overturn that result.

## 9. Paper-Supported Claims

Sol Gate2 status: **GO / VERIFIED**; no P0/P1 blockers remain for this
snapshot.

Supported by this Phase 4 evidence:

- the complete quantized linear, scale propagation, key-major QK, explicit-P,
  Frozen Mixed mode-3, independent P update, and independent P x V path runs
  at both requested anchors;
- host P-QM numerical values in Table 2 and Q/K/V values in Table 2a;
- fused-vs-staged scale arithmetic agrees to approximately `1e-7` stable
  relative error in the two host checkpoints;
- target P/O integration against host Mixed passes the `<1%` witness gate;
- the reciprocal low-perturbation FSM configuration is visible in the raw
  logs and has no DASM trace or RTL modification.

Not supported by this report:

- an end-to-end speedup, throughput improvement, or energy result;
- strict FP32 softmax accuracy for mode 3;
- universal accuracy across shapes, seeds, stress inputs, or multi-trial
  paper-frozen builds;
- a reciprocal critical-path/timing improvement (Phase 3 explicitly does not
  support that claim).

## 10. Blocked / Deferred

- The clean final two-anchor measurement has been completed at implementation
  commit `ad7cf8b5476d8eeeed026a7a2c1431965568e970`.  The simulator started
  from a clean worktree; the runner's manifest records `git_dirty=true`
  because it checks status after writing tracked CSV outputs with its default
  CRLF terminator.  Those CSVs were normalized back to LF and their contents
  match the implementation snapshot.  Multi-trial confirmation and a
  larger-shape sweep remain deferred because they are not required for this
  Phase 4 snapshot.
- Error B stress behavior remains a Phase 3 limitation and needs a dedicated
  future numerical study; no new Phase 4 stress claim is made.
- QKV and P x V are not optimized or fused in this experiment.  P is
  intentionally materialized and P x V is intentionally independent so that
  the cross-layer boundary is auditable.
- Physical timing/area closure remains a Phase 3 follow-up, not a conclusion
  from these Verilator cycles.

## 11. Reproducibility and cleanup

Software was built externally at `/home/wxt/work-phase4-sw/N8_D32` and
`/home/wxt/work-phase4-sw/N16_D64` with `-DPRINTF_DISABLE_SUPPORT_FLOAT`.
TCDM checks passed before N16 launch: N8 footprint 25,216/131,072 bytes and
N16 footprint 50,816/131,072 bytes (including the 16,512-byte runtime
reservation).  The no-`fdiv` objdump gate passed for both ELFs.

The reciprocal simulator was built externally with both required defines:

```text
make -C /home/wxt/work-online-merge-supplement/hw/system/spatz_cluster \
  VLT_BUILDDIR=/home/wxt/work-phase4-recip-vlt \
  VLT_BIN=/home/wxt/work-phase4-recip-sim/spatz_cluster.vlt \
  DEFS='-DSPATZ_DISABLE_DASM -DONLINE_MERGE_MIXED_RECIPROCAL' \
  /home/wxt/work-phase4-recip-sim/spatz_cluster.vlt
```

Simulator SHA256 is
`8f85b204d064f1ced29d2fc27518754f8b018db0530cf2328a3a1062687c9138`.
The final measurement was a no-reuse two-anchor simulator run from the clean
implementation snapshot.  It rebuilt and ran both standard logs, then wrote
the final manifest with measurement commit
`ad7cf8b5476d8eeeed026a7a2c1431965568e970`.  The manifest's
`git_dirty=true` is the runner's post-output observation described in Section
10; the simulator launch itself occurred at the clean implementation
snapshot:

```text
python3 experiments/phase4_quantized_attention/run_system.py \
  --case 8x32 --case 16x64 \
  --simulator /home/wxt/work-phase4-recip-sim/spatz_cluster.vlt \
  --timeout 7200
```

No additional simulator rerun is required after this final command.  The two
raw logs are archived as `results/system_logs/N8_D32.log` and
`results/system_logs/N16_D64.log`; the manifest command list contains no
`reuse-log` entry.

ELF SHA256 values are N8/D32
`93760cf287b3d4eb4f57b0f9057c86b65d79f9dd340d04495459b2a79868c28c` and
N16/D64
`5b9a3f28a7461650708d1bf26e53ee8374bf3b2ee6d3dec65c156f5ed7d86c49`.
The repository-generated `sw/build-phase4` tree and Phase 4 Python
`__pycache__` were removed after validation; external builds were retained so
the manifest hashes remain inspectable.

## 12. Artifacts

- [`run_system.py`](run_system.py) — minimal external build/run/parser driver.
- [`system_results.json`](results/system_results.json) — decoded P4/FSM/config records.
- [`cycles.csv`](results/cycles.csv) — required cycle fields and aggregation.
- [`device_accuracy.csv`](results/device_accuracy.csv) — target MAE/stable-relative witness.
- [`device_scales.csv`](results/device_scales.csv) — decoded scales and max-absolute values.
- [`system_manifest.json`](results/system_manifest.json) — seed, commit/dirty state, hashes, and commands.
- [`N8_D32.log`](results/system_logs/N8_D32.log) and
  [`N16_D64.log`](results/system_logs/N16_D64.log) — raw system logs.
