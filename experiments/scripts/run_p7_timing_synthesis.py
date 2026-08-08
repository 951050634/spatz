#!/usr/bin/env python3
"""P7 standalone SMU timing (ABC library-delay estimate) and Fmax.

For each fixed C1/C2 mapped top we run the same Nangate45 / Yosys / ABC flow
as P0-6, but drive ABC with explicit delay targets (-D) and record ABC's
post-map `stime` critical-path delay estimate (pre-layout, no clock tree, no
routing, no output load).  Because iEDA STA cannot ingest the flattened Yosys
netlists (parser/STA bug, not our netlist), this is the honest synthesis-level
timing source we can produce with the pinned toolchain; the report states that
caveat explicitly.  We additionally time the EXP / Reciprocal / vector-merge
scope tops (same flow) so the flat critical path can be attributed to the
scalar control/datapath rather than the specialized arithmetic.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
LIBERTY = Path("/home/wxt/yosys-sta/pdk/nangate45/lib/Nangate45_typ.lib")
YOSYS = Path("/home/wxt/yosys-sta/oss-cad-suite/bin/yosys")

SOURCES = (
    "hw/ip/online_merge/src/online_merge_fp32_helpers.sv",
    "hw/ip/online_merge/src/online_merge_exp_approx.sv",
    "hw/ip/online_merge/src/online_merge_recip_approx.sv",
    "hw/ip/online_merge/src/online_merge_update_engine.sv",
    "hw/ip/online_merge/synth/online_merge_resource_wrapper.sv",
    "hw/ip/online_merge/synth/online_merge_mapped_wrapper.sv",
)

DESIGNS = (
    ("C1_SCALAR", "online_merge_c1_scalar_mapped_top"),
    ("C2_FULL", "online_merge_c2_full_mapped_top"),
)
SCOPE_TOPS = (
    ("EXP_LUT", "online_merge_exp_resource_top"),
    ("RECIP_LUT", "online_merge_reciprocal_resource_top"),
    ("VECTOR_MERGE", "online_merge_vector_resource_top"),
)
DELAY_TARGETS_PS = (1000, 1500, 3000, 5000)
SCOPE_TARGET_PS = 1500
ABC_SCRIPT = (
    "+strash; if -K 6; dretime; map -D {target}; "
    "&get -n; &st; &dch; &nf; &put; stime -p 5; print_stats -m"
)

FLOW_TEMPLATE = """\
proc
opt
memory_collect
opt_clean
flatten
setattr -set fsm_encoding "auto" w:*state_q
fsm
opt
techmap
opt
dfflibmap -liberty {liberty}
abc -D {target} -script "{abc_script}" -liberty {liberty}
clean
check -assert
tee -q -o mapped-stat.json stat -json -liberty {liberty}
write_verilog -noattr -noexpr mapped-netlist.v
"""

DELAY_LINE = re.compile(r"Delay =\s*([\d.]+) ps")
PATH_LINE = re.compile(r"ABC: Path\s+\d+\s+--\s+(\d+)\s*:\s*\d+\s+\d+\s+([A-Za-z0-9_]+)")
AREA_FAIL = re.compile(r"Cannot meet the target required times \(([\d.]+)\)")


def parse_stat(path: Path) -> dict[str, float | int] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    design = payload.get("design")
    if not isinstance(design, dict):
        return None
    count = design.get("num_cells")
    if not isinstance(count, int) or count < 0:
        return None
    area = float(design.get("area", 0.0))
    seq = float(design.get("sequential_area", 0.0))
    return {
        "mapped_cell_count": count,
        "mapped_cell_area": area,
        "sequential_cell_area": seq,
    }


def parse_log(log: str) -> dict[str, Any]:
    delay = None
    for line in log.splitlines():
        m = DELAY_LINE.search(line)
        if m:
            delay = float(m.group(1))
    paths = [m.group(2) for m in PATH_LINE.finditer(log)][:5]
    met = not bool(AREA_FAIL.search(log))
    return {"critical_delay_ps": delay, "critical_path_gates": paths, "target_met": met}


def run_yosys(
    work_dir: Path,
    top: str,
    target_ps: int,
    label: str,
    sources: tuple[str, ...],
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    flow = FLOW_TEMPLATE.format(
        liberty=LIBERTY,
        target=target_ps,
        abc_script=ABC_SCRIPT.format(target=target_ps),
    )
    flow_path = work_dir / "flow.ys"
    flow_path.write_text(flow, encoding="utf-8")
    source_tokens = " ".join(str(REPO_ROOT / s) for s in sources)
    cmd = (
        f"{YOSYS} -Q -m slang -p "
        f"\"read_liberty -lib {LIBERTY}; read_slang --std 1800-2017 {source_tokens}; "
        f"hierarchy -check -top {top}; script flow.ys\""
    )
    started = time.time()
    result = subprocess.run(
        cmd, shell=True, cwd=work_dir, capture_output=True, text=True, timeout=3600
    )
    elapsed = time.time() - started
    (work_dir / "yosys.log").write_text(result.stdout, encoding="utf-8")
    stat = parse_stat(work_dir / "mapped-stat.json")
    timing = parse_log(result.stdout)
    if stat is None:
        raise RuntimeError(f"{label}: no mapped-stat.json produced")
    return {
        "label": label,
        "top": top,
        "delay_target_ps": target_ps,
        "elapsed_s": round(elapsed, 1),
        "mapped_cell_count": stat["mapped_cell_count"],
        "mapped_cell_area": stat["mapped_cell_area"],
        "sequential_cell_area": stat["sequential_cell_area"],
        **timing,
    }


def fmax_mhz(delay_ps: float | None) -> float | None:
    if delay_ps is None or delay_ps <= 0:
        return None
    return 1e6 / delay_ps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work-root",
        default=REPO_ROOT / "work-p7" / "p7runs",
        type=Path,
    )
    parser.add_argument(
        "--trials", type=int, default=1, help="repetitions per config (1 default)"
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="regenerate parsed CSV from existing work-p7 logs (no synthesis)",
    )
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    work_root = args.work_root

    def collect_one(label: str, top: str, target: int) -> dict:
        sub = work_root / label.replace("/", "_") / f"{target}ps"
        log = sub / "yosys.log"
        stat_path = sub / "mapped-stat.json"
        if not log.exists() or not stat_path.exists():
            raise RuntimeError(f"{label}@{target}ps: missing work-p7 artifacts")
        stat = parse_stat(stat_path)
        timing = parse_log(log.read_text(encoding="utf-8"))
        timing["fmax_mhz"] = fmax_mhz(timing["critical_delay_ps"])
        return {
            "label": label,
            "top": top,
            "delay_target_ps": target,
            "elapsed_s": "",
            "mapped_cell_count": stat["mapped_cell_count"],
            "mapped_cell_area": stat["mapped_cell_area"],
            "sequential_cell_area": stat["sequential_cell_area"],
            **timing,
        }

    def run_one(label: str, top: str, target: int, sources: tuple[str, ...]) -> dict:
        sub = work_root / label.replace("/", "_") / f"{target}ps"
        row = run_yosys(sub, top, target, f"{label}@{target}ps", sources)
        row["fmax_mhz"] = fmax_mhz(row["critical_delay_ps"])
        rows.append(row)
        print(
            f"{row['label']:>22} -D {target:>5}ps  "
            f"area={row['mapped_cell_area']:>12.3f}  "
            f"delay={row['critical_delay_ps'] if row['critical_delay_ps'] is not None else 'n/a'}ps  "
            f"fmax={row['fmax_mhz'] if row['fmax_mhz'] is not None else 'n/a'}MHz  "
            f"met={row['target_met']}  ({row['elapsed_s']}s)"
        )
        return row

    for trial in range(1, args.trials + 1):
        for label, top in DESIGNS:
            for target in DELAY_TARGETS_PS:
                if args.collect_only:
                    rows.append(collect_one(f"{label}/trial{trial}", top, target))
                else:
                    run_one(f"{label}/trial{trial}", top, target, SOURCES)
        for label, top in SCOPE_TOPS:
            if args.collect_only:
                rows.append(collect_one(f"SCOPE_{label}/trial{trial}", top, SCOPE_TARGET_PS))
            else:
                run_one(f"SCOPE_{label}/trial{trial}", top, SCOPE_TARGET_PS, SOURCES)

    out_dir = REPO_ROOT / "experiments" / "parsed" / "p7_timing"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "p7_timing.csv"
    header = [
        "label", "top", "delay_target_ps", "mapped_cell_count", "mapped_cell_area",
        "sequential_cell_area", "critical_delay_ps", "fmax_mhz", "target_met",
        "elapsed_s", "critical_path_gates",
    ]
    with csv_path.open("w", encoding="utf-8") as fh:
        fh.write(",".join(header) + "\n")
        for r in rows:
            fh.write(
                ",".join(
                    str(r.get(h, ""))
                    .replace(",", ";")
                    .replace('"', "'")
                    .replace("\n", " ")
                    if isinstance(r.get(h), (list, tuple))
                    else str(r.get(h, ""))
                    for h in header
                )
                + "\n"
            )
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
