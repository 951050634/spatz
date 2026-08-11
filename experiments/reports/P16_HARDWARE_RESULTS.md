# P16 — Final Hardware Evidence

**Active evidence is limited to standalone mapped cells, Liberty cell-area
units, and PARTIAL P7-R reg→reg delay proxies.** Synchronous Fmax, absolute
latency, throughput, cluster PPA, physical timing, power, and energy are not
active claims.

## Standalone hardware table

| Metric | A1 Proposed: Scalar SMU + RVV | A2 Full-Offload ablation |
| --- | ---: | ---: |
| P0-6 mapped cells | 73,505 | 107,372 |
| P0-6 mapped area (Nangate45 Liberty units) | 77,103.292 | 114,713.298 |
| Relative area to A1 | 1.000000000000 | 1.487787291884 |
| Delta area vs A1 (Liberty units) | 0.000 | +37,610.006 |
| P7-R reg→reg delay proxy (ps) | 12,342.85 | 13,202.60 |
| P7-R synchronous Fmax | UNAVAILABLE | UNAVAILABLE |

The P0-6 rows are formal three-trial standalone synthesis evidence.  The
P7-R rows are pre-layout Nangate45/ABC combinational-delay proxies only; they
are not synchronous timing closure or cluster timing.

## Scope and roles

A1 is the Proposed Scalar SMU + existing RVV design.  A2 is Full-Offload
ablation only.  Cluster mapped area/overhead, cluster critical delay/Fmax,
physical/layout area, power, and energy remain UNAVAILABLE.

Measured cycle and speedup evidence is maintained separately in
`experiments/parsed/final_workload_comparison.csv`; no absolute latency or
throughput is copied into this hardware table.

## Data files

- Active CSV: `experiments/parsed/final_hardware_results.csv`
- Area source: `experiments/parsed/final_area.csv`
- Timing source: `experiments/parsed/final_timing.csv`
- Freeze and provenance: `experiments/reports/FINAL_EVIDENCE_FREEZE.md`
