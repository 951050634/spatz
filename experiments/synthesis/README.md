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
