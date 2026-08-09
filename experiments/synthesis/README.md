# Synthesis experiments

P0-6 compares three fixed synthesis-only tops with one identical packed
interface:

- `C0_NONE`: no SMU engine; the interface is tied off;
- `C1_SCALAR`: the production update engine fixed to scalar-only mode 1;
- `C2_FULL`: the production update engine fixed to full-update mode 0.

The comparison deliberately covers only the incremental SMU scope, not the
complete Spatz cluster.  The versioned flow maps each top independently to the
existing Nangate45 typical Liberty library three times without timing or
physical constraints.  Its accepted metric is therefore pre-layout mapped
cell area in Liberty units.  It does not support complete-cluster area,
physical area, Fmax, critical-path, timing-closure, power, or energy claims.

After constant propagation, the flow explicitly extracts the production FSM
so the scalar-only top does not retain unreachable full-update states.  It
then uses the same Yosys `abc -fast` script (`strash; dretime; map`) for all
three configurations.  The default higher-effort ABC script exceeded the
fixed 3,600-second C1 diagnostic budget; that timeout remains failure
evidence.  `-fast` trades output quality for bounded runtime, so these values
are not presented as the minimum area achievable under every mapping effort.

The open Nangate library is explicitly research-only and non-manufacturable.
The configuration catalog pins the library, Yosys executable, and Slang
plugin identities; a runner must reject mismatches rather than silently using
another tool or corner.  Existing generic-resource proxy results remain
separate and are not substituted for P0-6 mapped synthesis.

Run the complete three-process matrix from a clean committed worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  experiments/scripts/run_p0_6_synthesis.py \
  --require-clean
```

Every trial is a separate Yosys process with its own external directory,
timeout, log, rendered flow, mapped statistics, JSON netlist, and Verilog
netlist.  Failures are retained per configuration and do not suppress later
scheduled trials.  `--config-id` and `--trials` may bound a diagnostic smoke,
but only the exact three-configuration, three-trial clean run can become
paper-eligible.

After indexing the completed external root as the `p0_6` set, independently
rehash and summarize it from another clean committed state:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/scripts/analyze_p0_6.py \
  --index-set experiments/manifests/p0_6_index_set.json \
  --output-dir experiments/parsed/p0_6 \
  --require-clean
```

The analyzer reopens every mapped stat file, verifies every raw hash and
current source/tool/library identity, reconstructs the exact three-process
matrix, checks the C0/C1/C2 ordering, and emits trial, summary, and cell-type
CSV files plus a bounded synthesis report and manifest.

## Cluster STOP evidence (P6/P8)

The final cluster attempt is preserved, without rerunning synthesis, in
`experiments/synthesis/p6-stop/`.  Full SystemVerilog elaboration passed, and
the captured attempt passed proc/opt/memory_collect before reaching the
flatten pass and exiting 137 under resource/OOM pressure.  Cluster mapped area,
cluster overhead, cluster critical delay, and cluster Fmax are therefore
unavailable.  The Bender flist is an exact host-path-specific capture; the
108 MB raw synthesis log is omitted and represented by its SHA-256 in
`p6-stop/flatten_oom_evidence.txt`.
