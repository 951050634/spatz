# P0-4 Scaling and Boundary Report

This report contains only measured Verilator cycle proxies.  Boundary
and capacity evidence is retained as supporting-only and is excluded
from headline performance and model fits.

## Validation

- Indexed roots: 17
- Raw records: 588
- Failure entries: 0
- Validation issues: 0
- Paper-eligible raw rows: 276

## Scaling model

The exact least-squares form is `C = C0 + Cs*N + Cv*N*D`; the
per-point residual is reported separately as `Cstall`.

| Config | Points | C0 | Cs/row | Cv/element | R² |
| --- | ---: | ---: | ---: | ---: | ---: |
| B2R_RVV | 23 | 153.477363 | 1594.233808 | 2.086684 | 0.999946203 |
| A2_SMU_FULL | 23 | 1285.577085 | 19.317262 | 8.029465 | 0.999987011 |

## Directly measured break-even

`A2_SMU_FULL <= B2R_RVV`; no fitted prediction is mixed into
this table.

| N | Minimum measured D | Satisfying measured D values |
| ---: | ---: | --- |
| 1 | 1 | 1, 8, 16, 32 |
| 2 | 1 | 1, 8, 16, 32 |
| 4 | 1 | 1, 8, 16, 32 |
| 8 | 1 | 1, 8, 16, 32 |

## Boundary and capacity status

| Evidence class | Summary rows | Status counts |
| --- | ---: | --- |
| FUNCTIONAL_BOUNDARY | 68 | PASS=64, UNSUPPORTED_SHAPE=4 |
| CAPACITY_PROBE | 36 | PASS=28, SKIPPED_MEMORY_LIMIT=8 |
