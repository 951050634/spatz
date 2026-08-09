# P6 — Cluster-Level Area Status

## Status and final STOP evidence

Cluster mapped area and cluster overhead are **unavailable**.  The final
reviewable attempt is preserved under `experiments/synthesis/p6-stop/`:

- full SystemVerilog elaboration passed with the captured host-path-specific
  Bender flist (`cluster_bb.f`); `elab_bb3.log` and `elab-stat.json` record the
  `spatz_cluster_wrapper` hierarchy and 467,110 elaborated cells;
- `proc`, `opt`, and `memory_collect` completed in the synthesis attempt;
- the attempt reached `18. Executing FLATTEN pass`, then exited with `137`
  (resource/OOM stop), before mapped cluster PPA was produced;
- the 108 MB raw log is intentionally not committed.  Its SHA-256 is recorded
  in `experiments/synthesis/p6-stop/flatten_oom_evidence.txt`.

This STOP evidence does not provide a cluster area, cluster overhead, cluster
critical delay, or cluster Fmax result.  No numeric cluster value is inferred.

## Exact standalone SMU area (P0-6)

| Config | Mapped cells (P0-6 standalone) | Mapped area (P0-6 Liberty units) | Cluster area status |
| --- | ---: | ---: | --- |
| C0_NONE | 0 | 0.000 | unavailable |
| A1_SMU_SCALAR — Scalar SMU + existing RVV | 73,505 | 77,103.292 | unavailable |
| A2_SMU_FULL — Full-Offload Ablation | 107,372 | 114,713.298 | unavailable |

The formal area comparison is standalone and P0-6 only: A2/A1 mapped area is
1.4878×, A2 is 48.8% larger, and A1 is 32.8% smaller.  These are not
cluster-level overhead percentages.

## Data files

- CSV: `experiments/parsed/p6_cluster/p6_cluster_area.csv`
- Generator: `experiments/scripts/derive_p6_cluster_area.py`
- STOP evidence: `experiments/synthesis/p6-stop/`
