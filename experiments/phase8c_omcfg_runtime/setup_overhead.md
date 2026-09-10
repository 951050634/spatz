# One-time configuration setup overhead

The setup timer begins immediately before the first persistent configuration
operation and ends immediately after INIT completes, before the first OMERGE.
It excludes configuration-state diagnostic reads and the Native Core window.

| Case | MMIO setup | OMCFG setup | OMCFG - MMIO | OMCFG/MMIO | Reduction |
|---|---:|---:|---:|---:|---:|
| N8/D32 | 991 | 659 | -332 | 0.6650 | 33.50% |
| N16/D64 | 986 | 632 | -354 | 0.6410 | 35.90% |

The MMIO path performs nine field writes plus one MMIO INIT write. The OMCFG
path executes nine field instructions plus one CTRL/INIT instruction. Both
paths include the same runtime API-dispatch structure and have byte-identical
`.text` per shape.

## Core and setup-inclusive views

| Case | MMIO Native Core | OMCFG Native Core | Difference | MMIO setup + Core | OMCFG setup + Core | Inclusive difference |
|---|---:|---:|---:|---:|---:|---:|
| N8/D32 | 72,636 | 72,636 | 0 | 73,627 | 73,295 | -332 (-0.451%) |
| N16/D64 | 507,464 | 507,476 | +12 (+0.0024%) | 508,450 | 508,108 | -342 (-0.067%) |

The result supports a reduction in one-time configuration setup overhead. It
does not support a recurring OMERGE or whole-Attention speedup claim: OMERGE,
the SMU, and RVV are unchanged, and only one formal run per path/shape was
requested. The 12-cycle N16 steady-state difference is reported as observed
and is not attributed to OMCFG.
