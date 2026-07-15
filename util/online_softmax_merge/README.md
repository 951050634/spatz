# Online Softmax Merge Experiment Runner

This runner implements the common measurement and preservation protocol from
`docs/online-softmax-merge-engine/需要补充的若干实验内容.md`.
It currently drives the compact-buffer B1/B2-R/B3 benchmark.  B2-R reuses the
RTL-aligned scalar weight calculation and performs the `O[D]` update with a
VLA RVV kernel.  Later experiment stages extend the same record and artifact
conventions.

## Prerequisites

Configure the software build once for the selected simulator.  The default
cluster configuration is:

```text
hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson
```

The target benchmark reserves 8 KiB of stack per core by defining
`snrt_stack_size = 13`.  Its three implementations' measured-result arrays
make the main frame larger than the runtime's 1 KiB default; the larger stack
keeps the two cores' frames disjoint.  The compact data allocation remains
independently limited to 70% of the 128 KiB TCDM.

## Run one case

Run from the repository root.  Results must be outside the Git worktree and
the result directory basename must start with `work-online-merge-`:

```bash
cluster="$PWD/hw/system/spatz_cluster"
python3 util/online_softmax_merge/run_experiments.py \
  --repo-root "$PWD" \
  --source-dir "$cluster/sw" \
  --build-dir "$cluster/sw/build" \
  --simulator "$cluster/bin/spatz_cluster.vlt" \
  --cfg "$cluster/cfg/spatz_cluster.default.dram.hjson" \
  --work-dir "$(dirname "$PWD")/work-online-merge-smoke" \
  --case 1,1,1,main,1800 \
  --repeats 5 \
  --jobs 8
```

A command-line case has the form:

```text
N,D[,seed[,case-kind[,timeout-seconds]]]
```

Alternatively, `--case-file cases.json` accepts a JSON array:

```json
[
  {
    "N": 8,
    "D": 32,
    "seed": 1,
    "case_kind": "main",
    "repeats": 5,
    "timeout_seconds": 1800
  }
]
```

`repeats` must be between 3 and 16.  Each case performs one unmeasured warm-up
and retains every measured repeat.  The default per-case timeout is 30 minutes;
cases with `N * D >= 1024` use the 60-minute large-case timeout unless the case
provides an explicit timeout.

Use `--no-configure` or `--no-build` only when the existing build is known to
match the requested case.  Before execution, the runner copies the exact ELF
into the case result directory.

Every runnable case also passes an LLVM `objdump` gate before simulation.  The
saved `online_merge_rvv_update` disassembly must contain `vsetvli`, two vector
loads, FP32 vector multiply/FMA, and a vector store.  A missing symbol,
undecoded instruction, or missing required mnemonic is retained as
`tool_error`; B2-R results are never accepted without this target-code proof.

## Capacity and status semantics

The host and target both check the reference-inclusive compact footprint:

```text
footprint = N * (32 + 16D) bytes
allocation = round_up(footprint, 256 bytes)
```

An allocator-rounded size above 91,750 bytes becomes `capacity_skip`.  No
simulator is started for that case.  Final record status is one of:

```text
pass, correctness_fail, timeout, capacity_skip, unsupported, tool_error
```

A host timeout or nonzero simulator exit overrides a target-side `pass`.
When a timed-out process emitted a complete target result set, the runner keeps
its cycles and correctness metrics, records `target_status`, and sets final
`status` to `timeout`.  The simulator runs in a separate process group; timeout
handling sends `TERM`, then `KILL` if necessary.

## Outputs

The runner updates small metadata files after every case:

- `records.csv` and `records.json`: one row per implementation and repeat;
- `summary.json`: median/min/max cycles and retained status counts;
- `failures.json`: parse, correctness, timeout, and validation details;
- `commands.json`: exact argv, time window, return code, status, and log path;
- `artifact_manifest.json`: path, SHA256, commit, CFG hash, tool version, and
  workload/window for the CFG, simulator, exact ELF, logs, and traces;
- `run_manifest.json`: fixed context, cases, tool versions, wall-clock window,
  validation result, limitations, and artifact index.

JSON serialization rejects NaN and infinity.  The runner derives 64-bit cycles
from `cycles_hi` and `cycles_lo`, computes RMSE from the retained sum of squared
errors, and keeps the required cycle/element and congestion ratios.

Large logs, `.dasm`, `.rtlbinary`, VCD/FST, ELFs, and other generated artifacts
must stay in the external `work-online-merge-*` directory.  Do not add them to
Git.  A run with `git_dirty=true` is diagnostic validation only; formal evidence
must be rerun from a clean committed worktree.

## Validation

```bash
PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest discover -s util/online_softmax_merge/tests -v

git diff --check
```

For the correctness path, additionally verify that the target compiler did not
reintroduce scalar division:

```bash
elf=hw/system/spatz_cluster/sw/build/spatzBenchmarks/\
test-spatzBenchmarks-online-softmax-merge
install/llvm/bin/llvm-objdump -d --no-show-raw-insn \
  "$elf" \
  | awk '/<check_output>:/,/^$/' \
  | grep '\bfdiv\.s\b'
```

No output from the final command is the expected result.

The runner performs the RVV instruction check automatically.  It can also be
inspected directly:

```bash
elf=hw/system/spatz_cluster/sw/build/spatzBenchmarks/\
test-spatzBenchmarks-online-softmax-merge
install/llvm/bin/llvm-objdump -d --no-show-raw-insn --mattr=+v "$elf" \
  | awk '/<online_merge_rvv_update>:/,/^[0-9a-fA-F]+ <.*>:$/'
```
