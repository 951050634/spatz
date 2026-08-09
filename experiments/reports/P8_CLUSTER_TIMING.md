# P8 — Cluster-Level Timing Status

## Final STOP evidence and availability

P8 requires baseline/A1/A2 cluster critical delay and Fmax.  Those values are
**unavailable**.  The final captured flow passed full SystemVerilog
elaboration, then completed `proc`, `opt`, and `memory_collect`; it reached
`18. Executing FLATTEN pass` and exited `137` during resource/OOM pressure.
The exact scripts, logs, statistics, host-path-specific flist, and concise
hash-anchored excerpt are preserved in `experiments/synthesis/p6-stop/`.

Consequently, no cluster critical path, cluster Fmax, timing closure, or
cluster frequency claim is made.  In particular, standalone Fmax does not
establish a cluster frequency limit or an achievable cluster frequency.

## Available standalone timing evidence

P7 provides only timing-driven standalone SMU estimates:

- A1 Scalar SMU + existing RVV: critical delay **12,342.85 ps**, estimated
  standalone Fmax **81.0186 MHz**;
- A2 Full-Offload Ablation: critical delay **13,202.60 ps**, estimated
  standalone Fmax **75.7427 MHz**.

These estimates are pre-layout ABC `stime` values with no clock tree, routing,
or output load.  They are not cluster measurements.

## Common derived-performance assumption

P9–P11 use a common **81.0186 MHz iso-frequency assumption** for B2R, A1, and
A2.  Latency and throughput in those artifacts are derived from measured
cycles under this assumption; they are not measured wall time or system
throughput.  The common frequency isolates cycle effects from the separate P7
standalone timing evidence.

## Data and evidence files

- Timing CSV: `experiments/parsed/p7_timing/p7_timing.csv`
- Cluster STOP evidence: `experiments/synthesis/p6-stop/`
