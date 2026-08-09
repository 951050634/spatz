#!/usr/bin/env python3
"""P6 cluster-level area status and standalone SMU area.

Full-cluster mapped synthesis is unavailable after the final STOP evidence.
This output therefore reports only exact standalone SMU mapped results from
P0-6 and carries an explicit unavailable cluster status.  No cluster-area or
overhead value is derived.
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
P06 = REPO_ROOT / "experiments" / "parsed" / "p0_6" / "p0_6_synthesis_summary.csv"
OUT_DIR = REPO_ROOT / "experiments" / "parsed" / "p6_cluster"
OUT_CSV = OUT_DIR / "p6_cluster_area.csv"


def main() -> int:
    rows = {}
    with P06.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[r["config_id"]] = r
    scalar = float(rows["C1_SCALAR"]["mapped_cell_area"])
    full = float(rows["C2_FULL"]["mapped_cell_area"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = [["kind", "config", "mapped_cell_count",
            "mapped_area_liberty_units", "cluster_area_status", "note"]]
    out.append(["standalone_increment", "C1_SCALAR",
                rows["C1_SCALAR"]["mapped_cell_count"], f"{scalar:.3f}",
                "UNAVAILABLE",
                "exact P0-6 3-trial standalone SMU result; no cluster overhead"])
    out.append(["standalone_increment", "C2_FULL",
                rows["C2_FULL"]["mapped_cell_count"], f"{full:.3f}",
                "UNAVAILABLE",
                "exact P0-6 3-trial standalone SMU result; no cluster overhead"])
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(out)
    print(f"wrote {OUT_CSV}")
    print(f"Scalar standalone area = {scalar:.3f}, Full standalone area = "
          f"{full:.3f}, Full/Scalar = {full/scalar:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
