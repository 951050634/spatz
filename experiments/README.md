# Online Softmax Merge Paper Experiments

This directory is the paper-facing entry point for the Spatz online-merge
experiments.  It deliberately reuses the implementation in:

- `sw/spatzBenchmarks/online-softmax-merge/` for target code and inputs;
- `hw/ip/online_merge/` for the SMU RTL;
- `util/online_softmax_merge/` for the established low-level runners and
  analyzers.

The `experiments/scripts/` programs add the publication policy: canonical
configuration names, independent simulator trials, non-overwrite rules,
reproducibility gates, a unified result schema, and paper-eligibility checks.
They do not create duplicate implementations of B1, B2-R, A1, or B3.

## Configuration names

| Canonical name | Target implementation | Meaning |
| --- | --- | --- |
| `B1_SCALAR` | `B1` | Software scalar recurrence and scalar output update |
| `B2R_RVV` | `B2-R` (`A0` alias) | Software recurrence and RVV output update |
| `A1_SMU_SCALAR` | `A1` | SMU recurrence and RVV output update |
| `A2_SMU_FULL` | `B3` (`A2` alias) | Full SMU recurrence and output update |

`EXP_ONLY` is not implemented.  It must remain absent rather than being
represented by software `exp()` or an idealized zero-cost result.

## Raw data policy

Large logs, ELFs, disassemblies, DASM traces, and VCD files stay in a fresh
external directory whose basename starts with `work-online-merge-`.  A small
index in `experiments/raw/<run_id>.json` records the external path and hashes.
Parsed data and plots are reproducible only while every indexed raw artifact
is present and matches its recorded SHA256.

Run IDs have the form:

```text
YYYYMMDDTHHMMSSZ_<git-commit-8>_<suite>
```

Existing IDs and external result directories are never overwritten.

## P0 workflow

Run a bounded smoke test:

```bash
experiments/scripts/run_smoke.sh
```

Capture a new timestamped environment snapshot without changing tools (the
pre-implementation state remains in `PROJECT_STATE.md`):

```bash
python3 experiments/scripts/collect_project_state.py
```

Run formal cases with a low-perturbation measurement simulator and an
independently built DASM-enabled trace-witness simulator.  The runner accepts
the measured cycles only when the first binary reports
`profile=low_perturbation`, DASM disabled, and the FSM observer enabled.  For
each executable B2-R case it runs the second binary once with the identical
ELF and generated input, audits dynamic RVV execution, and requires the
non-timing target-result fields to match the measurement run:

```bash
python3 experiments/scripts/run_performance_matrix.py \
  --case-file experiments/configs/p0_anchor_cases.json \
  --simulator /path/to/low-perturbation/spatz_cluster.vlt \
  --trace-witness-simulator /path/to/traced/spatz_cluster.vlt
```

Case files may provide a path-safe unique `case_id` and one of these evidence
classes: `MAIN_PERFORMANCE`, `MODEL_WORKLOAD`, `FUNCTIONAL_BOUNDARY`,
`CAPACITY_PROBE`, or `OPTIONAL_DIAGNOSTIC`.  Boundary, capacity, and optional
diagnostic rows are preserved but are supporting-only and cannot become
`paper_eligible=YES`.  Expected capacity skips and unsupported shapes still
run three independent processes and must produce stable terminal records;
they are never silently removed or replaced by a measured kernel result.

Parse and check a preserved run:

```bash
python3 experiments/scripts/parse_results.py \
  --raw-root /path/to/work-online-merge-<run-id>
python3 experiments/scripts/check_reproducibility.py \
  --records /path/to/work-online-merge-<run-id>/records.json
python3 experiments/scripts/audit_instruction_trace.py \
  --trace /path/to/trace_hart_00000.dasm \
  --disassembly /path/to/objdump.txt \
  --config B2R_RVV --N 32 --D 64 \
  --output /path/to/b2r_trace_audit.json
python3 experiments/scripts/make_plots.py \
  --progressive-csv experiments/parsed/progressive_baseline.csv
```

Formal evidence additionally requires a clean committed worktree.  A dirty
run is retained as validation evidence but receives `paper_eligible=NO`.

Correctness first records bitwise-equal elements, then applies the fixed
absolute-scaled criterion
`abs(actual-reference) <= 1e-3 * max(abs(reference), 1)`.  The reported
`max_rel_error` uses that same denominator; mean absolute and L2-relative
errors, plus NaN and signed-infinity counts, are retained for every trial.

## Current measurement limitations

- The current kernel has no independent tile-size parameter.  `tile_size` and
  hardware tile granularity are therefore `NA`, not an assumed constant.
- `N` is the number of independent merge rows and `D` is the output-vector
  length per row.  They are not automatically token count and head dimension.
- The effective RVV compatibility strip is eight FP32 elements.  The code
  intentionally caps AVL at eight because longer partial e32,m8 groups are
  incorrect in the current fixed RTL/Verilator model.
- There is no explicit DMA or input-reordering phase in the benchmark, so
  `end_to_end_cycles` is `NA` with reason `NO_EXPLICIT_TRANSFER_PHASE`.
- TCDM access and congestion event counts are available.  Directional byte
  counts and exact bank-conflict counts are not, and remain `NA`.
- `memory_footprint_bytes` includes the allocator-rounded benchmark buffers,
  two 8 KiB hart stacks, per-hart stack bank skew, and the 112-byte snRuntime
  root-team state.  Main-run capacity is gated at 80% of the configured TCDM.
- Existing generic Yosys resource results are structural proxies, not standard
  cell area, timing, power, or energy.
- The current Verilator harness exposes no max-cycle CLI plusarg.  The runner
  enforces both a per-case process-group wall-time watchdog and a declared
  post-run `max_kernel_cycles` gate; either records `TIMEOUT`.  The wall-time
  watchdog still protects hangs, while a true in-simulator cycle abort remains
  a documented follow-up.
- Plot rendering uses the Python backend and requires `matplotlib` and
  `numpy`.  The current environment has `numpy` but not `matplotlib`; the
  plotting source is provided, but rendering is intentionally blocked until
  that pinned experiment environment supplies the missing package.
