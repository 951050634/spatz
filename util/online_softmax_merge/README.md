# Online Softmax Merge Experiment Runner

This runner implements the common measurement and preservation protocol from
`docs/online-softmax-merge-engine/需要补充的若干实验内容.md`.
It currently drives the compact-buffer B1/B2-R/B3 benchmark.  B2-R reuses the
RTL-aligned scalar weight calculation and performs the `O[D]` update with a
VLA RVV kernel.  Later experiment stages extend the same record and artifact
conventions.

## Prerequisites

Use either a software build already configured for the selected simulator or
the repeated `--cmake-define` options documented below.  The default cluster
configuration is:

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

## Fresh external build directories

`--cmake-define KEY=VALUE` is repeatable.  The runner appends every definition
to every configure command and records the ordered key, value, and exact `-D`
argument in `run_manifest.json`.  This permits a clean external build directory
without relying on cache state inherited from another experiment.

For `spatz_cluster.default.dram.hjson`, use these fixed CFG-derived values:

```bash
cmake_defines=(
  --cmake-define BUILD_TESTS=ON
  --cmake-define "LLVM_PATH=$PWD/install/llvm"
  --cmake-define "GCC_PATH=$PWD/install/riscv-gcc"
  --cmake-define ELEN=64
  --cmake-define MEM_DRAM_ORIGIN=2147483648
  --cmake-define MEM_DRAM_SIZE=2147483648
  --cmake-define SNRT_BASE_HARTID=0
  --cmake-define SNRT_CLUSTER_CORE_NUM=2
  --cmake-define SNRT_CLUSTER_OFFSET=0
  --cmake-define SNRT_NFPU_PER_CORE=4
  --cmake-define SNRT_TCDM_SIZE=131072
  --cmake-define SNRT_TCDM_START_ADDR=1048576
  --cmake-define PLATFORM_SOURCE_FOLDER=src/platforms/standalone
  --cmake-define SPATZ_CLUSTER_CFG=spatz_cluster.default.dram.hjson
)

build="$(dirname "$PWD")/work-online-merge-build-fresh"
results="$(dirname "$PWD")/work-online-merge-fresh"
python3 util/online_softmax_merge/run_experiments.py \
  --repo-root "$PWD" \
  --source-dir "$PWD/hw/system/spatz_cluster/sw" \
  --build-dir "$build" \
  --simulator "$PWD/hw/system/spatz_cluster/bin/spatz_cluster.vlt" \
  --cfg "$PWD/hw/system/spatz_cluster/cfg/\
spatz_cluster.default.dram.hjson" \
  --work-dir "$results" \
  --case 1,1,1,main,1800 \
  --repeats 3 \
  --jobs 2 \
  "${cmake_defines[@]}"
```

Keys must match `[A-Za-z_][A-Za-z0-9_]*`; values must be nonempty and may
contain additional `=` characters.  Duplicate keys, CMake typed-key syntax,
and these case-owned keys are rejected before the result directory is created:

```text
ONLINE_MERGE_N, ONLINE_MERGE_D, ONLINE_MERGE_SEED,
ONLINE_MERGE_CASE_KIND, ONLINE_MERGE_REPEATS
```

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
- `run_manifest.json`: fixed context, cases, ordered CMake definitions, tool
  versions, wall-clock window, validation result, limitations, and artifact
  index.

JSON serialization rejects NaN and infinity.  The runner derives 64-bit cycles
from `cycles_hi` and `cycles_lo`, computes RMSE from the retained sum of squared
errors, and keeps the required cycle/element and congestion ratios.

Large logs, `.dasm`, `.rtlbinary`, VCD/FST, ELFs, and other generated artifacts
must stay in the external `work-online-merge-*` directory.  Do not add them to
Git.  A run with `git_dirty=true` is diagnostic validation only; formal evidence
must be rerun from a clean committed worktree.

## Scaling and measured break-even analysis

After clean result batches have completed, pass every preserved result root to
`analyze_scaling.py` with a repeated `--result-root` option.  The output must be
a fresh external directory whose basename starts with `work-online-merge-`:

```bash
out="$(dirname "$PWD")/work-online-merge-scaling-analysis"
python3 util/online_softmax_merge/analyze_scaling.py \
  --repo-root "$PWD" \
  --result-root /home/user/work-online-merge-matrix-a \
  --result-root /home/user/work-online-merge-matrix-b \
  --output-dir "$out" \
  --break-even-n 1,2,4,8 \
  --break-even-d 1,8,16,32
```

Each input root must contain `run_manifest.json`, `records.json`, and
`failures.json`.  Formal analysis requires clean Git provenance, one consistent
CFG and simulator identity, and recorded validation and measurement windows.
Equivalent repeated records are deduplicated, while conflicting evidence is
rejected.  Every non-pass record and every `failures.json` entry is retained in
`analysis.json`; timeouts and other failures must not be dropped to improve the
fit.

The analyzer fits B2-R and B3 independently with exact rational least squares:

```text
C(N,D) = C0 + Cs*N + Cv*N*D + Cstall
```

`Cstall` is the signed residual at a measured coordinate, not a physical stall
counter.  The report includes exact numerator/denominator values, decimals,
SSE, SST, `R²`, cycles per element, elements per cycle, congestion, and speedup
versus B2-R.  Fitted values and residuals remain separate from the direct
break-even decision.  `break_even.csv` uses only measured median cycles and the
definition `C_smu(N,D) <= C_rvv(N,D)`; a missing cell remains missing rather
than being filled by a model prediction.

The deterministic outputs are:

- `analysis.json`: provenance, retained evidence, fit parameters, residuals,
  acceptance gates, and the directly measured break-even table;
- `model_residuals.csv`: one measured coordinate per fitted implementation;
- `break_even.csv`: the requested measured `(N,D)` grid;
- `artifact_manifest.json`: input hashes, analyzer identity, and output hashes.

## Full-SMU FSM decomposition and A0/A2 ablation

`online_merge_update_engine.sv` contains a simulation-only observer between
`translate_off`/`translate_on` pragmas.  It does not add a functional port or
feed functional RTL.  For every B3 invocation it emits one line beginning with
`OM_FSM ` followed by a JSON object.  Invocation zero is the unmeasured B3
warm-up; invocations one through `repeats` correspond to measured repeats zero
through `repeats - 1`.  The observer latches `N` and `D` at start and counts one
of these mutually exclusive `state_q` enum states on every busy cluster cycle:

```text
LOAD_SCALAR
COMPUTE_SCALAR
COMPUTE_WEIGHT
STORE_SCALAR
UPDATE_VECTOR
```

Run the three mandatory cases from one clean commit with a simulator built from
that same commit.  The build directory, result root, case file, simulator, ELF,
and logs must remain outside the Git worktree:

```bash
cat > /home/user/work-online-merge-fsm-cases.json <<'JSON'
[
  {"N": 1, "D": 1, "seed": 1, "case_kind": "main",
   "repeats": 3, "timeout_seconds": 1800},
  {"N": 8, "D": 32, "seed": 1, "case_kind": "main",
   "repeats": 3, "timeout_seconds": 1800},
  {"N": 16, "D": 64, "seed": 1, "case_kind": "main",
   "repeats": 3, "timeout_seconds": 3600}
]
JSON

python3 util/online_softmax_merge/run_experiments.py \
  --repo-root "$PWD" \
  --source-dir "$PWD/hw/system/spatz_cluster/sw" \
  --build-dir /home/user/work-online-merge-fsm-build \
  --simulator /home/user/work-online-merge-fsm-simulator/\
spatz_cluster.vlt \
  --cfg "$PWD/hw/system/spatz_cluster/cfg/\
spatz_cluster.default.dram.hjson" \
  --work-dir /home/user/work-online-merge-fsm-results \
  --case-file /home/user/work-online-merge-fsm-cases.json \
  --jobs 2 \
  "${cmake_defines[@]}"
```

Analyze the preserved runner root into a fresh controlled external directory:

```bash
python3 util/online_softmax_merge/analyze_fsm.py \
  --repo-root "$PWD" \
  --result-root /home/user/work-online-merge-fsm-results \
  --output-dir /home/user/work-online-merge-fsm-analysis
```

The analyzer requires at least three contiguous passing B2-R/A0 and B3/A2
repeats at each mandatory coordinate, one warm-up plus all measured `OM_FSM`
records, matching clean commit/CFG/simulator provenance, passing simulator
commands, finite correctness metrics, and a directly confirmed RTL enum/busy
encoding.  It emits deterministic files:

- `analysis.json`: measurement semantics, provenance, retained non-pass and
  failure evidence, acceptance gates, raw observations, per-repeat rows, and
  medians;
- `fsm_observations.csv`: warm-up and measured FSM observations;
- `fsm_breakdown.csv`: per-repeat A0/A2, state, busy, control-remainder, TCDM,
  and correctness data;
- `ablation_a0_a2.csv`: one median summary per mandatory coordinate;
- `artifact_manifest.json`: input/log/tool identities and output hashes.

The two exact per-repeat reconciliations are:

```text
LOAD_SCALAR + COMPUTE_SCALAR + COMPUTE_WEIGHT +
STORE_SCALAR + UPDATE_VECTOR = busy_cycles

busy_cycles + command_setup_wait_error_nonoverlap_cycles =
A2_end_to_end_cycles
```

FSM states do not overlap.  The core's high-frequency completion polling does
overlap SMU busy and is therefore not added to the FSM totals.  Only the
measured end-to-end remainder is labeled non-overlapped command/setup/wait/error
boundary overhead.  These Verilator cycles and TCDM counters are an ablation
and congestion measurement only; they are not area, Fmax, power, energy, or
physical-efficiency results.

## Core--SMU concurrency capture

`run_concurrency.py` builds and validates the dedicated C0/C1/C2/C3
microbenchmark.  Its default point is `(N,D)=(16,64)` with one warm-up and
three measured repeats.  C3 scans relative byte offsets
`{0,8,...,120}`, covering all 16 `addr[6:3]` bank phases.  The complete target
schedule has 148 records and 76 SMU invocations; every SMU record is paired by
invocation number with one simulation-only `OM_FSM` record.

Use fresh external build and result directories.  The simulator source path
identifies the checkout from which the exact simulator was built; a formal run
can require both source checkouts to be clean:

```bash
python3 util/online_softmax_merge/run_concurrency.py \
  --repo-root "$PWD" \
  --source-dir "$PWD/hw/system/spatz_cluster/sw" \
  --build-dir /home/user/work-online-merge-concurrency-build \
  --simulator /home/user/work-online-merge-concurrency-simulator/\
spatz_cluster.vlt \
  --simulator-source-dir \
    /home/user/work-online-merge-concurrency-simulator-source \
  --cfg "$PWD/hw/system/spatz_cluster/cfg/\
spatz_cluster.default.dram.hjson" \
  --work-dir /home/user/work-online-merge-concurrency-results \
  --n 16 --d 64 --repeats 3 --jobs 2 \
  --require-clean \
  "${cmake_defines[@]}"
```

The register-only loop must have a local back-edge and no load, store, stack
reference, or undecoded instruction.  The streaming loop must contain
`vsetvli`, `vle32.v`, `vse32.v`, a local back-edge, and no undecoded
instruction.  GNU objdump is preferred because the pinned LLVM objdump may
not decode every target RVV opcode.

The runner enforces the exact schedule, phase arithmetic, RVV tail, correctness
counts, sparse post-work polling, zero status/counter reads inside the core
window, and a C0 register/SMU calibration ratio in `[0.8,1.2]`.  Configure,
build, disassembly, and simulation have independent timeouts.  Partial target
and FSM records are retained on timeout or error.  Capacity, unsupported,
timeout, correctness, and tool failures remain explicit structured statuses.

Deterministic structured outputs include:

- `concurrency_records.{csv,json}`: raw target timing, correctness, TCDM, bank
  phase, and terminal records;
- `fsm_records.{csv,json}`: per-invocation state and busy-cycle observations;
- `concurrency_metadata.json`: target allocation and protocol metadata;
- `failures.json`: parse, validation, command, and early-terminal evidence;
- `commands.json`, `artifact_manifest.json`, and `run_manifest.json`:
  commands, hashes, Git/CFG/tool provenance, and measurement semantics.

The capture files report Verilator same-configuration runtime proxies only.
They do not support physical area, frequency, power, energy, or critical-path
claims.

## Core--SMU concurrency analysis

`analyze_concurrency.py` consumes one or more complete runner result roots.
Run it from a clean checkout at the same commit recorded by every input root.
The output directory must be a new external directory whose basename starts
with `work-online-merge-`:

```bash
python3 util/online_softmax_merge/analyze_concurrency.py \
  --repo-root "$PWD" \
  --result-root /home/user/work-online-merge-concurrency-results \
  --output-dir /home/user/work-online-merge-concurrency-analysis \
  --required-case 16,64
```

Repeat `--result-root` to combine independent passing runs.  Repeat
`--required-case N,D` when more than one coordinate is mandatory.  Result
roots are ordered canonically, so reversing otherwise identical command-line
input order does not change output bytes.  A non-passing-only root still
produces retained structured output, but the command exits nonzero because the
required-case gate is unsatisfied.

Every concurrent target record is paired with the exact `OM_FSM` invocation
named by its `smu_invocation` field.  Baselines are selected per measured
repeat:

- C1 uses `C0_SMU` and `C0_REG` from the same repeat;
- C2 uses `C0_SMU` and `C0_STREAM` from the same repeat;
- C3 uses `C0_SMU` from the same repeat and `C3_CORE` from the same phase and
  repeat.

The analyzer reports all component windows rather than only a speedup:

```text
overlap_saved_cycles = T_smu + T_core - T_concurrent
eta_overlap = overlap_saved_cycles / min(T_smu, T_core)
slowdown_smu = T_smu_concurrent / T_smu
slowdown_core = T_core_concurrent / T_core
congestion_ratio = tcdm_congested / tcdm_accessed
core_bytes_per_cycle = core_bytes / T_core_concurrent
smu_elements_per_cycle = (N * D) / T_smu_concurrent
```

Ratio decimals are accompanied by exact numerator and denominator fields.
Negative overlap is retained without clamping.  Warm-up rows use `repeat=-1`
and remain in `concurrency_observations.csv`, but only repeats `0..R-1`
contribute to medians.

C3 summaries include all 16 relative offsets.  Best and worst phases minimize
and maximize median `T_concurrent`.  The representative median phase is the
observed phase closest to the median of the 16 phase medians; ties choose the
lower `T_concurrent`, then the lower byte offset.  This is a relative
`addr[6:3]` phase comparison, not a claim that two streaming workloads occupy
disjoint banks.

The deterministic outputs are:

- `analysis.json`: metrics, exact ratios, summaries, gates, complete retained
  records/metadata/failures/commands/artifacts, and input provenance;
- `concurrency_observations.csv`: warm-up and measured C1/C2/C3 rows;
- `concurrency_summary.csv`: measured-only C1/C2/C3 medians;
- `bank_phase_summary.csv`: measured-only summaries for all 16 C3 phases;
- `retained_status_records.csv`: every raw target record, including terminal
  capacity, unsupported, timeout, correctness, and tool-error states;
- `artifact_manifest.json`: hashes of every analysis output and every input
  evidence root.

All metrics remain same-configuration RTL-simulation cycle, counter, and
throughput proxies.  They are not physical area, frequency/Fmax, power,
energy, critical-path, or physical-efficiency results.

## Yosys Slang generic-resource proxy capture

`run_resource_proxy.py` drives the versioned fixed-type synthesis tops in
`hw/ip/online_merge/synth/online_merge_resource_wrapper.sv` through the pass
sequence in `hw/ip/online_merge/synth/generic_resource.ys`.  The fixed full-SMU
top matches the default cluster's 17-bit 128 KiB TCDM byte address, 64-bit data,
eight-bit strobe, and four-bit packed TCDM user payload.  It is synthesis-only
and does not replace the functional cluster integration.

Use a fresh external result directory.  A formal capture requires a clean
checkout and defaults to independent `exp`, `reciprocal`, `vector`, and `full`
scopes:

```bash
python3 util/online_softmax_merge/run_resource_proxy.py \
  --repo-root "$PWD" \
  --work-dir \
    /home/user/work-online-merge-resource-proxy-$(date -u +%Y%m%dT%H%M%SZ) \
  --yosys /path/to/oss-cad-suite/bin/yosys \
  --timeout-seconds 600 \
  --require-clean
```

The `exp`, `reciprocal`, and `full` scopes are the acceptance-required set.
The standalone `vector` scope repeats the exact vector merge expression as a
structural decomposition aid.  Every scope is synthesized independently and
therefore its total is explicitly non-additive; independent optimization makes
subtraction an invalid way to manufacture a scalar/FSM/control residual.

The runner first records `yosys -V` and a `read_slang` plugin probe.  For every
scope it preserves the merged Yosys log, pre-techmap and post-techmap `stat`
JSON/text, and raw Yosys JSON netlists.  Incremental structured records are:

- `run_manifest.json`: Git cleanliness, tool identity, wrapper/script/config
  hashes, fixed type parameters, requested scopes, and claim boundary;
- `input_manifest.json`: every RTL, wrapper, pass script, and configuration
  reference with SHA256 and source commit;
- `scope_results.{csv,json}`: terminal status and top-level pre/post cell count
  for every requested scope;
- `failures.json`: every timeout, tool failure, missing output, and partial
  output set;
- `commands.json` and `artifact_manifest.json`: exact commands, timestamps,
  external paths, sizes, SHA256 values, source commit, tool version, and scope.

Raw JSON netlists can be tens of MiB and must remain in the external
`work-online-merge-*` directory.  A dirty capture is retained as validation but
sets `resource_proxy_evidence=false`.  The output is a version-specific generic
logic complexity proxy only.  No liberty, PDK, physical constraint, timing, or
power model is used, so these files must never be relabeled as ASIC area,
frequency/Fmax, critical path, power, energy, or physical efficiency.

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
