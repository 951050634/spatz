# Matched results

## Formal runs

| Case | Config path | Setup cycles | Native Core | Setup + Core | Merge | RVV update | OMERGE | SMU start/done | Selector toggles | Final hash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N8/D32 | MMIO | 991 | 72,636 | 73,627 | 1,694 | 808 | 1 | 1/1 | 1 | `0x9c7cdedc` |
| N8/D32 | OMCFG | 659 | 72,636 | 73,295 | 1,694 | 808 | 1 | 1/1 | 1 | `0x9c7cdedc` |
| N16/D64 | MMIO | 986 | 507,464 | 508,450 | 13,013 | 7,905 | 3 | 3/3 | 3 | `0xfd0d2cff` |
| N16/D64 | OMCFG | 632 | 507,476 | 508,108 | 12,983 | 7,875 | 3 | 3/3 | 3 | `0xfd0d2cff` |

All four runs exited with code 0 and reported zero errors, zero timeouts, and
zero non-finite outputs.

## Matched-pair correctness

| Case | Output words | Word-for-word equal | Pairwise MAE | Stable relative error | Cosine | Configuration state equal |
|---|---:|---:|---:|---:|---:|---:|
| N8/D32 | 256 | yes | 0 | 0 | 1 | yes |
| N16/D64 | 1,024 | yes | 0 | 0 | 1 | yes |

MMIO counts are nine ordinary field writes plus one MMIO INIT write. OMCFG
counts are ten instructions: nine field writes plus one CTRL/INIT.
