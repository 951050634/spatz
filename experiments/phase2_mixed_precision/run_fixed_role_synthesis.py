#!/usr/bin/env python3
"""Small fixed-role area/timing runner for the Phase-2 evidence set.

The runner deliberately writes all Yosys work products outside the repository
and only appends compact records under the new Phase-2 result directory.  It
does not touch the historical P0/P7 parsed files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
YOSYS = Path("/home/wxt/yosys-sta/oss-cad-suite/bin/yosys")
LIBERTY = Path("/home/wxt/yosys-sta/pdk/nangate45/lib/Nangate45_typ.lib")
FLOW_TEMPLATE = ROOT / "hw/ip/online_merge/synth/nangate45_area.ys.in"
SOURCES = (
    "hw/ip/online_merge/src/online_merge_fp32_helpers.sv",
    "hw/ip/online_merge/src/online_merge_exp_approx.sv",
    "hw/ip/online_merge/src/online_merge_recip_approx.sv",
    "hw/ip/online_merge/src/online_merge_update_engine.sv",
    "hw/ip/online_merge/synth/online_merge_resource_wrapper.sv",
    "hw/ip/online_merge/synth/online_merge_mapped_wrapper.sv",
)
ROLES = {
    "LEGACY_SCALAR": "online_merge_legacy_scalar_mapped_top",
    # Phase-2 compatibility role retained for the original mixed baseline.
    "MIXED_SCALAR_ONLY": "online_merge_mixed_scalar_mapped_top",
    # Reciprocal-normalization comparison points.  These keep the same
    # scalar-only interface and fixed mode as MIXED_SCALAR_ONLY; only the
    # compile-time normalization implementation changes.
    "MIXED_SCALAR_DIVISION": "online_merge_mixed_division_scalar_mapped_top",
    "MIXED_SCALAR_RECIPROCAL": "online_merge_mixed_reciprocal_scalar_mapped_top",
    "DUAL_SCALAR": "online_merge_dual_scalar_mapped_top",
    "LEGACY_FULL": "online_merge_legacy_full_mapped_top",
}
TIMING_TARGET_PS = 1500
TIMING_SCRIPT = (
    "+strash; if -K 6; dretime; map -D {target}; &get -n; &st; &dch; "
    "&nf; &put; stime -p 5; print_stats -m"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_manifest() -> dict[str, Any]:
    files = [FLOW_TEMPLATE, LIBERTY, YOSYS]
    files.extend(ROOT / relative for relative in SOURCES)
    plugin = YOSYS.parent.parent / "share/yosys/plugins/slang.so"
    launcher = YOSYS.parent.parent / "libexec/yosys"
    files.extend((plugin, launcher))
    return {
        str(path): {"exists": path.is_file(), "sha256": sha256(path)}
        for path in files
        if path.is_file()
    }


def stat_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    design = payload.get("design")
    if not isinstance(design, dict):
        return None
    area = float(design.get("area", 0.0))
    sequential = float(design.get("sequential_area", 0.0))
    return {
        "mapped_cell_count": int(design.get("num_cells", 0)),
        "mapped_cell_area": area,
        "sequential_cell_area": sequential,
        "combinational_cell_area": area - sequential,
        "cell_types": design.get("num_cells_by_type", {}),
    }


def timing_summary(log: str) -> dict[str, Any]:
    delay = None
    paths: list[str] = []
    for line in log.splitlines():
        if "Delay =" in line:
            try:
                delay = float(line.split("Delay =", 1)[1].split()[0])
            except (IndexError, ValueError):
                pass
        if line.startswith("ABC: Path") and len(paths) < 5:
            paths.append(line.strip())
    return {
        "critical_delay_ps": delay,
        "delay_target_ps": TIMING_TARGET_PS,
        "target_met": "Cannot meet the target required times" not in log,
        "critical_path_lines": paths,
    }


def write_records(result_dir: Path, stage: str, rows: list[dict[str, Any]]) -> None:
    json_path = result_dir / f"{stage}_trials.json"
    csv_path = result_dir / f"{stage}_trials.csv"
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    fields = [
        "stage", "role", "top", "trial", "status", "elapsed_s",
        "mapped_cell_count", "mapped_cell_area", "sequential_cell_area",
        "combinational_cell_area", "critical_delay_ps", "delay_target_ps",
        "target_met", "exact_signature",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def run_one(
    stage: str,
    role: str,
    top: str,
    trial: int,
    work_root: Path,
    timeout_s: int,
) -> dict[str, Any]:
    trial_dir = work_root / stage / role / f"trial-{trial}"
    if trial_dir.exists():
        raise RuntimeError(f"refusing to overwrite {trial_dir}")
    trial_dir.mkdir(parents=True)
    if stage == "area":
        flow = FLOW_TEMPLATE.read_text(encoding="utf-8").replace(
            "@LIBERTY@", str(LIBERTY)
        )
    elif stage == "timing":
        flow = "\n".join(
            [
                "proc",
                "opt",
                "memory_collect",
                "opt_clean",
                "flatten",
                'setattr -set fsm_encoding "auto" w:*state_q',
                "fsm",
                "opt",
                "wreduce",
                "techmap",
                "opt",
                f"dfflibmap -liberty {LIBERTY}",
                (
                    f'abc -D {TIMING_TARGET_PS} -script '
                    f'"{TIMING_SCRIPT.format(target=TIMING_TARGET_PS)}" '
                    f"-liberty {LIBERTY}"
                ),
                "clean",
                "check -assert",
                f"tee -q -o mapped-stat.json stat -json -liberty {LIBERTY}",
                "write_verilog -noattr -noexpr mapped-netlist.v",
                "",
            ]
        )
    else:
        flow = "\n".join(
            [
                "proc",
                "opt",
                "memory_collect",
                "opt_clean",
                "flatten",
                'setattr -set fsm_encoding "auto" w:*state_q',
                "fsm",
                "opt",
                "opt_clean -purge",
                "clean",
                "check -assert",
                "write_verilog -noattr -noexpr elab-netlist.v",
                "",
            ]
        )
    flow_path = trial_dir / "flow.ys"
    flow_path.write_text(flow, encoding="utf-8")
    source_tokens = " ".join(str(ROOT / relative) for relative in SOURCES)
    invocation = (
        f"read_liberty -lib {LIBERTY}; "
        f"read_slang --std 1800-2017 {source_tokens}; "
        f"hierarchy -check -top {top}; script flow.ys"
    )
    command = [str(YOSYS), "-Q", "-m", "slang", "-p", invocation]
    started = time.monotonic()
    status = "PASS"
    error = None
    try:
        completed = subprocess.run(
            command,
            cwd=trial_dir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            status = "FAIL"
            error = f"returncode={completed.returncode}"
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        status = "TIMEOUT"
        error = f"timeout>{timeout_s}s"
    elapsed = round(time.monotonic() - started, 1)
    (trial_dir / "yosys.log").write_text(output, encoding="utf-8")
    summary = stat_summary(trial_dir / "mapped-stat.json")
    if stage != "elab" and summary is None and status == "PASS":
        status = "FAIL"
        error = "missing mapped-stat.json/design"
    row: dict[str, Any] = {
        "stage": stage,
        "role": role,
        "top": top,
        "trial": trial,
        "status": status,
        "error": error,
        "elapsed_s": elapsed,
        "command": command,
        "flow_sha256": sha256(flow_path),
        "log_sha256": sha256(trial_dir / "yosys.log"),
        "artifacts": {
            name: sha256(trial_dir / name)
            for name in (
                "mapped-stat.json", "mapped-stat.txt", "mapped-netlist.json",
                "mapped-netlist.v", "elab-netlist.v",
            )
            if (trial_dir / name).is_file()
        },
    }
    if summary is not None:
        row.update(summary)
        signature_payload = {
            key: row.get(key)
            for key in (
                "mapped_cell_count", "mapped_cell_area",
                "sequential_cell_area", "combinational_cell_area",
                "cell_types", "artifacts",
            )
        }
        row["exact_signature"] = hashlib.sha256(
            json.dumps(signature_payload, sort_keys=True).encode()
        ).hexdigest()
    if stage == "timing":
        row.update(timing_summary(output))
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=("area", "timing", "elab"), required=True
    )
    parser.add_argument("--trial-start", type=int, required=True)
    parser.add_argument("--trial-end", type=int, required=True)
    parser.add_argument("--timeout-s", type=int, default=1200)
    parser.add_argument(
        "--result-dir", type=Path,
        default=ROOT / "experiments/phase2_mixed_precision",
    )
    parser.add_argument(
        "--work-root", type=Path,
        default=Path("/tmp/om_phase2_fixed_role_synthesis"),
    )
    parser.add_argument(
        "--role", action="append", choices=tuple(ROLES),
        help="restrict the run to one or more fixed roles",
    )
    args = parser.parse_args()
    if args.trial_start < 1 or args.trial_end < args.trial_start:
        raise SystemExit("invalid trial range")
    args.result_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.result_dir / f"{args.stage}_trials.json"
    rows: list[dict[str, Any]] = []
    if result_path.exists():
        rows = json.loads(result_path.read_text(encoding="utf-8"))
    existing = {(row["role"], row["trial"]) for row in rows}
    requested_roles = args.role or list(ROLES)
    for trial in range(args.trial_start, args.trial_end + 1):
        for role in requested_roles:
            top = ROLES[role]
            if (role, trial) in existing:
                raise SystemExit(f"record already exists: {role} trial {trial}")
            print(f"{args.stage} {role} trial {trial}", flush=True)
            row = run_one(
                args.stage, role, top, trial,
                args.work_root.resolve(), args.timeout_s,
            )
            rows.append(row)
            write_records(args.result_dir, args.stage, rows)
            print(
                f"  {row['status']} elapsed={row['elapsed_s']}s "
                f"area={row.get('mapped_cell_area', 'n/a')} "
                f"delay={row.get('critical_delay_ps', 'n/a')}",
                flush=True,
            )
    meta = {
        "stage": args.stage,
        "roles": ROLES,
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip(),
        "git_dirty": bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip()),
        "yosys": str(YOSYS),
        "yosys_version": subprocess.run(
            [str(YOSYS), "-V"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "liberty": str(LIBERTY),
        "timing_target_ps": TIMING_TARGET_PS if args.stage == "timing" else None,
        "source_sha256": source_manifest(),
    }
    (args.result_dir / f"{args.stage}_manifest.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n"
    )
    return 0 if all(row["status"] == "PASS" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
