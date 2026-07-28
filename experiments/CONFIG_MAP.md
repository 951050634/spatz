# Experiment Configuration Map

This map names actual implementations.  Aliases never create additional rows
or independent measurements.

| Canonical configuration | Current label | Recurrence | `O[D]` update | Alias policy |
| --- | --- | --- | --- | --- |
| `B1_SCALAR` | `B1` | Scalar software using the RTL-aligned fixed-point approximation | Scalar software | none |
| `B2R_RVV` | `B2-R` | Same scalar software recurrence as B1 | VLA RVV kernel | `A0` is an alias |
| `A1_SMU_SCALAR` | `A1` | SMU mode 1, with weights written to TCDM | Same RVV kernel as B2-R | none |
| `A2_SMU_FULL` | `B3` | SMU mode 0 | SMU vector stream | `A2` is an alias |
| `EXP_ONLY` | absent | not implemented | not implemented | no data permitted |

## Actual code paths

- B1 calls `online_merge_rtl_reference()`.
- B2-R calls `online_merge_b2_r()`, which uses
  `online_merge_rvv_update()` for each row.
- A1 programs the cluster-local MMIO register interface with mode 1, waits for
  SMU scalar completion, then calls the same RVV update used by B2-R.
- B3 programs mode 0 and waits for the full SMU update to complete.

The public paper-facing name for B3 is `A2_SMU_FULL`; raw target output keeps
`B3` so historical logs remain parseable.

## Semantic boundary

The target merges `N` independent pairs of online-softmax states.  For every
row it consumes old/tile `m`, `l`, and `O[D]`, then produces merged `m`, `l`,
and `O[D]`.  It does not calculate `QK^T`, does not execute a complete attention
row, and does not run a complete model.

The current paths process exactly the requested logical shape: RVV strip-mines
the tail with a capped AVL and the SMU iterates `elem < D`.  No hidden padding
is applied, so `padded_N=logical_N`, `padded_D=logical_D`, and
`padding_ratio=1`.  Non-divisible `D` values remain explicit smoke cases.
