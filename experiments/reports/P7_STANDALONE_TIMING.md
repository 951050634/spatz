# SUPERSEDED — P7 Standalone Timing (Do Not Use for Paper)

This historical report is retained for provenance only.  Its old inverse-delay
MHz values are withdrawn after the P7-R synchronous timing audit.  The active
timing source is `experiments/parsed/final_timing.csv`, backed by
`experiments/parsed/p7r_timing/p7r_path_summary.csv` and
`experiments/reports/P7R_SYNCHRONOUS_TIMING_AUDIT.md`.

## Active policy

P7-R recovers both old ABC paths as registered-boundary paths:

| Design | Classification | Delay proxy | Synchronous Fmax |
| --- | --- | ---: | --- |
| A1 — Scalar SMU + existing RVV | reg→reg | 12,342.85 ps (12.34285 ns) | UNAVAILABLE |
| A2 — Full-Offload ablation | reg→reg | 13,202.60 ps (13.20260 ns) | UNAVAILABLE |

These are pre-layout Nangate45/ABC `stime` combinational-delay proxies only.
They omit clock-to-Q, setup/hold, skew, I/O constraints, and physical load or
buffer semantics.  Do not convert them to frequency or use them as cluster
timing, signoff timing, or achievable Fmax.

The previous `p7_timing.csv` and this report are listed in
`experiments/parsed/SUPERSEDED_EVIDENCE.md`; no historical artifact was
deleted.
