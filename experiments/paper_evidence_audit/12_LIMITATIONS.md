# Limitations

## Measurement scope

- Formal native performance covers four deterministic shapes and one seed. Phase 7
  and Phase 8 comparisons cover only N8/D32 and N16/D64, one active run per path.
- Native Core excludes allocation, input generation, diagnostics, and Q/K/V loading
  or linear projection. It is not a full Transformer or full end-to-end attention
  layer measurement.
- Cycles come from RTL/Verilator simulation, not silicon.
- N32/D64 has no matched formal result (`NOT MEASURED`).
- No model suite, batch-size sweep, multi-head execution, or multi-seed confidence
  interval is available.

## Numerical scope

- The extended optimized-vs-FP32 stress minimum cosine is 0.999873853; a global
  `>0.9999` claim is unsupported.
- Phase 5/6 native numerical comparisons use deterministic generated references;
  they do not establish downstream model accuracy or training behavior.
- Reciprocal isolation is strong, but the report's attribution of stress error to
  EXP/FP16-max is a root-cause candidate, not a complete formal error decomposition.
- Phase 7 final-O arrays are exact between paths, but intermediate m/l/weight dumps,
  hashes, and MAEs are `NOT MEASURED` in the active recovery records.
- Phase 4 target-side cosine is diagnostic due to approximate target sqrt/reciprocal;
  only host float64 cosine is formal there.

## ISA and control scope

- OMCFG v1 configures only nine fields plus INIT. D, precision/mode, tile size,
  O-buffer addresses, stride, and selector are not runtime cfg IDs.
- OMCFG/OMERGE correctness is not a formal proof and is not validated for concurrent
  multi-core ownership, concurrent MMIO/ISA writes, interrupts, pipeline flushes,
  cancellation, or fault recovery.
- Phase 7 optional no-trace validation is deferred; active formal recovery logs are
  trace-enabled.
- Reserved OMCFG IDs invalidate context in directed tests, but no exhaustive dynamic
  execution test across all 4,086 reserved IDs was run. The full namespace claim is
  decode-collision safety, not functional validation of each reserved word.
- Exact MMIO/ISA/OMCFG equivalence is demonstrated only for two anchors.

## Performance interpretation

- Recurrence/control includes SMU busy. It must not be described as dispatch-only
  latency or as an isolated SMU arithmetic speedup.
- Merge includes recurrence, RVV, and orchestration, but excludes score/local and
  first-tile work. It is not whole attention.
- OMERGE setup-inclusive Native Core gains are 0.841% and 0.448%; larger recurring
  control reductions must not be presented as end-to-end gains.
- OMCFG improves one-time setup by 33.50–35.90%; Phase 8C shows no meaningful
  steady-state gain.
- Small shared-component cycle differences exist between cold simulator runs.
- B2R is matched-arithmetic software+RVV, not demonstrated to be an optimized
  state-of-the-art library implementation.
- Explicit-P results reject uniform Softmax acceleration; SMU benefit is specific
  to the measured native online dataflow.

## PPA scope

- Standalone block area is available; cluster-level area overhead is
  `BLOCKED_RESOURCE`.
- Standalone delay values are pre-layout reg-to-reg proxies from separate mappings,
  not Fmax, STA, post-layout timing, or cluster timing.
- Cluster baseline and SMU synthesis both lack mapped hierarchical statistics after
  OOM at techmap. No area, incremental overhead, timing change, frequency, power,
  or energy result exists.
- Standalone area cannot substitute for missing cluster overhead.
- Phase 3 three-way mixed PPA and historical M2 A1/A2 PPA use different tops/epochs;
  absolute values must not be combined.

## Evidence/provenance scope

- Some artifact manifests contain pre-relocation absolute paths; HEAD updates paths,
  while content hashes remain the authoritative identity.
- Phase 7 required a full recovery because the initial continuation lacked raw
  transcripts. Only recovered raw files are active.
- Phase 8C cosine handling includes a derived exact-vector post-processing correction;
  raw logs remain unchanged.
- The current manuscript is stale relative to Phase 7/8. This dossier audits evidence
  only and deliberately does not edit or rewrite the paper.

## Unsupported claim list

```text
UNSUPPORTED: universal or full-model attention acceleration
UNSUPPORTED: generic row-wise Softmax acceleration
UNSUPPORTED: global cosine > 0.9999
UNSUPPORTED: cluster-level area/Fmax/power/energy overhead
UNSUPPORTED: silicon Fmax, silicon throughput, or post-layout timing
UNSUPPORTED: runtime-adaptive mixed precision
UNSUPPORTED: OMCFG configuration beyond its nine frozen fields
NOT MEASURED: N32/D64 matched performance
NOT MEASURED: Phase 7 intermediate-state equivalence
NOT MEASURED: multihart/concurrency/interrupt/flush behavior
BLOCKED_RESOURCE: matched cluster mapped area and timing proxy
```
