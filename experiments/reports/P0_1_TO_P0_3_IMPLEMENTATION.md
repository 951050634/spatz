# P0-1 to P0-3 Implementation Status

## Scope and eligibility

The unified measurement facade, strong-software-baseline audit, and
progressive B1/B2-R/A1/A2 comparison are implemented.  No EXP-only, scaling,
model-workload, synthesis, or power experiment is claimed here.

The implementation smoke runs were made from a dirty worktree before a user
commit.  They validate the machinery but are not paper data; every such row is
retained with `paper_eligible=NO`.

## Implemented evidence chain

- Four canonical, single-implementation ELFs replace the legacy practice of
  timing all implementations in one process.  Each simulator process performs
  one unmeasured warm-up and one measured sample.
- Three fresh simulator processes are required per point.  Kernel cycles and
  the canonical target-result hash must match exactly.
- The saved input header, ELF, complete compile commands, link command,
  disassembly, symbol table, section sizes, simulator logs, DASM traces, and
  per-trace audit all receive SHA256 provenance.
- B1 is rejected if its measured scalar symbol contains RVV.  B2-R and A1 are
  rejected unless the expected VLA RVV sequence is present; B2-R additionally
  requires retired RVV instructions in the measured DASM envelope.
- A1 and A2 require exactly two SMU FSM invocations (warm-up 0 and measured 1),
  matching `N/D`, `DONE` termination, a valid busy interval, and the expected
  absence/presence of vector-update states.
- Correctness records bitwise agreement, maximum absolute and scaled-relative
  error, mean absolute error, L2-relative error, and NaN/Inf counts.
- TCDM footprint includes aligned benchmark buffers plus two 8 KiB stacks,
  stack-bank skew, and the observed 112-byte snRuntime team state.  The main
  capacity gate applies to this total at 80% of TCDM.
- Cross-configuration fairness compares CFG, simulator, input, logical and
  physical shape, padding, dirty-source snapshot, and normalized compiler
  flags.  Only the implementation selector and object output path are removed
  from the compiler comparison.

## Current diagnostic result

Preserved batch:
`work-online-merge-framework-current-all-r1-20260728`.

Shape: `(N,D)=(1,1)`, seed 1, `main` input, memory-counter profile.  All 12
runs passed; each configuration produced one exact cycle value across three
independent processes, one exact target-result hash, zero nonfinite outputs,
and the same 16,768-byte total TCDM footprint.

| Config | Cycles | vs B1 | vs B2-R | DASM RVV | TCDM accesses | SMU busy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `B1_SCALAR` | 2065 | 1.000 | 0.830 | 0 | 133 | NA |
| `B2R_RVV` | 1713 | 1.205 | 1.000 | 6 | 117 | NA |
| `A1_SMU_SCALAR` | 1467 | 1.408 | 1.168 | 6 | 396 | 24 |
| `A2_SMU_FULL` | 1338 | 1.543 | 1.280 | 0 | 378 | 29 |

The maximum absolute and scaled-relative errors were both
`1.2516975402832031e-06`; mean absolute error was
`4.172325134277344e-07`, and L2-relative error was
`3.152311533271239e-07`.

At this startup-dominated point, B2-R is 1.205x faster than B1; recurrence
offload adds 1.168x over B2-R, and the full vector-update path adds 1.096x over
A1.  The primary strong-baseline comparison, B2-R to A2, is 1.280x.  These are
diagnostic values from one tiny shape and must not be presented as paper
results or as a crossover/scaling conclusion.

The B2-R hotspot contains one `vsetvli`, two vector loads, two vector arithmetic
instructions, and one vector store statically; all six RVV instructions retire
inside the dynamic marker envelope.  The normalized main-source compiler hash
is identical across all four configurations.

## Preserved failed attempts

- `work-online-merge-framework-smoke-20260728`: configuration/build stopped
  because the original input generator rejected the new single-sample ELF.
- `work-online-merge-framework-smoke-r2-20260728`: builds passed, then the
  runner exposed a missing per-trial working-directory creation step.

Both failure directories and logs were retained.  The defects were corrected
without overwriting either batch.

## Remaining blockers before formal P0 evidence

- Commit the intended framework changes, then rerun from a clean worktree so
  `paper_eligible` can become `YES`.
- Run both memory and instruction counter profiles for all P0 anchor cases;
  the current full four-way batch is only a minimal memory-profile smoke.
- The Python plotting backend lacks `matplotlib` in the current environment.
  Plot source passes through an explicit dependency gate; no alternative
  backend or fabricated PDF was used.
- The Verilator harness has no native max-cycle abort option.  The runner uses
  a process-group wall-time watchdog plus a post-run `max_kernel_cycles` gate.
- End-to-end cycles remain `NA` because this kernel has no explicit DMA or
  input-reordering phase.  Tile size is `NA` because the current kernel has no
  independent tile parameter.

## Reproduction after a clean commit

```bash
experiments/scripts/run_smoke.sh

python3 experiments/scripts/run_performance_matrix.py \
  --case-file experiments/configs/p0_anchor_cases.json

python3 experiments/scripts/check_reproducibility.py \
  --records /path/to/work-online-merge-<run-id>/records.json

python3 experiments/scripts/parse_results.py \
  --raw-root /path/to/work-online-merge-<run-id>

python3 experiments/scripts/make_plots.py
```

`make_plots.py` must be run only after the selected, pinned Python environment
provides `matplotlib`; it rejects paper-ineligible or incomplete matrices by
default.
