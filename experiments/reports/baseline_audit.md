# Strong Software Baseline Audit

## Evidence status

Static disassembly and dynamic DASM evidence are retained; the auxiliary counter profile additionally records hardware retired events. A result is not promoted to paper-eligible B2-R evidence until the gated dynamic DASM audit records retired RVV instructions.

## B1 versus B2-R

| `(N,D)` | B1 cycles | B2-R cycles | B1/B2-R | Status |
| --- | ---: | ---: | ---: | --- |
| `(1, 1)` | 2065 | 1713 | 1.20549 | PASS |
| `(8, 32)` | 96853 | 13111 | 7.38716 | PASS |
| `(16, 64)` | 372649 | 27302 | 13.6491 | PASS |

## Code-generation gates

| Config | `(N,D)` | vsetvli | RVV loads | RVV math | RVV stores | Retired RVV | Dynamic trace |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| B1_SCALAR | `(1,1)` | 0 | 0 | 0 | 0 | 0 | YES |
| B2R_RVV | `(1,1)` | 1 | 2 | 2 | 1 | 6 | YES |
| B1_SCALAR | `(8,32)` | 0 | 0 | 0 | 0 | 0 | YES |
| B2R_RVV | `(8,32)` | 1 | 2 | 2 | 1 | 192 | YES |
| B1_SCALAR | `(16,64)` | 0 | 0 | 0 | 0 | 0 | YES |
| B2R_RVV | `(16,64)` | 1 | 2 | 2 | 1 | 768 | YES |

## Cycle attribution

DASM retirement intervals are grouped by instruction category and proportionally scaled to the authoritative kernel-cycle window. These are attribution estimates, not independent per-block hardware counters.

| Config | `(N,D)` | Scalar recurrence | RVV | Load/store | Loop/control | Synchronization | Other |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B1_SCALAR | `(1,1)` | 36.7% | 0.0% | 11.9% | 33.0% | 0.3% | 18.1% |
| B2R_RVV | `(1,1)` | 35.5% | 0.8% | 12.3% | 31.7% | 0.3% | 19.4% |
| B1_SCALAR | `(8,32)` | 36.1% | 0.0% | 3.2% | 29.8% | 0.0% | 30.9% |
| B2R_RVV | `(8,32)` | 35.2% | 1.6% | 7.8% | 27.9% | 0.0% | 27.4% |
| B1_SCALAR | `(16,64)` | 34.9% | 0.0% | 2.6% | 30.8% | 0.0% | 31.7% |
| B2R_RVV | `(16,64)` | 34.2% | 2.8% | 6.7% | 27.0% | 0.0% | 29.3% |

## Remaining B2-R bottleneck

- `(1,1)`: the largest attributed component is scalar recurrence (35.5%).
- `(8,32)`: the largest attributed component is scalar recurrence (35.2%).
- `(16,64)`: the largest attributed component is scalar recurrence (34.2%).

## Interpretation boundary

- B1 must have zero RVV instructions in its measured scalar symbol.
- B2-R must pass both static RVV and dynamic retired-RVV gates.
- The current AVL cap of eight is a documented tail-correctness compatibility constraint, not a claimed optimum.
- Missing dynamic trace evidence is reported as pending and never converted to a zero count.
