# Phase 4 Ablation: Software Softmax vs Mixed-Precision SMU

## Experiment Motivation

This control experiment isolates the contribution of the Mixed-Precision SMU
inside the already validated quantized-attention path.  The input, quantized
Q/K/V linear layers, Q/K/V requantization, INT8 QK^T, score rescaling, VQ,
P x V, and output scaling are held fixed.  Only the Softmax backend is
replaced.  This separates a Softmax-kernel effect from any change to the
surrounding quantized datapath.

The experiment uses the two existing anchors only: N=8,D=32 and N=16,D=64,
with deterministic seed 1.  No model sweep or full Transformer benchmark is
included.

## Experimental Setup

The two performance paths are:

```
Input -> quantized Q/K/V Linear -> INT8 QK^T -> score rescale
      -> Software Softmax or Mixed-Precision SMU -> P x V -> output scale
```

The target score buffer is key-major, `score[key*N + query]`.  The Software
Softmax reads that exact layout and materializes query-major
`P[query*N + key]`, which is the layout consumed by the unchanged P x V loop.
The `device_compare` build executes both backends on the same score and VQ
buffers and compares the actual device-materialized P and output buffers; it
does not use host-precomputed probabilities.

Both performance backends were built with the same source, compiler/runtime,
seed, simulator, configuration, C flags, root working directory, and a fresh
simulator process per log.  The only backend build define is
`-DPHASE4_SOFTWARE_SOFTMAX` for the control; Mixed uses the default frozen
path.  The direct comparison build uses `-DPHASE4_DEVICE_COMPARE` only for
the numerical cross-check.  All Mixed and device-compare runs emitted exactly
N-1 mode-3 SMU commands and completed successfully; Software emitted no SMU
commands.

Environment evidence:

| Item | Value |
| --- | --- |
| Simulator | `/home/wxt/work-phase4-recip-sim/spatz_cluster.vlt` |
| Simulator SHA256 | `8f85b204d064f1ced29d2fc27518754f8b018db0530cf2328a3a1062687c9138` |
| Cluster config SHA256 | `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775` |
| Profile | `low_perturbation` |
| DASM trace | disabled |
| FSM observer | enabled |
| Seed | 1 |

The final aggregate was generated only from the six current logs in
`experiments/phase4_softmax_ablation/results/system_logs/`.  The older
Phase 4 N16 Mixed log was not used.  The runner rejects logs without the
current backend and Softmax-cycle fields and rejects input paths outside this
experiment's log directory.  The manifest labels these inputs
`fresh_ablation_logs_only`; its command list records the final aggregate/
reparse invocation, not the original fresh log-generation command lines.

## Implementation Difference

The Mixed-Precision SMU implementation, including its EXP/reciprocal LUTs,
precision allocation, FSM, interface, initialization, scalar window, vector
probability update, and swap/clear orchestration, was left unchanged.

The control path performs, for each query, max subtraction over the key-major
score column, exponential evaluation, accumulation, reciprocal normalization,
and row-major P materialization.  The target simulator does not implement
`fdiv.s`; therefore the target reference uses the pre-existing 32-entry
`attnres-baselines` exp2 LUT/interpolation and the existing
`reciprocal_f32` helper.  This is a copied software/reference implementation,
not a new Taylor approximation or Softmax optimization.  No RTL, SMU
datapath, INT8 Linear, quantization, QK^T, score-fusion, or P x V code was
changed.

For performance, Software Softmax cycles cover the complete software
Softmax operation.  Mixed `softmax` equals `smu_total`, covering explicit P
initialization, all SMU launch/poll operations, RVV probability updates, and
swap/clear orchestration.  The narrower `smu_scalar_window` is reported only
as a diagnostic and is not used as the comparison.

## Numerical Results

The formal cosine values below come from the deterministic Software-vs-Mixed
backend vectors recomputed on the host with float64 accumulation and are the
authoritative cosine values.  The direct device run supplies the authoritative
target-buffer MAEs.  Its target-side cosine is retained only as a diagnostic:
`metric_float` uses the target's approximate `sqrt_f32_no_div` and
`reciprocal_f32`, so values close to one must not be used as the formal cosine
claim.

### Formal host recomputation (authoritative cosine)

| Case | Probability MAE | Probability cosine | Attention output MAE | Attention output cosine |
| --- | ---: | ---: | ---: | ---: |
| N8/D32 | 9.01923e-4 | 0.999960077 | 5.22701e-4 | 0.999953092 |
| N16/D64 | 4.74585e-4 | 0.999957064 | 6.14677e-4 | 0.999950108 |

These values compare the deterministic host Software Softmax against the
frozen host Mixed model.  They are stored in `results/numerical.csv`; their
cosines are the formal requested cosine results, while the device MAEs in the
next table remain the direct target-buffer evidence.

### Direct device MAE and target-side cosine diagnostic

| Case | Probability MAE (device) | Probability cosine diagnostic* | Attention output MAE (device) | Attention output cosine diagnostic* | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| N8/D32 | 9.02078e-4 | 1.000000000 | 5.22663e-4 | 0.999999881 | PASS |
| N16/D64 | 4.74481e-4 | 0.999999940 | 6.14540e-4 | 1.000000000 | PASS |

`*` The cosine columns are approximate target diagnostics, not formal cosine
measurements.  The direct device MAE columns remain direct evidence from the
actual device-materialized P/O buffers.  The renamed CSV fields are
`probability_cosine_diagnostic` and `output_cosine_diagnostic`; formal cosine
fields are the unqualified `probability_cosine` and `output_cosine` in
`results/numerical.csv`.

## Performance Results

`Attention Total` below is the arithmetic sum of the five requested stages,
so every row sums exactly to its displayed total:

`QKV Linear + QK^T + Score Scaling + Softmax + P x V`.

It is a comparable stage total, not an independently measured end-to-end
counter.  `Raw total` is the measured full P4 timing window, including input
max-absolute scaling, input quantization, Q/K/V requantization, output
rescaling, and the surrounding timing boundaries.

### Cycle breakdown

| Case | Backend | QKV Linear | QK^T | Score Scaling | Softmax | P x V | Attention Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N8/D32 | Software Softmax | 757440 | 31494 | 1411 | 12502 | 36264 | 839111 |
| N8/D32 | Mixed SMU | 757328 | 31759 | 1429 | 14812 | 36269 | 841597 |
| N16/D64 | Software Softmax | 6129107 | 281354 | 5428 | 48595 | 302903 | 6767387 |
| N16/D64 | Mixed SMU | 6129157 | 281363 | 5441 | 48534 | 303911 | 6768406 |

The measured full-window totals are:

| Case | Software raw total | Mixed raw total | Mixed minus Software | Mixed speedup |
| --- | ---: | ---: | ---: | ---: |
| N8/D32 | 931920 | 934412 | +2492 cycles | -0.267% |
| N16/D64 | 7134015 | 7135062 | +1047 cycles | -0.015% |

Speedup is defined as `1 - Mixed/Software`; positive means Mixed is faster.
At the Softmax stage, N8/D32 changes from 12502 to 14812 cycles, so Mixed is
18.48% slower (`-18.477%`).  N16/D64 changes from 48595 to 48534 cycles,
only a 61-cycle or 0.126% improvement (`+0.126%`).  The corresponding
five-stage totals change by +2486 cycles (-0.296%) and +1019 cycles
(-0.015%), respectively.

For reference, Mixed's complete Softmax-stage breakdown is:

| Case | Scalar SMU window | Probability update | Setup/orchestration | SMU total |
| --- | ---: | ---: | ---: | ---: |
| N8/D32 | 9723 | 2512 | 2577 | 14812 |
| N16/D64 | 24211 | 14144 | 10179 | 48534 |

The QKV Linear stage remains the dominant measured component: approximately
81.3% of Software's raw N8/D32 window and 85.9% of Software's raw N16/D64
window.  Consequently, a Softmax-stage change is expected to have little
effect on the full attention window when the linear layers dominate.

## Conclusion

The numerical replacement claim is supported by the formal host recomputation:
probability cosine is 0.999960077 (N8/D32) and 0.999957064 (N16/D64), while
attention-output cosine is 0.999953092 and 0.999950108, respectively.  The
direct target MAEs are 9.02078e-4/4.74481e-4 for P and
5.22663e-4/6.14540e-4 for the output.  The target-side cosine values are
reported only as approximate diagnostics and are not used for this claim.

The requested uniform performance claim is not supported by these two
anchors.  Mixed SMU is slower by 18.48% at the Softmax stage for N8/D32 and
faster by only 0.126% for N16/D64.  It is slower in the five-stage attention
total and in the full measured window for both anchors.  Therefore this
experiment does not establish that Mixed SMU lowers Softmax execution cost
across the anchor set, and it does not establish broad Attention
end-to-end acceleration.

In particular, no claim of full Transformer acceleration is made.  The
evidence supports numerical consistency of the backend replacement, while
the independent hardware-value/performance claim remains unproven under
this control experiment.

## Limitations

- Only the two existing anchors and one deterministic seed were measured.
- The performance rows use matched cold-start backend ELFs and fresh
  simulator processes.  Small non-Softmax cycle differences are visible in
  QK^T, score scaling, and P x V; the report therefore distinguishes the
  Softmax kernel counter, the arithmetic five-stage sum, and the full raw
  timing window.
- The target Software reference uses the pre-existing LUT-based exp
  implementation required by the simulator's no-`fdiv` constraint, rather
  than host/libm `expf`; the direct device comparison measures the actual
  target buffers.
- Target cosine diagnostics use approximate target sqrt/reciprocal helpers;
  formal cosine values therefore come from the float64 host recomputation in
  `results/numerical.csv`.
- Simulator cycles are not silicon measurements.
- This experiment isolates only the Softmax backend.  It does not benchmark a
  complete Transformer or claim full-model acceleration.

## Reproducibility and Artifacts

The following commands were used for the final quick regeneration and checks.
They re-parse the six already completed fresh logs; they are not the original
log-generation command lines, which were not captured in the final manifest:

```bash
python3 experiments/phase4_softmax_ablation/run_host.py

python3 experiments/phase4_softmax_ablation/run_system.py \
  --simulator /home/wxt/work-phase4-recip-sim/spatz_cluster.vlt \
  --timeout 7200 \
  --reuse-log software:8x32=experiments/phase4_softmax_ablation/results/system_logs/software_N8_D32.log \
  --reuse-log mixed:8x32=experiments/phase4_softmax_ablation/results/system_logs/mixed_N8_D32.log \
  --reuse-log device_compare:8x32=experiments/phase4_softmax_ablation/results/system_logs/device_compare_N8_D32.log \
  --reuse-log software:16x64=experiments/phase4_softmax_ablation/results/system_logs/software_N16_D64.log \
  --reuse-log mixed:16x64=experiments/phase4_softmax_ablation/results/system_logs/mixed_N16_D64.log \
  --reuse-log device_compare:16x64=experiments/phase4_softmax_ablation/results/system_logs/device_compare_N16_D64.log

python3 -m py_compile \
  experiments/phase4_softmax_ablation/run_system.py \
  experiments/phase4_softmax_ablation/run_host.py

install/llvm/bin/llvm-objdump \
  --mcpu=snitch --mattr=a --mattr=v --mattr=m --mattr=zfh -d <each-ablation-ELF>
```

The six target logs were produced with the same runner and fresh simulator
processes; the command above only re-parses those completed logs and
regenerates the aggregate files.  The no-`fdiv` gate passed for all six ELFs.

Results and raw evidence:

- [cycle breakdown](results/cycles.csv)
- [direct device metrics](results/device_numerical.csv)
- [host metrics](results/numerical.csv)
- [host raw results](results/host_results.json)
- [system results](results/system_results.json)
- [system manifest](results/system_manifest.json)
- [system logs](results/system_logs/)
