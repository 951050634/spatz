# Progressive Baseline Report

`A0` is an alias of `B2R_RVV`; `B3` is the current raw label for `A2_SMU_FULL`.  Aliases are not duplicated below.

| `(N,D)` | Config | Cycles | vs B1 | vs B2-R | Reproducible | Paper eligible |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `(1,1)` | B1_SCALAR | 2065 | 1 | 0.82954 | YES | YES |
| `(1,1)` | B2R_RVV | 1713 | 1.20549 | 1 | YES | YES |
| `(1,1)` | A1_SMU_SCALAR | 1467 | 1.40763 | 1.16769 | YES | YES |
| `(1,1)` | A2_SMU_FULL | 1338 | 1.54335 | 1.28027 | YES | YES |
| `(8,32)` | B1_SCALAR | 96853 | 1 | 0.13537 | YES | YES |
| `(8,32)` | B2R_RVV | 13111 | 7.38716 | 1 | YES | YES |
| `(8,32)` | A1_SMU_SCALAR | 2497 | 38.7877 | 5.2507 | YES | YES |
| `(8,32)` | A2_SMU_FULL | 3477 | 27.8553 | 3.77078 | YES | YES |
| `(16,64)` | B1_SCALAR | 372649 | 1 | 0.0732647 | YES | YES |
| `(16,64)` | B2R_RVV | 27302 | 13.6491 | 1 | YES | YES |
| `(16,64)` | A1_SMU_SCALAR | 4778 | 77.9927 | 5.71411 | YES | YES |
| `(16,64)` | A2_SMU_FULL | 9820 | 37.948 | 2.78024 | YES | YES |

## Per-stage contribution

| `(N,D)` | B1 to B2-R | B2-R to A1 | A1 to A2 | B2-R to A2 | B1 to A2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `(1,1)` | 1.20549 | 1.16769 | 1.09641 | 1.28027 | 1.54335 |
| `(8,32)` | 7.38716 | 5.2507 | 0.718148 | 3.77078 | 27.8553 |
| `(16,64)` | 13.6491 | 5.71411 | 0.486558 | 2.78024 | 37.948 |

B1 to B2-R isolates the RVV software update; B2-R to A1 isolates scalar-recurrence offload; A1 to A2 isolates the SMU vector-update path. B2-R to A2 is the primary strong-baseline comparison.

## Supporting counters

| `(N,D)` | Config | Retired instructions | TCDM accesses | TCDM congestion | SMU utilization | Command/sync ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `(1,1)` | B1_SCALAR | 1194 | 133 | 0 | NA | NA |
| `(1,1)` | B2R_RVV | 1070 | 117 | 0 | NA | NA |
| `(1,1)` | A1_SMU_SCALAR | 769 | 396 | 0 | 1.6% | 98.4% |
| `(1,1)` | A2_SMU_FULL | 693 | 378 | 0 | 2.2% | 97.8% |
| `(8,32)` | B1_SCALAR | 73479 | 1297 | 0 | NA | NA |
| `(8,32)` | B2R_RVV | 8777 | 813 | 0 | NA | NA |
| `(8,32)` | A1_SMU_SCALAR | 1565 | 919 | 1 | 7.7% | 92.3% |
| `(8,32)` | A2_SMU_FULL | 1845 | 1591 | 21 | 64.0% | 36.0% |
| `(16,64)` | B1_SCALAR | 281210 | 4057 | 0 | NA | NA |
| `(16,64)` | B2R_RVV | 18464 | 2325 | 0 | NA | NA |
| `(16,64)` | A1_SMU_SCALAR | 3525 | 2240 | 1 | 8.1% | 91.9% |
| `(16,64)` | A2_SMU_FULL | 5109 | 5112 | 46 | 86.9% | 13.1% |

## Measurement boundary

Kernel cycles include software/RVV work, SMU MMIO command issue, busy polling, completion synchronization, and final output writeback. End-to-end cycles remain NA because this benchmark has no explicit DMA or transfer phase.

Rows failing correctness, reproducibility, code-generation, FSM, or clean-provenance gates remain in the CSV with `paper_eligible=NO`.
