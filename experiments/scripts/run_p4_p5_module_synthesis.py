#!/usr/bin/env python3
"""P4/P5 scope-synthesis module area decomposition for the Online Merge SMU.

The P0-6 mapped netlists are flattened, so exact per-module areas are not
recoverable from the C1/C2 artifacts.  Per the engineering plan (P5-4) this
script uses a scope-synthesis proxy: the exp LUT, reciprocal LUT, and the
standalone vector merge datapath are each synthesized as an independent top
with the exact same versioned Nangate45 flow used by P0-6
(hw/ip/online_merge/synth/nangate45_area.ys.in, abc -fast).  The scalar
control/datapath/interface remainder is then deduced as C1 - EXP - RECIP and
the Full vector path as C2 - C1.  These are non-additive structural
decomposition aids, not an exact hierarchy accounting.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
LIBERTY = Path(
    "/home/wxt/yosys-sta/pdk/nangate45/lib/Nangate45_typ.lib"
)
YOSYS = Path("/home/wxt/yosys-sta/oss-cad-suite/bin/yosys")
FLOW_TEMPLATE = REPO_ROOT / "hw/ip/online_merge/synth/nangate45_area.ys.in"

SRC_FILES = (
    "hw/ip/online_merge/src/online_merge_fp32_helpers.sv",
    "hw/ip/online_merge/src/online_merge_exp_approx.sv",
    "hw/ip/online_merge/src/online_merge_recip_approx.sv",
    "hw/ip/online_merge/src/online_merge_update_engine.sv",
    "hw/ip/online_merge/synth/online_merge_resource_wrapper.sv",
)

# (top, requires) - requires lists which source files are needed by the top
# (all sources are read anyway; this documents the dependency for the report).
TOPS = (
    ("online_merge_exp_resource_top", "exp_approx"),
    ("online_merge_reciprocal_resource_top", "recip_approx"),
    ("online_merge_vector_resource_top", "vector_resource"),
)
TRIALS = 3


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def numeric(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} is not numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{field} is not finite and nonnegative")
    return result


def parse_stat(payload: dict[str, Any], top: str) -> dict[str, Any]:
    modules = payload.get("modules")
    design = payload.get("design")
    if not isinstance(modules, dict) or not isinstance(design, dict):
        raise ValueError("mapped stat lacks modules/design objects")
    normalized = {str(name).lstrip("\\") for name in modules}
    if top not in normalized:
        raise ValueError(f"mapped stat lacks expected top {top}")
    count = design.get("num_cells")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("invalid num_cells")
    if count:
        area = numeric(design.get("area"), "mapped area")
        seq_area = numeric(design.get("sequential_area", 0.0), "seq area")
    else:
        area = 0.0
        seq_area = 0.0
    if seq_area > area:
        raise ValueError("sequential area exceeds total")
    return {
        "mapped_cell_count": count,
        "mapped_cell_area": area,
        "sequential_cell_area": seq_area,
        "combinational_cell_area": area - seq_area,
    }


def run_trial(work_dir: Path, top: str, trial: int) -> dict[str, Any]:
    trial_dir = work_dir / top / f"trial-{trial}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    flow = FLOW_TEMPLATE.read_text(encoding="utf-8").replace(
        "@LIBERTY@", str(LIBERTY)
    )
    flow_path = trial_dir / "flow.ys"
    flow_path.write_text(flow, encoding="utf-8")
    sources = " ".join(str(REPO_ROOT / src) for src in SRC_FILES)
    cmd = (
        f"{YOSYS} -Q -m slang -p "
        f"\"read_liberty -lib {LIBERTY}; read_slang --std 1800-2017 {sources}; "
        f"hierarchy -check -top {top}; script {flow_path}\""
    )
    log_path = trial_dir / "yosys.log"
    started = time.time()
    result = subprocess.run(
        cmd, shell=True, cwd=trial_dir, capture_output=True, text=True, timeout=1800
    )
    elapsed = time.time() - started
    log_path.write_text(result.stdout, encoding="utf-8")
    stat_json = trial_dir / "mapped-stat.json"
    if not stat_json.is_file():
        raise RuntimeError(f"trial {top}/{trial} produced no mapped-stat.json")
    payload = json.loads(stat_json.read_text(encoding="utf-8"))
    summary = parse_stat(payload, top)
    summary["trial"] = trial
    summary["elapsed_s"] = round(elapsed, 2)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path,
                        default=REPO_ROOT / "work-module-area")
    parser.add_argument("--output-dir", type=Path,
                        default=REPO_ROOT / "experiments" / "parsed" / "p4_p5")
    args = parser.parse_args()

    work_dir = args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    version = subprocess.run(
        [str(YOSYS), "-V"], capture_output=True, text=True, check=True
    ).stdout.strip().splitlines()[-1]

    rows: list[dict[str, Any]] = []
    for top, role in TOPS:
        trial_rows = []
        for trial in range(1, TRIALS + 1):
            trial_rows.append(run_trial(work_dir, top, trial))
        areas = {row["mapped_cell_area"] for row in trial_rows}
        exact = len(areas) == 1
        if not exact:
            raise RuntimeError(
                f"{top} trials are not exactly reproducible: {areas}"
            )
        rows.append(
            {
                "module": top,
                "role": role,
                "trials": TRIALS,
                "exact_reproducible": exact,
                **trial_rows[0],
            }
        )

    manifest = {
        "schema_version": 1,
        "title": "P4/P5 scope-synthesis module area proxy",
        "yosys_version": version,
        "liberty": str(LIBERTY),
        "liberty_sha256": sha256_file(LIBERTY),
        "flow_template": str(FLOW_TEMPLATE.relative_to(REPO_ROOT)),
        "flow_template_sha256": sha256_file(FLOW_TEMPLATE),
        "sources": {
            src: sha256_file(REPO_ROOT / src) for src in SRC_FILES
        },
        "trial_count": TRIALS,
        "all_exact_reproducible": all(r["exact_reproducible"] for r in rows),
        "rows": rows,
        "note": (
            "Unconstrained pre-layout Nangate45 Liberty cell-area proxy; "
            "non-additive structural decomposition aid only."
        ),
    }
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Build the module area table, referencing the frozen P0-6 C1/C2 totals.
    p0_6 = json.loads(
        (REPO_ROOT / "experiments" / "parsed" / "p0_6" / "p0_6_analysis.json")
        .read_text(encoding="utf-8")
    )
    summaries = {
        row["config_id"]: row
        for row in p0_6.get("synthesis_summary", [])
        if "config_id" in row
    }
    c1_area = float(summaries["C1_SCALAR"]["mapped_cell_area"])
    c1_cells = int(summaries["C1_SCALAR"]["mapped_cell_count"])
    c2_area = float(summaries["C2_FULL"]["mapped_cell_area"])
    c2_cells = int(summaries["C2_FULL"]["mapped_cell_count"])

    by_role = {row["role"]: row for row in rows}
    exp_area = by_role["exp_approx"]["mapped_cell_area"]
    recip_area = by_role["recip_approx"]["mapped_cell_area"]
    vector_area = by_role["vector_resource"]["mapped_cell_area"]

    table_rows = [
        ("EXP (exp LUT proxy)", "exp_approx", exp_area,
         by_role["exp_approx"]["mapped_cell_count"]),
        ("Reciprocal (recip LUT proxy)", "recip_approx", recip_area,
         by_role["recip_approx"]["mapped_cell_count"]),
        ("Scalar control+datapath+interface (deduced)", "C1 - EXP - RECIP",
         c1_area - exp_area - recip_area, None),
        ("Full vector path (deduced)", "C2 - C1", c2_area - c1_area, None),
        ("Vector merge datapath (standalone proxy)", "vector_resource_top",
         vector_area, by_role["vector_resource"]["mapped_cell_count"]),
    ]

    import csv

    csv_path = args.output_dir / "p4_p5_module_area.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["module", "basis", "mapped_cell_area", "mapped_cell_count"]
        )
        for name, basis, area, cells in table_rows:
            writer.writerow([name, basis, area, "" if cells is None else cells])
    print(f"wrote {csv_path}")
    for name, basis, area, cells in table_rows:
        print(f"{name:48s} {basis:24s} {area:12.3f} {cells}")
    print(f"C1_SCALAR total = {c1_area} ({c1_cells} cells)")
    print(f"C2_FULL   total = {c2_area} ({c2_cells} cells)")
    print(f"Full/Scalar ratio = {c2_area / c1_area:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
