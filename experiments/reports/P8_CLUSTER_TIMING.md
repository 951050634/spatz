# P8 — Cluster Timing Status

## Final STOP evidence and availability

P8 requires baseline/A1/A2 cluster critical delay and Fmax.  Those values are
**UNAVAILABLE**.  The captured flow elaborated the full SystemVerilog design,
then reached flatten/resource pressure and exited `137`; the exact STOP
evidence remains under `experiments/synthesis/p6-stop/`.

No cluster critical path, cluster Fmax, timing closure, physical area, power,
or energy claim is made.  Standalone delay does not establish a cluster
frequency limit or achievable cluster frequency.

## Active standalone timing boundary

P7-R supplies only PARTIAL pre-layout Nangate45/ABC reg→reg combinational-delay
proxies:

| Design | Delay proxy | Synchronous Fmax |
| --- | ---: | --- |
| A1 Scalar SMU + existing RVV | 12,342.85 ps | UNAVAILABLE |
| A2 Full-Offload ablation | 13,202.60 ps | UNAVAILABLE |

The P7-R paths are recovered from DFF Q/QN to D ownership, while ABC's `pi`/`po`
labels are not physical top-level ports.  Clock-to-Q, setup/hold, skew,
input/output constraints, and physical buffering/load are not modeled.

Absolute latency and throughput are not inferred from these delays.  Active
cycle and speedup evidence is in
`experiments/parsed/final_workload_comparison.csv`; active units and status are
frozen in `experiments/reports/FINAL_EVIDENCE_FREEZE.md`.

## Evidence files

- Cluster STOP: `experiments/synthesis/p6-stop/`
- P7-R audit: `experiments/reports/P7R_SYNCHRONOUS_TIMING_AUDIT.md`
- Active timing: `experiments/parsed/final_timing.csv`
