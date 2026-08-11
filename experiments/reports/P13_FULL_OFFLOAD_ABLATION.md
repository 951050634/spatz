# P13 — Full-Offload Ablation

Full SMU remains an ablation reference only.  The Proposed design is fixed as
Scalar SMU + existing RVV; Full is not the primary architecture.

## Active M2 model evidence

| Design | Cs (cycles/row) | Cv (cycles/element) |
| --- | ---: | ---: |
| B2R_RVV | 1471.8187127369117 | 2.2670632230803 |
| A1 Proposed | 90.27815541344518 | 2.126010148452419 |
| A2 Full ablation | 19.317262422475853 | 8.029464672201952 |

Full reduces recurrence cost further, but its vector-update term is about
`3.776776267×` A1's.  This supports the conclusion that selectively
offloading the scalar recurrence preserves the efficient existing RVV path,
whereas full offload replaces it with a more expensive vector datapath.

## Active standalone area evidence

| Design | Mapped cells | Liberty area units | Relative area to A1 |
| --- | ---: | ---: | ---: |
| A1 Proposed | 73,505 | 77,103.292 | 1.000000000000 |
| A2 Full ablation | 107,372 | 114,713.298 | 1.487787291884 |

Cluster area and overhead remain UNAVAILABLE.  Timing is limited to the
PARTIAL reg→reg proxies in `experiments/parsed/final_timing.csv`; synchronous
Fmax, absolute latency, throughput, power, and energy are not active claims.

## Active source

`experiments/parsed/final_scaling_model.csv`,
`experiments/parsed/final_area.csv`, and
`experiments/parsed/final_hardware_results.csv` are the only final machine-
readable sources.  Superseded historical records are listed in
`experiments/parsed/SUPERSEDED_EVIDENCE.md`.
