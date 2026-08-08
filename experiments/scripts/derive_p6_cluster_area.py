#!/usr/bin/env python3
"""P6 cluster-level area overhead: honest incremental-area + bound derivation.

Full-cluster mapped synthesis is not achievable with the pinned Yosys+slang
toolchain (read_slang elaborates modules in isolation, so `parameter type ...
= logic` member accesses in the AXI/register_interface IP fail; the 350-file
bender flist cannot be elaborated).  We therefore report the exact standalone
SMU incremental mapped area (P0-6, 3-trial deterministic) and derive a
conservative cluster-level overhead upper bound parameterized by the baseline
cluster logic-cell count A_cluster.
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
P06 = REPO_ROOT / "experiments" / "parsed" / "p0_6" / "p0_6_synthesis_summary.csv"
OUT_DIR = REPO_ROOT / "experiments" / "parsed" / "p6_cluster"
OUT_CSV = OUT_DIR / "p6_cluster_area.csv"

# Representative baseline cluster logic-cell counts for the bound table.
# Clearly illustrative, not measured: the repo has no cluster synthesis flow.
ASSUMED_CLUSTER_CELLS = (200_000, 500_000, 1_000_000, 2_000_000)


def main() -> int:
    rows = {}
    with P06.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[r["config_id"]] = r
    scalar = float(rows["C1_SCALAR"]["mapped_cell_area"])
    full = float(rows["C2_FULL"]["mapped_cell_area"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = [["kind", "config", "cells", "mapped_area", "cluster_cells_assumed",
            "cluster_overhead_upper_bound_pct", "note"]]
    out.append(["standalone_increment", "C1_SCALAR",
                rows["C1_SCALAR"]["mapped_cell_count"], f"{scalar:.3f}", "",
                "", "exact P0-6 3-trial mapped area (incremental over C0=0)"])
    out.append(["standalone_increment", "C2_FULL",
                rows["C2_FULL"]["mapped_cell_count"], f"{full:.3f}", "",
                "", "exact P0-6 3-trial mapped area (incremental over C0=0)"])
    for a in ASSUMED_CLUSTER_CELLS:
        out.append(["overhead_bound", "C1_SCALAR", "", "", str(a),
                    f"{100.0 * scalar / a:.2f}",
                    "conservative upper bound: incremental / assumed A_cluster"])
        out.append(["overhead_bound", "C2_FULL", "", "", str(a),
                    f"{100.0 * full / a:.2f}",
                    "conservative upper bound: incremental / assumed A_cluster"])
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(out)
    print(f"wrote {OUT_CSV}")
    print(f"Scalar increment = {scalar:.1f}, Full increment = {full:.1f}, "
          f"Full/Scalar = {full/scalar:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
